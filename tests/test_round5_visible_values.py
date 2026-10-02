"""Visible punctuation is content; actual blank glyphs still cannot be content."""

import json
from unittest.mock import Mock

import pytest

from lawruler_mcp import client as client_module, server
from lawruler_mcp.errors import ArgumentError
from lawruler_mcp.validation import meaningful_name, meaningful_value
from unicode_blank_sweep import API_NAMES, forms, routes_for


# All old name-rule P*/S* rejections except the two actual blank symbols.
# First 25 are the round-4 findings; the remaining nine close its capped audit.
VISIBLE_POINTS = (
    0x060D,
    0x066B,
    0x066C,
    0x10FB,
    0x1368,
    0x2396,
    0x2400,
    0x241C,
    0x241D,
    0x241E,
    0x241F,
    0x2420,
    0x2D70,
    0x2E31,
    0x3037,
    0x10100,
    0x10101,
    0x1091F,
    0x111C8,
    0x1123A,
    0x115C4,
    0x115C5,
    0x11C43,
    0x1DA7F,
    0x1DA80,
    0x2422,
    0x303F,
    0xA8F9,
    0x10AF6,
    0x1144E,
    0x11945,
    0x11C44,
    0x11C45,
    0x11F48,
)
BLANK_FLOOR = (
    0x2800,
    0x3164,
    0xFFA0,
    0x115F,
    0x1160,
    0x13441,
    0x13442,
    0x1D159,
    0x0020,
    0x00A0,
    0x2003,
    0x2028,
    0x2029,
    0x0000,
    0x0001,
    0x200B,
    0xFE0F,
    0xE000,
    0xF0000,
    0x0378,
    0xD800,
    0x0301,
    0x093E,
    0x20DD,
)


@pytest.fixture
def boundary(monkeypatch):
    client = object.__new__(client_module.LawRulerClient)
    client._post = Mock(return_value={"LeadID": 7})
    monkeypatch.setattr(server, "_c", lambda: client)
    return client


@pytest.mark.parametrize("cp", VISIBLE_POINTS, ids=lambda cp: f"U+{cp:04X}")
@pytest.mark.parametrize("form_index", range(9))
def test_visible_symbols_post_unchanged_but_cannot_supply_names(
    boundary, cp, form_index
):
    value = forms(chr(cp))[form_index]
    assert meaningful_value(value)
    assert not meaningful_name(value)
    for route, kind, call in routes_for(boundary, server):
        boundary._post.reset_mock()
        if kind == "name":
            with pytest.raises(ArgumentError):
                call(value)
            boundary._post.assert_not_called()
        else:
            call(value)
            boundary._post.assert_called_once()
            assert value in boundary._post.call_args.args[0].values(), route


@pytest.mark.parametrize("cp", VISIBLE_POINTS, ids=lambda cp: f"U+{cp:04X}")
def test_visible_symbols_cannot_supply_any_custom_name_field(boundary, cp):
    for value in forms(chr(cp)):
        for field in API_NAMES:
            for spelling in (field, field.lower()):
                with pytest.raises(ArgumentError):
                    server.update_lead_fields(
                        7, custom_fields_json=json.dumps({spelling: value})
                    )
                with pytest.raises(ArgumentError):
                    boundary.set_custom_field(7, spelling, value)
                boundary._post.assert_not_called()


@pytest.mark.parametrize("cp", BLANK_FLOOR, ids=lambda cp: f"U+{cp:04X}")
@pytest.mark.parametrize("form_index", range(9))
def test_blank_floor_never_reaches_post(boundary, cp, form_index):
    value = forms(chr(cp))[form_index]
    for route, kind, call in routes_for(boundary, server):
        boundary._post.reset_mock()
        if kind == "optional" and cp not in (0, 0xD800):
            call(value)
            boundary._post.assert_called_once()
            assert value not in boundary._post.call_args.args[0].values(), route
        else:
            with pytest.raises(ArgumentError):
                call(value)
            boundary._post.assert_not_called()


def test_name_words_do_not_make_future_punctuation_or_symbols_blank(monkeypatch):
    from lawruler_mcp import validation

    real_name = validation.unicodedata.name
    monkeypatch.setattr(
        validation.unicodedata,
        "name",
        lambda c, default="": {
            "!": "FUTURE INVISIBLE SEPARATOR",
            "©": "FUTURE BLANK FILLER",
        }.get(c, real_name(c, default)),
    )
    monkeypatch.setattr(
        validation, "_BLANK_CODE_POINTS", validation._derive_blank_code_points()
    )
    assert validation.meaningful_value("!")
    assert validation.meaningful_value("©")
    assert not validation.meaningful_name("!")
    assert not validation.meaningful_name("©")
