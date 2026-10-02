#!/usr/bin/env python3
"""LawRuler MCP setup — API key + portal URL configuration."""

import json
import sys
from getpass import getpass
import requests

from lawruler_mcp import credentials
from lawruler_mcp.client import _is_failure_envelope, _xml_to_dict
from lawruler_mcp.errors import LawRulerToolError
from lawruler_mcp.validation import validate_portal_url

REQUEST_TIMEOUT = (3.05, 30)


def test_connection(base_url: str, api_key: str) -> tuple[int, str]:
    endpoint = f"{validate_portal_url(base_url)}/api-legalcrmapp.aspx"
    resp = requests.post(
        endpoint,
        data={
            "Key": api_key,
            "Operation": "GetStatus",
            "ReturnJSON": "True",
            "LeadID": "1",
        },
        timeout=REQUEST_TIMEOUT,
        allow_redirects=False,
    )
    return resp.status_code, resp.text


def _failure_envelope(body: str) -> bool:
    try:
        payload = (
            _xml_to_dict(body) if body.lstrip().startswith("<") else json.loads(body)
        )
        return _is_failure_envelope(payload)
    except Exception:
        return True


def _run_setup():
    print("LawRuler MCP Setup")
    print("==================")
    print("You need your firm's LawRuler portal URL and API key.")
    print("Find the API key in: Setup → 3rd Party Integrations")
    print()

    try:
        base_url = input("Portal URL (e.g. https://yourfirm.lawruler.com): ")
    except (EOFError, KeyboardInterrupt):
        print("Portal URL is required.")
        sys.exit(1)
    if not base_url:
        print("Portal URL is required.")
        sys.exit(1)
    base_url = validate_portal_url(base_url)

    try:
        api_key = getpass("API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("API Key is required.")
        sys.exit(1)
    if not api_key:
        print("API Key is required.")
        sys.exit(1)

    print()
    print("Testing connection...")
    try:
        status_code, response_text = test_connection(base_url, api_key)
    except (requests.Timeout, requests.ConnectionError):
        print(
            "✗ LawRuler setup request timed out or lost its connection; the outcome is unknown. Check whether it completed before retrying setup."
        )
        sys.exit(1)
    except requests.RequestException:
        print(
            "✗ Could not reach the configured LawRuler endpoint. Check the portal URL and try setup again."
        )
        sys.exit(1)

    # Accept only a structured response with no explicit failure envelope.
    if status_code == 200 and not _failure_envelope(response_text):
        print(f"✓ Connected (HTTP {status_code})")
    elif status_code == 403:
        print(
            "✗ LawRuler access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawruler-mcp-setup if so)."
        )
        sys.exit(1)
    elif status_code == 401:
        print(
            "✗ LawRuler authentication failed. Check the API key and run lawruler-mcp-setup again."
        )
        sys.exit(1)
    elif status_code == 404:
        print(f"✗ Portal URL not found ({status_code}). Check your portal URL.")
        sys.exit(1)
    elif status_code >= 400:
        print(
            f"✗ LawRuler rejected setup verification (HTTP {status_code}). Check the portal URL and API key."
        )
        sys.exit(1)
    elif status_code == 200:
        print(
            "✗ LawRuler returned a failure response (HTTP 200). Check the portal URL and API key."
        )
        sys.exit(1)
    else:
        print(
            f"✗ Unexpected LawRuler response (HTTP {status_code}). Check the portal URL and API key."
        )
        sys.exit(1)

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


def main():
    try:
        _run_setup()
    except LawRulerToolError as exc:
        print(f"✗ LawRuler setup failed: {exc}")
        sys.exit(1)
    except Exception:
        print(
            "✗ LawRuler setup failed. Check the portal URL and credential storage, then run lawruler-mcp-setup again."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
