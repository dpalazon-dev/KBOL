"""VAL-03: what a proposal may change against the base (mutability matrix of core 1.0)."""

import copy

from conftest import decision, event, record

from kbol.mutability import compare
from kbol.projection import Snapshot


def snap(pairs, revision):
    return Snapshot({r["id"]: r for r, _ in pairs}, revision, {r["id"]: c for r, c in pairs})


def errors(res):
    return [h for h in res["findings"] if h["severity"] == "error"]


def base_and_copy(*pairs):
    base = snap(pairs, "base")
    return base, copy.deepcopy(base)


def test_no_changes_no_findings():
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    res = compare(base, Snapshot(prop.records, "prop", prop.bodies))
    assert res["findings"] == [] and res["modified"] == [] and res["new"] == []


def test_accepted_clause_is_not_rewritten_removed_or_added():
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday.", "C2": "Checked data."}))
    for body in (
        '<clause id="C1">\nTuesday.\n</clause>\n<clause id="C2">\nChecked data.\n</clause>\n',
        '<clause id="C1">\nMonday.\n</clause>\n',
        '<clause id="C1">\nMonday.\n</clause>\n<clause id="C2">\nChecked data.\n</clause>\n<clause id="C3">\nX.\n</clause>\n',
    ):
        prop.bodies["DEC-A"] = body
        assert any(h["control"] == "VAL-03" for h in errors(compare(base, prop))), body


def test_prose_outside_clauses_title_and_description_may_change():
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    prop.bodies["DEC-A"] = "New context.\n\n" + prop.bodies["DEC-A"]
    prop.records["DEC-A"]["title"] = "Corrected title"
    prop.records["DEC-A"]["description"] = "Corrected description."
    res = compare(base, prop)
    assert errors(res) == [] and res["modified"] == ["DEC-A"]


def test_normative_fields_of_an_accepted_decision_are_protected():
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    prop.records["DEC-A"]["authorized_by"] = ["ROLE-OTHER"]
    prop.records["DEC-A"]["amends"] = [{"target": "DEC-Z#C1", "operation": "repeals"}]
    paths = {h["path"] for h in errors(compare(base, prop))}
    assert {"DEC-A/authorized_by", "DEC-A/amends"} <= paths


def test_a_proposal_is_edited_freely():
    base, prop = base_and_copy(decision("DEC-P", {"C1": "x"}, state="proposed"))
    prop.bodies["DEC-P"] = '<clause id="C1">\ny\n</clause>\n'
    prop.records["DEC-P"]["criteria"] = ["other"]
    assert errors(compare(base, prop)) == []


def test_events_append_only_and_only_from_the_integration():
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    prop.records["DEC-A"]["events"][0]["reason"] = "rewritten"
    assert any("events" in h["path"] for h in errors(compare(base, prop)))
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    prop.records["DEC-A"]["events"].append(
        event("approval_revocation", event_id="E9", recorded_at=None, approval_id="AP-DEC-A")
    )
    assert any("integration" in h["message"] for h in errors(compare(base, prop)))


def test_state_is_not_edited():
    base, prop = base_and_copy(decision("DEC-P", {"C1": "x"}, state="proposed"))
    prop.records["DEC-P"]["state"] = "accepted"
    assert any(h["path"] == "DEC-P/state" for h in errors(compare(base, prop)))


def test_record_is_not_deleted_and_does_not_change_type():
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    del prop.records["DEC-A"]
    assert errors(compare(base, prop))
    base, prop = base_and_copy(decision("DEC-A", {"C1": "Monday."}))
    prop.records["DEC-A"]["type"] = "fact"
    assert errors(compare(base, prop))


def test_source_fingerprint_immutable_and_pointer_movable():
    f = record(
        "source", events=[event("creation", event_id="E0", previous_state=None, new_state="registered")]
    )
    base, prop = base_and_copy((f, ""))
    prop.records["SRC-A"]["sha256"] = "c" * 64
    assert errors(compare(base, prop))
    base, prop = base_and_copy((f, ""))
    prop.records["SRC-A"]["location"] = "sources/moved/SRC-A.pdf"
    res = compare(base, prop)
    assert errors(res) == [] and any("VAL-10" in h["message"] for h in res["findings"])


def test_new_record_without_fabricated_events():
    base, prop = base_and_copy()
    new, body = decision("DEC-N", {"C1": "x"}, state="proposed")
    prop.records["DEC-N"], prop.bodies["DEC-N"] = new, body
    res = compare(base, prop)
    assert res["new"] == ["DEC-N"] and any("integration" in h["message"] for h in errors(res))
    new["events"] = []
    assert errors(compare(base, prop)) == []


def test_policy_change_is_flagged_for_prior_authority():
    role = record("role", events=[event("creation", event_id="E0", previous_state=None, new_state="proposed")])
    base, prop = base_and_copy((role, ""))
    prop.records["ROLE-EXAMPLE"]["capabilities"] = ["ratify", "administer"]
    res = compare(base, prop)
    assert res["policy_changes"] == ["ROLE-EXAMPLE"]
    assert any(
        h["code"] == "INSUFFICIENT_AUTHORITY" and h["severity"] == "requires_authority" for h in res["findings"]
    )
