"""`kbol propose`: from the working tree to the canonical branch, through the integrator's clone and without skipping
the gate.

The remote is a local `--bare` repository and the installation state (`KBOL_STATE`) a temporary folder: nothing leaves
the machine. What matters: the dry run changes nothing; whoever collects the approval gives it, with the package
digests, and it goes stale if the content changes; what was integrated and not pushed is not lost, and the after steps
only write views.
"""

import copy
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from conftest import DECISION_BODY, decision, record
from test_integrate import Repo, active, canonical

from kbol.core import parse, serialize
from kbol.propose import integration_of, is_view, propose

INSTANT = "2026-11-05T18:00:00Z"
# Without previous_state: the gate fills it in before the digest, and what is approved has to come from its same code.
ACCEPT = {"DEC-X": [{"new_state": "accepted", "valid_from": "2026-11-05T00:00:00Z"}]}
AGENT = "claude-code/opus-5.5"
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def py(code):
    return {"command": ["{python}", "-c", code], "timeout": 60}


WRITES_INDEX = py("import pathlib; pathlib.Path('kb/index.md').write_bytes(b'index\\n')")


def git_in(path, *args):
    p = subprocess.run(["git", "-C", str(path), *IDENT, *args], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """An installation with its remote: a person with a role, an accepted decision and the configuration on the branch."""
    monkeypatch.setenv("KBOL_STATE", str(tmp_path / "state"))
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo = Repo(tmp_path / "repo")
    role = active("role", "ROLE-OP", scopes=["operations"], capabilities=["ratify"], approval_rule="one")
    per = active(
        "person",
        "PER-H",
        nature="human",
        identity_ref="declared:h",
        holds=[{"role": "ROLE-OP", "from": "2026-10-02T00:00:00Z"}],
    )
    a, ca = decision("DEC-A", {"C1": "Monday."}, recorded="2026-10-03T00:00:00Z", authorized_by=["ROLE-OP"])
    for ident, r, c in (("ROLE-OP", role, ""), ("PER-H", per, ""), ("DEC-A", a, ca)):
        repo.write(f"kb/{ident}.md", canonical(r, c))
    installation = {
        "canonical_branch": "main",
        "records_folder": "kb",
        "integration": {"remote": remote.as_posix(), "repository": "test"},
    }
    repo.write("kbol.json", json.dumps(installation))
    base = repo.commit("base")
    repo.git("remote", "add", "origin", str(remote))
    repo.git("push", "-q", "origin", "main")
    clone = tmp_path / "state" / "test" / "integrator.git"
    return SimpleNamespace(repo=repo, remote=remote, base=base, installation=installation, clone=clone, tmp=tmp_path)


def with_config(inst, checks=None, **integration):
    installation = copy.deepcopy(inst.installation)
    installation["integration"].update(integration)
    if checks:
        installation["checks"] = checks
    return installation


def new_decision(inst):
    r = record("decision", id="DEC-X", authorized_by=["ROLE-OP"])
    inst.repo.write("kb/DEC-X.md", serialize(r, DECISION_BODY))
    return ["kb/DEC-X.md"]


def new_question(inst, ident="Q-N"):
    r = record("question", id=ident, owner="ROLE-OP")
    inst.repo.write(f"kb/{ident}.md", serialize(r, "Text.\n"))
    return [f"kb/{ident}.md"]


def sign(package):
    """What whoever collects the approval provides; the digests and the base shown come from the package."""
    return [
        {**e, "identity": "declared:h", "session": "test session", "instant": INSTANT, "quote": "Yes, I accept DEC-X"}
        for e in package["approvals"]
    ]


def accept(inst, installation=None, **kw):
    return propose(
        inst.repo.root,
        installation or inst.installation,
        operation_id="op-1",
        files=new_decision(inst),
        effects=ACCEPT,
        **kw,
    )


def on_the_remote(inst):
    return git_in(inst.remote, "rev-parse", "main")


def someone_pushes(inst):
    """Someone else pushes a commit to the canonical branch of the remote."""
    other = inst.tmp / "other"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(inst.remote), str(other)], check=True)
    (other / "README.md").write_text("other\n", encoding="utf-8")
    git_in(other, "add", "-A")
    git_in(other, "commit", "-q", "-m", "other")
    git_in(other, "push", "-q", "origin", "main")
    return git_in(other, "rev-parse", "HEAD")


def test_the_dry_run_without_approval_returns_the_package_and_changes_nothing(inst):
    res = accept(inst)
    assert res["state"] == "pending_approval" and res["code"] == "INSUFFICIENT_AUTHORITY", res
    package = res["package"]
    assert [r["id"] for r in package["records"]] == ["DEC-X"]
    skeleton = package["approvals"][0]
    assert skeleton["base_shown"] == inst.base and set(skeleton["digests"]) == {"DEC-X"}
    assert all(skeleton[k] is None for k in ("identity", "session", "instant", "quote"))
    assert on_the_remote(inst) == inst.base and git_in(inst.clone, "rev-parse", "main") == inst.base
    assert git_in(inst.clone, "for-each-ref", "--format=%(refname)", "refs/heads/") == "refs/heads/main"
    assert not (inst.clone.parent / "receipts").exists()


def test_the_signed_package_integrates_pushes_and_leaves_the_quote_and_the_receipt(inst):
    package = accept(inst)["package"]
    dry_run = accept(inst, approvals=sign(package))
    assert dry_run["state"] == "dry_run_done" and dry_run["decisive"] == ["DEC-X"], dry_run
    assert on_the_remote(inst) == inst.base
    res = accept(inst, approvals=sign(package), until="push")
    assert res["state"] == "pushed" and res["pushed"] and res["pending_push"] == 0, res
    assert on_the_remote(inst) == res["integrated_revision"] == git_in(inst.clone, "rev-parse", "main")
    meta, _ = parse(git_in(inst.remote, "show", "main:kb/DEC-X.md") + "\n")
    assert meta["state"] == "accepted"
    ratification = next(e for e in meta["events"] if e["event_type"] == "ratification")
    assert ratification["approval"]["proof"]["quote"] == "Yes, I accept DEC-X"
    receipt = json.loads((inst.clone.parent / "receipts" / "op-1.json").read_text(encoding="utf-8"))
    assert receipt["integrated_revision"] == res["integrated_revision"]
    assert receipt["approval_details"][0]["proof"]["digests"] == package["approvals"][0]["digests"]


def test_if_the_content_changes_after_showing_it_the_approval_goes_stale(inst):
    approvals = sign(accept(inst)["package"])
    r = record("decision", id="DEC-X", authorized_by=["ROLE-OP"], rationale="Something else.")
    inst.repo.write("kb/DEC-X.md", serialize(r, DECISION_BODY))
    res = propose(
        inst.repo.root,
        inst.installation,
        operation_id="op-1",
        files=["kb/DEC-X.md"],
        effects=ACCEPT,
        approvals=approvals,
        until="push",
    )
    assert res["state"] == "blocked" and res["code"] == "STALE_APPROVAL", res
    assert on_the_remote(inst) == inst.base and git_in(inst.clone, "rev-parse", "main") == inst.base


@pytest.mark.parametrize("mode", ["all", "decisive"])
def test_without_approval_the_decisive_is_neither_integrated_nor_pushed(inst, mode):
    res = accept(inst, with_config(inst, approval=mode), actor=AGENT, until="push")
    assert res["state"] == "blocked" and res["code"] == "INSUFFICIENT_AUTHORITY", res
    assert on_the_remote(inst) == inst.base and git_in(inst.clone, "rev-parse", "main") == inst.base


@pytest.mark.parametrize("approvals", [[{"mechanism": "github-review", "pull": 1, "review_id": 1}], {"a": 1}])
def test_only_admits_declared_approvals(inst, approvals):
    res = accept(inst, approvals=approvals, until="push")
    assert res["state"] == "blocked" and "declared" in res["reason"]
    assert not inst.clone.exists()


def test_in_decisive_mode_the_non_decisive_dry_runs_fully_with_the_actor(inst):
    installation = with_config(inst, approval="decisive")
    files = new_question(inst)
    res = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT)
    assert res["state"] == "dry_run_done" and res["decisive"] == [] and res["records"] == ["Q-N"], res
    assert git_in(inst.clone, "rev-parse", "main") == inst.base
    without_actor = propose(inst.repo.root, installation, operation_id="op-1", files=files)
    assert without_actor["state"] == "blocked" and "actor" in without_actor["reason"]


def test_integrated_and_not_pushed_is_not_lost_and_pushes_with_the_next(inst):
    installation = with_config(inst, approval="decisive")
    one = propose(
        inst.repo.root, installation, operation_id="op-1", files=new_question(inst), actor=AGENT, until="integrate"
    )
    assert one["state"] == "integrated" and not one["pushed"] and one["pending_push"] == 1, one
    assert on_the_remote(inst) == inst.base
    two = propose(
        inst.repo.root,
        installation,
        operation_id="op-2",
        files=new_question(inst, "Q-M"),
        actor=AGENT,
        until="push",
    )
    assert two["state"] == "pushed" and two["base"] == one["integrated_revision"], two
    assert on_the_remote(inst) == two["integrated_revision"]
    assert git_in(inst.remote, "show", "main:kb/Q-N.md") and git_in(inst.remote, "show", "main:kb/Q-M.md")


def test_if_the_remote_moves_on_the_proposal_goes_on_its_head(inst):
    accept(inst)
    new = someone_pushes(inst)
    res = accept(inst)
    assert res["base"] == new and res["package"]["approvals"][0]["base_shown"] == new


def test_if_the_clone_and_the_remote_diverge_it_blocks_without_discarding_anything(inst):
    installation = with_config(inst, approval="decisive")
    one = propose(
        inst.repo.root, installation, operation_id="op-1", files=new_question(inst), actor=AGENT, until="integrate"
    )
    someone_pushes(inst)
    two = propose(inst.repo.root, installation, operation_id="op-2", files=new_question(inst, "Q-M"), actor=AGENT)
    assert two["state"] == "blocked" and two["code"] == "BASE_CHANGED", two
    assert git_in(inst.clone, "rev-parse", "main") == one["integrated_revision"]


def test_if_the_remote_rejects_the_push_it_says_so_and_stays_pending(inst):
    installation = with_config(inst, approval="decisive")
    propose(inst.repo.root, installation, operation_id="op-0", files=new_question(inst, "Q-0"), actor=AGENT)
    rejection = inst.remote / "hooks" / "pre-receive"
    rejection.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
    rejection.chmod(0o755)
    res = propose(
        inst.repo.root, installation, operation_id="op-1", files=new_question(inst), actor=AGENT, until="push"
    )
    assert res["state"] == "blocked" and res["code"] == "UNKNOWN_RESULT" and not res["pushed"], res
    assert res["pending_push"] == 1 and on_the_remote(inst) == inst.base
    assert git_in(inst.clone, "rev-parse", "main") == res["integrated_revision"]


def test_does_not_use_the_clone_of_another_remote(inst):
    accept(inst)
    other = inst.tmp / "other.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(inst.remote), str(other)], check=True)
    res = accept(inst, with_config(inst, remote=other.as_posix()))
    assert res["state"] == "blocked" and "is not a clone" in res["reason"]


def test_the_after_steps_write_the_views_in_a_commit_of_their_own_before_pushing(inst):
    checks = {
        "indexes": WRITES_INDEX,
        # The second step sees as tracked what the first one generated.
        "checker": {"command": ["git", "ls-files", "--error-unmatch", "kb/index.md"], "timeout": 60},
    }
    installation = with_config(
        inst,
        checks,
        approval="decisive",
        after_integrate=["indexes", "checker"],
        views=["kb/**/index.md"],
        author={"name": "operator", "email": "operator@localhost"},
    )
    files = new_question(inst)
    dry_run = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT)
    assert dry_run["state"] == "dry_run_done" and dry_run["views"] == ["kb/index.md"], dry_run
    assert [p["result"] for p in dry_run["after"]] == ["passed", "passed"]
    assert on_the_remote(inst) == inst.base and git_in(inst.clone, "rev-parse", "main") == inst.base
    res = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="push")
    assert res["state"] == "pushed" and res["views"] == ["kb/index.md"], res
    assert on_the_remote(inst) == res["head"] != res["integrated_revision"]
    assert git_in(inst.remote, "rev-parse", "main^") == res["integrated_revision"]
    assert git_in(inst.remote, "show", "main:kb/index.md") == "index"
    assert git_in(inst.remote, "log", "-1", "--format=%an <%ce> %s", "main") == (
        "operator <operator@localhost> kb: views after op-1"
    )
    assert git_in(inst.remote, "diff", "--name-only", "main^", "main") == "kb/index.md"


@pytest.mark.parametrize("until", ["dry_run", "push"])
def test_a_failing_after_step_prevents_pushing(inst, until):
    checks = {"checker": py("import sys; print('broken'); sys.exit(3)")}
    installation = with_config(inst, checks, approval="decisive", after_integrate=["checker"])
    res = propose(inst.repo.root, installation, operation_id="op-1", files=new_question(inst), actor=AGENT, until=until)
    assert res["state"] == "blocked" and "checker does not pass" in res["reason"], res
    assert res["after"][0]["code"] == 3 and res["after"][0]["final_output"] == ["broken"]
    assert on_the_remote(inst) == inst.base and not res["pushed"]
    # The dry run leaves nothing; outside it, what was integrated stays in the clone and this is said.
    integrated = git_in(inst.clone, "rev-parse", "main") != inst.base
    assert integrated == (until == "push") and res["pending_push"] == int(integrated)


@pytest.mark.parametrize(
    "code",
    [
        "import pathlib; pathlib.Path('README.md').write_bytes(b'something else')",
        "import pathlib; pathlib.Path('kb/DEC-A.md').write_bytes(b'something else')",
        "import pathlib; pathlib.Path('kb/_fingerprints.json').write_bytes(b'{}')",
    ],
)
def test_an_after_step_may_only_change_views(inst, code):
    installation = with_config(
        inst, {"step": py(code)}, approval="decisive", after_integrate=["step"], views=["kb/**", "docs/**"]
    )
    res = propose(
        inst.repo.root, installation, operation_id="op-1", files=new_question(inst), actor=AGENT, until="push"
    )
    assert res["state"] == "blocked" and "is not a declared view" in res["reason"], res
    assert on_the_remote(inst) == inst.base


def test_what_is_a_view():
    cfg = SimpleNamespace(views=("docs/**/index.md", "kb/**", "*.txt"), folders=("kb", "knowledge/decisions"))
    assert is_view("docs/index.md", cfg) and is_view("docs/a/b/index.md", cfg) and is_view("kb/x/index.md", cfg)
    assert is_view("notes.txt", cfg)
    for path in ("docs/a/other.md", "kb/DEC-A.md", "kb/_fingerprints.json", "kb/_requests/op.json", "a/notes.txt"):
        assert not is_view(path, cfg), path


def test_the_request_is_not_given_both_ways(inst):
    inst.repo.write("kb/_requests/op-1.json", json.dumps({"operation_id": "op-1", "effects": ACCEPT}))
    res = propose(
        inst.repo.root,
        inst.installation,
        operation_id="op-1",
        files=[*new_decision(inst), "kb/_requests/op-1.json"],
        effects=ACCEPT,
    )
    assert res["state"] == "blocked" and "both ways" in res["reason"]


def test_what_is_not_a_record_is_rejected_by_the_gate(inst):
    inst.repo.write("README.md", "other\n")
    res = propose(inst.repo.root, inst.installation, operation_id="op-1", files=["README.md"], until="push")
    assert res["state"] == "blocked" and "is not a record" in res["reason"], res


@pytest.mark.parametrize(
    "files", [[], ["../outside.md"], ["kb/does-not-exist.md"], ["kb/DEC-A.md", "kb/../kb/DEC-A.md"]]
)
def test_files_that_cannot_be_proposed(inst, files):
    with pytest.raises((ValueError, OSError)):
        propose(inst.repo.root, inst.installation, operation_id="op-1", files=files)
    assert not inst.clone.exists()


def test_the_root_is_the_repository_s(inst):
    with pytest.raises(ValueError, match="root"):
        propose(inst.repo.root / "kb", inst.installation, operation_id="op-1", files=["DEC-A.md"])


@pytest.mark.parametrize(
    "change",
    [
        {"integration": None},
        {"canonical_branch": None},
        {"canonical_branch": "a..b"},
        {"records_folder": "kb,,other"},
        {"integration": {"remote": "x"}},
        {"integration": {"remote": "--upload-pack=x", "repository": "p"}},
        {"integration": {"remote": "x", "repository": "../p"}},
        {"integration": {"remote": "x", "repository": "p", "approval": "none"}},
        {"integration": {"remote": "x", "repository": "p", "after_integrate": ["not-declared"]}},
        {"integration": {"remote": "x", "repository": "p", "views": ["../outside/**"]}},
        {"integration": {"remote": "x", "repository": "p", "author": {"name": "n"}}},
        {"integration": {"remote": "x", "repository": "p", "author": {"name": "n", "email": "integrator@localhost"}}},
        {"integration": {"remote": "x", "repository": "p", "quote": "Yes"}},
    ],
)
def test_invalid_configuration(inst, change):
    with pytest.raises(ValueError):
        integration_of({**inst.installation, **change})


def test_configuration_with_several_folders(inst):
    cfg = integration_of({**inst.installation, "records_folder": "kb,knowledge/decisions"})
    assert cfg.folders == ("kb", "knowledge/decisions") and cfg.mode == "all" and cfg.after == ()


def kbol(*args):
    return subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")


def cli(inst, *extra):
    effects = inst.tmp / "effects.json"
    effects.write_text(json.dumps(ACCEPT), encoding="utf-8")
    args = ["propose", str(inst.repo.root), "--installation", str(inst.repo.root / "kbol.json")]
    args += ["--operation-id", "op-1", "--files", *new_decision(inst), "--effects", str(effects)]
    return kbol(*args, *extra)


def test_cli_from_the_package_to_the_push(inst):
    p = cli(inst)
    envelope = json.loads(p.stdout)
    assert p.returncode == 3 and envelope["operation"] == "propose", p.stdout
    assert envelope["result"]["state"] == "pending_approval"
    text = cli(inst, "--text")
    assert text.returncode == 3 and text.stdout.startswith("Approval package of op-1")
    approvals = inst.tmp / "approvals.json"
    approvals.write_text(json.dumps(sign(envelope["result"]["package"])), encoding="utf-8")
    p = cli(inst, "--approvals", str(approvals), "--until", "push")
    envelope = json.loads(p.stdout)
    assert p.returncode == 0 and envelope["result"]["state"] == "pushed", p.stdout
    assert envelope["revision"] == on_the_remote(inst)


@pytest.mark.parametrize(
    "extra", [["--approval", "decisive"], ["--canonical-branch", "other"], ["--folder", "kb"], ["--receipts", "r"]]
)
def test_cli_what_the_installation_sets_is_not_passed_as_argument(inst, extra):
    p = cli(inst, *extra)
    assert p.returncode == 2 and "set by the installation" in json.loads(p.stdout)["result"]["reason"]
    assert not inst.clone.exists()


def test_cli_the_installation_is_read_from_head(inst):
    inst.repo.write("kbol.json", json.dumps(with_config(inst, approval="decisive")))
    p = cli(inst)
    assert p.returncode == 1 and "uncommitted changes" in json.loads(p.stdout)["result"]["reason"]


def test_cli_missing_inputs(inst):
    p = kbol("propose", str(inst.repo.root))
    assert p.returncode == 2 and "needs" in json.loads(p.stdout)["result"]["reason"]


def test_an_integrated_not_pushed_operation_is_finished_with_the_same_id(inst):
    installation = with_config(inst, approval="decisive")
    files = new_question(inst)
    one = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="integrate")
    assert one["state"] == "integrated" and on_the_remote(inst) == inst.base
    res = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="push")
    assert res["state"] == "pushed" and res["resumed"] and res["integrated_revision"] == one["integrated_revision"], res
    assert any("was already integrated" in a for a in res["warnings"])
    assert on_the_remote(inst) == one["integrated_revision"]


def test_after_a_failed_after_step_it_is_finished_with_the_same_id(inst):
    mark = inst.tmp / "passed"
    step = py(f"import pathlib, sys; sys.exit(0 if pathlib.Path({str(mark)!r}).exists() else 3)")
    installation = with_config(inst, {"checker": step}, approval="decisive", after_integrate=["checker"])
    files = new_question(inst)
    one = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="push")
    assert one["state"] == "blocked" and one["pending_push"] == 1
    mark.write_text("", encoding="utf-8")
    res = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="push")
    assert res["state"] == "pushed" and res["resumed"], res
    assert [p["result"] for p in res["after"]] == ["passed"]


def test_if_someone_pushes_first_it_says_how_to_redo_it_and_it_is_redone_with_another_id(inst):
    installation = with_config(inst, approval="decisive")
    files = new_question(inst)
    one = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="integrate")
    remote = someone_pushes(inst)
    res = propose(inst.repo.root, installation, operation_id="op-1", files=files, actor=AGENT, until="push")
    assert res["state"] == "blocked" and res["code"] == "BASE_CHANGED", res
    assert res["integrated_not_pushed"] == one["integrated_revision"] and res["remote"] == remote
    order = res["reason"].split("`")[1].split()
    assert order[:3] == ["git", "-C", str(inst.clone)] and order[3] == "update-ref"
    subprocess.run(order, check=True)  # a person discards it, with the command they are given
    res = propose(inst.repo.root, installation, operation_id="op-2", files=files, actor=AGENT, until="push")
    assert res["state"] == "pushed" and res["base"] == remote, res


def test_a_local_remote_with_a_relative_path_works_in_the_second_command(inst, monkeypatch):
    monkeypatch.chdir(inst.tmp)
    installation = with_config(inst, remote="remote.git", approval="decisive")
    for op in ("op-1", "op-2"):
        files = new_question(inst, f"Q-{op[-1]}")
        res = propose(inst.repo.root, installation, operation_id=op, files=files, actor=AGENT)
        assert res["state"] == "dry_run_done", res


@pytest.mark.parametrize("op", ["a..b", "con", "NUL.x"])
def test_operation_id_that_cannot_be_used(inst, op):
    res = propose(inst.repo.root, inst.installation, operation_id=op, files=new_decision(inst))
    assert res["state"] == "blocked" and res["code"] is None


@pytest.mark.parametrize("written, normal", [("kb/", ("kb",)), ("kb//x, other/", ("kb/x", "other"))])
def test_folders_are_normalized_as_in_the_gate(inst, written, normal):
    assert integration_of({**inst.installation, "records_folder": written}).folders == normal


@pytest.mark.parametrize("email", ["integrator@localhost.", ".Integrator@localhost", "Bootstrap@LOCALHOST", "x@"])
def test_the_author_email_does_not_impersonate_the_integrator(inst, email):
    with pytest.raises(ValueError):
        integration_of(with_config(inst, author={"name": "n", "email": email}))
