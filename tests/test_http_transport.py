"""In-process Streamable HTTP checks for MCP 2026-07-28."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import httpx2 as httpx
import pytest
from mcp import Client

from lawruler_mcp import server


PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
_LOOPBACK_BASE = "http://127.0.0.1:8080"


def _headers(method: str, *, name: str | None = None) -> dict[str, str]:
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    return headers


def _body(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
) -> dict[str, Any]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "lawruler-http-test", "version": "0"},
    }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


def _payload(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        data = None
        for line in response.text.splitlines():
            if line.startswith("data:"):
                data = line[len("data:") :].strip()
        assert data, response.text
        return json.loads(data)
    return response.json()


def _result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = _payload(response)
    assert payload["jsonrpc"] == "2.0"
    assert "mcp-session-id" not in response.headers
    return payload["result"]


def _input_schema(tool: Any) -> dict[str, Any]:
    if isinstance(tool, dict):
        schema = tool["inputSchema"]
    else:
        schema = getattr(tool, "input_schema", None)
        if schema is None:
            schema = tool.inputSchema
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True, mode="json", exclude_none=True)
    return json.loads(json.dumps(schema))


async def _open(app, base_url: str = _LOOPBACK_BASE):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url=base_url)


async def _post(
    client: httpx.AsyncClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
    name: str | None = None,
    header_overrides: dict[str, str] | None = None,
) -> httpx.Response:
    headers = _headers(method, name=name)
    if header_overrides:
        headers.update(header_overrides)
    return await client.post(
        "/mcp",
        headers=headers,
        json=_body(method, params, request_id=request_id),
    )


def test_tools_list_matches_stdio_and_requests_share_no_session(monkeypatch) -> None:
    monkeypatch.setenv("LAWRULER_MCP_HOST", "127.0.0.1")

    async def scenario():
        async with Client(server.mcp, cache=None) as client:
            stdio = await client.list_tools()
        app = server.create_serve_app()
        async with app.router.lifespan_context(app):
            async with await _open(app) as http:
                first = await _post(http, "tools/list", request_id=1)
                second = await _post(http, "tools/list", request_id=2)
        return stdio, first, second

    stdio, first, second = asyncio.run(scenario())
    first_result = _result(first)
    second_result = _result(second)
    http_names = [tool["name"] for tool in first_result["tools"]]
    stdio_names = [tool.name for tool in stdio.tools]
    assert http_names == stdio_names
    assert {tool["name"]: _input_schema(tool) for tool in first_result["tools"]} == {
        tool.name: _input_schema(tool) for tool in stdio.tools
    }
    assert [tool["name"] for tool in second_result["tools"]] == http_names
    assert "mcp-session-id" not in first.headers
    assert "mcp-session-id" not in second.headers


def test_connection_state_does_not_carry_between_http_requests(monkeypatch) -> None:
    """A marker stored on one request's Connection.state must be absent on the next."""
    monkeypatch.setenv("LAWRULER_MCP_HOST", "127.0.0.1")
    from mcp.server import _streamable_http_modern as modern
    from mcp.server.connection import Connection

    marker = "lawruler-prior-request"
    used: list[tuple[Connection, bool]] = []
    original_serve_one = modern.serve_one

    async def serve_and_mark(*args, **kwargs):
        connection = kwargs["connection"]
        carried = marker in connection.state
        used.append((connection, carried))
        if not carried:
            connection.state[marker] = len(used)
        return await original_serve_one(*args, **kwargs)

    monkeypatch.setattr(modern, "serve_one", serve_and_mark)

    async def scenario():
        app = server.create_serve_app()
        async with app.router.lifespan_context(app):
            async with await _open(app) as http:
                first = await _post(http, "tools/list", request_id=1)
                second = await _post(http, "tools/list", request_id=2)
        return first, second

    first, second = asyncio.run(scenario())
    assert first.status_code == 200
    assert second.status_code == 200
    assert [carried for _, carried in used] == [False, False]
    assert used[0][0] is not used[1][0]
    assert used[0][0].state is not used[1][0].state
    assert used[0][0].state[marker] == 1
    assert used[1][0].state[marker] == 2


def test_get_lead_runs_over_http(monkeypatch) -> None:
    from tests.test_tool_errors import Response, setup_http

    monkeypatch.setenv("LAWRULER_MCP_HOST", "127.0.0.1")
    client = setup_http(
        monkeypatch,
        [
            Response(
                200,
                {"LeadID": 7, "Status": "Test"},
                {"Content-Type": "application/json"},
            )
        ],
    )

    async def scenario():
        app = server.create_serve_app()
        async with app.router.lifespan_context(app):
            async with await _open(app) as http:
                return await _post(
                    http,
                    "tools/call",
                    {"name": "get_lead", "arguments": {"lead_id": 7}},
                    name="get_lead",
                )

    result = _result(asyncio.run(scenario()))
    assert result["isError"] is False
    assert result["structuredContent"] == {
        "result": '{\n  "LeadID": 7,\n  "Status": "Test"\n}'
    }
    sent = client.session.post.call_args
    assert client.session.post.call_count == 1
    assert sent.args == ("https://test.lawruler.com/api-legalcrmapp.aspx",)
    assert sent.kwargs["data"] == {
        "Operation": "GetStatus",
        "ReturnJSON": "True",
        "LeadID": "7",
        "Key": "fake-key",
    }


def test_stateless_lifespan_enters_once(monkeypatch) -> None:
    monkeypatch.setenv("LAWRULER_MCP_HOST", "127.0.0.1")
    enters: list[int] = []
    low = server.mcp._lowlevel_server
    original = low.lifespan

    @contextlib.asynccontextmanager
    async def counting(app):
        enters.append(1)
        async with original(app) as ctx:
            yield ctx

    monkeypatch.setattr(low, "lifespan", counting)

    async def scenario():
        app = server.create_serve_app()
        async with app.router.lifespan_context(app):
            async with await _open(app) as http:
                first = await _post(http, "tools/list", request_id=1)
                second = await _post(http, "server/discover", request_id=2)
        return first, second

    first, second = asyncio.run(scenario())
    assert first.status_code == 200
    assert second.status_code == 200
    assert enters == [1]


def test_bogus_transport_names_both_options(monkeypatch, capsys) -> None:
    monkeypatch.setenv("LAWRULER_MCP_TRANSPORT", "bogus")
    monkeypatch.setattr(server, "BASE_URL", "")
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 1
    message = capsys.readouterr().err
    assert "stdio" in message
    assert "streamable-http" in message


def test_default_transport_is_stdio(monkeypatch) -> None:
    monkeypatch.delenv("LAWRULER_MCP_TRANSPORT", raising=False)
    monkeypatch.setattr(server, "BASE_URL", "")
    called: list[str] = []

    def run() -> None:
        called.append("run")

    monkeypatch.setattr(server.mcp, "run", run)
    server.main()
    assert called == ["run"]
    assert server._requested_transport() == "stdio"


def test_allowed_hosts_refuse_other_host_and_bad_origin(monkeypatch) -> None:
    monkeypatch.setenv("LAWRULER_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("LAWRULER_MCP_ALLOWED_HOSTS", "lawruler.internal")
    monkeypatch.setenv("LAWRULER_MCP_ALLOWED_ORIGINS", "https://lawruler.internal")

    async def scenario():
        app = server.create_serve_app()
        async with app.router.lifespan_context(app):
            async with await _open(app, "http://evil.example") as evil:
                refused = await _post(evil, "tools/list")
            async with await _open(app, "http://lawruler.internal") as allowed:
                forbidden = await _post(
                    allowed,
                    "tools/list",
                    header_overrides={"origin": "https://evil.example"},
                )
        return refused, forbidden

    refused, forbidden = asyncio.run(scenario())
    assert refused.status_code == 421
    assert forbidden.status_code == 403


def test_non_loopback_host_without_allowed_hosts_exits(monkeypatch, capsys) -> None:
    monkeypatch.setenv("LAWRULER_MCP_HOST", "0.0.0.0")
    monkeypatch.delenv("LAWRULER_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit) as exc:
        server.create_serve_app()
    assert exc.value.code == 1
    assert "LAWRULER_MCP_ALLOWED_HOSTS" in capsys.readouterr().err


def test_non_integer_port_exits(monkeypatch, capsys) -> None:
    monkeypatch.setenv("PORT", "nope")
    with pytest.raises(SystemExit) as exc:
        server._port()
    assert exc.value.code == 1
    assert "PORT" in capsys.readouterr().err


def test_get_and_delete_are_method_not_allowed(monkeypatch) -> None:
    monkeypatch.setenv("LAWRULER_MCP_HOST", "127.0.0.1")

    async def scenario():
        app = server.create_serve_app()
        headers = {"mcp-protocol-version": PROTOCOL_VERSION}
        async with app.router.lifespan_context(app):
            async with await _open(app) as http:
                get = await http.get("/mcp", headers=headers)
                delete = await http.delete("/mcp", headers=headers)
        return get, delete

    get, delete = asyncio.run(scenario())
    assert get.status_code == 405
    assert delete.status_code == 405


def test_discover_advertises_protocol_and_version(monkeypatch) -> None:
    monkeypatch.setenv("LAWRULER_MCP_HOST", "127.0.0.1")

    async def scenario():
        app = server.create_serve_app()
        async with app.router.lifespan_context(app):
            async with await _open(app) as http:
                return await _post(http, "server/discover")

    result = _result(asyncio.run(scenario()))
    assert PROTOCOL_VERSION in result["supportedVersions"]
    version = result["_meta"][SERVER_INFO_META_KEY]["version"]
    assert isinstance(version, str) and version.strip()
