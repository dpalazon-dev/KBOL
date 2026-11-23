"""Integration and bootstrap from the CLI, with declared approval.

The CLI pushes nothing: with --remote it fetches the remote and requires the base and the local branch to be up to
date with it, so that the later push, which a person makes, is not rejected. Without the required inputs or with a
mechanism the CLI does not integrate, it fails closed.
"""

import json
import subprocess
import sys

import pytest
from conftest import DECISION_BODY, record
from test_bootstrap_declared import declaration
from test_bootstrap_declared import root as root  # noqa: F401 (fixture)
from test_declared import acceptance, declared_approval
from test_declared import environment as environment  # noqa: F401 (fixture)
from test_integrate import ACCEPT, propose, request

from kbol.core import serialize
from kbol.declared import MECHANISM
from kbol.digest import digest


def kbol(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def json_in(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def integrate_cli(repo, base, prop, receipts, approvals, tmp_path, *extra):
    return kbol(
        "integrate",
        str(repo.root),
        "--canonical-branch",
        "canon",
        "--folder",
        "kb",
        "--operation-id",
        "op-1",
        "--base",
        base,
        "--proposal",
        prop,
        "--approvals",
        json_in(tmp_path, "approvals.json", approvals),
        "--receipts",
        str(receipts),
        *extra,
    )


def test_integrates_with_a_declared_approval(environment, tmp_path):  # noqa: F811
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    code, output = integrate_cli(repo, base, prop, receipts, [declared_approval(base)], tmp_path)
    assert code == 0, output
    assert output["operation"] == "integrate" and output["result"]["state"] == "integrated"
    assert repo.git("rev-parse", "canon") == output["result"]["integrated_revision"]


def test_a_rejection_comes_out_blocked(environment, tmp_path):  # noqa: F811
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    code, output = integrate_cli(repo, base, prop, receipts, [declared_approval(base, digests={"DEC-X": "0" * 64})], tmp_path)
    assert code == 2 and output["result"]["code"] == "STALE_APPROVAL"


@pytest.mark.parametrize("approvals", [[], [{"mechanism": "github-review", "pull": 1, "review_id": 1}], {"a": 1}])
def test_without_declared_approvals_it_does_not_integrate(environment, tmp_path, approvals):  # noqa: F811
    repo, base, receipts = environment
    prop = acceptance(repo, base)
    code, output = integrate_cli(repo, base, prop, receipts, approvals, tmp_path)
    assert code == 2 and output["result"]["state"] == "blocked"
    assert repo.git("rev-parse", "canon") == base


def test_missing_inputs(environment):  # noqa: F811
    repo, _, _ = environment
    code, output = kbol("integrate", str(repo.root), "--canonical-branch", "canon")
    assert code == 2 and "needs" in output["result"]["reason"]


def remote_of(repo, tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo.git("remote", "add", "origin", str(remote))
    repo.git("push", "-q", "origin", "canon")
    return remote


def test_with_an_up_to_date_remote_it_integrates(environment, tmp_path):  # noqa: F811
    repo, base, receipts = environment
    remote_of(repo, tmp_path)
    prop = acceptance(repo, base)
    code, output = integrate_cli(repo, base, prop, receipts, [declared_approval(base)], tmp_path, "--remote", "origin")
    assert code == 0, output


def test_if_the_remote_moved_ahead_it_does_not_integrate(environment, tmp_path):  # noqa: F811
    repo, base, receipts = environment
    remote = remote_of(repo, tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "canon", str(remote), str(other)], check=True)
    (other / "README.md").write_text("other\n", encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "-C", str(other), *ident, "commit", "-q", "-am", "other"], check=True)
    subprocess.run(["git", "-C", str(other), "push", "-q", "origin", "canon"], check=True)
    prop = acceptance(repo, base)
    code, output = integrate_cli(repo, base, prop, receipts, [declared_approval(base)], tmp_path, "--remote", "origin")
    assert code == 2 and output["result"]["code"] == "BASE_CHANGED", output
    assert repo.git("rev-parse", "canon") == base


def test_declared_bootstrap_from_the_cli(root, tmp_path):  # noqa: F811
    repo, base, receipts = root
    args = ["bootstrap", str(repo.root), "--canonical-branch", "canon", "--folder", "kb", "--operation-id", "bootstrap-1"]
    args += ["--base", base, "--person", "PER-D", "--roles", "ROLE-ROOT", "--receipts", str(receipts)]
    code, output = kbol(*args, "--declaration", json_in(tmp_path, "declaration.json", declaration()))
    assert code == 0, output
    assert output["result"]["state"] == "bootstrapped"
    again = kbol(*args[:7], "bootstrap-2", *args[8:], "--declaration", json_in(tmp_path, "d2.json", declaration()))
    assert again[0] == 2


def test_after_the_bootstrap_the_cli_integrates_with_the_root(root, tmp_path):  # noqa: F811
    repo, base, receipts = root
    args = ["bootstrap", str(repo.root), "--canonical-branch", "canon", "--folder", "kb", "--operation-id", "bootstrap-1"]
    args += ["--base", base, "--person", "PER-D", "--roles", "ROLE-ROOT", "--receipts", str(receipts)]
    _, bootstrap = kbol(*args, "--declaration", json_in(tmp_path, "declaration.json", declaration()))
    canon = bootstrap["result"]["integrated_revision"]
    r = record("decision", id="DEC-X", authorized_by=["ROLE-ROOT"])
    prop = propose(
        repo, canon, {"kb/DEC-X.md": serialize(r, DECISION_BODY), **request("op-1", {"DEC-X": ACCEPT})}
    )
    approval = {
        "mechanism": MECHANISM,
        "identity": "declared:d",
        "session": "s",
        "instant": bootstrap["result"]["recorded_at"],
        "quote": "I accept DEC-X",
        "base_shown": canon,
        "digests": {"DEC-X": digest(r, DECISION_BODY, ACCEPT)},
    }
    code, output = integrate_cli(repo, canon, prop, receipts, [approval], tmp_path)
    assert code == 0, output
