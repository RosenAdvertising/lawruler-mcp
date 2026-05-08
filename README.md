# lawruler-mcp

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

Set via `~/.lawruler-mcp/.env` (created by setup wizard):

```
LAWRULER_BASE_URL=https://yourfirm.lawruler.com
LAWRULER_API_KEY=your_api_key
```

Find your API key in LawRuler: **Setup → 3rd Party Integrations**

## Tools (15)

**Create Leads**
- `create_lead` — core fields (name, phone, email, case type)
- `create_lead_full` — all fields including address, DOB, contact preferences
- `create_lead_obo` — on-behalf-of (skips duplicate check)

**Retrieve**
- `get_lead` — retrieve lead by LeadID

**Update Status & Assignment**
- `update_lead_status`, `update_lead_assignee`, `update_lead_owner`, `update_lead_case_type`

**Update Content**
- `update_lead_summary`, `add_conversation_note`, `add_tags_to_lead`, `update_lead_language`

**Update Contact Info**
- `update_lead_contact_info` — phone, email, address

**Custom Fields**
- `set_custom_field` — single custom field by API name
- `update_lead_fields` — bulk update multiple fields + custom fields via JSON
