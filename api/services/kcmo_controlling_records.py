from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx

from shared.llm.zenmux import extract_pdf_text

logger = logging.getLogger(__name__)

LEGISTAR_API = "https://webapi.legistar.com/v1/kansascity"
CONTROLLING_RECORD_VERSION = 1
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


def _clean_ordinance(value: Any) -> str | None:
    match = re.search(r"\b\d{5,6}\b", str(value or ""))
    return match.group(0) if match else None


def _case_number(title: str) -> str | None:
    patterns = (
        r"\bCD-[A-Z]+-\d{4}-\d{5}\b",
        r"\b\d{4,6}-(?:URD|UR|CPC)-\d+\b",
    )
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(0).upper()
    return None


def _attachment_kind(name: str) -> str:
    normalized = name.casefold()
    if "approved plan" in normalized or "development plan" in normalized:
        return "approved_development_plan"
    if "staff report" in normalized or "docket memo" in normalized:
        return "staff_report"
    if "authenticated" in normalized or "ordinance" in normalized:
        return "ordinance"
    if "exhibit" in normalized:
        return "exhibit"
    if "map" in normalized:
        return "map"
    return "supporting_record"


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def public_record_url(record: dict[str, Any]) -> str | None:
    """Return a public URL that is known to resolve for a Legistar record."""
    attachments = record.get("attachments") or []
    official_document = next(
        (
            item.get("url")
            for item in attachments
            if item.get("kind") == "ordinance" and item.get("url")
        ),
        None,
    )
    if official_document:
        return str(official_document)
    matter_id = record.get("matterId")
    return f"{LEGISTAR_API}/Matters/{matter_id}" if matter_id else None


async def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def _extract_attachment(url: str, name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        content = response.content
    if len(content) > MAX_ATTACHMENT_BYTES:
        return {"status": "too_large", "standards": [], "conditions": []}

    raw = await extract_pdf_text(
        content,
        prompt=(
            "This is an official Kansas City zoning ordinance or approved development record. "
            "Return only JSON with keys record_title, case_number, standards, conditions, and notes. "
            "standards must be an array of objects with key, value, unit, applicability, page, and "
            "source_quote. Extract only explicitly readable approved values such as lot area, gross "
            "floor area, FAR, height, setbacks, density, parking, loading, uses, phases, and public "
            "improvements. Never infer a value. conditions must include page and source_quote. "
            f"The attachment name is {name}."
        ),
    )
    parsed = _parse_json_object(raw)
    return {
        "status": "parsed" if parsed else "unreadable",
        "recordTitle": parsed.get("record_title"),
        "caseNumber": parsed.get("case_number"),
        "standards": parsed.get("standards", []) if isinstance(parsed.get("standards"), list) else [],
        "conditions": parsed.get("conditions", []) if isinstance(parsed.get("conditions"), list) else [],
        "notes": parsed.get("notes"),
    }


async def resolve_ur_controlling_record(ordinance_value: Any) -> dict[str, Any]:
    ordinance = _clean_ordinance(ordinance_value)
    if not ordinance:
        return {
            "version": CONTROLLING_RECORD_VERSION,
            "lookupStatus": "missing_ordinance",
            "extractionStatus": "not_started",
            "standards": [],
            "conditions": [],
            "attachments": [],
        }

    matters = await _get_json(
        f"{LEGISTAR_API}/Matters",
        {"$filter": f"MatterFile eq '{ordinance}'"},
    )
    if not matters:
        return {
            "version": CONTROLLING_RECORD_VERSION,
            "ordinance": ordinance,
            "lookupStatus": "not_found",
            "extractionStatus": "not_started",
            "standards": [],
            "conditions": [],
            "attachments": [],
        }

    matter = matters[0]
    matter_id = int(matter["MatterId"])
    attachments_payload, histories = await asyncio.gather(
        _get_json(f"{LEGISTAR_API}/Matters/{matter_id}/Attachments"),
        _get_json(f"{LEGISTAR_API}/Matters/{matter_id}/Histories"),
    )
    title = str(matter.get("MatterTitle") or "")
    passed = next(
        (
            history
            for history in histories
            if "pass" in str(history.get("MatterHistoryActionName") or "").casefold()
        ),
        None,
    )
    attachments = [
        {
            "id": item.get("MatterAttachmentId"),
            "name": item.get("MatterAttachmentName") or item.get("MatterAttachmentFileName"),
            "url": item.get("MatterAttachmentHyperlink"),
            "kind": _attachment_kind(str(item.get("MatterAttachmentName") or "")),
        }
        for item in attachments_payload
        if item.get("MatterAttachmentHyperlink") and item.get("MatterAttachmentShowOnInternetPage", True)
    ]
    has_approved_plan = any(item["kind"] == "approved_development_plan" for item in attachments)
    extraction_status = "not_configured"
    standards: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []

    if os.getenv("ZENMUX_API_KEY", "").strip():
        extraction_status = "parsed"
        candidates = [
            item
            for item in attachments
            if item["kind"] in {"approved_development_plan", "ordinance", "staff_report", "exhibit"}
        ][:4]
        for attachment in candidates:
            try:
                parsed = await _extract_attachment(attachment["url"], attachment["name"])
            except Exception as exc:
                logger.warning("Could not parse KCMO attachment %s: %s", attachment["url"], exc)
                attachment["extractionStatus"] = "failed"
                continue
            attachment["extractionStatus"] = parsed["status"]
            for standard in parsed["standards"]:
                if isinstance(standard, dict):
                    standards.append({**standard, "attachmentId": attachment["id"], "url": attachment["url"]})
            for condition in parsed["conditions"]:
                if isinstance(condition, dict):
                    conditions.append({**condition, "attachmentId": attachment["id"], "url": attachment["url"]})
        if not standards and not conditions:
            extraction_status = "no_values_found"

    return {
        "version": CONTROLLING_RECORD_VERSION,
        "ordinance": ordinance,
        "lookupStatus": "found",
        "matterId": matter_id,
        "matterGuid": matter.get("MatterGuid"),
        "title": title,
        "caseNumber": _case_number(title),
        "recordStatus": matter.get("MatterStatusName"),
        "approvalAction": passed.get("MatterHistoryActionName") if passed else None,
        "approvalDate": passed.get("MatterHistoryActionDate") if passed else None,
        "officialUrl": public_record_url(
            {"matterId": matter_id, "attachments": attachments}
        ),
        "hasPublicApprovedPlan": has_approved_plan,
        "extractionStatus": extraction_status,
        "standards": standards,
        "conditions": conditions,
        "attachments": attachments,
    }
