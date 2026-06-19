"""Serialize LLM HTTP calls across Band agent processes (Render all-in-one)."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

_LOCK_PATH = Path(os.getenv("LLM_LOCK_PATH", "/app/data/llm.lock"))
_MIN_INTERVAL_SEC = float(os.getenv("LLM_MIN_INTERVAL_SEC", "4"))
_last_release_monotonic = 0.0


def cross_process_llm_lock_enabled() -> bool:
    explicit = os.getenv("LLM_CROSS_PROCESS_LOCK", "").lower()
    if explicit in ("0", "false", "no"):
        return False
    if explicit in ("1", "true", "yes"):
        return True
    # Default: on Linux band deploy, four agent processes share one API key.
    return (
        sys.platform == "linux"
        and os.getenv("PERMITOS_ORCHESTRATION", "band").lower() == "band"
    )


@contextmanager
def llm_request_slot():
    """Hold a file lock so only one agent process calls the LLM at a time."""
    global _last_release_monotonic

    if not cross_process_llm_lock_enabled():
        yield
        return

    if sys.platform == "win32":
        # Local Windows dev: in-process spacing only (agents usually separate terminals).
        wait = _last_release_monotonic + _MIN_INTERVAL_SEC - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            yield
        finally:
            _last_release_monotonic = time.monotonic()
        return

    import fcntl

    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCK_PATH, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            wait = _last_release_monotonic + _MIN_INTERVAL_SEC - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            yield
            _last_release_monotonic = time.monotonic()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
