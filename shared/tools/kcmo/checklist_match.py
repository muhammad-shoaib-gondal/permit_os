"""Filename → checklist keyword matching (no DB / FastAPI imports)."""

from __future__ import annotations

from shared.tools.kcmo.load import load_kcmo_json


def match_filename_to_checklist_keys(filename: str) -> list[str]:
    pack = load_kcmo_json("document_checklists.json")
    assert isinstance(pack, dict)
    keywords = pack.get("match_keywords") or {}
    name = filename.lower()
    matched: list[str] = []
    for key, tokens in keywords.items():
        if any(token.lower() in name for token in tokens):
            matched.append(key)
    return matched
