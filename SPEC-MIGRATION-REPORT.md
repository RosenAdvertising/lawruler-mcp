# MCP 2026-07-28 migration report

## Result

`lawruler-mcp` required migration. The default-branch baseline used MCP Python
SDK `1.28.1`, whose installed `LATEST_PROTOCOL_VERSION` was `2025-11-25`, and
constructed the v1 `FastMCP` class. It now pins `mcp[cli]==2.0.0`, locks
`mcp-types==2.0.0`, reports protocol `2026-07-28`, and constructs SDK v2's
`MCPServer`.

The authoritative per-change classification and official citations are in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md). No deployment, live
LawRuler account, or live API was touched. Imports followed the repository's
normal read-only credential lookup; no credential was printed, changed, or
sent in a request.

## Implementation

- Replaced `FastMCP` with `MCPServer`; the decorator API and all 15 tools,
  three resources, and three prompts are preserved.
- Kept `mcp.run()`'s stdio default. This repository had no production HTTP
  transport options to relocate; tests construct an SDK-owned stateless HTTP
  app only to inspect the modern wire protocol.
- Preserved the LawRuler API-key and portal credential model, keyring/file
  fallback, request timeout/retry behavior, resource contents, prompts, and
  tool results.
- Kept SDK v2's dual-era behavior: modern clients negotiate `2026-07-28`, and
  legacy clients still negotiate `2025-11-25`.
- Kept conservative SDK cache defaults (`ttlMs: 0`, `cacheScope: private`) and
  added no MCP session state, extension, task system, publisher, or event store.
- Added a small protocol guard and an explicit Python-3.10 core Ruff policy.

## AFFECTS-US mapping

| AFFECTS-US item | Handling | Commit |
| --- | --- | --- |
| Sessionless modern protocol and per-request metadata | SDK v2 dual-era dispatcher; raw modern requests prove no session header is required | `29ef48d`; `ee3bf6f` |
| Required `server/discover` | Exact supported version, identity, capabilities, cache fields, and `resultType` asserted | `ee3bf6f` |
| Required `resultType` | Discovery, list, resource-read, and tool results asserted complete | `ee3bf6f` |
| Modern HTTP routing headers | Raw `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` requests plus missing/mismatched-header regressions | `ee3bf6f` |
| SDK-managed subscription declarations | Existing high-level capability declarations preserved; no new publisher or bus | `29ef48d`; `ee3bf6f` |
| Capability `extensions` | Discovery proves no unused extension is advertised | `ee3bf6f` |
| Required cache hints | Private zero-TTL hints asserted for all list categories and resource reads | `ee3bf6f` |
| Deterministic `tools/list` | Two independent listings assert the same 15 names in the same order | `ee3bf6f` |
| JSON Schema 2020-12/general structured content | SDK v2 model implementation; generated object schemas and a normal structured tool result asserted | `29ef48d`; `ee3bf6f` |
| Resource-not-found `-32602` | Unknown resource regression asserts Invalid Params | `ee3bf6f` |
| New reserved error allocation | Header mismatch `-32020`, unsupported version `-32022`, and unknown method `-32601` asserted | `ee3bf6f` |

## Canary sibling checks

- **A — LIST-TOOL LIMIT/ORDER: N-A.** The server has no LawRuler vendor list
  tool or auto-pagination path. MCP `tools/list` ordering is deterministic and
  regression-tested, but there is no vendor limit/order parameter to change.
- **B — SILENT REJECTIONS: FIXED.** Identified validation guards now log only
  fixed reason codes: missing client configuration, unsafe XML, malformed or
  non-object custom-field JSON, and reserved-parameter injection. Tests cover
  the reasons and prove supplied PII values do not enter the log.
- **C — ORIGIN/CSP: N-A.** Production is stdio-only and the repository serves
  no browser pages, HTML, custom web routes, or CSP response.
- **D — PII-IN-LOGS: CLEAN.** A source sweep found no `sub`, email, personal
  name, API key, or user-supplied field value passed to a logger. Server/client
  rejection logs contain only event names, reason codes, or numeric retry
  timing. The setup and verification commands retain their interactive stdout
  behavior; they are not service log sites.

## Verification

Baseline on default branch, installed from the original lock with Python 3.12:

- `uv run pytest -q`: **5/5 passed**.
- `uvx ruff check .`: **failed with 18 pre-existing findings** under Ruff's
  unrestricted default policy.

Final verification, installed from the refreshed lock with Python 3.12:

- `uv sync --locked`: **passed** (`53` packages checked).
- `uv run pytest -q tests/test_spec_2026_07_28.py`: **7/7 passed**.
- `uv run pytest -q`: **20/20 passed**.
- `python tests/spec_check.py`: **PASS**, MCP `2026-07-28`.
- `uvx ruff check .`: **all checks passed** under the committed core policy.
- `git diff --check`: **passed**.

## Git history and sandbox handoff

The repository's `.git` directory rejected branch creation with `Operation not
permitted`. Commits were therefore created in the authorized scratchpad Git
database. Branch history at report-writing time is:

```text
ee3bf6f test: prove MCP 2026-07-28 conformance
29ef48d feat: migrate server to MCP 2026-07-28
6aecdb7 docs: document MCP 2026-07-28 delta
7ae1459 chore(deps): lock file maintenance (#47)
```

This report is the fourth conventional commit. The final scratchpad report
records its hash. The portable bundle must be imported into a writable clone;
it contains complete history through branch `spec-2026-07-28`. No push was
attempted.

## Remaining verification

All migration behavior is method-verified offline. No live LawRuler account or
credentials were available or needed, so downstream API calls were not
live-tested. No deployment was performed.
