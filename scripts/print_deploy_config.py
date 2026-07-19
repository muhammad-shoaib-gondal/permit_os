#!/usr/bin/env python3
"""Log non-secret deployment configuration at startup."""

from shared.llm.zenmux import resolve_zenmux_config


def main() -> None:
    config = resolve_zenmux_config()
    print("=== EstatePermit deploy config ===")
    print("  AI_PROVIDER=ZenMux")
    print(f"  ZENMUX_MODEL={config.model}")
    print(f"  ZENMUX_BASE_URL={config.base_url}")
    print(f"  ZENMUX_MAX_TOKENS={config.max_tokens}")
    print(f"  ZENMUX_MAX_RETRIES={config.max_retries}")
    print("==============================")


if __name__ == "__main__":
    main()
