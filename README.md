# lawruler-mcp

[![PyPI version](https://img.shields.io/pypi/v/lawruler-mcp.svg)](https://pypi.org/project/lawruler-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server for LawRuler Legal CRM. Provides 15 tools for lead/intake creation, retrieval, and management.

## Setup

```bash
pip install lawruler-mcp
lawruler-mcp-setup   # prompts for portal URL + API key
lawruler-mcp-verify  # test connection
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "lawruler": {
      "command": "lawruler-mcp"
    }
  }
}
```

## Credentials

The setup wizard prompts for your portal URL (`LAWRULER_BASE_URL`) and API key
(`LAWRULER_API_KEY`). Find your API key in LawRuler:
**Setup → 3rd Party Integrations**.

By default both values are stored in your operating system's native secret store
via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS      | Backend                                  |
| ------- | ---------------------------------------- |
| macOS   | Keychain                                 |
| Windows | Credential Manager                       |
| Linux   | Secret Service (GNOME Keyring / KWallet) |

Secrets are saved under the service name `lawruler-mcp`. Nothing is written to
disk in clear text.

**File fallback.** On a host with no keyring backend (e.g. a headless Linux box
without Secret Service), or if you set `LAWRULER_MCP_USE_KEYRING=0`, the values
fall back to a `~/.lawruler-mcp/.env` file with `0600` permissions:

```text
LAWRULER_BASE_URL=https://yourfirm.lawruler.com
LAWRULER_API_KEY=your_api_key
```

**Read order.** Values resolve in the order OS keyring → process environment →
`.env` file. So a rotated key in the keyring always wins, and a value exported in
your shell overrides the file fallback without touching the keyring.

**Pluggable backend.** `keyring` lets you point at any secret store. For example,
install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for
an encrypted file backend, or a cloud backend, then select it with the standard
`PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the
[keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Tools (15)

### Create Leads

- `create_lead` — core fields (name, phone, email, case type)
- `create_lead_full` — all fields including address, DOB, contact preferences
- `create_lead_obo` — on-behalf-of (skips duplicate check)

### Retrieve

- `get_lead` — retrieve lead by LeadID

### Update Status & Assignment

- `update_lead_status`, `update_lead_assignee`, `update_lead_owner`, `update_lead_case_type`

### Update Content

- `update_lead_summary`, `add_conversation_note`, `add_tags_to_lead`, `update_lead_language`

### Update Contact Info

- `update_lead_contact_info` — phone, email, address

### Custom Fields

- `set_custom_field` — single custom field by API name
- `update_lead_fields` — bulk update multiple fields + custom fields via JSON
