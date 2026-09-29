#!/usr/bin/env python3
"""LawRuler (Legal CRM) API client. Single-endpoint form-data POST API with API key auth."""

import json
import logging
import math
import os
import time
from email.utils import parsedate_to_datetime

import requests
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from lawruler_mcp import credentials
from lawruler_mcp.errors import (
    ArgumentError,
    AuthenticationError,
    MissingCredentialsError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TransportError,
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


def _is_failure_envelope(payload) -> bool:
    """Recognize explicit JSON failure shapes without exposing their prose."""
    if isinstance(payload, list):
        return any(_is_failure_envelope(item) for item in payload)
    if not isinstance(payload, dict):
        return True
    if not payload:
        return True
    normalized = {str(key).casefold(): value for key, value in payload.items()}
    if normalized.get("success") is False or normalized.get("ok") is False:
        return True
    if any(
        isinstance(normalized.get(key), str) and normalized[key].casefold() == "false"
        for key in ("success", "ok")
    ):
        return True
    status = normalized.get("status")
    if isinstance(status, str) and status.casefold() in {"error", "failed", "failure"}:
        return True
    if isinstance(status, int) and status >= 400:
        return True
    for field in ("error", "errors"):
        value = normalized.get(field)
        if (
            value is not None
            and value is not False
            and value != ""
            and value != []
            and value != {}
        ):
            return True
    return any(
        _is_failure_envelope(normalized[key])
        for key in ("response", "result")
        if isinstance(normalized.get(key), (dict, list))
    )


def _retry_after_seconds(value) -> int:
    """Parse Retry-After without shortening a vendor-requested delay."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            return 10
    if not math.isfinite(seconds):
        return 10
    return max(0, math.ceil(seconds))


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
        if root.tag.rsplit("}", 1)[-1].casefold() in {"error", "errors"}:
            return {"error": "request_rejected"}

        def children(element):
            return {
                child.tag.rsplit("}", 1)[-1]: children(child)
                if len(child)
                else child.text
                for child in element
            }

        payload = children(root)
        if not payload:
            raise VendorHTTPError(200, "invalid_response")
        return payload
    except DefusedXmlException:
        logger.warning("xml_response_rejected reason=unsafe_markup")
        raise
    except ET.ParseError:
        raise VendorHTTPError(200, "invalid_response") from None


class LawRulerClient:
    def __init__(self):
        self.endpoint = _endpoint()
        self.session = requests.Session()

    def _post(self, data: dict) -> dict:
        data = dict(data)
        data["Key"] = API_KEY
        retry_after = 10
        waited = 0
        for attempt in range(3):
            try:
                resp = self.session.post(
                    self.endpoint,
                    data=data,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.Timeout:
                raise TransportError(timed_out=True) from None
            except requests.ConnectionError:
                raise TransportError(timed_out=False) from None
            if resp.status_code == 429:
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                if attempt < 2:
                    remaining = 60 - waited
                    if retry_after > remaining:
                        raise RateLimitError(retry_after)
                    time.sleep(retry_after)
                    waited += retry_after
                continue
            if resp.status_code == 401:
                raise AuthenticationError()
            if resp.status_code == 403:
                raise PermissionDeniedError()
            if resp.status_code == 404:
                raise NotFoundError()
            if not 200 <= resp.status_code < 300:
                raise VendorHTTPError(resp.status_code, _safe_vendor_reason(resp))
            # A 200 response can still carry a vendor failure envelope.
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                try:
                    payload = resp.json()
                except ValueError:
                    raise VendorHTTPError(
                        resp.status_code, "invalid_response"
                    ) from None
                if _is_failure_envelope(payload):
                    raise VendorHTTPError(200, _safe_vendor_reason(resp))
                return payload
            text = resp.text.strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    payload = json.loads(text)
                    if _is_failure_envelope(payload):
                        raise VendorHTTPError(200, _safe_vendor_reason(resp))
                    return payload
                except json.JSONDecodeError:
                    raise VendorHTTPError(
                        resp.status_code, "invalid_response"
                    ) from None
            if text.startswith("<"):
                payload = _xml_to_dict(text)
                if _is_failure_envelope(payload):
                    raise VendorHTTPError(200, _safe_vendor_reason(resp))
                return payload
            raise VendorHTTPError(200, "request_rejected")
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
