"""Pytest fixtures — mock Band orchestration (no live agents in CI)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "riverside_band_result.json"


@pytest.fixture(autouse=True)
def mock_band_orchestration(monkeypatch):
    """Unit tests never hit Band REST or live LLM."""
    monkeypatch.setenv("PERMITOS_ORCHESTRATION", "band")

    async def _fake_band_case(brief, existing_room_id=None, on_progress=None):
        if FIXTURE.exists():
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            data["brief"] = brief.model_dump(mode="json")
            data["case_summary"]["case_id"] = str(brief.case_id)
            data["band_room_id"] = data.get("band_room_id") or f"test-room-{uuid4().hex[:8]}"
            return data
        raise RuntimeError("Missing tests/fixtures/riverside_band_result.json")

    monkeypatch.setattr("shared.band_client.orchestrator.run_band_case", _fake_band_case)
