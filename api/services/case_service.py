from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.models import AuditLogEntry, Base, PermitCase
from shared.band_client.config import load_settings
from shared.llm.backends import orchestration_hint
from shared.schemas.project_brief import ProjectBrief
from shared.tools.workflow import run_workflow_with_activity_async

logger = logging.getLogger(__name__)

settings = load_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_case(brief: ProjectBrief, demo: bool = False) -> dict[str, Any]:
    band_room_id = f"permit-case-{brief.case_id}"
    results = await run_workflow_with_activity_async(brief, band_room_id=band_room_id)
    await _save_case_results(brief, results)
    return results


async def start_case_async(brief: ProjectBrief) -> dict[str, Any]:
    """Create case row and run Band pipeline in background (avoids HTTP timeout)."""
    import asyncio

    case_id = str(brief.case_id)
    async with SessionLocal() as session:
        session.add(
            PermitCase(
                case_id=case_id,
                project_name=brief.project_name,
                status="ANALYZING",
                brief=brief.model_dump(mode="json"),
                results=None,
                band_room_id=None,
            )
        )
        await session.commit()

    asyncio.create_task(_run_case_background(brief))
    return {
        "case_id": case_id,
        "status": "ANALYZING",
        "message": "Band agents are analyzing. Poll GET /cases/{case_id} for results.",
    }


async def _update_case_progress(case_id: str, partial: dict[str, Any]) -> None:
    partial = {
        **partial,
        "last_progress_at": datetime.now(timezone.utc).isoformat(),
    }
    async with SessionLocal() as session:
        result = await session.execute(select(PermitCase).where(PermitCase.case_id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            return
        merged = dict(case.results or {})
        merged.update(partial)
        case.results = merged
        case.band_room_id = partial.get("band_room_id") or case.band_room_id
        await session.commit()


async def _run_case_background(brief: ProjectBrief) -> None:
    case_id = str(brief.case_id)
    existing_room: str | None = None
    try:
        case = await get_case(case_id)
        if case and case.band_room_id and not case.band_room_id.startswith("local-"):
            existing_room = case.band_room_id

        async def on_progress(partial: dict[str, Any]) -> None:
            await _update_case_progress(case_id, partial)

        results = await run_workflow_with_activity_async(
            brief, band_room_id=existing_room, on_progress=on_progress
        )
        await _save_case_results(brief, results)
    except Exception as exc:
        logger.exception("Pipeline failed for case %s", case_id)
        err_detail = f"{type(exc).__name__}: {exc}"[:500]
        async with SessionLocal() as session:
            result = await session.execute(select(PermitCase).where(PermitCase.case_id == case_id))
            case = result.scalar_one_or_none()
            if case:
                merged = dict(case.results or {})
                merged.update(
                    {
                        "error": orchestration_hint(),
                        "error_detail": err_detail,
                        "stalled": True,
                        "stall_reason": orchestration_hint(),
                        "last_progress_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                case.status = "FAILED"
                case.results = merged
                await session.commit()


async def _save_case_results(brief: ProjectBrief, results: dict[str, Any]) -> None:
    case_id = str(brief.case_id)
    async with SessionLocal() as session:
        result = await session.execute(select(PermitCase).where(PermitCase.case_id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            case = PermitCase(
                case_id=case_id,
                project_name=brief.project_name,
                brief=brief.model_dump(mode="json"),
            )
            session.add(case)
        case.status = str((results.get("case_summary") or {}).get("status", "AWAITING_APPROVAL"))
        case.results = results
        case.band_room_id = results.get("band_room_id") or case.band_room_id
        pkg = results.get("permit_package") or {}
        case.audit_hash = pkg.get("audit_hash")
        for evt in results.get("activity", []):
            session.add(
                AuditLogEntry(
                    case_id=case_id,
                    agent_id=evt["agent"],
                    event_type=evt["event_type"],
                    detail=evt.get("detail"),
                    payload=evt.get("payload"),
                )
            )
        await session.commit()


async def get_case(case_id: str) -> PermitCase | None:
    async with SessionLocal() as session:
        result = await session.execute(select(PermitCase).where(PermitCase.case_id == case_id))
        return result.scalar_one_or_none()


async def get_audit_log(case_id: str) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(AuditLogEntry).where(AuditLogEntry.case_id == case_id).order_by(AuditLogEntry.id)
        )
        entries = result.scalars().all()
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "agent_id": e.agent_id,
                "event_type": e.event_type,
                "detail": e.detail,
                "payload": e.payload,
            }
            for e in entries
        ]


async def simulate_rfi(case_id: str, rfi_text: str) -> dict[str, Any] | None:
    case = await get_case(case_id)
    if not case or not case.results:
        return None

    draft = (
        f"RE: {rfi_text}\n\n"
        f"Project: {case.project_name} ({case_id})\n\n"
        "Response:\n"
        "Per the approved site plan (Sheet A-2.1), Block B maintains a dedicated "
        "fire apparatus access route along the east property line with 20'-0\" clear width "
        "per Austin Fire Code 503.1.1. A supplemental access diagram is attached showing "
        "turning radii and hydrant locations.\n\n"
        "Submitted for review,\nPermitOS Packager Agent"
    )

    async with SessionLocal() as session:
        session.add(
            AuditLogEntry(
                case_id=case_id,
                agent_id="packager",
                event_type="rfi_draft",
                detail=rfi_text,
                payload={"draft": draft},
            )
        )
        await session.commit()

    return {"case_id": case_id, "rfi_text": rfi_text, "draft": draft}


async def approve_case(case_id: str, approved_by: str = "human-reviewer") -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(select(PermitCase).where(PermitCase.case_id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            return None

        case.status = "APPROVED_FOR_FILING"
        case.approved_by = approved_by
        case.approved_at = datetime.now(timezone.utc)
        session.add(
            AuditLogEntry(
                case_id=case_id,
                agent_id="human",
                event_type="approved",
                detail=f"Approved by {approved_by}",
                payload={"audit_hash": case.audit_hash},
            )
        )
        await session.commit()
        return {
            "case_id": case_id,
            "status": case.status,
            "audit_hash": case.audit_hash,
            "approved_by": approved_by,
            "approved_at": case.approved_at.isoformat(),
        }
