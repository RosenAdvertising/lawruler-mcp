<p align="center"><a href="https://rosenadvertising.com/datalink/?utm_source=github&utm_medium=readme-banner&utm_campaign=lawruler-mcp"><img src="https://image.rosenadvertising.com/datalink/readme-banner-v2.png" alt="DataLink by Rosen Advertising: don't want to install and run this yourself? Get it hosted." width="100%"></a></p>

# LawRuler MCP server

[![CI](https://github.com/RosenAdvertising/lawruler-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/lawruler-mcp/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)
[![PyPI version](https://img.shields.io/pypi/v/lawruler-mcp.svg)](https://pypi.org/project/lawruler-mcp/)

Connect Claude and other MCP clients to LawRuler to create leads, track intake status, assign owners, add notes and tags, and update custom fields.

LawRuler MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for LawRuler, the legal CRM and intake platform. It registers 15 tools that read and write LawRuler leads. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. LawRuler credentials stay on the machine that runs the server: they come from the setup command and your operating system's keyring, never from the client.

## Features

- **Create leads**: create a lead with core fields, with the full field set (address, date of birth, contact preferences), or on behalf of another party without the duplicate check.
- **Retrieve leads**: look up a lead by LeadID.
- **Status and assignment**: update a lead's status, assignee, owner and case type.
- **Notes and tags**: update the case summary, add conversation notes and tags, and set the preferred language.
- **Contact details**: update phone, email and address.
- **Custom fields**: set one custom field, or update several standard and custom fields at once.

## Tools

The server registers 15 tools.

| Tool | What it does |
| --- | --- |
| `create_lead` | Create a lead with core fields: name, phone, email and case type. |
| `create_lead_full` | Create a lead with the full field set, including address, date of birth and contact preferences. |
| `create_lead_obo` | Create a lead on behalf of another party, with the duplicate check disabled. |
| `get_lead` | Retrieve a lead by LeadID. |
| `update_lead_status` | Update a lead's status. |
| `update_lead_assignee` | Assign a lead to a staff member. |
| `update_lead_owner` | Set the lead's owner, the attorney or partner who owns the matter. |
| `update_lead_case_type` | Update a lead's case type. |
| `update_lead_summary` | Update the case summary. |
| `add_conversation_note` | Add a conversation note or chat transcript. |
| `add_tags_to_lead` | Add one or more comma-separated tags. |
| `update_lead_language` | Update the preferred language. |
| `update_lead_contact_info` | Update phone, email and address. |
| `set_custom_field` | Set one custom field by its API field name. |
| `update_lead_fields` | Update several standard and custom fields at once, with custom fields as a JSON object. |

### Prompts and resources

The server also registers three prompts and three resources.

| Prompt | What it does |
| --- | --- |
| `new_intake_workflow` | Step-by-step intake creation for a contact name, phone, email and case type. |
| `intake_status_progression` | Moves one lead (`lead_id`) through the retainer-signing statuses. |
| `lead_triage_report` | Triages a set of known LeadIDs by priority. |

| Resource | What it provides |
| --- | --- |
| `lawruler://lead_status_options` | Common lead status values. |
| `lawruler://lead_fields_reference` | Reference guide to LawRuler lead field names and usage. |
| `lawruler://security-notes` | Security notes for the server. |

## Requirements

- Python 3.12+.
- A LawRuler portal and API key (in LawRuler: **Setup → 3rd Party Integrations**).
- An MCP client such as Claude Desktop.

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/lawruler-mcp.git
cd lawruler-mcp
uv sync --locked
```

Releases are also published to PyPI: `pip install lawruler-mcp` installs version 0.1.2, which predates the HTTP mode described below. Install from source to use HTTP mode.

## Configuration

Run the setup command once. It prompts for your portal URL and API key, tests the connection, and saves both values (see [Credential storage](#credential-storage)). Find your API key in LawRuler under **Setup → 3rd Party Integrations**.

```bash
uv run lawruler-mcp-setup
```

Check the connection at any time:

```bash
uv run lawruler-mcp-verify
```

Server messages that say to run `lawruler-mcp-setup` mean `uv run lawruler-mcp-setup` from your clone. The server reads its credentials once at startup, so restart the MCP server after changing them.

The server reads these variables, which you can also set in its environment:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LAWRULER_API_KEY` | Yes (saved by setup) | Keyring, then `~/.lawruler-mcp/.env` | LawRuler API key. |
| `LAWRULER_BASE_URL` | Yes (saved by setup) | Keyring, then `~/.lawruler-mcp/.env` | Portal origin, for example `https://yourfirm.lawruler.com`. See [Portal URL and write validation](#portal-url-and-write-validation). |
| `LAWRULER_MCP_USE_KEYRING` | No | `1` | Set to `0`, `false`, `no` or `off` to skip the operating system keyring and use the `.env` file. |

### Credential storage

By default both values are stored in your operating system's native secret store via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS | Backend |
| --- | --- |
| macOS | Keychain |
| Windows | Credential Manager |
| Linux | Secret Service (GNOME Keyring / KWallet) |

Secrets are saved under the service name `lawruler-mcp` when a keyring backend is available. The file fallback described below stores values on disk.

**File fallback.** On a host with no keyring backend (for example a headless Linux box without Secret Service), or if you set `LAWRULER_MCP_USE_KEYRING=0`, the values fall back to a `~/.lawruler-mcp/.env` file with `0600` permissions:

```text
LAWRULER_BASE_URL=https://yourfirm.lawruler.com
LAWRULER_API_KEY=your_api_key
```

On Windows, the file is stored in the user's profile and protected by Windows' default per-user access rules. On POSIX, files are created with `0600` permissions and writes fail closed if private permissions cannot be established.

**Read order.** A value set in the process environment is used as is. When a variable is not set, the server reads the OS keyring, then the `~/.lawruler-mcp/.env` file. A key exported in your shell therefore overrides the keyring and the file, and the keyring entry written by setup is used only while the variable is unset.

**Pluggable backend.** `keyring` lets you point at any secret store. For example, install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for an encrypted file backend, or a cloud backend, then select it with the standard `PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the [keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "lawruler": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/lawruler-mcp", "lawruler-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/lawruler-mcp` with the path of your clone, then restart Claude Desktop. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `LAWRULER_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool, including write tools, with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `LAWRULER_MCP_ALLOWED_HOSTS` and `LAWRULER_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LAWRULER_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. An empty value selects `stdio`. |
| `LAWRULER_MCP_HOST` | `127.0.0.1` | Bind address. An empty value selects `127.0.0.1`. `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other value requires `LAWRULER_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `LAWRULER_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `LAWRULER_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted. |

LawRuler credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
LAWRULER_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked lawruler-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`.

## Error handling

A failed tool call returns an MCP error result (`isError`) with a fixed message. The server never passes a LawRuler response body, a request URL or a credential back to the client.

| Situation | What the tool returns |
| --- | --- |
| Credentials missing | "LawRuler credentials are missing. Run `lawruler-mcp-setup` or set LAWRULER_API_KEY and LAWRULER_BASE_URL. Restart the MCP server after changing credentials." |
| Authentication rejected (HTTP 401) | "LawRuler authentication was rejected. Reauthorize with `lawruler-mcp-setup`." |
| Access denied (HTTP 403) | "LawRuler access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawruler-mcp-setup if so)." |
| Endpoint not found (HTTP 404) | "LawRuler endpoint was not found (HTTP 404). Check the configured portal URL and API endpoint." |
| Rate limited (HTTP 429) | After the retries below: "LawRuler rate limit reached. Retry after N seconds." |
| Any other HTTP error | "LawRuler request failed (HTTP 500): request_rejected." The status varies, and the reason is a fixed code such as `invalid_request`, `duplicate_record` or `service_unavailable`, or `request_rejected` when the response carries none. |
| HTTP 200 that carries a failure (JSON `success: false`, an `error` field, an XML error element, or plain text) | "LawRuler request failed (HTTP 200): request_rejected." (or `invalid_response` when the body cannot be parsed). |
| Timeout or connection failure | "LawRuler request timed out. The outcome is unknown; check whether the action completed before retrying." or "Could not connect to LawRuler. The outcome is unknown; check whether the action completed before retrying." |
| Invalid arguments | A message such as "Invalid argument 'lead_id': expected integer." or "Invalid argument 'LAWRULER_BASE_URL': expected an HTTPS portal URL on lawruler.com or its subdomains, without userinfo, query, fragment, or a path; run lawruler-mcp-setup." |
| Anything else | "LawRuler tool execution failed." |

Each request has a connect timeout of 3.05 seconds and a read timeout of 30 seconds, and redirects are never followed. On HTTP 429 the server waits for the `Retry-After` interval (10 seconds when the header is missing or unreadable) and retries, for up to three attempts in all and 60 seconds of total waiting; if the next wait would exceed what is left, the tool returns the rate-limit message at once. The server does not retry timeouts, connection failures or 5xx responses. A failed resource read returns "Requested LawRuler resource was not found." or "Unable to read the requested LawRuler resource."

At startup the server exits with a message on stderr and a non-zero status when `LAWRULER_BASE_URL` is set but is not a valid LawRuler portal origin, when `LAWRULER_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when a non-loopback `LAWRULER_MCP_HOST` is set without `LAWRULER_MCP_ALLOWED_HOSTS`.

## Portal URL and write validation

`LAWRULER_BASE_URL` must be an HTTPS origin on `lawruler.com` or a subdomain,
for example `https://yourfirm.lawruler.com`. Startup, setup and verify share
the same validator. IP addresses, unrelated domains, userinfo, query strings,
fragments, paths other than `/`, and ports other than 443 are rejected before
requests or setup credential storage. Redirects are disabled on every request.
LawRuler's [public API guide](https://kb.lawruler.com/knowledge-base/integrations/other/the-legal-crm-api-guide.htm)
uses `https://sample.lawruler.com/api-legalcrmapp.aspx`.

All three create tools require a nonblank `full_name`, or both `first_name`
and `last_name`. They also require `cell_phone` and primary `email`, which
the API guide's Available Fields table marks required. The existing tool
schemas are unchanged; missing data is rejected locally. All update paths require
at least one meaningful changed value; explicit custom values `0` and `false`
remain valid. For presence checks, text is normalized with Unicode NFKC and
whitespace and Unicode categories Cc/Cf/Zs/Zl/Zp are removed. NUL anywhere and
unpaired surrogate characters are rejected outright. Meaningful original values
(including non-ASCII names such as `José García`) are preserved in the request.

Custom API field names must match `[A-Za-z_][A-Za-z0-9_]*` after NFKC
normalization. Empty names, whitespace anywhere (including wrapped names),
control/format characters, surrogates and other punctuation are rejected.
Normalized, case-folded `key`, `operation`, `leadid`, `overridelead`, `returnjson`
and `returnxml` are reserved. Names are validated before empty values are omitted;
any invalid name rejects the call. Accepted names are sent in normalized form.
This applies to single custom-field writes and multi-field updates.
Verify prints a fixed success message without displaying the returned lead record.

## Testing

The test suite runs offline and needs no LawRuler account: every LawRuler API call is answered by a test double for the `requests` session. It covers tool requests and responses, input and custom-field-name validation (including Unicode edge cases), portal URL checks, error handling and rate-limit retries, credential file handling, the setup and verify commands, the stdio server, and the Streamable HTTP transport including the 2026-07-28 wire format, Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

## License

MIT. See [LICENSE](LICENSE).
