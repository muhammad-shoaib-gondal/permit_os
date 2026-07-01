"""Evaluate user-defined custom rules against a project brief using LLM."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from shared.agent_logic.local_runner import _make_llm, _skip_llm
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


def _status(raw: str) -> CheckStatus:
    try:
        return CheckStatus(raw.lower())
    except ValueError:
        return CheckStatus.WARN


async def evaluate_custom_rules(
    brief: ProjectBrief,
    rules: list[dict[str, Any]],
) -> list[CheckResult]:
    enabled = [r for r in rules if r.get("enabled", True)]
    if not enabled:
        return []

    if _skip_llm():
        return [
            CheckResult(
                rule=r.get("rule", "Custom rule"),
                status=CheckStatus.WARN,
                citation="Custom rule (LLM skipped)",
                detail=r.get("condition") or "Enable LLM to evaluate this rule.",
                category="custom",
            )
            for r in enabled
        ]

    brief_json = brief.model_dump(mode="json")
    rules_payload = [
        {
            "id": r.get("id"),
            "rule": r.get("rule"),
            "condition": r.get("condition") or r.get("rule"),
            "category": r.get("category", "custom"),
            "severity": r.get("severity", "warning"),
            "area": r.get("area"),
        }
        for r in enabled
    ]

    prompt = (
        "You are a permitting compliance reviewer. Evaluate each custom rule against "
        "the project brief. Return ONLY valid JSON array with one object per rule:\n"
        '[{"id":"...","status":"pass|fail|warn","detail":"...","citation":"..."}]\n\n'
        f"Project brief:\n{json.dumps(brief_json, indent=2)[:4000]}\n\n"
        f"Rules to evaluate:\n{json.dumps(rules_payload, indent=2)}"
    )

    try:
        llm: ChatOpenAI = _make_llm()
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = (resp.content or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("Expected JSON array")

        by_id = {str(r.get("id")): r for r in enabled if r.get("id")}
        checks: list[CheckResult] = []
        for item in parsed:
            rid = str(item.get("id", ""))
            src = by_id.get(rid, {})
            checks.append(
                CheckResult(
                    rule=src.get("rule") or item.get("rule", "Custom rule"),
                    status=_status(str(item.get("status", "warn"))),
                    citation=item.get("citation") or "User-defined rule",
                    detail=item.get("detail", "No detail provided."),
                    category=src.get("category", "custom"),
                )
            )
        return checks
    except Exception as exc:
        logger.warning("Custom rules LLM evaluation failed: %s", exc)
        return [
            CheckResult(
                rule=r.get("rule", "Custom rule"),
                status=CheckStatus.WARN,
                citation="Custom rule",
                detail=f"Could not evaluate automatically: {exc}",
                category="custom",
            )
            for r in enabled
        ]
