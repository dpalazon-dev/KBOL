"""RES-02 and RES-06: controlled local integration, with idempotent receipts and rejection on a changed base (ESC-03.5)."""

import copy
import hashlib
import json
import subprocess

import pytest
from conftest import DECISION_BODY, body_of, decision, event, record

from kbol.core import parse, serialize
from kbol.digest import canonical_bytes, digest
from kbol.github import GitHubClient, GitHubVerifier
from kbol.integrate import integrate
from kbol.schema import validate

ACCEPT = [{"previous_state": "proposed", "new_state": "accepted", "valid_from": "2026-11-05T00:00:00Z"}]
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
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


class Repo:
    def __init__(self, root):
        self.root = root
        self.n = 0
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.root), *IDENT, *args], capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def write(self, path, text):
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")


def canonical(r, c=""):
    return serialize(r, c, mode="canonical")


@pytest.fixture
def environment(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.write("README.md", "x\n")
    repo.write("notes/guide.md", "---\ntype: Guide\ntitle: g\n---\nGuide.\n")
    role = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    per = active(
        "person",
        "PER-H",
        nature="human",
        identity_ref="github:101",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    ag = active("person", "PER-AG", nature="agent", identity_ref="github:900", holds=[])
    no_role = active("person", "PER-N", nature="human", identity_ref="github:300", holds=[])
    repo.write("kb/PER-N.md", canonical(no_role))
    a, ca = decision("DEC-A", {"C1": "Monday."}, recorded="2026-10-03T00:00:00Z", authorized_by=["ROLE-OP"])
    repo.write("kb/ROLE-OP.md", canonical(role))
    repo.write("kb/PER-H.md", canonical(per))
    repo.write("kb/PER-AG.md", canonical(ag))
    repo.write("kb/DEC-A.md", canonical(a, ca))
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def propose(repo, base, files, message="proposal", move=None):
    repo.n += 1
    repo.git("checkout", "-q", "-b", f"p{repo.n}", base)
    if move:
        repo.git("mv", *move)
    for path, text in files.items():
        repo.write(path, text)
    rev = repo.commit(message)
    repo.git("checkout", "-q", "main")
    return rev


def request(op, effects):
    return {f"kb/_requests/{op}.json": json.dumps({"operation_id": op, "effects": effects})}


class Client(GitHubClient):
    def __init__(self, responses, on_call=None):
        super().__init__(token="t")
        self.responses = responses
        self.on_call = on_call

    def get(self, path):
        if self.on_call:
            self.on_call()
            self.on_call = None
        return copy.deepcopy(self.responses[path])


def verifier(head, base, user=101, commit=None, on_call=None):
    revision = {
        "id": 11,
        "user": {"id": user},
        "state": "APPROVED",
        "commit_id": commit or head,
        "submitted_at": "2026-11-04T10:00:00Z",
    }
    responses = {
        "/repos/o/r/pulls/1": {"head": {"sha": head}, "base": {"sha": base, "ref": "canon"}},
        "/repos/o/r/pulls/1/reviews?per_page=100&page=1": [revision],
        "/repos/o/r/issues/1/timeline?per_page=100&page=1": [],
    }
    return GitHubVerifier(Client(responses, on_call), "o/r", "canon")


def dec_x():
    return record("decision", id="DEC-X", authorized_by=["ROLE-OP"]), DECISION_BODY


def prepare_acceptance(repo, base, op="op-1"):
    r, c = dec_x()
    return propose(repo, base, {"kb/DEC-X.md": serialize(r, c), **request(op, {"DEC-X": ACCEPT})})


def call(repo, base, prop, receipts, op="op-1", revisions=None, ver=None, **kw):
    arguments = dict(
        branch="canon",
        folder="kb",
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=[REVISION] if revisions is None else revisions,
        verifier=ver or verifier(prop, base),
        receipts=receipts,
    )
    arguments.update(kw)
    return integrate(repo.root, **arguments)


def test_valid_integration_with_receipt_and_without_touching_the_tree(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    head_before = repo.git("rev-parse", "HEAD")
    res = call(repo, base, prop, receipts)
    assert res["state"] == "integrated", res
    canon = repo.git("rev-parse", "canon")
    assert res["integrated_revision"] == canon and canon not in (base, prop)
    assert repo.git("rev-parse", "HEAD") == head_before and repo.git("status", "--porcelain") == ""
    # Flattened: a single parent, the base; the history of the proposal does not enter the canonical branch.
    assert repo.git("log", "-1", "--format=%P", "canon").split() == [base]
    message = repo.git("log", "-1", "--format=%B", "canon")
    assert (
        f"Operation-Id: op-1\nRequest-Sha256: {res['request_sha256']}\nBase: {base}\nProposal: {prop}" in message
    )
    assert "Reviews: github-review:o/r#1/11" in message
    meta, body = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert meta["state"] == "accepted"
    assert [e["event_type"] for e in meta["events"]] == ["creation", "ratification", "transition"]
    ap = meta["events"][1]["approval"]
    assert ap["actor"] == "human:PER-H" and ap["roles"] == ["ROLE-OP"] and ap["base_revision"] == base
    assert ap["digest"] == digest(*dec_x(), ACCEPT)
    assert meta["events"][2]["valid_from"] == "2026-11-05T00:00:00Z"
    assert validate(meta, body, mode="canonical") == []
    receipt = json.loads((receipts / "op-1.json").read_text(encoding="utf-8"))
    assert receipt["integrated_revision"] == canon and receipt["records"] == ["DEC-X"]
    assert set(receipt["impact"]) >= {"affected", "warnings"}


def test_esc03_5_repeating_the_operation_returns_the_receipt_without_second_acceptance(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    first = call(repo, base, prop, receipts)
    second = call(repo, base, prop, receipts)
    assert second["state"] == "integrated" and second["repeated"] is True
    assert second["integrated_revision"] == first["integrated_revision"] == repo.git("rev-parse", "canon")


def test_lost_response_is_reconciled_from_the_commit(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    first = call(repo, base, prop, receipts)
    (receipts / "op-1.json").unlink()
    other = call(repo, base, prop, receipts)
    assert other["state"] == "integrated" and other["reconciled"] is True
    assert other["integrated_revision"] == first["integrated_revision"] == repo.git("rev-parse", "canon")
    assert other["records"] == ["DEC-X"] and "affected" in other["impact"]


def test_same_id_with_another_request_is_rejected_without_writing(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    call(repo, base, prop, receipts)
    canon = repo.git("rev-parse", "canon")
    res = call(repo, base, prop, receipts, revisions=[REVISION, {**REVISION, "review_id": 12}])
    assert res["state"] == "blocked" and "was already used with another request" in res["reason"]
    assert repo.git("rev-parse", "canon") == canon


def test_forged_receipt_does_not_count(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    call(repo, base, prop, receipts)
    path = receipts / "op-1.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**receipt, "integrated_revision": "0" * 40}), encoding="utf-8")
    res = call(repo, base, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "UNKNOWN_RESULT"


def test_forged_trailer_in_the_proposal_does_not_reconcile(environment):
    # The proposal carries in its message a trailer with the real fingerprint of an invented op-7 request.
    repo, base, receipts = environment
    r, c = dec_x()
    invented = "b" * 40
    req = {"branch": "canon", "folder": "kb", "base": base, "proposal": invented, "revisions": [REVISION]}
    fingerprint = hashlib.sha256(canonical_bytes(req)).hexdigest()
    fake = f"proposal\n\nOperation-Id: op-7\nRequest-Sha256: {fingerprint}\nBase: {base}\nProposal: {invented}\n"
    prop = propose(
        repo, base, {"kb/DEC-X.md": serialize(r, c), **request("op-1", {"DEC-X": ACCEPT})}, message=fake
    )
    assert call(repo, base, prop, receipts)["state"] == "integrated"
    other = call(repo, base, invented, receipts, op="op-7")
    # Not reconciled: the fake commit is neither the integrator's nor on the mainline. The normal gate follows.
    assert other["state"] == "blocked" and other["code"] == "BASE_CHANGED" and not other.get("reconciled")
    assert not (receipts / "op-7.json").exists()


def test_changed_base_does_not_integrate(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    other_rev = propose(
        repo,
        base,
        {"kb/DEC-Z.md": serialize(record("decision", id="DEC-Z", authorized_by=["ROLE-OP"]), DECISION_BODY)},
    )
    repo.git("update-ref", "refs/heads/canon", other_rev, base)
    res = call(repo, base, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "BASE_CHANGED"
    assert repo.git("rev-parse", "canon") == other_rev and not receipts.exists()


def test_symbolic_expected_base_is_rejected(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    res = call(repo, base, prop, receipts, expected_base="canon")
    assert res["state"] == "blocked" and "SHA" in res["reason"]


def test_content_changed_after_the_review(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    res = call(repo, base, prop, receipts, ver=verifier(prop, base, commit=base))
    assert res["state"] == "blocked" and res["code"] == "STALE_APPROVAL"
    assert repo.git("rev-parse", "canon") == base


def test_the_branch_changes_during_verification(environment):
    # Another write moves canon while the reviews are verified: the compare-and-swap fails and nothing is written.
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    other_rev = propose(
        repo,
        base,
        {"kb/DEC-Z.md": serialize(record("decision", id="DEC-Z", authorized_by=["ROLE-OP"]), DECISION_BODY)},
    )

    def move():
        repo.git("update-ref", "refs/heads/canon", other_rev, base)

    res = call(repo, base, prop, receipts, ver=verifier(prop, base, on_call=move))
    assert res["state"] == "blocked" and res["code"] == "BASE_CHANGED"
    assert repo.git("rev-parse", "canon") == other_rev and not (receipts / "op-1.json").exists()


def test_esc03_4_a_person_does_not_grant_herself_the_role_she_uses_to_approve(environment):
    # Active human without a role in the base: the proposal gives her ROLE-OP and accepts DEC-X with her review. The previous policy applies.
    repo, base, receipts = environment
    meta, body = parse(repo.git("show", f"{base}:kb/PER-N.md") + "\n")
    meta["holds"] = [{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}]
    r, c = dec_x()
    files = {"kb/PER-N.md": serialize(meta, body, mode="canonical"), "kb/DEC-X.md": serialize(r, c)}
    prop = propose(repo, base, {**files, **request("op-1", {"DEC-X": ACCEPT})})
    res = call(repo, base, prop, receipts, ver=verifier(prop, base, user=300))
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY"
    assert repo.git("rev-parse", "canon") == base


def test_without_reviews_there_is_no_integration(environment):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    res = call(repo, base, prop, receipts, revisions=[])
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY"


def test_a_proposal_without_effects_also_needs_a_review(environment):
    repo, base, receipts = environment
    r, c = dec_x()
    prop = propose(repo, base, {"kb/DEC-X.md": serialize(r, c)})
    assert call(repo, base, prop, receipts, revisions=[])["state"] == "blocked"
    res = call(repo, base, prop, receipts)
    assert res["state"] == "integrated", res
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert meta["state"] == "proposed" and [e["event_type"] for e in meta["events"]] == ["creation"]


def test_esc03_4_the_agent_does_not_grant_itself_the_role_and_accept_in_the_same_operation(environment):
    repo, base, receipts = environment
    text = repo.git("show", f"{base}:kb/PER-AG.md") + "\n"
    meta, body = parse(text)
    meta["holds"] = [{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}]
    r, c = dec_x()
    files = {"kb/PER-AG.md": serialize(meta, body, mode="canonical"), "kb/DEC-X.md": serialize(r, c)}
    prop = propose(repo, base, {**files, **request("op-1", {"DEC-X": ACCEPT})})
    res = call(repo, base, prop, receipts, ver=verifier(prop, base, user=900))
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY"
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize(
    "files,move",
    [
        ({"README.md": "changed\n"}, None),
        ({}, ("notes/guide.md", "kb/guide.md")),  # a rename deletes the source
        ({"kb/note.md": "---\ntype: Guide\ntitle: x\n---\n"}, None),  # .md that is not a record of the profile
        ({"kb/index.md": "* [x](x.md)\n"}, None),
    ],
)
def test_only_records_of_the_folder(environment, files, move):
    repo, base, receipts = environment
    r, c = dec_x()
    prop = propose(repo, base, {"kb/DEC-X.md": serialize(r, c), **files}, move=move)
    res = call(repo, base, prop, receipts)
    assert res["state"] == "blocked", res
    assert repo.git("rev-parse", "canon") == base


def test_accepted_clause_rewritten(environment):
    repo, base, receipts = environment
    text = repo.git("show", f"{base}:kb/DEC-A.md") + "\n"
    clause = '<clause id="C1">\nMonday.\n</clause>'
    assert text.count(clause) == 1
    prop = propose(repo, base, {"kb/DEC-A.md": text.replace(clause, clause.replace("Monday.", "Tuesday."))})
    res = call(repo, base, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "INVALID_SCHEMA"
    assert [h["path"] for h in res["findings"]] == ["DEC-A/body"]


def test_two_accepted_replacements_of_the_same_clause_are_a_conflict(environment):
    repo, base, receipts = environment
    files = {}
    for ident, text in (("DEC-B", "Tuesday."), ("DEC-D", "Thursday.")):
        r = record(
            "decision",
            id=ident,
            authorized_by=["ROLE-OP"],
            amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": f"{ident}#C1"}],
        )
        files[f"kb/{ident}.md"] = serialize(r, body_of({"C1": text}))
    prop = propose(repo, base, {**files, **request("op-1", {"DEC-B": ACCEPT, "DEC-D": ACCEPT})})
    res = call(repo, base, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "NORMATIVE_CONFLICT"
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize("branch", ["main", "CANON", "alias"])
def test_branch_in_use_symbolic_or_with_another_name(environment, branch):
    repo, base, receipts = environment
    repo.git("symbolic-ref", "refs/heads/alias", "refs/heads/canon")
    prop = prepare_acceptance(repo, base)
    try:
        head = repo.git("rev-parse", branch)
    except subprocess.CalledProcessError:
        # `CANON` only names `canon` where refs are case-insensitive (Windows, macOS).
        pytest.skip("refs are case-sensitive: there is no other name to test")
    res = call(repo, head, prop, receipts, branch=branch)
    assert res["state"] == "blocked"
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize("op", ["../outside", "a/b", "", "x" * 200])
def test_safe_operation_id(environment, op):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    assert call(repo, base, prop, receipts, op=op)["state"] == "blocked"


@pytest.mark.parametrize("folder", ["kb/..", ".", ":/", "kb\\x", "/kb"])
def test_safe_folder(environment, folder):
    repo, base, receipts = environment
    prop = prepare_acceptance(repo, base)
    assert call(repo, base, prop, receipts, folder=folder)["state"] == "blocked"


def test_request_of_another_operation_does_not_count(environment):
    repo, base, receipts = environment
    r, c = dec_x()
    prop = propose(repo, base, {"kb/DEC-X.md": serialize(r, c), **request("op-2", {"DEC-X": ACCEPT})})
    res = call(repo, base, prop, receipts, op="op-1")
    assert res["state"] == "blocked"  # the op-2 file is neither a record nor the op-1 request


def _base_with(repo, base, files):
    """Moves canon to a commit with already canonical records, as if they had been integrated before."""
    new = propose(repo, base, files)
    repo.git("update-ref", "refs/heads/canon", new, base)
    return new


def _replaces_a1(ident, text):
    return record(
        "decision",
        id=ident,
        authorized_by=["ROLE-OP"],
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": f"{ident}#C1"}],
    ), body_of({"C1": text})


def test_conflict_with_an_existing_decision_that_comes_into_force_later(environment):
    # DEC-E, already integrated, replaces DEC-A#C1 from 10 Dec. The new DEC-N replaces it from 1 Dec.
    # On 1 Dec there is no conflict; from 10 Dec both are in force without a declared succession.
    repo, base, receipts = environment
    e, ce = decision(
        "DEC-E",
        {"C1": "Thursday."},
        recorded="2026-10-04T00:00:00Z",
        valid="2026-12-10T00:00:00Z",
        authorized_by=["ROLE-OP"],
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-E#C1"}],
    )
    base2 = _base_with(repo, base, {"kb/DEC-E.md": canonical(e, ce)})
    n, cn = _replaces_a1("DEC-N", "Tuesday.")
    from_1 = [{**ACCEPT[0], "valid_from": "2026-12-01T00:00:00Z"}]
    prop = propose(repo, base2, {"kb/DEC-N.md": serialize(n, cn), **request("op-1", {"DEC-N": from_1})})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "NORMATIVE_CONFLICT", res
    assert res["conflicts"][0]["clause"] == "DEC-A#C1"
    assert repo.git("rev-parse", "canon") == base2 and not (receipts / "op-1.json").exists()


def test_unrelated_previous_conflict_does_not_block_another_integration(environment):
    # The base already carries a conflict between DEC-E and DEC-F; a proposal that does not touch it is integrated and warns about it.
    repo, base, receipts = environment
    files = {}
    for ident, text in (("DEC-E", "Thursday."), ("DEC-F", "Friday.")):
        r, c = decision(
            ident,
            {"C1": text},
            recorded="2026-10-04T00:00:00Z",
            authorized_by=["ROLE-OP"],
            amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": f"{ident}#C1"}],
        )
        files[f"kb/{ident}.md"] = canonical(r, c)
    base2 = _base_with(repo, base, files)
    r, c = dec_x()
    prop = propose(repo, base2, {"kb/DEC-X.md": serialize(r, c)})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "integrated", res
    assert any("DEC-A#C1" in a for a in res["warnings"])


def test_the_new_one_worsening_a_previous_conflict_does_block(environment):
    # The base carries the DEC-E/DEC-F conflict on DEC-A#C1; DEC-N enters as a third candidate: it gets worse and blocks.
    repo, base, receipts = environment
    files = {}
    for ident, text in (("DEC-E", "Thursday."), ("DEC-F", "Friday.")):
        r, c = decision(
            ident,
            {"C1": text},
            recorded="2026-10-04T00:00:00Z",
            authorized_by=["ROLE-OP"],
            amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": f"{ident}#C1"}],
        )
        files[f"kb/{ident}.md"] = canonical(r, c)
    base2 = _base_with(repo, base, files)
    n, cn = _replaces_a1("DEC-N", "Tuesday.")
    prop = propose(repo, base2, {"kb/DEC-N.md": serialize(n, cn), **request("op-1", {"DEC-N": ACCEPT})})
    res = call(repo, base2, prop, receipts)
    assert res["state"] == "blocked" and res["code"] == "NORMATIVE_CONFLICT"
    assert res["conflicts"][0]["candidates"] == ["DEC-E#C1", "DEC-F#C1", "DEC-N#C1"]
    assert repo.git("rev-parse", "canon") == base2
