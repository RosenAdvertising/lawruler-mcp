#!/usr/bin/env python3
"""Verify LawRuler MCP credentials."""

import json
import sys
from lawruler_mcp.client import LawRulerClient, BASE_URL, API_KEY


def main():
    print("Verifying LawRuler MCP credentials...")
    if not API_KEY or not BASE_URL:
        print("✗ LAWRULER_API_KEY and LAWRULER_BASE_URL must be set. Run lawruler-mcp-setup.")
        sys.exit(1)

    print(f"  Portal: {BASE_URL}")
    print(f"  Key:    {API_KEY[:8]}...")
    print()

    try:
        client = LawRulerClient()
        # Query lead 1 — may or may not exist, but confirms the endpoint is reachable
        result = client.get_lead(1)
        print("✓ Connection successful.")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
