"""Reviewer bypass probes must fail before any credential-bearing POST."""

import asyncio
import json
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequestParams

from lawruler_mcp import client as client_module, server
from lawruler_mcp.errors import ArgumentError
from lawruler_mcp.validation import meaningful_value, validate_field_name


INVISIBLE = [
    "",
    " \t\r\n",
    "\x00",
    "\x01\x7f\x85",
    "\u200b",
    "\ufeff",
    "\u2003\u00a0",
    "\u2028\u2029",
    "\u200e\u2060",
    "\ud800",
    " \u200b\ufeff\x1f\u2029 ",
]
BAD_NAMES = [
    "",
    " ",
    "\x00",
    "\u200b",
    "\ufeff",
    "\ud800",
    "\r\ncustom1",
    " custom1 ",
    "\tcustom1\n",
    "custom\x001",
    "custom\u200b1",
    "custom\ufeff1",
    "custom 1",
    "custom-1",
    "custom.1",
    "custom[1]",
    "custom=1",
    "custom&1",
    "custom/1",
    "custom:1",
    "José",
    "1custom",
    "\u00a0custom1\u00a0",
    "\u2028custom1",
    "custom1\u2029",
]
RESERVED_NAMES = [
    "Key",
    "Operation",
    "LeadID",
    "overridelead",
    "ReturnJSON",
    "ReturnXML",
    " Operation ",
    "\tOperation\n",
    "oPeRaTiOn",
    "Ｏｐｅｒａｔｉｏｎ",
    "ＫＥＹ",
    "LeaｄID",
    "ReturnＪＳＯＮ",
    "\u200bOperation\ufeff",
]
CREATE_TOOLS = ["create_lead", "create_lead_full", "create_lead_obo"]
SINGLE_UPDATES = [
    ("update_lead_status", "status"),
    ("update_lead_assignee", "assignee"),
    ("update_lead_owner", "owner"),
    ("update_lead_case_type", "case_type"),
    ("update_lead_summary", "summary"),
    ("add_conversation_note", "conversation"),
    ("add_tags_to_lead", "tags"),
    ("update_lead_language", "language"),
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(client_module, "BASE_URL", "https://test.lawruler.com")
    monkeypatch.setattr(client_module, "API_KEY", "SENTINEL-API-KEY")
    client = client_module.LawRulerClient()
    client.session.post = Mock(
        return_value=Mock(status_code=200, headers={}, text='{"LeadID":7}')
    )
    monkeypatch.setattr(server, "_c", lambda: client)
    return client


def invoke(name, args):
    return asyncio.run(
        server.mcp._handle_call_tool(
            None, CallToolRequestParams(name=name, arguments=args)
        )
    )


def rejected(client, name, args):
    result = invoke(name, args)
    assert result.is_error
    assert "Invalid argument" in result.content[0].text
    client.session.post.assert_not_called()


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize("blank", INVISIBLE)
@pytest.mark.parametrize(
    "field", ["full_name", "first_name", "last_name", "cell_phone", "email"]
)
def test_each_required_create_field_is_meaningful(client, tool, blank, field):
    args = {
        "full_name": "José García",
        "cell_phone": "5550100",
        "email": "example@example.invalid",
    }
    if field in ("first_name", "last_name"):
        args.pop("full_name")
        args.update(first_name="José", last_name="García")
    args[field] = blank
    rejected(client, tool, args)


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize("blank", ["\x00", "\u200b", "\ufeff"])
def test_exact_reviewer_blank_lead_probe(client, tool, blank):
    rejected(client, tool, dict.fromkeys(("full_name", "cell_phone", "email"), blank))


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize("field", ["full_name", "cell_phone", "email", "summary"])
def test_nul_inside_meaningful_create_text_is_rejected(client, tool, field):
    args = {
        "full_name": "José García",
        "cell_phone": "5550100",
        "email": "example@example.invalid",
    }
    args[field] = "visible\x00value"
    rejected(client, tool, args)


@pytest.mark.parametrize("tool", CREATE_TOOLS)
@pytest.mark.parametrize(
    "identity",
    [{"full_name": "José García"}, {"first_name": "José", "last_name": "García"}],
)
def test_legitimate_non_ascii_leads_post_unchanged(client, tool, identity):
    args = dict(identity, cell_phone="5550100", email="example@example.invalid")
    assert not invoke(tool, args).is_error
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    if "full_name" in identity:
        assert data["FullName"] == "José García"
    else:
        assert (data["FirstName"], data["LastName"]) == ("José", "García")


@pytest.mark.parametrize("name", BAD_NAMES + RESERVED_NAMES)
@pytest.mark.parametrize("path", ["multi", "single", "direct", "custom_create"])
def test_malformed_or_reserved_field_names_never_post(client, name, path):
    if path == "multi":
        rejected(
            client,
            "update_lead_fields",
            {"lead_id": 7, "custom_fields_json": json.dumps({name: "x"})},
        )
    elif path == "single":
        rejected(
            client, "set_custom_field", {"lead_id": 7, "field_name": name, "value": "x"}
        )
    else:
        with pytest.raises(ArgumentError):
            if path == "direct":
                client.update_lead(7, **{name: "x"})
            else:
                client.create_lead_with_custom_fields(json.dumps({name: "x"}))
        client.session.post.assert_not_called()


@pytest.mark.parametrize("name", BAD_NAMES + RESERVED_NAMES)
@pytest.mark.parametrize("value", [None, ""])
def test_names_validated_even_when_value_would_be_compacted(client, name, value):
    rejected(
        client,
        "update_lead_fields",
        {
            "lead_id": 7,
            "status": "New Lead",
            "custom_fields_json": json.dumps({name: value}),
        },
    )


@pytest.mark.parametrize("blank", INVISIBLE + ["visible\x00value"])
@pytest.mark.parametrize("path", ["contact", "standard", "custom", "single"])
def test_content_free_updates_and_nul_never_post(client, blank, path):
    if path == "contact":
        rejected(client, "update_lead_contact_info", {"lead_id": 7, "email": blank})
    elif path == "standard":
        rejected(client, "update_lead_fields", {"lead_id": 7, "status": blank})
    elif path == "custom":
        rejected(
            client,
            "update_lead_fields",
            {"lead_id": 7, "custom_fields_json": json.dumps({"custom1": blank})},
        )
    else:
        rejected(
            client,
            "set_custom_field",
            {"lead_id": 7, "field_name": "custom1", "value": blank},
        )


@pytest.mark.parametrize("tool, field", SINGLE_UPDATES)
@pytest.mark.parametrize("blank", INVISIBLE + ["visible\x00value"])
def test_required_single_update_values_are_meaningful(client, tool, field, blank):
    rejected(client, tool, {"lead_id": 7, field: blank})


@pytest.mark.parametrize("tool, field", SINGLE_UPDATES)
def test_legitimate_single_updates_still_post(client, tool, field):
    assert not invoke(tool, {"lead_id": 7, field: "José García"}).is_error
    client.session.post.assert_called_once()
    assert "José García" in client.session.post.call_args.kwargs["data"].values()


@pytest.mark.parametrize("value", [0, False, "José García", "Ｊｏｓé García"])
def test_legitimate_custom_updates_and_normalized_names_post(client, value):
    assert not invoke(
        "update_lead_fields",
        {
            "lead_id": 7,
            "custom_fields_json": json.dumps({"ｃｕｓｔｏｍ2413": value}),
        },
    ).is_error
    client.session.post.assert_called_once()
    data = client.session.post.call_args.kwargs["data"]
    assert data["custom2413"] == str(value)
    assert "ｃｕｓｔｏｍ2413" not in data


@pytest.mark.parametrize(
    "name", ["custom2413", "custom_1", "_custom1", "ｃｕｓｔｏｍ2413"]
)
def test_legitimate_single_custom_update_posts_normalized_name(client, name):
    assert not invoke(
        "set_custom_field", {"lead_id": 7, "field_name": name, "value": "José García"}
    ).is_error
    client.session.post.assert_called_once()
    assert (
        client.session.post.call_args.kwargs["data"][validate_field_name(name)]
        == "José García"
    )


def test_blank_optional_fields_do_not_block_real_update(client):
    assert not invoke(
        "update_lead_fields",
        {
            "lead_id": 7,
            "summary": "José García",
            "status": "\u200b",
            "custom_fields_json": json.dumps({"custom1": "\ufeff", "custom2": False}),
        },
    ).is_error
    data = client.session.post.call_args.kwargs["data"]
    assert data["Summary"] == "José García"
    assert data["custom2"] == "False"
    assert "Status" not in data and "custom1" not in data


@pytest.mark.parametrize("value", [["x", "\x00"], {"x": "\x00"}, {"\x00": "x"}])
def test_nested_custom_values_cannot_hide_nul(client, value):
    rejected(
        client,
        "update_lead_fields",
        {"lead_id": 7, "custom_fields_json": json.dumps({"custom1": value})},
    )


def test_shared_meaningful_normalization():
    # NFKC leaves SPACE + an unattached mark; neither provides a visible base.
    assert not meaningful_value("\u00a8")
    assert meaningful_value("A\u0308")
    assert not meaningful_value("\u200b\u2029\x1f")
    assert meaningful_value(0) and meaningful_value(False)
    assert meaningful_value("José García")
    assert not meaningful_value(["\u200b", None])


@pytest.mark.parametrize(
    "fields",
    [
        {"ｃｕｓｔｏｍ1": "\x00", "custom1": "visible"},
        {"custom1": "\x00", "ｃｕｓｔｏｍ1": "visible"},
    ],
)
def test_normalized_alias_cannot_hide_nul(client, fields):
    rejected(
        client,
        "update_lead_fields",
        {
            "lead_id": 7,
            "custom_fields_json": json.dumps(fields),
        },
    )
