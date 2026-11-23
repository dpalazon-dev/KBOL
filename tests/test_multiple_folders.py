"""Several canonical folders in one installation: one snapshot over their union, with a single root.

The policy lives in the first folder, which also holds the requests; records can be in any of them. References,
unique IDs, mutability and authority are checked over the union, and one operation can touch several folders.
"""

import json

import pytest
from conftest import DECISION_BODY, record
from test_integrate import ACCEPT, Repo, active, canonical, propose

from kbol.core import parse, serialize
from kbol.declared import MECHANISM, DeclaredVerifier
from kbol.digest import digest
from kbol.integrate import integrate
from kbol.snapshot import load

FOLDERS = ["kb", "docs/decisions"]


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
    repo.write("docs/decisions/README.md", "---\ntype: Cover\ntitle: Decisions\n---\nNot a record.\n")
    repo.write("docs/other/note.md", "---\ntype: Guide\ntitle: n\n---\n")
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def approval(base, digests):
    return {
        "mechanism": MECHANISM,
        "identity": "declared:h",
        "session": "s",
        "instant": "2026-11-05T12:00:00Z",
        "quote": "I approve the operation",
        "base_shown": base,
        "digests": digests,
    }


def integrate_in(repo, base, receipts, files, digests, op="op-1", folder=None):
    prop = propose(repo, base, files)
    return integrate(
        repo.root,
        branch="canon",
        folder=FOLDERS if folder is None else folder,
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=[approval(base, digests)],
        verifier=DeclaredVerifier(repo.root),
        receipts=receipts,
    )


def test_a_record_in_another_folder_is_integrated_with_the_policy_of_the_first(environment):
    repo, base, receipts = environment
    r = record("decision", id="DEC-Y", authorized_by=["ROLE-OP"])
    files = {
        "docs/decisions/DEC-Y.md": serialize(r, DECISION_BODY),
        "kb/_requests/op-1.json": json.dumps({"operation_id": "op-1", "effects": {"DEC-Y": ACCEPT}}),
    }
    res = integrate_in(repo, base, receipts, files, {"DEC-Y": digest(r, DECISION_BODY, ACCEPT)})
    assert res["state"] == "integrated", res
    meta, _ = parse(repo.git("show", "canon:docs/decisions/DEC-Y.md") + "\n")
    assert meta["state"] == "accepted"


def test_a_reference_across_folders_resolves_and_one_operation_touches_both(environment):
    repo, base, receipts = environment
    y = record("decision", id="DEC-Y", authorized_by=["ROLE-OP"])
    z = record("decision", id="DEC-Z", authorized_by=["ROLE-OP"], affects=["DEC-Y#C1"])
    files = {
        "docs/decisions/DEC-Y.md": serialize(y, DECISION_BODY),
        "kb/DEC-Z.md": serialize(z, DECISION_BODY),
    }
    digests = {"DEC-Y": digest(y, DECISION_BODY, []), "DEC-Z": digest(z, DECISION_BODY, [])}
    res = integrate_in(repo, base, receipts, files, digests)
    assert res["state"] == "integrated", res
    assert sorted(res["records"]) == ["DEC-Y", "DEC-Z"]


def test_loading_joins_the_folders_and_an_id_repeated_across_them_does_not_load_completely(environment):
    repo, base, _ = environment
    r = record("decision", id="DEC-Y", authorized_by=["ROLE-OP"])
    repo.git("checkout", "-q", "-b", "rep", base)
    repo.write("kb/DEC-Y.md", serialize(r, DECISION_BODY))
    repo.write("docs/decisions/DEC-Y.md", serialize(r, DECISION_BODY))
    rev = repo.commit("repeated")
    repo.git("checkout", "-q", "main")
    snap, coverage = load(repo.root, FOLDERS, base)
    assert set(snap.records) == {"ROLE-OP", "PER-H"} and coverage["state"] == "complete"
    _, repeated = load(repo.root, FOLDERS, rev, mode="proposal")
    assert repeated["state"] != "complete"


def test_nothing_outside_the_folders_is_touched(environment):
    repo, base, receipts = environment
    files = {"docs/other/note.md": "---\ntype: Guide\ntitle: other\n---\n"}
    res = integrate_in(repo, base, receipts, files, {})
    assert res["state"] == "blocked"


@pytest.mark.parametrize(
    "folder",
    [[], ["kb", "kb"], ["docs", "docs/decisions"], ["kb", "../outside"], ["kb", ""], "kb\\x", [1]],
)
def test_malformed_or_overlapping_folders_are_rejected(environment, folder):
    repo, base, receipts = environment
    res = integrate_in(repo, base, receipts, {"kb/x.md": "x\n"}, {}, folder=folder)
    assert res["state"] == "blocked"
    assert repo.git("rev-parse", "canon") == base


def test_a_single_folder_as_text_still_works(environment):
    repo, base, receipts = environment
    r = record("decision", id="DEC-Y", authorized_by=["ROLE-OP"])
    res = integrate_in(
        repo,
        base,
        receipts,
        {"kb/DEC-Y.md": serialize(r, DECISION_BODY)},
        {"DEC-Y": digest(r, DECISION_BODY, [])},
        folder="kb",
    )
    assert res["state"] == "integrated", res
