"""The `support` query: whether what holds up each record is in force at the two cuts, and what changed."""

import copy

from conftest import decision, event, record

from kbol.projection import Snapshot
from kbol.support import delta, support, supports

T1, T2, T3, T4, T5 = (f"2026-11-0{d}T00:00:00Z" for d in (1, 2, 3, 4, 5))
BEFORE = dict(valid_at="2026-11-03T12:00:00Z", known_until="2026-11-03T12:00:00Z")
AFTER = dict(valid_at="2026-11-10T12:00:00Z", known_until="2026-11-10T12:00:00Z")


def history(type_, ident, *steps, **fields):
    """Record with one state event per step (state, recorded_at[, valid_from])."""
    events, prev = [], None
    for i, (state, t, *since) in enumerate(steps):
        events.append(
            event(
                "creation" if prev is None else "transition",
                event_id=f"E{i}",
                previous_state=prev,
                new_state=state,
                recorded_at=t,
                valid_from=since[0] if since else t,
            )
        )
        prev = state
    return record(type_, id=ident, state=prev, events=events, **fields)


def fact(ident, t=T1, since=None, **fields):
    return history("fact", ident, ("proposed", t), ("accepted", t, since or t), **fields)


def synthesis(ident, dependencies):
    return history("synthesis", ident, ("draft", T1), dependencies=dependencies)


def snap(*pairs, legacy=None):
    regs, bodies = {}, {}
    for pair in pairs:
        r, c = pair if isinstance(pair, tuple) else (pair, "")
        regs[r["id"]], bodies[r["id"]] = r, c
    return Snapshot(regs, "r1", bodies, {}, legacy or {})


def entry(res, ident):
    return next(r for r in res["records"] if r["id"] == ident)


def support_(res, ident, ref):
    return next(a for a in entry(res, ident)["supports"] if a["ref"] == ref)


def bench_case(**amendment):
    """Synthesis that depends on DEC-A#C1; DEC-B, accepted later, replaces or repeals it. The synthesis does not change."""
    a = decision("DEC-A", {"C1": "Monday."}, recorded=T1)
    b = decision("DEC-B", {"C1": "Tuesday."}, recorded=T5, amends=[{"target": "DEC-A#C1", **amendment}])
    return snap(a, b, (synthesis("SYN-A", ["DEC-A#C1"]), "Summary: the report is delivered on Mondays."))


def test_synthesis_whose_text_does_not_change_but_loses_validity():
    s = bench_case(operation="replaces", by="DEC-B#C1")
    before, after = support(s, **BEFORE), support(s, **AFTER)
    assert support_(before, "SYN-A", "DEC-A#C1")["situation"] == "in_force"
    assert entry(before, "SYN-A")["support"] == "intact"
    a = support_(after, "SYN-A", "DEC-A#C1")
    assert a["situation"] == "not_in_force" and a["field"] == "dependencies" and "DEC-B#C1" in a["reason"]
    assert a["chain"] == ["DEC-A#C1", "DEC-B#C1"] and a["origin"] == "DEC-B#C1"
    assert entry(after, "SYN-A")["support"] == "broken" and entry(after, "SYN-A")["state"] == "draft"
    d = delta(s, BEFORE, AFTER)
    (change,) = d["changes"]
    assert (change["id"], change["ref"], change["before"]["situation"], change["after"]["situation"]) == (
        "SYN-A",
        "DEC-A#C1",
        "in_force",
        "not_in_force",
    )
    assert change["explanation"]["chain"] == ["DEC-A#C1", "DEC-B#C1"]
    assert {"id": "SYN-A", "before": "intact", "after": "broken"} in d["records"]


def test_repealed_clause_names_the_decision_that_repeals_it():
    s = bench_case(operation="repeals", by="DEC-B")
    a = support_(support(s, **AFTER), "SYN-A", "DEC-A#C1")
    assert a["situation"] == "not_in_force" and a["origin"] == "DEC-B" and "repealed" in a["reason"]
    assert delta(s, BEFORE, AFTER)["changes"][0]["explanation"]["origin"] == "DEC-B"


def test_validity_ending_before_the_cut_explains_the_transition():
    a = decision("DEC-A", {"C1": "Monday."}, recorded=T1, until=T5)
    s = snap(a, synthesis("SYN-A", ["DEC-A#C1"]))
    assert support_(support(s, **BEFORE), "SYN-A", "DEC-A#C1")["situation"] == "in_force"
    assert support_(support(s, **AFTER), "SYN-A", "DEC-A#C1")["situation"] == "not_in_force"
    (change,) = delta(s, BEFORE, AFTER)["changes"]
    assert change["explanation"]["transition"]["valid_until"] == T5


def test_succeeded_fact_is_not_in_force_and_names_its_successor():
    s = snap(fact("FACT-A"), fact("FACT-B", t=T5, supersedes=["FACT-A"]), fact("FACT-X", based_on=["FACT-A"]))
    assert support_(support(s, **BEFORE), "FACT-X", "FACT-A")["situation"] == "in_force"
    a = support_(support(s, **AFTER), "FACT-X", "FACT-A")
    assert a["situation"] == "not_in_force" and a["successors"] == ["FACT-B"]
    assert delta(s, BEFORE, AFTER)["changes"][0]["explanation"]["successors"] == ["FACT-B"]


def test_retired_source_is_not_in_force_in_based_on_nor_in_sources():
    f = history("source", "SRC-A", ("registered", T1), ("retired", T5))
    x = fact("FACT-X", based_on=["SRC-A"], sources=[{"id": "s1", "resource": "SRC-A"}])
    s = snap(f, x)
    res = support(s, **AFTER)
    assert [(a["field"], a["situation"]) for a in entry(res, "FACT-X")["supports"]] == [
        ("based_on", "not_in_force"),
        ("sources", "not_in_force"),
    ]
    assert "retired" in support_(res, "FACT-X", "SRC-A")["reason"]
    assert entry(support(s, **BEFORE), "FACT-X")["support"] == "intact"


def test_late_correction_changes_the_answer_with_the_knowledge_cut():
    # FACT-B is added on day 5 with effect from day 2: what was known on day 4 does not include it yet.
    b = fact("FACT-B", t=T5, since=T2, supersedes=["FACT-A"])
    s = snap(fact("FACT-A"), b, fact("FACT-X", based_on=["FACT-A"]))
    valid = "2026-11-10T12:00:00Z"
    known_on_4 = dict(valid_at=valid, known_until=T4)
    known_on_10 = dict(valid_at=valid, known_until=valid)
    assert support_(support(s, **known_on_4), "FACT-X", "FACT-A")["situation"] == "in_force"
    assert support_(support(s, **known_on_10), "FACT-X", "FACT-A")["situation"] == "not_in_force"
    assert delta(s, known_on_4, known_on_10)["changes"][0]["explanation"]["successors"] == ["FACT-B"]


def test_time_with_day_precision_is_undetermined():
    s = snap(fact("FACT-A", since="2026-11-10"), fact("FACT-X", based_on=["FACT-A"]))
    res = support(s, **AFTER)
    a = support_(res, "FACT-X", "FACT-A")
    assert a["situation"] == "undetermined" and a["code"] == "AMBIGUOUS_TIME"
    assert entry(res, "FACT-X")["support"] == "undetermined"


def test_successor_with_ambiguous_time_leaves_the_support_undetermined():
    b = fact("FACT-B", t=T5, since="2026-11-10", supersedes=["FACT-A"])
    a = support_(support(snap(fact("FACT-A"), b, fact("FACT-X", based_on=["FACT-A"])), **AFTER), "FACT-X", "FACT-A")
    assert a["situation"] == "undetermined" and a["successors"] == ["FACT-B"]


def test_missing_target_breaks_the_support():
    res = support(snap(fact("FACT-X", based_on=["SRC-NO"])), **AFTER)
    a = support_(res, "FACT-X", "SRC-NO")
    assert a["situation"] == "missing" and a["code"] == "MISSING_REFERENCE"
    assert entry(res, "FACT-X")["support"] == "broken"


def test_proposed_decision_as_support_is_not_in_force():
    p = decision("DEC-P", {"C1": "x"}, state="proposed")
    a = support_(support(snap(p, synthesis("SYN-A", ["DEC-P#C1"])), **AFTER), "SYN-A", "DEC-P#C1")
    assert a["situation"] == "not_in_force" and a["state"] == "proposed"


def test_fact_citation_in_the_body_counts_as_support():
    x = (fact("FACT-X", based_on=[]), 'According to <fact ref="FACT-A">the flow</fact>, it is enough.')
    res = support(snap(fact("FACT-A"), x), **AFTER)
    assert [(a["field"], a["ref"], a["situation"]) for a in entry(res, "FACT-X")["supports"]] == [
        ("body", "FACT-A", "in_force")
    ]


def test_malformed_mark_is_reported_and_not_kept_quiet():
    x = (fact("FACT-X", based_on=["FACT-A"]), 'According to <fact ref="FACT-B">without closing.')
    assert supports(*x)[1] and "malformed body" in supports(*x)[1]
    res = support(snap(fact("FACT-A"), x), **AFTER)
    e = entry(res, "FACT-X")
    assert "malformed body" in e["body"] and e["support"] == "undetermined"
    assert any("FACT-X" in t and "malformed body" in t for t in res["warnings"])


def test_cited_synthesis_reports_its_state_no_validity_and_legacy_does_not_break():
    inherited = {"id": "ADR-0001", "type": "decision", "path": "d.md", "legacy_state": "Accepted"}
    s = snap(synthesis("SYN-A", []), synthesis("SYN-B", ["SYN-A", "ADR-0001"]), legacy={"ADR-0001": inherited})
    res = support(s, **AFTER)
    assert [(a["ref"], a["situation"], a.get("state")) for a in entry(res, "SYN-B")["supports"]] == [
        ("SYN-A", "no_validity", "draft"),
        ("ADR-0001", "legacy", "Accepted"),
    ]
    assert entry(res, "SYN-B")["support"] == "intact" and entry(res, "SYN-A")["support"] == "no_supports"


def test_ids_filters_and_names_the_missing():
    res = support(bench_case(operation="replaces", by="DEC-B#C1"), **AFTER, ids=["SYN-A", "SYN-NO"])
    assert [r["id"] for r in res["records"]] == ["SYN-A"] and res["missing"] == ["SYN-NO"]
    assert res["records_examined"] == 1 and res["count"] == {"broken": 1}


def test_the_query_does_not_change_the_snapshot():
    s = bench_case(operation="replaces", by="DEC-B#C1")
    records, bodies = copy.deepcopy(s.records), copy.deepcopy(s.bodies)
    support(s, **AFTER)
    delta(s, BEFORE, AFTER)
    assert s.records == records and s.bodies == bodies


def test_retired_synthesis_as_support_breaks_the_support():
    """A support without an effective state does not break by itself, but one recorded as retired does."""
    retired = history("synthesis", "SYN-A", ("draft", T1), ("retired", T1), dependencies=[])
    res = support(snap(retired, synthesis("SYN-B", ["SYN-A"])), **AFTER)
    assert support_(res, "SYN-B", "SYN-A")["situation"] == "no_validity"
    assert support_(res, "SYN-B", "SYN-A")["state"] == "retired" and entry(res, "SYN-B")["support"] == "broken"


def test_without_ids_legacy_records_are_named_and_not_examined():
    inherited = {"id": "ADR-0001", "type": "decision", "path": "d.md", "legacy_state": "Accepted"}
    res = support(snap(synthesis("SYN-A", []), legacy={"ADR-0001": inherited}), **AFTER)
    assert [r["id"] for r in res["records"]] == ["SYN-A"] and res["records_examined"] == 1
    assert res["legacy"] == [inherited]
