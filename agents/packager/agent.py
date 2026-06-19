"""PermitOS Permit Packager & Tracker — Anthropic + Band SDK."""

from __future__ import annotations

import asyncio
import logging
import sys

from shared.band_client.config import AgentRole
from shared.band_client.factory import run_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("permitos.packager")


def main() -> None:
    try:
        asyncio.run(run_agent(AgentRole.PACKAGER))
    except KeyboardInterrupt:
        logger.info("Packager agent stopped")
    except FileNotFoundError as exc:
        logger.error("Packager agent failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
