from unittest.mock import Mock

import pytest
from defusedxml.common import DefusedXmlException

import lawruler_mcp.client as client_module
import lawruler_mcp.setup.oauth_flow as oauth_flow
import lawruler_mcp.setup.verify as verify_module


def test_verify_hides_api_key(monkeypatch, capsys):
    api_key = "super-secret-key-12345678"
    client = Mock()
    client.get_lead.return_value = {"ok": True}

    monkeypatch.setattr(verify_module, "API_KEY", api_key)
    monkeypatch.setattr(verify_module, "BASE_URL", "https://example.lawruler.com")
    monkeypatch.setattr(verify_module, "LawRulerClient", Mock(return_value=client))

    verify_module.main()

    output = capsys.readouterr().out
    assert api_key not in output
    assert api_key[:8] not in output
    assert "Key:    set (hidden)" in output


def test_client_request_has_timeout(monkeypatch):
    monkeypatch.setattr(client_module, "API_KEY", "test-key")
    monkeypatch.setattr(client_module, "BASE_URL", "https://example.lawruler.com")
    client = client_module.LawRulerClient()
    response = Mock(ok=True, status_code=200, headers={}, text="{}")
    post = Mock(return_value=response)
    monkeypatch.setattr(client.session, "post", post)

    client.get_lead(1)

    post.assert_called_once_with(
        "https://example.lawruler.com/api-legalcrmapp.aspx",
        data={
            "Operation": "GetStatus",
            "ReturnJSON": "True",
            "LeadID": "1",
            "Key": "test-key",
        },
        timeout=client_module.REQUEST_TIMEOUT,
    )


def test_setup_request_has_timeout(monkeypatch):
    response = Mock(status_code=200, text="connected")
    post = Mock(return_value=response)
    monkeypatch.setattr(oauth_flow.requests, "post", post)

    assert oauth_flow.test_connection("https://example.lawruler.com", "test-key") == (
        200,
        "connected",
    )
    post.assert_called_once_with(
        "https://example.lawruler.com/api-legalcrmapp.aspx",
        data={
            "Key": "test-key",
            "Operation": "GetStatus",
            "ReturnJSON": "True",
            "LeadID": "1",
        },
        timeout=oauth_flow.REQUEST_TIMEOUT,
    )


def test_xml_parser_rejects_entities():
    malicious_xml = """\
<!DOCTYPE root [
  <!ENTITY secret SYSTEM "file:///etc/passwd">
]>
<root><item>&secret;</item></root>
"""

    with pytest.raises(DefusedXmlException):
        client_module._xml_to_dict(malicious_xml)


def test_xml_parser_accepts_safe_response():
    assert client_module._xml_to_dict("<root><item>safe</item></root>") == {
        "item": "safe"
    }
