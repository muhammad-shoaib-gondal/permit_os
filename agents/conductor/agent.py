"""PermitOS Conductor — LangGraph + Band SDK."""

from __future__ import annotations

import asyncio
import logging
import sys

from shared.band_client.config import AgentRole
from shared.band_client.factory import run_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("permitos.conductor")


def main() -> None:
    try:
        asyncio.run(run_agent(AgentRole.CONDUCTOR))
    except KeyboardInterrupt:
        logger.info("Conductor stopped")
    except Exception as exc:
        logger.error("Conductor failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
