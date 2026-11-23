"""Fingerprints and drift: the integration stores the fingerprint of what it writes and `drift` warns about what
was edited outside the flow, without blocking."""

# ruff: noqa: F811  (the environment fixture is imported from test_declared)

import json
import subprocess
import sys

from test_decisive import call, question
from test_declared import environment  # noqa: F401
from test_integrate import propose

from kbol.core import serialize
from kbol.fingerprints import ARCHIVE, drift, fingerprint


def integrate_question(repo, base, receipts):
    r, c = question()
    res = call(repo, base, propose(repo, base, {"kb/Q-N.md": serialize(r, c)}), receipts)
    assert res["state"] == "integrated", res
    return res


def test_the_integration_stores_the_fingerprint_of_what_it_writes(environment):
    repo, base, receipts = environment
    integrate_question(repo, base, receipts)
    stored = json.loads(repo.git("show", f"canon:kb/{ARCHIVE}"))
    assert stored["Q-N"] == {"path": "kb/Q-N.md", "sha256": fingerprint(repo.git("show", "canon:kb/Q-N.md") + "\n")}
    assert set(stored) == {"Q-N"}


def test_a_proposal_cannot_touch_the_fingerprints(environment):
    repo, base, receipts = environment
    r, c = question()
    prop = propose(repo, base, {"kb/Q-N.md": serialize(r, c), f"kb/{ARCHIVE}": "{}\n"})
    assert call(repo, base, prop, receipts)["state"] == "blocked"


def test_drift_warns_about_a_hand_edit_and_about_what_has_no_fingerprint(environment):
    repo, base, receipts = environment
    integrate_question(repo, base, receipts)
    repo.git("checkout", "-q", "canon")
    res = drift(repo.root, "kb", branch="canon")
    missing = {a["id"] for a in res["alerts"] if a["reason"] == "no_fingerprint"}
    assert "Q-N" not in missing and "PER-H" in missing  # those of the base did not go through this integration
    assert not [a for a in res["alerts"] if a["reason"] == "different"]
    path = repo.root / "kb" / "Q-N.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Text.", "Text changed by hand."), encoding="utf-8")
    different = [a for a in drift(repo.root, "kb", branch="canon")["alerts"] if a["reason"] == "different"]
    assert different == [{"id": "Q-N", "path": "kb/Q-N.md", "reason": "different", "last_integrated": "canon:kb/Q-N.md"}]


def test_when_staged_it_compares_the_index_and_not_the_disk(environment):
    repo, base, receipts = environment
    integrate_question(repo, base, receipts)
    repo.git("checkout", "-q", "canon")
    path = repo.root / "kb" / "Q-N.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("Text.", "Other."), encoding="utf-8")
    assert not [a for a in drift(repo.root, "kb", staged=True)["alerts"] if a["reason"] == "different"]
    repo.git("add", "kb/Q-N.md")
    assert [a["id"] for a in drift(repo.root, "kb", staged=True)["alerts"] if a["reason"] == "different"] == ["Q-N"]


def test_line_endings_do_not_change_the_fingerprint():
    assert fingerprint("a\r\nb\n") == fingerprint("a\nb\n") == fingerprint(b"a\nb\n")


def test_the_cli_warns_without_blocking(environment):
    repo, base, receipts = environment
    integrate_question(repo, base, receipts)
    repo.git("checkout", "-q", "canon")
    path = repo.root / "kb" / "Q-N.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Text.", "Other."), encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "drift", str(repo.root), "--folder", "kb", "--canonical-branch", "canon"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0, p.stderr
    envelope = json.loads(p.stdout)
    assert envelope["result"]["state"] == "completed" and envelope["result"]["checked"] > 0
    assert "Q-N" in {a["id"] for a in envelope["result"]["alerts"]}
    assert envelope["warnings"]


def test_the_fingerprint_gate_recognizes_the_same_emails_as_integrate_and_bootstrap():
    from kbol.bootstrap import _BOOTSTRAP_IDENTITY
    from kbol.fingerprints import GATE_EMAILS
    from kbol.integrate import EMAIL

    assert {EMAIL, _BOOTSTRAP_IDENTITY["GIT_COMMITTER_EMAIL"]} == GATE_EMAILS


def test_a_direct_commit_to_the_canonical_branch_shows_outside_the_flow(environment):
    from kbol.fingerprints import commits_outside_flow

    repo, base, receipts = environment
    assert commits_outside_flow(repo.root, "kb", "canon") == {"evaluated": False, "from": None, "commits": []}
    res = integrate_question(repo, base, receipts)
    clean = commits_outside_flow(repo.root, "kb", "canon")
    assert clean == {"evaluated": True, "from": res["integrated_revision"], "commits": []}
    repo.git("checkout", "-q", "canon")
    repo.write("README.md", "other\n")
    repo.commit("outside the records: does not count")
    repo.write("kb/note.txt", "by hand\n")
    direct = repo.commit("by hand in the records")
    outside = commits_outside_flow(repo.root, "kb", "canon")
    assert [c["commit"] for c in outside["commits"]] == [direct]
    assert outside["commits"][0]["subject"] == "by hand in the records"
    assert commits_outside_flow(repo.root, "kb", "does-not-exist")["evaluated"] is False


def test_the_cli_warns_about_commits_outside_the_flow_without_blocking(environment):
    repo, base, receipts = environment
    integrate_question(repo, base, receipts)
    repo.git("checkout", "-q", "canon")
    repo.write("kb/note.txt", "by hand\n")
    direct = repo.commit("by hand in the records")
    order = [sys.executable, "-m", "kbol.cli", "drift", str(repo.root), "--folder", "kb"]
    p = subprocess.run([*order, "--canonical-branch", "canon"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    envelope = json.loads(p.stdout)
    assert [c["commit"] for c in envelope["result"]["commits_outside_flow"]] == [direct]
    assert any("without going through the gate" in a for a in envelope["warnings"])
    without_branch = json.loads(subprocess.run(order, capture_output=True, text=True, encoding="utf-8").stdout)
    assert "commits_outside_flow" not in without_branch["result"]
    assert "commits of the canonical branch" in without_branch["coverage"]["not_evaluated"]
