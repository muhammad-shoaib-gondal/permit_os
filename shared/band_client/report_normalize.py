"""Normalize Band agent LLM JSON into PermitOS report schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def _norm_status(raw: Any) -> str:
    s = str(raw or "warn").lower()
    if s in ("pass", "fail", "warn"):
        return s
    if "fail" in s or "non-compliance" in s or "issue" in s:
        return "fail"
    if "pass" in s or "ok" in s or "within" in s or "meets" in s:
        return "pass"
    return "warn"


def _norm_readiness(raw: Any) -> str:
    s = str(raw or "").lower()
    if "blocked" in s:
        return "blocked"
    if any(x in s for x in ("not ready", "needs", "fail", "issue", "hold")):
        return "needs_changes"
    if "ready" in s:
        return "ready"
    return "needs_changes"


def _norm_check(c: dict[str, Any]) -> dict[str, Any]:
    detail = c.get("detail") or c.get("check_result") or str(c)
    status_raw = c.get("status")
    if not status_raw:
        status_raw = detail
        name = str(c.get("rule") or c.get("check_name") or "")
        if "setback" in name.lower() and ("8ft" in detail or "instead of" in detail.lower()):
            status_raw = "fail"
    return {
        "rule": c.get("rule") or c.get("check_name") or c.get("name") or "Check",
        "status": _norm_status(status_raw),
        "citation": c.get("citation") or c.get("check_citation") or "",
        "detail": detail,
        "category": c.get("category"),
    }


def _norm_blockers(raw: Any) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for b in raw if isinstance(raw, list) else [raw]:
        if isinstance(b, str):
            out.append(b)
        elif isinstance(b, dict):
            out.append(
                b.get("blocker_description")
                or b.get("blocker_name")
                or b.get("issue")
                or str(b)
            )
    return out


def _fix_case_id(data: dict[str, Any], case_id: UUID | str | None) -> None:
    if not case_id:
        return
    cid = data.get("case_id")
    if not cid or cid in ("<uuid>", "<case_id>", "uuid", "your_case_id"):
        data["case_id"] = str(case_id)


def normalize_jurisdiction_payload(data: dict[str, Any], case_id: UUID | str | None = None) -> dict[str, Any]:
    out = dict(data)
    _fix_case_id(out, case_id)
    out["agent"] = "jurisdiction"
    out["readiness_impact"] = _norm_readiness(out.get("readiness_impact") or out.get("summary"))
    checks = out.get("checks") or []
    if isinstance(checks, list):
        out["checks"] = [_norm_check(c) for c in checks if isinstance(c, dict)]
    out["blockers"] = _norm_blockers(out.get("blockers"))
    if not out.get("summary"):
        out["summary"] = "Jurisdiction review complete"
    return out


def normalize_building_payload(data: dict[str, Any], case_id: UUID | str | None = None) -> dict[str, Any]:
    out = dict(data)
    _fix_case_id(out, case_id)
    out["agent"] = "building"
    out["readiness_impact"] = _norm_readiness(out.get("readiness_impact") or out.get("summary"))
    checks = out.get("checks") or []
    if isinstance(checks, list):
        out["checks"] = [_norm_check(c) for c in checks if isinstance(c, dict)]
    out["blockers"] = _norm_blockers(out.get("blockers"))
    if not out.get("summary"):
        out["summary"] = "Building review complete"
    return out


def normalize_site_payload(data: dict[str, Any], case_id: UUID | str | None = None) -> dict[str, Any]:
    out = dict(data)
    _fix_case_id(out, case_id)
    out["agent"] = "site"
    out["readiness_impact"] = _norm_readiness(out.get("readiness_impact"))
    for key in ("environmental_checks", "utility_checks"):
        checks = out.get(key) or []
        if isinstance(checks, list):
            out[key] = [_norm_check(c) for c in checks if isinstance(c, dict)]
    out["blockers"] = _norm_blockers(out.get("blockers"))
    if not out.get("summary"):
        out["summary"] = "Site review complete"
    return out


def normalize_for_agent(agent_name: str, data: dict[str, Any], case_id: UUID | str | None) -> dict[str, Any]:
    if agent_name == "jurisdiction":
        return normalize_jurisdiction_payload(data, case_id)
    if agent_name == "building":
        return normalize_building_payload(data, case_id)
    if agent_name == "site":
        return normalize_site_payload(data, case_id)
    _fix_case_id(data, case_id)
    return data
