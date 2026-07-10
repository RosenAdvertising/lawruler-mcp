#!/usr/bin/env python3
"""LawRuler MCP setup — API key + portal URL configuration."""

import json
import sys
import requests

from lawruler_mcp import credentials

REQUEST_TIMEOUT = (3.05, 30)


def test_connection(base_url: str, api_key: str) -> tuple[int, str]:
    endpoint = f"{base_url.rstrip('/')}/api-legalcrmapp.aspx"
    resp = requests.post(
        endpoint,
        data={
            "Key": api_key,
            "Operation": "GetStatus",
            "ReturnJSON": "True",
            "LeadID": "1",
        },
        timeout=REQUEST_TIMEOUT,
    )
    return resp.status_code, resp.text[:300]


def main():
    print("LawRuler MCP Setup")
    print("==================")
    print("You need your firm's LawRuler portal URL and API key.")
    print("Find the API key in: Setup → 3rd Party Integrations")
    print()

    base_url = input("Portal URL (e.g. https://yourfirm.lawruler.com): ").strip()
    if not base_url:
        print("Portal URL is required.")
        sys.exit(1)

    api_key = input("API Key: ").strip()
    if not api_key:
        print("API Key is required.")
        sys.exit(1)

    print()
    print("Testing connection...")
    status_code, response_text = test_connection(base_url, api_key)

    # A 200 response (even "Lead not found") confirms the endpoint is reachable and key is valid
    if status_code == 200:
        print(f"✓ Connected (HTTP {status_code})")
    elif status_code == 401 or status_code == 403:
        print(f"✗ Authentication failed ({status_code}). Check your API key.")
        sys.exit(1)
    elif status_code == 404:
        print(f"✗ Portal URL not found ({status_code}). Check your portal URL.")
        sys.exit(1)
    else:
        print(f"✓ Endpoint reached (HTTP {status_code})")

    credentials.set_secret("LAWRULER_BASE_URL", base_url)
    backend = credentials.set_secret("LAWRULER_API_KEY", api_key)

    if backend == "keyring":
        print(
            f"✓ Credentials saved to the OS keyring ({credentials.storage_backend()})."
        )
    else:
        print(f"✓ Credentials saved to {credentials.ENV_FILE} (0600).")
    print()
    print("Add to your Claude Desktop config:")
    print(
        json.dumps({"mcpServers": {"lawruler": {"command": "lawruler-mcp"}}}, indent=2)
    )


if __name__ == "__main__":
    main()
