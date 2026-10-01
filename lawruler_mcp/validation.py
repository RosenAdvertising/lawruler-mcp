"""Shared validation at LawRuler request boundaries."""

import logging
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from lawruler_mcp.errors import ArgumentError

RESERVED_FIELDS = frozenset(
    {"key", "operation", "leadid", "overridelead", "returnjson", "returnxml"}
)
_IGNORED_CATEGORIES = frozenset({"Cc", "Cf", "Zs", "Zl", "Zp"})
logger = logging.getLogger(__name__)


def _meaningful_text(value: str) -> str:
    """Normalize for validation only; never silently repair NUL or surrogates."""
    if "\x00" in value or any(unicodedata.category(c) == "Cs" for c in value):
        raise ArgumentError("fields", "text without NUL or surrogate characters")
    return "".join(
        c
        for c in unicodedata.normalize("NFKC", value)
        if not c.isspace() and unicodedata.category(c) not in _IGNORED_CATEGORIES
    )


def meaningful_value(value) -> bool:
    """Ignore empty/invisible values, preserve zero/false, reject NUL anywhere."""
    if isinstance(value, str):
        return bool(_meaningful_text(value))
    if isinstance(value, dict):
        # Visit every entry, even after meaningful content is found.
        present = []
        for key, item in value.items():
            meaningful_value(key)
            present.append(meaningful_value(item))
        return any(present)
    if isinstance(value, (list, tuple)):
        return any([meaningful_value(item) for item in value])
    return value is not None


def validate_field_name(value: str, argument: str = "field_name") -> str:
    """Return an NFKC API name: [A-Za-z_][A-Za-z0-9_]*, never reserved.

    Whitespace, controls and format characters are rejected, not repaired.
    """
    expected = "a non-reserved field name matching [A-Za-z_][A-Za-z0-9_]*"
    if not isinstance(value, str):
        raise ArgumentError(argument, expected)
    meaningful = _meaningful_text(value)
    normalized = unicodedata.normalize("NFKC", value)
    if meaningful.casefold() in RESERVED_FIELDS:
        prefix = "custom_fields" if argument == "custom_fields_json" else "custom_field"
        logger.warning("%s_rejected reason=reserved_parameter", prefix)
        raise ArgumentError(argument, "a non-reserved LawRuler custom field name")
    if normalized != meaningful or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*", normalized
    ):
        raise ArgumentError(argument, expected)
    return normalized


def validate_portal_url(value: str) -> str:
    """Accept only HTTPS origins on LawRuler's documented domain."""
    expected = (
        "an HTTPS portal URL on lawruler.com or its subdomains, without "
        "userinfo, query, fragment, or a path; run lawruler-mcp-setup"
    )
    try:
        # Reject parser-normalized whitespace, escapes and Unicode lookalikes.
        if (
            not value
            or not value.isascii()
            or any(
                char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value
            )
            or any(char in value for char in "\\%?#")
        ):
            raise ValueError
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().removesuffix(".")
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/")
            or len(host) > 253
            or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in host.split(".")
            )
            or not (host == "lawruler.com" or host.endswith(".lawruler.com"))
        ):
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ArgumentError("LAWRULER_BASE_URL", expected) from None
    # The fixed domain suffix also excludes every literal/alternate IP notation.
    return urlunsplit(("https", host, "", "", ""))
