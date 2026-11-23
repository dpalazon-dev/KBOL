"""`decisive` approval mode: only what is decisive asks for approval; everything carries its actor.

Non-conforming local choice (docs/design-choices.md, "Non-conforming mechanisms"): what decides nothing (a new
proposal, a relation, starting a milestone, resolving a question) enters without approval, with the operation actor in
each event. Accepting or rejecting a decision, authorizing, closing or cancelling a plan or a milestone, changing people
or roles and importing a supersession or a closure still require the approval of whoever decides.
"""

# ruff: noqa: F811  (the environment fixture is imported from test_declared)

import json

from conftest import record
from test_declared import ACCEPT, acceptance, dec_x, declared_approval, environment  # noqa: F401
from test_integrate import propose, request

from kbol.core import parse, serialize
from kbol.declared import DeclaredVerifier
from kbol.integrate import ACTOR, integrate, is_decisive

AGENT = "claude-code/opus-5.5"


def call(repo, base, prop, receipts, revisions=(), op="op-1", actor=AGENT, approval="decisive"):
    return integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=list(revisions),
        verifier=DeclaredVerifier(repo.root),
        receipts=receipts,
        approval=approval,
        actor=actor,
    )


def question():
    return record("question", id="Q-N", owner="ROLE-OP"), "Text.\n"


def test_what_is_not_decisive_enters_without_approval_with_the_actor_in_each_event(environment):
    repo, base, receipts = environment
    r, c = question()
    prop = propose(repo, base, {"kb/Q-N.md": serialize(r, c)})
    res = call(repo, base, prop, receipts)
    assert res["state"] == "integrated", res
    assert res["decisive"] == [] and res["actor"] == AGENT and res["approval_mode"] == "decisive"
    meta, _ = parse(repo.git("show", "canon:kb/Q-N.md") + "\n")
    assert [e["event_type"] for e in meta["events"]] == ["creation"]
    assert meta["events"][0]["actor"] == AGENT
    message = repo.git("log", "-1", "--format=%B", "canon")
    assert f"Actor: {AGENT}" in message and "Approval: decisive" in message


def test_accepting_a_decision_without_approval_is_rejected_also_in_decisive_mode(environment):
    repo, base, receipts = environment
    res = call(repo, base, acceptance(repo, base), receipts)
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY"
    assert repo.git("rev-parse", "canon") == base


def test_accepting_with_the_approval_of_whoever_decides_integrates_and_ratifies(environment):
    repo, base, receipts = environment
    res = call(repo, base, acceptance(repo, base), receipts, [declared_approval(base)])
    assert res["state"] == "integrated", res
    assert res["decisive"] == ["DEC-X"]
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    types = [e["event_type"] for e in meta["events"]]
    assert types == ["creation", "ratification", "transition"] and meta["state"] == "accepted"
    rat = meta["events"][1]
    assert rat["actor"] == AGENT and rat["approval"]["actor"] == "human:PER-H"


def test_a_mixed_operation_only_ratifies_what_is_decisive(environment):
    repo, base, receipts = environment
    r, c = dec_x()
    q, cq = question()
    files = {
        "kb/DEC-X.md": serialize(r, c),
        "kb/Q-N.md": serialize(q, cq),
        **request("op-1", {"DEC-X": ACCEPT}),
    }
    res = call(repo, base, propose(repo, base, files), receipts, [declared_approval(base)])
    assert res["state"] == "integrated", res
    assert res["decisive"] == ["DEC-X"]
    meta, _ = parse(repo.git("show", "canon:kb/Q-N.md") + "\n")
    assert [e["event_type"] for e in meta["events"]] == ["creation"]


def test_the_usual_mode_still_asks_approval_for_everything(environment):
    repo, base, receipts = environment
    r, c = question()
    prop = propose(repo, base, {"kb/Q-N.md": serialize(r, c)})
    res = call(repo, base, prop, receipts, approval="all", actor=ACTOR)
    assert res["state"] == "blocked"


def test_invalid_actor_and_mode_are_rejected_without_writing(environment):
    repo, base, receipts = environment
    r, c = question()
    prop = propose(repo, base, {"kb/Q-N.md": serialize(r, c)})
    for kw in ({"actor": "someone without shape"}, {"actor": "x\ny/z"}, {"approval": "none"}):
        res = call(repo, base, prop, receipts, **kw)
        assert res["state"] == "blocked", kw
    assert repo.git("rev-parse", "canon") == base


def test_what_is_decisive():
    dec = {"type": "decision"}
    milestone = {"type": "milestone"}
    q = {"type": "question"}
    assert is_decisive("D", dec, {"D": [{"new_state": "accepted"}]}, [], {})
    assert is_decisive("H", milestone, {"H": [{"new_state": "authorized"}]}, [], {})
    assert not is_decisive("H", milestone, {"H": [{"new_state": "in_progress"}]}, [], {})
    assert not is_decisive("Q", q, {"Q": [{"new_state": "resolved"}]}, [], {})
    assert is_decisive("P", {"type": "person"}, {}, ["P"], {})
    assert is_decisive("P", {"type": "person"}, {"P": [{"new_state": "active"}]}, [], {})
    assert is_decisive("R", {"type": "role"}, {"R": [{"new_state": "retired"}]}, [], {})
    assert is_decisive("HE", {"type": "fact"}, {"HE": [{"new_state": "accepted"}]}, [], {})
    assert is_decisive("A", dec, {}, [], {"A": {"decisive": ["the legacy record declares what it supersedes"]}})
    assert is_decisive("A", {**dec, "supersedes": ["ADR-1"]}, {}, [], {"A": {}})
    assert not is_decisive("A", {**dec, "affects": ["ADR-1"]}, {}, [], {"A": {}})
    assert not is_decisive("A", {**dec, "supersedes": ["ADR-1"]}, {}, [], {})


def test_the_request_in_decisive_mode_has_another_fingerprint_than_the_usual_one(environment):
    """Repeating the operation in another mode does not reuse its receipt: the fingerprint includes the mode and the actor."""
    repo, base, receipts = environment
    r, c = question()
    prop = propose(repo, base, {"kb/Q-N.md": serialize(r, c)})
    first = call(repo, base, prop, receipts)
    assert first["state"] == "integrated"
    other = call(repo, base, prop, receipts, actor="process:other")
    assert other["state"] == "blocked"
    assert json.loads((receipts / "op-1.json").read_text(encoding="utf-8"))["actor"] == AGENT
