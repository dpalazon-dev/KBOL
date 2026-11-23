"""verify (KB-DPP implementation 1.0, "verify" operation and check results; E7 bounded).

Only what the installation declares is run, without a shell; the result carries the tested revision and tree,
instants, code, duration and evidence, and is annotated in the handoff as executed by KBOL. It stops being valid if
the tree changes.
"""

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from kbol import handoff as rv
from kbol import verify as vf
from kbol.context import context, present

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def py(code):
    return ["{python}", "-c", code]


INSTALLATION = {
    "checks": {
        "ok": {"command": py("print('all good')"), "timeout": 30},
        "bad": {"command": py("import sys; print('broken'); sys.exit(3)"), "timeout": 30},
        "slow": {"command": py("import time; time.sleep(10)"), "timeout": 1},
        "missing": {"command": ["program-that-does-not-exist-kbol"], "timeout": 30},
        "dirties": {"command": py("open('dirty.txt', 'w').write('x')"), "timeout": 30},
        "three": {"command": py("import sys; sys.exit(3)"), "timeout": 30, "expected_code": 3},
    }
}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), *GIT, "commit", "-q", "-m", "base"], check=True)
    return root


def head(root):
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def annotated(root, task="t"):
    return rv.handoff(root, task)["checks"]


def test_a_check_that_passes_is_annotated_with_its_evidence(repo):
    r = vf.run(repo, "t", INSTALLATION, "ok")
    assert r["result"] == "passed" and r["handoff_result"] == "passed" and r["code"] == 0
    assert r["tested_revision"] == head(repo) and r["tested_tree"] and r["observations"] == []
    assert r["environment_ref"]["isolation"] == "none" and "all good" in r["final_output"]
    evidence = repo / r["evidence_ref"]["path"]
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == r["evidence_ref"]["sha256"]
    [v] = annotated(repo)
    assert v["origin"] == "kbol" and v["check_id"] == "ok" and v["result"] == "passed"
    assert v["outdated"] is False and v["started_at"] <= v["at"]


@pytest.mark.parametrize(
    "ident, contract, handoff, observation",
    [
        ("bad", "failed", "failed", None),
        ("three", "passed", "passed", None),
        ("slow", "requires_review", "unknown", "did not finish in 1 s"),
        ("missing", "not_run", "unknown", "did not start"),
        ("dirties", "requires_review", "unknown", "changed the working tree"),
    ],
)
def test_each_result_is_stated_as_it_is(repo, ident, contract, handoff, observation):
    r = vf.run(repo, "t", INSTALLATION, ident)
    assert r["result"] == contract and r["handoff_result"] == handoff
    if observation:
        assert any(observation in o for o in r["observations"])
        [v] = annotated(repo)
        assert observation in v["reason"]


def test_changing_the_tree_leaves_the_check_outdated(repo):
    vf.run(repo, "t", INSTALLATION, "ok")
    (repo / "a.txt").write_text("two\n", encoding="utf-8")  # uncommitted: the revision does not change
    assert annotated(repo)[0]["outdated"] is True
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    assert annotated(repo)[0]["outdated"] is False
    (repo / "new.txt").write_text("x\n", encoding="utf-8")  # a new file is also another tree
    assert annotated(repo)[0]["outdated"] is True


def test_kbol_local_state_does_not_change_the_tree(repo):
    before = rv.tree_fingerprint(repo)
    rv.save(repo, "other", {"goal": "x"})
    vf.run(repo, "t", INSTALLATION, "ok")  # writes evidence and handoff in .kbol/
    assert rv.tree_fingerprint(repo) == before


def test_repeating_a_check_replaces_the_previous_one(repo):
    vf.run(repo, "t", INSTALLATION, "bad")
    vf.run(repo, "t", INSTALLATION, "ok")
    vf.run(repo, "t", INSTALLATION, "bad")
    assert sorted((v["check_id"], v["result"]) for v in annotated(repo)) == [("bad", "failed"), ("ok", "passed")]


def test_a_failure_followed_by_a_success_stays_in_the_history(repo):
    """The replaced run moves to the history, without its full output, and saving the handoff does not lose it."""
    vf.run(repo, "t", INSTALLATION, "three")
    vf.run(repo, "t", INSTALLATION, "bad")
    vf.run(repo, "t", INSTALLATION, "bad")
    rv.save(repo, "t", {"goal": "x"})
    history = rv.handoff(repo, "t")["check_history"]
    assert [(v["check_id"], v["result"]) for v in history] == [("bad", "failed")]
    assert history[0]["evidence"]["deleted"] is True
    assert not (repo / history[0]["evidence"]["path"]).exists()
    assert [(v["check_id"], v["result"]) for v in annotated(repo)] == [("three", "passed"), ("bad", "failed")]


def test_the_history_is_bounded(repo, monkeypatch):
    monkeypatch.setattr(rv, "HISTORY", 2)
    for _ in range(4):
        vf.run(repo, "t", INSTALLATION, "ok")
    assert len(rv.handoff(repo, "t")["check_history"]) == 2


def test_save_keeps_the_executed_ones_and_does_not_let_them_be_written(repo):
    vf.run(repo, "t", INSTALLATION, "ok")
    rv.save(repo, "t", {"goal": "x", "checks": [{"command": "by hand", "result": "not_run"}]})
    assert {v.get("origin", "session") for v in annotated(repo)} == {"kbol", "session"}
    fake = {"command": "ok", "result": "passed", "revision": "abc", "at": "2026-11-05T00:00:00Z", "origin": "kbol"}
    with pytest.raises(ValueError, match="kbol verify"):
        rv.save(repo, "t", {"goal": "x", "checks": [fake]})


def test_what_is_not_declared_is_not_run(repo):
    with pytest.raises(ValueError, match="not declared"):
        vf.run(repo, "t", INSTALLATION, "rm-rf")
    with pytest.raises(ValueError, match="task id"):
        vf.run(repo, "../outside", INSTALLATION, "dirties")
    assert not (repo / "dirty.txt").exists() and not (repo / ".kbol").exists()


@pytest.mark.parametrize(
    "declared, error",
    [
        ({"x": {"command": "pytest -q", "timeout": 10}}, "list"),
        ({"x": {"command": [], "timeout": 10}}, "list"),
        ({"x": {"command": ["pytest"], "timeout": True}}, "timeout"),
        ({"x": {"command": ["pytest"], "timeout": 0}}, "timeout"),
        ({"x": {"command": ["pytest"], "timeout": 10, "shell": True}}, "admits"),
        ({"X Y": {"command": ["pytest"], "timeout": 10}}, "check id"),
        ([], "object"),
    ],
)
def test_declared_checks_are_validated(declared, error):
    with pytest.raises(ValueError, match=error):
        vf.checks_of({"checks": declared})


def test_the_package_tells_the_executed_from_the_declared(repo):
    vf.run(repo, "t", INSTALLATION, "bad")
    rv.save(repo, "t", {"goal": "x", "checks": [{"command": "by hand", "result": "not_run"}]})
    (repo / "kb").mkdir()
    installation = {**INSTALLATION, "instructions": [], "procedures": []}
    text = present(
        context(
            repo,
            task="t",
            goal=None,
            scope="a",
            folder="kb",
            installation=installation,
            valid_at="2026-11-20T00:00:00Z",
        )
    )
    assert "Check failed (annotated by kbol verify, without receipt): bad:" in text
    assert "Check not_run (declared by the session): by hand" in text


def commit(root, message="change"):
    subprocess.run(["git", "-C", str(root), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), *GIT, "commit", "-q", "-m", message], check=True)


def kb_verify(repo, installation, *extra):
    command = [
        sys.executable,
        "-m",
        "kbol.cli",
        "verify",
        str(repo),
        "--task",
        "t",
        "--installation",
        str(installation),
    ]
    p = subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def test_cli_verify_with_the_integrated_installation(repo):
    installation = repo / "installation.json"
    installation.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    commit(repo)
    code, output = kb_verify(repo, installation, "--check", "ok")
    assert code == 0 and output["operation"] == "verify"
    assert output["result"]["result"] == "passed" and output["revision"] == head(repo)
    assert output["result"]["declaration"]["path"] == "installation.json"
    assert "isolation of the run" in output["coverage"]["not_evaluated"]
    code, output = kb_verify(repo, installation)
    assert code == 2 and "--check" in output["result"]["reason"]


def test_cli_does_not_run_an_installation_that_is_not_the_integrated_one(repo, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    code, output = kb_verify(repo, outside, "--check", "ok")
    assert code == 1 and "inside the root" in output["result"]["reason"]
    loose = repo / "loose.json"
    loose.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    code, output = kb_verify(repo, loose, "--check", "ok")
    assert code == 1 and "is not versioned" in output["result"]["reason"]
    commit(repo)
    other = {"checks": {"ok": {"command": py("open('pwned', 'w')"), "timeout": 30}}}
    loose.write_text(json.dumps(other), encoding="utf-8")
    code, output = kb_verify(repo, loose, "--check", "ok")
    assert code == 1 and "uncommitted changes" in output["result"]["reason"] and not (repo / "pwned").exists()


def test_a_grandchild_that_does_not_finish_does_not_hang_the_check(repo):
    # The child launches a grandchild that inherits the output and sleeps; with pipes, run() would wait for it forever.
    grandchild = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
    installation = {"checks": {"grandchild": {"command": py(grandchild), "timeout": 2}}}
    start = time.monotonic()
    r = vf.run(repo, "t", installation, "grandchild")
    assert time.monotonic() - start < 20
    assert r["result"] == "requires_review" and "all its processes" in r["observations"][0]


def test_a_command_that_ends_leaving_a_grandchild_alive_does_not_wait_for_it(repo):
    leaves = (
        "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(8)']); print('done')"
    )
    installation = {"checks": {"leaves": {"command": py(leaves), "timeout": 30}}}
    start = time.monotonic()
    r = vf.run(repo, "t", installation, "leaves")
    assert time.monotonic() - start < 6 and r["result"] == "passed" and "done" in r["final_output"]


def test_a_head_change_during_the_check_does_not_pass(repo):
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    code = f"import subprocess; subprocess.run(['git', *{ident!r}, 'commit', '-q', '--allow-empty', '-m', 'x'])"
    r = vf.run(repo, "t", {"checks": {"moves": {"command": py(code), "timeout": 30}}}, "moves")
    assert r["result"] == "requires_review" and any("head" in o for o in r["observations"])


def test_simultaneous_checks_and_saves_do_not_overwrite_each_other(repo):
    ids = ["ok", "bad", "three"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(vf.run, repo, "t", INSTALLATION, i) for i in ids]
        jobs.append(pool.submit(rv.save, repo, "t", {"goal": "x"}))
        for f in jobs:
            f.result()
    assert sorted(v["check_id"] for v in annotated(repo)) == sorted(ids)
    assert rv.handoff(repo, "t")["goal"] == "x"


def test_repeating_deletes_the_replaced_evidence(repo):
    vf.run(repo, "t", INSTALLATION, "ok")
    vf.run(repo, "t", INSTALLATION, "ok")
    [v] = annotated(repo)
    logs = list((repo / ".kbol" / "checks" / "t").glob("ok-*.log"))
    assert [p.relative_to(repo).as_posix() for p in logs] == [v["evidence"]["path"]]


@pytest.mark.parametrize("task", ["NUL", "con.log", "a."])
def test_names_windows_does_not_admit(repo, task):
    with pytest.raises(ValueError, match="Windows"):
        vf.run(repo, task, INSTALLATION, "dirties")
    assert not (repo / "dirty.txt").exists()


def test_the_command_does_not_admit_line_breaks():
    with pytest.raises(ValueError, match="single-line"):
        vf.checks_of({"checks": {"x": {"command": ["pytest", "a\nConstraints:"], "timeout": 10}}})


def test_the_command_does_not_inherit_the_token_or_git(repo, monkeypatch):
    monkeypatch.setenv("KB_GITHUB_TOKEN", "kbol-secret")
    monkeypatch.setenv("GIT_DIR", "somewhere-else")
    code = "import os; print([k for k in os.environ if k.upper() == 'KB_GITHUB_TOKEN' or k.upper().startswith('GIT_')])"
    r = vf.run(repo, "t", {"checks": {"env": {"command": py(code), "timeout": 30}}}, "env")
    assert r["final_output"] == ["[]"]


def test_the_interpreter_is_the_root_one_if_it_has_one(tmp_path):
    assert vf.python_of(tmp_path) == (sys.executable, True)
    own = tmp_path / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    own.parent.mkdir(parents=True)
    own.write_text("", encoding="utf-8")
    assert vf.python_of(tmp_path) == (str(own), False)
