"""Approval package: what the person sees before approving, with the digests the gate checks.

The test that matters is end to end: the package skeleton, completed with what whoever collects the approval
provides, integrates; if the content changes afterwards, it goes stale; and if the gate were to block, the package
blocks first with the same code.
"""

import json
import subprocess
import sys

import pytest
from conftest import DECISION_BODY, body_of, decision, event, record
from test_importing import BODY as ADR_BODY
from test_importing import IMPORT, LEGACY_ADR, LEGACY_QD, adr
from test_integrate import ACCEPT, Repo, active, canonical, propose, request

from kbol.core import parse, serialize
from kbol.declared import FIELDS, MECHANISM, DeclaredVerifier
from kbol.integrate import ACTOR, integrate
from kbol.package import approval_package, present

INSTANT = "2026-11-05T18:00:00Z"
VALID = "2026-11-06T00:00:00Z"
# Without previous_state: the gate fills it in before computing the digest, and the package has to do the same.
ACCEPT_WITHOUT_PREVIOUS = [{"new_state": "accepted", "valid_from": "2026-11-05T00:00:00Z"}]
CREATED = "2026-10-03T00:00:00Z"


def _created():
    return event(
        "creation",
        event_id="E0",
        previous_state=None,
        new_state="proposed",
        recorded_at=CREATED,
        valid_from=CREATED,
    )


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
    a, ca = decision("DEC-A", {"C1": "Monday."}, recorded=CREATED, authorized_by=["ROLE-OP"])
    p, cp = decision("DEC-P", {"C1": "Tuesday."}, recorded=CREATED, state="proposed", authorized_by=["ROLE-OP"])
    he = record("fact", id="FACT-P", based_on=[], events=[_created()])
    for ident, r, c in (
        ("ROLE-OP", role, ""),
        ("PER-H", per, ""),
        ("DEC-A", a, ca),
        ("DEC-P", p, cp),
        ("FACT-P", he, ""),
    ):
        repo.write(f"kb/{ident}.md", canonical(r, c))
    repo.write("kb/ADR-0001.md", LEGACY_ADR)
    repo.write("kb/QD-001.md", LEGACY_QD)
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "receipts"


def dec_x(**fields):
    return record("decision", id="DEC-X", authorized_by=["ROLE-OP"], **fields), DECISION_BODY


def package(repo, base, prop, op="op-1", **kw):
    return approval_package(repo.root, folder="kb", operation_id=op, base=base, proposal=prop, valid_at=VALID, **kw)


def sign(skeleton):
    """What whoever collects the approval provides: the generator does not write it."""
    return {**skeleton, "identity": "declared:h", "session": "test session", "instant": INSTANT, "quote": "Yes"}


def integrate_with(repo, base, prop, receipts, approvals, op="op-1", mode="all"):
    return integrate(
        repo.root,
        branch="canon",
        folder="kb",
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=approvals,
        verifier=DeclaredVerifier(repo.root),
        receipts=receipts,
        approval=mode,
        actor="claude-code/opus-5.5" if mode == "decisive" else ACTOR,
    )


def _creation(repo, base, op):
    r, c = dec_x()
    return propose(repo, base, {"kb/DEC-X.md": serialize(r, c)}), "DEC-X"


def _transition(repo, base, op):
    r, c = dec_x()
    return propose(
        repo, base, {"kb/DEC-X.md": serialize(r, c), **request(op, {"DEC-X": ACCEPT_WITHOUT_PREVIOUS})}
    ), "DEC-X"


def _import(repo, base, op):
    req = {"operation_id": op, "effects": {}, "imports": {"ADR-0001": IMPORT}}
    files = {"kb/ADR-0001.md": serialize(adr(), ADR_BODY), f"kb/_requests/{op}.json": json.dumps(req)}
    return propose(repo, base, files), "ADR-0001"


CASES = {"creation": _creation, "transition": _transition, "import": _import}


def _ratifications(repo, ident):
    meta, _ = parse(repo.git("show", f"canon:kb/{ident}.md") + "\n")
    return [e["approval"] for e in meta["events"] if e["event_type"] == "ratification"]


@pytest.mark.parametrize("mode", ["all", "decisive"])
@pytest.mark.parametrize("case", sorted(CASES))
def test_the_completed_skeleton_integrates_with_the_same_digests(environment, case, mode):
    repo, base, receipts = environment
    prop, ident = CASES[case](repo, base, "op-1")
    pkg = package(repo, base, prop)
    assert pkg["state"] == "completed", pkg
    assert [r["id"] for r in pkg["records"]] == [ident]
    [skeleton] = pkg["approvals"]
    assert skeleton["base_shown"] == base and set(skeleton["digests"]) == {ident}
    res = integrate_with(repo, base, prop, receipts, [sign(skeleton)], mode=mode)
    assert res["state"] == "integrated", res
    assert res["records"] == [ident]
    # The package digests are the ones the gate recomputed and left in the ratification and in the receipt.
    digest = pkg["records"][0]["digest"]
    assert skeleton["digests"][ident] == digest
    ratifications = _ratifications(repo, ident)
    assert all(a["digest"] == digest for a in ratifications)
    for detail in res.get("approval_details", []):
        assert detail["proof"]["digests"] == skeleton["digests"]
    if case == "transition":
        assert len(ratifications) == 1 and pkg["records"][0]["decisive"]
        assert res["decisive"] == [ident]
    else:
        assert not pkg["records"][0]["decisive"]
        assert res["decisive"] == ([ident] if mode == "all" else [])


def test_the_transition_carries_the_previous_state_the_gate_fills_in(environment):
    repo, base, _ = environment
    prop, _ = _transition(repo, base, "op-1")
    [r] = package(repo, base, prop)["records"]
    assert r["effects"] == [{**ACCEPT_WITHOUT_PREVIOUS[0], "previous_state": "proposed"}]
    assert r["decisive_reasons"] == ["transition to accepted"] and r["change"] == "new"


def test_the_import_shows_what_is_approved_and_the_legacy_state(environment):
    repo, base, _ = environment
    prop, _ = _import(repo, base, "op-1")
    [r] = package(repo, base, prop)["records"]
    assert r["change"] == "imported"
    assert r["import"] == {**IMPORT, "legacy_state": "Accepted"}


def test_content_changed_after_the_package_makes_the_approval_stale(environment):
    repo, base, receipts = environment
    prop, _ = _transition(repo, base, "op-1")
    skeleton = package(repo, base, prop)["approvals"][0]
    r, c = dec_x(title="Another title")
    other = propose(repo, base, {"kb/DEC-X.md": serialize(r, c), **request("op-1", {"DEC-X": ACCEPT_WITHOUT_PREVIOUS})})
    res = integrate_with(repo, base, other, receipts, [sign(skeleton)])
    assert res["state"] == "blocked" and res["code"] == "STALE_APPROVAL", res
    assert repo.git("rev-parse", "canon") == base


def _rewrites_accepted_clause(repo, base):
    text = repo.git("show", f"{base}:kb/DEC-A.md") + "\n"
    return propose(repo, base, {"kb/DEC-A.md": text.replace("Monday.", "Tuesday.")})


def _impossible_transition(repo, base):
    r, c = dec_x()
    effect = [{"previous_state": "accepted", "new_state": "rejected", "valid_from": "2026-11-05T00:00:00Z"}]
    return propose(repo, base, {"kb/DEC-X.md": serialize(r, c), **request("op-1", {"DEC-X": effect})})


def _touches_something_that_is_not_a_record(repo, base):
    r, c = dec_x()
    return propose(repo, base, {"kb/DEC-X.md": serialize(r, c), "README.md": "other\n"})


@pytest.mark.parametrize(
    "make", [_rewrites_accepted_clause, _impossible_transition, _touches_something_that_is_not_a_record]
)
def test_what_the_gate_would_block_the_package_blocks_first_with_the_same_code(environment, make):
    repo, base, receipts = environment
    prop = make(repo, base)
    pkg = package(repo, base, prop)
    gate = integrate_with(repo, base, prop, receipts, [])
    assert pkg["state"] == gate["state"] == "blocked", (pkg, gate)
    assert (pkg["code"], pkg["reason"]) == (gate["code"], gate["reason"])
    assert "records" not in pkg and "approvals" not in pkg


def test_a_normative_conflict_blocks_the_package(environment):
    repo, base, _ = environment
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
    pkg = package(repo, base, prop)
    assert pkg["state"] == "blocked" and pkg["code"] == "NORMATIVE_CONFLICT", pkg


def test_the_skeleton_leaves_empty_what_whoever_approves_provides(environment):
    repo, base, _ = environment
    prop, _ = _creation(repo, base, "op-1")
    [skeleton] = package(repo, base, prop)["approvals"]
    assert set(skeleton) == set(FIELDS) and skeleton["mechanism"] == MECHANISM
    assert all(skeleton[k] is None for k in ("identity", "session", "instant", "quote"))


def test_a_changed_clause_shows_the_old_and_the_new_text(environment):
    repo, base, _ = environment
    text = repo.git("show", f"{base}:kb/DEC-P.md") + "\n"
    clause = '<clause id="C1">\nTuesday.\n</clause>'
    assert text.count(clause) == 1
    new = text.replace(clause, clause.replace("Tuesday.", "Wednesday.")).replace("title: Title", "title: New")
    prop = propose(repo, base, {"kb/DEC-P.md": new})
    [r] = package(repo, base, prop)["records"]
    assert r["change"] == "modified"
    assert r["clauses"] == [{"anchor": "C1", "change": "changed", "before": "Tuesday.", "after": "Wednesday."}]
    assert r["header"] == [{"field": "title", "before": "Title", "after": "New"}]


def test_an_amendment_shows_the_text_in_force_next_to_the_new_one(environment):
    repo, base, _ = environment
    r = record(
        "decision",
        id="DEC-B",
        authorized_by=["ROLE-OP"],
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
    )
    prop = propose(repo, base, {"kb/DEC-B.md": serialize(r, body_of({"C1": "Tuesday."}))})
    pkg = package(repo, base, prop)
    [reg] = pkg["records"]
    assert reg["amends"] == [
        {
            "target": "DEC-A#C1",
            "operation": "replaces",
            "by": "DEC-B#C1",
            "current_text": "Monday.",
            "new_text": "Tuesday.",
        }
    ]
    assert reg["clauses"] == [{"anchor": "C1", "change": "new", "after": "Tuesday."}]
    assert {"field": "amends", "before": None, "after": r["amends"]} in reg["header"]
    assert not any(c["field"] in ("events", "state", "id") for c in reg["header"])


def test_a_support_not_in_force_is_shown_as_such(environment):
    repo, base, _ = environment
    r, c = dec_x(based_on=["FACT-P"])
    prop = propose(repo, base, {"kb/DEC-X.md": serialize(r, c)})
    [reg] = package(repo, base, prop)["records"]
    assert reg["support"] == "broken"
    [support_] = reg["supports"]
    assert support_["ref"] == "FACT-P" and support_["field"] == "based_on" and support_["situation"] == "not_in_force"


def test_the_impact_is_the_one_the_receipt_would_leave(environment):
    repo, base, receipts = environment
    text = repo.git("show", f"{base}:kb/FACT-P.md") + "\n"
    fields = {"state": "proposed", "based_on": ["FACT-P"], "authorized_by": ["ROLE-OP"]}
    r, c = decision("DEC-X", {"C1": "Thursday."}, recorded=CREATED, **fields)
    base2 = propose(repo, base, {"kb/DEC-X.md": canonical(r, c)})
    repo.git("update-ref", "refs/heads/canon", base2, base)  # DEC-X already consumes FACT-P in the base
    prop = propose(repo, base2, {"kb/FACT-P.md": text.replace("Title", "Other")})
    pkg = package(repo, base2, prop)
    assert pkg["state"] == "completed", pkg
    assert [a["affected"] for a in pkg["impact"]["affected"]] == ["DEC-X"]
    res = integrate_with(repo, base2, prop, receipts, [sign(pkg["approvals"][0])])
    assert res["state"] == "integrated", res
    assert res["impact"]["affected"] == pkg["impact"]["affected"]


def test_without_touched_records_there_is_nothing_to_approve(environment):
    repo, base, _ = environment
    prop = propose(repo, base, {"kb/_requests/op-1.json": json.dumps({"operation_id": "op-1", "effects": {}})})
    pkg = package(repo, base, prop)
    assert pkg["state"] == "completed" and pkg["records"] == [], pkg
    assert pkg["approvals"][0]["digests"] == {}


def test_read_only(environment):
    repo, base, _ = environment
    prop, _ = _transition(repo, base, "op-1")
    refs = repo.git("for-each-ref")
    package(repo, base, prop)
    assert repo.git("for-each-ref") == refs and repo.git("status", "--porcelain") == ""


def test_a_cut_without_zone_blocks(environment):
    repo, base, _ = environment
    prop, _ = _creation(repo, base, "op-1")
    pkg = approval_package(repo.root, folder="kb", operation_id="op-1", base=base, proposal=prop, valid_at="2026-11-06")
    assert pkg["state"] == "blocked" and pkg["code"] == "AMBIGUOUS_TIME"


def test_the_presentation_says_what_changes_and_what_was_not_evaluated(environment):
    repo, base, _ = environment
    r = record(
        "decision",
        id="DEC-B",
        authorized_by=["ROLE-OP"],
        based_on=["FACT-P"],
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
    )
    files = {"kb/DEC-B.md": serialize(r, body_of({"C1": "Tuesday."})), **request("op-1", {"DEC-B": ACCEPT})}
    pkg = package(repo, base, propose(repo, base, files))
    text = present(pkg)
    assert "Amends DEC-A#C1 (replaces): now «Monday.» → «Tuesday.»" in text
    assert "Effect: proposed → accepted from 2026-11-05T00:00:00Z" in text
    assert "Decisive: transition to accepted" in text
    assert "FACT-P (based_on): not_in_force" in text
    assert pkg["records"][0]["digest"] in text and "Not evaluated:" in text
    assert "---" not in text and "events" not in text


def kbol(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


def _cli(repo, base, prop, *extra):
    return kbol(
        "approval_package",
        str(repo.root),
        "--folder",
        "kb",
        "--operation-id",
        "op-1",
        "--base",
        base,
        "--proposal",
        prop,
        "--valid-at",
        VALID,
        *extra,
    )


def test_cli_returns_the_envelope_with_the_package(environment):
    repo, base, receipts = environment
    prop, _ = _transition(repo, base, "op-1")
    code, output = _cli(repo, base, prop)
    envelope = json.loads(output)
    assert code == 0 and envelope["operation"] == "approval_package", envelope
    assert envelope["result"]["state"] == "completed" and envelope["revision"] == prop
    assert envelope["valid_at"] == VALID and "not_evaluated" not in envelope["result"]
    assert any("authenticity" in n for n in envelope["coverage"]["not_evaluated"])
    [skeleton] = envelope["result"]["approvals"]
    assert integrate_with(repo, base, prop, receipts, [sign(skeleton)])["state"] == "integrated"


def test_cli_as_text(environment):
    repo, base, _ = environment
    prop, _ = _transition(repo, base, "op-1")
    code, output = _cli(repo, base, prop, "--text")
    assert code == 0 and output.startswith("Approval package of op-1"), output
    assert "DEC-X (decision, new)" in output and "Digest: " in output


def test_cli_blocked_exits_with_two(environment):
    repo, base, _ = environment
    code, output = _cli(repo, base, _rewrites_accepted_clause(repo, base))
    envelope = json.loads(output)
    assert code == 2 and envelope["result"]["code"] == "INVALID_SCHEMA", envelope


def test_cli_without_touched_records_is_partial(environment):
    repo, base, _ = environment
    prop = propose(repo, base, {"kb/_requests/op-1.json": json.dumps({"operation_id": "op-1", "effects": {}})})
    code, output = _cli(repo, base, prop)
    envelope = json.loads(output)
    assert code == 3 and envelope["result"]["state"] == "partial", envelope
    assert any("nothing to approve" in a for a in envelope["warnings"])


def test_cli_without_required_inputs_blocks(environment):
    repo, base, _ = environment
    code, output = kbol("approval_package", str(repo.root), "--folder", "kb", "--base", base)
    envelope = json.loads(output)
    assert code == 2 and "--operation-id" in envelope["result"]["reason"]
