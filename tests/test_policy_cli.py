"""CLI policy: an operation that examines nothing does not end `completed`.

Two levels: a table that forces every enabled operation to say what it returns for an empty input, and specific tests
of each case the decision names.
"""

# ruff: noqa: F811  (the fixtures are imported from other test modules)

import json
import subprocess
import sys

import pytest
from conftest import decision, event, record
from test_cli_impact import kb as kb_impact
from test_cli_impact import repo_with_consumer
from test_declared import environment  # noqa: F401
from test_fingerprints import integrate_question
from test_verify import INSTALLATION, commit, kb_verify, repo  # noqa: F401

from kbol import cli
from kbol.core import serialize

T = "2026-11-03T12:00:00Z"
GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


@pytest.fixture
def empty(tmp_path):
    """Repository with a commit and a `kb` folder without records: nothing to examine."""
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    (root / "kb").mkdir()
    (root / "kb" / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), *GIT, "commit", "-q", "-m", "base"], check=True)
    return root


# Operation -> (arguments over the empty root, natural state of an empty input). A new operation in ENABLED does
# not pass without its row: what matters is that empty is never read as success.
def _table(r):
    kb_ = str(r / "kb")
    query = [str(r), "--folder", "kb", "--valid-at", T]
    return {
        "validate": (["validate", kb_], "failed"),
        "migrate": (["migrate", kb_, "--revision", "HEAD"], "partial"),
        "digest": (["digest", kb_], "failed"),
        "consolidate": (["consolidate", *query, "--ids", "DEC-X"], "partial"),
        "ready": (["ready", *query], "partial"),
        "impact": (["impact", str(r), "--folder", "kb", "--base", "HEAD"], "partial"),
        "handoff": (["handoff", str(r)], "blocked"),
        "context": (["context", str(r)], "blocked"),
        "verify": (["verify", str(r)], "blocked"),
        "query": (["query", *query, "--ids", "DEC-X"], "partial"),
        "search": (["search", *query, "--query", "nothing"], "partial"),
        "integrate": (["integrate", str(r)], "blocked"),
        "bootstrap": (["bootstrap", str(r)], "blocked"),
        "drift": (["drift", str(r), "--folder", "kb"], "partial"),
        "citations": (["citations", str(r), "--folder", "kb"], "partial"),
        "links": (["links", str(r)], "partial"),
        "integrity": (["integrity", str(r), "--folder", "kb"], "partial"),
        "support": (["support", *query], "partial"),
        "approval_package": (["approval_package", str(r)], "blocked"),
        "vocabulary": (["vocabulary", *query], "partial"),
        "session": (["session", str(r)], "blocked"),
        "propose": (["propose", str(r)], "blocked"),
        "export_skills": (["export_skills", str(r / "skills"), "--skills"], "blocked"),
    }


def test_the_table_covers_exactly_the_enabled_operations(empty):
    assert set(_table(empty)) == set(cli.ENABLED)


@pytest.mark.parametrize("op", cli.ENABLED)
def test_an_empty_input_is_never_completed(empty, op):
    args, expected = _table(empty)[op]
    code, out = kb(*args)
    assert out["result"]["state"] == expected, out
    assert out["result"]["state"] != "completed" and code != 0
    assert code == {"failed": 1, "blocked": 2, "partial": 3}[expected]


def write(folder, name, r, c=""):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")


def test_consolidate_with_a_missing_id_is_partial(tmp_path):
    creation = event("creation", event_id="E0", previous_state=None, new_state="proposed")
    write(tmp_path / "kb", "ROLE", record("role", events=[creation]))
    write(tmp_path / "kb", "DEC-A", *decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z"))
    base = ["consolidate", str(tmp_path), "--folder", "kb", "--valid-at", T]
    code, out = kb(*base, "--ids", "DEC-A")
    assert code == 0 and out["result"]["state"] == "completed", out
    code, out = kb(*base, "--ids", "DEC-A", "DEC-NO")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["missing"] == ["DEC-NO"]
    assert any("DEC-NO" in a for a in out["warnings"])


def test_citations_over_a_folder_that_does_not_exist_is_failed(tmp_path):
    code, out = kb("citations", str(tmp_path), "--folder", "does-not-exist")
    assert code == 1 and out["result"]["state"] == "failed", out
    assert out["result"]["code"] == "MISSING_REFERENCE"


def test_citations_over_an_empty_folder_is_partial_with_the_reason(tmp_path):
    (tmp_path / "kb").mkdir()
    code, out = kb("citations", str(tmp_path), "--folder", "kb")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["rows"] == [] and any("no citation" in a for a in out["warnings"])


def test_citations_looks_in_the_subfolders(tmp_path):
    sub = tmp_path / "kb" / "sub" / "more"
    sub.mkdir(parents=True)
    (sub / "DEC-1.md").write_text("---\nid: DEC-1\nsources:\n- id: s1\n  resource: SRC-none\n---\n", encoding="utf-8")
    code, out = kb("citations", str(tmp_path), "--folder", "kb")
    assert [f["record"] for f in out["result"]["rows"]] == ["DEC-1"], out
    assert out["result"]["rows"][0]["state"] == "broken" and code == 3


def test_drift_without_checked_records_is_partial_and_declares_the_coverage(empty):
    code, out = kb("drift", str(empty), "--folder", "kb")
    assert code == 3 and out["result"]["state"] == "partial" and out["result"]["checked"] == 0, out
    assert any("no record" in a for a in out["warnings"])
    assert out["coverage"]["records_read"] == 0 and "truncated" in out["coverage"]


def test_drift_with_drift_warns_and_stays_at_zero(environment):
    repo_, base, receipts = environment
    integrate_question(repo_, base, receipts)
    repo_.git("checkout", "-q", "canon")
    path = repo_.root / "kb" / "Q-N.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Text.", "Other."), encoding="utf-8")
    code, out = kb("drift", str(repo_.root), "--folder", "kb", "--canonical-branch", "canon")
    assert code == 0 and out["result"]["state"] == "completed", out
    assert out["result"]["checked"] > 0 and out["result"]["alerts"] and out["warnings"]
    assert out["coverage"]["records_read"] > 0


def test_drift_with_an_unreadable_record_is_partial(environment):
    """The state does not contradict the coverage: what could not be read might have drifted."""
    repo_, base, receipts = environment
    integrate_question(repo_, base, receipts)
    repo_.git("checkout", "-q", "canon")
    (repo_.root / "kb" / "broken.md").write_text("---\nid: [unclosed\n---\n", encoding="utf-8")
    code, out = kb("drift", str(repo_.root), "--folder", "kb", "--canonical-branch", "canon")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["checked"] > 0 and out["coverage"]["truncated"] is True


def test_migrate_a_folder_without_legacy_records_is_partial(tmp_path):
    """A file out of scope is not an examined record."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "README.md").write_text("# Notes\n", encoding="utf-8")
    code, out = kb("migrate", str(folder), "--revision", "r1")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["summary"]["total"] == 1 and out["result"]["summary"]["proposed"] == 0


def test_impact_without_changes_stays_completed(tmp_path):
    repo_, _, final = repo_with_consumer(tmp_path)
    code, out = kb_impact("impact", str(repo_), "--folder", "kb", "--base", final, "--revision", final)
    assert code == 0 and out["result"]["state"] == "completed", out
    assert out["result"]["changed"] == [] and out["coverage"]["records_read"] > 0


def test_verify_that_fails_is_failed(repo):
    installation = repo / "installation.json"
    installation.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    commit(repo)
    code, out = kb_verify(repo, installation, "--check", "bad")
    assert code == 1 and out["result"]["state"] == "failed", out
    assert out["result"]["result"] == "failed" and isinstance(out["result"]["code"], int)
    assert out["result"]["code"] != 0 and "failed" in out["result"]["reason"]


@pytest.mark.parametrize("ident", ["missing", "slow"])
def test_verify_unknown_or_not_run_is_partial(repo, ident):
    installation = repo / "installation.json"
    installation.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    commit(repo)
    code, out = kb_verify(repo, installation, "--check", ident)
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["result"] in ("not_run", "requires_review")
    assert any(a.startswith("check ") for a in out["warnings"])


def test_verify_that_passes_stays_completed(repo):
    installation = repo / "installation.json"
    installation.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    commit(repo)
    code, out = kb_verify(repo, installation, "--check", "ok")
    assert code == 0 and out["result"]["state"] == "completed", out


@pytest.mark.parametrize("op", ["validate", "digest"])
def test_validate_and_digest_over_a_folder_are_failed_with_envelope(tmp_path, op):
    code, out = kb(op, str(tmp_path))
    assert code == 1 and out["operation"] == op and out["result"]["state"] == "failed", out
    assert out["result"]["code"] == "MISSING_REFERENCE"


def test_context_with_a_scope_without_records_is_partial(empty, tmp_path):
    installation = tmp_path / "installation.json"
    installation.write_text(json.dumps({"project": "p", "instructions": [], "procedures": []}), encoding="utf-8")
    code, out = kb(
        "context",
        str(empty),
        "--folder",
        "kb",
        "--task",
        "t",
        "--scope",
        "nothing",
        "--installation",
        str(installation),
        "--valid-at",
        T,
    )
    assert code == 3 and out["result"]["state"] == "partial", out
    assert "no record in the scope" in out["result"]["reason"]


def test_migrate_a_folder_without_records_is_partial(tmp_path):
    (tmp_path / "old").mkdir()
    code, out = kb("migrate", str(tmp_path / "old"), "--revision", "r")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["summary"]["total"] == 0 and out["warnings"]
