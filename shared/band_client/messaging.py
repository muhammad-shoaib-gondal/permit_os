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


def parse_band_message(text: str) -> BandMessage | None:
    """Extract JSON block from Band message text."""
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return BandMessage.model_validate_json(fenced.group(1))
        except Exception:
            pass
    for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL):
        try:
            data = json.loads(match.group(0))
            if "type" in data and "case_id" in data and "agent" in data:
                return BandMessage.model_validate(data)
        except Exception:
            continue
    return None


def mention(role: str) -> str:
    return f"@{role}"
