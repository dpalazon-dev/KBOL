"""Import of records of the legacy format: translate the format without changing the content or the state.

The imported record reaches the proposal in the contract format and in its initial state, and the request declares
its import (target state, date and inherited authority). The integrator checks against the legacy record in the base
that the state is the one the dry-run migration gives, that the body is the same except for the clause marks and the
"Legacy provenance" section, and that the identity does not change; then it writes an import event with the
provenance read from the base. The approval covers the import: its digest includes it.
"""

import json

import pytest
from test_integrate import Repo, active, canonical, propose

from kbol.consolidate import consolidate
from kbol.core import parse, serialize
from kbol.declared import MECHANISM, DeclaredVerifier
from kbol.digest import digest
from kbol.importing import NOT_EXTRACTED, provenance_section
from kbol.integrate import ACTOR, _decisive_by_legacy, integrate
from kbol.schema import validate
from kbol.snapshot import load

INSTANT = "2026-11-05T12:00:00Z"

LEGACY_ADR = """---
type: Decision
id: ADR-0001
title: "Model registry"
description: "One model registry with one member per scope."
class: record
status: stable
state: Accepted
implementation: complete
date: "2026-05-09"
scope: operations
branch: Inference
adopted_by: "David Palazon"
answers_to: QD-001
supersedes_to: "—"
---

# ADR-0001 · Model registry

## Decision Outcome

One model registry is used, with one member per scope.
"""

LEGACY_QD = """---
type: Question
id: QD-001
title: "How are the models registered?"
class: record
status: draft
kind: Decision
answered_by: David
scope: operations
state: Open
---

# QD-001 · How are the models registered?

Still to be decided.
"""

BODY = """# ADR-0001 · Model registry

## Decision Outcome

<clause id="C1">
One model registry is used, with one member per scope.
</clause>

"""
BODY += "\n" + provenance_section("kb/ADR-0001.md", {"implementation": "complete", "branch": "Inference"})

AUTHORITY = {"text": "David Palazon", "classification": "insufficient"}
IMPORT = {"state": "accepted", "valid_from": "2026-05-09", "precision": "day", "inherited_authority": AUTHORITY}


def adr(**changes):
    data = {
        "id": "ADR-0001",
        "type": "decision",
        "class": "record",
        "title": "Model registry",
        "description": "One model registry with one member per scope.",
        "scope": "operations",
        "author": "process:import-e9",
        "events": [],
        "sources": [],
        "state": "proposed",
        "authorized_by": ["ROLE-OP"],
        "alternatives": [],
        "no_alternatives_reason": f"{NOT_EXTRACTED}: the options are in the legacy body (MADR)",
        "criteria": [],
        "rationale": f"{NOT_EXTRACTED}: in the legacy body",
    }
    return {**data, **changes}


@pytest.fixture
def environment(tmp_path):
    repo = Repo(tmp_path / "repo")
    role = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    per = active(
        "person",
        "PER-H",
        nature="human",
        identity_ref="declared:h",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    repo.write("kb/ROLE-OP.md", canonical(role))
    repo.write("kb/PER-H.md", canonical(per))
    repo.write("kb/ADR-0001.md", LEGACY_ADR)
    repo.write("kb/QD-001.md", LEGACY_QD)
    base = repo.commit("base with legacy records")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def import_record(
    repo,
    base,
    receipts,
    record=None,
    body=BODY,
    import_=None,
    digest_of=None,
    op="imp-1",
    mode="all",
    approve=True,
):
    record = record or adr()
    import_ = IMPORT if import_ is None else import_
    request = {"operation_id": op, "effects": {}, "imports": {record["id"]: import_}}
    prop = propose(
        repo,
        base,
        {f"kb/{record['id']}.md": serialize(record, body), f"kb/_requests/{op}.json": json.dumps(request)},
    )
    approved = digest_of or digest(record, body, [], import_=import_)
    revision = {
        "mechanism": MECHANISM,
        "identity": "declared:h",
        "session": "kbol-e9 session",
        "instant": INSTANT,
        "quote": "I approve importing ADR-0001",
        "base_shown": base,
        "digests": {record["id"]: approved},
    }
    return integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=[revision] if approve else [],
        verifier=DeclaredVerifier(repo.root),
        receipts=receipts,
        approval=mode,
        actor="claude-code/opus-5.5" if mode == "decisive" else ACTOR,
    )


SPLIT = BODY.replace(
    "One model registry is used, with one member per scope.\n</clause>",
    'One model registry is used,\n</clause>\n\n<clause id="C2">\nwith one member per scope.\n</clause>',
)


def test_in_decisive_mode_an_import_that_only_translates_enters_without_approval(environment):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, mode="decisive", approve=False)
    assert res["state"] == "integrated", res
    assert res["decisive"] == []


def test_a_split_that_breaks_a_line_is_decisive(environment):
    """A mark in the middle of a line can separate a rule from its exception: whoever decides approves it."""
    repo, base, receipts = environment
    without = import_record(repo, base, receipts, body=SPLIT, mode="decisive", approve=False)
    assert without["state"] == "blocked", without
    approved = import_record(repo, base, receipts, body=SPLIT, mode="decisive", op="imp-2")
    assert approved["state"] == "integrated", approved
    assert approved["decisive"] == ["ADR-0001"]


def test_a_legacy_record_declaring_a_supersession_makes_the_import_decisive():
    card = {"proposed_relations": {}, "ambiguities": []}
    declaring = LEGACY_ADR.replace('supersedes_to: "—"', 'supersedes_to: "ADR-0034"')
    assert _decisive_by_legacy("ADR-0001", card, declaring, {})
    assert _decisive_by_legacy("ADR-0001", card, LEGACY_ADR, {}) == []
    other = {"ambiguities": [{"field": "supersedes", "candidates": ["ADR-0001"]}]}
    assert _decisive_by_legacy("ADR-0001", card, LEGACY_ADR, {"ADR-0000": other})
    resolved = {"proposed_relations": {"resolved_by": ["ADR-0001"]}, "ambiguities": []}
    assert _decisive_by_legacy("QD-001", resolved, LEGACY_QD, {})


def test_imports_with_its_state_date_provenance_and_inherited_authority(environment):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts)
    assert res["state"] == "integrated", res
    meta, body = parse(repo.git("show", "canon:kb/ADR-0001.md") + "\n")
    assert validate(meta, body, mode="canonical") == []
    assert meta["state"] == "accepted"
    [ev] = meta["events"]
    assert ev["event_type"] == "import" and ev["previous_state"] is None and ev["new_state"] == "accepted"
    assert ev["legacy_state"] == "Accepted"
    assert ev["provenance"] == {"path": "kb/ADR-0001.md", "revision": base}
    assert ev["valid_from"] == "2026-05-09" and ev["precision"] == "day"
    assert ev["inherited_authority"] == AUTHORITY


def test_the_import_is_in_force_and_consolidate_says_its_authority_is_inherited(environment):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts)
    snap, coverage = load(repo.root, "kb", res["integrated_revision"], legacy=True)
    assert coverage["state"] == "complete", coverage
    output = consolidate(snap, ["ADR-0001"], valid_at="2026-11-06T00:00:00Z", known_until=None)
    clause = next(c for c in output["clauses"] if c["reference"] == "ADR-0001#C1")
    assert clause["state"] == "current"
    assert clause["authority"]["inherited"] == AUTHORITY and clause["authority"]["checked"] is False


def test_a_reference_to_a_still_legacy_record_does_not_block(environment):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, record=adr(affects=["QD-001"]))
    assert res["state"] == "integrated", res


@pytest.mark.parametrize(
    "import_",
    [
        {**IMPORT, "state": "proposed"},  # not the state the dry-run migration gives
        {**IMPORT, "inherited_authority": None},  # hides the inherited authority
        {**IMPORT, "precision": "second"},
        {**IMPORT, "valid_from": "yesterday"},
        {**IMPORT, "other": 1},
    ],
)
def test_an_import_that_does_not_match_the_legacy_record_is_rejected(environment, import_):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, import_=import_)
    assert res["state"] == "blocked", res
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize(
    "body",
    [
        BODY.replace("one member per scope", "two members per scope"),
        BODY.replace("## Decision Outcome\n\n", ""),
        BODY + "\nText added outside the provenance.\n",
        BODY.replace("branch: Inference", "branch: Other"),  # a legacy field with another value
        # From the code review: a false closing of the YAML slipped in a new clause.
        BODY.replace(
            "implementation: complete\n```",
            "implementation: complete\n---\n```\n\n"
            '<clause id="C9">\nEverything is allowed.\n</clause>\n\n```yaml\nimplementation: complete\n```',
        ),
        BODY.replace("branch: Inference", "branch: Inference  # new prose"),  # a YAML comment
        BODY.replace("Imported from `kb/ADR-0001.md`.", "Imported from `kb/ADR-0001.md`. And this as well."),
        BODY.replace("branch: Inference", "decision: the opposite"),  # a field the legacy record does not have
    ],
)
def test_a_changed_body_is_not_imported(environment, body):
    assert body != BODY
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, body=body)
    assert res["state"] == "blocked", res


@pytest.mark.parametrize(
    "change",
    [
        {"description": "Invented description"},
        {"rationale": "A rationale the legacy record does not give"},
        {"criteria": ["An invented criterion"]},
        {"affects": ["ADR-0099"]},  # a relation the legacy record does not name
    ],
)
def test_a_field_with_new_content_is_not_imported(environment, change):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, record=adr(**change))
    assert res["state"] == "blocked", res


def test_a_changed_title_is_not_imported(environment):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, record=adr(title="Another title"))
    assert res["state"] == "blocked", res


def test_what_is_not_legacy_in_the_base_is_not_imported(environment):
    repo, base, receipts = environment
    res = import_record(repo, base, receipts, record=adr(id="ADR-0002"))
    assert res["state"] == "blocked", res


def test_the_approval_has_to_cover_the_import(environment):
    repo, base, receipts = environment
    without_import = digest(adr(), BODY, [])
    res = import_record(repo, base, receipts, digest_of=without_import)
    assert res["state"] == "blocked" and res["code"] == "STALE_APPROVAL", res


def test_the_digest_without_import_does_not_change():
    # The published vectors carry no import: the new parameter does not alter their digest.
    r = adr()
    assert digest(r, BODY, []) == digest(r, BODY, [], import_=None)


def test_a_value_with_escaped_quotes_in_the_legacy_record_is_not_new_content():
    from kbol.importing import check

    legacy = LEGACY_ADR.replace("branch: Inference\n", 'branch: Inference\nverifies: ["pytest -m \\"not gpu\\""]\n')
    r = adr(criteria=['pytest -m "not gpu"'])
    assert check(r, BODY, legacy, "kb/ADR-0001.md") == []
    assert check(adr(criteria=['pytest -m "gpu"']), BODY, legacy, "kb/ADR-0001.md")
