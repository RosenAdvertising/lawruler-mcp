import logging
from unittest.mock import Mock

import pytest
from defusedxml.common import DefusedXmlException

import lawruler_mcp.client as client_module
import lawruler_mcp.server as server_module
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


def test_xml_parser_rejects_entities_with_pii_free_log(caplog):
    malicious_xml = """\
<!DOCTYPE root [
  <!ENTITY secret SYSTEM "file:///etc/passwd">
]>
<root><item>&secret;</item></root>
"""

    with caplog.at_level(logging.WARNING):
        with pytest.raises(DefusedXmlException):
            client_module._xml_to_dict(malicious_xml)

    assert "xml_response_rejected reason=unsafe_markup" in caplog.text
    assert "file:///etc/passwd" not in caplog.text


def test_xml_parser_accepts_safe_response():
    assert client_module._xml_to_dict("<root><item>safe</item></root>") == {
        "item": "safe"
    }


def test_missing_client_configuration_logs_rejection_reason(
    monkeypatch, caplog
):
    monkeypatch.setattr(client_module, "API_KEY", "")
    monkeypatch.setattr(client_module, "BASE_URL", "")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="must be set"):
            client_module.LawRulerClient()

    assert "client_configuration_rejected reason=missing_credentials" in caplog.text


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ('{"Key":"private-name@example.test"}', "reserved_parameter"),
        ('["private-name@example.test"]', "not_object"),
        ('{"value":"private-name@example.test"', "invalid_json"),
    ],
)
def test_server_custom_field_rejections_log_pii_free_reason(
    payload, reason, caplog
):
    with caplog.at_level(logging.WARNING):
        result = server_module.update_lead_fields(1, custom_fields_json=payload)

    assert "error" in result
    assert f"custom_fields_rejected reason={reason}" in caplog.text
    assert "private-name@example.test" not in caplog.text


def test_client_reserved_field_rejection_log_is_pii_free(
    monkeypatch, caplog
):
    monkeypatch.setattr(client_module, "API_KEY", "test-key")
    monkeypatch.setattr(client_module, "BASE_URL", "https://example.lawruler.com")
    client = client_module.LawRulerClient()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValueError, match="reserved parameter"):
            client.set_custom_field(1, "Key", "private-name@example.test")

    assert "custom_field_rejected reason=reserved_parameter" in caplog.text
    assert "private-name@example.test" not in caplog.text


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ('{"Key":"private-name@example.test"}', "reserved_parameter"),
        ('["private-name@example.test"]', "not_object"),
        ('{"value":"private-name@example.test"', "invalid_json"),
    ],
)
def test_client_custom_field_rejections_log_pii_free_reason(
    payload, reason, monkeypatch, caplog
):
    monkeypatch.setattr(client_module, "API_KEY", "test-key")
    monkeypatch.setattr(client_module, "BASE_URL", "https://example.lawruler.com")
    client = client_module.LawRulerClient()

    with caplog.at_level(logging.WARNING):
        with pytest.raises((ValueError, TypeError)):
            client.create_lead_with_custom_fields(payload)

    assert f"custom_fields_rejected reason={reason}" in caplog.text
    assert "private-name@example.test" not in caplog.text
