# MCP specification delta: 2025-11-25 to 2026-07-28

Research date: 2026-08-09. Sources are limited to the official MCP
specification and official MCP Python SDK documentation.

## Current target and migration release

The repository currently targets MCP `2025-11-25`:

- `pyproject.toml` declares `mcp[cli]>=1.28.1,<2`, and `uv.lock` resolves
  `mcp==1.28.1`.
- The installed SDK reports `LATEST_PROTOCOL_VERSION == "2025-11-25"`.
- `lawruler_mcp/server.py` constructs the v1 `FastMCP` class and calls
  `mcp.run()` with its default stdio transport.
- The existing test suite has no protocol-version or raw-wire assertions.

The official changelog says `2026-07-28` follows `2025-11-25`
([spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)).
The implementation release is MCP Python SDK `2.0.0`, whose release notes say
it supports `2026-07-28` and all earlier revisions from one server
([SDK v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)).
The SDK's official
[v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/)
is the source for Python API changes.

Verdicts below mean:

- **AFFECTS-US**: this server exposes or relies on the changed surface. The SDK
  may implement the wire behavior, but this migration must pin or test it.
- **NOT-APPLICABLE**: the feature or direction is absent here and will not be
  added merely because the new revision permits it.

## Protocol negotiation and lifecycle

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Protocol sessions and `Mcp-Session-Id` are removed; application state must use explicit handles. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The server has no MCP session state. Modern raw-wire tests must prove requests do not acquire or require a session header. |
| Modern requests remove `initialize` and instead carry version, capabilities, and recommended client identity in `_meta`; results should identify the server; version mismatch uses `UnsupportedProtocolVersionError`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | SDK v2 supplies the dual-era dispatcher. Tests must exercise modern stateless requests and preserve legacy negotiation. |
| Servers must implement `server/discover`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | This mandatory RPC must advertise `2026-07-28`, server identity, and this server's tool/resource/prompt capabilities. |
| Every result requires `resultType`, normally `"complete"`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Discovery, list, read, prompt, and tool results are all exposed. |
| Multi Round-Trip Requests replace server-initiated requests. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No tool, resource, or prompt uses roots, sampling, elicitation, or another server-to-client request. |
| `ping`, `logging/setLevel`, and `notifications/roots/list_changed` are removed; protocol logs require per-request opt-in. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server implements none of these methods and uses only application stderr output. |

## Transports and notifications

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Streamable HTTP POST requires `Mcp-Method` and, for named operations, `Mcp-Name`; `x-mcp-header` can map tool parameters to headers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Production remains stdio-only, but the same SDK server exposes its Streamable HTTP app and the required fleet raw-wire suite must prove header validation. No tool opts into `x-mcp-header`. |
| HTTP GET and resource subscribe/unsubscribe are replaced by `subscriptions/listen`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | SDK-managed list-change/resource-subscription declarations are part of the high-level server's discovery result. They are preserved without adding a publisher, event store, or custom bus. |
| SSE resumption/redelivery is removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The repo has no HTTP event store, `Last-Event-ID`, or SSE resumption logic. |
| Legacy HTTP+SSE is deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The production entry point is stdio and does not expose the legacy transport. |

## Capabilities and extensions

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Client and server capabilities gain `extensions`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Discovery exposes this shape; the tests must prove no unused extension is advertised. |
| Core tasks move to the `io.modelcontextprotocol/tasks` extension. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server has no task handlers or task-augmented tools, and SDK v2.0.0 does not implement that extension. |
| Roots, Sampling, and Logging are deprecated; sampling `includeContext` values are also deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | None is declared or used. |

## Tools, resources, prompts, and cache semantics

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Tool, prompt, resource, resource-template list results and resource reads require `ttlMs` and `cacheScope`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes all three primitive types. Tests will assert SDK v2's conservative `ttlMs: 0`, `cacheScope: private` defaults. |
| `tools/list` should be deterministic. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The 15 registered tools must appear in identical order across independent listings. |
| Tool schemas accept JSON Schema 2020-12 and `structuredContent` may be any JSON value. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Decorators generate the 15 tool schemas. SDK v2 owns validation; tests will prove the generated object schemas remain valid. |
| Resource-not-found changes from `-32002` to Invalid Params `-32602`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server registers three static resources; an unknown URI must produce `-32602`. |
| URL elicitation completion fields are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server performs no elicitation. |
| Generated schema numeric types were corrected. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#other-schema-changes) | **NOT-APPLICABLE** | The repo neither vendors the MCP schema artifact nor directly validates against that meta-schema. |

## Authorization and security

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Authorization responses should carry RFC 9207 `iss`; MCP clients must validate it. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This is neither an MCP authorization server nor an MCP OAuth client. Its LawRuler API-key setup is downstream application authentication. |
| Dynamic Client Registration requires `application_type`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The code does not dynamically register an MCP client. |
| Persisted MCP client credentials must be issuer-bound. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The credential module stores a LawRuler API key and portal URL, not MCP client registrations. |
| Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server neither hosts DCR nor acts as a dynamically registered MCP client. |

## Errors, metadata, and observability

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| MCP reserves `-32020..-32099`; header mismatch, missing capability, and unsupported version use `-32020`, `-32021`, and `-32022`; unknown methods use `-32601`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Raw-wire tests must prove the reachable header-mismatch, unsupported-version, and unknown-method cases. There is no resolver-routed operation with which to manufacture `-32021`. |
| `_meta` formally carries W3C trace-context keys. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server has no MCP tracing integration. |

The governance and SEP-process changes do not impose runtime work. The feature
lifecycle is respected by not adding deprecated Roots, Sampling, Logging,
HTTP+SSE, or DCR behavior.
