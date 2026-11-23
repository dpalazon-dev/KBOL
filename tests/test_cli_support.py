"""CLI `support`: flags the supports that are not in force without blocking, and compares two pairs of cuts."""

import json
import subprocess
import sys

import pytest
from conftest import decision, event, record
from test_dependencies import with_history

from kbol.core import serialize

T = "2026-11-10T12:00:00Z"
BEFORE = "2026-11-03T12:00:00Z"


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def write(folder, r, c=""):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{r['id']}.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")


@pytest.fixture
def root(tmp_path):
    """Synthesis that depends on DEC-A#C1, replaced on the 5th by DEC-B#C1."""
    folder = tmp_path / "kb"
    creation = event("creation", event_id="E0", previous_state=None, new_state="proposed")
    write(folder, record("role", id="ROLE-EXAMPLE", events=[creation]))
    write(folder, *decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z"))
    write(
        folder,
        *decision(
            "DEC-B",
            {"C1": "Tuesday."},
            recorded="2026-11-05T00:00:00Z",
            amends=[{"target": "DEC-A#C1", "operation": "replaces", "by": "DEC-B#C1"}],
        ),
    )
    write(folder, with_history("synthesis", "draft", id="SYN-A", dependencies=["DEC-A#C1"]), "Summary.")
    return tmp_path


def base(root):
    return ["support", str(root), "--folder", "kb", "--valid-at", T]


def test_a_broken_support_is_flagged_and_the_exit_is_zero(root):
    code, out = kb(*base(root))
    assert code == 0 and out["result"]["state"] == "completed", out
    syn = next(r for r in out["result"]["records"] if r["id"] == "SYN-A")
    assert syn["support"] == "broken" and syn["supports"][0]["situation"] == "not_in_force"
    assert out["result"]["records_examined"] == 4 and out["valid_at"] == T
    assert "semantic backing of the supports" in out["coverage"]["not_evaluated"]


def test_ids_filters_and_an_id_that_does_not_exist_is_partial(root):
    code, out = kb(*base(root), "--ids", "SYN-A")
    assert code == 0 and [r["id"] for r in out["result"]["records"]] == ["SYN-A"], out
    code, out = kb(*base(root), "--ids", "SYN-A", "SYN-NO")
    assert code == 3 and out["result"]["state"] == "partial" and out["result"]["missing"] == ["SYN-NO"]
    assert any("SYN-NO" in a for a in out["warnings"])


def test_no_record_examined_is_partial(root):
    code, out = kb(*base(root), "--ids", "SYN-NO")
    assert code == 3 and out["result"]["records_examined"] == 0, out
    assert any("no record examined" in a for a in out["warnings"])


def test_two_pairs_of_cuts_return_the_change_and_its_chain(root):
    code, out = kb(*base(root), "--before-valid-at", BEFORE, "--before-known-until", BEFORE)
    assert code == 0 and out["result"]["state"] == "completed", out
    (change,) = out["result"]["changes"]
    assert (change["id"], change["ref"], change["before"]["situation"], change["after"]["situation"]) == (
        "SYN-A",
        "DEC-A#C1",
        "in_force",
        "not_in_force",
    )
    assert change["explanation"]["chain"] == ["DEC-A#C1", "DEC-B#C1"]
    assert out["result"]["before"]["valid_at"] == BEFORE and out["result"]["after"]["valid_at"] == T


def test_the_before_cuts_are_validated_and_only_apply_to_support(root):
    code, out = kb(*base(root), "--before-valid-at", "2026-11-03")
    assert code == 2 and out["result"]["code"] == "AMBIGUOUS_TIME", out
    code, out = kb("ready", str(root), "--folder", "kb", "--valid-at", T, "--before-valid-at", BEFORE)
    assert code == 2 and "only apply to support" in out["result"]["reason"], out
