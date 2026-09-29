#!/usr/bin/env python3
"""LawRuler (Legal CRM) API client. Single-endpoint form-data POST API with API key auth."""

import json
import logging
import os
import time

import requests
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from lawruler_mcp import credentials
from lawruler_mcp.errors import (
    ArgumentError,
    AuthenticationError,
    MissingCredentialsError,
    NotFoundError,
    RateLimitError,
    VendorHTTPError,
)

# Resolve credentials through the pluggable store (OS keyring -> .env file).
credentials.load_into_environ(["LAWRULER_API_KEY", "LAWRULER_BASE_URL"])

API_KEY = os.environ.get("LAWRULER_API_KEY", "")
BASE_URL = os.environ.get("LAWRULER_BASE_URL", "").rstrip("/")
REQUEST_TIMEOUT = (3.05, 30)
logger = logging.getLogger(__name__)

_VENDOR_REASONS = {
    "invalid_request",
    "invalid_api_key",
    "unauthorized",
    "forbidden",
    "not_found",
    "duplicate_record",
    "validation_error",
    "rate_limited",
    "service_unavailable",
    "internal_error",
}


def _safe_vendor_reason(response) -> str:
    """Return only a known vendor code; never surface free-form response text."""
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return "request_rejected"
    if isinstance(payload, dict):
        for field in ("code", "error", "reason"):
            value = payload.get(field)
            if isinstance(value, str) and value.casefold() in _VENDOR_REASONS:
                return value.casefold()
    return "request_rejected"


def _retry_after_seconds(value) -> int:
    """Parse integer Retry-After values, defaulting and capping safely."""
    try:
        parsed = int(value)
    except (ValueError, TypeError, OverflowError):
        return 10
    return min(max(parsed, 0), 30)


def _endpoint():
    if not API_KEY or not BASE_URL:
        logger.error("client_configuration_rejected reason=missing_credentials")
        raise MissingCredentialsError()
    return f"{BASE_URL}/api-legalcrmapp.aspx"


def _xml_to_dict(xml_str: str) -> dict:
    """Parse LawRuler XML response into a dict."""
    try:
        root = ET.fromstring(
            xml_str,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
        result = {}
        for child in root:
            result[child.tag] = child.text
        return result
    except DefusedXmlException:
        logger.warning("xml_response_rejected reason=unsafe_markup")
        raise
    except ET.ParseError:
        return {"raw": xml_str}


class LawRulerClient:
    def __init__(self):
        self.endpoint = _endpoint()
        self.session = requests.Session()

    def _post(self, data: dict) -> dict:
        data = dict(data)
        data["Key"] = API_KEY
        retry_after = 10
        for attempt in range(3):
            resp = self.session.post(
                self.endpoint,
                data=data,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                if attempt < 2:
                    time.sleep(retry_after)
                continue
            if resp.status_code in (401, 403):
                raise AuthenticationError()
            if resp.status_code == 404:
                raise NotFoundError()
            if not resp.ok:
                raise VendorHTTPError(resp.status_code, _safe_vendor_reason(resp))
            # Try JSON first, fall back to text
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                try:
                    return resp.json()
                except ValueError:
                    raise VendorHTTPError(
                        resp.status_code, "invalid_response"
                    ) from None
            text = resp.text.strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    raise VendorHTTPError(
                        resp.status_code, "invalid_response"
                    ) from None
            if text.startswith("<"):
                return _xml_to_dict(text)
            return {"response": text}
        raise RateLimitError(retry_after)

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
        # SECURITY: ``ssn`` is intentionally excluded from the MCP server tool
        # (server.py ``create_lead_full``) to prevent SSN from transiting Claude's
        # context window, appearing in conversation logs, or being visible to
        # intermediate MCP layers.  This parameter exists only for direct
        # programmatic use of the client outside the MCP layer.  Do NOT expose
        # it via any MCP tool signature.
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
        return self._post(
            {
                "Operation": "GetStatus",
                "ReturnJSON": "True",
                "LeadID": str(lead_id),
            }
        )

    def update_lead_status(self, lead_id: int, status: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "Status": status,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def update_lead_assignee(self, lead_id: int, assignee: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "LeadAssignee": assignee,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def update_lead_owner(self, lead_id: int, owner: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "LeadOwner": owner,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def add_tags_to_lead(self, lead_id: int, tags: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "Tags": tags,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def update_lead_case_type(self, lead_id: int, case_type: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "CaseType": case_type,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def update_lead_summary(self, lead_id: int, summary: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "Summary": summary,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def add_conversation_note(self, lead_id: int, conversation: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "Conversation": conversation,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def update_lead_language(self, lead_id: int, language: str) -> dict:
        return self._post(
            {
                "LeadID": str(lead_id),
                "Language": language,
                "overridelead": "true",
                "ReturnJSON": "True",
            }
        )

    def set_custom_field(self, lead_id: int, field_name: str, value: str) -> dict:
        RESERVED = {
            "leadid",
            "overridelead",
            "key",
            "returnjson",
            "returnxml",
            "operation",
        }
        if field_name.casefold() in RESERVED:
            logger.warning("custom_field_rejected reason=reserved_parameter")
            raise ArgumentError(
                "field_name", "a non-reserved LawRuler custom field name"
            )
        return self._post(
            {
                "LeadID": str(lead_id),
                "overridelead": "true",
                "ReturnJSON": "True",
                field_name: value,
            }
        )

    # Parameters that must never be overridden by caller-supplied JSON.
    _RESERVED = frozenset(
        {"key", "operation", "leadid", "overridelead", "returnjson", "returnxml"}
    )

    def create_lead_with_custom_fields(
        self, custom_fields_json: str, **standard_fields
    ) -> dict:
        """Create a lead with both standard and custom fields.

        ``custom_fields_json`` is deserialized and merged into the POST body.  Keys
        matching reserved LawRuler parameters (``key``, ``operation``, ``leadid``,
        ``overridelead``, ``returnjson``, ``returnxml``) are rejected to prevent a
        caller from injecting an ``Operation=DeleteAll`` or similar payload.
        """
        try:
            custom = json.loads(custom_fields_json) if custom_fields_json else {}
        except json.JSONDecodeError:
            logger.warning("custom_fields_rejected reason=invalid_json")
            raise ArgumentError("custom_fields_json", "a JSON object") from None
        if not isinstance(custom, dict):
            logger.warning("custom_fields_rejected reason=not_object")
            raise ArgumentError("custom_fields_json", "a JSON object")
        bad = self._RESERVED & {str(k).casefold() for k in custom.keys()}
        if bad:
            logger.warning("custom_fields_rejected reason=reserved_parameter")
            raise ArgumentError("custom_fields_json", "an object without reserved keys")
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
