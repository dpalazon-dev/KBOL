"""State materialized from events and total projection of `status` (VAL-08)."""

import pytest
from conftest import DECISION_BODY, event, record

from kbol.events import HistoryError, state_at
from kbol.projection import Snapshot, project_status
from kbol.schema import validate


def creation(state, t="2026-11-01T00:00:00Z", eid="E0"):
    return event("creation", event_id=eid, previous_state=None, new_state=state, recorded_at=t, valid_from=t)


def step(a, b, t, valid=None, eid="E1"):
    return event(previous_state=a, new_state=b, recorded_at=t, valid_from=valid or t, event_id=eid)


def test_state_rebuilt_at_the_knowledge_cut():
    ev = [creation("proposed"), step("proposed", "accepted", "2026-11-10T09:00:00Z", "2026-11-15T00:00:00Z")]
    assert state_at(ev, "2026-11-05T00:00:00Z") == "proposed"
    assert state_at(ev, "2026-11-10T09:00:00Z") == "accepted"
    assert state_at(ev, "2026-10-01T00:00:00Z") is None


def test_incoherent_history_is_rejected():
    with pytest.raises(HistoryError):
        state_at([step("proposed", "accepted", "2026-11-02T00:00:00Z")], None)  # no creation
    with pytest.raises(HistoryError):
        state_at([creation("proposed"), step("rejected", "accepted", "2026-11-02T00:00:00Z")], None)
    with pytest.raises(HistoryError):  # recorded out of order
        state_at(
            [creation("proposed", "2026-11-05T00:00:00Z"), step("proposed", "accepted", "2026-11-02T00:00:00Z")], None
        )


def test_written_state_must_match_the_history():
    ev = [creation("proposed")]
    assert validate(record("decision", state="accepted", events=ev), DECISION_BODY, mode="canonical")
    assert validate(record("decision", state="proposed", events=ev), DECISION_BODY, mode="canonical") == []


def test_reopening_without_policy_rejected():
    ev = [
        creation("open"),
        step("open", "resolved", "2026-11-02T00:00:00Z"),
        step("resolved", "open", "2026-11-03T00:00:00Z", eid="E2"),
    ]
    assert validate(record("question", state="open", events=ev), mode="canonical")


def _snap(*records):
    return Snapshot({r["id"]: r for r in records}, revision="r1")


def test_projection_rules_in_order():
    T = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")
    accepted = record(
        "decision",
        state="accepted",
        events=[creation("proposed"), step("proposed", "accepted", "2026-11-02T00:00:00Z")],
    )
    assert project_status(accepted, _snap(accepted), **T) == "stable"
    assert project_status({**accepted, "class": "archive"}, _snap(accepted), **T) == "deprecated"
    future = record(
        "decision",
        state="accepted",
        events=[creation("proposed"), step("proposed", "accepted", "2026-11-02T00:00:00Z", "2026-12-01T00:00:00Z")],
    )
    assert project_status(future, _snap(future), **T) == "draft"
    expired = record(
        "decision",
        state="accepted",
        events=[
            creation("proposed"),
            {**step("proposed", "accepted", "2026-11-02T00:00:00Z"), "valid_until": "2026-11-10T00:00:00Z"},
        ],
    )
    assert project_status(expired, _snap(expired), **T) == "stable"  # expired is not future (rule 3)

    def with_history(type_, *states):
        ev = [creation(states[0])]
        for i, (a, b) in enumerate(zip(states, states[1:]), start=1):
            ev.append(step(a, b, f"2026-11-0{i + 1}T00:00:00Z", eid=f"E{i}"))
        return record(type_, state=states[-1], events=ev)

    cases = [
        (with_history("question", "open"), "stable"),  # open is stable as a record
        (with_history("hypothesis", "open"), "draft"),
        (with_history("assumption", "active"), "draft"),
        (with_history("hypothesis", "open", "refuted"), "deprecated"),
        (with_history("role", "proposed", "active"), "stable"),
        (with_history("milestone", "proposed", "cancelled"), "deprecated"),
        (with_history("synthesis", "draft", "current"), "stable"),
    ]
    for r, expected in cases:
        assert project_status(r, _snap(r), **T) == expected, (r["type"], r["state"])


def test_complete_succession_in_force_deprecates():
    T = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")
    a = record(
        "decision",
        id="DEC-A",
        state="accepted",
        events=[creation("proposed"), step("proposed", "accepted", "2026-11-01T00:00:00Z")],
    )
    b = record(
        "decision",
        id="DEC-B",
        state="accepted",
        supersedes=["DEC-A"],
        events=[creation("proposed"), step("proposed", "accepted", "2026-11-02T00:00:00Z")],
    )
    assert project_status(a, _snap(a, b), **T) == "deprecated"
    # A successor that is only proposed does not deprecate.
    bp = {**b, "state": "proposed", "events": [creation("proposed")]}
    assert project_status(a, _snap(a, bp), **T) == "stable"
    # An accepted but future successor does not either.
    bf = {
        **b,
        "events": [
            creation("proposed"),
            step("proposed", "accepted", "2026-11-02T00:00:00Z", "2026-12-01T00:00:00Z"),
        ],
    }
    assert project_status(a, _snap(a, bf), **T) == "stable"
    # Knowledge before the successor was incorporated.
    assert (
        project_status(a, _snap(a, b), valid_at="2026-11-20T00:00:00Z", known_until="2026-11-01T12:00:00Z")
        == "stable"
    )


def test_projection_requires_explicit_cuts():
    with pytest.raises(TypeError):
        project_status(record("question"), _snap())
