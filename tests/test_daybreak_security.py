"""Regressions for PUBLIC2: no credentials/writes cross invalid boundaries."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from mcp.types import CallToolRequestParams

from lawruler_mcp import client as client_module, server
from lawruler_mcp.errors import ArgumentError, VendorHTTPError
from lawruler_mcp.setup import oauth_flow as setup, verify
from lawruler_mcp.validation import validate_portal_url


BAD_URLS = [
    "http://127.0.0.1:8080",
    "http://2130706433:8080",
    "http://0x7f000001:9000",
    "https://127.0.0.1.sslip.io",
    "https://attacker.example",
    "https://user:pass@attacker.example",
    "https://127.0.0.1",
    "https://10.0.0.1",
    "https://169.254.169.254",
    "https://8.8.8.8",
    "https://[::1]",
    "https://[::ffff:127.0.0.1]",
    "https://2130706433",
    "https://0x7f000001",
    "https://0177.0.0.1",
    "https://127.1",
    "https://localhost",
    "https://lawruler.com.attacker.example",
    "https://notlawruler.com",
    "https://user:pass@firm.lawruler.com",
    "https://firm.lawruler.com?next=https://attacker.example",
    "https://firm.lawruler.com#fragment",
    "https://firm.lawruler.com?",
    "https://firm.lawruler.com#",
    "https://firm.lawruler.com/redirect",
    "https://firm.lawruler.com:8443",
    "https://firm.lawruler.com:bad",
    "https://firm.lawruler.com:99999",
    "https://%6cawruler.com",
    "https://ｌawruler.com",
    "https://firm。lawruler.com",
    "https://firm.lawruler.com\\@attacker.example",
    "https://firm.\nlawruler.com",
    " https://firm.lawruler.com",
    "https://firm..lawruler.com",
    "https://-firm.lawruler.com",
    "https://firm.lawruler.com..",
    "https://[broken",
    "file:///etc/passwd",
    "//firm.lawruler.com",
]


@pytest.mark.parametrize("url", BAD_URLS)
def test_bad_portal_rejected_at_every_entry_before_request_or_save(
    monkeypatch, capsys, url
):
    post = Mock(side_effect=AssertionError("request must not happen"))
    save = Mock(side_effect=AssertionError("save must not happen"))
    monkeypatch.setattr(requests.Session, "request", post)
    monkeypatch.setattr(setup.credentials, "set_secret", save)
    monkeypatch.setattr(client_module, "API_KEY", "SENTINEL-API-KEY")
    monkeypatch.setattr(client_module, "BASE_URL", url)
    with pytest.raises(ArgumentError, match="LAWRULER_BASE_URL"):
        client_module.LawRulerClient()
    with pytest.raises(ArgumentError, match="LAWRULER_BASE_URL"):
        setup.test_connection(url, "SETUP-SENTINEL")

    monkeypatch.setattr("builtins.input", lambda _: url)
    monkeypatch.setattr(setup, "getpass", lambda _: "SETUP-SENTINEL")
    with pytest.raises(SystemExit) as exc:
        setup.main()
    assert exc.value.code == 1

    monkeypatch.setattr(verify, "BASE_URL", url)
    monkeypatch.setattr(verify, "API_KEY", "SENTINEL-API-KEY")
    with pytest.raises(SystemExit) as exc:
        verify.main()
    assert exc.value.code == 1

    monkeypatch.setattr(server, "BASE_URL", url)
    run = Mock()
    monkeypatch.setattr(server.mcp, "run", run)
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 1
    run.assert_not_called()
    post.assert_not_called()
    save.assert_not_called()
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "LAWRULER_BASE_URL" in output
    assert "SENTINEL" not in output
    assert url not in output


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://lawruler.com", "https://lawruler.com"),
        ("https://yourfirm.lawruler.com/", "https://yourfirm.lawruler.com"),
        ("HTTPS://FIRM.LAWRULER.COM.:443/", "https://firm.lawruler.com"),
        ("https://a.b.lawruler.com", "https://a.b.lawruler.com"),
    ],
)
def test_allowed_portals_normalized(url, expected):
    assert validate_portal_url(url) == expected


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(client_module, "BASE_URL", "https://test.lawruler.com")
    monkeypatch.setattr(client_module, "API_KEY", "SENTINEL-API-KEY")
    client = client_module.LawRulerClient()
    client.session.post = Mock(
        return_value=Mock(status_code=200, headers={}, text='{"LeadID":7}')
    )
    monkeypatch.setattr(server, "_c", lambda: client)
    return client


def invoke(name, args):
    return asyncio.run(
        server.mcp._handle_call_tool(
            None, CallToolRequestParams(name=name, arguments=args)
        )
    )


@pytest.mark.parametrize("name", ["create_lead", "create_lead_full", "create_lead_obo"])
@pytest.mark.parametrize(
    "args",
    [
        {},
        {"full_name": " \t\n"},
        {"first_name": "Ada"},
        {"last_name": "Lovelace"},
        {"first_name": "Ada", "last_name": "  "},
        {"cell_phone": "5550100", "email": "example@example.invalid"},
        {"summary": "Only a summary"},
        {"full_name": "\u2003"},
    ],
)
def test_blank_creates_reject_before_post(client, name, args):
    result = invoke(name, args)
    assert result.is_error
    assert "full_name or both first_name and last_name" in result.content[0].text
    client.session.post.assert_not_called()


@pytest.mark.parametrize("name", ["create_lead", "create_lead_full", "create_lead_obo"])
@pytest.mark.parametrize(
    "identity",
    [
        {"full_name": "Ada Lovelace"},
        {"first_name": "Ada", "last_name": "Lovelace"},
    ],
)
def test_creates_with_identity_and_vendor_contact_fields(client, name, identity):
    result = invoke(
        name, dict(identity, cell_phone="5550100", email="example@example.invalid")
    )
    assert not result.is_error
    client.session.post.assert_called_once()
    sent = client.session.post.call_args.kwargs
    assert sent["allow_redirects"] is False
    assert sent["data"]["Key"] == "SENTINEL-API-KEY"
    assert ("dupcheck" in sent["data"]) == (name == "create_lead_obo")


@pytest.mark.parametrize("name", ["create_lead", "create_lead_full", "create_lead_obo"])
@pytest.mark.parametrize(
    "contact",
    [
        {},
        {"cell_phone": "  "},
        {"cell_phone": "5550100"},
        {"email": "example@example.invalid"},
        {"cell_phone": "5550100", "email": "  "},
    ],
)
def test_vendor_required_contact_fields_reject_locally(client, name, contact):
    assert invoke(name, dict(contact, full_name="Ada Lovelace")).is_error
    client.session.post.assert_not_called()


@pytest.mark.parametrize(
    "name, args",
    [
        ("update_lead_contact_info", {}),
        ("update_lead_contact_info", {"email": " \t", "city": "\n"}),
        ("update_lead_fields", {}),
        ("update_lead_fields", {"status": " ", "summary": "\n"}),
        ("update_lead_fields", {"custom_fields_json": "{}"}),
        (
            "update_lead_fields",
            {"custom_fields_json": '{"custom1":null,"custom2":" "}'},
        ),
        ("update_lead_fields", {"custom_fields_json": '{"custom1":[],"custom2":{}}'}),
        ("update_lead_fields", {"custom_fields_json": '{"ReturnJSON":"True"}'}),
        ("update_lead_fields", {"custom_fields_json": '{" Operation ":"GetStatus"}'}),
        ("update_lead_fields", {"custom_fields_json": '{" ":"value"}'}),
    ],
)
def test_control_only_updates_reject_before_post(client, name, args):
    assert invoke(name, dict(args, lead_id=7)).is_error
    client.session.post.assert_not_called()


@pytest.mark.parametrize(
    "name, args, field, value",
    [
        (
            "update_lead_contact_info",
            {"email": "example@example.invalid"},
            "Email1",
            "example@example.invalid",
        ),
        ("update_lead_fields", {"status": "New Lead"}, "Status", "New Lead"),
        ("update_lead_fields", {"custom_fields_json": '{"custom1":0}'}, "custom1", "0"),
        (
            "update_lead_fields",
            {"custom_fields_json": '{"custom1":false}'},
            "custom1",
            "False",
        ),
    ],
)
def test_explicit_update_fields_still_post(client, name, args, field, value):
    assert not invoke(name, dict(args, lead_id=7)).is_error
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    assert data[field] == value
    assert data["LeadID"] == "7"
    assert data["overridelead"] == "true"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_client_redirect_never_followed(client, status):
    client.session.post.return_value = Mock(
        status_code=status, headers={"Location": "https://attacker.example"}
    )
    with pytest.raises(VendorHTTPError):
        client.get_lead(7)
    client.session.post.assert_called_once()
    assert client.session.post.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_setup_redirect_never_followed_or_saved(monkeypatch, status):
    post = Mock(return_value=Mock(status_code=status, text='{"LeadID":7}'))
    save = Mock()
    monkeypatch.setattr(setup.requests, "post", post)
    monkeypatch.setattr(setup.credentials, "set_secret", save)
    monkeypatch.setattr("builtins.input", lambda _: "https://firm.lawruler.com")
    monkeypatch.setattr(setup, "getpass", lambda _: "SETUP-SENTINEL")
    with pytest.raises(SystemExit) as exc:
        setup.main()
    assert exc.value.code == 1
    post.assert_called_once()
    assert post.call_args.kwargs["allow_redirects"] is False
    save.assert_not_called()


def test_setup_saves_only_normalized_validated_portal(monkeypatch):
    post = Mock(return_value=Mock(status_code=200, text='{"LeadID":7}'))
    save = Mock(return_value="file")
    monkeypatch.setattr(setup.requests, "post", post)
    monkeypatch.setattr(setup.credentials, "set_secret", save)
    monkeypatch.setattr("builtins.input", lambda _: "https://FIRM.LAWRULER.COM.:443/")
    monkeypatch.setattr(setup, "getpass", lambda _: "SETUP-SENTINEL")
    setup.main()
    assert save.call_args_list[0].args == (
        "LAWRULER_BASE_URL",
        "https://firm.lawruler.com",
    )
    assert post.call_args.args == ("https://firm.lawruler.com/api-legalcrmapp.aspx",)
    assert post.call_args.kwargs["allow_redirects"] is False


def test_verify_success_is_fixed_and_never_prints_record(monkeypatch, capsys):
    client = Mock()
    client.get_lead.return_value = {
        "Email": "client@example.invalid",
        "ConfidentialNote": "SENTINEL-LEGAL-PII",
    }
    monkeypatch.setattr(verify, "API_KEY", "SENTINEL-API-KEY")
    monkeypatch.setattr(verify, "BASE_URL", "https://firm.lawruler.com")
    monkeypatch.setattr(verify, "LawRulerClient", lambda: client)
    verify.main()
    assert capsys.readouterr().out == (
        "Verifying LawRuler MCP credentials...\n"
        "  Portal: configured (hidden)\n  Key:    set (hidden)\n\n"
        "✓ Connection successful.\n"
    )
    client.get_lead.assert_called_once_with(1)


def test_ordered_tool_definitions_byte_identical_to_head(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    baseline = subprocess.check_output(
        ["git", "show", "HEAD:lawruler_mcp/server.py"], cwd=repo
    )
    baseline_path = tmp_path / "baseline_server.py"
    baseline_path.write_bytes(baseline)
    script = """
import asyncio, importlib.util, json, sys
spec = importlib.util.spec_from_file_location('baseline_server', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps([tool.model_dump(mode='json', by_alias=True) for tool in asyncio.run(module.mcp.list_tools())], ensure_ascii=False))
"""
    before = subprocess.check_output(
        [sys.executable, "-c", script, str(baseline_path)], cwd=repo
    )
    after = (
        json.dumps(
            [
                tool.model_dump(mode="json", by_alias=True)
                for tool in asyncio.run(server.mcp.list_tools())
            ],
            ensure_ascii=False,
        )
        + "\n"
    ).encode()
    assert before == after


def test_installed_stdio_starts_without_configuration(monkeypatch):
    import os
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    monkeypatch.delenv("LAWRULER_API_KEY", raising=False)
    monkeypatch.delenv("LAWRULER_BASE_URL", raising=False)
    repo = Path(__file__).resolve().parents[1]

    async def check():
        params = StdioServerParameters(
            command=str(repo / ".venv/bin/lawruler-mcp"),
            cwd=repo,
            env=dict(os.environ),
        )
        async with Client(params, cache=None) as client:
            tools = await client.list_tools()
            expected = await server.mcp.list_tools()
            assert [tool.name for tool in tools.tools] == [
                tool.name for tool in expected
            ]
            result = await client.call_tool("get_lead", {"lead_id": 7})
            assert result.is_error
            assert "credentials are missing" in result.content[0].text

    asyncio.run(asyncio.wait_for(check(), timeout=15))
