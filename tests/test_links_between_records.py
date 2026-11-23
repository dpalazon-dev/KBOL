"""Work links and fields, and what is assigned to a person.

A milestone closes, advances, tests a hypothesis and produces; a plan relies on decisions; milestones and questions
have an owner and evidence; a decision, its implementation. They are free: changing them does not reopen a closure nor
an authorization. `impact` follows them and `query` shows them, along with what a person has assigned.
"""

import copy

from conftest import decision, record
from test_integrate import active

from kbol.impact import impact
from kbol.importing import check
from kbol.mutability import compare
from kbol.projection import Snapshot
from kbol.query import assigned, query
from kbol.references import validate_snapshot
from kbol.schema import validate


def snap(pairs, revision="r"):
    return Snapshot({r["id"]: r for r, _ in pairs}, revision, {r["id"]: c for r, c in pairs})


def errors(findings):
    return [h for h in findings if h["severity"] == "error"]


def milestone(**fields):
    return record("milestone", **{"id": "MS-A", **fields})


def test_a_milestone_with_its_links_and_work_fields_is_valid():
    r = milestone(
        closes=["Q-A"],
        advances=["Q-B"],
        tests_hypothesis=["HYP-A"],
        produces=["DEC-EXAMPLE", "DEC-EXAMPLE#C1"],
        owner="PER-A",
        evidence=["tests/test_x.py", "commit abc123"],
    )
    assert errors(validate(r, "")) == []
    assert errors(validate(record("plan", relies_on=["DEC-EXAMPLE#C1"]), "")) == []
    assert errors(validate(record("question", evidence=["pytest output"]), "")) == []
    d = record("decision", implementation="partial")
    assert errors(validate(d, '<clause id="C1">\nx\n</clause>\n')) == []


def test_links_require_their_target_type_and_their_origin():
    assert errors(validate(milestone(closes=["DEC-EXAMPLE"]), ""))
    assert errors(validate(milestone(tests_hypothesis=["Q-A"]), ""))
    assert errors(validate(milestone(closes=["Q-A#C1"]), ""))
    assert errors(validate(record("decision", closes=["Q-A"]), '<clause id="C1">\nx\n</clause>\n'))
    assert errors(validate(record("decision", implementation="almost"), '<clause id="C1">\nx\n</clause>\n'))


def test_a_link_to_a_record_that_does_not_exist_is_a_reference_error():
    s = snap([(milestone(closes=["Q-NO"], owner="ROLE-NO"), "")])
    paths = {h["path"] for h in errors(validate_snapshot(s))}
    assert "MS-A/closes" in paths and "MS-A/owner" in paths


def test_changing_links_does_not_reopen_a_completed_milestone_nor_an_authorized_plan():
    completed = milestone(state="completed", closes=["Q-A"])
    plan = record("plan", state="authorized", relies_on=["DEC-EXAMPLE"])
    base = snap([(completed, ""), (plan, "")])
    prop = copy.deepcopy(base)
    prop.records["MS-A"].update(closes=["Q-A", "Q-B"], produces=["DEC-EXAMPLE"], evidence=["commit 1"])
    prop.records["MS-A"]["owner"] = "PER-A"
    prop.records["PLAN-A"]["relies_on"] = ["DEC-EXAMPLE", "DEC-OTHER"]
    assert errors(compare(base, Snapshot(prop.records, "p", prop.bodies))["findings"]) == []
    prop.records["MS-A"]["goal"] = "Other"
    assert errors(compare(base, Snapshot(prop.records, "p", prop.bodies))["findings"])


def test_impact_follows_the_work_links():
    a = decision("DEC-A", {"C1": "Monday."})
    q = (record("question", id="Q-A"), "")
    h = (milestone(closes=["Q-A"], owner="PER-A"), "")
    p = (record("plan", id="PLAN-A", relies_on=["DEC-A#C1"]), "")
    base = snap([a, q, h, p], "b")
    change = copy.deepcopy(q[0])
    change["title"] = "Other"
    res = impact(base, snap([a, (change, ""), h, p], "f"))
    affected = {x["affected"]: x for x in res["affected"]}
    assert set(affected) == {"MS-A"} and affected["MS-A"]["owner"] == ["PER-A"]
    new = decision(
        "DEC-B", {"C1": "Tuesday."}, amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}]
    )
    res = impact(base, snap([a, q, h, p, new], "f"))
    assert "PLAN-A" in {x["affected"] for x in res["affected"]}


def _team():
    role = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    david = active(
        "person",
        "PER-D",
        nature="human",
        identity_ref="declared:d",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    other = active("person", "PER-J", nature="human", identity_ref="declared:j", holds=[])
    return [
        (role, ""),
        (david, ""),
        (other, ""),
        (milestone(id="MS-1", owner="PER-D"), ""),
        (milestone(id="MS-2", owner="ROLE-OP", state="completed"), ""),
        (milestone(id="MS-3", owner="PER-J"), ""),
        (record("question", id="Q-1", owner="ROLE-OP"), ""),
    ]


def test_what_is_assigned_to_a_person_includes_their_roles_and_says_whether_it_is_still_open():
    s = snap(_team())
    items = {x["id"]: x for x in assigned(s, "PER-D")}
    assert set(items) == {"MS-1", "MS-2", "Q-1"}
    assert items["MS-2"]["via"] == "ROLE-OP" and items["MS-2"]["open"] is False
    assert items["MS-1"]["open"] is True
    assert [x["id"] for x in assigned(s, "PER-J")] == ["MS-3"]


def test_querying_a_person_brings_what_is_assigned_and_a_milestone_its_work_fields():
    s = Snapshot(*_full_snap())
    res = query(s, ["PER-D", "MS-1"], valid_at=None, known_until=None)["results"]
    assert {x["id"] for x in res[0]["assigned"]} == {"MS-1", "MS-2", "Q-1"}
    assert res[1]["work"] == {"owner": "PER-D"}


def _full_snap():
    pairs = _team()
    return (
        {r["id"]: r for r, _ in pairs},
        "r",
        {r["id"]: c for r, c in pairs},
        {r["id"]: f"kb/{r['id']}.md" for r, _ in pairs},
    )


LEGACY = """---
type: Decision
title: T
description: D
---
Chosen option: **Option A**, because it aligns audience with visibility: what
an external reviewer sees is in `docs/`.
"""


def test_the_guard_tolerates_whitespace_but_not_a_new_word():
    r = {"id": "ADR-0003", "title": "T", "description": "D"}
    reflow = (
        '<clause id="C1">\n\nChosen option: **Option A**, because it aligns audience with visibility:\n'
        "what an external reviewer sees is in `docs/`.\n\n</clause>\n"
    )
    assert check(r, reflow, LEGACY, "docs/decisions/0003.md") == []
    changed = reflow.replace("external", "internal")
    assert check(r, changed, LEGACY, "docs/decisions/0003.md")
