"""`kbol session`: the knowledge logic of the hooks of an installation, behind one command.

`start` gives the context package and the drift and reuses them while what decides them does not change; `stop`
validates as proposals the records with uncommitted changes; `commit` warns about the drift of the index without
blocking.
"""

import json
import subprocess
import sys

import pytest
from conftest import decision, event, record

from kbol import handoff as rv
from kbol import session
from kbol.core import serialize
from kbol.fingerprints import ARCHIVE, fingerprint

V = "2026-11-20T00:00:00Z"
INSTALLATION = {
    "project": "Test",
    "canonical_branch": "main",
    "records_folder": "kb",
    "scope": "operations",
    "budget": 50,
    "instructions": [{"ref": "AGENTS.md#limits", "summary": "merge only with sign-off", "decisive": True}],
}


def git(root, *args):
    command = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@localhost", "-c", "core.autocrlf=false"]
    return subprocess.run([*command, *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def write(root, name, r, c="", mode="canonical"):
    path = root / "kb" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(r, c, mode=mode), encoding="utf-8", newline="\n")
    return path


def configure(root, **changes):
    path = root / "installation.json"
    path.write_text(json.dumps({**INSTALLATION, **changes}), encoding="utf-8")
    return path


@pytest.fixture
def root(tmp_path):
    """A repository with the role, an in-force decision and an open question, with their fingerprints, on feat/x."""
    creation = event("creation", event_id="E0", previous_state=None, new_state="proposed")
    opened = event("creation", event_id="E0", previous_state=None, new_state="open")
    paths = {
        "ROLE-EXAMPLE": write(tmp_path, "ROLE", record("role", events=[creation])),
        "DEC-A": write(tmp_path, "DEC-A", *decision("DEC-A", {"C1": "Only checked data."})),
        "Q-A": write(tmp_path, "Q-A", record("question", events=[opened])),
    }
    fingerprints = {i: {"path": f"kb/{r.name}", "sha256": fingerprint(r.read_bytes())} for i, r in paths.items()}
    (tmp_path / "kb" / ARCHIVE).write_text(json.dumps(fingerprints), encoding="utf-8")
    configure(tmp_path)
    (tmp_path / ".gitignore").write_text(".kbol/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "feat/x")
    return tmp_path


def start(root, **kw):
    return session.start(root, "installation.json", **kw)


def cli(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


# --- start ---


def test_start_gives_the_package_and_the_drift_with_the_task_of_the_branch(root):
    res = start(root)
    r = res["result"]
    assert res["code"] == 0 and r["state"] == "completed", r
    assert r["task"] == "feat-x" and r["package"]["task"] == "feat-x"
    assert "Only checked data." in [x["text"] for x in r["package"]["constraints"]]
    assert r["drift"] == {"checked": 3, "alerts": []}
    assert "Only checked data." in res["text"] and "KBOL drift" not in res["text"]


def test_start_reads_the_clock_only_if_not_given_the_cut_and_declares_it(root):
    assert start(root, valid_at=V)["valid_at"] == V
    given = start(root)["valid_at"]
    assert given != V and rv.is_instant(given)
    with pytest.raises(ValueError, match="instant"):
        start(root, valid_at="2026-11-20")


def test_start_resolves_the_root_from_any_folder_of_the_tree(root):
    assert start(root / "kb")["result"]["state"] == "completed"
    assert (root / ".kbol" / "session" / "start-feat-x.json").is_file()


def test_start_reuses_what_was_saved_while_what_decides_it_does_not_change(root):
    first = start(root, valid_at=V)["result"]
    second = start(root, valid_at=V)["result"]
    assert not first["reused"] and second["reused"]
    assert second["package"]["package_id"] == first["package"]["package_id"]
    assert second["fingerprint"] == first["fingerprint"]


@pytest.mark.parametrize("change", ["record", "handoff", "installation", "cut", "commit", "task"])
def test_start_recomputes_when_what_decides_it_changes(root, change):
    before = start(root, valid_at=V)["result"]
    arguments = {"valid_at": V}
    if change == "record":
        write(root, "DEC-B", *decision("DEC-B", {"C1": "Report on Mondays."}))
    elif change == "handoff":
        rv.save(root, "feat-x", {"goal": "Prepare the report"})
    elif change == "installation":
        configure(root, budget=40)
    elif change == "cut":
        arguments["valid_at"] = "2026-11-21T00:00:00Z"
    elif change == "commit":
        git(root, "commit", "-q", "--allow-empty", "-m", "another")
    else:
        arguments["task"] = "other"
    after = start(root, **arguments)["result"]
    assert not after["reused"] and after["fingerprint"] != before["fingerprint"]


def test_start_does_not_reuse_a_broken_saved_result(root):
    fingerprint = start(root, valid_at=V)["result"]["fingerprint"]
    saved = root / ".kbol" / "session" / "start-feat-x.json"
    for content in ("{", json.dumps({"fingerprint": fingerprint, "computed": {"package": {}, "drift": {}}})):
        saved.write_text(content, encoding="utf-8")
        res = start(root, valid_at=V)["result"]
        assert not res["reused"] and res["state"] == "completed"


def test_start_with_the_given_task_recomputes_when_the_branch_changes(root):
    before = start(root, valid_at=V, task="report")["result"]
    git(root, "checkout", "-q", "-b", "feat/y")
    after = start(root, valid_at=V, task="report")["result"]
    assert not after["reused"] and after["package"]["handoff"]["git"]["branch"] == "feat/y"
    assert before["package"]["handoff"]["git"]["branch"] == "feat/x"


def test_start_gives_the_result_even_if_it_cannot_save_it(root):
    (root / ".kbol").mkdir()
    (root / ".kbol" / "session").write_text("a file where the folder would go", encoding="utf-8")
    res = start(root, valid_at=V)
    assert res["code"] == 0 and not res["result"]["reused"]


def test_start_warns_about_a_drift_without_changing_the_code(root):
    path = root / "kb" / "Q-A.md"
    path.write_text(path.read_text(encoding="utf-8").replace("One line.", "Another line."), encoding="utf-8")
    res = start(root)
    assert res["code"] == 0
    assert [a["id"] for a in res["result"]["drift"]["alerts"]] == ["Q-A"]
    assert "1 differ from what was integrated (Q-A)" in res["text"] and "main" in res["text"]
    assert any(a.startswith("Q-A (kb/Q-A.md)") for a in res["warnings"])


def test_start_is_partial_if_loading_is_and_the_text_says_so(root):
    (root / "kb" / "broken.md").write_text("no header\n", encoding="utf-8")
    res = start(root)
    assert res["code"] == 3 and res["result"]["state"] == "partial"
    assert "Package partial" in res["text"] and res["coverage"]["invalid"]


def test_blocked_start_exits_with_2_and_still_gives_the_text(root):
    copy, body = decision("DEC-A", {"C1": "Something else."})
    write(root, "DEC-A-copy", copy, body)
    res = start(root)
    assert res["code"] == 2 and res["result"]["state"] == "blocked"
    assert "Package blocked" in res["text"]


def test_start_without_records_with_history_does_not_take_the_drift_as_checked(tmp_path):
    write(tmp_path, "Q-A", record("question"), mode="proposal")
    configure(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    res = start(tmp_path)
    assert res["code"] == 3 and "drift" in res["result"]["reason"]
    assert "no record with history was checked" in res["text"]


def test_after_compacting_the_text_carries_the_work_of_the_task_in_git(root):
    git(root, "commit", "-q", "--allow-empty", "-m", "first step")
    (root / "notes.txt").write_text("x", encoding="utf-8")
    (root / "other.txt").write_text("x", encoding="utf-8")
    normal = start(root)["text"]
    compacted = start(root, origin="compact")["text"]
    assert "Task work in git" not in normal
    assert "Task work in git (branch feat/x)" in compacted
    assert "Own commits (1): first step" in compacted
    assert "Uncommitted changes (2)" in compacted and "  other.txt" in compacted


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"records_folder": None}, "records_folder"),
        ({"records_folder": "kb,"}, "records_folder"),
        ({"scope": 3}, "scope"),
        ({"budget": True}, "budget"),
        ({"canonical_branch": 1}, "canonical_branch"),
    ],
)
def test_start_rejects_an_installation_without_what_it_needs(root, changes, reason):
    configure(root, **changes)
    with pytest.raises(ValueError, match=reason):
        start(root)


def test_start_and_commit_read_with_the_legacy_format_of_the_installation(root):
    format = {"records": {"Decision Record": {"type": "decision", "id": r"DEC-\d{3,}"}}}
    configure(root, legacy_format=format)
    legacy = "---\ntype: Decision Record\nid: {}\ntitle: Example\nstate: Accepted\n---\n\n# Example\n"
    path = root / "kb" / "DEC-108.md"
    path.write_text(legacy.format("DEC-108"), encoding="utf-8", newline="\n")
    assert start(root)["code"] == 0  # the legacy record is read apart, with its format, and is not in force
    path.write_text(legacy.format("DEC-1"), encoding="utf-8", newline="\n")
    res = start(root)
    assert res["code"] == 3 and res["coverage"]["invalid"]  # an ID outside the pattern of its label
    git(root, "add", "kb/DEC-108.md")
    assert session.commit(root, "installation.json")["code"] == 3
    configure(root, legacy_format={"records": {}})
    with pytest.raises(ValueError, match="legacy_format"):
        start(root)


def test_outside_a_git_tree_there_is_no_session(tmp_path):
    configure(tmp_path)
    with pytest.raises(ValueError, match="working tree"):
        start(tmp_path)


def test_the_task_of_the_branch_follows_the_pattern_of_the_handoff(root):
    assert session.task_of_branch(root) == "feat-x"
    git(root, "checkout", "-q", "-b", "_fix/a+b/c.d")
    task = session.task_of_branch(root)
    assert task == "fix-a-b-c.d" and rv.handoff_path(root, task)
    git(root, "checkout", "-q", "--detach")
    assert session.task_of_branch(root) == "no-branch"


# --- stop ---


def stop(root, **kw):
    return session.stop(root, "installation.json", **kw)


def without_condition(root, ident):
    """A question that lacks a required field: it does not validate as a proposal."""
    path = write(root, ident, record("question", id=ident), mode="proposal")
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if not x.startswith("closing_condition:")]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def test_stop_without_records_with_changes_has_examined_nothing(root):
    (root / "notes.md").write_text("outside the folders\n", encoding="utf-8")
    res = stop(root)
    assert res["code"] == 3 and res["result"]["state"] == "partial"
    assert res["result"]["examined"] == 0 and res["text"] == "" and res["warnings"]


def test_stop_validates_as_proposal_what_is_still_uncommitted(root):
    write(root, "Q-N", record("question", id="Q-N"), mode="proposal")
    res = stop(root)
    assert res["code"] == 0 and res["result"]["examined"] == 1 and res["text"] == ""
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "question")
    assert stop(root)["result"]["examined"] == 0  # what is already committed is not from this turn


def test_stop_rejects_a_record_that_does_not_validate_and_says_why(root):
    without_condition(root, "Q-N")
    (root / "kb" / "broken.md").write_text("no header\n", encoding="utf-8")
    res = stop(root)
    r = res["result"]
    assert res["code"] == 1 and r["state"] == "failed" and r["code"] == "INVALID_SCHEMA"
    assert [x["path"] for x in r["rejected"]] == ["kb/Q-N.md", "kb/broken.md"] and r["examined"] == 2
    assert "closing_condition" in json.dumps(r["rejected"][0]["errors"], ensure_ascii=False)
    assert res["text"].startswith("KBOL rejects") and "kb/Q-N.md:" in res["text"] and "kb/broken.md:" in res["text"]


def test_stop_with_paths_only_looks_at_what_the_session_edited(root):
    without_condition(root, "Q-N")
    write(root, "Q-M", record("question", id="Q-M"), mode="proposal")
    assert stop(root, paths=["kb/Q-M.md"])["code"] == 0
    assert stop(root, paths=[])["code"] == 3
    assert stop(root, paths=[str(root / "kb" / "Q-N.md"), "kb\\Q-M.md"])["result"]["examined"] == 2
    assert stop(root, paths=["kb/DEC-A.md"])["code"] == 3  # edited and already committed: nothing to validate
    configure(root, records_folder="./kb/")
    assert stop(root, paths=["./kb/Q-M.md"])["result"]["examined"] == 1


def test_stop_does_not_count_what_is_not_a_record_of_the_profile(root):
    (root / "kb" / "guide.md").write_text("---\ntype: Guide\ntitle: x\n---\nText.\n", encoding="utf-8")
    (root / "kb" / "index.md").write_text("index\n", encoding="utf-8")
    res = stop(root)
    assert res["code"] == 3 and res["result"]["no_records"] == ["kb/guide.md"]


# --- commit ---


def test_commit_warns_about_what_goes_into_the_commit_and_does_not_block(root):
    path = root / "kb" / "Q-A.md"
    path.write_text(path.read_text(encoding="utf-8").replace("One line.", "Another line."), encoding="utf-8")
    unstaged = session.commit(root, "installation.json")
    assert unstaged["code"] == 0 and unstaged["text"] == ""
    git(root, "add", "kb/Q-A.md")
    res = session.commit(root, "installation.json")
    assert res["code"] == 0 and res["result"]["state"] == "completed" and res["result"]["checked"] == 3
    assert res["text"] == (
        "warning: Q-A (kb/Q-A.md) differs from what was integrated in main: propose it through integration"
    )


def test_commit_without_records_with_history_is_partial(tmp_path):
    write(tmp_path, "Q-A", record("question"), mode="proposal")
    configure(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git(tmp_path, "add", "-A")
    res = session.commit(tmp_path, "installation.json")
    assert res["code"] == 3 and res["result"]["state"] == "partial"


# --- CLI ---


def test_the_cli_returns_the_envelope_with_the_cut_it_used(root):
    code, output = cli("session", str(root / "kb"), "--event", "start", "--installation", "installation.json")
    envelope = json.loads(output)
    assert code == 0 and envelope["operation"] == "session" and envelope["revision"] == "disk"
    assert envelope["valid_at"] and envelope["result"]["event"] == "start"
    assert envelope["coverage"]["read"] == 3 and "who made the edit" in envelope["coverage"]["not_evaluated"]
    assert "warnings" not in envelope["result"]["package"]


def test_the_cli_with_text_gives_only_what_is_injected(root):
    args = ("--installation", str(root / "installation.json"), "--text")
    code, output = cli("session", str(root), "--event", "start", "--task", "report", *args)
    assert code == 0 and output.startswith("KBOL context for task report")
    code, output = cli("session", str(root), "--event", "stop", *args)
    assert code == 3 and output.strip() == ""
    (root / "kb" / "broken.md").write_text("no header\n", encoding="utf-8")
    code, output = cli("session", str(root), "--event", "stop", "--paths", "kb/broken.md", *args)
    assert code == 1 and "kb/broken.md" in output


def test_the_cli_fails_closed_without_event_without_installation_or_with_an_unreadable_one(root):
    code, output = cli("session", str(root), "--installation", "installation.json")
    assert code == 2 and "--event" in json.loads(output)["result"]["reason"]
    code, output = cli("session", str(root), "--event", "start")
    assert code == 2 and "--installation" in json.loads(output)["result"]["reason"]
    code, output = cli("session", str(root), "--event", "start", "--installation", "does-not-exist.json", "--text")
    assert code == 1 and json.loads(output)["result"]["code"] == "MISSING_REFERENCE"
    (root / "installation.json").write_text("{", encoding="utf-8")
    code, output = cli("session", str(root), "--event", "commit", "--installation", "installation.json")
    assert code == 1 and json.loads(output)["result"]["code"] == "INVALID_SCHEMA"
