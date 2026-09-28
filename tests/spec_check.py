#!/usr/bin/env python3
"""Offline guard for the MCP protocol revision targeted by this repository."""

from mcp.types import LATEST_PROTOCOL_VERSION


EXPECTED_MCP_PROTOCOL_VERSION = "2026-07-28"


def main() -> int:
    if LATEST_PROTOCOL_VERSION != EXPECTED_MCP_PROTOCOL_VERSION:
        print(
            "Spec check: FAIL: expected "
            f"{EXPECTED_MCP_PROTOCOL_VERSION}, got {LATEST_PROTOCOL_VERSION}"
        )
        return 1
    print(f"Spec check: PASS: MCP {EXPECTED_MCP_PROTOCOL_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
