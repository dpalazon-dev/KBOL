"""Bootstrap of the root of trust: only once, with the verified account, and then the normal integration (E4)."""

import json

import pytest
from conftest import DECISION_BODY, record
from test_integrate import ACCEPT, REVISION, Client, Repo, canonical, propose, request, verifier

from kbol.bootstrap import bootstrap_run
from kbol.core import parse, serialize
from kbol.integrate import integrate
from kbol.schema import validate

ROLE = dict(scopes=["operations"], capabilities=["ratify", "govern_policy"], approval_rule="one")


def person(**changes):
    data = dict(
        id="PER-D",
        nature="human",
        identity_ref="github:101",
        holds=[{"role": "ROLE-ROOT", "from": "2026-10-01T00:00:00Z"}],
    )
    return record("person", **{**data, **changes})


@pytest.fixture
def root(tmp_path):
    """Repository with the proposed root (a role that governs the policy and the person who holds it)."""
    repo = Repo(tmp_path / "repo")
    repo.write("README.md", "x\n")
    repo.write("kb/ROLE-ROOT.md", serialize(record("role", id="ROLE-ROOT", **ROLE), ""))
    repo.write("kb/PER-D.md", serialize(person(), ""))
    base = repo.commit("proposed root")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def account(ident=101, login="david", type_="User"):
    return Client({"/user": {"id": ident, "login": login, "type": type_}})


def call(repo, base, receipts, op="bootstrap-1", client=None, **kw):
    arguments = dict(
        branch="canon",
        folder="kb",
        expected_base=base,
        person="PER-D",
        roles=["ROLE-ROOT"],
        client=client or account(),
        receipts=receipts,
        operation_id=op,
    )
    arguments.update(kw)
    return bootstrap_run(repo.root, **arguments)


def reviewed_after(ver, since):
    """The verifier with the review dated at the instant of the bootstrap: before it, the person was not active yet."""
    for revision in ver.client.responses["/repos/o/r/pulls/1/reviews?per_page=100&page=1"]:
        revision["submitted_at"] = since
    return ver


def read(repo, path, rev="canon"):
    return parse(repo.git("show", f"{rev}:{path}") + "\n")


def test_valid_bootstrap_activates_the_root_with_admitted_events(root):
    repo, base, receipts = root
    res = call(repo, base, receipts)
    assert res["state"] == "bootstrapped", res
    canon = repo.git("rev-parse", "canon")
    assert res["integrated_revision"] == canon and repo.git("log", "-1", "--format=%P", "canon").split() == [base]
    message = repo.git("log", "-1", "--format=%B", "canon")
    assert "Operation-Id: bootstrap-1" in message and "Bootstrap: github:101" in message and f"Base: {base}" in message
    for path in ("kb/ROLE-ROOT.md", "kb/PER-D.md"):
        meta, body = read(repo, path)
        assert meta["state"] == "active"
        assert [e["event_type"] for e in meta["events"]] == ["creation", "transition"]
        assert all(e["recorded_at"] for e in meta["events"])
        assert meta["events"][1]["event_evidence"]["mechanism"] == "bootstrap-github-user"
        assert "github:101 (david)" in meta["events"][1]["event_evidence"]["proof"]
        assert validate(meta, body, mode="canonical") == []
    receipt = json.loads((receipts / "bootstrap-1.json").read_text(encoding="utf-8"))
    assert receipt["integrated_revision"] == canon and receipt["account"] == {"id": 101, "login": "david"}
    assert receipt["records"] == ["ROLE-ROOT", "PER-D"]


def test_after_the_bootstrap_the_normal_integration_accepts_with_that_person(root):
    repo, base, receipts = root
    boot = call(repo, base, receipts)
    canon = boot["integrated_revision"]
    r = record("decision", id="DEC-X", authorized_by=["ROLE-ROOT"])
    prop = propose(repo, canon, {"kb/DEC-X.md": serialize(r, DECISION_BODY), **request("op-1", {"DEC-X": ACCEPT})})
    res = integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id="op-1",
        expected_base=canon,
        proposal_rev=prop,
        revisions=[REVISION],
        verifier=reviewed_after(verifier(prop, canon, user=101), boot["recorded_at"]),
        receipts=receipts,
    )
    assert res["state"] == "integrated", res
    meta, _ = read(repo, "kb/DEC-X.md")
    assert meta["state"] == "accepted" and meta["events"][1]["approval"]["actor"] == "human:PER-D"


def test_the_root_is_bootstrapped_only_once(root):
    repo, base, receipts = root
    canon = call(repo, base, receipts)["integrated_revision"]
    res = call(repo, canon, receipts, op="bootstrap-2")
    assert res["state"] == "blocked" and res["code"] == "ROOT_ALREADY_ESTABLISHED"
    assert repo.git("rev-parse", "canon") == canon


@pytest.mark.parametrize(
    "client, code",
    [
        (account(ident=202), "INSUFFICIENT_AUTHORITY"),  # the token belongs to another account
        (account(type_="Bot"), "INSUFFICIENT_AUTHORITY"),  # an account that is not a person's
        (Client({"/user": {"login": "david"}}), "INSUFFICIENT_AUTHORITY"),  # without id
    ],
)
def test_the_verified_account_must_be_the_person_s(root, client, code):
    repo, base, receipts = root
    res = call(repo, base, receipts, client=client)
    assert res["state"] == "blocked" and res["code"] == code
    assert repo.git("rev-parse", "canon") == base and not (receipts / "bootstrap-1.json").exists()


@pytest.mark.parametrize(
    "role, per, reason",
    [
        (dict(capabilities=["ratify"]), {}, "governs the policy"),
        ({}, dict(nature="agent"), "human"),
        ({}, dict(holds=[]), "does not hold"),
        ({}, dict(holds=[{"role": "ROLE-ROOT", "from": "2099-01-01T00:00:00Z"}]), "does not hold"),
    ],
)
def test_the_proposed_root_must_be_consistent(tmp_path, role, per, reason):
    repo = Repo(tmp_path / "repo")
    repo.write("kb/ROLE-ROOT.md", serialize(record("role", id="ROLE-ROOT", **{**ROLE, **role}), ""))
    repo.write("kb/PER-D.md", serialize(person(**per), ""))
    base = repo.commit("root")
    repo.git("branch", "canon")
    res = call(repo, base, tmp_path / "receipts")
    assert res["state"] == "blocked" and reason in res["reason"], res
    assert repo.git("rev-parse", "canon") == base


def test_a_root_record_with_history_is_not_bootstrapped(tmp_path):
    from test_integrate import active

    repo = Repo(tmp_path / "repo")
    repo.write(
        "kb/ROLE-ROOT.md", canonical(active("role", "ROLE-ROOT", scopes=["operations"], capabilities=["ratify"]))
    )
    repo.write("kb/PER-D.md", serialize(person(), ""))
    base = repo.commit("root")
    repo.git("branch", "canon")
    res = call(repo, base, tmp_path / "receipts")
    assert res["state"] == "blocked" and "proposed" in res["reason"]


def test_changed_base_does_not_bootstrap(root):
    repo, base, receipts = root
    repo.git("checkout", "-q", "canon")
    repo.write("README.md", "y\n")
    other = repo.commit("other")
    repo.git("checkout", "-q", "main")
    res = call(repo, base, receipts)
    assert res["state"] == "blocked" and res["code"] == "BASE_CHANGED"
    assert repo.git("rev-parse", "canon") == other


def test_other_records_without_history_prevent_the_bootstrap(root):
    # After the bootstrap the integration loads the base in canonical mode: a hand-written proposal would block it.
    repo, base, receipts = root
    repo.git("checkout", "-q", "canon")
    repo.write("kb/DEC-P.md", serialize(record("decision", id="DEC-P", authorized_by=["ROLE-ROOT"]), DECISION_BODY))
    with_proposal = repo.commit("hand-written proposal")
    repo.git("checkout", "-q", "main")
    res = call(repo, with_proposal, receipts)
    assert res["state"] == "blocked" and "DEC-P" in res["reason"]
    assert repo.git("rev-parse", "canon") == with_proposal


def test_retiring_the_root_role_does_not_allow_a_second_bootstrap(tmp_path):
    from conftest import event
    from test_integrate import active

    repo = Repo(tmp_path / "repo")
    role = active("role", "ROLE-ROOT", **ROLE)
    role["events"].append(
        event(
            event_id="E2",
            previous_state="active",
            new_state="retired",
            recorded_at="2026-10-03T00:00:00Z",
            valid_from="2026-10-03T00:00:00Z",
        )
    )
    role["state"] = "retired"
    repo.write("kb/ROLE-ROOT.md", canonical(role))
    # Someone with write permission leaves a new proposed root, with another account.
    repo.write("kb/ROLE-2.md", serialize(record("role", id="ROLE-2", **ROLE), ""))
    other = person(id="PER-X", identity_ref="github:666", holds=[{"role": "ROLE-2", "from": "2026-10-01T00:00:00Z"}])
    repo.write("kb/PER-X.md", serialize(other, ""))
    base = repo.commit("retired root and new proposed root")
    repo.git("branch", "canon")
    res = call(repo, base, tmp_path / "r", person="PER-X", roles=["ROLE-2"], client=account(ident=666))
    assert res["state"] == "blocked" and res["code"] == "ROOT_ALREADY_ESTABLISHED"


def test_does_not_leave_a_base_the_integration_would_not_load(root):
    from conftest import event

    repo, base, receipts = root
    repo.git("checkout", "-q", "canon")
    # An admitted event, but a written state its history does not materialize: valid as a proposal, not as canonical.
    d = record(
        "decision",
        id="DEC-L",
        authorized_by=["ROLE-ROOT"],
        state="accepted",
        events=[event("creation", event_id="E0", previous_state=None, new_state="proposed")],
    )
    repo.write("kb/DEC-L.md", serialize(d, DECISION_BODY))
    base = repo.commit("decision with inconsistent history")
    repo.git("checkout", "-q", "main")
    res = call(repo, base, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA" and "canonical" in res["reason"]
    assert repo.git("rev-parse", "canon") == base and not (receipts / "bootstrap-1.json").exists()


def test_does_not_overwrite_a_receipt_nor_accept_malformed_inputs(root):
    repo, base, receipts = root
    receipts.mkdir()
    (receipts / "bootstrap-1.json").write_text("{}", encoding="utf-8")
    assert call(repo, base, receipts)["state"] == "blocked"
    assert (receipts / "bootstrap-1.json").read_text(encoding="utf-8") == "{}"
    assert call(repo, base, receipts, op="bootstrap-2", roles="ROLE-ROOT")["state"] == "blocked"
    assert repo.git("rev-parse", "canon") == base


def test_the_branch_changes_during_the_verification(root):
    repo, base, receipts = root

    class ClientThatMoves:
        def get(self, path):
            repo.git("checkout", "-q", "canon")
            repo.write("README.md", "race\n")
            self.other = repo.commit("concurrent write")
            repo.git("checkout", "-q", "main")
            return {"id": 101, "login": "david", "type": "User"}

    client = ClientThatMoves()
    res = call(repo, base, receipts, client=client)
    assert res["code"] == "BASE_CHANGED" and repo.git("rev-parse", "canon") == client.other
    assert not (receipts / "bootstrap-1.json").exists()


def test_after_the_bootstrap_nobody_takes_the_root_identity(root):
    # The proposal changes the root person's account to github:555 and approves with that account: with the policy
    # of the proposal it would pass; with the base's, which is the one that counts, github:555 is nobody.
    repo, base, receipts = root
    boot = call(repo, base, receipts)
    canon = boot["integrated_revision"]
    meta, body = read(repo, "kb/PER-D.md")
    prop = propose(repo, canon, {"kb/PER-D.md": canonical({**meta, "identity_ref": "github:555"}, body)})
    res = integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id="op-1",
        expected_base=canon,
        proposal_rev=prop,
        revisions=[REVISION],
        verifier=reviewed_after(verifier(prop, canon, user=555), boot["recorded_at"]),
        receipts=receipts,
    )
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY", res
    [revision] = res["authority"]["revisions"]
    assert "github:555 does not match a single active person in the base policy" in revision["reason"]
    assert repo.git("log", "-1", "--format=%ae", boot["integrated_revision"]) == "bootstrap@localhost"
