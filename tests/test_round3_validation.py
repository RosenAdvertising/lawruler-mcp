"""Visible-content security regressions; every rejected write has zero POSTs."""

import asyncio
import json
import unicodedata
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequestParams

from lawruler_mcp import client as client_module, server
from lawruler_mcp.errors import ArgumentError
from lawruler_mcp.validation import meaningful_value


CREATE_TOOLS = ("create_lead", "create_lead_full", "create_lead_obo")
UPDATE_PATHS = ("contact", "standard", "multi-custom", "single-custom")
# Independent fixture of the requested DerivedCoreProperties property ranges.
DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)
REREVIEW_BYPASSES = ("\u0301", "\u034f", "\u20dd", "\ufe0f", "\u3164")
# Every code point is checked below; transport tests sample each range's ends
# as well as the exact reviewer corpus and combinations of blank/mark classes.
INVISIBLE = tuple(
    dict.fromkeys(
        (
            *REREVIEW_BYPASSES,
            *(
                chr(cp)
                for start, end in DEFAULT_IGNORABLE_RANGES
                for cp in (start, end)
            ),
            "\u2800",
            "\u3000",
            "\u2028",
            "\u2029",
            "\u0301\u20dd",
            "\u093e",
            "\u115f\u1160",
            "\u3164\uffa0",
            "\u2800\u0301",
            " \u0301",
            "\u034f\ufe0f\u20dd",
            "\u00a8",
            "\u037a",
            "\x01\x7f\x85",
            "\u200c",
            "\u200d",
            "\u2061",
            "\u2066",
            "\u2069",
            "\u2003\u00a0",
            "",
            " \t\n",
        )
    )
)
VALID_NAMES = (
    "Jose\u0301 Garci\u0301a",
    "José García",
    "สมชาย ใจดี",
    "خوسيه غارسيا",
    "王小明",
    "A\u20dd",
    "\u0301A",
    "A\ufe0f",
    "A\u034f\u0301",
    "\u3164A\u2800",
    "１２３",
)
CONTACT = {"cell_phone": "5550100", "email": "sentinel@example.invalid"}
API_CONTACT = {"CellPhone": "5550100", "Email1": "sentinel@example.invalid"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(client_module, "BASE_URL", "https://test.lawruler.com")
    monkeypatch.setattr(client_module, "API_KEY", "SENTINEL-API-KEY")
    client = client_module.LawRulerClient()
    client.session.post = Mock(
        return_value=Mock(status_code=200, headers={}, text='{"LeadID":7}')
    )
    client._post = Mock(wraps=client._post)
    monkeypatch.setattr(server, "_c", lambda: client)
    return client


def invoke(tool, args):
    return asyncio.run(
        server.mcp._handle_call_tool(
            None, CallToolRequestParams(name=tool, arguments=args)
        )
    )


def rejected(client, tool, args):
    result = invoke(tool, args)
    assert result.is_error
    assert "Invalid argument" in result.content[0].text
    client.session.post.assert_not_called()
    client._post.assert_not_called()


def update_call(path, value):
    if path == "contact":
        return "update_lead_contact_info", {"lead_id": 7, "email": value}, "Email1"
    if path == "standard":
        return "update_lead_fields", {"lead_id": 7, "status": value}, "Status"
    if path == "multi-custom":
        return (
            "update_lead_fields",
            {"lead_id": 7, "custom_fields_json": json.dumps({"custom1": value})},
            "custom1",
        )
    return (
        "set_custom_field",
        {"lead_id": 7, "field_name": "custom1", "value": value},
        "custom1",
    )


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize("blank", REREVIEW_BYPASSES)
def test_exact_rereview_blank_create_rejects(client, tool, blank):
    rejected(client, tool, dict.fromkeys(("full_name", "cell_phone", "email"), blank))


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize("blank", INVISIBLE)
@pytest.mark.parametrize(
    "field", ("full_name", "first_name", "last_name", "cell_phone", "email")
)
def test_each_required_create_field_rejects_invisible(client, tool, blank, field):
    args = dict(CONTACT, full_name="José García")
    if field in ("first_name", "last_name"):
        args.pop("full_name")
        args.update(first_name="José", last_name="García")
    args[field] = blank
    rejected(client, tool, args)


@pytest.mark.parametrize("path", UPDATE_PATHS)
@pytest.mark.parametrize("blank", INVISIBLE)
def test_each_update_class_rejects_invisible(client, path, blank):
    tool, args, _ = update_call(path, blank)
    rejected(client, tool, args)


@pytest.mark.parametrize("blank", INVISIBLE)
@pytest.mark.parametrize("source", ("custom-only", "standard-only", "merged"))
def test_direct_helper_rejects_empty_or_invisible_create(client, blank, source):
    custom = {"custom1": blank}
    standard = {}
    if source == "standard-only":
        standard = dict.fromkeys(("FullName", "CellPhone", "Email1"), blank)
        custom = {}
    elif source == "merged":
        standard = {"FullName": blank}
        custom.update(CellPhone=blank, Email1=blank)
    with pytest.raises(ArgumentError):
        client.create_lead_with_custom_fields(json.dumps(custom), **standard)
    client.session.post.assert_not_called()
    client._post.assert_not_called()


@pytest.mark.parametrize(
    "payload, standard",
    [
        ("{}", {}),
        ("", {}),
        ('{"custom1":"visible"}', {}),
        ("{}", {"FullName": "José García"}),
        ("{}", dict(API_CONTACT)),
        ("{}", {"FullName": "José García", "CellPhone": "5550100"}),
        ("{}", {"FullName": "José García", "Email1": "sentinel@example.invalid"}),
    ],
)
def test_direct_helper_requires_identity_and_both_contacts(client, payload, standard):
    with pytest.raises(ArgumentError):
        client.create_lead_with_custom_fields(payload, **standard)
    client.session.post.assert_not_called()
    client._post.assert_not_called()


@pytest.mark.parametrize("start, end", DEFAULT_IGNORABLE_RANGES)
def test_every_default_ignorable_code_point_is_content_free(start, end):
    for cp in range(start, end + 1):
        value = chr(cp)
        assert not meaningful_value(value), f"U+{cp:04X}"
        assert not meaningful_value(value + "\u0301"), f"U+{cp:04X} plus mark"
        assert meaningful_value("A" + value + "\u0301"), f"A plus U+{cp:04X}"


def test_every_space_separator_is_content_free():
    for cp in range(0x110000):
        value = chr(cp)
        if unicodedata.category(value) == "Zs":
            assert not meaningful_value(value + "\u0301"), f"U+{cp:04X}"


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize("name", VALID_NAMES)
@pytest.mark.parametrize("split", (False, True))
def test_legitimate_names_post_exactly_as_given(client, tool, name, split):
    identity = {"first_name": name, "last_name": name} if split else {"full_name": name}
    assert not invoke(tool, dict(CONTACT, **identity)).is_error
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    for field in ("FirstName", "LastName") if split else ("FullName",):
        assert data[field] == name


@pytest.mark.parametrize("path", UPDATE_PATHS)
@pytest.mark.parametrize(
    "value", (*VALID_NAMES, "!\u0301", "😀\ufe0f", "©", "0", "false")
)
def test_visible_update_values_post_unchanged(client, path, value):
    tool, args, field = update_call(path, value)
    assert not invoke(tool, args).is_error
    client.session.post.assert_called_once()
    assert client.session.post.call_args.kwargs["data"][field] == value


@pytest.mark.parametrize("name", VALID_NAMES)
@pytest.mark.parametrize("custom_value", (0, False))
@pytest.mark.parametrize("source", ("standard", "custom", "merged"))
def test_direct_helper_valid_payload_posts_unchanged(
    client, name, custom_value, source
):
    standard = dict(API_CONTACT, FullName=name)
    custom = {"custom1": custom_value}
    if source == "custom":
        custom.update(standard)
        standard = {}
    elif source == "merged":
        custom["FullName"] = standard.pop("FullName")
    assert client.create_lead_with_custom_fields(json.dumps(custom), **standard) == {
        "LeadID": 7
    }
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    assert data["FullName"] == name
    assert data["custom1"] is custom_value
    assert data["ReturnJSON"] == "True"
    assert data["Key"] == "SENTINEL-API-KEY"


@pytest.mark.parametrize("value", (0, False))
def test_numeric_and_boolean_custom_updates_remain_valid(client, value):
    tool, args, field = update_call("multi-custom", value)
    assert not invoke(tool, args).is_error
    client.session.post.assert_called_once()
    assert client.session.post.call_args.kwargs["data"][field] == str(value)


NAME_FIELDS = (
    *(
        (tool, field)
        for tool in CREATE_TOOLS
        for field in ("full_name", "first_name", "last_name")
    ),
    ("create_lead_full", "business_name"),
    ("create_lead_full", "campaign_name"),
)
NON_NAMES = ("!", "—…", "😀", "©\ufe0f", "!\u0301", "\u3164!\u20dd", "\u2800©")
API_NAME_FIELDS = ("FullName", "FirstName", "LastName", "BusinessName", "CampaignName")


@pytest.mark.parametrize("tool, field", NAME_FIELDS)
@pytest.mark.parametrize("value", NON_NAMES)
def test_every_create_name_field_needs_letter_or_number(client, tool, field, value):
    # A valid alternate identity must not allow a punctuation/symbol-only name
    # to be sent in another accepted name field.
    args = dict(CONTACT, full_name="José García", first_name="José", last_name="García")
    args[field] = value
    rejected(client, tool, args)


@pytest.mark.parametrize("field", API_NAME_FIELDS)
@pytest.mark.parametrize("value", NON_NAMES)
@pytest.mark.parametrize("source", ("standard", "custom"))
def test_direct_helper_checks_every_name_after_merge(client, field, value, source):
    standard = dict(
        API_CONTACT, FullName="José García", FirstName="José", LastName="García"
    )
    custom = {}
    if source == "standard":
        standard[field] = value
    else:
        custom[field] = value
    with pytest.raises(ArgumentError):
        client.create_lead_with_custom_fields(json.dumps(custom), **standard)
    client.session.post.assert_not_called()
    client._post.assert_not_called()


@pytest.mark.parametrize("tool, field", NAME_FIELDS)
@pytest.mark.parametrize("name", ("A\u20dd", "王小明", "１２３"))
def test_each_optional_name_preserves_visible_original(client, tool, field, name):
    args = dict(CONTACT, full_name="José García")
    args[field] = name
    assert not invoke(tool, args).is_error
    client.session.post.assert_called_once()
    api_field = "".join(word.capitalize() for word in field.split("_"))
    assert client.session.post.call_args.kwargs["data"][api_field] == name


@pytest.mark.parametrize(
    "field", ("FullName", "FirstName", "LastName", "CellPhone", "Email1")
)
@pytest.mark.parametrize("blank", INVISIBLE)
@pytest.mark.parametrize("source", ("standard", "custom", "merged"))
def test_direct_helper_each_required_field_is_visible(client, field, blank, source):
    fields = dict(API_CONTACT, FullName="José García")
    if field in ("FirstName", "LastName"):
        fields.pop("FullName")
        fields.update(FirstName="José", LastName="García")
    fields[field] = blank
    standard, custom = fields, {}
    if source == "custom":
        standard, custom = {}, fields
    elif source == "merged":
        custom[field] = standard.pop(field)
    with pytest.raises(ArgumentError):
        client.create_lead_with_custom_fields(json.dumps(custom), **standard)
    client.session.post.assert_not_called()
    client._post.assert_not_called()


@pytest.mark.parametrize("blank", REREVIEW_BYPASSES + ("\u2800", "\u115f\u1160"))
@pytest.mark.parametrize("path", ("create", "update", "helper"))
def test_blank_optional_values_are_omitted_beside_real_content(client, blank, path):
    if path == "create":
        assert not invoke(
            "create_lead",
            dict(CONTACT, full_name="Jose\u0301 Garci\u0301a", summary=blank),
        ).is_error
    elif path == "update":
        assert not invoke(
            "update_lead_fields",
            {
                "lead_id": 7,
                "summary": "A\u20dd",
                "status": blank,
                "custom_fields_json": json.dumps({"custom1": blank, "custom2": False}),
            },
        ).is_error
    else:
        client.create_lead_with_custom_fields(
            json.dumps({"custom1": blank, "custom2": 0}),
            **dict(API_CONTACT, FullName="Jose\u0301 Garci\u0301a", Summary=blank),
        )
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    assert "custom1" not in data
    if path == "update":
        assert "Status" not in data
        assert data["Summary"] == "A\u20dd"
        assert data["custom2"] == "False"
    else:
        assert "Summary" not in data
        assert data["FullName"] == "Jose\u0301 Garci\u0301a"
        if path == "helper":
            assert data["custom2"] == 0


@pytest.mark.parametrize(
    "tool, field",
    (
        ("update_lead_status", "status"),
        ("update_lead_assignee", "assignee"),
        ("update_lead_owner", "owner"),
        ("update_lead_case_type", "case_type"),
        ("update_lead_summary", "summary"),
        ("add_conversation_note", "conversation"),
        ("add_tags_to_lead", "tags"),
        ("update_lead_language", "language"),
    ),
)
@pytest.mark.parametrize("blank", REREVIEW_BYPASSES)
def test_single_standard_update_wrappers_reject_bypasses(client, tool, field, blank):
    rejected(client, tool, {"lead_id": 7, field: blank})


@pytest.mark.parametrize("blank", INVISIBLE)
@pytest.mark.parametrize("container", (list, dict))
def test_nested_custom_containers_need_visible_values(client, blank, container):
    value = [blank, None] if container is list else {"label": blank}
    rejected(
        client,
        "update_lead_fields",
        {
            "lead_id": 7,
            "custom_fields_json": json.dumps({"custom1": value}),
        },
    )


@pytest.mark.parametrize("source", ("standard", "custom"))
@pytest.mark.parametrize("value", ("\x00", "A\x00B", "\ud800", "A\udfffB"))
def test_direct_helper_cannot_hide_unsafe_text_beside_valid_fields(
    client, source, value
):
    standard = dict(API_CONTACT, FullName="José García")
    custom = {"custom1": "visible"}
    if source == "standard":
        standard["custom1"] = value
    else:
        custom["custom1"] = value
    with pytest.raises(ArgumentError):
        client.create_lead_with_custom_fields(json.dumps(custom), **standard)
    client.session.post.assert_not_called()
    client._post.assert_not_called()


@pytest.mark.parametrize("field", ("FullName", "FirstName", "LastName"))
@pytest.mark.parametrize("value", (0, False, True, ["visible"], {"label": "visible"}))
def test_direct_helper_names_are_text_not_containers_or_scalars(client, field, value):
    standard = dict(API_CONTACT, FullName="José García")
    if field in ("FirstName", "LastName"):
        standard.pop("FullName")
        standard.update(FirstName="José", LastName="García")
    standard[field] = value
    with pytest.raises(ArgumentError):
        client.create_lead_with_custom_fields("{}", **standard)
    client.session.post.assert_not_called()
    client._post.assert_not_called()


@pytest.mark.parametrize("source", ("standard", "custom", "merged"))
def test_direct_helper_accepts_split_identity_and_normalized_api_keys(client, source):
    standard = dict(API_CONTACT, FirstName="Jose\u0301", LastName="Garci\u0301a")
    custom = {"ｃｕｓｔｏｍ１": False}
    if source == "custom":
        custom.update(standard)
        standard = {}
    elif source == "merged":
        custom["ＦｉｒｓｔＮａｍｅ"] = standard.pop("FirstName")
        custom["Ｅｍａｉｌ１"] = standard.pop("Email1")
    client.create_lead_with_custom_fields(json.dumps(custom), **standard)
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    assert data["FirstName"] == "Jose\u0301"
    assert data["LastName"] == "Garci\u0301a"
    assert data["Email1"] == API_CONTACT["Email1"]
    assert data["custom1"] is False
