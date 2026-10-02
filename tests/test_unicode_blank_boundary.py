"""Regression gates for the exhaustive sweep and the shared write boundary."""

import asyncio
import json
import unicodedata
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequestParams

from lawruler_mcp import client as client_module, server
from lawruler_mcp.errors import ArgumentError
from lawruler_mcp.validation import meaningful_name, meaningful_value
from unicode_blank_sweep import (
    API_CONTACT,
    API_NAMES,
    CONTACT,
    LEGITIMATE,
    MARKS,
    classify,
    forms,
    routes_for,
)


@pytest.fixture
def boundary(monkeypatch):
    client = object.__new__(client_module.LawRulerClient)
    client._post = Mock(return_value={"LeadID": 7})
    monkeypatch.setattr(server, "_c", lambda: client)
    return client


def test_entire_runtime_unicode_database_has_no_content_free_acceptance():
    for cp in range(0x110000):
        value = chr(cp)
        if classify(value) == "visible":
            continue
        for candidate in forms(value):
            try:
                present = meaningful_value(candidate)
                named = meaningful_name(candidate)
            except ArgumentError:
                assert cp == 0 or unicodedata.category(value) == "Cs"
            else:
                assert not present and not named, f"U+{cp:06X}: {ascii(candidate)}"


@pytest.mark.parametrize(
    "blank",
    ("\U00013441", "\U00013442", "\u2800", "\u3164", "\uffa0", "\U0001d159"),
)
@pytest.mark.parametrize("form_index", range(9))
def test_new_blank_and_filler_classes_on_every_route(boundary, blank, form_index):
    value = forms(blank)[form_index]
    for name, kind, call in routes_for(boundary, server):
        boundary._post.reset_mock()
        if kind == "optional":
            call(value)
            boundary._post.assert_called_once()
            assert value not in boundary._post.call_args.args[0].values(), name
        else:
            with pytest.raises(ArgumentError):
                call(value)
            boundary._post.assert_not_called()


@pytest.mark.parametrize(
    "value", LEGITIMATE + ("\u1700", "\u1760", "\U0001d670", "\U000122f3")
)
def test_legitimate_names_and_name_substring_collisions_are_preserved(boundary, value):
    # TAGALOG, TAGBANWA, MONOSPACE, cuneiform TAG are real letters.
    assert meaningful_name(value)
    for name, _, call in routes_for(boundary, server):
        boundary._post.reset_mock()
        call(value)
        boundary._post.assert_called_once()
        assert value in boundary._post.call_args.args[0].values(), name


@pytest.mark.parametrize("field", API_NAMES)
@pytest.mark.parametrize("value", ("!", "©", "😀", "!" + "".join(MARKS), 0, False))
@pytest.mark.parametrize("path", ("client", "custom-json", "single-custom"))
def test_all_update_name_fields_require_a_real_letter_or_number(
    boundary, field, value, path
):
    # The same API name rules apply through standard/custom fields and aliases.
    for spelling in (
        field,
        field.lower(),
        "".join(chr(ord(c) + 0xFEE0) for c in field),
    ):
        with pytest.raises(ArgumentError):
            if path == "client":
                boundary.update_lead(7, **{spelling: value})
            elif path == "custom-json":
                server.update_lead_fields(
                    7, custom_fields_json=json.dumps({spelling: value})
                )
            else:
                boundary.set_custom_field(7, spelling, value)
        boundary._post.assert_not_called()


@pytest.mark.parametrize(
    "field", ("full_name", "first_name", "last_name", "business_name", "campaign_name")
)
def test_create_name_fields_use_same_boundary(boundary, field):
    args = dict(CONTACT, full_name=LEGITIMATE[0], first_name="Valid", last_name="Name")
    args[field] = "©"
    with pytest.raises(ArgumentError):
        server.create_lead_full(**args)
    boundary._post.assert_not_called()


@pytest.mark.parametrize("value", (0, False, "0", "false"))
def test_custom_zero_and_false_are_preserved(boundary, value):
    boundary.create_lead_with_custom_fields(
        json.dumps({"custom1": value}), FullName=LEGITIMATE[0], **API_CONTACT
    )
    assert boundary._post.call_args.args[0]["custom1"] == value
    boundary._post.reset_mock()
    server.update_lead_fields(7, custom_fields_json=json.dumps({"custom1": value}))
    assert boundary._post.call_args.args[0]["custom1"] == str(value)


def test_all_registered_write_tools_reject_egyptian_blanks_through_mcp(boundary):
    async def probe():
        for tool in server.mcp._tool_manager.list_tools():
            if tool.name == "get_lead":
                continue
            value = "\U00013442" + "".join(MARKS)
            if tool.name.startswith("create_lead"):
                args = dict(CONTACT, full_name=value)
            elif tool.name == "update_lead_fields":
                args = {"lead_id": 7, "status": value}
            elif tool.name == "update_lead_contact_info":
                args = {"lead_id": 7, "email": value}
            elif tool.name == "set_custom_field":
                args = {"lead_id": 7, "field_name": "custom1", "value": value}
            else:
                field = next(k for k in tool.parameters["properties"] if k != "lead_id")
                args = {"lead_id": 7, field: value}
            result = await server.mcp._handle_call_tool(
                None, CallToolRequestParams(name=tool.name, arguments=args)
            )
            assert result.is_error, tool.name
            boundary._post.assert_not_called()

    asyncio.run(probe())


@pytest.mark.parametrize("bad", ("\x00", "\ud800", "\udfff"))
def test_hard_errors_cannot_be_hidden_by_visible_fields_or_aliases(boundary, bad):
    with pytest.raises(ArgumentError):
        boundary.create_lead_with_custom_fields(
            json.dumps({"ｃｕｓｔｏｍ１": bad, "custom1": "visible"}),
            FullName=LEGITIMATE[0],
            **API_CONTACT,
        )
    boundary._post.assert_not_called()


def test_marks_and_normalization_do_not_create_content():
    for value in ("\u00a8", "\u037a", "".join(MARKS), "\U00013441" + "".join(MARKS)):
        assert not meaningful_value(value)
        assert not meaningful_name(value)
    assert meaningful_name("e\u0301")
    assert meaningful_value("!\u0301")


def test_new_unicode_class_members_are_derived_without_point_lists(monkeypatch):
    from lawruler_mcp import validation

    real_name, real_category = unicodedata.name, unicodedata.category
    future_names = {
        "A": "FUTURE FULL BLANK",
        "B": "FUTURE FILLER",
        "C": "FUTURE SPACE",
        "D": "FUTURE INVISIBLE",
        "E": "FUTURE ZERO WIDTH",
        "F": "FUTURE SEPARATOR",
        "G": "VARIATION SELECTOR-999",
        "H": "TAG FUTURE LETTER",
        "I": "FUTURE JOINER",
        "J": "FUTURE NULL",
    }
    monkeypatch.setattr(
        unicodedata,
        "name",
        lambda c, default="": future_names.get(c, real_name(c, default)),
    )
    monkeypatch.setattr(
        unicodedata,
        "category",
        lambda c: {
            "K": "Co",
            "L": "Cn",
            "M": "Mn",
            "N": "Mc",
            "O": "Me",
            "P": "Cf",
            "Q": "Zs",
        }.get(c, real_category(c)),
    )
    monkeypatch.setattr(
        validation, "_BLANK_CODE_POINTS", validation._derive_blank_code_points()
    )
    for value in "ABCDEFGHIJKLMNOPQ":
        assert not validation.meaningful_value(value)
        assert not validation.meaningful_name(value)
    assert validation.meaningful_name("R")


def test_mixed_blank_classes_cannot_supply_content(boundary):
    import random

    pool = (
        "\U00013441",
        "\U0001d159",
        "\u115f",
        "\u2800",
        "\ue000",
        "\U000f0000",
        "\u0378",
        "\u200b",
        "\u2061",
        "\u2029",
        "\u001f",
        *MARKS,
    )
    randomizer = random.Random(20261002)
    for _ in range(1000):
        value = "".join(randomizer.choices(pool, k=12))
        assert not meaningful_value(value) and not meaningful_name(value)
        with pytest.raises(ArgumentError):
            boundary.update_lead(7, custom1=value)
        boundary._post.assert_not_called()
