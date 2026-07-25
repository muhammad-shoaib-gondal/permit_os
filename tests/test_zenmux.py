from __future__ import annotations

import pytest

from shared.llm.zenmux import (
    ZENMUX_DEFAULT_BASE_URL,
    ZENMUX_DEFAULT_MODEL,
    resolve_zenmux_config,
)


def test_zenmux_uses_its_documented_defaults(monkeypatch):
    monkeypatch.setenv("ZENMUX_API_KEY", "zenmux-test")
    monkeypatch.delenv("ZENMUX_BASE_URL", raising=False)
    monkeypatch.delenv("ZENMUX_MODEL", raising=False)

    config = resolve_zenmux_config()

    assert config.api_key == "zenmux-test"
    assert config.base_url == ZENMUX_DEFAULT_BASE_URL
    assert config.model == ZENMUX_DEFAULT_MODEL


def test_zenmux_key_is_required(monkeypatch):
    monkeypatch.delenv("ZENMUX_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ZENMUX_API_KEY"):
        resolve_zenmux_config()
