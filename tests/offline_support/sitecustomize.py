"""Explicitly opt-in offline pytest isolation (via PYTHONPATH).

Keep credential fallback files and test artifacts inside the requested evidence
directory without changing HOME or accessing the user's keyring. Subprocesses
inherit the same isolation. Mocked HTTP/ASGI tests still work; real DNS/connects
fail immediately. Loopback bind is left to the actual sandbox policy.
"""

import os
from pathlib import Path
import socket


def _no_network(*args, **kwargs):
    raise AssertionError("Real network access is forbidden in offline tests")


socket.socket.connect = _no_network
socket.socket.connect_ex = _no_network
socket.create_connection = _no_network
socket.getaddrinfo = _no_network
os.environ["LAWRULER_MCP_USE_KEYRING"] = "0"

from lawruler_mcp import credentials  # noqa: E402

credentials.CONFIG_DIR = Path(os.environ["LAWRULER_OFFLINE_CONFIG_DIR"])
credentials.ENV_FILE = credentials.CONFIG_DIR / ".env"
