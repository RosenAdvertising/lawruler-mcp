"""Exhaustive offline Unicode/write-path audit, deliberately outside pytest collection.

Run with the repo's Python, --output DIR --label before|after --workers 8.
Every scalar AND surrogate/unassigned point is actually invoked on every route;
there is no predicate-based routing shortcut or representative-point sampling.
Combining-category coverage means prefix/suffix Mn, Mc, Me and their mixture,
not the Cartesian product of every code point with every individual mark.
Every individual mark is itself a base candidate in the full code-point loop.
"""

import argparse
import asyncio
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sys
import time
import unicodedata as ud


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TERMS = (
    "BLANK",
    "FILLER",
    "SPACE",
    "INVISIBLE",
    "ZERO WIDTH",
    "SEPARATOR",
    "VARIATION SELECTOR",
    "TAG",
    "JOINER",
    "NULL",
)
# Unicode 15 DerivedCoreProperties / PropList fixtures, independent of production.
IGNORABLE_RANGES = (
    (0xAD, 0xAD),
    (0x34F, 0x34F),
    (0x61C, 0x61C),
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
WHITE_SPACE_RANGES = (
    (9, 13),
    (0x20, 0x20),
    (0x85, 0x85),
    (0xA0, 0xA0),
    (0x1680, 0x1680),
    (0x2000, 0x200A),
    (0x2028, 0x2029),
    (0x202F, 0x202F),
    (0x205F, 0x205F),
    (0x3000, 0x3000),
)
IGNORABLE = {cp for lo, hi in IGNORABLE_RANGES for cp in range(lo, hi + 1)}
WHITE_SPACE = {cp for lo, hi in WHITE_SPACE_RANGES for cp in range(lo, hi + 1)}
# Independently reviewed rendering exceptions, not name-substring guesses.
# Braille blank has no dots; the musical null notehead supplies no notehead ink.
# The Egyptian placeholders are Lo, so keep them explicit as a policy floor.
RENDERING_BLANKS = {0x2800, 0x13441, 0x13442, 0x1D159}
MARKS = ("\u0301", "\u093e", "\u20dd")  # Mn, Mc, Me
FORM_NAMES = (
    "alone",
    "repeated",
    "suffix-Mn",
    "prefix-Mn",
    "suffix-Mc",
    "prefix-Mc",
    "suffix-Me",
    "prefix-Me",
    "mixed-Mn-Mc-Me",
)
CONTACT = {"cell_phone": "5550100", "email": "sentinel@example.invalid"}
API_CONTACT = {"CellPhone": "5550100", "Email1": "sentinel@example.invalid"}
API_NAMES = ("FullName", "FirstName", "LastName", "BusinessName", "CampaignName")
LEGITIMATE = (
    "José García",
    "Jose\u0301 Garci\u0301a",
    "สมชาย ใจดี",
    "خوسيه غارسيا",
    "王小明",
)


def forms(char):
    return (
        char,
        char * 2,
        *(v for mark in MARKS for v in (char + mark, mark + char)),
        MARKS[0] + char + MARKS[1] + MARKS[2],
    )


def name_mechanism(name):
    # Match semantic name words, not substrings of TAGALOG, MONOSPACE, VOLTAGE,
    # PENTAGON, etc. TAG characters are a prefix class, not cuneiform syllables.
    words = name.replace("-", " ").split()
    for term in TERMS:
        if term == "TAG":
            if name.startswith("TAG ") or name in ("LANGUAGE TAG", "CANCEL TAG"):
                return "name:TAG"
        elif len(term.split()) == 1:
            if term in words:
                return "name:" + term
        elif term in name:
            return "name:" + term
    return ""


def direct_mechanism(char):
    cp = ord(char)
    category = ud.category(char)
    if cp in WHITE_SPACE:
        return "White_Space"
    if cp in IGNORABLE:
        return "Default_Ignorable_Code_Point"
    if category[0] in "ZCM":
        return "category:" + category
    if cp in RENDERING_BLANKS:
        return "rendering:blank"
    # Punctuation and symbol names describe their meaning, not their ink.
    if category[0] not in "PS":
        return name_mechanism(ud.name(char, ""))
    return ""


def classify(char):
    """Property/rendering policy; broad-name candidates are recorded separately."""
    reason = direct_mechanism(char)
    if reason:
        return reason
    normalized = ud.normalize("NFKC", char)
    if not any(
        not direct_mechanism(c) and ud.category(c)[0] in "LNPS" for c in normalized
    ):
        return "normalization:spacing-or-mark-only"
    return "visible"


def forbid_network(*args, **kwargs):
    raise AssertionError("Network is forbidden in the Unicode sweep")


def isolated_imports():
    os.environ["LAWRULER_API_KEY"] = "SENTINEL-API-KEY"
    os.environ["LAWRULER_BASE_URL"] = "https://test.lawruler.com"
    os.environ["LAWRULER_MCP_USE_KEYRING"] = "0"
    socket.socket.connect = forbid_network
    socket.socket.connect_ex = forbid_network
    socket.create_connection = forbid_network
    socket.getaddrinfo = forbid_network
    from lawruler_mcp import client, server, validation
    from lawruler_mcp.errors import ArgumentError
    import requests

    requests.sessions.Session.request = forbid_network
    return client, server, validation, ArgumentError


class PostRecorder:
    """Constant-memory _post mock: never constructs a session or sends HTTP."""

    def __init__(self):
        self.data = None

    def __call__(self, data):
        assert self.data is None, "A route posted more than once"
        self.data = data
        return {}


def routes_for(client, server):
    routes = []
    for tool_name in ("create_lead", "create_lead_full", "create_lead_obo"):
        tool = getattr(server, tool_name)
        routes.extend(
            (
                (
                    tool_name + "/name",
                    "name",
                    lambda v, f=tool: f(full_name=v, **CONTACT),
                ),
                (
                    tool_name + "/contacts",
                    "value",
                    lambda v, f=tool: f(full_name="Valid Name", cell_phone=v, email=v),
                ),
                (
                    tool_name + "/optional",
                    "optional",
                    lambda v, f=tool: f(full_name="Valid Name", summary=v, **CONTACT),
                ),
            )
        )
    routes.extend(
        (
            (
                "update/contact",
                "value",
                lambda v: server.update_lead_contact_info(7, email=v),
            ),
            (
                "update/standard",
                "value",
                lambda v: server.update_lead_fields(7, status=v),
            ),
            (
                "update/multi-custom",
                "value",
                lambda v: server.update_lead_fields(
                    7, custom_fields_json=json.dumps({"custom1": v})
                ),
            ),
            (
                "update/single-custom",
                "value",
                lambda v: server.set_custom_field(7, "custom1", v),
            ),
        )
    )
    for name in (
        "update_lead_status",
        "update_lead_assignee",
        "update_lead_owner",
        "update_lead_case_type",
        "update_lead_summary",
        "add_conversation_note",
        "add_tags_to_lead",
        "update_lead_language",
    ):
        tool = getattr(server, name)
        routes.append((name, "value", lambda v, f=tool: f(7, v)))
    routes.extend(
        (
            (
                "direct/update-names",
                "name",
                lambda v: client.update_lead(7, **dict.fromkeys(API_NAMES, v)),
            ),
            (
                "direct/create-standard",
                "name",
                lambda v: client.create_lead_with_custom_fields(
                    "{}", FullName=v, CellPhone=v, Email1=v
                ),
            ),
            (
                "direct/create-custom",
                "name",
                lambda v: client.create_lead_with_custom_fields(
                    json.dumps(dict.fromkeys(("FullName", "CellPhone", "Email1"), v))
                ),
            ),
            (
                "direct/create-merged",
                "name",
                lambda v: client.create_lead_with_custom_fields(
                    json.dumps({"CellPhone": v, "Email1": v}), FullName=v
                ),
            ),
            (
                "direct/create-optional",
                "optional",
                lambda v: client.create_lead_with_custom_fields(
                    json.dumps({"custom1": v}), FullName="Valid Name", **API_CONTACT
                ),
            ),
        )
    )
    return routes


def run_chunk(bounds):
    start, stop = bounds
    cm, server, validation, ArgumentError = isolated_imports()
    client = object.__new__(cm.LawRulerClient)
    recorder = PostRecorder()
    client._post = recorder
    server._c = lambda: client
    routes = routes_for(client, server)
    counts = Counter()
    route_counts = {name: Counter() for name, _, _ in routes}
    accepted = []
    escapes = []
    name_hits = []
    problems = []
    for cp in range(start, stop):
        char = chr(cp)
        category = ud.category(char)
        name = ud.name(char, "")
        mechanism = classify(char)
        blank = mechanism != "visible"
        expected_name = not blank and any(
            ud.category(c)[0] in "LN" and not direct_mechanism(c)
            for c in ud.normalize("NFKC", char)
        )
        counts["code_points"] += 1
        counts["category:" + category] += 1
        counts["classification:" + mechanism] += 1
        if any(term in name for term in TERMS):
            name_hits.append([cp, category, name, mechanism])
        name_mask = value_mask = 0
        escaped_routes = Counter()
        for index, value in enumerate(forms(char)):
            counts["forms"] += 1
            outcomes = []
            for predicate in (validation.meaningful_name, validation.meaningful_value):
                try:
                    outcomes.append(bool(predicate(value)))
                except ArgumentError:
                    outcomes.append(False)
                    counts["predicate_hard_errors"] += 1
            has_name, has_value = outcomes
            counts["predicate_calls"] += 2
            name_mask |= int(has_name) << index
            value_mask |= int(has_value) << index
            counts["accepted_name_forms"] += has_name
            counts["accepted_value_forms"] += has_value
            if blank:
                counts["blank_name_forms"] += has_name
                counts["blank_value_forms"] += has_value
            else:
                counts["visible_value_rejections"] += not has_value
                counts["name_oracle_mismatches"] += has_name != expected_name
            for route_name, kind, call in routes:
                stats = route_counts[route_name]
                recorder.data = None
                stats["calls"] += 1
                try:
                    call(value)
                except ArgumentError:
                    stats["rejected"] += 1
                except Exception as exc:
                    stats["unexpected_errors"] += 1
                    if len(problems) < 10:
                        problems.append([cp, index, route_name, type(exc).__name__])
                if recorder.data is not None:
                    stats["posts"] += 1
                    sent = value in recorder.data.values()
                    if sent:
                        stats["unchanged_values"] += 1
                        if blank:
                            stats["blank_values_posted"] += 1
                            escaped_routes[route_name] += 1
                        if kind == "name" and not has_name:
                            stats["non_name_values_posted"] += 1
                    elif has_name if kind == "name" else has_value:
                        stats["unexpected_omissions"] += 1
                        if len(problems) < 10:
                            problems.append(
                                [cp, index, route_name, "omitted meaningful value"]
                            )
                elif has_name if kind == "name" else has_value:
                    stats["meaningful_rejections"] += 1
                if (expected_name if kind == "name" else not blank) and (
                    recorder.data is None or value not in recorder.data.values()
                ):
                    stats["oracle_visible_rejections"] += 1
        if name_mask or value_mask:
            accepted.append([cp, category, mechanism, name_mask, value_mask])
        if blank and (name_mask or value_mask or escaped_routes):
            escapes.append(
                {
                    "cp": cp,
                    "category": category,
                    "name": name,
                    "mechanism": mechanism,
                    "name_mask": name_mask,
                    "value_mask": value_mask,
                    "routes": dict(escaped_routes),
                }
            )
    return (
        dict(counts),
        {k: dict(v) for k, v in route_counts.items()},
        accepted,
        escapes,
        name_hits,
        problems,
    )


def check_legitimate():
    cm, server, _, ArgumentError = isolated_imports()
    from mcp.types import CallToolRequestParams

    client = object.__new__(cm.LawRulerClient)
    recorder = PostRecorder()
    client._post = recorder
    server._c = lambda: client
    count = 0
    for value in LEGITIMATE:
        for name, _, call in routes_for(client, server):
            recorder.data = None
            call(value)
            assert recorder.data is not None and value in recorder.data.values(), name
            count += 1
    for value in (0, False):
        recorder.data = None
        client.create_lead_with_custom_fields(
            json.dumps({"custom1": value}), FullName=LEGITIMATE[0], **API_CONTACT
        )
        assert recorder.data["custom1"] is value
        count += 1
        recorder.data = None
        server.update_lead_fields(7, custom_fields_json=json.dumps({"custom1": value}))
        assert recorder.data["custom1"] == str(value)
        count += 1

    # Exercise actual MCP dispatch in addition to the full direct-tool sweep.
    async def dispatch_checks():
        cases = 0
        for value in LEGITIMATE:
            for tool in server.mcp._tool_manager.list_tools():
                if tool.name == "get_lead":
                    continue
                if tool.name.startswith("create_lead"):
                    args = dict(CONTACT, full_name=value)
                elif tool.name == "update_lead_fields":
                    args = {"lead_id": 7, "status": value}
                elif tool.name == "update_lead_contact_info":
                    args = {"lead_id": 7, "email": value}
                elif tool.name == "set_custom_field":
                    args = {"lead_id": 7, "field_name": "custom1", "value": value}
                else:
                    field = next(
                        k for k in tool.parameters["properties"] if k != "lead_id"
                    )
                    args = {"lead_id": 7, field: value}
                recorder.data = None
                result = await server.mcp._handle_call_tool(
                    None, CallToolRequestParams(name=tool.name, arguments=args)
                )
                assert not result.is_error and value in recorder.data.values(), (
                    tool.name
                )
                cases += 1
        return cases

    count += asyncio.run(dispatch_checks())
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--stop", type=lambda x: int(x, 0), default=0x110000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    summary = {
        "python": sys.version,
        "unicode": ud.unidata_version,
        "stop": args.stop,
        "forms": FORM_NAMES,
        "marks": [ord(c) for c in MARKS],
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                ROOT / "lawruler_mcp/validation.py",
                ROOT / "lawruler_mcp/client.py",
                Path(__file__),
            )
        },
    }
    counts, routes = Counter(), {}
    escapes, name_hits, problems = [], [], []
    batches = [
        (start, min(start + 0x1000, args.stop)) for start in range(0, args.stop, 0x1000)
    ]
    accepted_path = args.output / (args.label + "-accepted.tsv")
    with (
        accepted_path.open("w") as out,
        ProcessPoolExecutor(
            max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")
        ) as pool,
    ):
        out.write(
            "code_point\tcategory\tclassification\tname_forms_bitmask\tvalue_forms_bitmask\n"
        )
        for index, (stats, route_stats, accepted, found, hits, errors) in enumerate(
            pool.map(run_chunk, batches)
        ):
            counts.update(stats)
            for name, values in route_stats.items():
                routes.setdefault(name, Counter()).update(values)
            escapes.extend(found)
            name_hits.extend(hits)
            problems.extend(errors)
            for cp, category, mechanism, names, values in accepted:
                out.write(f"U+{cp:06X}\t{category}\t{mechanism}\t{names}\t{values}\n")
            if index % 8 == 7 or index + 1 == len(batches):
                print(
                    f"{args.label}: {counts['code_points']:,}/{args.stop:,} points; "
                    f"{len(escapes)} escaped points; {time.monotonic() - started:.1f}s",
                    flush=True,
                )
    summary.update(
        counts=dict(counts),
        routes=routes,
        escapes=escapes,
        broad_name_hits=name_hits,
        problems=problems,
        legitimate_checks=check_legitimate(),
        seconds=time.monotonic() - started,
    )
    summary["route_calls"] = sum(v["calls"] for v in routes.values())
    summary["blank_values_posted"] = sum(
        v["blank_values_posted"] for v in routes.values()
    )
    (args.output / (args.label + "-sweep.json")).write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "route_calls",
                    "blank_values_posted",
                    "legitimate_checks",
                    "seconds",
                )
            }
        )
    )
    if args.label == "after" or args.label.startswith("round5-after"):
        assert not escapes and not problems, "See sweep JSON for failures"
        assert not counts["visible_value_rejections"]
        assert not counts["name_oracle_mismatches"]
        assert all(
            not v.get("unexpected_errors")
            and not v.get("unexpected_omissions")
            and not v.get("non_name_values_posted")
            and not v.get("meaningful_rejections")
            and not v.get("oracle_visible_rejections")
            for v in routes.values()
        )


if __name__ == "__main__":
    main()
