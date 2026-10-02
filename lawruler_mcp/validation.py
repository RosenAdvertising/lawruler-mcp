"""Shared validation at LawRuler request boundaries."""

import logging
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from lawruler_mcp.errors import ArgumentError

RESERVED_FIELDS = frozenset(
    {"key", "operation", "leadid", "overridelead", "returnjson", "returnxml"}
)
# Unicode DerivedCoreProperties.txt: Default_Ignorable_Code_Point.
# Keep the explicit ranges as a floor, including reserved code points. The
# runtime-derived table below also covers new members of known Unicode classes.
_DEFAULT_IGNORABLE = re.compile(
    r"[\u00ad\u034f\u061c\u115f-\u1160\u17b4-\u17b5"
    r"\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f"
    r"\u3164\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufff8"
    r"\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]"
)
# Unicode PropList.txt: White_Space. isspace() additionally tracks the runtime
# database (and includes some Cc characters, which are already content-free).
_WHITE_SPACE = re.compile(
    r"[\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a"
    r"\u2028-\u2029\u202f\u205f\u3000]"
)
# These are semantic name classes, not arbitrary substrings: TAGALOG letters,
# MONOSPACE letters and cuneiform TAG signs are real content. Apply these only
# outside P*/S*: a punctuation/symbol name describes its meaning, not its ink
# (for example SYMBOL FOR SPACE and ARABIC DECIMAL SEPARATOR are visible).
_BLANK_NAME = re.compile(
    r"\b(?:BLANK|FILLER|SPACE|INVISIBLE|ZERO WIDTH|SEPARATOR|"
    r"VARIATION SELECTOR|JOINER|NULL)\b|^(?:TAG |LANGUAGE TAG$|CANCEL TAG$)"
)
# Reviewed rendering exceptions, independent of category/name heuristics.
# Braille blank has no dots; the null notehead contributes no notehead glyph.
# Egyptian full/half blanks are layout placeholders despite their Lo category.
# Keep these and the property ranges above as a floor on every Unicode runtime.
_RENDERING_BLANKS = frozenset({0x2800, 0x13441, 0x13442, 0x1D159})
_NAME_FIELDS = frozenset(
    {"fullname", "firstname", "lastname", "businessname", "campaignname"}
)
logger = logging.getLogger(__name__)


def _derive_blank_code_points() -> bytes:
    """Derive content-free classes once from this runtime's Unicode database.

    A byte per point avoids a large Python set of nearly a million Cn/Co points.
    Marks never supply a base; Co/Cn never count even if a local font draws them.
    Explicit property ranges and reviewed rendering blanks remain a floor.
    """
    blank = bytearray(0x110000)
    for cp in range(len(blank)):
        char = chr(cp)
        category = unicodedata.category(char)
        if (
            category[0] in "CMZ"
            or char.isspace()
            or _WHITE_SPACE.fullmatch(char)
            or _DEFAULT_IGNORABLE.fullmatch(char)
            or cp in _RENDERING_BLANKS
            or (
                category[0] not in "PS"
                and _BLANK_NAME.search(unicodedata.name(char, ""))
            )
        ):
            blank[cp] = 1
    return bytes(blank)


_BLANK_CODE_POINTS = _derive_blank_code_points()


def _meaningful_text(value: str) -> str:
    """Return only eligible bases, for validation; never rewrite the payload.

    Check source points before normalization, so a blank/mark cannot normalize
    into apparent content. Then check each normalized point as well: a spacing
    accent can normalize into just whitespace and marks. Ignoring marks in this
    scratch representation preserves NFD and multilingual text in the actual
    request. Scan all input so NUL/surrogates are hard errors even beside content.
    """
    visible = []
    for char in value:
        cp = ord(char)
        if cp == 0 or 0xD800 <= cp <= 0xDFFF:
            raise ArgumentError("fields", "text without NUL or surrogate characters")
        if _BLANK_CODE_POINTS[cp]:
            continue
        for normalized in unicodedata.normalize("NFKC", char):
            if not _BLANK_CODE_POINTS[ord(normalized)]:
                visible.append(normalized)
    return "".join(visible)


def meaningful_name(value) -> bool:
    """Names require a visible letter or number, not just punctuation/symbols."""
    return isinstance(value, str) and any(
        unicodedata.category(char)[0] in "LN" for char in _meaningful_text(value)
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


def validate_write_value(field: str, value) -> bool:
    """Shared content boundary for every create/update field before POST.

    Return False for absent/content-free values. Validate name fields before
    aliases or custom/standard dictionaries can merge and hide invalid inputs.
    """
    present = meaningful_value(value)
    normalized_field = unicodedata.normalize("NFKC", field)
    if present and normalized_field.casefold() in _NAME_FIELDS:
        if not meaningful_name(value):
            raise ArgumentError(
                normalized_field, "a name containing at least one letter or number"
            )
    return present


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
