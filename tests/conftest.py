"""Pytest fixtures — skip live LLM calls in CI."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def skip_llm(monkeypatch):
    """Unit tests never hit the LLM API."""
    monkeypatch.setenv("LOCAL_SKIP_LLM", "1")
