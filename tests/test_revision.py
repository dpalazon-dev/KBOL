"""Regressions from the independent review of 3 Nov 2026 (HIGH, MEDIUM and LOW findings)."""

import re

import pytest
from conftest import BY_TYPE, DECISION_BODY, event, record

from kbol.core import FormatError, new_id, parse, serialize, write
from kbol.digest import digest
from kbol.events import in_force_at
from kbol.markdown import facts
from kbol.model import ID_UUID
from kbol.projection import Snapshot, project, project_status
from kbol.references import validate_snapshot
from kbol.schema import validate

T = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")


def creation(state, t="2026-11-01T00:00:00Z"):
    return event("creation", event_id="E0", previous_state=None, new_state=state, recorded_at=t, valid_from=t)


def ratification(t="2026-11-02T00:00:00Z"):
    appr = dict(
        approval_id="AP1",
        actor="human:david",
        identity_ref="github:1",
        roles=["ROLE-EXAMPLE"],
        digest="b" * 64,
        base_revision="r0",
        approved_at=t,
        policy_revision="r0",
        proof="review:1",
    )
    return event("ratification", event_id="E1", recorded_at=t, valid_from=t, approval=appr)


def acceptance(t="2026-11-02T00:00:00Z", valid=None, **extra):
    return event(
        event_id="E2",
        previous_state="proposed",
        new_state="accepted",
        recorded_at=t,
        valid_from=valid or t,
        **extra,
    )


def accepted(**changes):
    return record("decision", state="accepted", events=[creation("proposed"), ratification(), acceptance()], **changes)


@pytest.mark.parametrize(
    "field,value",
    [("description", "one line\n"), ("id", "Q-A\n"), ("author", "human:x\n"), ("owner", "ROLE-EXAMPLE\n")],
)
def test_patterns_do_not_admit_a_final_newline(field, value):
    assert validate(record("question", **{field: value}))


def test_instants_and_fingerprints_do_not_admit_a_final_newline():
    ev = creation("open")
    assert validate(record("question", events=[{**ev, "recorded_at": ev["recorded_at"] + "\n"}]))
    assert validate(record("source", sha256="a" * 64 + "\n"))


def test_canonical_requires_history_from_creation():
    assert validate(record("decision", state="accepted"), DECISION_BODY, mode="canonical")
    assert validate(record("decision", events=[ratification()]), DECISION_BODY, mode="canonical")
    assert validate(accepted(), DECISION_BODY, mode="canonical") == []


def test_accepting_a_decision_requires_a_previous_ratification():
    without = record("decision", state="accepted", events=[creation("proposed"), acceptance()])
    assert validate(without, DECISION_BODY, mode="canonical")


def test_new_proposal_is_in_the_initial_state():
    assert validate(record("decision", state="accepted"), DECISION_BODY)


def test_canonical_does_not_admit_local_events():
    local = {**creation("open"), "recorded_at": None}
    assert validate(record("question", events=[local]), mode="canonical")
    assert validate(record("question", events=[local])) == []


def test_serialize_canonical_requires_history():
    with pytest.raises(FormatError):
        serialize(record("decision", state="accepted"), DECISION_BODY, mode="canonical")
    assert serialize(accepted(), DECISION_BODY, mode="canonical")


def test_without_history_there_is_no_projection_nor_succession():
    a = accepted(id="DEC-A")
    b_without = record("decision", id="DEC-B", state="accepted", supersedes=["DEC-A"])
    snap = Snapshot({"DEC-A": a, "DEC-B": b_without}, revision="r1")
    assert project_status(a, snap, **T) == "stable"
    assert project_status(b_without, snap, **T) is None
    assert project(b_without, snap, **T)["warnings"]


def test_local_events_are_ignored_when_projecting():
    local = {**creation("open"), "recorded_at": None}
    r = record("question", events=[local])
    assert project_status(r, Snapshot({}, "r"), **T) is None


def test_day_ambiguity_does_not_break_the_projection():
    imp = event(
        "import",
        event_id="E0",
        previous_state=None,
        new_state="accepted",
        legacy_state="Accepted",
        provenance={"path": "docs/x.md", "revision": "r"},
        valid_from="2026-11-20",
        precision="day",
    )
    r = record("decision", state="accepted", events=[imp])
    p = project(r, Snapshot({}, "r"), **T)
    assert p["status"] == "draft" and any("AMBIGUOUS_TIME" in a for a in p["warnings"])


def test_day_ambiguity_depends_on_the_unknown_zone():
    with pytest.raises(ValueError, match="ambiguous"):
        in_force_at("2026-11-15", None, "2026-11-15T00:30:00+01:00")
    with pytest.raises(ValueError, match="ambiguous"):
        in_force_at("2026-11-15", None, "2026-11-14T23:30:00-05:00")
    assert in_force_at("2026-11-15", None, "2026-11-17T00:00:00Z") is True
    assert in_force_at("2026-11-15", None, "2026-11-13T00:00:00Z") is False


def test_integral_decimals_rejected_in_any_field():
    v = BY_TYPE["milestone"]["checks"][0]
    assert validate(record("milestone", checks=[{**v, "timeout": 600.0}]))
    assert validate(record("role", approval_rule={"quorum": 2.0}))


def test_inline_code_does_not_cross_paragraphs():
    body = 'Press ` to open.\n\n<fact id="H1" evidence="invented" source="nothing">5</fact>\n\nAnd ` again.'
    assert facts(body)
    assert validate(record("question"), body)


def test_digest_validates_effects():
    r = record("decision")
    with pytest.raises(ValueError):
        digest(r, DECISION_BODY, {"any": "thing"})
    effect = {"new_state": "accepted", "valid_from": "2026-11-01T00:00:00Z", "recorded_at": "x"}
    with pytest.raises(ValueError):
        digest(r, DECISION_BODY, [effect])


def test_non_specific_tag_rejected():
    with pytest.raises(FormatError):
        parse("---\na: ! 123\n---\n")


def test_yaml_1_1_from_text():
    meta, _ = parse("---\naliases: [no, yes]\n---\n")
    assert validate(record("entity", aliases=meta["aliases"]))


def test_ordered_intervals():
    fact = record("fact")
    del fact["date"]
    fact["interval"] = {"from": "2026-11-02", "until": "2026-11-01"}
    assert validate(fact)
    bad = acceptance(valid="2026-12-01T00:00:00Z", valid_until="2026-11-01T00:00:00Z")
    r = record("decision", state="accepted", events=[creation("proposed"), ratification(), bad])
    assert validate(r, DECISION_BODY)


def test_additional_references_and_anchor_coverage():
    role = record("role")
    syn = record("synthesis", dependencies=["DEC-NONE#C1"])
    snap = Snapshot({"ROLE-EXAMPLE": role, "SYN-A": syn}, "r")
    assert "MISSING_REFERENCE" in {h["code"] for h in validate_snapshot(snap)}
    source = record("question", sources=[{"id": "s1", "resource": "SRC-NONE"}])
    assert validate_snapshot(Snapshot({"ROLE-EXAMPLE": role, "Q-A": source}, "r"))
    dec = record("decision")
    q = record("question", challenges=["DEC-EXAMPLE#C99"])
    h = validate_snapshot(Snapshot({"ROLE-EXAMPLE": role, "DEC-EXAMPLE": dec, "Q-A": q}, "r"))
    assert [x["severity"] for x in h] == ["alert"]  # body not loaded: it could not be checked
    assert validate(record("question"), '<fact ref="ZZ-1">x</fact>')


def test_mutual_replacement_is_a_cycle():
    role = record("role")
    a = record("decision", id="DEC-A", amends=[{"target": "DEC-B#C1", "operation": "replaces", "by": "DEC-A#C1"}])
    b = record("decision", id="DEC-B", amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}])
    bodies = {"DEC-A": DECISION_BODY, "DEC-B": DECISION_BODY}
    snap = Snapshot({"ROLE-EXAMPLE": role, "DEC-A": a, "DEC-B": b}, "r", bodies)
    assert "NORMATIVE_CONFLICT" in {h["code"] for h in validate_snapshot(snap)}


def test_new_id_and_atomic_write(tmp_path):
    ident = new_id("decision")
    assert re.fullmatch(ID_UUID, ident)
    f = tmp_path / "d.md"
    write(f, record("decision", id=ident), DECISION_BODY.replace("DEC-EXAMPLE", ident))
    meta, body = parse(f.read_text(encoding="utf-8"))
    assert meta["id"] == ident and body == DECISION_BODY
    assert list(tmp_path.iterdir()) == [f]
    with pytest.raises(FormatError):
        write(tmp_path / "e.md", record("decision", extra=1), DECISION_BODY)
    assert list(tmp_path.iterdir()) == [f]
