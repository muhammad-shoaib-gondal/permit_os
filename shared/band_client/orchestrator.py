"""Band REST orchestration — demo runs through live Band agents only."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.band_client.config import AgentRole, band_urls, get_agent_credentials
from shared.band_client.factory import AGENT_HANDLES
from shared.band_client.messaging import parse_band_message
from shared.schemas.band_message import MessageType
from shared.schemas.package import PermitPackage
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import (
    BuildingSafetyReport,
    JurisdictionReport,
    SiteEnvironmentalReport,
)
from shared.tools.conductor import compute_audit_hash, merge_reports

logger = logging.getLogger(__name__)

SPECIALIST_ROLES = (AgentRole.JURISDICTION, AgentRole.BUILDING, AgentRole.SITE)
POLL_INTERVAL_SEC = 3.0
JOIN_WAIT_SEC = 4.0


class BandOrchestrationError(RuntimeError):
    """Band room workflow failed."""


def _timeout_sec() -> float:
    return float(os.getenv("BAND_ORCHESTRATION_TIMEOUT", "300"))


def _rest_client(api_key: str):
    from thenvoi_rest import AsyncRestClient

    return AsyncRestClient(api_key=api_key, base_url=band_urls()["rest_url"].rstrip("/"))


def _mention_item(role: AgentRole):
    from thenvoi_rest import ChatMessageRequestMentionsItem

    agent_id, _ = get_agent_credentials(role)
    return ChatMessageRequestMentionsItem(id=agent_id, handle=AGENT_HANDLES[role])


async def _create_room_and_add_agents(conductor_key: str, brief: ProjectBrief) -> str:
    from thenvoi_rest import ChatRoomRequest, ParticipantRequest

    client = _rest_client(conductor_key)
    try:
        room_resp = await client.agent_api_chats.create_agent_chat(chat=ChatRoomRequest())
        room_id = room_resp.data.id
        logger.info("Band room created: %s", room_id)

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


def _extract_report(content: str | None, agent_name: str, model_cls: type):
    if not content:
        return None
    band_msg = parse_band_message(content)
    if band_msg and band_msg.agent == agent_name:
        if band_msg.type == MessageType.COMPLETE and band_msg.payload:
            data = dict(band_msg.payload)
            data.setdefault("case_id", str(band_msg.case_id))
            data.setdefault("agent", agent_name)
            try:
                return model_cls.model_validate(data)
            except Exception as exc:
                logger.debug("Band payload validate failed for %s: %s", agent_name, exc)
    # Direct report JSON (agent field matches)
    for match in _json_blobs(content):
        if match.get("agent") == agent_name or agent_name in str(match.get("agent", "")):
            try:
                return model_cls.model_validate(match)
            except Exception:
                pass
        if "checks" in match or "environmental_checks" in match or "permits_required" in match:
            try:
                match.setdefault("agent", agent_name)
                return model_cls.model_validate(match)
            except Exception:
                continue
    return None


def _json_blobs(text: str):
    import re

    fenced = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    for raw in fenced:
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        yield json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return


async def _list_messages(api_key: str, room_id: str) -> list[Any]:
    client = _rest_client(api_key)
    try:
        resp = await client.agent_api_messages.list_agent_messages(chat_id=room_id)
        return list(resp.data or [])
    finally:
        await client._client_wrapper.httpx_client.httpx_client.aclose()


async def _poll_specialists(
    api_key: str, room_id: str, case_id: UUID, deadline: float
) -> tuple[JurisdictionReport, BuildingSafetyReport, SiteEnvironmentalReport]:
    seen: set[str] = set()
    reports: dict[str, Any] = {}

    models = {
        "jurisdiction": JurisdictionReport,
        "building": BuildingSafetyReport,
        "site": SiteEnvironmentalReport,
    }

    while time.monotonic() < deadline and len(reports) < 3:
        for msg in await _list_messages(api_key, room_id):
            msg_id = getattr(msg, "id", None) or str(msg)
            if msg_id in seen:
                continue
            seen.add(msg_id)
            sender = (getattr(msg, "sender_name", "") or "").lower()
            content = msg.content or ""
            for agent_name, model_cls in models.items():
                if agent_name in reports:
                    continue
                if agent_name in sender or f"permitos-{agent_name}" in sender:
                    report = _extract_report(content, agent_name, model_cls)
                    if report:
                        reports[agent_name] = report
                        logger.info("Received %s report from Band", agent_name)
        if len(reports) >= 3:
            break
        await asyncio.sleep(POLL_INTERVAL_SEC)

    missing = [k for k in models if k not in reports]
    if missing:
        raise BandOrchestrationError(
            f"Timed out waiting for Band agents: {', '.join(missing)}. "
            "Ensure all 5 agents are running (scripts/start_all_agents.ps1)."
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
            for blob in _json_blobs(content):
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
        "Timed out waiting for Packager agent on Band. Check agent logs and HF/LLM credits."
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


async def run_band_case(brief: ProjectBrief) -> dict[str, Any]:
    """Create Band room, dispatch live agents, poll structured responses."""
    _, conductor_key = get_agent_credentials(AgentRole.CONDUCTOR)
    deadline = time.monotonic() + _timeout_sec()

    room_id = await _create_room_and_add_agents(conductor_key, brief)

    brief_json = brief.model_dump_json(indent=2)
    dispatch_specialists = (
        f"PermitOS case intake — analyze with your Austin tools.\n\n"
        f"ProjectBrief:\n```json\n{brief_json}\n```\n\n"
        f"Reply via band_send_message with ```json containing "
        f'"type":"complete", "case_id":"{brief.case_id}", "agent":"<your_role>", '
        f'"payload": {{<full report object>}}`.'
    )
    await _send_message(
        conductor_key,
        room_id,
        dispatch_specialists,
        list(SPECIALIST_ROLES),
    )

    jurisdiction, building, site = await _poll_specialists(
        conductor_key, room_id, brief.case_id, deadline
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
