"""VAL-04 and ESC-03: the approval counts through verified identity, prior authority and the exact reviewed diff."""

import copy

import pytest
from conftest import DECISION_BODY, event, record

from kbol.authority import evaluate
from kbol.digest import digest
from kbol.github import GitHubClient, GitHubVerifier, VerificationError
from kbol.projection import Snapshot

EFFECTS = [{"previous_state": "proposed", "new_state": "accepted", "valid_from": "2026-11-05T00:00:00Z"}]
REV, BASE = "c" * 40, "b" * 40
REVISION = {"mechanism": "github-review", "pull": 1, "review_id": 11}


def active(type_, ident, **fields):
    ev = [
        event(
            "creation",
            event_id="E0",
            previous_state=None,
            new_state="proposed",
            recorded_at="2026-10-01T00:00:00Z",
            valid_from="2026-10-01T00:00:00Z",
        ),
        event(
            event_id="E1",
            previous_state="proposed",
            new_state="active",
            recorded_at="2026-10-02T00:00:00Z",
            valid_from="2026-10-02T00:00:00Z",
        ),
    ]
    return record(type_, id=ident, state="active", events=ev, **fields)


def human(ident="PER-H", account=101, roles=("ROLE-OP",), until=None):
    holds = [{"role": r, "from": "2026-10-02T00:00:00Z", **({"until": until} if until else {})} for r in roles]
    return active("person", ident, nature="human", identity_ref=f"github:{account}", holds=holds)


def policy(*extra):
    role = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    agent = active("person", "PER-AG", nature="agent", identity_ref="github:900", holds=[])
    regs = {r["id"]: r for r in (role, human(), agent)}
    regs.update({r["id"]: r for r in extra})
    return Snapshot(regs, "base1")


def proposal(**changes):
    return record("decision", id="DEC-X", authorized_by=["ROLE-OP"], **changes)


class Client(GitHubClient):
    """Replaces only the HTTP call: the rest of the verifier is the real one."""

    def __init__(self, responses):
        super().__init__(token="t")
        self.responses = responses
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        return copy.deepcopy(self.responses[path])


def github_responses(revisions, head, base, ref="main", timeline=()):
    """API responses for PR 1: the PR, its reviews in order and its timeline."""
    return {
        "/repos/o/r/pulls/1": {"head": {"sha": head}, "base": {"sha": base, "ref": ref}},
        "/repos/o/r/pulls/1/reviews?per_page=100&page=1": [{"id": k, **v} for k, v in revisions.items()],
        "/repos/o/r/issues/1/timeline?per_page=100&page=1": list(timeline),
    }


def verifier(revisions=None, head=REV, base=BASE, **kw):
    client = Client(github_responses(revisions or {11: review()}, head, base, **kw))
    return GitHubVerifier(client, "o/r", "main")


def review(user=101, state="APPROVED", commit=REV, when="2026-11-04T10:00:00Z"):
    return {"user": {"id": user}, "state": state, "commit_id": commit, "submitted_at": when}


def evaluate_x(r=None, body=DECISION_BODY, effects=EFFECTS, revisions=(REVISION,), pol=None, ver=None, **kw):
    r = r or proposal()
    return evaluate(r, body, effects, list(revisions), pol or policy(), ver or verifier(), REV, BASE, **kw)


def test_esc03_1_verified_written_by_the_agent_is_not_an_approval():
    r = proposal(verified=[{"by": "human:david", "at": "2026-11-04T10:00:00Z", "digest": "a" * 64}])
    res = evaluate_x(r, revisions=[])
    assert res["authorized"] is False and res["code"] == "INSUFFICIENT_AUTHORITY"


def test_esc03_2_approval_through_trusted_channel_with_verified_data():
    res = evaluate_x()
    assert res["authorized"] is True and res["code"] is None
    (ap,) = res["approvals"]
    assert ap == {
        "approval_id": "github-review:o/r#1/11",
        "actor": "human:PER-H",
        "identity_ref": "github:101",
        "roles": ["ROLE-OP"],
        "digest": digest(proposal(), DECISION_BODY, EFFECTS),
        "base_revision": BASE,
        "approved_at": "2026-11-04T10:00:00Z",
        "policy_revision": "base1",
        "proof": {"mechanism": "github-review", "repository": "o/r", "pull": 1, "review_id": 11},
    }


@pytest.mark.parametrize("ver", [dict(head="d" * 40), dict(revisions={11: review(commit="d" * 40)})])
def test_esc03_3_content_changed_after_review_goes_stale(ver):
    res = evaluate_x(ver=verifier(**ver))
    assert res["authorized"] is False and res["code"] == "STALE_APPROVAL"


def test_the_pr_must_compare_against_the_expected_base():
    res = evaluate_x(ver=verifier(base="e" * 40))
    assert res["authorized"] is False and res["code"] == "INSUFFICIENT_AUTHORITY"


def test_esc03_4_an_agent_does_not_ratify():
    res = evaluate_x(ver=verifier({11: review(user=900)}))
    assert res["authorized"] is False
    agent = active(
        "person",
        "PER-AG",
        nature="agent",
        identity_ref="github:900",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    res = evaluate_x(pol=policy(agent), ver=verifier({11: review(user=900)}))
    assert res["authorized"] is False and res["revisions"][0]["reason"] == "an agent does not ratify"


def test_account_without_person_in_the_policy():
    assert evaluate_x(ver=verifier({11: review(user=555)}))["authorized"] is False


@pytest.mark.parametrize("state", ["CHANGES_REQUESTED", "DISMISSED", "COMMENTED"])
def test_non_approving_review(state):
    assert evaluate_x(ver=verifier({11: review(state=state)}))["authorized"] is False


def test_review_without_valid_instant():
    assert evaluate_x(ver=verifier({11: review(when=None)}))["authorized"] is False
    assert evaluate_x(ver=verifier({11: review(when="yesterday")}))["authorized"] is False


def test_role_outside_scope_and_expired_holding():
    assert evaluate_x(proposal(scope="finance"))["authorized"] is False
    expired = human(until="2026-11-01T00:00:00Z")
    assert evaluate_x(pol=policy(expired))["authorized"] is False


def test_revocation_between_review_and_integration():
    # Held the role when reviewing (10:00) but no longer when integrating (13:00): revalidated when integrating.
    ends = human(until="2026-11-04T12:00:00Z")
    assert evaluate_x(pol=policy(ends))["authorized"] is True
    res = evaluate_x(pol=policy(ends), revalidate_at="2026-11-04T13:00:00Z")
    assert res["authorized"] is False


def test_only_the_roles_held_count():
    gov = active("role", "ROLE-GOV", scopes=["system"], capabilities=["govern_policy"], approval_rule="one")
    (ap,) = evaluate_x(pol=policy(gov))["approvals"]
    assert ap["roles"] == ["ROLE-OP"]


def test_all_and_quorum_rules():
    h2 = human("PER-H2", 102)
    v = verifier({11: review(), 13: review(user=102)})
    all_rule = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="all")
    other = {**REVISION, "review_id": 13}
    assert evaluate_x(pol=policy(all_rule, h2), ver=v)["authorized"] is False
    assert evaluate_x(pol=policy(all_rule, h2), ver=v, revisions=[REVISION, other])["authorized"] is True
    quorum = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule={"quorum": 2})
    repeated = evaluate_x(pol=policy(quorum, h2), ver=v, revisions=[REVISION, REVISION])
    assert repeated["authorized"] is False  # the same person does not count twice


def test_policy_change_requires_governance_role():
    gov = active("role", "ROLE-GOV", scopes=["system"], capabilities=["govern_policy"], approval_rule="one")
    new_role = record("role", id="ROLE-NEW", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    effects = [{"previous_state": "proposed", "new_state": "active", "valid_from": "2026-11-05T00:00:00Z"}]
    assert evaluate_x(new_role, "", effects, pol=policy(gov))["authorized"] is False
    with_gov = evaluate_x(new_role, "", effects, pol=policy(gov, human(roles=("ROLE-OP", "ROLE-GOV"))))
    assert with_gov["authorized"] is True and with_gov["approvals"][0]["roles"] == ["ROLE-GOV"]


def test_without_token_the_verifier_is_not_enabled(monkeypatch):
    monkeypatch.delenv("KB_GITHUB_TOKEN", raising=False)
    with pytest.raises(VerificationError, match="not enabled"):
        GitHubClient.from_environment()
    assert "SECRET-123" not in repr(GitHubClient("SECRET-123"))


@pytest.mark.parametrize("repo", ["o/r/tarball/main?", "o", "../x/y", "o/r#1"])
def test_configured_repository_validated(repo):
    with pytest.raises(VerificationError):
        GitHubVerifier(Client({}), repo, "main")


def test_approval_later_withdrawn_by_the_same_person_does_not_count():
    # GitHub counts the last stance of each account: citing the old approval does not help.
    v = verifier({11: review(), 12: review(state="CHANGES_REQUESTED", when="2026-11-04T11:00:00Z")})
    res = evaluate_x(ver=v)
    assert res["authorized"] is False and "changed or withdrew" in res["revisions"][0]["reason"]
    # A later comment does not change the stance.
    v = verifier({11: review(), 12: review(state="COMMENTED", when="2026-11-04T11:00:00Z")})
    assert evaluate_x(ver=v)["authorized"] is True


def test_pr_against_another_branch_or_with_base_changed_later():
    assert evaluate_x(ver=verifier(ref="other"))["authorized"] is False
    change = [{"event": "base_ref_changed", "created_at": "2026-11-04T12:00:00Z"}]
    assert evaluate_x(ver=verifier(timeline=change))["authorized"] is False
    before = [{"event": "base_ref_changed", "created_at": "2026-11-04T09:00:00Z"}]
    assert evaluate_x(ver=verifier(timeline=before))["authorized"] is True


def test_review_not_in_the_pr():
    assert evaluate_x(revisions=[{**REVISION, "review_id": 99}])["authorized"] is False


def test_review_pagination():
    many = {2000 + i: review(user=1000 + i, state="COMMENTED") for i in range(100)}
    responses = github_responses(many, REV, BASE)
    responses["/repos/o/r/pulls/1/reviews?per_page=100&page=2"] = [{"id": 11, **review()}]
    del many
    client = Client(responses)
    res = evaluate_x(ver=GitHubVerifier(client, "o/r", "main"))
    assert res["authorized"] is True and "/repos/o/r/pulls/1/reviews?per_page=100&page=2" in client.calls


def test_repeated_review_counts_once():
    res = evaluate_x(revisions=[REVISION, dict(REVISION)])
    assert res["authorized"] is True and len(res["approvals"]) == 1


@pytest.mark.parametrize(
    "ref",
    [
        {"mechanism": "other", "pull": 1, "review_id": 11},
        {"mechanism": "github-review", "pull": "1", "review_id": 11},
        "text",
    ],
)
def test_malformed_review_reference(ref):
    assert evaluate_x(revisions=[ref])["authorized"] is False
