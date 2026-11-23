"""CLI `consolidate` and `ready` over a snapshot from the disk or from a git revision."""

import json
import subprocess
import sys

from conftest import decision, event, record

from kbol.core import serialize
from kbol.snapshot import load


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def write_esc01(folder, tuesday=True, valid_role=False):
    a = decision("DEC-A", {"C1": "Monday.", "C2": "Checked data."}, recorded="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Tuesday." if tuesday else "Thursday."},
        recorded="2026-11-02T00:00:00Z",
        amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
    )
    creation = event("creation", event_id="E0", previous_state=None, new_state="proposed")
    role = record("role", events=[creation] if valid_role else [])
    folder.mkdir(parents=True, exist_ok=True)
    for (r, c), name in ((a, "DEC-A"), (b, "DEC-B")):
        (folder / f"{name}.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")
    (folder / "ROLE.md").write_text(serialize(role, ""), encoding="utf-8", newline="\n")
    (folder / "legacy.md").write_text("---\ntype: Decision\nid: ADR-0001\n---\n", encoding="utf-8")


def texts(out):
    return [c["text"] for c in out["result"]["clauses"] if c["state"] == "current"]


def test_consolidate_from_disk(tmp_path):
    write_esc01(tmp_path / "kb")
    code, out = kb(
        "consolidate", str(tmp_path), "--folder", "kb", "--ids", "DEC-A", "--valid-at", "2026-11-03T12:00:00Z"
    )
    # The role without history is not canonical: it is left out and the query is partial; the legacy one is omitted.
    assert code == 3 and out["result"]["state"] == "partial", out
    assert texts(out) == ["Tuesday.", "Checked data."]
    assert out["valid_at"] == "2026-11-03T12:00:00Z" and out["known_until"] is None
    assert out["revision"] == "disk" and any("disk" in a for a in out["warnings"])
    assert any("knowledge cut" in a for a in out["warnings"])
    assert out["coverage"]["records_read"] == 2 and out["coverage"]["omitted"] == 1
    assert out["coverage"]["truncated"] is True
    assert [i["path"] for i in out["coverage"]["invalid"]] == ["kb/ROLE.md"]


def test_consolidate_requires_an_explicit_well_formed_clock(tmp_path):
    write_esc01(tmp_path)
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A")
    assert code == 2 and "valid-at" in out["result"]["reason"]
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", "2026-11-03")
    assert code == 2 and out["result"]["code"] == "AMBIGUOUS_TIME"


def test_git_revision_ignores_unintegrated_changes(tmp_path):
    repo = tmp_path / "repo"
    write_esc01(repo / "kb", valid_role=True)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    rev = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    write_esc01(repo / "kb", tuesday=False, valid_role=True)  # change on disk, without a commit
    snap, _ = load(repo, "kb", rev)
    assert snap.revision == rev and "Tuesday." in snap.bodies["DEC-B"]
    code, out = kb(
        "consolidate",
        str(repo),
        "--folder",
        "kb",
        "--revision",
        rev,
        "--ids",
        "DEC-A",
        "--valid-at",
        "2026-11-03T12:00:00Z",
    )
    assert code == 0 and texts(out)[0] == "Tuesday." and out["revision"] == rev


def test_ready_through_cli(tmp_path):
    (tmp_path / "empty").mkdir()
    code, out = kb(
        "ready",
        str(tmp_path / "empty"),
        "--valid-at",
        "2026-11-03T12:00:00Z",
        "--known-until",
        "2026-11-03T12:00:00Z",
    )
    # A folder without milestones was not examined: it is not a correct "nothing ready".
    assert code == 3 and out["result"]["state"] == "partial", out
    assert out["result"]["ready"] == [] and out["result"]["milestones_examined"] == 0
    assert out["known_until"] == "2026-11-03T12:00:00Z"
    assert any("no milestone examined" in a for a in out["warnings"])
