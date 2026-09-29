import asyncio
import logging
from unittest.mock import Mock
from typing import Any, cast

import pytest
import requests
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolRequestParams

import lawruler_mcp.client as client_module
import lawruler_mcp.server as server_module


class Response:
    def __init__(self, status, payload=None, headers=None, text=""):
        self.status_code = status
        self.ok = 200 <= status < 400
        self.headers = headers or {}
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def call_tool(name, arguments):
    params = CallToolRequestParams(name=name, arguments=arguments)
    return asyncio.run(server_module.mcp._handle_call_tool(cast(Any, None), params))


def setup_http(monkeypatch, responses):
    monkeypatch.setattr(client_module, "API_KEY", "fake-key")
    monkeypatch.setattr(client_module, "BASE_URL", "https://lawruler.invalid")
    client = client_module.LawRulerClient()
    client.session.post = Mock(side_effect=responses)
    monkeypatch.setattr(server_module, "_c", lambda: client)
    return client


def result_text(result):
    assert result.is_error is True
    return result.content[0].text


def test_missing_credentials_result_is_actionable(monkeypatch):
    monkeypatch.setattr(client_module, "API_KEY", "")
    monkeypatch.setattr(client_module, "BASE_URL", "")
    monkeypatch.setattr(server_module, "_c", client_module.LawRulerClient)

    text = result_text(call_tool("get_lead", {"lead_id": 1}))

    assert text == (
        "LawRuler credentials are missing. Run `lawruler-mcp-setup` or set "
        "LAWRULER_API_KEY and LAWRULER_BASE_URL."
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            401,
            "LawRuler authentication was rejected. Reauthorize with `lawruler-mcp-setup`.",
        ),
        (
            403,
            "LawRuler authentication was rejected. Reauthorize with `lawruler-mcp-setup`.",
        ),
        (
            404,
            "LawRuler record was not found (HTTP 404). Check the LeadID and try again.",
        ),
        (400, "LawRuler request failed (HTTP 400): validation_error."),
    ],
)
def test_http_classes_are_actionable_and_sanitized(monkeypatch, status, expected):
    payload = (
        {"error": "validation_error"}
        if status == 400
        else {
            "error": "validation_error PRIVATE-PII https://evil.invalid/?token=sentinel"
        }
    )
    setup_http(monkeypatch, [Response(status, payload, text="API_KEY=sentinel")])

    assert result_text(call_tool("get_lead", {"lead_id": 5})) == expected


def test_unrecognized_vendor_reason_is_not_echoed(monkeypatch):
    secret = "TOKEN-SECRET-URL-PII"
    setup_http(monkeypatch, [Response(500, {"error": secret}, text=secret)])

    text = result_text(call_tool("get_lead", {"lead_id": 5}))

    assert text == "LawRuler request failed (HTTP 500): request_rejected."
    assert secret not in text


@pytest.mark.parametrize(
    ("header", "expected", "sleep"),
    [("900000", 30, 30), ("not-a-number SECRET", 10, 10)],
)
def test_429_retry_hint_is_parsed_and_capped(monkeypatch, header, expected, sleep):
    client = setup_http(
        monkeypatch,
        [Response(429, headers={"Retry-After": header}) for _ in range(3)],
    )
    waits = []
    monkeypatch.setattr(client_module.time, "sleep", waits.append)

    text = result_text(call_tool("get_lead", {"lead_id": 5}))

    assert text == f"LawRuler rate limit reached. Retry after {expected} seconds."
    assert waits == [sleep, sleep]
    assert header not in text
    assert cast(Mock, client.session.post).call_count == 3


@pytest.mark.parametrize(
    ("bad_value", "expected"),
    [
        (
            "not-json SECRET",
            "Invalid argument 'custom_fields_json': expected a JSON object.",
        ),
        (
            '{"Key":"secret"}',
            "Invalid argument 'custom_fields_json': expected an object without reserved keys.",
        ),
    ],
)
def test_custom_field_validation_is_tool_error(monkeypatch, bad_value, expected):
    client = Mock()
    monkeypatch.setattr(server_module, "_c", lambda: client)

    text = result_text(
        call_tool("update_lead_fields", {"lead_id": 7, "custom_fields_json": bad_value})
    )

    assert text == expected
    client.update_lead.assert_not_called()
    assert "SECRET" not in text


def test_schema_validation_does_not_echo_input_value_or_unknown_name(caplog):
    sentinel = "INPUT-PII-TOKEN-SENTINEL"
    with caplog.at_level(logging.INFO):
        result = call_tool("get_lead", {"lead_id": sentinel, "attacker-key": sentinel})

    text = result_text(result)
    assert text == "Invalid argument 'lead_id': expected integer."
    assert sentinel not in text
    assert "attacker-key" not in text
    assert sentinel not in caplog.text


def test_unknown_exception_is_masked_and_not_logged(caplog, monkeypatch):
    sentinel = "EXCEPTION-TOKEN-URL-PII-SENTINEL"

    class BrokenClient:
        def get_lead(self, _lead_id):
            raise RuntimeError(sentinel)

    monkeypatch.setattr(server_module, "_c", BrokenClient)
    with caplog.at_level(logging.ERROR):
        result = call_tool("get_lead", {"lead_id": 1})

    assert result_text(result) == "Error executing tool get_lead"
    assert sentinel not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            requests.Timeout("PRIVATE-ERROR"),
            "LawRuler request timed out. Retry shortly.",
        ),
        (
            requests.ConnectionError("PRIVATE-ERROR"),
            "Could not connect to LawRuler. Check connectivity and retry.",
        ),
        (ValueError("PRIVATE-ERROR"), "Error executing tool get_lead"),
        (ToolError("PRIVATE-ERROR"), "Error executing tool get_lead"),
    ],
)
def test_transport_and_unclassified_errors(monkeypatch, caplog, error, expected):
    client = setup_http(monkeypatch, [error])
    with caplog.at_level(logging.INFO):
        assert result_text(call_tool("get_lead", {"lead_id": 1})) == expected
    assert cast(Mock, client.session.post).call_count == 1
    assert "PRIVATE-ERROR" not in caplog.text
    assert "Traceback" not in caplog.text


def test_invalid_vendor_json_is_safe(monkeypatch):
    setup_http(
        monkeypatch,
        [
            Response(
                200,
                ValueError("PRIVATE-RESPONSE"),
                {"Content-Type": "application/json"},
                "PRIVATE-RESPONSE",
            )
        ],
    )
    assert (
        result_text(call_tool("get_lead", {"lead_id": 1}))
        == "LawRuler request failed (HTTP 200): invalid_response."
    )


def test_nonstring_vendor_code_preserves_status(monkeypatch):
    setup_http(monkeypatch, [Response(500, {"code": ["PRIVATE-RESPONSE"]})])
    assert (
        result_text(call_tool("get_lead", {"lead_id": 1}))
        == "LawRuler request failed (HTTP 500): request_rejected."
    )
