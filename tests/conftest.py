"""Pytest fixtures for deterministic permit-analysis tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeChatModel:
    async def ainvoke(self, _messages):
        return SimpleNamespace(content="Automated review completed from the supplied facts.")


@pytest.fixture(autouse=True)
def mock_zenmux(monkeypatch):
    """Unit tests never make live model requests."""
    monkeypatch.setenv("ZENMUX_API_KEY", "test-zenmux-key")
    monkeypatch.setattr(
        "shared.analysis.runner.create_chat_model",
        lambda: _FakeChatModel(),
    )
