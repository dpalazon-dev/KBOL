"""Domain vocabulary at the integration gate and in the approval package.

The vocabulary of the final tree is in force: the decision that defines a term may enter with its first use. Only the
step of an entity to `active` with a class not in force at the start of validity of that effect blocks; the rest
enters with the alert in the receipt.
"""

# ruff: noqa: F811  (the fixture is imported from test_integrate)

import pytest
from conftest import decision, record
from test_integrate import ACCEPT, _base_with, active, call, canonical, environment, propose, request  # noqa: F401
from test_vocabulary import defines

from kbol.core import serialize
from kbol.integrate import decisive_reasons, final_tree, prepare_request
from kbol.package import approval_package, present
from kbol.schema import validate
from kbol.vocabulary import in_force_vocabulary

ACTIVATE = [{"previous_state": "proposed", "new_state": "active", "valid_from": "2026-11-05T00:00:00Z"}]
CUT = "2026-11-06T00:00:00Z"


def dec_v(ident="DEC-V", entry=None):
    """(record, body) of a proposed decision that defines `plant` in its C1, or whatever `entry` says."""
    r = record("decision", id=ident, authorized_by=["ROLE-OP"], defines=defines(entry or {}))
    return r, '<clause id="C1">\nA plant treats water.\n</clause>\n'


def accepted(ident="DEC-V", **fields):
    return decision(
        ident,
        {"C1": "A plant treats water."},
        recorded="2026-10-04T00:00:00Z",
        authorized_by=["ROLE-OP"],
        defines=defines(fields.pop("defines", {})),
        **fields,
    )


def ent(ident, class_):
    return record("entity", id=ident, entity_class=class_)


def closed(repo, base, *extra):
    """Base with `plant` declared (closed world) plus whatever is added, already integrated."""
    files = {"kb/DEC-V.md": canonical(*accepted())}
    for r, c in extra:
        files[f"kb/{r['id']}.md"] = canonical(r, c)
    return _base_with(repo, base, files)


def proposal(repo, base, records, effects, op="op-1"):
    files = {f"kb/{r['id']}.md": serialize(r, c) for r, c in records}
    return propose(repo, base, {**files, **request(op, effects)})


def vocabulary_alerts(res):
    return [a for a in res["warnings"] if "entity_class" in a or "scope" in a]


def test_the_definition_and_its_first_use_enter_in_the_same_integration(environment):
    repo, base, receipts = environment
    prop = proposal(repo, base, [dec_v(), (ent("ENT-X", "WWTP"), "")], {"DEC-V": ACCEPT, "ENT-X": ACTIVATE})
    res = call(repo, base, prop, receipts)
    assert res["state"] == "integrated", res
    assert vocabulary_alerts(res) == []


def test_a_proposed_entity_with_an_undeclared_term_enters_with_an_alert(environment):
    repo, base, receipts = environment
    base2 = closed(repo, base)
    prop = proposal(repo, base2, [(ent("ENT-Y", "Plant"), "")], {})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "integrated", res
    assert vocabulary_alerts(res) == ["ENT-Y: undeclared term in entity_class: 'Plant'"]


def test_activating_an_entity_with_an_undeclared_term_blocks(environment):
    repo, base, receipts = environment
    base2 = closed(repo, base)
    prop = proposal(repo, base2, [(ent("ENT-Y", "Plant"), "")], {"ENT-Y": ACTIVATE})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA", res
    assert res["reason"].startswith("ENT-Y: undeclared term in entity_class: 'Plant'")
    assert repo.git("rev-parse", "canon") == base2 and not (receipts / "op-1.json").exists()


def test_a_term_defined_only_by_a_proposed_decision_is_not_in_force(environment):
    repo, base, receipts = environment
    base2 = closed(repo, base)
    new = dec_v("DEC-P", {"term": "treatment-plant", "aliases": []})
    prop = proposal(repo, base2, [new, (ent("ENT-Y", "treatment-plant"), "")], {"ENT-Y": ACTIVATE})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA", res
    assert "undeclared term" in res["reason"] and "'treatment-plant'" in res["reason"]


def test_an_undetermined_term_counts_as_undeclared(environment):
    repo, base, receipts = environment
    base2 = closed(repo, base, accepted("DEC-W", defines={"description": "Building."}))
    prop = proposal(repo, base2, [(ent("ENT-Y", "plant"), "")], {"ENT-Y": ACTIVATE})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA", res
    assert res["reason"].startswith("ENT-Y: undetermined term in entity_class: 'plant'")
    assert repo.git("rev-parse", "canon") == base2


def test_in_an_open_world_everything_enters_as_before(environment):
    repo, base, receipts = environment
    prop = proposal(repo, base, [(ent("ENT-Y", "whatever"), "")], {"ENT-Y": ACTIVATE})
    res = call(repo, base, prop, receipts)
    assert res["state"] == "integrated", res
    assert res["warnings"] == []


def test_retiring_a_term_in_use_lists_the_affected_uses_in_the_receipt(environment):
    repo, base, receipts = environment
    base2 = closed(repo, base, (active("entity", "ENT-1", entity_class="plant"), ""))
    repeals = record(
        "decision",
        id="DEC-W",
        authorized_by=["ROLE-OP"],
        amends=[{"target": "DEC-V#C1", "operation": "repeals"}],
    )
    prop = proposal(repo, base2, [(repeals, '<clause id="C1">\nRepealed.\n</clause>\n')], {"DEC-W": ACCEPT})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "integrated", res
    alert = "ENT-1: retired term, no longer in force in entity_class: 'plant'; use affected by this operation"
    assert vocabulary_alerts(res) == [alert]


def _without_warnings(voc):
    return {k: v for k, v in voc.items() if k not in ("warnings", "cuts")}


@pytest.mark.parametrize(
    "case",
    ["accepts_definition", "proposed_definition", "activates_entity", "repeals", "entity_without_effect"],
)
def test_the_vocabulary_only_changes_with_something_decisive(environment, case):
    """Invariant: if the vocabulary of the final tree is not that of the base, some touched record is decisive."""
    repo, base, _ = environment
    base2 = closed(repo, base)
    repeals = record(
        "decision", id="DEC-W", authorized_by=["ROLE-OP"], amends=[{"target": "DEC-V#C1", "operation": "repeals"}]
    )
    other = dec_v("DEC-N", {"term": "treatment-plant", "aliases": []})
    cases = {
        "accepts_definition": ([other], {"DEC-N": ACCEPT}, True),
        "proposed_definition": ([other], {}, False),
        "activates_entity": ([(ent("ENT-Y", "plant"), "")], {"ENT-Y": ACTIVATE}, False),
        "repeals": ([(repeals, '<clause id="C1">\nRepealed.\n</clause>\n')], {"DEC-W": ACCEPT}, True),
        "entity_without_effect": ([(ent("ENT-Y", "Plant"), "")], {}, False),
    }
    records, effects, changes = cases[case]
    prop = proposal(repo, base2, records, effects)
    p = prepare_request(repo.root, folder="kb", operation_id="op-1", base=base2, proposal=prop)
    final, _, _ = final_tree(p)
    before = _without_warnings(in_force_vocabulary(p.base_snap, valid_at=CUT, known_until=None))
    after = _without_warnings(in_force_vocabulary(final, valid_at=CUT, known_until=None))
    assert (before != after) == changes
    if before != after:
        assert any(p.decisive_reasons(i) for i in p.touched)


def _package(repo, base, prop, op="op-1"):
    return approval_package(repo.root, folder="kb", operation_id=op, base=base, proposal=prop, valid_at=CUT)


def test_the_package_blocks_like_the_gate_and_lists_the_findings(environment):
    repo, base, receipts = environment
    base2 = closed(repo, base)
    prop = proposal(repo, base2, [(ent("ENT-Y", "Plant"), "")], {"ENT-Y": ACTIVATE})
    pkg = _package(repo, base2, prop)
    gate = call(repo, base2, prop, receipts)
    assert pkg["state"] == gate["state"] == "blocked"
    assert pkg["code"] == gate["code"] == "INVALID_SCHEMA" and pkg["reason"] == gate["reason"]
    without_effect = proposal(repo, base2, [(ent("ENT-Y", "Plant"), "")], {}, op="op-2")
    pkg = _package(repo, base2, without_effect, op="op-2")
    assert pkg["state"] == "completed", pkg
    assert pkg["vocabulary"] == [
        {"id": "ENT-Y", "field": "entity_class", "value": "Plant", "situation": "undeclared", "touched": True}
    ]
    text = present(pkg)
    assert "Domain vocabulary:\n- ENT-Y: undeclared term in entity_class: 'Plant'" in text


def test_the_package_without_findings_does_not_add_the_section(environment):
    repo, base, _ = environment
    prop = proposal(repo, base, [dec_v(), (ent("ENT-X", "plant"), "")], {"DEC-V": ACCEPT, "ENT-X": ACTIVATE})
    pkg = _package(repo, base, prop)
    assert pkg["state"] == "completed" and pkg["vocabulary"] == [], pkg
    assert "Domain vocabulary" not in present(pkg)


BEFORE_DEFINING = [{"previous_state": "proposed", "new_state": "active", "valid_from": "2026-09-01T00:00:00Z"}]


def test_dating_the_activation_before_the_definition_does_not_open_the_world(environment):
    """The proposer chooses the start of validity: with the world closed when integrating, an undeclared class blocks."""
    repo, base, receipts = environment
    base2 = closed(repo, base)
    prop = proposal(repo, base2, [(ent("ENT-Y", "Plant"), "")], {"ENT-Y": BEFORE_DEFINING})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA", res
    assert "ENT-Y" in res["reason"] and "Plant" in res["reason"]


def test_a_declared_class_is_not_in_force_before_its_definition(environment):
    """The class must be in force at the start of validity of the effect and when integrating (C4), not only today."""
    repo, base, receipts = environment
    base2 = closed(repo, base)
    prop = proposal(repo, base2, [(ent("ENT-Y", "plant"), "")], {"ENT-Y": BEFORE_DEFINING})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA", res
    assert "2026-09-01" in res["reason"]


def test_an_import_that_carries_defines_is_decisive():
    """What fixes the vocabulary requires approval also in the decisive-only mode."""
    with_defines, _ = dec_v("DEC-H")
    without_defines = record("decision", id="DEC-H", authorized_by=["ROLE-OP"])
    assert decisive_reasons("DEC-H", with_defines, {}, set(), {"DEC-H": {}})
    assert not decisive_reasons("DEC-H", without_defines, {}, set(), {"DEC-H": {}})


@pytest.mark.parametrize("name", ["sensor ", " sensor", "entity "])
def test_a_term_with_surrounding_spaces_is_rejected(name):
    r, body = dec_v(entry={"term": name})
    errors = [h for h in validate(r, body) if h["severity"] == "error"]
    assert any("spaces" in h["message"] for h in errors), errors


def test_an_active_entity_does_not_change_to_a_class_not_in_force(environment):
    """Activating with a declared class and changing it later would be activating in two steps with one not in force."""
    repo, base, receipts = environment
    base2 = closed(repo, base, (active("entity", "ENT-1", entity_class="plant"), ""))
    changed = active("entity", "ENT-1", entity_class="Well")
    prop = propose(repo, base2, {"kb/ENT-1.md": canonical(changed, "")})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA", res
    assert "ENT-1" in res["reason"] and "Well" in res["reason"]


def test_an_active_entity_may_change_to_another_class_in_force(environment):
    repo, base, receipts = environment
    v, body = accepted(defines={"aliases": ["station"]})
    base2 = _base_with(
        repo,
        base,
        {"kb/DEC-V.md": canonical(v, body), "kb/ENT-1.md": canonical(active("entity", "ENT-1", entity_class="plant"), "")},
    )
    prop = propose(repo, base2, {"kb/ENT-1.md": canonical(active("entity", "ENT-1", entity_class="station"), "")})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "integrated", res
