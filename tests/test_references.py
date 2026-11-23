"""VAL-02 and VAL-07 over a snapshot: identity, references, target types and cycles."""

from conftest import DECISION_BODY, record

from kbol.projection import Snapshot
from kbol.references import validate_snapshot


def snap(*records, bodies=None):
    return Snapshot({r["id"]: r for r in records}, revision="r1", bodies=bodies or {})


def codes(h):
    return sorted(x["code"] for x in h)


def test_coherent_snapshot_without_findings():
    role = record("role")
    dec = record("decision")
    assert validate_snapshot(snap(role, dec, bodies={"DEC-EXAMPLE": DECISION_BODY})) == []


def test_missing_reference_and_target_type():
    dec = record("decision", authorized_by=["ROLE-NOBODY"])
    assert codes(validate_snapshot(snap(dec, bodies={"DEC-EXAMPLE": DECISION_BODY}))) == ["MISSING_REFERENCE"]
    q = record("question", resolved_by=["DEC-EXAMPLE"])
    hyp = record("hypothesis", id="HYP-B", state="open")
    role = record("role")
    dec = record("decision")
    assert validate_snapshot(snap(q, role, dec, hyp, bodies={"DEC-EXAMPLE": DECISION_BODY})) == []
    bad = record("question", resolved_by=["HYP-B"])
    assert "INVALID_SCHEMA" in codes(validate_snapshot(snap(bad, hyp)))


def test_anchor_of_nonexistent_clause():
    role = record("role")
    dec = record("decision")
    q = record("question", challenges=["DEC-EXAMPLE#C9"])
    assert codes(validate_snapshot(snap(role, dec, q, bodies={"DEC-EXAMPLE": DECISION_BODY}))) == [
        "MISSING_REFERENCE"
    ]


def test_forbidden_cycles_and_allowed_context_cycles():
    role = record("role")
    a = record("milestone", id="MS-A", depends_on=[{"target": "MS-B", "condition": "completed_with_evidence"}])
    b = record("milestone", id="MS-B", depends_on=[{"target": "MS-A", "condition": "completed_with_evidence"}])
    assert "NORMATIVE_CONFLICT" in codes(validate_snapshot(snap(role, a, b)))
    # A question resolved by a decision that affects it is a legitimate context cycle.
    q = record("question", resolved_by=["DEC-EXAMPLE"])
    dec = record("decision", affects=["Q-A"])
    assert validate_snapshot(snap(role, q, dec, bodies={"DEC-EXAMPLE": DECISION_BODY})) == []


def test_cyclic_succession_rejected():
    role = record("role")
    a = record("decision", id="DEC-A", supersedes=["DEC-B"])
    b = record("decision", id="DEC-B", supersedes=["DEC-A"])
    bodies = {"DEC-A": DECISION_BODY, "DEC-B": DECISION_BODY}
    assert "NORMATIVE_CONFLICT" in codes(validate_snapshot(snap(role, a, b, bodies=bodies)))


def test_supersedes_requires_same_type():
    role = record("role")
    dec = record("decision", supersedes=["Q-A"])
    q = record("question")
    assert "INVALID_SCHEMA" in codes(validate_snapshot(snap(role, dec, q, bodies={"DEC-EXAMPLE": DECISION_BODY})))
