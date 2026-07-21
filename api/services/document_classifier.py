from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

from shared.llm.zenmux import chat_completion

logger = logging.getLogger(__name__)

DOCUMENT_TYPES = {
    "architectural_plan",
    "site_plan",
    "structural_plan",
    "code_analysis",
    "fire_protection_plan",
    "mechanical_plan",
    "plumbing_plan",
    "electrical_plan",
    "elevation",
    "civil_plan",
    "survey",
    "energy_document",
    "application_form",
    "supporting_document",
    "other",
}

_FILENAME_HINTS = (
    (("architect", "floor plan", "floor_plan"), "architectural_plan"),
    (("site plan", "site_plan"), "site_plan"),
    (("structural", "foundation", "framing"), "structural_plan"),
    (("code analysis", "code_analysis", "code summary"), "code_analysis"),
    (("fire", "sprinkler", "life safety"), "fire_protection_plan"),
    (("mechanical", "hvac"), "mechanical_plan"),
    (("plumbing",), "plumbing_plan"),
    (("electrical", "lighting", "power plan"), "electrical_plan"),
    (("elevation",), "elevation"),
    (("civil", "utility", "grading", "stormwater"), "civil_plan"),
    (("survey", "plat"), "survey"),
    (("energy", "comcheck"), "energy_document"),
    (("application", "permit form"), "application_form"),
)


def infer_document_type(filename: str) -> str:
    normalized = Path(filename).stem.casefold().replace("-", "_")
    for hints, document_type in _FILENAME_HINTS:
        if any(hint in normalized for hint in hints):
            return document_type
    return "supporting_document"


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


async def classify_project_document(
    *,
    filename: str,
    content: bytes,
    content_type: str | None,
    permits: list[dict[str, str]],
) -> dict[str, Any]:
    fallback_type = infer_document_type(filename)
    fallback = {
        "document_type": fallback_type,
        "summary": f"Uploaded project document classified from its filename as {fallback_type.replace('_', ' ')}.",
        "permit_types": [],
        "source": "filename",
    }
    if len(content) > 20 * 1024 * 1024:
        return fallback

    mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    encoded = base64.standard_b64encode(content).decode("ascii")
    permit_catalog = permits or []
    prompt = (
        "Classify this construction or real-estate project document. Return only JSON with keys "
        "document_type, summary, and permit_types. document_type must be one of: "
        + ", ".join(sorted(DOCUMENT_TYPES))
        + ". summary must be a factual 1-3 sentence description of the document and useful permitting facts; "
        "do not invent unreadable values. permit_types must contain only exact permit_type values from this "
        f"project permit list when the document supports them: {json.dumps(permit_catalog)}"
    )
    try:
        raw = await chat_completion(
            "document_classification",
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "file",
                            "file": {
                                "filename": filename,
                                "file_data": f"data:{mime};base64,{encoded}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=700,
        )
        parsed = _parse_json_object(raw)
        document_type = str(parsed.get("document_type", "")).strip()
        if document_type not in DOCUMENT_TYPES:
            document_type = fallback_type
        summary = str(parsed.get("summary", "")).strip()[:1500] or fallback["summary"]
        allowed_permits = {item["permit_type"] for item in permit_catalog if item.get("permit_type")}
        permit_types = [
            value
            for value in parsed.get("permit_types", [])
            if isinstance(value, str) and value in allowed_permits
        ]
        return {
            "document_type": document_type,
            "summary": summary,
            "permit_types": list(dict.fromkeys(permit_types)),
            "source": "ai",
        }
    except Exception as exc:
        logger.warning("Document classification failed for %s: %s", filename, exc)
        return fallback
