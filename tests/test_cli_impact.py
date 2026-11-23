"""CLI `impact`: consumers affected by moving from a base revision to another (E5, read-only query)."""

import json
import subprocess
import sys

from conftest import decision, event, record

from kbol.core import serialize

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def write(folder, name, r, c=""):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")


def commit(repo, message):
    subprocess.run(["git", "-C", str(repo), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), *GIT, "commit", "-q", "-m", message], check=True)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def repo_with_consumer(tmp_path):
    """Base: DEC-A, DEC-C that depends on DEC-A#C1, and the role. After: DEC-B replaces DEC-A#C1."""
    repo, kb_ = tmp_path / "repo", tmp_path / "repo" / "kb"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    creation = event("creation", event_id="E0", previous_state=None, new_state="proposed")
    write(kb_, "ROLE", record("role", events=[creation]))
    write(kb_, "DEC-A", *decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z"))
    consumer = decision(
        "DEC-C",
        {"C1": "The report goes out on the set day."},
        recorded="2026-11-01T00:00:00Z",
        depends_on=[{"target": "DEC-A#C1", "condition": "accepted_and_in_force"}],
    )
    write(kb_, "DEC-C", *consumer)
    base = commit(repo, "base")
    new = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
    )
    write(kb_, "DEC-B", *new)
    return repo, base, commit(repo, "replacement")


def test_impact_between_two_revisions(tmp_path):
    repo, base, final = repo_with_consumer(tmp_path)
    code, out = kb("impact", str(repo), "--folder", "kb", "--base", base, "--revision", final)
    assert code == 0 and out["result"]["state"] == "completed", out
    assert out["result"]["changed"] == ["DEC-B"]
    [affected] = out["result"]["affected"]
    assert affected["affected"] == "DEC-C" and affected["path"] == ["DEC-B", "DEC-A#C1", "DEC-C"]
    assert affected["resolution"] == "pending"
    assert out["revision"] == final and out["result"]["base"] == base


def test_impact_requires_the_base(tmp_path):
    repo, _, final = repo_with_consumer(tmp_path)
    code, out = kb("impact", str(repo), "--folder", "kb", "--revision", final)
    assert code == 2 and "--base" in out["result"]["reason"]


def test_impact_against_the_disk_declares_it(tmp_path):
    repo, base, _ = repo_with_consumer(tmp_path)
    code, out = kb("impact", str(repo), "--folder", "kb", "--base", base)
    assert code == 0 and out["revision"] == "disk"
    assert any("disk" in a for a in out["warnings"])


def test_impact_with_a_base_that_does_not_exist(tmp_path):
    repo, _, final = repo_with_consumer(tmp_path)
    code, out = kb("impact", str(repo), "--folder", "kb", "--base", "0" * 40, "--revision", final)
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE"
