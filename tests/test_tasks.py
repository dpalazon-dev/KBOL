"""Tasks of a milestone as `CT*` clauses: they are ticked, but neither deleted nor rewritten.

A report or a note cites tasks by `PLAN-nnn-Hk#CTn`: a citable task has to keep its text and its anchor.
Ticking its box is progress, not a content change; in a closed milestone not even that.
"""

import pytest
from conftest import record

from kbol.mutability import compare
from kbol.projection import Snapshot

TASKS = (
    "## Tasks\n\n"
    '<clause id="CT1">\n- [ ] Measure parity\n</clause>\n\n'
    '<clause id="CT2">\n- [x] Write the red test\n</clause>\n'
)


def snap(body, state="in_progress"):
    milestone = record("milestone", state=state)
    return Snapshot({"MS-A": milestone}, "r", {"MS-A": body}, {"MS-A": "kb/MS-A.md"})


def errors(before, after, state="in_progress"):
    out = compare(snap(before, state), snap(after, state))
    return [h["message"] for h in out["findings"] if h["severity"] == "error"]


def test_ticking_a_box_is_progress_not_a_protected_change():
    assert errors(TASKS, TASKS.replace("- [ ] Measure", "- [x] Measure")) == []
    assert errors(TASKS, TASKS.replace("- [x] Write", "- [ ] Write")) == []


def test_a_new_task_can_be_added():
    new = TASKS + '\n<clause id="CT3">\n- [ ] Document\n</clause>\n'
    assert errors(TASKS, new) == []


@pytest.mark.parametrize(
    "after",
    [
        TASKS.replace("Measure parity", "Measure something else"),
        TASKS.replace('<clause id="CT1">\n- [ ] Measure parity\n</clause>\n\n', ""),
        TASKS.replace('id="CT2"', 'id="CT9"'),
    ],
)
def test_a_task_is_not_rewritten_deleted_or_renumbered(after):
    assert any("task" in m for m in errors(TASKS, after))


def test_in_a_closed_milestone_not_even_ticking():
    assert any("task" in m for m in errors(TASKS, TASKS.replace("- [ ] Measure", "- [x] Measure"), "completed"))


def test_a_body_with_broken_markup_does_not_pass():
    assert any("task" in m for m in errors(TASKS, TASKS.replace("</clause>\n\n", "\n", 1)))


def test_a_milestone_with_broken_markup_in_the_base_admits_no_unchecked_changes():
    broken = '<clause id="CT1">\n- [ ] Measure\n'
    assert errors(broken, broken + "</clause>\n")
