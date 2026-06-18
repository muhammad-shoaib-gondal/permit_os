from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.schemas.band_message import BandMessage, MessageType


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_band_message(
    *,
    msg_type: MessageType,
    case_id: UUID,
    agent: str,
    payload: dict[str, Any] | None = None,
    citations: list[dict[str, str]] | None = None,
) -> BandMessage:
    from shared.schemas.band_message import Citation

    return BandMessage(
        type=msg_type,
        case_id=case_id,
        agent=agent,
        timestamp=utc_now_iso(),
        payload=payload or {},
        citations=[Citation(**c) if isinstance(c, dict) else c for c in (citations or [])],
    )


def _balanced_json_objects(text: str):
    """Yield JSON objects by matching braces (handles nested payloads)."""
    i = 0
    while i < len(text):
        start = text.find("{", i)
        if start < 0:
            return
        depth = 0
        in_str = False
        escape = False
        for j in range(start, len(text)):
            ch = text[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = text[start : j + 1]
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        pass
                    i = j + 1
                    break
        else:
            return


def iter_json_blobs(text: str):
    """Extract JSON objects from fenced blocks or free-form message text."""
    for block in re.finditer(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE):
        for obj in _balanced_json_objects(block.group(1)):
            yield obj
    if not re.search(r"```json", text, re.IGNORECASE):
        yield from _balanced_json_objects(text)


def unwrap_band_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten Band complete wrapper {type, case_id, agent, payload} into report fields."""
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return dict(data)
    out = dict(payload)
    if data.get("case_id") and not out.get("case_id"):
        out["case_id"] = data["case_id"]
    if data.get("agent") and not out.get("agent"):
        out["agent"] = data["agent"]
    return out


def parse_band_message(text: str) -> BandMessage | None:
    """Extract JSON block from Band message text."""
    for data in iter_json_blobs(text):
        if "type" in data and "case_id" in data and "agent" in data:
            try:
                return BandMessage.model_validate(data)
            except Exception:
                continue
    return None


def mention(role: str) -> str:
    return f"@{role}"
