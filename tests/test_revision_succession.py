"""Regressions from the review of 4 Nov 2026: chained full succession and unreadable YAML on load."""

import json
import subprocess
import sys

from conftest import decision, event, record

from kbol.consolidate import consolidate
from kbol.core import serialize
from kbol.projection import Snapshot

C = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")


def snap(*pairs):
    return Snapshot({r["id"]: r for r, _ in pairs}, "r1", {r["id"]: c for r, c in pairs})


def full_chain():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b = decision("DEC-B", {"C1": "Tuesday."}, recorded="2026-11-02T00:00:00Z", supersedes=["DEC-A"])
    c = decision("DEC-C", {"C1": "Thursday."}, recorded="2026-11-03T00:00:00Z", supersedes=["DEC-B"])
    return a, b, c


def test_superseded_does_not_come_back_when_its_successor_is_superseded():
    a, b, c = full_chain()
    res = consolidate(snap(a, b, c), ["DEC-A", "DEC-B", "DEC-C"], **C)
    assert res["validity"] == {"DEC-A": "not_in_force", "DEC-B": "not_in_force", "DEC-C": "full"}
    assert [x["text"] for x in res["clauses"] if x["state"] == "current"] == ["Thursday."]


def test_status_of_the_superseded_does_not_return_to_stable():
    from kbol.projection import project_status

    a, b, c = full_chain()
    s = snap(a, b, c)
    assert project_status(a[0], s, **C) == "deprecated"
    assert project_status(b[0], s, **C) == "deprecated"
    assert project_status(c[0], s, **C) == "stable"


def test_superseded_does_not_come_back_when_its_successor_expires():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        until="2026-11-10T00:00:00Z",
        supersedes=["DEC-A"],
    )
    res = consolidate(snap(a, b), ["DEC-A"], **C)
    assert res["validity"] == {"DEC-A": "not_in_force"} and res["clauses"] == []


def test_future_successor_does_not_retire_yet():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Tuesday."},
        recorded="2026-11-02T00:00:00Z",
        valid="2026-12-01T00:00:00Z",
        supersedes=["DEC-A"],
    )
    assert consolidate(snap(a, b), ["DEC-A"], **C)["validity"] == {"DEC-A": "full"}


def test_chain_before_the_last_successor_comes_in():
    a, b, c = full_chain()
    cut = dict(valid_at="2026-11-02T12:00:00Z", known_until="2026-11-20T00:00:00Z")
    res = consolidate(snap(a, b, c), ["DEC-A", "DEC-B"], **cut)
    assert res["validity"] == {"DEC-A": "not_in_force", "DEC-B": "full"}


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def test_unreadable_yaml_leaves_the_query_partial(tmp_path):
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    role = record("role", events=[event("creation", event_id="E0", previous_state=None, new_state="proposed")])
    (tmp_path / "DEC-A.md").write_text(serialize(*a, mode="canonical"), encoding="utf-8", newline="\n")
    (tmp_path / "ROLE.md").write_text(serialize(role, ""), encoding="utf-8", newline="\n")
    (tmp_path / "DEC-B.md").write_text("---\nid: DEC-B\nid: DEC-B\ntype: decision\n---\n", encoding="utf-8")
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 3 and out["result"]["state"] == "partial"
    assert [i["path"] for i in out["coverage"]["invalid"]] == ["DEC-B.md"]


def test_without_header_is_also_invalid_but_the_index_is_not(tmp_path):
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    role = record("role", events=[event("creation", event_id="E0", previous_state=None, new_state="proposed")])
    (tmp_path / "DEC-A.md").write_text(serialize(*a, mode="canonical"), encoding="utf-8", newline="\n")
    (tmp_path / "ROLE.md").write_text(serialize(role, ""), encoding="utf-8", newline="\n")
    (tmp_path / "index.md").write_text("* [DEC-A](DEC-A.md)\n", encoding="utf-8")
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 0, out
    (tmp_path / "loose.md").write_text("Text without a header.\n", encoding="utf-8")
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 3 and [i["path"] for i in out["coverage"]["invalid"]] == ["loose.md"]
