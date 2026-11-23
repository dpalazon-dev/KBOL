"""Declared approval (RES-02 partial): the person approves in the conversation and the agent quotes their words.

The verifier authenticates nobody: it accepts the declared identity and says so in the proof. What the integration
does check is the same as with any channel: that the approval covers exactly what is integrated (the digests shown),
that the person is human, active and holds the role in the base policy, and that the base shown precedes the current
one.
"""

import json

import pytest
from conftest import DECISION_BODY, decision, record
from test_integrate import ACCEPT, Repo, active, canonical, propose, request

from kbol.consolidate import consolidate
from kbol.core import parse, serialize
from kbol.declared import MECHANISM, DeclaredVerifier
from kbol.digest import digest
from kbol.integrate import integrate
from kbol.schema import validate
from kbol.snapshot import load
from kbol.verification import VerificationError

INSTANT = "2026-11-05T18:00:00Z"
QUOTE = "I approve accepting DEC-X as it is"


@pytest.fixture
def environment(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.write("README.md", "x\n")
    role = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    per = active(
        "person",
        "PER-H",
        nature="human",
        identity_ref="declared:h",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    no_role = active("person", "PER-N", nature="human", identity_ref="declared:n", holds=[])
    ag = active(
        "person",
        "PER-AG",
        nature="agent",
        identity_ref="declared:agent",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    a, ca = decision("DEC-A", {"C1": "Monday."}, recorded="2026-10-03T00:00:00Z", authorized_by=["ROLE-OP"])
    for ident, r, c in (("ROLE-OP", role, ""), ("PER-H", per, ""), ("PER-N", no_role, ""), ("PER-AG", ag, "")):
        repo.write(f"kb/{ident}.md", canonical(r, c))
    repo.write("kb/DEC-A.md", canonical(a, ca))
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def dec_x():
    return record("decision", id="DEC-X", authorized_by=["ROLE-OP"]), DECISION_BODY


def acceptance(repo, base, op="op-1"):
    r, c = dec_x()
    return propose(repo, base, {"kb/DEC-X.md": serialize(r, c), **request(op, {"DEC-X": ACCEPT})})


def declared_approval(base, identity="declared:h", digests=None, **changes):
    revision = {
        "mechanism": MECHANISM,
        "identity": identity,
        "session": "Claude Code session kbol-e9",
        "instant": INSTANT,
        "quote": QUOTE,
        "base_shown": base,
        "digests": {"DEC-X": digest(*dec_x(), ACCEPT)} if digests is None else digests,
    }
    revision.update(changes)
    return revision


def call(repo, base, prop, receipts, revisions, op="op-1"):
    return integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=revisions,
        verifier=DeclaredVerifier(repo.root),
        receipts=receipts,
    )


def test_declared_approval_integrates_and_leaves_the_quote_in_ratification_receipt_and_trailer(environment):
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    res = call(repo, base, prop, receipts, [declared_approval(base)])
    assert res["state"] == "integrated", res
    meta, body = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert meta["state"] == "accepted"
    assert validate(meta, body, mode="canonical") == []
    ratification = next(e for e in meta["events"] if e["event_type"] == "ratification")
    ap = ratification["approval"]
    assert ap["actor"] == "human:PER-H" and ap["identity_ref"] == "declared:h"
    assert ap["proof"]["quote"] == QUOTE and ap["proof"]["authenticated"] is False
    assert ap["approved_at"] == INSTANT
    assert ratification["event_evidence"]["mechanism"] == MECHANISM
    assert QUOTE in ratification["event_evidence"]["proof"]
    assert "not authenticated" in ratification["event_evidence"]["proof"]
    receipt = json.loads((receipts / "op-1.json").read_text(encoding="utf-8"))
    details = receipt["approval_details"]
    assert len(details) == 1 and details[0]["proof"]["quote"] == QUOTE
    message = repo.git("log", "-1", "--format=%B", "canon")
    revisions = next(line for line in message.splitlines() if line.startswith("Reviews: "))
    assert revisions == f"Reviews: {ap['approval_id']}" and "\n" not in ap["approval_id"]
    assert ap["approval_id"].startswith(f"{MECHANISM}:")


def test_consolidate_says_what_is_in_force_relies_on_a_declared_approval(environment):
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    res = call(repo, base, prop, receipts, [declared_approval(base)])
    snap, coverage = load(repo.root, "kb", res["integrated_revision"])
    assert coverage["state"] == "complete", coverage
    output = consolidate(snap, ["DEC-X"], valid_at="2026-11-06T00:00:00Z", known_until=None)
    clause = next(c for c in output["clauses"] if c["reference"] == "DEC-X#C1")
    authority = clause["authority"]
    assert authority["checked"] is False
    assert authority["declared"] == authority["ratifications"] and len(authority["declared"]) == 1


def test_a_proposal_without_effects_leaves_the_approval_in_receipt_and_trailer_without_ratifying(environment):
    repo, base, receipts = environment
    r, c = dec_x()
    prop = propose(repo, base, {"kb/DEC-X.md": serialize(r, c)})
    res = call(repo, base, prop, receipts, [declared_approval(base, digests={"DEC-X": digest(r, c, [])})])
    assert res["state"] == "integrated", res
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert [e["event_type"] for e in meta["events"]] == ["creation"]
    receipt = json.loads((receipts / "op-1.json").read_text(encoding="utf-8"))
    assert receipt["approval_details"][0]["proof"]["quote"] == QUOTE


def test_digests_different_from_what_was_shown_make_the_approval_stale(environment):
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    res = call(repo, base, prop, receipts, [declared_approval(base, digests={"DEC-X": "0" * 64})])
    assert res["state"] == "blocked" and res["code"] == "STALE_APPROVAL", res
    assert repo.git("rev-parse", "canon") == base


def test_a_touched_record_without_a_shown_digest_is_not_approved(environment):
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    res = call(repo, base, prop, receipts, [declared_approval(base, digests={})])
    assert res["state"] == "blocked" and res["code"] == "STALE_APPROVAL", res


def test_a_shown_base_that_does_not_precede_the_current_one_does_not_count(environment):
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    foreign = propose(repo, base, {"README.md": "other\n"})
    res = call(repo, base, prop, receipts, [declared_approval(foreign)])
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY", res


@pytest.mark.parametrize("identity", ["declared:n", "declared:agent", "declared:nobody"])
def test_without_role_agent_or_unknown_does_not_approve(environment, identity):
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    res = call(repo, base, prop, receipts, [declared_approval(base, identity=identity)])
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY", res


def test_a_person_does_not_grant_herself_the_role_she_uses_to_approve(environment):
    repo, base, receipts = environment
    meta, body = parse(repo.git("show", f"{base}:kb/PER-N.md") + "\n")
    meta["holds"] = [{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}]
    r, c = dec_x()
    files = {"kb/PER-N.md": serialize(meta, body, mode="canonical"), "kb/DEC-X.md": serialize(r, c)}
    prop = propose(repo, base, {**files, **request("op-1", {"DEC-X": ACCEPT})})
    digests = {"DEC-X": digest(r, c, ACCEPT), "PER-N": digest(meta, body, [])}
    res = call(repo, base, prop, receipts, [declared_approval(base, identity="declared:n", digests=digests)])
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY", res


@pytest.mark.parametrize(
    "change",
    [
        {"mechanism": "github-review"},
        {"identity": "h"},
        {"identity": "declared:"},
        {"session": ""},
        {"quote": "  "},
        {"instant": "2026-11-05"},
        {"instant": "2026-11-05T18:00:00"},
        {"base_shown": "abc"},
        {"digests": ["DEC-X"]},
        {"digests": {"DEC-X": "short"}},
    ],
)
def test_a_malformed_approval_is_not_verified(environment, change):
    repo, base, _ = environment
    with pytest.raises(VerificationError):
        DeclaredVerifier(repo.root).verify(declared_approval(base, **change), base, base)


def test_the_same_approval_with_digests_in_another_order_counts_once(environment):
    repo, base, receipts = environment
    r, c = dec_x()
    other = {**dec_x()[0], "id": "DEC-Y"}
    files = {"kb/DEC-X.md": serialize(r, c), "kb/DEC-Y.md": serialize(other, c)}
    prop = propose(repo, base, {**files, **request("op-1", {"DEC-X": ACCEPT})})
    one = {"DEC-X": digest(r, c, ACCEPT), "DEC-Y": digest(other, c, [])}
    two = {"DEC-Y": one["DEC-Y"], "DEC-X": one["DEC-X"]}
    res = call(repo, base, prop, receipts, [declared_approval(base, digests=one), declared_approval(base, digests=two)])
    assert res["state"] == "integrated", res
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert [e["event_type"] for e in meta["events"]].count("ratification") == 1


def test_an_instant_in_the_future_is_not_verified(environment):
    repo, base, _ = environment
    with pytest.raises(VerificationError):
        DeclaredVerifier(repo.root).verify(declared_approval(base, instant="2999-01-01T00:00:00Z"), base, base)


def test_without_repository_the_verifier_is_not_created():
    with pytest.raises(VerificationError):
        DeclaredVerifier(None)


def test_the_proof_never_says_it_is_authenticated(environment):
    repo, base, _ = environment
    v = DeclaredVerifier(repo.root).verify(declared_approval(base), base, base)
    assert v["proof"]["authenticated"] is False and v["identity"] == "declared:h"
    assert v["instant"] == INSTANT and v["digests"] == declared_approval(base)["digests"]
