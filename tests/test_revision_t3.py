"""Regressions from the independent review of consolidate, dependencies, mutability and snapshot (3 Nov 2026)."""

import copy
import json
import subprocess
import sys

from conftest import decision, event, record

from kbol.consolidate import consolidate
from kbol.core import serialize
from kbol.dependencies import evaluate, ready
from kbol.mutability import compare
from kbol.projection import Snapshot

C = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")


def snap(*pairs):
    return Snapshot({r["id"]: r for r, _ in pairs}, "r1", {r["id"]: c for r, c in pairs})


def repl(target, by):
    return {"target": target, "operation": "replaces", "by": by}


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def canonical_role():
    return record(
        "role",
        events=[
            event("creation", event_id="E0", previous_state=None, new_state="proposed"),
        ],
    )


def to_disk(folder, *pairs, names=None):
    folder.mkdir(parents=True, exist_ok=True)
    for i, (r, c) in enumerate(pairs):
        name = names[i] if names else f"{r['id']}.md"
        mode = "canonical" if r.get("events") else "proposal"
        (folder / name).write_text(serialize(r, c, mode=mode), encoding="utf-8", newline="\n")


def base_scn():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    b = decision("DEC-B", {"C1": "Tuesday."}, recorded="2026-11-02T00:00:00Z", amends=[repl("DEC-A#C1", "DEC-B#C1")])
    return a, b


# --- HIGH ---------------------------------------------------------------------------------------------------


def test_excluded_record_leaves_the_query_partial(tmp_path):
    a, b = base_scn()
    to_disk(tmp_path, a, b, (canonical_role(), ""))
    text = (tmp_path / "DEC-B.md").read_text(encoding="utf-8").replace("---\n", "---\nextra: 1\n", 1)
    (tmp_path / "DEC-B.md").write_text(text, encoding="utf-8")
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 3 and out["result"]["state"] == "partial"


def test_repeated_id_blocks(tmp_path):
    a, b = base_scn()
    b2 = copy.deepcopy(b)
    to_disk(tmp_path, a, b, b2, (canonical_role(), ""), names=["DEC-A.md", "a-DEC-B.md", "z-DEC-B.md", "ROLE.md"])
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 2 and out["result"]["state"] == "blocked"


def test_coherent_snapshot_is_completed(tmp_path):
    a, b = base_scn()
    to_disk(tmp_path, a, b, (canonical_role(), ""))
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 0 and out["result"]["state"] == "completed", out


def test_mutual_succession_is_conflict_not_base_text():
    a, b = base_scn()
    b[0]["depends_on"] = [{"target": "DEC-D", "condition": "accepted_and_in_force"}]
    d = decision(
        "DEC-D",
        {"C1": "Wednesday."},
        recorded="2026-11-02T12:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-D#C1")],
        depends_on=[{"target": "DEC-B", "condition": "accepted_and_in_force"}],
    )
    (c1,) = consolidate(snap(a, b, d), ["DEC-A"], **C)["clauses"]
    assert c1["state"] == "conflict"


def test_wholly_repealed_decision_is_not_in_force_nor_satisfies():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    f = decision(
        "DEC-F",
        {"C1": "M."},
        recorded="2026-11-02T00:00:00Z",
        amends=[{"target": "DEC-A#C1", "operation": "repeals"}],
    )
    s = snap(a, f)
    assert consolidate(s, ["DEC-A"], **C)["validity"] == {"DEC-A": "not_in_force"}
    h = record("milestone", depends_on=[{"target": "DEC-A", "condition": "accepted_and_in_force"}])
    assert evaluate(h, s, **C)[0]["satisfied"] is False


# --- MEDIUM -------------------------------------------------------------------------------------------------


def test_amending_another_clause_is_not_succession():
    a, b = base_scn()
    d = decision(
        "DEC-D",
        {"C1": "Wednesday."},
        recorded="2026-11-02T12:00:00Z",
        amends=[repl("DEC-A#C1", "DEC-D#C1"), {"target": "DEC-B#C7", "operation": "repeals"}],
    )
    (c1,) = consolidate(snap(a, b, d), ["DEC-A"], **C)["clauses"]
    assert c1["state"] == "conflict"


def test_full_succession_cycle_is_ambiguous_in_any_order():
    x = decision("DEC-X", {"C1": "x"}, supersedes=["DEC-Y"])
    y = decision("DEC-Y", {"C1": "y"}, supersedes=["DEC-X"])
    for order in (["DEC-X", "DEC-Y"], ["DEC-Y", "DEC-X"]):
        res = consolidate(snap(x, y), order, **C)
        assert res["validity"] == {"DEC-X": "not_in_force", "DEC-Y": "not_in_force"}, order
        assert any("cycle" in a for a in res["warnings"])


def test_proposal_at_the_cut_even_if_the_header_says_accepted():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    c = decision(
        "DEC-C", {"C1": "Estimated."}, recorded="2026-11-05T00:00:00Z", amends=[repl("DEC-A#C1", "DEC-C#C1")]
    )
    c[0]["events"][0]["recorded_at"] = c[0]["events"][0]["valid_from"] = "2026-11-01T00:00:00Z"
    res = consolidate(snap(a, c), ["DEC-A"], valid_at="2026-11-03T00:00:00Z", known_until="2026-11-03T00:00:00Z")
    assert [p["decision"] for p in res["proposals"]] == ["DEC-C"]


def test_proposed_addition_is_reported():
    a = decision("DEC-A", {"C1": "Monday."}, recorded="2026-11-01T00:00:00Z")
    g = decision(
        "DEC-G",
        {"C1": "Panel."},
        state="proposed",
        amends=[{"target": "DEC-A", "operation": "adds", "by": "DEC-G#C1", "position": "at the end"}],
    )
    res = consolidate(snap(a, g), ["DEC-A"], **C)
    assert [p["decision"] for p in res["proposals"]] == ["DEC-G"]


def with_history(type_, steps, **fields):
    """steps: [(state, valid_from, valid_until)]; the first one is the creation."""
    ev = []
    previous = None
    for i, (state, since, until) in enumerate(steps):
        t = f"2026-11-0{i + 1}T00:00:00Z"
        e = event(
            "creation" if i == 0 else "transition",
            event_id=f"E{i}",
            previous_state=previous,
            new_state=state,
            recorded_at=t,
            valid_from=since or t,
        )
        if until:
            e["valid_until"] = until
        ev.append(e)
        previous = state
    return record(type_, state=previous, events=ev, **fields)


def test_ready_requires_an_authorization_in_force():
    future = with_history("milestone", [("proposed", None, None), ("authorized", "2026-12-01T00:00:00Z", None)], id="MS-F")
    expired = with_history(
        "milestone", [("proposed", None, None), ("authorized", None, "2026-11-05T00:00:00Z")], id="MS-V"
    )
    res = ready(Snapshot({"MS-F": future, "MS-V": expired}, "r"), **C)
    assert res["ready"] == []


def test_completed_without_checks_does_not_satisfy():
    y = with_history(
        "milestone",
        [("proposed", None, None), ("authorized", None, None), ("in_progress", None, None), ("completed", None, None)],
        id="MS-Y",
    )
    x = record("milestone", id="MS-X", depends_on=[{"target": "MS-Y", "condition": "completed_with_evidence"}])
    (r,) = evaluate(x, Snapshot({"MS-Y": y, "MS-X": x}, "r"), **C)
    assert r["satisfied"] is False and r["code"] == "INSUFFICIENT_EVIDENCE"


def _compare(before, change, body=""):
    base = Snapshot({before["id"]: before}, "b", {before["id"]: body})
    prop = copy.deepcopy(base)
    change(prop)
    return [h for h in compare(base, prop)["findings"] if h["severity"] == "error"]


def test_closed_records_of_other_types_are_protected():
    hip = with_history("hypothesis", [("open", None, None), ("validated", None, None)])
    assert _compare(hip, lambda p: p.records["HYP-A"].update(claim="other"))
    q = with_history("question", [("open", None, None), ("resolved", None, None)])
    assert _compare(q, lambda p: p.records["Q-A"].update(closing_condition="other"))
    milestone = with_history("milestone", [("proposed", None, None), ("authorized", None, None)])
    assert _compare(milestone, lambda p: p.records["MS-A"].update(work_scope="the whole repository"))


def test_fact_in_the_prose_of_a_closed_decision_is_protected():
    r, body = decision("DEC-A", {"C1": "Monday."}, sources=[{"id": "s1", "resource": "SRC-A"}])
    body += 'Flow <fact id="H1" evidence="observed" source="s1">5 m3/h</fact>.\n'

    def change(p):
        p.bodies["DEC-A"] = body.replace("5 m3/h", "50 m3/h").replace("observed", "declared")

    assert _compare(r, change, body)


def test_import_without_start_of_validity_is_ambiguous():
    imp = event(
        "import",
        event_id="E0",
        previous_state=None,
        new_state="accepted",
        legacy_state="Accepted",
        provenance={"path": "docs/x.md", "revision": "r"},
        valid_from=None,
        precision="unknown",
    )
    r = record("decision", id="DEC-I", state="accepted", events=[imp])
    res = consolidate(
        Snapshot({"DEC-I": r}, "r", {"DEC-I": '<clause id="C1">\nRule.\n</clause>\n'}),
        ["DEC-I"],
        valid_at="1990-01-01T00:00:00Z",
        known_until=None,
    )
    assert res["validity"] == {"DEC-I": "not_in_force"} and any("AMBIGUOUS_TIME" in a for a in res["warnings"])


# --- LOW ----------------------------------------------------------------------------------------------------


def test_authority_is_that_of_the_origin_decision_without_revoked_ones():
    a, b = base_scn()
    b[0]["authorized_by"] = ["ROLE-B"]
    b[0]["events"].append(
        event(
            "approval_revocation",
            event_id="E3",
            recorded_at="2026-11-03T00:00:00Z",
            valid_from="2026-11-03T00:00:00Z",
            approval_id="AP-DEC-B",
        )
    )
    (c1,) = consolidate(snap(a, b), ["DEC-A"], **C)["clauses"]
    assert c1["authority"]["decision"] == "DEC-B" and c1["authority"]["authorized_by"] == ["ROLE-B"]
    assert c1["authority"]["ratifications"] == []


def test_source_access_is_policy_and_format_immutable():
    f = with_history("source", [("registered", None, None)])
    base = Snapshot({"SRC-A": f}, "b", {"SRC-A": ""})
    prop = copy.deepcopy(base)
    prop.records["SRC-A"]["access"] = "public"
    assert compare(base, prop)["policy_changes"] == ["SRC-A"]
    assert _compare(f, lambda p: p.records["SRC-A"].update(format="text/plain"))


def test_revision_from_subfolder_and_missing_folder(tmp_path):
    repo = tmp_path / "repo"
    a, b = base_scn()
    to_disk(repo / "docs" / "kb", a, b, (canonical_role(), ""))
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    code, out = kb(
        "consolidate",
        str(repo / "docs"),
        "--folder",
        "kb",
        "--revision",
        "HEAD",
        "--ids",
        "DEC-A",
        "--valid-at",
        C["valid_at"],
    )
    assert code == 0, out
    code, out = kb("ready", str(repo), "--folder", "does-not-exist", "--valid-at", C["valid_at"])
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE"
    code, out = kb("ready", str(repo), "--folder", "does-not-exist", "--revision", "HEAD", "--valid-at", C["valid_at"])
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE"


def test_non_utf8_file_does_not_break_the_load(tmp_path):
    a, b = base_scn()
    to_disk(tmp_path, a, b, (canonical_role(), ""))
    (tmp_path / "broken.md").write_bytes(b"---\ntitle: \xff\n---\n")
    code, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert code == 3 and [i["path"] for i in out["coverage"]["invalid"]] == ["broken.md"]


def test_a_single_warning_without_cut(tmp_path):
    a, b = base_scn()
    to_disk(tmp_path, a, b, (canonical_role(), ""))
    _, out = kb("consolidate", str(tmp_path), "--ids", "DEC-A", "--valid-at", C["valid_at"])
    assert sum("admitted history" in a for a in out["warnings"]) == 1
