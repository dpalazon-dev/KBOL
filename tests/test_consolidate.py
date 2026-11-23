"""RES-01: what is in force. Scenarios ESC-01 and ESC-02 of the contract and mandatory clause cases (guide §7)."""

from conftest import decision

from kbol.consolidate import consolidate
from kbol.projection import Snapshot


def snap(*pairs):
    return Snapshot({r["id"]: r for r, _ in pairs}, revision="r1", bodies={r["id"]: c for r, c in pairs})


def repl(target, by):
    return {"target": target, "operation": "replaces", "by": by}


def by_ref(res):
    return {c["reference"]: c for c in res["clauses"]}


CUT_ESC01 = dict(valid_at="2026-11-03T12:00:00Z", known_until="2026-11-03T12:00:00Z")


def esc01(*extra):
    a = decision(
        "DEC-A",
        {"C1": "The report is delivered on Mondays.", "C2": "The report only includes checked data."},
        recorded="2026-11-01T00:00:00Z",
    )
    b = decision(
        "DEC-B",
        {"C1": "The report is delivered on Tuesdays."},
        recorded="2026-11-02T00:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-B#C1")],
    )
    c = decision(
        "DEC-C",
        {"C1": "The report also includes estimated data."},
        state="proposed",
        amends=[repl("DEC-A#C2", "DEC-C#C1")],
    )
    return snap(a, b, c, *extra)


def test_esc01_partial_replacement_without_losing_conditions():
    res = consolidate(esc01(), ["DEC-A"], **CUT_ESC01)
    c = by_ref(res)
    assert c["DEC-A#C1"]["state"] == "current" and c["DEC-A#C1"]["text"] == "The report is delivered on Tuesdays."
    assert c["DEC-A#C1"]["origin"] == "DEC-B#C1" and c["DEC-A#C1"]["chain"] == ["DEC-A#C1", "DEC-B#C1"]
    assert c["DEC-A#C2"]["text"] == "The report only includes checked data." and c["DEC-A#C2"]["origin"] == "DEC-A#C2"
    assert res["validity"] == {"DEC-A": "partial"}
    assert res["proposals"] == [
        {"decision": "DEC-C", "amendment": repl("DEC-A#C2", "DEC-C#C1"), "state": "proposed", "binding": False}
    ]
    assert res["conflicts"] == []
    # The authority of the text in force is that of the originating decision.
    assert c["DEC-A#C1"]["authority"]["authorized_by"] == ["ROLE-EXAMPLE"]


def test_esc01_conflict_variant():
    d = decision(
        "DEC-D",
        {"C1": "The report is delivered on Wednesdays."},
        recorded="2026-11-02T12:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-D#C1")],
    )
    res = consolidate(esc01(d), ["DEC-A"], **CUT_ESC01)
    c = by_ref(res)
    assert c["DEC-A#C1"]["state"] == "conflict" and "text" not in c["DEC-A#C1"]
    assert res["conflicts"] == [
        {"code": "NORMATIVE_CONFLICT", "clause": "DEC-A#C1", "candidates": ["DEC-B#C1", "DEC-D#C1"]}
    ]
    assert c["DEC-A#C2"]["state"] == "current"  # the conflict does not contaminate the rest


def test_declared_succession_resolves_the_overlap():
    d = decision(
        "DEC-D",
        {"C1": "The report is delivered on Wednesdays."},
        recorded="2026-11-02T12:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-D#C1")],
        depends_on=[{"target": "DEC-B", "condition": "accepted_and_in_force"}],
    )
    c = by_ref(consolidate(esc01(d), ["DEC-A"], **CUT_ESC01))
    assert c["DEC-A#C1"]["origin"] == "DEC-D#C1"


def test_replacement_chain_keeps_origin():
    e = decision(
        "DEC-E",
        {"C1": "The report is delivered on Thursdays."},
        recorded="2026-11-03T00:00:00Z",
        amends=[repl("DEC-B#C1", "DEC-E#C1")],
    )
    c = by_ref(consolidate(esc01(e), ["DEC-A"], **CUT_ESC01))
    assert c["DEC-A#C1"]["chain"] == ["DEC-A#C1", "DEC-B#C1", "DEC-E#C1"] and c["DEC-A#C1"]["origin"] == "DEC-E#C1"


def test_repealing_the_amending_decision_does_not_revive_the_previous_text():
    f = decision(
        "DEC-F",
        {"C1": "Reason."},
        recorded="2026-11-03T00:00:00Z",
        amends=[{"target": "DEC-B#C1", "operation": "repeals"}],
    )
    c = by_ref(consolidate(esc01(f), ["DEC-A"], **CUT_ESC01))
    assert c["DEC-A#C1"]["state"] == "repealed" and c["DEC-A#C1"]["origin"] == "DEC-F"
    assert "text" not in c["DEC-A#C1"]


def test_retired_amending_decision_does_not_revive():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        until="2026-11-10T00:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-B#C1")],
    )
    res = consolidate(snap(a, b), ["DEC-A"], valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")
    c = by_ref(res)
    assert c["DEC-A#C1"]["state"] == "no_rule" and "text" not in c["DEC-A#C1"]
    assert any("DEC-B" in a for a in res["warnings"])


def test_future_amendment_does_not_alter_the_current_consolidation():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        valid="2026-12-01T00:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-B#C1")],
    )
    res = consolidate(snap(a, b), ["DEC-A"], **CUT_ESC01)
    c = by_ref(res)
    assert c["DEC-A#C1"]["text"] == "Monday." and res["validity"] == {"DEC-A": "full"}
    assert res["future"] == [{"decision": "DEC-B", "valid_from": "2026-12-01T00:00:00Z"}]


def test_addition_with_identity_and_position():
    g = decision(
        "DEC-G",
        {"C1": "The report is published on the dashboard."},
        recorded="2026-11-03T00:00:00Z",
        amends=[{"target": "DEC-A", "operation": "adds", "by": "DEC-G#C1", "position": "after DEC-A#C2"}],
    )
    c = by_ref(consolidate(esc01(g), ["DEC-A"], **CUT_ESC01))
    assert c["DEC-G#C1"]["state"] == "current" and c["DEC-G#C1"]["position"] == "after DEC-A#C2"
    assert c["DEC-G#C1"]["added_to"] == "DEC-A"


def test_decision_not_in_force_does_not_apply():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z", valid="2026-12-01T00:00:00Z")
    res = consolidate(snap(a), ["DEC-A"], **CUT_ESC01)
    assert res["clauses"] == [] and res["validity"] == {"DEC-A": "not_in_force"}
    p = decision("DEC-P", {"C1": "x"}, state="proposed")
    res = consolidate(snap(p), ["DEC-P"], **CUT_ESC01)
    assert res["clauses"] == [] and res["validity"] == {"DEC-P": "not_in_force"}


def test_missing_decision():
    res = consolidate(snap(), ["DEC-X"], **CUT_ESC01)
    assert res["clauses"] == [] and res["missing"] == ["DEC-X"]


def esc02():
    t = decision(
        "DEC-T", {"C1": "The deadline is five days."}, recorded="2026-11-10T09:00:00Z", valid="2026-11-15T00:00:00Z"
    )
    u = decision(
        "DEC-U",
        {"C1": "The deadline is seven days."},
        recorded="2026-11-20T09:00:00Z",
        valid="2026-11-12T00:00:00Z",
        amends=[repl("DEC-T#C1", "DEC-U#C1")],
    )
    return snap(t, u)


def texts(res):
    return [c["text"] for c in res["clauses"] if c["state"] == "current"]


def test_esc02_query_a_nothing_known_in_force():
    res = consolidate(
        esc02(), ["DEC-T", "DEC-U"], valid_at="2026-11-13T12:00:00Z", known_until="2026-11-14T12:00:00Z"
    )
    assert texts(res) == []
    assert res["future"] == [{"decision": "DEC-T", "valid_from": "2026-11-15T00:00:00Z"}]
    assert res["missing"] == []  # DEC-U exists in the revision, but was not recorded at the cut
    assert res["validity"]["DEC-U"] == "not_recorded_then"


def test_esc02_query_b_retroactive():
    res = consolidate(
        esc02(), ["DEC-T", "DEC-U"], valid_at="2026-11-13T12:00:00Z", known_until="2026-11-21T12:00:00Z"
    )
    assert texts(res) == ["The deadline is seven days."]
    assert any("retroactive" in a and "DEC-U" in a for a in res["warnings"])


def test_esc02_query_c_two_knowledge_cuts():
    before = consolidate(
        esc02(), ["DEC-T", "DEC-U"], valid_at="2026-11-16T12:00:00Z", known_until="2026-11-17T12:00:00Z"
    )
    assert texts(before) == ["The deadline is five days."]
    after = consolidate(
        esc02(), ["DEC-T", "DEC-U"], valid_at="2026-11-16T12:00:00Z", known_until="2026-11-21T12:00:00Z"
    )
    assert texts(after) == ["The deadline is seven days."]  # only once, even if it arrives by two ways


def test_consolidate_neither_writes_nor_mutates_the_snapshot():
    s = esc01()
    import copy

    before = copy.deepcopy(s.records), copy.deepcopy(s.bodies)
    consolidate(s, ["DEC-A"], **CUT_ESC01)
    assert (s.records, s.bodies) == before


def test_an_id_with_anchor_consolidates_only_that_clause():
    # Bench baseline, P12: `consolidate --ids ADR-0059#C3` reported the clause as missing.
    res = consolidate(esc01(), ["DEC-A#C1"], **CUT_ESC01)
    assert [c["reference"] for c in res["clauses"]] == ["DEC-A#C1"]
    assert res["clauses"][0]["origin"] == "DEC-B#C1" and res["validity"] == {"DEC-A": "partial"}
    assert res["missing"] == []


def test_an_anchor_the_decision_does_not_have_is_missing():
    res = consolidate(esc01(), ["DEC-A#C9"], **CUT_ESC01)
    assert res["clauses"] == [] and res["validity"] == {} and res["missing"] == ["DEC-A#C9"]
