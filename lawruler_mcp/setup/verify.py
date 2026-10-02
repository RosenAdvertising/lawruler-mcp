#!/usr/bin/env python3
"""Verify LawRuler MCP credentials."""

import sys

from lawruler_mcp.errors import LawRulerToolError
from lawruler_mcp.client import LawRulerClient, BASE_URL, API_KEY
from lawruler_mcp.validation import validate_portal_url


def main():
    print("Verifying LawRuler MCP credentials...")
    if not API_KEY or not BASE_URL:
        print(
            "✗ LAWRULER_API_KEY and LAWRULER_BASE_URL must be set. Run lawruler-mcp-setup."
        )
        sys.exit(1)

    print("  Portal: configured (hidden)")
    print("  Key:    set (hidden)")
    print()

    try:
        validate_portal_url(BASE_URL)
        client = LawRulerClient()
        # Query lead 1 — may or may not exist, but confirms the endpoint is reachable
        client.get_lead(1)
        print("✓ Connection successful.")
    except LawRulerToolError as exc:
        print(f"✗ Verification failed: {exc}")
        sys.exit(1)
    except Exception:
        print(
            "✗ Verification failed. Check the portal URL and credentials, then run lawruler-mcp-setup."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
