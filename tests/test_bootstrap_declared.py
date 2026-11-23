"""Declared bootstrap of the root: the person declares that they are the root and the agent quotes their words.

The same guarantees as the bootstrap with GitHub except one: nobody verifies the identity. The proof says so, and the
root is established all the same, so there is no second bootstrap through any channel.
"""

import json

import pytest
from conftest import DECISION_BODY, record
from test_bootstrap import ROLE, account, read
from test_integrate import ACCEPT, Repo, propose, request

from kbol.bootstrap import DECLARED_MECHANISM, bootstrap_run
from kbol.core import serialize
from kbol.declared import MECHANISM, DeclaredVerifier
from kbol.digest import digest
from kbol.integrate import integrate
from kbol.schema import validate

QUOTE = "I am David and I bootstrap the root of the installation"


@pytest.fixture
def root(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.write("README.md", "x\n")
    repo.write("kb/ROLE-ROOT.md", serialize(record("role", id="ROLE-ROOT", **ROLE), ""))
    person = record(
        "person",
        id="PER-D",
        nature="human",
        identity_ref="declared:d",
        holds=[{"role": "ROLE-ROOT", "from": "2026-10-01T00:00:00Z"}],
    )
    repo.write("kb/PER-D.md", serialize(person, ""))
    base = repo.commit("proposed root")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def declaration(**changes):
    data = {"identity": "declared:d", "session": "session kbol-e9", "instant": "2026-11-05T19:00:00Z", "quote": QUOTE}
    return {**data, **changes}


def call(repo, base, receipts, op="bootstrap-1", **kw):
    arguments = dict(
        branch="canon",
        folder="kb",
        expected_base=base,
        person="PER-D",
        roles=["ROLE-ROOT"],
        declaration=declaration(),
        receipts=receipts,
        operation_id=op,
    )
    arguments.update(kw)
    return bootstrap_run(repo.root, **arguments)


def test_declared_bootstrap_activates_the_root_and_says_it_is_not_authenticated(root):
    repo, base, receipts = root
    res = call(repo, base, receipts)
    assert res["state"] == "bootstrapped", res
    for path in ("kb/ROLE-ROOT.md", "kb/PER-D.md"):
        meta, body = read(repo, path)
        assert meta["state"] == "active" and validate(meta, body, mode="canonical") == []
        evidence = meta["events"][1]["event_evidence"]
        assert evidence["mechanism"] == DECLARED_MECHANISM
        assert QUOTE in evidence["proof"] and "not authenticated" in evidence["proof"]
    receipt = json.loads((receipts / "bootstrap-1.json").read_text(encoding="utf-8"))
    assert receipt["account"]["identity"] == "declared:d" and receipt["account"]["authenticated"] is False
    assert receipt["account"]["quote"] == QUOTE
    assert "Bootstrap: declared:d" in repo.git("log", "-1", "--format=%B", "canon")


def test_the_declared_identity_must_be_the_person_s(root):
    repo, base, receipts = root
    res = call(repo, base, receipts, declaration=declaration(identity="declared:other"))
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY", res
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize(
    "change",
    [{"identity": "d"}, {"quote": " "}, {"session": ""}, {"instant": "2026-11-05"}, {"other": "field"}],
)
def test_a_malformed_declaration_does_not_bootstrap(root, change):
    repo, base, receipts = root
    res = call(repo, base, receipts, declaration=declaration(**change))
    assert res["state"] == "blocked", res
    assert repo.git("rev-parse", "canon") == base


def test_one_channel_and_only_one(root):
    repo, base, receipts = root
    both = call(repo, base, receipts, client=account())
    none = call(repo, base, receipts, declaration=None)
    assert both["state"] == none["state"] == "blocked"
    assert repo.git("rev-parse", "canon") == base


def test_after_the_declared_bootstrap_there_is_no_other_bootstrap_through_any_channel(root):
    repo, base, receipts = root
    canon = call(repo, base, receipts)["integrated_revision"]
    other = call(repo, canon, receipts, op="bootstrap-2")
    github = call(repo, canon, receipts, op="bootstrap-3", declaration=None, client=account())
    assert other["code"] == github["code"] == "ROOT_ALREADY_ESTABLISHED"
    assert repo.git("rev-parse", "canon") == canon


def test_then_the_integration_accepts_with_a_declared_approval_of_the_root(root):
    repo, base, receipts = root
    boot = call(repo, base, receipts)
    canon = boot["integrated_revision"]
    r = record("decision", id="DEC-X", authorized_by=["ROLE-ROOT"])
    prop = propose(repo, canon, {"kb/DEC-X.md": serialize(r, DECISION_BODY), **request("op-1", {"DEC-X": ACCEPT})})
    approval = {
        "mechanism": MECHANISM,
        "identity": "declared:d",
        "session": "session kbol-e9",
        "instant": boot["recorded_at"],
        "quote": "I accept DEC-X",
        "base_shown": canon,
        "digests": {"DEC-X": digest(r, DECISION_BODY, ACCEPT)},
    }
    res = integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id="op-1",
        expected_base=canon,
        proposal_rev=prop,
        revisions=[approval],
        verifier=DeclaredVerifier(repo.root),
        receipts=receipts,
    )
    assert res["state"] == "integrated", res
    meta, _ = read(repo, "kb/DEC-X.md")
    assert meta["state"] == "accepted"
