"""Single gate: only the modules on the list write git references.

It counts, as code literals, the git commands that move references or rewrite history. Changing the list is a decision
visible in the diff: a new module that writes the canonical branch has to appear here.
"""

import ast
from collections import Counter
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "kbol"
WRITES = frozenset({"update-ref", "commit-tree", "push", "merge", "rebase", "reset", "cherry-pick"})
ALLOWED = {
    "bootstrap.py": {"update-ref": 1, "commit-tree": 1},
    "integrate.py": {"update-ref": 1, "commit-tree": 1},
    # The integrator clone: fetches the branch, writes the proposal, dry-runs on a temporary branch and pushes.
    # "push" also names the last step of `--until` (dry_run, integrate, push), hence two literals.
    "propose.py": {"update-ref": 5, "commit-tree": 1, "push": 2},
}


def _writes(source):
    return Counter(n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and n.value in WRITES)


def test_only_the_gate_modules_write_references():
    actual = {}
    for p in sorted(PACKAGE.glob("*.py")):
        count = _writes(p.read_text(encoding="utf-8"))
        if count:
            actual[p.name] = dict(count)
    assert actual == ALLOWED


def test_the_count_detects_a_new_write():
    assert _writes('git("update-ref", ref, new)\nx = "reset"\n') == Counter({"update-ref": 1, "reset": 1})
    assert not _writes('git("rev-parse", "HEAD")  # update-ref in a comment does not count\n')
