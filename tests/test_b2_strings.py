"""The setup wizard prints the same Claude Desktop config the README shows."""

from __future__ import annotations

import re
from pathlib import Path

import lawruler_mcp.setup.oauth_flow as setup

README = Path(__file__).resolve().parent.parent / "README.md"


def _readme_claude_desktop_json() -> str:
    text = README.read_text(encoding="utf-8")
    section = text.split("## Usage with Claude Desktop", 1)[1]
    match = re.search(r"```json\n(.*?)\n```", section, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_setup_prints_the_readme_claude_desktop_config(monkeypatch, capsys) -> None:
    answers = iter(["https://test.lawruler.com", "fake-key"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(setup, "getpass", lambda _prompt: next(answers))
    monkeypatch.setattr(setup, "test_connection", lambda *args: (200, "{}"))
    monkeypatch.setattr(setup, "_failure_envelope", lambda body: False)
    monkeypatch.setattr(setup.credentials, "set_secret", lambda key, value: "keyring")
    monkeypatch.setattr(setup.credentials, "storage_backend", lambda: "TestKeyring")

    setup.main()
    output = capsys.readouterr().out

    assert _readme_claude_desktop_json() in output
    assert setup.CLAUDE_DESKTOP_CONFIG == _readme_claude_desktop_json()
    assert '"command": "uv"' in output
    assert '"--directory", "/absolute/path/to/lawruler-mcp", "lawruler-mcp"' in output
    assert (
        "Replace /absolute/path/to/lawruler-mcp with the path of your clone" in output
    )
    # The old snippet was a bare command that the README does not show.
    assert '"command": "lawruler-mcp"' not in output
