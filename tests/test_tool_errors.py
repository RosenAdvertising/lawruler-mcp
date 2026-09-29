import asyncio
import logging
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock
from typing import Any, cast

import pytest
import requests
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.exceptions import ResourceError
from mcp.types import CallToolRequestParams, CallToolResult, TextContent

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


def call_tool(name, arguments) -> CallToolResult:
    params = CallToolRequestParams(name=name, arguments=arguments)
    result = asyncio.run(server_module.mcp._handle_call_tool(cast(Any, None), params))
    assert isinstance(result, CallToolResult)
    return result


def setup_http(monkeypatch, responses):
    monkeypatch.setattr(client_module, "API_KEY", "fake-key")
    monkeypatch.setattr(client_module, "BASE_URL", "https://lawruler.invalid")
    client = client_module.LawRulerClient()
    client.session.post = Mock(side_effect=responses)
    monkeypatch.setattr(server_module, "_c", lambda: client)
    return client


def result_text(result: CallToolResult) -> str:
    assert result.is_error is True
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    return result.content[0].text


def test_missing_credentials_result_is_actionable(monkeypatch):
    monkeypatch.setattr(client_module, "API_KEY", "")
    monkeypatch.setattr(client_module, "BASE_URL", "")
    monkeypatch.setattr(server_module, "_c", client_module.LawRulerClient)

    text = result_text(call_tool("get_lead", {"lead_id": 1}))

    assert text == (
        "LawRuler credentials are missing. Run `lawruler-mcp-setup` or set "
        "LAWRULER_API_KEY and LAWRULER_BASE_URL. Restart the MCP server after changing credentials."
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
            "LawRuler access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawruler-mcp-setup if so).",
        ),
        (
            404,
            "LawRuler endpoint was not found (HTTP 404). Check the configured portal URL and API endpoint.",
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
    [("900000", 900000, 0), ("not-a-number SECRET", 10, 10)],
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
    assert waits == ([] if header == "900000" else [sleep, sleep])
    if header != "900000":
        assert header not in text
    assert cast(Mock, client.session.post).call_count == (
        1 if header == "900000" else 3
    )


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

    assert result_text(result) == "LawRuler tool execution failed."
    assert sentinel not in caplog.text
    assert "Traceback" not in caplog.text


def test_arbitrary_exception_does_not_unwrap_known_nested_cause(monkeypatch):
    class BrokenClient:
        def get_lead(self, _lead_id):
            try:
                raise requests.Timeout("SECRET-NESTED")
            except requests.Timeout as cause:
                raise RuntimeError("outer-private") from cause

    monkeypatch.setattr(server_module, "_c", BrokenClient)
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert result_text(result) == "LawRuler tool execution failed."


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            requests.Timeout("PRIVATE-ERROR"),
            "LawRuler request timed out. The outcome is unknown; check whether the action completed before retrying.",
        ),
        (
            requests.ConnectionError("PRIVATE-ERROR"),
            "Could not connect to LawRuler. The outcome is unknown; check whether the action completed before retrying.",
        ),
        (ValueError("PRIVATE-ERROR"), "LawRuler tool execution failed."),
        (ToolError("PRIVATE-ERROR"), "LawRuler tool execution failed."),
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


@pytest.mark.parametrize(
    "body",
    [
        {"success": False, "message": "PRIVATE-VENDOR-TEXT"},
        {"error": "PRIVATE-VENDOR-TEXT"},
    ],
)
def test_http_200_json_failure_envelope_is_tool_error(monkeypatch, body):
    setup_http(monkeypatch, [Response(200, body, {"Content-Type": "application/json"})])
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert (
        result_text(result) == "LawRuler request failed (HTTP 200): request_rejected."
    )


def test_http_200_plaintext_failure_is_tool_error(monkeypatch):
    setup_http(monkeypatch, [Response(200, text="PRIVATE-VENDOR-TEXT")])
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert (
        result_text(result) == "LawRuler request failed (HTTP 200): request_rejected."
    )


def test_http_200_xml_error_envelope_is_tool_error(monkeypatch):
    setup_http(
        monkeypatch,
        [Response(200, text="<Response><Error>PRIVATE-VENDOR-TEXT</Error></Response>")],
    )
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert (
        result_text(result) == "LawRuler request failed (HTTP 200): request_rejected."
    )


@pytest.mark.parametrize(
    "response",
    [
        Response(200, {}, {"Content-Type": "application/json"}),
        Response(200, text="<Response>Lead not found</Response>"),
        Response(200, text="<Response />"),
    ],
)
def test_http_200_empty_or_malformed_success_envelopes_are_errors(
    monkeypatch, response
):
    setup_http(monkeypatch, [response])
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert result_text(result) in {
        "LawRuler request failed (HTTP 200): request_rejected.",
        "LawRuler request failed (HTTP 200): invalid_response.",
    }


@pytest.mark.parametrize("response", [Response(400), Response(403), Response(500)])
def test_empty_failure_bodies_remain_errors(monkeypatch, response):
    setup_http(monkeypatch, [response])
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert result_text(result).startswith(("LawRuler ", "Lawruler "))


def test_retry_sleep_budget_spans_multiple_429_responses(monkeypatch):
    client = setup_http(
        monkeypatch,
        [
            Response(429, headers={"Retry-After": "40"}),
            Response(429, headers={"Retry-After": "30"}),
        ],
    )
    waits = []
    monkeypatch.setattr(client_module.time, "sleep", waits.append)
    result = call_tool("get_lead", {"lead_id": 1})
    assert result.is_error is True
    assert result_text(result) == "LawRuler rate limit reached. Retry after 30 seconds."
    assert waits == [40]
    assert cast(Mock, client.session.post).call_count == 2


def test_data_request_has_timeout(monkeypatch):
    client = setup_http(
        monkeypatch,
        [Response(200, {"LeadID": 1}, {"Content-Type": "application/json"})],
    )
    call_tool("get_lead", {"lead_id": 1})
    assert (
        cast(Mock, client.session.post).call_args.kwargs["timeout"]
        == client_module.REQUEST_TIMEOUT
    )


def test_setup_request_has_timeout(monkeypatch):
    import lawruler_mcp.setup.oauth_flow as setup

    post = Mock(return_value=Response(200, text="<Response />"))
    monkeypatch.setattr(setup.requests, "post", post)
    setup.test_connection("https://firm.invalid", "fake-key")
    assert post.call_args.kwargs["timeout"] == setup.REQUEST_TIMEOUT


@pytest.mark.parametrize(
    "error", [requests.Timeout("sentinel"), requests.ConnectionError("sentinel")]
)
def test_write_transport_failure_warns_unknown_outcome(monkeypatch, error):
    setup_http(monkeypatch, [error])
    result = call_tool("update_lead_status", {"lead_id": 1, "status": "New"})
    assert result.is_error is True
    assert "outcome is unknown" in result_text(result)
    assert "check whether the action completed before retrying" in result_text(result)
    assert "sentinel" not in result_text(result)


def test_verify_entrypoint_hides_unknown_exception(monkeypatch, capsys):
    import lawruler_mcp.setup.verify as verify

    monkeypatch.setattr(verify, "API_KEY", "fake-key")
    monkeypatch.setattr(
        verify, "BASE_URL", "https://private.invalid/path?token=sentinel"
    )
    monkeypatch.setattr(
        verify,
        "LawRulerClient",
        lambda: (_ for _ in ()).throw(RuntimeError("KEY-SECRET")),
    )
    with pytest.raises(SystemExit) as exc:
        verify.main()
    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert "lawruler-mcp-setup" in output
    assert "sentinel" not in output and "KEY-SECRET" not in output


def test_verify_entrypoint_without_credentials_is_actionable(monkeypatch, capsys):
    import lawruler_mcp.setup.verify as verify

    monkeypatch.setattr(verify, "API_KEY", "")
    monkeypatch.setattr(verify, "BASE_URL", "")
    with pytest.raises(SystemExit) as exc:
        verify.main()
    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert "LAWRULER_API_KEY and LAWRULER_BASE_URL" in output
    assert "lawruler-mcp-setup" in output


@pytest.mark.parametrize(
    "inputs, message",
    [
        ([], "Portal URL is required."),
        (["https://firm.invalid"], "API Key is required."),
    ],
)
def test_setup_entrypoint_handles_eof_and_empty_inputs(
    monkeypatch, capsys, inputs, message
):
    import lawruler_mcp.setup.oauth_flow as setup

    answers = iter(inputs)

    def read(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", read)
    monkeypatch.setattr(setup, "getpass", read)
    with pytest.raises(SystemExit) as exc:
        setup.main()
    assert exc.value.code == 1
    assert message in capsys.readouterr().out


def test_setup_entrypoint_bad_key_is_safe(monkeypatch, capsys):
    import lawruler_mcp.setup.oauth_flow as setup

    answers = iter(["https://firm.invalid", "fake-bad-key"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(setup, "getpass", lambda _prompt: next(answers))
    monkeypatch.setattr(
        setup.requests, "post", lambda *a, **k: Response(401, text="SECRET-RESPONSE")
    )
    with pytest.raises(SystemExit) as exc:
        setup.main()
    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert "authentication failed" in output
    assert "SECRET-RESPONSE" not in output and "fake-bad-key" not in output


def test_setup_entrypoint_403_uses_required_permission_guidance(monkeypatch, capsys):
    import lawruler_mcp.setup.oauth_flow as setup

    answers = iter(["https://firm.invalid", "fake-key"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(setup, "getpass", lambda _prompt: next(answers))
    monkeypatch.setattr(
        setup.requests, "post", lambda *a, **k: Response(403, text="PRIVATE")
    )
    with pytest.raises(SystemExit) as exc:
        setup.main()
    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert (
        "LawRuler access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawruler-mcp-setup if so)."
        in output
    )
    assert "PRIVATE" not in output and "fake-key" not in output


def test_installed_setup_command_rejects_fake_bad_key_safely():
    class UnauthorizedHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"PRIVATE-VENDOR-RESPONSE")

        def log_message(self, *_args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), UnauthorizedHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        command = subprocess.run(
            [".venv/bin/lawruler-mcp-setup"],
            input=f"http://127.0.0.1:{httpd.server_port}\nfake-bad-key\n",
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        httpd.server_close()
    assert command.returncode == 1
    assert "authentication failed" in command.stdout
    assert "fake-bad-key" not in command.stdout
    assert "PRIVATE-VENDOR-RESPONSE" not in command.stdout
    assert "Traceback" not in command.stdout + command.stderr


def test_installed_verify_command_without_credentials_is_actionable():
    command = subprocess.run(
        [".venv/bin/lawruler-mcp-verify"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert command.returncode == 1
    assert "LAWRULER_API_KEY and LAWRULER_BASE_URL" in command.stdout
    assert "lawruler-mcp-setup" in command.stdout
    assert "Traceback" not in command.stdout + command.stderr


def test_installed_verify_command_fake_bad_key_is_safe():
    class UnauthorizedHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"PRIVATE-VENDOR-RESPONSE")

        def log_message(self, *_args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), UnauthorizedHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        import os

        env = os.environ.copy()
        env["LAWRULER_API_KEY"] = "fake-bad-key"
        env["LAWRULER_BASE_URL"] = f"http://127.0.0.1:{httpd.server_port}"
        command = subprocess.run(
            [".venv/bin/lawruler-mcp-verify"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        httpd.server_close()
    assert command.returncode == 1
    assert "authentication was rejected" in command.stdout
    assert "fake-bad-key" not in command.stdout + command.stderr
    assert "PRIVATE-VENDOR-RESPONSE" not in command.stdout + command.stderr
    assert "Traceback" not in command.stdout + command.stderr


def test_setup_entrypoint_http_200_error_envelope_fails_safely(monkeypatch, capsys):
    import lawruler_mcp.setup.oauth_flow as setup

    answers = iter(["https://firm.invalid", "fake-key"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(setup, "getpass", lambda _prompt: next(answers))
    monkeypatch.setattr(
        setup.requests,
        "post",
        lambda *a, **k: Response(200, text='{"success":false,"message":"PRIVATE"}'),
    )
    with pytest.raises(SystemExit) as exc:
        setup.main()
    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert "failure response (HTTP 200)" in output
    assert "PRIVATE" not in output and "fake-key" not in output


def test_resource_exception_is_masked_without_traceback(monkeypatch, caplog):
    manager = server_module.mcp._resource_manager
    monkeypatch.setattr(
        manager,
        "get_resource",
        Mock(side_effect=RuntimeError("URL=PRIVATE-URL TOKEN=PRIVATE-TOKEN")),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            ResourceError, match="Unable to read the requested LawRuler resource"
        ):
            asyncio.run(
                server_module.mcp.read_resource("lawruler://lead_status_options")
            )
    assert "PRIVATE-URL" not in caplog.text and "PRIVATE-TOKEN" not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    "body, expected",
    [
        ("<Response><Error>PRIVATE", "invalid_response"),
        ("<Error>PRIVATE</Error>", "request_rejected"),
        (
            "<Response><Result><Error>PRIVATE</Error></Result></Response>",
            "request_rejected",
        ),
        ('"PRIVATE"', "request_rejected"),
        ('{"Status":"failure","message":"PRIVATE"}', "request_rejected"),
    ],
)
def test_unrecognized_and_nested_failure_bodies_never_succeed(
    monkeypatch, body, expected
):
    headers = {"Content-Type": "application/json"} if body.startswith('"') else {}
    setup_http(monkeypatch, [Response(200, "PRIVATE", headers, body)])
    result = call_tool("get_lead", {"lead_id": 1})
    assert result_text(result) == f"LawRuler request failed (HTTP 200): {expected}."


@pytest.mark.parametrize("header", ["60.1", "Thu, 01 Jan 1970 00:01:01 GMT"])
def test_fractional_and_date_retry_delays_are_not_shortened(monkeypatch, header):
    setup_http(monkeypatch, [Response(429, headers={"Retry-After": header})])
    waits = []
    monkeypatch.setattr(client_module.time, "sleep", waits.append)
    monkeypatch.setattr(client_module.time, "time", lambda: 0)
    assert (
        result_text(call_tool("get_lead", {"lead_id": 1}))
        == "LawRuler rate limit reached. Retry after 61 seconds."
    )
    assert waits == []


def test_sentinel_identifier_stays_in_post_body(monkeypatch):
    client = setup_http(
        monkeypatch,
        [Response(200, {"LeadID": 1}, {"Content-Type": "application/json"})],
    )
    client.get_lead(cast(Any, "../x"))
    sent = cast(Mock, client.session.post).call_args
    assert sent.args == ("https://lawruler.invalid/api-legalcrmapp.aspx",)
    assert sent.kwargs["data"]["LeadID"] == "../x"


@pytest.mark.parametrize(
    "body",
    ["", "<Error>PRIVATE</Error>", "<broken", '{"Status":"failure"}', '"PRIVATE"'],
)
def test_setup_uses_same_failure_envelope_policy(body):
    from lawruler_mcp.setup.oauth_flow import _failure_envelope

    assert _failure_envelope(body) is True


def test_verify_preserves_safe_permission_guidance(monkeypatch, capsys):
    from lawruler_mcp.errors import PermissionDeniedError
    from lawruler_mcp.setup import verify

    monkeypatch.setattr(verify, "API_KEY", "fake")
    monkeypatch.setattr(verify, "BASE_URL", "https://offline.invalid")
    monkeypatch.setattr(
        verify, "LawRulerClient", lambda: (_ for _ in ()).throw(PermissionDeniedError())
    )
    with pytest.raises(SystemExit) as stopped:
        verify.main()
    assert stopped.value.code == 1
    assert (
        "✗ Verification failed: " + str(PermissionDeniedError())
        in capsys.readouterr().out
    )


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError])
def test_setup_post_transport_failure_has_unknown_outcome(monkeypatch, capsys, failure):
    from lawruler_mcp.setup import oauth_flow as setup

    monkeypatch.setattr("builtins.input", lambda _: "https://portal.invalid")
    monkeypatch.setattr(setup, "getpass", lambda _: "fake-key")

    def fail(*args, **kwargs):
        raise failure("PRIVATE-TRANSPORT-SENTINEL")

    monkeypatch.setattr(setup.requests, "post", fail)
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 1
    text = capsys.readouterr().out
    assert text.endswith(
        "✗ LawRuler setup request timed out or lost its connection; the outcome is unknown. "
        "Check whether it completed before retrying setup.\n"
    )
    assert "PRIVATE-TRANSPORT-SENTINEL" not in text
