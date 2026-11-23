"""Legacy format configurable per installation.

The sample records are synthetic, shaped like those of a project with its own format: IDs `DEC-nnn`, `Q-nnn` and
`H-nnn`, an "In force" state and state prose separated by full stop or comma. Without `legacy_format`, the reading is
that of the default format. The last tests prove that a project whose legacy records are written in Spanish reads
them by declaring its words in `legacy_format.equivalences`: that Spanish text is deliberate test data.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from kbol.consolidate import consolidate
from kbol.migration import DEFAULT, format_of, inspect
from kbol.query import query
from kbol.snapshot import load

LEGACY = Path(__file__).parent / "legacy"
C = dict(valid_at="2026-11-20T00:00:00Z", known_until="2026-11-20T00:00:00Z")

FORMAT = {
    "records": {
        "Decision": {"type": "decision", "id": r"DEC-\d{3,}", "equivalences": {"In force": "Accepted"}},
        "Question": {"type": "question", "id": r"Q-\d{3,}", "equivalences": {"Draft": "Open"}},
        "Hypothesis": {"type": "hypothesis", "id": r"H-\d{3,}"},
    },
    "separators": "(;.,",
}
INSTALLATION = {"project": "Business", "legacy_format": FORMAT}


def doc(type_, ident, state, **extra):
    fields = "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in extra.items())
    header = f"type: {type_}\n" + (f"id: {ident}\n" if ident else "")
    return f"---\n{header}title: Example\nstate: {json.dumps(state, ensure_ascii=False)}\n{fields}---\n\n# Example\n"


DEC_IN_FORCE = doc("Decision", "DEC-108", "In force", date="27 Oct 2026", adopted_by="Founders")
DEC_PARTIAL = doc("Decision", "DEC-020", "In force; partially superseded by DEC-117 and DEC-130")
DEC_SUPERSEDED = doc("Decision", "DEC-015", "Superseded by DEC-130")
Q_RESOLVED = doc(
    "Question",
    "Q-087",
    "Resolved (decision, 27 Oct 2026): the module goes (DEC-108). Announcement (Q-096): on hold",
    resolved_by="DEC-108",
)
Q_YAML_ONLY = doc("Question", "Q-010", "Resolved (decision, 19 Oct 2026)", resolved_by="DEC-003")
Q_WITHOUT_DECISION = doc("Question", "Q-011", "Resolved (decision, 19 Oct 2026)", resolved_by="—")
Q_DRAFT = doc("Question", "Q-012", "Draft")
H_PROSE = doc("Hypothesis", "H-068", "Open. Announcement from management (MTG-006): an opportunity was seen")


def business(folder, **files):
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / f"{name}.md").write_text(text, encoding="utf-8", newline="\n")
    return folder


def test_without_a_declared_format_the_default_one_is_read():
    assert format_of({}) is DEFAULT and format_of({"project": "Faro"}) is DEFAULT


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"records": {"decision": {"type": "decision", "id": r"DEC-\d+"}}}, "type of the profile"),
        ({"records": {"Meeting": {"type": "source", "id": r"MTG-\d+"}}}, "legacy format"),
        ({"records": {"Decision": {"type": "decision", "id": r"\d+"}}}, "literal uppercase prefix"),
        ({"records": {"Hypothesis": {"type": "hypothesis", "id": r"Q-\d+"}}}, "another contract type"),
        ({"records": {"Decision": {"type": "decision", "id": r"DEC-(\d+"}}}, "pattern"),
        (
            {"records": {"Decision": {"type": "decision", "id": r"DEC-\d+", "equivalences": {"In force": "Rules"}}}},
            "Rules",
        ),
        ({"records": {"Decision": {"type": "decision", "id": r"DEC-\d+", "other": 1}}}, "other"),
        ({"records": {}}, "records"),
        ({"separators": ""}, "separators"),
        ({"extra": True}, "extra"),
    ],
)
def test_a_malformed_configuration_is_rejected(change, error):
    with pytest.raises(ValueError, match=error):
        format_of({"legacy_format": {**FORMAT, **change}})


def test_in_force_is_equivalent_to_accepted_and_keeps_the_review_rules():
    f = format_of(INSTALLATION)
    in_force = inspect(DEC_IN_FORCE, "control/decisions/DEC-108.md", "r1", f)
    assert in_force["type"] == "decision" and in_force["id"] == "DEC-108"
    assert in_force["legacy_state"] == "In force" and in_force["proposed_state"] == "accepted"
    assert in_force["ambiguities"] == [] and in_force["requires_review"]  # authority in prose is not checked
    partial = inspect(DEC_PARTIAL, "DEC-020.md", "r1", f)
    [amb] = partial["ambiguities"]
    assert partial["proposed_state"] == "accepted" and amb["field"] == "amends"
    assert amb["candidates"] == ["DEC-117", "DEC-130"]
    superseded = inspect(DEC_SUPERSEDED, "DEC-015.md", "r1", f)
    assert superseded["ambiguities"][0]["field"] == "supersedes"
    assert superseded["ambiguities"][0]["candidates"] == ["DEC-130"]


def test_the_header_is_cut_at_the_declared_separators():
    f = format_of(INSTALLATION)
    h = inspect(H_PROSE, "H-068.md", "r1", f)
    assert h["proposed_state"] == "open" and h["ambiguities"] == []
    # With the separators of the default format, the same prose has no match.
    assert inspect(H_PROSE, "H-068.md", "r1")["proposed_state"] is None
    assert inspect(Q_DRAFT, "Q-012.md", "r1", f)["proposed_state"] == "open"


def test_resolved_by_is_read_from_the_field_and_from_the_text():
    f = format_of(INSTALLATION)
    q = inspect(Q_RESOLVED, "Q-087.md", "r1", f)
    assert q["proposed_state"] == "resolved" and q["proposed_relations"] == {"resolved_by": ["DEC-108"]}
    assert q["ambiguities"] == []
    only = inspect(Q_YAML_ONLY, "Q-010.md", "r1", f)
    assert only["proposed_relations"] == {"resolved_by": ["DEC-003"]} and only["ambiguities"] == []
    without = inspect(Q_WITHOUT_DECISION, "Q-011.md", "r1", f)
    assert without["proposed_relations"] == {"resolved_by": []}
    assert without["ambiguities"][0]["reason"] == "resolved without an identifiable decision"


def test_resolved_by_from_the_field_also_in_the_default_format():
    text = doc("Question", "QD-300", "Resolved", resolved_by="ADR-0063")
    assert inspect(text, "QD-300.md", "r1")["proposed_relations"] == {"resolved_by": ["ADR-0063"]}


def test_loading_with_the_declared_format_reads_the_legacy_records(tmp_path):
    business(tmp_path / "control", **{"DEC-108": DEC_IN_FORCE, "Q-087": Q_RESOLVED, "H-068": H_PROSE})
    without, cov_without = load(tmp_path, "control", legacy=True)
    assert without.legacy == {} and len(cov_without["invalid"]) == 3 and cov_without["state"] == "partial"
    snap, cov = load(tmp_path, "control", legacy=True, format=format_of(INSTALLATION))
    assert set(snap.legacy) == {"DEC-108", "Q-087", "H-068"} and snap.records == {}
    assert cov["invalid"] == [] and cov["state"] == "complete" and cov["legacy"] == 3
    assert snap.legacy["Q-087"]["proposed_relations"] == {"resolved_by": ["DEC-108"]}


def test_the_declared_format_replaces_the_default_one(tmp_path):
    folder = business(tmp_path / "control", **{"DEC-108": DEC_IN_FORCE})
    shutil.copy(LEGACY / "QD-054.md.txt", folder / "QD-054.md")
    snap, cov = load(tmp_path, "control", legacy=True, format=format_of(INSTALLATION))
    assert set(snap.legacy) == {"DEC-108"}
    assert [i["path"] for i in cov["invalid"]] == ["control/QD-054.md"]


def test_the_id_has_to_match_the_pattern_of_its_label(tmp_path):
    business(tmp_path / "control", **{"Q-200": doc("Decision", "Q-200", "In force")})
    snap, cov = load(tmp_path, "control", legacy=True, format=format_of(INSTALLATION))
    assert snap.legacy == {} and cov["invalid"][0]["reason"] == "legacy record without a valid id: 'Q-200'"


def test_without_id_it_counts_as_a_record_if_the_name_is_an_id_of_the_format(tmp_path):
    business(
        tmp_path / "control",
        **{"DEC-005": doc("Decision", None, "In force"), "roadmap": doc("Decision", None, "In force")},
    )
    _, cov = load(tmp_path, "control", legacy=True, format=format_of(INSTALLATION))
    assert [i["path"] for i in cov["invalid"]] == ["control/DEC-005.md"] and cov["omitted"] == 1


def test_a_legacy_record_read_with_the_declared_format_is_not_in_force(tmp_path):
    business(tmp_path / "control", **{"DEC-108": DEC_IN_FORCE, "Q-087": Q_RESOLVED})
    snap, _ = load(tmp_path, "control", legacy=True, format=format_of(INSTALLATION))
    res = consolidate(snap, ["DEC-108"], **C)
    assert [f["id"] for f in res["legacy"]] == ["DEC-108"]
    [r] = query(snap, ["DEC-108"], **C)["results"]
    assert r["found"] == "legacy" and r["in_force"] is False and r["proposed_state"] == "accepted"


def kbol(*args):
    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8", check=False
    )
    return json.loads(p.stdout), p.returncode


def test_cli_reads_the_format_of_the_installation(tmp_path):
    business(tmp_path / "control", **{"DEC-108": DEC_IN_FORCE, "Q-087": Q_RESOLVED, "H-068": H_PROSE})
    installation = tmp_path / "kbol.json"
    installation.write_text(json.dumps(INSTALLATION), encoding="utf-8")
    common = ["--folder", "control", "--valid-at", C["valid_at"], "--installation", str(installation)]
    before, _ = kbol("ready", str(tmp_path), "--legacy", "--folder", "control", "--valid-at", C["valid_at"])
    assert before["coverage"]["legacy"] == 0 and len(before["coverage"]["invalid"]) == 3
    ready, code = kbol("ready", str(tmp_path), "--legacy", *common)
    assert code == 3 and ready["coverage"]["legacy"] == 3 and ready["coverage"]["invalid"] == []
    consolidated, _ = kbol("consolidate", str(tmp_path), "--legacy", "--ids", "Q-087", *common)
    [q] = consolidated["result"]["legacy"]
    assert q["proposed_relations"] == {"resolved_by": ["DEC-108"]}
    queried, code = kbol("query", str(tmp_path), "--ids", "DEC-108", *common)
    assert code == 3 and queried["result"]["results"][0]["in_force"] is False
    migrated, code = kbol("migrate", str(tmp_path / "control"), "--revision", "r1", "--installation", str(installation))
    assert code == 0 and migrated["result"]["summary"]["proposed"] == 3


def test_cli_a_malformed_installation_reads_nothing(tmp_path):
    business(tmp_path / "control", **{"DEC-108": DEC_IN_FORCE})
    installation = tmp_path / "kbol.json"
    installation.write_text(json.dumps({"legacy_format": {"records": {}}}), encoding="utf-8")
    output, code = kbol(
        "ready", str(tmp_path), "--legacy", "--folder", "control", "--valid-at", C["valid_at"],
        "--installation", str(installation),
    )  # fmt: skip
    assert code == 1 and output["result"]["code"] == "INVALID_SCHEMA"


# Deliberate non-English test data: legacy records written in Spanish, read through `equivalences`.
SPANISH = {
    "records": {
        "Decisión": {
            "type": "decision",
            "id": r"ADR-\d{4}",
            "equivalences": {"Aceptada": "Accepted", "Propuesta": "Proposed", "Sustituida por": "Superseded by"},
        },
        "Pregunta": {
            "type": "question",
            "id": r"QD-\d{3,}",
            "equivalences": {"Abierta": "Open", "Resuelta": "Resolved", "Descartada": "Discarded"},
        },
    },
}


def test_spanish_legacy_records_are_read_through_equivalences():
    f = format_of({"legacy_format": SPANISH})
    accepted = inspect(doc("Decisión", "ADR-0063", "Aceptada"), "ADR-0063.md", "r1", f)
    assert accepted["type"] == "decision" and accepted["proposed_state"] == "accepted"
    assert accepted["legacy_state"] == "Aceptada"
    assert inspect(doc("Decisión", "ADR-0064", "Propuesta"), "ADR-0064.md", "r1", f)["proposed_state"] == "proposed"
    superseded = inspect(doc("Decisión", "ADR-0001", "Sustituida por ADR-0063"), "ADR-0001.md", "r1", f)
    assert superseded["ambiguities"][0]["field"] == "supersedes"
    assert superseded["ambiguities"][0]["candidates"] == ["ADR-0063"]
    resolved = inspect(doc("Pregunta", "QD-184", "Resuelta (ADR-0063)", resolved_by="ADR-0063"), "QD-184.md", "r1", f)
    assert resolved["proposed_state"] == "resolved"
    assert resolved["proposed_relations"] == {"resolved_by": ["ADR-0063"]}
    assert inspect(doc("Pregunta", "QD-185", "Descartada"), "QD-185.md", "r1", f)["proposed_state"] == "discarded"


def test_spanish_labels_are_not_read_by_the_default_format():
    r = inspect(doc("Decisión", "ADR-0063", "Aceptada"), "ADR-0063.md", "r1")
    assert r["type"] is None and r["result"] == "out_of_scope"
    english_label = inspect(doc("Decision", "ADR-0063", "Aceptada"), "ADR-0063.md", "r1")
    assert english_label["proposed_state"] is None  # the Spanish word has no match without an equivalence
