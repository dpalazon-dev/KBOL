"""Contract envelope of the CLI: same fields in every operation and closed failure."""

import json
import subprocess
import sys

import pytest
from conftest import DECISION_BODY, record

from kbol.core import serialize

FIELDS = {
    "operation",
    "operation_id",
    "revision",
    "valid_at",
    "known_until",
    "result",
    "warnings",
    "coverage",
}


def kb(*args, cwd=None):
    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8", cwd=cwd
    )
    return p.returncode, json.loads(p.stdout)


def test_validate_valid_record(tmp_path):
    f = tmp_path / "DEC-EXAMPLE.md"
    f.write_text(serialize(record("decision"), DECISION_BODY), encoding="utf-8", newline="\n")
    code, out = kb("validate", str(f))
    assert code == 0 and set(out) == FIELDS
    assert out["operation"] == "validate" and out["result"]["state"] == "completed"
    assert out["result"]["errors"] == []
    assert out["valid_at"] is None and out["known_until"] is None
    assert "authority" in out["coverage"]["not_evaluated"]


def test_validate_invalid_record(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nid: DEC-A\n---\n", encoding="utf-8")
    code, out = kb("validate", str(f))
    assert code == 1 and out["result"]["state"] == "failed"
    assert {e["code"] for e in out["result"]["errors"]} == {"INVALID_SCHEMA"}


def test_missing_path_and_empty_argument(tmp_path):
    code, out = kb("validate", str(tmp_path / "no.md"))
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE"
    code, out = kb("validate", "")
    assert code == 2 and out["result"]["state"] == "blocked"


@pytest.mark.parametrize("op", ["ingest"])
def test_capabilities_not_enabled_fail_closed(op):
    code, out = kb(op)
    assert code == 2 and set(out) == FIELDS
    assert out["result"] == {
        "state": "blocked",
        "code": None,
        "reason": "capability not enabled in this version",
    }


def test_dry_run_migrate_does_not_write(tmp_path):
    f = tmp_path / "QD-1.md"
    text = "---\ntype: Question\nid: QD-001\nstatus: Open\n---\nx\n"
    f.write_text(text, encoding="utf-8")
    code, out = kb("migrate", str(tmp_path), "--revision", "r1")
    assert code == 0 and out["revision"] == "r1"
    assert out["result"]["summary"]["total"] == 1
    assert f.read_text(encoding="utf-8") == text


def test_digest_of_invalid_record_or_bad_effects(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nid: DEC-A\n---\n", encoding="utf-8")
    code, out = kb("digest", str(f))
    assert code == 1 and out["result"]["state"] == "failed"
    g = tmp_path / "DEC-EXAMPLE.md"
    g.write_text(serialize(record("decision"), DECISION_BODY), encoding="utf-8", newline="\n")
    for content in ("{bad", '[{"new_state": "accepted", "new_state": "rejected"}]', '{"anything": 1}'):
        effects = tmp_path / "effects.json"
        effects.write_text(content, encoding="utf-8")
        code, out = kb("digest", str(g), "--effects", str(effects))
        assert code == 1 and out["result"]["code"] == "INVALID_SCHEMA", content


def test_digest_through_cli(tmp_path):
    f = tmp_path / "DEC-EXAMPLE.md"
    f.write_text(serialize(record("decision"), DECISION_BODY), encoding="utf-8", newline="\n")
    effects = tmp_path / "effects.json"
    effects.write_text("[]", encoding="utf-8")
    code, out = kb("digest", str(f), "--effects", str(effects))
    from kbol.digest import digest

    assert code == 0 and out["result"]["digest"] == digest(record("decision"), DECISION_BODY, [])


def test_version_says_the_installed_version():
    import kbol

    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "--version"], capture_output=True, text=True, encoding="utf-8"
    )
    assert p.returncode == 0 and p.stdout.strip() == f"kbol {kbol.__version__}"
