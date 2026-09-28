# MCP 2026-07-28 migration

## Current implementation

LawRuler requires `mcp[cli]>=2.2,<3`; `uv.lock` resolves both `mcp` and
`mcp-types` to 2.2.0. The server uses SDK `MCPServer` and keeps its stdio entry
point, 15 tools, three resources, and three prompts. The LawRuler API-key and
portal configuration, credential lookup, request behavior, and tool responses
are unchanged by this migration.

The SDK negotiates protocol `2026-07-28` with modern clients and retains
`2025-11-25` compatibility for legacy clients. Its modern dispatcher handles
sessionless requests and `server/discover`. The protocol mapping and source
links are in [SPEC-DELTA-2026-07-28.md](SPEC-DELTA-2026-07-28.md).

## Protocol coverage

The offline tests exercise modern discovery, version negotiation, routing
headers, error codes, tool/resource/prompt listings, resource reads, and a
structured tool result. They assert `resultType: complete`, private zero-TTL
cache hints, deterministic tool order, and no unused extension declaration.
HTTP requests use an in-process SDK app; the production entry point remains
stdio. No MCP session state, publisher, event store, or custom HTTP route was
added.

The LawRuler API has no vendor list or auto-pagination operation to migrate.
Validation-rejection logs use fixed reason codes rather than supplied values.
The server does not serve browser pages or implement CSP. These are scope notes,
not claims of live service verification.

## Reproduce the local checks

With the locked development environment installed and fixture credentials set
before importing the package:

```bash
LAWRULER_API_KEY=offline-fixture LAWRULER_BASE_URL=https://lawruler.invalid LAWRULER_MCP_USE_KEYRING=0 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/python tests/spec_check.py
uvx --offline ruff check lawruler_mcp/client.py lawruler_mcp/server.py tests/spec_check.py tests/test_security.py tests/test_spec_2026_07_28.py
uv lock --check --offline
```

The tests mock LawRuler requests or use an in-process MCP transport. They do
not verify a live LawRuler account, hosted runtime, or other platforms.

## Open product decision

MCP 2.2.0 masks exception messages other than `ToolError` and `ResourceError`
from clients. Keeping that masking limits leakage; explicitly safe `ToolError`
messages could provide more actionable feedback. Toby should decide which
validation and vendor errors, if any, warrant such messages. Existing exception
handling remains unchanged.
