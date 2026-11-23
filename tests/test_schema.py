"""VAL-01: common schema, per type, nested and per event class."""

import pytest
from conftest import BY_TYPE, DECISION_BODY, T0, event, record

from kbol.schema import validate


def codes(findings):
    return {h["code"] for h in findings}


def paths(findings):
    return {h["path"] for h in findings}


@pytest.mark.parametrize("type_", sorted(BY_TYPE))
def test_minimal_record_valid_per_type(type_):
    body = DECISION_BODY if type_ == "decision" else ""
    assert validate(record(type_), body) == []


def test_contract_example_validates_as_proposal():
    # "Complete example of a decision proposal", KB-DPP core 1.0.
    r = record("decision", title="Report delivery schedule")
    body = '<clause id="C1">\nThe report is delivered on Tuesdays.\n</clause>\n\n<clause id="C2">\nThe report only includes verified data.\n</clause>\n'
    assert validate(r, body) == []


@pytest.mark.parametrize(
    "field", ["id", "type", "class", "title", "description", "scope", "state", "author", "events", "sources"]
)
def test_common_fields_required(field):
    r = record("question")
    del r[field]
    assert "INVALID_SCHEMA" in codes(validate(r))


@pytest.mark.parametrize(
    "change",
    [
        {"description": "two\nlines"},
        {"class": "other"},
        {"state": "accepted"},  # not a question state
        {"author": "David"},  # actor without the shape human:/process:/producer/version
        {"sources": [{"id": "s1"}]},
        {"sources": [{"id": "s1", "resource": "SRC-A", "extra": 1}]},
        {"sources": [{"id": "s1", "resource": "SRC-A"}, {"id": "s1", "resource": "SRC-B"}]},
        {"sources": [{"id": "s1", "resource": "SRC-A", "hash": "short"}]},
        {"owner": ["ROLE-A"]},
        {"subtype": "other"},
        {"deadline": "tomorrow"},
        {"id": "DEC-A"},  # prefix of another type
        {"id": "no-prefix"},
    ],
)
def test_wrong_values_rejected(change):
    assert validate(record("question", **change))


def test_unknown_field_blocks_in_canonical_and_alerts_in_exchange():
    r = record("question", extra="x")
    assert codes(validate(r, mode="canonical")) == {"INVALID_SCHEMA"}
    alerts = validate(r, mode="exchange")
    assert alerts and all(h["severity"] == "alert" for h in alerts)


def test_field_of_another_type_is_unknown():
    # resolved_by only leaves a question; amends, a decision.
    assert validate(record("fact", resolved_by=["DEC-A"]))
    assert validate(record("question", amends=[]))


def test_yaml_1_1_does_not_sneak_booleans_as_text():
    # "no" read by PyYAML is False: the schema rejects it instead of accepting it as an alias.
    assert validate(record("entity", aliases=[False]))


def test_exact_integers_and_no_decimals():
    v = BY_TYPE["milestone"]["checks"][0]
    assert validate(record("milestone", checks=[{**v, "timeout": 1.5}]))
    assert validate(record("milestone", checks=[{**v, "timeout": True}]))


def test_original_and_derived_source():
    assert validate(record("source", sha256="A" * 64))
    assert validate(record("source", subtype="derived"))
    derived = record(
        "source",
        id="SRC-AR",
        subtype="derived",
        derived_from=["SRC-A"],
        processor="docling",
        processor_version="2.1.0",
        configuration_ref="profile:tables",
        processed_at="2026-11-02T10:00:00+01:00",
        processing="partial",
        quality={
            "tables": {"method": "sample", "result": "partial", "limits": "column 3"},
            "figures": "not_evaluated",
        },
    )
    del derived["origin"]
    assert validate(derived) == []
    assert validate({**derived, "processing": "finished"})
    assert validate({**derived, "quality": {"tables": {"result": 0}}})


def test_decision_without_alternatives_requires_reason_and_selection():
    assert validate(record("decision", alternatives=[]), DECISION_BODY)
    assert (
        validate(record("decision", alternatives=[], no_alternatives_reason="Proven correction"), DECISION_BODY)
        == []
    )
    alts = [dict(a, selected=False) for a in BY_TYPE["decision"]["alternatives"]]
    assert validate(record("decision", alternatives=alts), DECISION_BODY)
    assert validate(record("decision", authorized_by=[]), DECISION_BODY)


def test_canonical_decision_needs_clauses_and_well_formed_body():
    assert validate(record("decision"), "free text", mode="canonical")
    assert validate(record("decision"), '<clause id="C1">\nopen', mode="exchange")


def test_typed_relations():
    r = record("decision")
    ok = [{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-EXAMPLE#C1"}]
    assert validate({**r, "amends": ok}, DECISION_BODY) == []
    for bad in (
        [{"target": "DEC-A#C1", "operation": "replaces"}],
        [{"target": "DEC-A#C1", "operation": "repeals", "by": "DEC-EXAMPLE#C1"}],
        [{"target": "DEC-A", "operation": "replaces", "by": "DEC-EXAMPLE#C1"}],  # replaces requires an anchor
        [{"target": "DEC-A#C1", "operation": "other", "by": "DEC-EXAMPLE#C1"}],
    ):
        assert validate({**r, "amends": bad}, DECISION_BODY), bad
    assert (
        validate(
            {
                **r,
                "amends": [
                    {"target": "DEC-A", "operation": "adds", "by": "DEC-EXAMPLE#C1", "position": "after DEC-A#C2"}
                ],
            },
            DECISION_BODY,
        )
        == []
    )
    assert validate(record("milestone", depends_on=[{"target": "MS-B", "condition": "completed_with_evidence"}])) == []
    assert validate(record("milestone", depends_on=[{"target": "MS-B", "condition": "exists"}]))
    assert validate(record("milestone", depends_on=["MS-B"]))
    assert validate(record("question", challenges=["DEC-A"]))  # challenges points to a clause
    assert validate(record("question", challenges=["DEC-A#C1"])) == []
    assert validate(record("question", resolved_by=["Q-B"]))  # a decision resolves it
    assert (
        validate(
            record(
                "decision",
                vetoes=[{"pattern": "tenant", "scope": "product", "use": "operational content", "exclusions": []}],
            ),
            DECISION_BODY,
        )
        == []
    )


def test_role_approval_rule():
    for ok in ("one", "all", {"quorum": 2}):
        assert validate(record("role", approval_rule=ok)) == []
    for bad in ("majority", {"quorum": 0}, {"quorum": "2"}):
        assert validate(record("role", approval_rule=bad))


def test_milestone_acceptance_and_checks():
    k = BY_TYPE["milestone"]["acceptance"][0]
    v = BY_TYPE["milestone"]["checks"][0]
    assert validate(record("milestone", checks=[{**v, "criterion_id": "K9"}]))  # nonexistent criterion
    assert validate(record("milestone", acceptance=[{**k, "method": "ai_assisted_evaluation"}]))  # no rubric
    ai = {**k, "method": "ai_assisted_evaluation", "rubric": "R", "disagreement_resolution": "David decides"}
    assert validate(record("milestone", acceptance=[ai])) == []
    assert validate(record("milestone", tolerances={"speed": "high"}))


def test_events_per_class():
    t = event(previous_state=None, new_state="open", event_type="creation")
    assert validate(record("question", events=[t])) == []
    assert validate(record("question", events=[{**t, "extra": 1}]))
    assert validate(record("question", events=[{**t, "recorded_at": "nonsense"}]))
    assert validate(record("question", events=[{**t, "recorded_at": "2026-11-03T10:00:00"}]))  # no zone
    assert validate(record("question", events=[{**t, "event_evidence": "text"}]))
    appr = dict(
        approval_id="AP1",
        actor="human:david",
        identity_ref="github:1",
        roles=["ROLE-EXAMPLE"],
        digest="b" * 64,
        base_revision="23fef059",
        approved_at=T0,
        policy_revision="23fef059",
        proof={"mechanism": "github-review", "id": "1"},
    )
    rat = event("ratification", event_id="E2", approval=appr)
    assert validate(record("decision", events=[rat]), DECISION_BODY) == []
    assert validate(record("decision", events=[{**rat, "approval": {**appr, "digest": "x"}}]), DECISION_BODY)


def test_events_with_repeated_id():
    t = event("creation", previous_state=None, new_state="open")
    assert validate(record("question", events=[t, t]))


def test_fact_requires_date_or_interval_with_precision():
    r = record("fact")
    del r["date"]
    assert validate(r)
    assert validate({**r, "interval": {"from": "2026-10-01"}, "precision": "day"}) == []
    assert validate({**r, "date": "2026-10-30", "precision": "seconds"})


def test_fact_markup_in_body_validated():
    r = record("decision", sources=[{"id": "s1", "resource": "SRC-A"}])
    body = DECISION_BODY + '\n<fact id="H1" evidence="declared" source="s1">Flow 5 m3/h</fact>\n'
    assert validate(r, body) == []
    assert validate(r, body.replace('source="s1"', 'source="s9"'))
    assert validate(r, body.replace("declared", "certain"))
