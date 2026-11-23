"""Integrity of the sources (`kbol integrity`): matches, altered, missing or unchecked, with its cause."""

import hashlib
import json
import subprocess

import pytest
from conftest import record

from kbol.cli import main
from kbol.core import serialize
from kbol.integrity import check, check_source

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
CONTENT = b"%PDF-1.7 test original\r\nwith Windows line breaks\r\n"
SHA = hashlib.sha256(CONTENT).hexdigest()
OTHER = "b" * 64


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *GIT, *args], check=True, capture_output=True, text=True)
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """Repository with an original versioned as is (line breaks not normalized) and its revision."""
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    (root / "originals").mkdir()
    (root / "originals" / "report.pdf").write_bytes(CONTENT)
    (root / "kb").mkdir()
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root, git(root, "rev-parse", "HEAD")


@pytest.fixture
def store(tmp_path):
    folder = tmp_path / "store"
    (folder / "sha256").mkdir(parents=True)
    (folder / "sha256" / SHA).write_bytes(CONTENT)
    return folder


def source(ident, location, sha256=SHA):
    return record("source", id=ident, location=location, sha256=sha256)


def save(root, r):
    (root / "kb" / f"{r['id']}.md").write_text(serialize(r, ""), encoding="utf-8", newline="\n")


def kb(capsys, *args):
    code = main(list(args))
    return code, json.loads(capsys.readouterr().out)


# ── One source ──────────────────────────────────────────────────────────────


def test_path_from_the_root(repo):
    root, _ = repo
    assert check_source(root, source("SRC-A", "originals/report.pdf")) == ("matches", None)
    state, cause = check_source(root, source("SRC-A", "originals/report.pdf", OTHER))
    assert state == "altered" and "working tree" in cause
    state, cause = check_source(root, source("SRC-A", "originals/not-there.pdf"))
    assert state == "missing" and "does not exist" in cause


def test_bytes_are_not_normalized(repo):
    root, _ = repo
    (root / "originals" / "report.pdf").write_bytes(CONTENT.replace(b"\r\n", b"\n"))
    assert check_source(root, source("SRC-A", "originals/report.pdf"))[0] == "altered"


def test_anchored_git_revision(repo):
    root, rev = repo
    location = f"git:{rev}:originals/report.pdf"
    assert check_source(root, source("SRC-A", location)) == ("matches", None)
    # The anchored revision does not change even if the working tree changes or loses the file.
    (root / "originals" / "report.pdf").unlink()
    assert check_source(root, source("SRC-A", location)) == ("matches", None)
    assert check_source(root, source("SRC-A", location, OTHER))[0] == "altered"
    state, cause = check_source(root, source("SRC-A", f"git:{rev}:originals/other.pdf"))
    assert state == "missing" and rev[:12] in cause


def test_a_folder_of_the_revision_is_not_an_altered_original(repo):
    root, rev = repo
    state, cause = check_source(root, source("SRC-A", f"git:{rev}:originales"))
    assert state == "missing" and "is not a file" in cause


def test_a_revision_not_in_the_clone_is_not_an_accusation(repo):
    root, _ = repo
    state, cause = check_source(root, source("SRC-A", "git:" + "0" * 40 + ":originals/report.pdf"))
    assert state == "unchecked" and "is not in this clone" in cause


def test_an_unanchored_revision_is_not_checked(repo):
    root, _ = repo
    state, cause = check_source(root, source("SRC-A", "git:main:originals/report.pdf"))
    assert state == "unchecked" and "full SHA" in cause


def test_shallow_clone_without_the_revision(repo, tmp_path):
    root, rev = repo
    (root / "other.txt").write_text("x\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "second")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", root.as_uri(), str(clone)], check=True)
    state, cause = check_source(clone, source("SRC-A", f"git:{rev}:originals/report.pdf"))
    assert state == "unchecked" and "shallow clone" in cause


def test_store(repo, store, tmp_path):
    root, _ = repo
    location = f"store:sha256/{SHA}"
    assert check_source(root, source("SRC-A", location), store) == ("matches", None)
    state, cause = check_source(root, source("SRC-A", location))
    assert state == "unchecked" and "no store was given" in cause
    state, cause = check_source(root, source("SRC-A", location), tmp_path / "other-store")
    assert state == "unchecked" and "not in this machine's store" in cause
    (store / "sha256" / SHA).write_bytes(b"other content")
    state, cause = check_source(root, source("SRC-A", location), store)
    assert state == "altered" and "store object" in cause


def test_the_store_location_names_the_source_fingerprint(repo, store):
    root, _ = repo
    state, cause = check_source(root, source("SRC-A", f"store:sha256/{SHA}", OTHER), store)
    assert state == "altered" and "not the source's" in cause


@pytest.mark.parametrize(
    "location",
    ["https://example.org/report.pdf", "C:/Users/someone/report.pdf", "/srv/report.pdf", "../outside/report.pdf"],
)
def test_what_cannot_be_looked_at_is_not_checked(repo, location):
    root, _ = repo
    assert check_source(root, source("SRC-A", location))[0] == "unchecked"


# ── The sources of a folder ─────────────────────────────────────────────────


def test_one_row_per_source_with_the_count(repo, store):
    root, rev = repo
    save(root, source("SRC-A", "originals/report.pdf"))
    save(root, source("SRC-B", f"git:{rev}:originals/report.pdf", OTHER))
    save(root, source("SRC-C", f"store:sha256/{OTHER}", OTHER))
    save(root, record("question"))
    res = check(root, "kb", store)
    assert [(f["id"], f["state"]) for f in res["sources"]] == [
        ("SRC-A", "matches"),
        ("SRC-B", "altered"),
        ("SRC-C", "unchecked"),
    ]
    assert res["sources"][0] == {
        "id": "SRC-A",
        "path": "kb/SRC-A.md",
        "location": "originals/report.pdf",
        "state": "matches",
        "cause": None,
    }
    assert res["count"] == {"matches": 1, "altered": 1, "missing": 0, "unchecked": 1}
    assert res["coverage"]["read"] == 4


def test_cli_all_match(repo, store, capsys):
    root, rev = repo
    save(root, source("SRC-A", "originals/report.pdf"))
    save(root, source("SRC-B", f"git:{rev}:originals/report.pdf"))
    save(root, source("SRC-C", f"store:sha256/{SHA}"))
    code, out = kb(capsys, "integrity", str(root), "--folder", "kb", "--store", str(store))
    assert code == 0 and out["operation"] == "integrity" and out["result"]["state"] == "completed", out
    assert out["result"]["count"]["matches"] == 3 and "code" not in out["result"]
    assert "last valid check of each source" in out["coverage"]["not_evaluated"]
    assert out["coverage"]["records_read"] == 3


def test_cli_a_broken_source_is_failed_with_its_code(repo, capsys):
    root, _ = repo
    save(root, source("SRC-A", "originals/report.pdf"))
    save(root, source("SRC-B", "originals/not-there.pdf"))
    save(root, source("SRC-C", f"store:sha256/{SHA}"))
    code, out = kb(capsys, "integrity", str(root), "--folder", "kb")
    assert code == 1 and out["result"]["state"] == "failed", out
    assert out["result"]["code"] == "INTEGRITY_BROKEN"
    assert out["result"]["count"] == {"matches": 1, "altered": 0, "missing": 1, "unchecked": 1}
    assert any(a.startswith("SRC-B (originals/not-there.pdf): missing") for a in out["warnings"])
    assert any(a.startswith("SRC-C ") and "unchecked" in a for a in out["warnings"])


def test_cli_unchecked_is_partial_and_not_broken(repo, capsys):
    root, _ = repo
    save(root, source("SRC-A", "originals/report.pdf"))
    save(root, source("SRC-C", f"store:sha256/{SHA}"))
    code, out = kb(capsys, "integrity", str(root), "--folder", "kb")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["code"] == "INTEGRITY_UNCHECKED"


def test_cli_a_source_that_does_not_load_leaves_the_check_partial(repo, capsys):
    root, _ = repo
    save(root, source("SRC-A", "originals/report.pdf"))
    (root / "kb" / "SRC-BROKEN.md").write_text("---\nid: [unclosed\n---\n", encoding="utf-8")
    code, out = kb(capsys, "integrity", str(root), "--folder", "kb")
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["count"]["matches"] == 1 and out["coverage"]["truncated"] is True
    assert "code" not in out["result"]


def test_cli_no_sources_is_partial_and_no_folder_failed(repo, capsys):
    root, _ = repo
    save(root, record("question"))
    code, out = kb(capsys, "integrity", str(root), "--folder", "kb")
    assert code == 3 and out["result"]["sources"] == [], out
    assert any("no source" in a for a in out["warnings"])
    code, out = kb(capsys, "integrity", str(root), "--folder", "does-not-exist")
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE", out
