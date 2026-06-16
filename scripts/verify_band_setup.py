#!/usr/bin/env python3
"""Verify Band agent credentials (REST check — no LLM key required)."""

from __future__ import annotations

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_setup")


async def verify(role: str = "conductor") -> None:
    from band.config import load_agent_config

    from shared.band_client.config import AgentRole, band_urls

    agent_role = AgentRole(role)
    agent_id, api_key = load_agent_config(agent_role.value)
    urls = band_urls()
    logger.info("Loaded %s → agent_id %s...", role, agent_id[:8])

    from band import Agent
    from band.core.simple_adapter import SimpleAdapter
    from band.core.types import Emit, PlatformMessage

    class PingAdapter(SimpleAdapter[list]):
        SUPPORTED_EMIT = frozenset({Emit.EXECUTION})

        async def on_message(
            self,
            msg: PlatformMessage,
            tools,
            history: list,
            participants_msg: str | None,
            contacts_msg: str | None,
            *,
            is_session_bootstrap: bool,
            room_id: str,
        ) -> None:
            if is_session_bootstrap:
                return
            await tools.send_message(f"PermitOS {role} agent online.")

    agent = Agent.create(
        adapter=PingAdapter(),
        agent_id=agent_id,
        api_key=api_key,
        ws_url=urls["ws_url"],
        rest_url=urls["rest_url"],
    )
    await agent.start()
    logger.info("Connected as: %s", agent.agent_name)
    if agent.agent_description:
        logger.info("Description: %s", agent.agent_description[:100])
    logger.info("Band credentials verified for %s!", role)
    await agent.stop()


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else "conductor"
    try:
        asyncio.run(verify(role))
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ImportError as exc:
        logger.error("%s", exc)
        logger.info(
            "Install Band SDK:\n"
            "  git clone --depth 1 https://github.com/thenvoi/thenvoi-sdk-python.git _vendor/thenvoi-sdk-python\n"
            "  pip install ./_vendor/thenvoi-sdk-python"
        )
        sys.exit(1)
    except Exception as exc:
        logger.error("Verification failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
