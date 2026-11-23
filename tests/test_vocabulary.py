"""Domain vocabulary: schema of `defines`, what is in force at two cuts, its uses and the command.

The integration gate and the approval package are tested in `test_vocabulary_integrate.py`.
"""

import pytest
from conftest import DECISION_BODY, decision, record
from test_integrate import active
from test_policy_cli import kb, write

from kbol.projection import Snapshot
from kbol.query import query
from kbol.schema import validate
from kbol.vocabulary import OPEN_WORLD, in_force_vocabulary, review, situation

PLANT = {
    "clause": "C1",
    "term": "plant",
    "class": "entity_class",
    "description": "Facility that treats water.",
    "aliases": ["WWTP"],
}
AFTER = "2026-11-20T00:00:00Z"


def with_defines(*entries, **changes):
    return record("decision", defines=[{**PLANT, **e} for e in entries], **changes)


def defines(*entries):
    return [{**PLANT, **e} for e in entries]


def snap(*pairs):
    return Snapshot({r["id"]: r for r, _ in pairs}, "r1", {r["id"]: c for r, c in pairs})


def role():
    return active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one"), ""


def entity(ident, class_, **fields):
    return active("entity", ident, entity_class=class_, **fields), ""


def dec_v(**extra):
    return decision("DEC-V", {"C1": "A plant treats water."}, defines=defines({}), authorized_by=["ROLE-OP"], **extra)


# Schema


def test_a_valid_defines_passes_the_schema():
    assert validate(with_defines({}), DECISION_BODY) == []
    without_aliases = {k: v for k, v in PLANT.items() if k != "aliases"}
    assert validate(record("decision", defines=[without_aliases]), DECISION_BODY) == []


def test_the_clause_of_a_defines_is_in_the_body():
    [h] = validate(with_defines({"clause": "C9"}), DECISION_BODY)
    assert h["code"] == "MISSING_REFERENCE" and h["path"] == "/defines/0/clause"


@pytest.mark.parametrize("name", ["based_on", "decision", "Entity", "entity_class", "defines", "scopes"])
def test_a_term_does_not_take_the_name_of_a_type_a_field_or_a_relation(name):
    for entry in ({"term": name}, {"aliases": [name]}):
        findings = validate(with_defines(entry), DECISION_BODY)
        assert [h["code"] for h in findings] == ["INVALID_SCHEMA"], findings
        assert "type, a field or a relation" in findings[0]["message"]


@pytest.mark.parametrize("change", [{"class": "role_class"}, {"scope": "x"}, {"term": "two\nlines"}])
def test_unknown_class_extra_key_or_multiline_term(change):
    assert [h["code"] for h in validate(with_defines(change), DECISION_BODY)] == ["INVALID_SCHEMA"]


def test_a_term_or_an_alias_does_not_repeat_in_the_record():
    repeated = validate(with_defines({}, {"description": "Another."}), DECISION_BODY)
    assert [h["path"] for h in repeated] == ["/defines/1/term", "/defines/1/aliases/0"]
    aliases = validate(with_defines({}, {"term": "treatment-plant", "aliases": ["plant"]}), DECISION_BODY)
    assert [h["path"] for h in aliases] == ["/defines/1/aliases/0"]


def test_only_a_decision_declares_defines():
    findings = validate(record("entity", defines=defines({})), "")
    assert any(h["path"] == "/defines" and "field not declared" in h["message"] for h in findings)


# What is in force


def test_a_term_is_in_force_when_its_decision_is_accepted():
    voc = in_force_vocabulary(snap(dec_v()), valid_at=AFTER, known_until=None)
    assert voc["declared"] is True
    assert voc["classes"] == {
        "plant": {"decision": "DEC-V", "clause": "C1", "description": PLANT["description"], "aliases": ["WWTP"]}
    }
    assert voc["aliases"] == {"WWTP": "plant"}
    assert situation(voc, "WWTP") == ("current", "plant")
    assert situation(voc, "Plant") == ("undeclared", "Plant")


def test_a_proposed_decision_declares_nothing():
    voc = in_force_vocabulary(snap(dec_v(state="proposed")), valid_at=AFTER, known_until=None)
    assert voc["classes"] == {} and voc["declared"] is False
    assert situation(voc, "anything") == ("open", "anything")


def test_a_term_is_in_force_at_both_cuts():
    s = snap(dec_v(recorded="2026-11-03T00:00:00Z", valid="2026-11-05T00:00:00Z"))
    # Before its start of validity, and when it was not known yet, it is not in force.
    assert in_force_vocabulary(s, valid_at="2026-11-04T00:00:00Z", known_until=None)["classes"] == {}
    assert in_force_vocabulary(s, valid_at=AFTER, known_until="2026-11-02T00:00:00Z")["classes"] == {}
    assert "plant" in in_force_vocabulary(s, valid_at=AFTER, known_until="2026-11-04T00:00:00Z")["classes"]


def _amends(ident, operation, body, recorded="2026-11-02T00:00:00Z", **extra):
    mod = {"target": "DEC-V#C1", "operation": operation} | ({"by": f"{ident}#C1"} if operation == "replaces" else {})
    return decision(ident, {"C1": body}, recorded=recorded, amends=[mod], **extra)


def test_a_replaced_clause_stops_defining_and_the_new_definition_is_in_force():
    renames = _amends("DEC-W", "replaces", "A treatment plant.", defines=defines({"term": "treatment-plant"}))
    voc = in_force_vocabulary(snap(dec_v(), renames), valid_at=AFTER, known_until=None)
    assert list(voc["classes"]) == ["treatment-plant"] and voc["classes"]["treatment-plant"]["decision"] == "DEC-W"
    assert situation(voc, "plant") == ("retired", "plant")
    # Renaming is replacing with the previous name as an alias (C6): the previous name still resolves.
    with_alias = _amends(
        "DEC-W", "replaces", "A treatment plant.", defines=defines({"term": "treatment-plant", "aliases": ["plant"]})
    )
    voc = in_force_vocabulary(snap(dec_v(), with_alias), valid_at=AFTER, known_until=None)
    assert situation(voc, "plant") == ("current", "treatment-plant") and voc["retired"] == []
    # Before the replacement was known, the previous definition was still in force.
    previous = in_force_vocabulary(snap(dec_v(), with_alias), valid_at=AFTER, known_until="2026-11-01T12:00:00Z")
    assert list(previous["classes"]) == ["plant"]


def test_a_repealed_clause_retires_the_term():
    voc = in_force_vocabulary(snap(dec_v(), _amends("DEC-W", "repeals", "Repealed.")), valid_at=AFTER, known_until=None)
    assert voc["classes"] == {} and voc["retired"] == [
        {"term": "plant", "definitions": ["DEC-V#C1"], "aliases": ["WWTP"]}
    ]
    assert situation(voc, "WWTP") == ("retired", "plant")


def test_two_different_definitions_in_force_leave_the_term_undetermined():
    other = decision("DEC-W", {"C1": "Something else."}, defines=defines({"description": "Building."}))
    voc = in_force_vocabulary(snap(dec_v(), other), valid_at=AFTER, known_until=None)
    assert voc["classes"] == {} and voc["declared"] is True
    [ind] = voc["undetermined"]
    assert ind["term"] == "plant" and ind["definitions"] == ["DEC-V#C1", "DEC-W#C1"]
    assert situation(voc, "plant") == ("undetermined", "plant")
    # The same definition in two decisions is not a conflict.
    same = decision("DEC-W", {"C1": "The same."}, defines=defines({}))
    assert "plant" in in_force_vocabulary(snap(dec_v(), same), valid_at=AFTER, known_until=None)["classes"]


def test_an_alias_that_is_another_term_leaves_both_undetermined():
    wwtp = decision("DEC-W", {"C1": "WWTP."}, defines=defines({"term": "WWTP", "aliases": []}))
    voc = in_force_vocabulary(snap(dec_v(), wwtp), valid_at=AFTER, known_until=None)
    assert voc["classes"] == {} and [i["term"] for i in voc["undetermined"]] == ["WWTP", "plant"]


def test_an_ambiguous_day_validity_leaves_the_term_undetermined():
    s = snap(dec_v(recorded="2026-11-03T00:00:00Z", valid="2026-11-05"))
    voc = in_force_vocabulary(s, valid_at="2026-11-05T06:00:00Z", known_until=None)
    assert voc["classes"] == {} and voc["declared"] is True
    assert voc["undetermined"][0]["reason"] == "its validity cannot be decided"
    assert any("AMBIGUOUS_TIME" in a for a in voc["warnings"])


def test_the_scopes_are_those_of_the_active_roles():
    proposed = record("role", id="ROLE-P", scopes=["other"], capabilities=["ratify"], approval_rule="one")
    voc = in_force_vocabulary(snap(role(), (proposed, "")), valid_at=AFTER, known_until=None)
    assert voc["scopes"] == ["operations"]
    # Before becoming active, the role covers nothing.
    assert in_force_vocabulary(snap(role()), valid_at=AFTER, known_until="2026-10-01T12:00:00Z")["scopes"] == []


# Uses


def test_an_undeclared_term_is_flagged_with_its_uses():
    s = snap(role(), dec_v(), entity("ENT-1", "plant"), entity("ENT-2", "Plant"), entity("ENT-3", "WWTP"))
    voc = in_force_vocabulary(s, valid_at=AFTER, known_until=None)
    rev = review(s, voc, known_until=None)
    assert rev["undeclared"] == [{"term": "Plant", "uses": ["ENT-2"]}]
    assert rev["undetermined"] == [] and rev["retired_in_use"] == [] and rev["scopes_without_role"] == []
    assert rev["coverage"] == [] and rev["records_examined"] == 5


def test_in_an_open_world_no_class_is_flagged():
    s = snap(role(), entity("ENT-2", "Plant"))
    rev = review(s, in_force_vocabulary(s, valid_at=AFTER, known_until=None), known_until=None)
    assert rev["undeclared"] == [] and rev["coverage"] == [OPEN_WORLD]


def test_an_undetermined_term_is_flagged_with_its_uses():
    other = decision("DEC-W", {"C1": "Something else."}, defines=defines({"description": "Building."}))
    s = snap(role(), dec_v(), other, entity("ENT-1", "WWTP"))
    rev = review(s, in_force_vocabulary(s, valid_at=AFTER, known_until=None), known_until=None)
    assert [(i["term"], i["uses"]) for i in rev["undetermined"]] == [("plant", ["ENT-1"])]
    assert rev["undeclared"] == []


def test_a_retired_term_does_not_remove_any_record_from_the_base():
    s = snap(role(), dec_v(), _amends("DEC-W", "repeals", "Repealed."), entity("ENT-1", "plant"))
    rev = review(s, in_force_vocabulary(s, valid_at=AFTER, known_until=None), known_until=None)
    assert rev["retired_in_use"] == [{"term": "plant", "uses": ["ENT-1"]}] and rev["undeclared"] == []
    assert "ENT-1" in s.records
    [res] = query(s, ["ENT-1"], valid_at=AFTER, known_until=None)["results"]
    assert res["found"] == "canonical" and res["state"] == "active"


def test_a_retired_entity_no_longer_uses_its_term():
    retired = active("entity", "ENT-R", entity_class="Plant")
    retired["events"].append(
        {**retired["events"][1], "event_id": "E2", "previous_state": "active", "new_state": "retired"}
    )
    s = snap(role(), dec_v(), (retired, ""))
    assert review(s, in_force_vocabulary(s, valid_at=AFTER, known_until=None), known_until=None)["undeclared"] == []


def test_a_scope_without_an_active_role_is_flagged():
    s = snap(role(), entity("ENT-1", "plant", scope="Operations"))
    rev = review(s, in_force_vocabulary(s, valid_at=AFTER, known_until=None), known_until=None)
    assert rev["scopes_without_role"] == [{"scope": "Operations", "uses": ["ENT-1"]}]


# `vocabulary` command


def _kb_vocabulary(root, *extra):
    return kb("vocabulary", str(root), "--folder", "kb", "--valid-at", AFTER, *extra)


def test_the_vocabulary_command_says_what_is_in_force_and_what_is_undeclared(tmp_path):
    folder = tmp_path / "kb"
    for r, c in (role(), dec_v(), entity("ENT-1", "WWTP"), entity("ENT-2", "Plant")):
        write(folder, r["id"], r, c)
    code, out = _kb_vocabulary(tmp_path)
    assert code == 0 and out["result"]["state"] == "completed", out
    res = out["result"]
    assert res["declared"] is True and list(res["classes"]) == ["plant"] and res["aliases"] == {"WWTP": "plant"}
    assert res["undeclared"] == [{"term": "Plant", "uses": ["ENT-2"]}]
    assert res["undetermined"] == [] and res["scopes_without_role"] == [] and res["scopes"] == ["operations"]
    assert OPEN_WORLD not in out["coverage"]["not_evaluated"]
    # Not with --ids: the command reviews the whole base.
    code, out = _kb_vocabulary(tmp_path, "--ids", "ENT-1")
    assert code == 2 and out["result"]["state"] == "blocked"


def test_the_vocabulary_command_in_an_open_world_says_so(tmp_path):
    folder = tmp_path / "kb"
    for r, c in (role(), entity("ENT-2", "Plant")):
        write(folder, r["id"], r, c)
    code, out = _kb_vocabulary(tmp_path, "--known-until", AFTER)
    assert code == 0 and out["result"]["declared"] is False, out
    assert out["result"]["undeclared"] == [] and OPEN_WORLD in out["coverage"]["not_evaluated"]


def test_the_vocabulary_command_without_records_is_partial(tmp_path):
    (tmp_path / "kb").mkdir()
    code, out = _kb_vocabulary(tmp_path)
    assert code == 3 and out["result"]["state"] == "partial", out
    assert any("no record examined" in a for a in out["warnings"])
