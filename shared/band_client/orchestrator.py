"""Band REST orchestration — demo runs through live Band agents only."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.band_client.config import AgentRole, band_urls, get_agent_credentials
from shared.band_client.factory import AGENT_HANDLES
from shared.band_client.messaging import iter_json_blobs, parse_band_message, unwrap_band_payload
from shared.schemas.band_message import MessageType
from shared.schemas.package import PermitPackage
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import (
    BuildingSafetyReport,
    JurisdictionReport,
    SiteEnvironmentalReport,
)
from shared.band_client.report_normalize import normalize_for_agent
from shared.llm.backends import orchestration_hint
from shared.tools.conductor import compute_audit_hash, merge_reports

logger = logging.getLogger(__name__)

SPECIALIST_ROLES = (AgentRole.JURISDICTION, AgentRole.BUILDING, AgentRole.SITE)
POLL_INTERVAL_SEC = 3.0
JOIN_WAIT_SEC = 4.0
SPECIALIST_STAGGER_SEC = 5.0

SPECIALIST_CHAIN: tuple[tuple[AgentRole, str, type], ...] = (
    (AgentRole.JURISDICTION, "jurisdiction", JurisdictionReport),
    (AgentRole.BUILDING, "building", BuildingSafetyReport),
    (AgentRole.SITE, "site", SiteEnvironmentalReport),
)


class BandOrchestrationError(RuntimeError):
    """Band room workflow failed."""


def _timeout_sec() -> float:
    return float(os.getenv("BAND_ORCHESTRATION_TIMEOUT", "600"))


def _orchestration_hint() -> str:
    return orchestration_hint()


def _rest_client(api_key: str):
    from thenvoi_rest import AsyncRestClient

    return AsyncRestClient(api_key=api_key, base_url=band_urls()["rest_url"].rstrip("/"))


def _mention_item(role: AgentRole):
    from thenvoi_rest import ChatMessageRequestMentionsItem

    agent_id, _ = get_agent_credentials(role)
    return ChatMessageRequestMentionsItem(id=agent_id, handle=AGENT_HANDLES[role])


async def _ensure_participants(conductor_key: str, room_id: str) -> None:
    """Add specialists to an existing room (idempotent)."""
    from thenvoi_rest import ParticipantRequest

    client = _rest_client(conductor_key)
    try:
        for role in (
            AgentRole.JURISDICTION,
            AgentRole.BUILDING,
            AgentRole.SITE,
            AgentRole.PACKAGER,
        ):
            agent_id, _ = get_agent_credentials(role)
            try:
                await client.agent_api_participants.add_agent_chat_participant(
                    chat_id=room_id,
                    participant=ParticipantRequest(participant_id=agent_id),
                )
            except Exception as exc:
                logger.debug("Participant %s may already be in room %s: %s", role.value, room_id, exc)
        await asyncio.sleep(JOIN_WAIT_SEC)
    finally:
        await client._client_wrapper.httpx_client.httpx_client.aclose()


async def _get_or_create_room(
    conductor_key: str, brief: ProjectBrief, existing_room_id: str | None
) -> str:
    if existing_room_id and not existing_room_id.startswith("local-"):
        logger.info("Reusing Band room %s for case %s", existing_room_id, brief.case_id)
        await _ensure_participants(conductor_key, existing_room_id)
        return existing_room_id
    return await _create_room_and_add_agents(conductor_key, brief)


async def _create_room_and_add_agents(conductor_key: str, brief: ProjectBrief) -> str:
    from thenvoi_rest import ChatRoomRequest, ParticipantRequest

    client = _rest_client(conductor_key)
    try:
        room_resp = await client.agent_api_chats.create_agent_chat(chat=ChatRoomRequest())
        room_id = room_resp.data.id
        logger.info("Band room created: %s for case %s", room_id, brief.case_id)

        for role in (
            AgentRole.JURISDICTION,
            AgentRole.BUILDING,
            AgentRole.SITE,
            AgentRole.PACKAGER,
        ):
            agent_id, _ = get_agent_credentials(role)
            await client.agent_api_participants.add_agent_chat_participant(
                chat_id=room_id,
                participant=ParticipantRequest(participant_id=agent_id),
            )
            logger.info("Added %s to room %s", role.value, room_id)

        await asyncio.sleep(JOIN_WAIT_SEC)
        return room_id
    finally:
        await client._client_wrapper.httpx_client.httpx_client.aclose()


async def _send_message(api_key: str, room_id: str, content: str, roles: list[AgentRole]) -> None:
    from thenvoi_rest import ChatMessageRequest

    client = _rest_client(api_key)
    try:
        await client.agent_api_messages.create_agent_chat_message(
            chat_id=room_id,
            message=ChatMessageRequest(
                content=content,
                mentions=[_mention_item(r) for r in roles],
            ),
        )
    finally:
        await client._client_wrapper.httpx_client.httpx_client.aclose()


def _validate_report(agent_name: str, data: dict[str, Any], model_cls: type, case_id: UUID | None):
    data = unwrap_band_payload(data)
    data = normalize_for_agent(agent_name, data, case_id)
    return model_cls.model_validate(data)


def _extract_report(
    content: str | None, agent_name: str, model_cls: type, case_id: UUID | None = None
):
    if not content:
        return None
    band_msg = parse_band_message(content)
    if band_msg and band_msg.payload:
        cid = case_id or band_msg.case_id
        if not case_id or str(band_msg.case_id) in (str(case_id), "<uuid>", "<case_id>"):
            try:
                wrapped = {
                    "type": band_msg.type.value,
                    "case_id": str(band_msg.case_id),
                    "agent": band_msg.agent,
                    "payload": band_msg.payload,
                }
                return _validate_report(agent_name, wrapped, model_cls, cid)
            except Exception as exc:
                logger.debug("Band payload validate failed for %s: %s", agent_name, exc)
    for match in iter_json_blobs(content):
        if case_id and match.get("case_id") and str(match.get("case_id")) not in (
            str(case_id),
            "<uuid>",
            "<case_id>",
        ):
            continue
        candidates: list[dict] = []
        if isinstance(match.get("payload"), dict):
            candidates.append(match)
        if match.get("agent") == agent_name or agent_name in str(match.get("agent", "")):
            candidates.append(match)
        if "checks" in match or "environmental_checks" in match or "permits_required" in match:
            candidates.append(match)
        for raw in candidates:
            try:
                return _validate_report(agent_name, dict(raw), model_cls, case_id)
            except Exception:
                continue
    return None


async def _list_messages(api_key: str, room_id: str) -> list[Any]:
    client = _rest_client(api_key)
    try:
        resp = await client.agent_api_messages.list_agent_messages(chat_id=room_id)
        return list(resp.data or [])
    finally:
        await client._client_wrapper.httpx_client.httpx_client.aclose()


async def _poll_single_report(
    api_key: str,
    room_id: str,
    agent_name: str,
    model_cls: type,
    deadline: float,
    seen: set[str],
    case_id: UUID,
) -> Any:
    while time.monotonic() < deadline:
        for msg in await _list_messages(api_key, room_id):
            msg_id = getattr(msg, "id", None) or str(msg)
            if msg_id in seen:
                continue
            seen.add(msg_id)
            content = msg.content or ""
            report = _extract_report(content, agent_name, model_cls, case_id)
            if report:
                logger.info("Received %s report from Band room %s", agent_name, room_id)
                return report
        await asyncio.sleep(POLL_INTERVAL_SEC)

    raise BandOrchestrationError(
        f"Timed out waiting for Band agent: {agent_name}. {_orchestration_hint()}"
    )


async def _dispatch_specialists_sequential(
    conductor_key: str,
    room_id: str,
    brief: ProjectBrief,
    deadline: float,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> tuple[JurisdictionReport, BuildingSafetyReport, SiteEnvironmentalReport]:
    """Dispatch one specialist at a time to avoid LLM rate limits (e.g. Cerebras 429)."""
    brief_json = brief.model_dump_json(indent=2)
    seen: set[str] = set()
    for msg in await _list_messages(conductor_key, room_id):
        seen.add(getattr(msg, "id", None) or str(msg))

    reports: dict[str, Any] = {}
    for role, agent_name, model_cls in SPECIALIST_CHAIN:
        dispatch = (
            f"PermitOS case intake — analyze with your Austin tools.\n\n"
            f"ProjectBrief:\n```json\n{brief_json}\n```\n\n"
            f"Reply via band_send_message with ```json containing "
            f'"type":"complete", "case_id":"{brief.case_id}", "agent":"{agent_name}", '
            f'"payload": {{<full report object>}}`.'
        )
        await _send_message(conductor_key, room_id, dispatch, [role])
        logger.info("Dispatched %s agent on Band (sequential)", agent_name)
        await asyncio.sleep(SPECIALIST_STAGGER_SEC)
        reports[agent_name] = await _poll_single_report(
            conductor_key, room_id, agent_name, model_cls, deadline, seen, brief.case_id
        )
        if on_progress:
            await on_progress(
                {
                    "status": "ANALYZING",
                    "brief": brief.model_dump(mode="json"),
                    "band_room_id": room_id,
                    f"{agent_name}_report": reports[agent_name].model_dump(mode="json"),
                    "completed_agents": list(reports.keys()),
                }
            )

    return reports["jurisdiction"], reports["building"], reports["site"]


async def _poll_packager(
    api_key: str, room_id: str, case_id: UUID, deadline: float
) -> PermitPackage:
    seen: set[str] = set()
    while time.monotonic() < deadline:
        for msg in await _list_messages(api_key, room_id):
            msg_id = getattr(msg, "id", None) or str(msg)
            if msg_id in seen:
                continue
            seen.add(msg_id)
            content = msg.content or ""
            sender = (getattr(msg, "sender_name", "") or "").lower()
            if "packager" not in sender and "packager" not in content.lower():
                continue
            band_msg = parse_band_message(content)
            if band_msg and band_msg.type == MessageType.COMPLETE and band_msg.payload:
                data = dict(band_msg.payload)
                data.setdefault("case_id", str(case_id))
                try:
                    pkg = PermitPackage.model_validate(data)
                    if pkg.permits_required:
                        pkg.audit_hash = compute_audit_hash(pkg)
                        return pkg
                except Exception:
                    pass
            for blob in iter_json_blobs(content):
                if "permits_required" in blob:
                    blob.setdefault("case_id", str(case_id))
                    try:
                        pkg = PermitPackage.model_validate(blob)
                        if pkg.permits_required:
                            pkg.audit_hash = compute_audit_hash(pkg)
                            return pkg
                    except Exception:
                        continue
        await asyncio.sleep(POLL_INTERVAL_SEC)

    raise BandOrchestrationError(
        f"Timed out waiting for Packager agent on Band. {_orchestration_hint()}"
    )


def _activity_from_band(
    room_id: str,
    brief: ProjectBrief,
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
    summary,
    package: PermitPackage,
) -> list[dict[str, Any]]:
    def evt(agent: str, event_type: str, detail: str, payload: dict | None = None):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "event_type": event_type,
            "detail": detail,
            "payload": payload or {},
        }

    return [
        evt("conductor", "room_created", f"Band room {room_id}", {"room_id": room_id}),
        evt("conductor", "dispatch", "Dispatched specialists on Band", {"case_id": str(brief.case_id)}),
        evt("jurisdiction", "complete", jurisdiction.summary, {"report": jurisdiction.model_dump(mode="json")}),
        evt("building", "complete", building.summary, {"report": building.model_dump(mode="json")}),
        evt("site", "complete", site.summary, {"report": site.model_dump(mode="json")}),
        evt("conductor", "merge_complete", summary.executive_summary or "", {"readiness": summary.readiness_score.value}),
        evt("packager", "complete", f"{len(package.permits_required)} permits", {"package": package.model_dump(mode="json")}),
        evt("conductor", "escalate", "Awaiting human approval", {}),
    ]


async def run_band_case(
    brief: ProjectBrief,
    existing_room_id: str | None = None,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Create or reuse Band room, dispatch live agents, poll structured responses."""
    _, conductor_key = get_agent_credentials(AgentRole.CONDUCTOR)
    deadline = time.monotonic() + _timeout_sec()

    room_id = await _get_or_create_room(conductor_key, brief, existing_room_id)
    if on_progress:
        await on_progress({"status": "ANALYZING", "band_room_id": room_id, "phase": "room_ready"})

    jurisdiction, building, site = await _dispatch_specialists_sequential(
        conductor_key, room_id, brief, deadline, on_progress=on_progress
    )
    summary = merge_reports(brief, jurisdiction, building, site, room_id)

    merge_json = json.dumps(
        {
            "jurisdiction": jurisdiction.model_dump(mode="json"),
            "building": building.model_dump(mode="json"),
            "site": site.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
        },
        indent=2,
    )
    dispatch_packager = (
        f"Assemble permit package from specialist reports. Case {brief.case_id}.\n\n"
        f"```json\n{merge_json}\n```\n\n"
        f'Reply with type=complete, agent=packager, payload=<full PermitPackage JSON> '
        f"including permits_required, filing_sequence, total_fees_estimate_usd."
    )
    await _send_message(conductor_key, room_id, dispatch_packager, [AgentRole.PACKAGER])

    package = await _poll_packager(conductor_key, room_id, brief.case_id, deadline)

    return {
        "brief": brief.model_dump(mode="json"),
        "jurisdiction_report": jurisdiction.model_dump(mode="json"),
        "building_report": building.model_dump(mode="json"),
        "site_report": site.model_dump(mode="json"),
        "case_summary": summary.model_dump(mode="json"),
        "permit_package": package.model_dump(mode="json"),
        "activity": _activity_from_band(room_id, brief, jurisdiction, building, site, summary, package),
        "band_room_id": room_id,
        "agent_driven": True,
        "band_orchestrated": True,
    }
