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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
