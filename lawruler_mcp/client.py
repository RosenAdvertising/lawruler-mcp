#!/usr/bin/env python3
"""LawRuler (Legal CRM) API client. Single-endpoint form-data POST API with API key auth."""

import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import requests
from pathlib import Path

CONFIG_DIR = Path.home() / ".lawruler-mcp"


def _load_env():
    env_file = CONFIG_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env()

API_KEY = os.environ.get("LAWRULER_API_KEY", "")
BASE_URL = os.environ.get("LAWRULER_BASE_URL", "").rstrip("/")


def _endpoint():
    if not API_KEY or not BASE_URL:
        raise RuntimeError("LAWRULER_API_KEY and LAWRULER_BASE_URL must be set. Run lawruler-mcp-setup.")
    return f"{BASE_URL}/api-legalcrmapp.aspx"


def _xml_to_dict(xml_str: str) -> dict:
    """Parse LawRuler XML response into a dict."""
    try:
        root = ET.fromstring(xml_str)
        result = {}
        for child in root:
            result[child.tag] = child.text
        return result
    except ET.ParseError:
        return {"raw": xml_str}


class LawRulerClient:
    def __init__(self):
        self.endpoint = _endpoint()
        self.session = requests.Session()

    def _post(self, data: dict) -> dict:
        data["Key"] = API_KEY
        for attempt in range(3):
            resp = self.session.post(self.endpoint, data=data)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                print(f"Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue
            if not resp.ok:
                raise RuntimeError(f"LawRuler API error {resp.status_code}: {resp.text[:400]}")
            # Try JSON first, fall back to text
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                return resp.json()
            text = resp.text.strip()
            if text.startswith("{") or text.startswith("["):
                return json.loads(text)
            if text.startswith("<"):
                return _xml_to_dict(text)
            return {"response": text}
        raise RuntimeError("Max retries exceeded")

    def _get(self, params: dict) -> dict:
        # LawRuler API is POST-only; Key must be in POST body, not query string.
        return self._post(params)

    # ── Leads / Intakes ────────────────────────────────────────────────────────

    def create_lead(
        self,
        first_name: str = "",
        last_name: str = "",
        full_name: str = "",
        cell_phone: str = "",
        email: str = "",
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
        email2: str = "",
        dob: str = "",
        ssn: str = "",
        lead_assignee: str = "",
        lead_owner: str = "",
        hear: str = "",
        tags: str = "",
        contact_preference: str = "",
        when_to_contact: str = "",
        case_role: str = "",
        contact_type: str = "",
        campaign_name: str = "",
        conversation: str = "",
        language: str = "",
        return_json: bool = True,
        disable_dup_check: bool = False,
    ) -> dict:
        data = {"ReturnJSON": "True" if return_json else "False"}
        if first_name:
            data["FirstName"] = first_name
        if last_name:
            data["LastName"] = last_name
        if full_name:
            data["FullName"] = full_name
        if cell_phone:
            data["CellPhone"] = cell_phone
        if email:
            data["Email1"] = email
        if case_type:
            data["CaseType"] = case_type
        if lead_provider:
            data["LeadProvider"] = lead_provider
        if status:
            data["Status"] = status
        if summary:
            data["Summary"] = summary
        if address1:
            data["Address1"] = address1
        if address2:
            data["Address2"] = address2
        if city:
            data["City"] = city
        if state:
            data["State"] = state
        if zip_code:
            data["Zip"] = zip_code
        if county:
            data["County"] = county
        if home_phone:
            data["HomePhone"] = home_phone
        if business_phone:
            data["BusinessPhone"] = business_phone
        if business_name:
            data["BusinessName"] = business_name
        if email2:
            data["Email2"] = email2
        if dob:
            data["DOB"] = dob
        if ssn:
            data["SSN"] = ssn
        if lead_assignee:
            data["LeadAssignee"] = lead_assignee
        if lead_owner:
            data["LeadOwner"] = lead_owner
        if hear:
            data["Hear"] = hear
        if tags:
            data["Tags"] = tags
        if contact_preference:
            data["ContactPreference"] = contact_preference
        if when_to_contact:
            data["WhenToContact"] = when_to_contact
        if case_role:
            data["CaseRole"] = case_role
        if contact_type:
            data["ContactType"] = contact_type
        if campaign_name:
            data["CampaignName"] = campaign_name
        if conversation:
            data["Conversation"] = conversation
        if language:
            data["Language"] = language
        if disable_dup_check:
            data["dupcheck"] = "0"
        return self._post(data)

    def update_lead(self, lead_id: int, override: bool = True, **fields) -> dict:
        data = {
            "LeadID": str(lead_id),
            "ReturnJSON": "True",
        }
        if override:
            data["overridelead"] = "true"
        for k, v in fields.items():
            if v is not None and v != "":
                data[k] = str(v)
        return self._post(data)

    def get_lead(self, lead_id: int) -> dict:
        return self._post({
            "Operation": "GetStatus",
            "ReturnJSON": "True",
            "LeadID": str(lead_id),
        })

    def update_lead_status(self, lead_id: int, status: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "Status": status,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def update_lead_assignee(self, lead_id: int, assignee: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "LeadAssignee": assignee,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def update_lead_owner(self, lead_id: int, owner: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "LeadOwner": owner,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def add_tags_to_lead(self, lead_id: int, tags: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "Tags": tags,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def update_lead_case_type(self, lead_id: int, case_type: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "CaseType": case_type,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def update_lead_summary(self, lead_id: int, summary: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "Summary": summary,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def add_conversation_note(self, lead_id: int, conversation: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "Conversation": conversation,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def update_lead_language(self, lead_id: int, language: str) -> dict:
        return self._post({
            "LeadID": str(lead_id),
            "Language": language,
            "overridelead": "true",
            "ReturnJSON": "True",
        })

    def set_custom_field(self, lead_id: int, field_name: str, value: str) -> dict:
        RESERVED = {"LeadID", "overridelead", "Key", "ReturnJSON", "Operation"}
        if field_name in RESERVED:
            raise ValueError(f"'{field_name}' is a reserved parameter name")
        return self._post({
            "LeadID": str(lead_id),
            "overridelead": "true",
            "ReturnJSON": "True",
            field_name: value,
        })

    def create_lead_with_custom_fields(self, custom_fields_json: str, **standard_fields) -> dict:
        """Create a lead with both standard and custom fields."""
        custom = json.loads(custom_fields_json) if custom_fields_json else {}
        data = {**standard_fields, **custom, "ReturnJSON": "True"}
        return self._post(data)

    def update_lead_contact_info(
        self,
        lead_id: int,
        cell_phone: str = "",
        home_phone: str = "",
        email: str = "",
        address1: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
    ) -> dict:
        data = {"LeadID": str(lead_id), "overridelead": "true", "ReturnJSON": "True"}
        if cell_phone:
            data["CellPhone"] = cell_phone
        if home_phone:
            data["HomePhone"] = home_phone
        if email:
            data["Email1"] = email
        if address1:
            data["Address1"] = address1
        if city:
            data["City"] = city
        if state:
            data["State"] = state
        if zip_code:
            data["Zip"] = zip_code
        return self._post(data)
