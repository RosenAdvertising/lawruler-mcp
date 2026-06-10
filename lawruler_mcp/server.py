#!/usr/bin/env python3
"""LawRuler (Legal CRM) MCP server — FastMCP tools for lead/intake management."""

import json
from mcp.server.fastmcp import FastMCP
from lawruler_mcp.client import LawRulerClient

mcp = FastMCP(
    "lawruler",
    instructions=(
        "LawRuler Legal CRM. Create and manage leads/intakes for law firms. "
        "All records are 'leads' or 'intakes' — use LeadID to retrieve or update existing records. "
        "CellPhone and Email are required for most intakes. "
        "Status, CaseType, LeadProvider are key classification fields."
    ),
)


def _c():
    return LawRulerClient()


# ── Create Leads / Intakes ─────────────────────────────────────────────────────


@mcp.tool()
def create_lead(
    first_name: str = "",
    last_name: str = "",
    full_name: str = "",
    cell_phone: str = "",
    email: str = "",
    case_type: str = "",
    lead_provider: str = "",
    status: str = "",
    summary: str = "",
    lead_assignee: str = "",
    lead_owner: str = "",
    hear: str = "",
    tags: str = "",
    language: str = "",
) -> str:
    """Create a new lead/intake. FirstName+LastName or FullName required. CellPhone and Email strongly recommended."""
    return json.dumps(
        _c().create_lead(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            cell_phone=cell_phone,
            email=email,
            case_type=case_type,
            lead_provider=lead_provider,
            status=status,
            summary=summary,
            lead_assignee=lead_assignee,
            lead_owner=lead_owner,
            hear=hear,
            tags=tags,
            language=language,
        ),
        indent=2,
    )


@mcp.tool()
def create_lead_full(
    first_name: str = "",
    last_name: str = "",
    full_name: str = "",
    cell_phone: str = "",
    email: str = "",
    email2: str = "",
    case_type: str = "",
    lead_provider: str = "",
    status: str = "",
    summary: str = "",
    address1: str = "",
    address2: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    county: str = "",
    home_phone: str = "",
    business_phone: str = "",
    business_name: str = "",
    dob: str = "",
    lead_assignee: str = "",
    lead_owner: str = "",
    hear: str = "",
    tags: str = "",
    contact_preference: str = "",
    when_to_contact: str = "",
    case_role: str = "",
    contact_type: str = "",
    campaign_name: str = "",
    language: str = "",
) -> str:
    """Create a new lead/intake with full field set including address, DOB, and contact preferences."""
    return json.dumps(
        _c().create_lead(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            cell_phone=cell_phone,
            email=email,
            email2=email2,
            case_type=case_type,
            lead_provider=lead_provider,
            status=status,
            summary=summary,
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            zip_code=zip_code,
            county=county,
            home_phone=home_phone,
            business_phone=business_phone,
            business_name=business_name,
            dob=dob,
            lead_assignee=lead_assignee,
            lead_owner=lead_owner,
            hear=hear,
            tags=tags,
            contact_preference=contact_preference,
            when_to_contact=when_to_contact,
            case_role=case_role,
            contact_type=contact_type,
            campaign_name=campaign_name,
            language=language,
        ),
        indent=2,
    )


@mcp.tool()
def create_lead_obo(
    first_name: str = "",
    last_name: str = "",
    full_name: str = "",
    cell_phone: str = "",
    email: str = "",
    case_type: str = "",
    lead_provider: str = "",
    summary: str = "",
    lead_assignee: str = "",
) -> str:
    """Create a lead with duplicate checking disabled (for On-Behalf-Of cases where the same contact has multiple matters)."""
    return json.dumps(
        _c().create_lead(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            cell_phone=cell_phone,
            email=email,
            case_type=case_type,
            lead_provider=lead_provider,
            summary=summary,
            lead_assignee=lead_assignee,
            disable_dup_check=True,
        ),
        indent=2,
    )


# ── Retrieve Leads ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_lead(lead_id: int) -> str:
    """Retrieve a lead/intake by LeadID. Returns contact info, status, case type, and all stored fields."""
    return json.dumps(_c().get_lead(lead_id), indent=2)


# ── Update Lead Status & Assignment ───────────────────────────────────────────


@mcp.tool()
def update_lead_status(lead_id: int, status: str) -> str:
    """Update the status of a lead/intake.
    Common values: New Lead, Emailed Intake Questionnaire, Sent Retainer Contract,
    Signed Retainer Contract, Converted to Case, Approved."""
    return json.dumps(_c().update_lead_status(lead_id, status), indent=2)


@mcp.tool()
def update_lead_assignee(lead_id: int, assignee: str) -> str:
    """Assign a lead/intake to a staff member (LeadAssignee — the user managing the lead)."""
    return json.dumps(_c().update_lead_assignee(lead_id, assignee), indent=2)


@mcp.tool()
def update_lead_owner(lead_id: int, owner: str) -> str:
    """Set the owner of a lead/intake (LeadOwner — the attorney or partner who owns the matter)."""
    return json.dumps(_c().update_lead_owner(lead_id, owner), indent=2)


@mcp.tool()
def update_lead_case_type(lead_id: int, case_type: str) -> str:
    """Update the case type of a lead/intake (e.g., Auto Accident, Workers Compensation, Divorce)."""
    return json.dumps(_c().update_lead_case_type(lead_id, case_type), indent=2)


# ── Update Lead Content ────────────────────────────────────────────────────────


@mcp.tool()
def update_lead_summary(lead_id: int, summary: str) -> str:
    """Update the case description/summary for a lead."""
    return json.dumps(_c().update_lead_summary(lead_id, summary), indent=2)


@mcp.tool()
def add_conversation_note(lead_id: int, conversation: str) -> str:
    """Add a conversation note or chat transcript to a lead."""
    return json.dumps(_c().add_conversation_note(lead_id, conversation), indent=2)


@mcp.tool()
def add_tags_to_lead(lead_id: int, tags: str) -> str:
    """Add tags to a lead. For multiple tags, separate with commas: 'New, Level 1, High Value'."""
    return json.dumps(_c().add_tags_to_lead(lead_id, tags), indent=2)


@mcp.tool()
def update_lead_language(lead_id: int, language: str) -> str:
    """Update the preferred language for a lead (e.g., Spanish, French, Mandarin)."""
    return json.dumps(_c().update_lead_language(lead_id, language), indent=2)


# ── Update Contact Info ────────────────────────────────────────────────────────


@mcp.tool()
def update_lead_contact_info(
    lead_id: int,
    cell_phone: str = "",
    home_phone: str = "",
    email: str = "",
    address1: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
) -> str:
    """Update contact information fields on a lead (phone, email, address)."""
    return json.dumps(
        _c().update_lead_contact_info(
            lead_id=lead_id,
            cell_phone=cell_phone,
            home_phone=home_phone,
            email=email,
            address1=address1,
            city=city,
            state=state,
            zip_code=zip_code,
        ),
        indent=2,
    )


# ── Custom Fields ─────────────────────────────────────────────────────────────


@mcp.tool()
def set_custom_field(lead_id: int, field_name: str, value: str) -> str:
    """Set a custom field on a lead. field_name is the API parameter name (e.g., custom2413).
    Custom field names are found in the LawRuler Intake Form Builder."""
    return json.dumps(_c().set_custom_field(lead_id, field_name, value), indent=2)


@mcp.tool()
def update_lead_fields(
    lead_id: int,
    status: str = "",
    case_type: str = "",
    lead_provider: str = "",
    hear: str = "",
    tags: str = "",
    summary: str = "",
    lead_assignee: str = "",
    lead_owner: str = "",
    contact_preference: str = "",
    when_to_contact: str = "",
    campaign_name: str = "",
    language: str = "",
    custom_fields_json: str = "",
) -> str:
    """Update multiple fields on an existing lead at once. custom_fields_json accepts a JSON object of field_name:value pairs for custom fields."""
    fields = {}
    if status:
        fields["Status"] = status
    if case_type:
        fields["CaseType"] = case_type
    if lead_provider:
        fields["LeadProvider"] = lead_provider
    if hear:
        fields["Hear"] = hear
    if tags:
        fields["Tags"] = tags
    if summary:
        fields["Summary"] = summary
    if lead_assignee:
        fields["LeadAssignee"] = lead_assignee
    if lead_owner:
        fields["LeadOwner"] = lead_owner
    if contact_preference:
        fields["ContactPreference"] = contact_preference
    if when_to_contact:
        fields["WhenToContact"] = when_to_contact
    if campaign_name:
        fields["CampaignName"] = campaign_name
    if language:
        fields["Language"] = language
    if custom_fields_json:
        try:
            custom = json.loads(custom_fields_json)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid custom_fields_json: {e}"})
        if not isinstance(custom, dict):
            return json.dumps({"error": "custom_fields_json must be a JSON object"})
        RESERVED = {
            "leadid",
            "overridelead",
            "key",
            "returnjson",
            "returnxml",
            "operation",
        }
        bad = RESERVED & {str(k).casefold() for k in custom.keys()}
        if bad:
            return json.dumps({"error": f"Reserved keys in custom_fields_json: {bad}"})
        fields.update(custom)
    return json.dumps(_c().update_lead(lead_id, override=True, **fields), indent=2)


# ── Resources ─────────────────────────────────────────────────────────────────


@mcp.resource("lawruler://lead_status_options", mime_type="application/json")
def lead_status_options_resource() -> str:
    """Common lead/intake status values — read-only reference data for classification."""
    return json.dumps(
        {
            "statuses": [
                "New Lead",
                "Emailed Intake Questionnaire",
                "Sent Retainer Contract",
                "Signed Retainer Contract",
                "Converted to Case",
                "Approved",
                "Not Retained",
                "Duplicate",
            ],
            "note": "Firm-specific custom statuses may also exist. Use get_lead to verify current value.",
        },
        indent=2,
    )


@mcp.resource("lawruler://lead_fields_reference", mime_type="application/json")
def lead_fields_reference_resource() -> str:
    """Reference guide for LawRuler lead/intake field names and usage."""
    return json.dumps(
        {
            "required_for_most_operations": ["CellPhone", "Email"],
            "name_fields": {
                "FirstName+LastName": "preferred for new leads",
                "FullName": "fallback when split name not available",
            },
            "classification_fields": ["Status", "CaseType", "LeadProvider", "Tags"],
            "assignment_fields": ["LeadAssignee", "LeadOwner"],
            "contact_fields": [
                "CellPhone",
                "HomePhone",
                "Email",
                "Address1",
                "City",
                "State",
                "Zip",
            ],
            "reserved_params_blocked": [
                "LeadID",
                "overridelead",
                "Key",
                "ReturnJSON",
                "ReturnXML",
                "Operation",
            ],
            "sensitive_fields": {
                "SSN": "NOT exposed as a tool parameter — must be handled client-side. Never echo SSN in outputs.",
                "DOB": "Available in create_lead_full; minimize use.",
            },
        },
        indent=2,
    )


@mcp.resource("lawruler://security-notes", mime_type="text/markdown")
def security_notes_resource() -> str:
    """Security posture documentation for this LawRuler MCP server."""
    return """\
# LawRuler MCP — Security Notes

## SSN handling

`ssn` exists as a parameter in the underlying `create_lead` client method but is
**intentionally excluded** from all MCP tool signatures (`create_lead`,
`create_lead_full`, `create_lead_obo`). SSN must be provided directly by the
client via a secure channel, not relayed through the agent layer.

Agents MUST:
- Never echo SSN back in any output, log, or Telegram message.
- Minimize PII generally — collect only what is required for the intake step.
- If a conversation contains SSN, treat it as read-once; do not store or repeat it.

## Reserved-parameter injection guard

LawRuler's API is a single POST endpoint. Parameters like `LeadID`,
`overridelead`, `Key`, `ReturnJSON`, `ReturnXML`, and `Operation` are system
parameters that control API behavior. An attacker injecting these via a
`custom_fields_json` payload could manipulate record routing or override existing
records unexpectedly.

**Mitigations in place (as of wt/secfix):**
- `set_custom_field` raises `ValueError` if `field_name` matches any reserved param (case-insensitive).
- `update_lead_fields` blocks reserved keys in the `custom_fields_json` dict before the API call.
- `create_lead_with_custom_fields` (client layer) does NOT enforce this blocklist — agents
  should prefer the MCP tools over calling the client directly.

**Reserved keys (case-insensitive):** `leadid`, `overridelead`, `key`, `returnjson`,
`returnxml`, `operation`.

## Authentication

`LAWRULER_API_KEY` and `LAWRULER_BASE_URL` are loaded via the pluggable credentials
store (OS keyring -> `.env`). The key is injected into POST body at call time only
and is never logged.
"""


# ── Prompts ───────────────────────────────────────────────────────────────────


@mcp.prompt()
def new_intake_workflow(
    contact_name: str, phone: str, email: str, case_type: str
) -> str:
    """Step-by-step intake creation workflow grounded in LawRuler tools."""
    return f"""You are a legal intake coordinator. Create a new lead/intake for:
  Name: {contact_name}
  Phone: {phone}
  Email: {email}
  Case type: {case_type}

Follow this sequence:
1. Call create_lead with the provided name, cell_phone, email, and case_type.
   - Set status to 'New Lead'.
   - SECURITY: Minimize PII. Do not include SSN — that must be collected via a secure channel, not this tool.
   - Do not echo sensitive fields back in your output.
2. Record the returned LeadID.
3. If a summary of the matter is available from trusted internal notes, call update_lead_summary with the LeadID.
4. Assign to the appropriate staff member with update_lead_assignee.
5. Verify the record with get_lead and confirm: name, phone, email, status, case type are all correct.
6. Report the LeadID and confirmed status. Flag any field that did not save correctly."""


@mcp.prompt()
def intake_status_progression(lead_id: int) -> str:
    """Guide a lead through the retainer-signing pipeline using LawRuler status tools."""
    return f"""Manage intake pipeline for LeadID {lead_id}.

1. Retrieve current state with get_lead({lead_id}).
2. Identify the current Status and the appropriate next step:
   - 'New Lead' -> send intake questionnaire -> update_lead_status({lead_id}, 'Emailed Intake Questionnaire')
   - 'Emailed Intake Questionnaire' -> if questionnaire received -> update_lead_status({lead_id}, 'Sent Retainer Contract')
   - 'Sent Retainer Contract' -> if signed -> update_lead_status({lead_id}, 'Signed Retainer Contract')
   - 'Signed Retainer Contract' -> update_lead_status({lead_id}, 'Converted to Case')
3. After each status update, confirm with get_lead that the status persisted.
4. Add a conversation note via add_conversation_note summarizing the action taken (no SSN, minimal PII).
5. Report: current status -> action taken -> new status."""


@mcp.prompt()
def lead_triage_report() -> str:
    """Identify leads needing immediate attention by reviewing a set of known LeadIDs."""
    return """Triage recent leads to identify priority follow-ups.

Note: LawRuler's API does not expose a bulk list endpoint; triage should be driven
by a known set of LeadIDs (e.g. from a CRM dashboard export or webhook batch).

For each LeadID in your current working set:
1. Call get_lead(lead_id) to retrieve current status and contact info.
2. Classify priority:
   - URGENT: Status is 'New Lead' and created more than 24 h ago (check timestamps if available).
   - HIGH: Status is 'Emailed Intake Questionnaire' with no response noted.
   - NORMAL: Status is progressing on schedule.
3. Output a triage table: LeadID | Name | Status | Priority | Recommended Action.
4. SECURITY: Omit SSN and DOB from any output. Show only name, status, and contact method."""


def main():
    mcp.run()


if __name__ == "__main__":
    main()
