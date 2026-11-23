"""Query by ID: what a memory or a note needs to link itself to canonical knowledge."""

import json
import subprocess
import sys

from conftest import decision, record
from test_integrate import active

from kbol.core import serialize
from kbol.projection import Snapshot
from kbol.query import query

T = "2026-11-06T00:00:00Z"


def snap():
    a, ca = decision("DEC-A", {"C1": "Monday.", "C2": "Tuesday."}, authorized_by=["ROLE-EXAMPLE"])
    b, cb = decision(
        "DEC-B",
        {"C1": "Wednesday."},
        recorded="2026-11-03T00:00:00Z",
        authorized_by=["ROLE-EXAMPLE"],
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
    )
    inherited = {"id": "ADR-0001", "type": "decision", "path": "docs/0001.md", "legacy_state": "Accepted"}
    inherited["proposed_state"] = "accepted"
    return Snapshot(
        {"DEC-A": a, "DEC-B": b},
        "r1",
        {"DEC-A": ca, "DEC-B": cb},
        {"DEC-A": "kb/DEC-A.md", "DEC-B": "kb/DEC-B.md"},
        {"ADR-0001": inherited},
    )


def one(ref):
    return query(snap(), [ref], valid_at=T, known_until=None)["results"][0]


def test_a_canonical_id_returns_type_state_and_unchecked_authority():
    r = one("DEC-A")
    assert r["found"] == "canonical" and r["type"] == "decision" and r["state"] == "accepted"
    assert r["path"] == "kb/DEC-A.md" and r["authority"]["checked"] is False
    assert r["authority"]["ratifications"] == ["AP-DEC-A"]


def test_an_anchor_returns_its_text_and_whether_it_is_in_force():
    current, superseded = one("DEC-A#C2"), one("DEC-A#C1")
    assert current["text"] == "Tuesday." and current["clause"]["state"] == "current"
    assert superseded["text"] == "Monday."
    assert superseded["clause"]["text"] == "Wednesday." and superseded["clause"]["origin"] == "DEC-B#C1"


def test_an_anchor_that_does_not_exist_is_reported():
    assert one("DEC-A#C9")["found"] == "missing_anchor"


def test_a_legacy_id_is_named_and_not_in_force():
    r = one("ADR-0001")
    assert r["found"] == "legacy" and r["in_force"] is False and r["legacy_state"] == "Accepted"


def test_a_missing_id_is_reported_with_a_warning():
    output = query(snap(), ["DEC-Z"], valid_at=T, known_until=None)
    assert output["results"][0]["found"] == "missing"
    assert any("DEC-Z" in a for a in output["warnings"])


def test_a_citation_of_a_missing_source_is_insufficient_evidence():
    s = snap()
    q = record("question", id="Q-A", based_on=["SRC-NO"])
    s.records["Q-A"], s.bodies["Q-A"] = q, "Text."
    output = query(s, ["Q-A"], valid_at=T, known_until=None)
    evidence = output["results"][0]["evidence"]
    assert [(a["ref"], a["field"], a["exists"], a["situation"]) for a in evidence["supports"]] == [
        ("SRC-NO", "based_on", False, "missing")
    ]
    assert evidence["sufficient"] is False and "SRC-NO missing" in evidence["reason"]
    assert any("INSUFFICIENT_EVIDENCE" in a and "SRC-NO" in a for a in output["warnings"])


def test_the_cli_queries_by_id(tmp_path):
    a, ca = decision("DEC-A", {"C1": "Monday."}, authorized_by=["ROLE-EXAMPLE"])
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "DEC-A.md").write_text(serialize(a, ca, mode="canonical"), encoding="utf-8", newline="\n")
    role = active("role", "ROLE-EXAMPLE", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    (tmp_path / "kb" / "ROLE-EXAMPLE.md").write_text(
        serialize(role, "", mode="canonical"), encoding="utf-8", newline="\n"
    )
    output = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "query", str(tmp_path), "--folder", "kb", "--ids", "DEC-A#C1"]
        + ["--valid-at", T],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data = json.loads(output.stdout)
    assert output.returncode == 0, output.stdout + output.stderr
    assert data["result"]["results"][0]["text"] == "Monday."
    without_clock = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "query", str(tmp_path), "--folder", "kb", "--ids", "DEC-A"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert without_clock.returncode == 2


def test_a_citation_of_a_fact_that_exists_but_is_not_in_force_is_insufficient_evidence():
    """Existing is not enough; the support has to be in force at the cut."""
    s = snap()
    s.records["FACT-A"], s.bodies["FACT-A"] = record("fact", id="FACT-A"), ""  # exists, without admitted history
    q = record("question", id="Q-A")
    s.records["Q-A"], s.bodies["Q-A"] = q, 'The <fact ref="FACT-A">flow</fact> is measured.'
    output = query(s, ["Q-A"], valid_at=T, known_until=None)
    evidence = output["results"][0]["evidence"]
    (support_,) = evidence["supports"]
    assert (support_["field"], support_["exists"], support_["situation"]) == ("body", True, "not_in_force")
    assert evidence["sufficient"] is False and "FACT-A not_in_force" in evidence["reason"]
    assert any("INSUFFICIENT_EVIDENCE" in a and "FACT-A" in a for a in output["warnings"])


def test_a_citation_of_a_clause_in_force_is_sufficient_evidence():
    s = snap()
    s.records["Q-A"], s.bodies["Q-A"] = record("question", id="Q-A", based_on=["DEC-A#C2"]), ""
    evidence = query(s, ["Q-A"], valid_at=T, known_until=None)["results"][0]["evidence"]
    assert evidence["sufficient"] is True and evidence["supports"][0]["situation"] == "in_force"


def test_the_authority_says_who_approved_when_and_in_which_words():
    # Bench baseline, P05 and P06: the record keeps the approval, but the query only gave its ID.
    a, ca = decision("DEC-A", {"C1": "Monday."}, authorized_by=["ROLE-EXAMPLE"])
    a["events"][1]["approval"]["proof"] = {
        "mechanism": "declared",
        "session": "test session",
        "instant": "2026-11-01T00:00:00Z",
        "quote": "I approve",
        "authenticated": False,
    }
    s = Snapshot({"DEC-A": a}, "r1", {"DEC-A": ca}, {"DEC-A": "kb/DEC-A.md"}, {})
    r = query(s, ["DEC-A"], valid_at=T, known_until=None)["results"][0]
    assert r["authority"]["approvals"] == [
        {
            "approval_id": "AP-DEC-A",
            "actor": "human:david",
            "roles": ["ROLE-EXAMPLE"],
            "approved_at": a["events"][1]["approval"]["approved_at"],
            "mechanism": "declared",
            "quote": "I approve",
            "authenticated": False,
        }
    ]
    assert r["authority"]["checked"] is False


def test_an_approval_with_a_proof_without_detail_does_not_invent_a_quote():
    r = one("DEC-A")
    (approval,) = r["authority"]["approvals"]
    assert approval["actor"] == "human:david" and approval["quote"] is None and approval["authenticated"] is None
