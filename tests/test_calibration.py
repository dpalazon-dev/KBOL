"""Calibration sample: what came in without approval is reviewed by sample, and only read."""

import importlib.util
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tools" / "calibration" / "sample.py"
_spec = importlib.util.spec_from_file_location("calibration_sample", PATH)
calibration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calibration)


def receipt(folder, op, records, decisive, mode="decisive", state="integrated", recorded="2026-11-10T10:00:00Z"):
    data = {
        "operation_id": op,
        "state": state,
        "approval_mode": mode,
        "records": records,
        "decisive": decisive,
        "integrated_revision": "a" * 40,
        "recorded_at": recorded,
        "actor": "claude-code/fable-5.2",
    }
    (folder / f"{op}.json").write_text(json.dumps(data), encoding="utf-8")


def test_only_what_did_not_ask_for_approval_enters_the_sample(tmp_path):
    receipt(tmp_path, "op-1", ["DEC-A", "Q-1", "Q-2"], ["DEC-A"])
    receipt(tmp_path, "op-2", ["DEC-B"], [], mode="all")
    receipt(tmp_path, "op-3", ["Q-3"], [], state="blocked")
    unapproved, read, unreadable = calibration.candidates(tmp_path)
    assert [(c["operation_id"], c["id"]) for c in unapproved] == [("op-1", "Q-1"), ("op-1", "Q-2")]
    assert read == 2 and unreadable == []


def test_the_sample_is_deterministic_and_does_not_depend_on_order(tmp_path):
    receipt(tmp_path, "op-1", [f"Q-{i}" for i in range(30)], [])
    unapproved, _, _ = calibration.candidates(tmp_path)
    one = calibration.sample(unapproved, 5)
    other = calibration.sample(list(reversed(unapproved)), 5)
    assert one == other and len(one) == 5
    assert one != unapproved[:5]


def test_with_nothing_to_sample_it_says_so_and_does_not_exit_with_zero(tmp_path, capsys):
    receipt(tmp_path, "op-1", ["DEC-A"], ["DEC-A"], mode="all")
    assert calibration.main([str(tmp_path)]) == 3
    assert "no record came in without approval" in capsys.readouterr().err


def test_writes_the_sheet_and_does_not_touch_the_receipts(tmp_path):
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    receipt(receipts, "op-1", ["Q-1"], [])
    (receipts / "broken.json").write_text("{", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in receipts.iterdir()}
    output = tmp_path / "sheet.md"
    assert calibration.main([str(receipts), "--output", str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    assert "| op-1 | Q-1 |" in text and "broken.json" in text
    assert {p.name: p.read_bytes() for p in receipts.iterdir()} == before


def test_since_leaves_out_earlier_receipts(tmp_path):
    receipt(tmp_path, "op-1", ["Q-1"], [], recorded="2026-10-01T00:00:00Z")
    receipt(tmp_path, "op-2", ["Q-2"], [], recorded="2026-11-10T00:00:00Z")
    unapproved, _, _ = calibration.candidates(tmp_path, since="2026-11-01T00:00:00Z")
    assert [c["id"] for c in unapproved] == ["Q-2"]


def test_a_folder_that_does_not_exist_is_an_error(tmp_path):
    assert calibration.main([str(tmp_path / "does-not-exist")]) == 1
