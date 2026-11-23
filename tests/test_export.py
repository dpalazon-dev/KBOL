"""Packaged skills: `kbol export_skills` writes the skill of the installed version."""

import json
import subprocess
import sys
from pathlib import Path

import kbol
from kbol.export import MARK, available, export, exported

ROOT = Path(__file__).resolve().parent.parent


def test_the_packaged_skills_are_kbols():
    assert available() == ["add-document", "kbol"]


def test_the_repository_skills_are_the_export_of_this_version():
    # If it fails after changing a skill or the version: `uv run kbol export_skills .claude/skills`.
    for name in available():
        copy = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert copy == exported(name, kbol.__version__), name


def test_the_mark_goes_right_after_the_header():
    lines = exported("kbol", "9.9.9").split("\n")
    closing = lines.index("---", 1)
    assert lines[0] == "---" and lines[closing + 1] == MARK.format(version="9.9.9")


def test_exports_and_the_second_time_does_not_rewrite(tmp_path):
    res = export(tmp_path, "1.0.0")
    assert res["state"] == "completed" and len(res["written"]) == 2
    assert (tmp_path / "kbol" / "SKILL.md").read_text(encoding="utf-8") == exported("kbol", "1.0.0")
    again = export(tmp_path, "1.0.0")
    assert again["written"] == [] and len(again["equal"]) == 2


def test_replaces_an_earlier_export_but_not_an_own_skill(tmp_path):
    export(tmp_path, "1.0.0", ["kbol"])
    assert export(tmp_path, "2.0.0", ["kbol"])["written"] == [(tmp_path / "kbol" / "SKILL.md").as_posix()]
    own = tmp_path / "add-document" / "SKILL.md"
    own.parent.mkdir()
    own.write_text("---\nname: own\n---\nMine.\n", encoding="utf-8")
    res = export(tmp_path, "3.0.0")
    assert res["state"] == "blocked" and res["rejected"][0]["path"] == own.as_posix()
    assert own.read_text(encoding="utf-8") == "---\nname: own\n---\nMine.\n"
    assert "kbol 2.0.0" in (tmp_path / "kbol" / "SKILL.md").read_text(encoding="utf-8")  # it wrote nothing


def test_replaces_an_export_from_kbol_0_12(tmp_path):
    old = tmp_path / "kbol" / "SKILL.md"
    old.parent.mkdir()
    old.write_text(
        "---\nname: kbol\n---\n<!-- Exportada por kbol 0.12.0 con `kbol exportar_skills`. -->\n", encoding="utf-8"
    )
    assert export(tmp_path, "1.0.0", ["kbol"])["written"] == [old.as_posix()]


def test_an_unknown_skill_blocks(tmp_path):
    assert export(tmp_path, "1.0.0", ["other"])["state"] == "blocked"
    assert not list(tmp_path.iterdir())


def test_the_cli_exports_with_the_installed_version(tmp_path):
    command = [sys.executable, "-m", "kbol.cli", "export_skills", str(tmp_path / "skills"), "--skills", "kbol"]
    p = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["result"]["state"] == "completed"
    assert f"kbol {kbol.__version__}" in (tmp_path / "skills" / "kbol" / "SKILL.md").read_text(encoding="utf-8")
    (tmp_path / "skills" / "kbol" / "SKILL.md").write_text("own\n", encoding="utf-8")
    assert subprocess.run(command, capture_output=True, text=True, encoding="utf-8").returncode == 2
