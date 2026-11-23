"""VAL-07: `depends_on` conditions and ready milestones, without discarding counting as meeting (AUD-04)."""

from conftest import decision, event, record

from kbol.consolidate import _Query
from kbol.dependencies import evaluate, in_force_at_cut, ready
from kbol.projection import Snapshot

C = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")


def with_history(type_, *states, **fields):
    ev = [
        event(
            "creation",
            event_id="E0",
            previous_state=None,
            new_state=states[0],
            recorded_at="2026-11-01T00:00:00Z",
            valid_from="2026-11-01T00:00:00Z",
        )
    ]
    for i, (a, b) in enumerate(zip(states, states[1:]), start=1):
        t = f"2026-11-0{i + 1}T00:00:00Z"
        ev.append(event(event_id=f"E{i}", previous_state=a, new_state=b, recorded_at=t, valid_from=t))
    return record(type_, state=states[-1], events=ev, **fields)


def snap(*regs, bodies=None):
    return Snapshot({r["id"]: r for r in regs}, "r1", bodies or {})


def dep(target, condition):
    return [{"target": target, "condition": condition}]


def one(r, s):
    (result,) = evaluate(r, s, **C)
    return result


def test_cancelled_milestone_does_not_satisfy_the_dependency():
    y = with_history("milestone", "proposed", "cancelled", id="MS-Y")
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("MS-Y", "completed_with_evidence"))
    r = one(x, snap(x, y))
    assert r["satisfied"] is False and "cancelled" in r["reason"]


def test_completed_milestone_fails_closed_on_evidence():
    y = with_history("milestone", "proposed", "authorized", "in_progress", "completed", id="MS-Y")
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("MS-Y", "completed_with_evidence"))
    r = one(x, snap(x, y))
    # Fails closed until the record of checks per criterion exists (VAL-12).
    assert r["satisfied"] is False and r["code"] == "INSUFFICIENT_EVIDENCE"


def test_decision_accepted_and_in_force():
    a, ca = decision("DEC-A", {"C1": "x"}, recorded="2026-11-01T00:00:00Z")
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("DEC-A", "accepted_and_in_force"))
    assert one(x, snap(x, a, bodies={"DEC-A": ca}))["satisfied"] is True
    f, cf = decision("DEC-A", {"C1": "x"}, recorded="2026-11-01T00:00:00Z", valid="2026-12-01T00:00:00Z")
    assert one(x, snap(x, f, bodies={"DEC-A": cf}))["satisfied"] is False
    p, cp = decision("DEC-A", {"C1": "x"}, state="proposed")
    assert one(x, snap(x, p, bodies={"DEC-A": cp}))["satisfied"] is False


def test_dependency_on_a_replaced_clause_is_not_satisfied():
    a, ca = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b, cb = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
    )
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("DEC-A#C1", "accepted_and_in_force"))
    r = one(x, snap(x, a, b, bodies={"DEC-A": ca, "DEC-B": cb}))
    assert r["satisfied"] is False and "DEC-B#C1" in r["reason"]


def test_resolved_question():
    q = with_history("question", "open", "resolved", id="Q-B")
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("Q-B", "resolved"))
    assert one(x, snap(x, q))["satisfied"] is True
    q2 = with_history("question", "open", "discarded", id="Q-B")
    assert one(x, snap(x, q2))["satisfied"] is False


def test_source_without_checked_integrity_blocks():
    f = with_history("source", "registered", id="SRC-A")
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("SRC-A", "available_with_integrity"))
    r = one(x, snap(x, f))
    assert r["satisfied"] is False and r["code"] == "INTEGRITY_UNCHECKED"


def test_missing_target_or_condition_of_another_type():
    x = with_history(
        "milestone", "proposed", "authorized", id="MS-X", depends_on=dep("MS-NONE", "completed_with_evidence")
    )
    assert one(x, snap(x))["code"] == "MISSING_REFERENCE"
    q = with_history("question", "open", "resolved", id="Q-B")
    y = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("Q-B", "completed_with_evidence"))
    assert one(y, snap(y, q))["code"] == "INVALID_SCHEMA"


def test_ready_requires_own_authorization_and_dependencies():
    plan = with_history("plan", "proposed", id="PLAN-A", milestones=["MS-X", "MS-Z", "MS-W"])
    x = with_history("milestone", "proposed", "authorized", id="MS-X")  # proposed plan: does not block by association
    z = with_history("milestone", "proposed", id="MS-Z")  # no authorization of its own
    y = with_history("milestone", "proposed", "cancelled", id="MS-Y")
    w = with_history("milestone", "proposed", "authorized", id="MS-W", depends_on=dep("MS-Y", "completed_with_evidence"))
    res = ready(snap(plan, x, z, y, w), **C)
    assert [h["id"] for h in res["ready"]] == ["MS-X"]
    assert [h["id"] for h in res["blocked"]] == ["MS-W"]


def test_without_history_it_is_not_ready():
    x = record("milestone", state="authorized")
    res = ready(snap(x), **C)
    assert res["ready"] == [] and res["warnings"]


def test_in_force_at_cut_is_the_rule_of_dependencies():
    """Dependencies and support share the definition of what is in force."""
    a, ca = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b, cb = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        amends=[{"target": "DEC-A#C1", "operation": "repeals", "by": "DEC-B"}],
    )
    s = snap(a, b, bodies={"DEC-A": ca, "DEC-B": cb})
    res = in_force_at_cut(_Query(s, C["valid_at"], C["known_until"]), "DEC-A#C1")
    assert res["situation"] == "not_in_force" and res["origin"] == "DEC-B" and res["state"] == "accepted"
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("DEC-A#C1", "accepted_and_in_force"))
    r = one(x, snap(x, a, b, bodies={"DEC-A": ca, "DEC-B": cb}))
    assert r["satisfied"] is False and r["reason"] == res["reason"]


def test_fact_with_a_successor_of_ambiguous_time_does_not_satisfy():
    """Without deciding whether the successor already came into force, the fact is not taken as in force."""
    h = with_history("fact", "proposed", "accepted", id="FACT-A")
    successor = with_history("fact", "proposed", "accepted", id="FACT-B", supersedes=["FACT-A"])
    successor["events"][-1]["valid_from"] = C["valid_at"][:10]
    x = with_history("milestone", "proposed", "authorized", id="MS-X", depends_on=dep("FACT-A", "accepted_and_in_force"))
    r = one(x, snap(x, h, successor))
    assert r["satisfied"] is False and r["code"] == "AMBIGUOUS_TIME" and r["warnings"]
