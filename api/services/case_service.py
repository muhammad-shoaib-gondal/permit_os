from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.models import AuditLogEntry, Base, PermitCase
from shared.band_client.config import load_settings
from shared.schemas.project_brief import ProjectBrief
from shared.tools.workflow import run_workflow_with_activity_async

settings = load_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_case(brief: ProjectBrief, demo: bool = False) -> dict[str, Any]:
    band_room_id = f"permit-case-{brief.case_id}"
    results = await run_workflow_with_activity_async(brief, band_room_id=band_room_id)

    async with SessionLocal() as session:
        case = PermitCase(
            case_id=str(brief.case_id),
            project_name=brief.project_name,
            status=results["case_summary"]["status"],
            brief=brief.model_dump(mode="json"),
            results=results,
            band_room_id=band_room_id,
            audit_hash=results["permit_package"].get("audit_hash"),
        )
        session.add(case)
        for evt in results.get("activity", []):
            session.add(
                AuditLogEntry(
                    case_id=str(brief.case_id),
                    agent_id=evt["agent"],
                    event_type=evt["event_type"],
                    detail=evt.get("detail"),
                    payload=evt.get("payload"),
                )
            )
        await session.commit()

    return results


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
