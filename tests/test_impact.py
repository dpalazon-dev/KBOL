"""VAL-09 and RES-05: a change identifies its consumers, with cause, path and owner."""

import copy

from conftest import decision, record

from kbol.impact import impact
from kbol.projection import Snapshot


def snap(pairs, revision):
    return Snapshot({r["id"]: r for r, _ in pairs}, revision, {r["id"]: c for r, c in pairs})


def by_affected(res):
    return {a["affected"]: a for a in res["affected"]}


def base():
    a = decision("DEC-A", {"C1": "Monday.", "C2": "Checked."})
    h = (record("milestone", id="MS-H", depends_on=[{"target": "DEC-A#C1", "condition": "accepted_and_in_force"}]), "")
    h2 = (record("milestone", id="MS-H2", depends_on=[{"target": "MS-H", "condition": "completed_with_evidence"}]), "")
    s = (record("synthesis", id="SYN-S", dependencies=["DEC-A#C1"]), "")
    q = (record("question", id="Q-Q", challenges=["DEC-A#C2"]), "")
    other = (record("milestone", id="MS-OTHER"), "")
    return [a, h, h2, s, q, other]


def test_amending_a_clause_reaches_its_consumers_and_follows_the_path():
    b = snap(base(), "b")
    new = decision(
        "DEC-B", {"C1": "Tuesday."}, amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}]
    )
    p = snap(base() + [new], "p")
    res = impact(b, p)
    af = by_affected(res)
    assert set(af) == {"MS-H", "MS-H2", "SYN-S"}
    assert af["MS-H"]["path"] == ["DEC-B", "DEC-A#C1", "MS-H"]
    assert af["MS-H2"]["path"] == ["DEC-B", "DEC-A#C1", "MS-H", "MS-H2"]
    assert af["SYN-S"]["outdated"] is True and af["MS-H"]["outdated"] is False
    assert af["MS-H"]["owner"] == ["ROLE-EXAMPLE"] and af["MS-H"]["resolution"] == "pending"
    assert res["changed"] == ["DEC-B"]


def test_without_declared_edges_no_impact_is_invented():
    b = snap(base(), "b")
    p = copy.deepcopy(b)
    p.records["MS-OTHER"]["title"] = "Another title"
    res = impact(b, Snapshot(p.records, "p", p.bodies))
    assert res["changed"] == ["MS-OTHER"] and res["affected"] == []


def test_new_version_of_a_source_flags_whoever_cites_the_previous_one():
    fa = record("source", id="SRC-A")
    he = record("fact", id="FACT-A", based_on=["SRC-A"], sources=[{"id": "s1", "resource": "SRC-A"}])
    b = snap([(fa, ""), (he, "")], "b")
    fb = record("source", id="SRC-B", sha256="c" * 64, supersedes=["SRC-A"])
    p = snap([(fa, ""), (he, ""), (fb, "")], "p")
    af = by_affected(impact(b, p))
    assert set(af) == {"FACT-A"} and af["FACT-A"]["path"] == ["SRC-B", "SRC-A", "FACT-A"]


def test_superseding_the_whole_decision_and_affects():
    b = snap(base(), "b")
    new = decision("DEC-B", {"C1": "M."}, supersedes=["DEC-A"], affects=["MS-OTHER"])
    af = by_affected(impact(b, snap(base() + [new], "p")))
    assert {"MS-H", "MS-H2", "SYN-S", "Q-Q", "MS-OTHER"} <= set(af)
    assert af["MS-OTHER"]["path"] == ["DEC-B", "MS-OTHER"]


def test_changed_role_and_fact_cited_in_the_body():
    role = record("role", id="ROLE-EXAMPLE")
    dec = record("decision", id="DEC-A")  # authorized_by ROLE-EXAMPLE
    per = record("person", id="PER-A")  # holds ROLE-EXAMPLE
    he = record("fact", id="FACT-A")
    q = record("question", id="Q-Z")
    pairs = [(role, ""), (dec, ""), (per, ""), (he, ""), (q, 'See <fact ref="FACT-A">the measurement</fact>.')]
    b = snap(pairs, "b")
    p = copy.deepcopy(b)
    p.records["ROLE-EXAMPLE"]["capabilities"] = ["ratify", "other"]
    p.records["FACT-A"]["claim"] = "Another"
    af = by_affected(impact(b, Snapshot(p.records, "p", p.bodies)))
    assert {"DEC-A", "PER-A", "Q-Z"} <= set(af)
    assert af["Q-Z"]["path"] == ["FACT-A", "Q-Z"]


def test_consumption_cycles_do_not_hang():
    x = record("milestone", id="MS-X", depends_on=[{"target": "MS-Y", "condition": "completed_with_evidence"}])
    y = record("milestone", id="MS-Y", depends_on=[{"target": "MS-X", "condition": "completed_with_evidence"}])
    b = snap([(x, ""), (y, "")], "b")
    p = copy.deepcopy(b)
    p.records["MS-X"]["work_scope"] = "other"
    res = impact(b, Snapshot(p.records, "p", p.bodies))
    assert {a["affected"] for a in res["affected"]} == {"MS-Y"}
