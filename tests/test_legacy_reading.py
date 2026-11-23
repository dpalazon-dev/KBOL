"""Compatible reading of the legacy format, while the transition to the contract lasts.

Legacy records are read separately, as imported without an admitted history: queries name them with their legacy
state, but never count them as normative nor consider a dependency that points to them met.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import decision, event, record

from kbol.consolidate import consolidate
from kbol.core import serialize
from kbol.dependencies import evaluate, ready
from kbol.snapshot import load

LEGACY = Path(__file__).parent / "legacy"
C = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")


def corpus(folder, *names):
    """Copies the given legacy records (without the .txt) and a KBOL record with history."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(LEGACY / f"{name}.txt", folder / name)
    r, c = decision("DEC-A", {"C1": "Monday."})
    (folder / "DEC-A.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")
    creation = event("creation", event_id="E0", previous_state=None, new_state="proposed")
    role = record("role", events=[creation])  # the role that authorizes DEC-A: without it the load would be partial
    (folder / f"{role['id']}.md").write_text(serialize(role, "", mode="canonical"), encoding="utf-8", newline="\n")
    return folder


ADR = "0063-one-working-copy-per-session.md"


def test_without_the_option_legacy_records_are_omitted_as_before(tmp_path):
    corpus(tmp_path / "docs", ADR, "PL-001-H3.md")
    snapshot, coverage = load(tmp_path, "docs")
    assert set(snapshot.records) == {"DEC-A", "ROLE-EXAMPLE"} and snapshot.legacy == {}
    assert coverage["omitted"] == 2 and coverage["legacy"] == 0


def test_with_the_option_they_are_read_separately_and_without_history(tmp_path):
    corpus(tmp_path / "docs", ADR, "PL-001-H3.md", "QD-054.md")
    snapshot, coverage = load(tmp_path, "docs", legacy=True)
    assert set(snapshot.records) == {"DEC-A", "ROLE-EXAMPLE"}
    assert set(snapshot.legacy) == {"ADR-0063", "PL-001-H3", "QD-054"}
    adr = snapshot.legacy["ADR-0063"]
    assert adr["type"] == "decision" and adr["legacy_state"] == "Accepted" and adr["proposed_state"] == "accepted"
    assert adr["path"] == f"docs/{ADR}" and adr["requires_review"]
    assert snapshot.legacy["QD-054"]["ambiguities"]  # "Under review" does not exist in the contract
    assert coverage["legacy"] == 3 and coverage["omitted"] == 0 and coverage["state"] == "complete"
    assert any("legacy format" in a for a in coverage["warnings"])


def test_a_legacy_id_repeating_one_of_the_profile_blocks(tmp_path):
    # During the migration, an already migrated record keeps its legacy ID and coexists with its old file.
    folder = corpus(tmp_path / "docs", ADR)
    r, c = decision("ADR-0063", {"C1": "One working copy per session."})
    (folder / "ADR-0063.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")
    _, coverage = load(tmp_path, "docs", legacy=True)
    assert coverage["state"] == "blocked"
    assert any("ADR-0063" in h["message"] and "legacy format" in h["message"] for h in coverage["findings"])


def test_a_legacy_record_with_a_profile_id_is_invalid(tmp_path):
    folder = corpus(tmp_path / "docs", ADR)
    rewrite(folder, ADR, "id: ADR-0063", "id: DEC-A")
    _, coverage = load(tmp_path, "docs", legacy=True)
    assert coverage["state"] == "partial" and [i["path"] for i in coverage["invalid"]] == [f"docs/{ADR}"]


def test_a_legacy_milestone_is_never_ready_and_it_is_explained(tmp_path):
    corpus(tmp_path / "docs", "PL-001-H3.md", "PL-001-H6.md")
    snapshot, _ = load(tmp_path, "docs", legacy=True)
    res = ready(snapshot, **C)
    assert res["ready"] == [] and res["blocked"] == []
    alerts = " ".join(res["warnings"])
    assert "PL-001-H3: legacy format (Pending)" in alerts and "PL-001-H6: legacy format (Done)" in alerts


def test_a_dependency_on_a_legacy_record_is_not_met(tmp_path):
    corpus(tmp_path / "docs", ADR)
    snapshot, _ = load(tmp_path, "docs", legacy=True)
    milestone = record(
        "milestone",
        state="authorized",
        events=[event("creation", event_id="E0", previous_state=None, new_state="authorized")],
        depends_on=[{"target": "ADR-0063", "condition": "accepted_and_in_force"}],
    )
    [dep] = evaluate(milestone, snapshot, **C)
    assert not dep["satisfied"] and "legacy format" in dep["reason"] and "Accepted" in dep["reason"]


def test_consolidate_names_the_legacy_decision_without_treating_it_as_in_force(tmp_path):
    corpus(tmp_path / "docs", ADR)
    snapshot, _ = load(tmp_path, "docs", legacy=True)
    res = consolidate(snapshot, ["ADR-0063", "ADR-9999"], **C)
    assert res["missing"] == ["ADR-9999"] and "ADR-0063" not in res["validity"]
    [card] = res["legacy"]
    assert card["id"] == "ADR-0063" and card["legacy_state"] == "Accepted"
    assert any("ADR-0063" in a and "not in force" in a for a in res["warnings"])


def test_cli_ready_with_legacy_records(tmp_path):
    corpus(tmp_path / "docs", "PL-001-H3.md")
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "kbol.cli",
            "ready",
            "--legacy",
            "--valid-at",
            C["valid_at"],
            "--folder",
            "docs",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = json.loads(p.stdout)
    # The corpus only has a legacy milestone, which is not in force: no milestone is examined and the output is partial.
    assert p.returncode == 3, output
    assert output["result"]["state"] == "partial" and output["result"]["milestones_examined"] == 0
    assert output["result"]["ready"] == []
    assert any("PL-001-H3: legacy format" in a for a in output["warnings"])
    assert output["coverage"]["legacy"] == 1


def rewrite(folder, name, before, after):
    path = folder / name
    path.write_text(path.read_text(encoding="utf-8").replace(before, after, 1), encoding="utf-8", newline="\n")


def test_a_legacy_record_without_a_valid_id_does_not_disappear(tmp_path):
    folder = corpus(tmp_path / "docs", "PL-001-H3.md", "PL-001-H5.md")
    rewrite(folder, "PL-001-H3.md", "id: PL-001-H3\n", "")
    rewrite(folder, "PL-001-H5.md", "id: PL-001-H5", "id: 123")
    snapshot, coverage = load(tmp_path, "docs", legacy=True)
    assert snapshot.legacy == {} and coverage["state"] == "partial"
    assert {i["path"] for i in coverage["invalid"]} == {"docs/PL-001-H3.md", "docs/PL-001-H5.md"}
    assert ready(snapshot, **C)["ready"] == []  # an id that is not text does not break the query


def test_two_legacy_records_with_the_same_id_block_and_say_so(tmp_path):
    folder = corpus(tmp_path / "docs", "PL-001-H3.md", "PL-001-H5.md")
    rewrite(folder, "PL-001-H5.md", "id: PL-001-H5", "id: PL-001-H3")
    _, coverage = load(tmp_path, "docs", legacy=True)
    assert coverage["state"] == "blocked"
    assert any("PL-001-H3" in h["message"] and "legacy format" in h["message"] for h in coverage["findings"])


def test_the_condition_is_checked_before_the_format(tmp_path):
    corpus(tmp_path / "docs", ADR)
    snapshot, _ = load(tmp_path, "docs", legacy=True)
    milestone = record("milestone", depends_on=[{"target": "ADR-0063", "condition": "resolved"}])
    [dep] = evaluate(milestone, snapshot, **C)
    assert not dep["satisfied"] and dep["code"] == "INVALID_SCHEMA"


def test_a_profile_reference_to_a_legacy_record_says_so(tmp_path):
    folder = corpus(tmp_path / "docs", ADR)
    r, c = decision(
        "DEC-B", {"C1": "Tuesday."}, depends_on=[{"target": "ADR-0063", "condition": "accepted_and_in_force"}]
    )
    (folder / "DEC-B.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")
    _, coverage = load(tmp_path, "docs", legacy=True)
    assert any("ADR-0063 is in legacy format" in h["message"] for h in coverage["findings"])


def test_cli_consolidate_a_legacy_record_is_not_treated_as_resolved(tmp_path):
    corpus(tmp_path / "docs", ADR)
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "kbol.cli",
            "consolidate",
            "--legacy",
            "--ids",
            "ADR-0063",
            "--valid-at",
            C["valid_at"],
            "--folder",
            "docs",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = json.loads(p.stdout)
    assert p.returncode == 3 and output["result"]["state"] == "partial"
    assert [f["id"] for f in output["result"]["legacy"]] == ["ADR-0063"]


def test_from_a_git_revision(tmp_path):
    corpus(tmp_path / "docs", ADR)
    for order in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *order], check=True, capture_output=True)
    snapshot, coverage = load(tmp_path, "docs", revision="HEAD", legacy=True)
    assert set(snapshot.legacy) == {"ADR-0063"} and snapshot.legacy["ADR-0063"]["path"] == f"docs/{ADR}"
    assert coverage["state"] == "complete"


def test_a_document_with_a_record_type_without_id_or_record_name_is_omitted(tmp_path):
    folder = corpus(tmp_path / "docs")
    for name in ("PLAN.md", "2026-02-18-quickstart.md"):
        (folder / name).write_text("---\ntype: Plan\ntitle: Work plan\n---\n\n# Plan\n", encoding="utf-8")
    snapshot, coverage = load(tmp_path, "docs", legacy=True)
    assert snapshot.legacy == {} and coverage["invalid"] == [] and coverage["omitted"] == 2


def test_context_and_drift_reads_count_legacy_records_and_are_not_partial(tmp_path):
    """While legacy records remain, a reference to one leaves neither the context package nor the drift partial."""
    from kbol.context import context
    from kbol.fingerprints import drift

    folder = corpus(tmp_path / "docs", ADR)
    r, c = decision("DEC-B", {"C1": "Tuesday."}, affects=["ADR-0063"])
    (folder / "DEC-B.md").write_text(serialize(r, c, mode="canonical"), encoding="utf-8", newline="\n")
    package = context(
        tmp_path,
        task="t",
        goal="o",
        scope="operations",
        folder="docs",
        installation={},
        valid_at=C["valid_at"],
    )
    assert package["coverage"]["state"] != "partial", package["coverage"]
    assert drift(tmp_path, "docs")["coverage"]["state"] == "complete"
