"""Skills empaquetadas: `kbol exportar_skills` escribe la skill de la versión instalada."""

import json
import subprocess
import sys
from pathlib import Path

import kbol
from kbol.exportar import MARCA, disponibles, exportada, exportar

RAIZ = Path(__file__).resolve().parent.parent


def test_las_skills_empaquetadas_son_las_de_kbol():
    assert disponibles() == ["incorporar-documento", "kbol"]


def test_las_skills_del_repositorio_son_la_exportacion_de_esta_version():
    # Si falla tras cambiar una skill o la versión: `uv run kbol exportar_skills .claude/skills`.
    for nombre in disponibles():
        copia = (RAIZ / ".claude" / "skills" / nombre / "SKILL.md").read_text(encoding="utf-8")
        assert copia == exportada(nombre, kbol.__version__), nombre


def test_la_marca_va_justo_despues_de_la_cabecera():
    lineas = exportada("kbol", "9.9.9").split("\n")
    cierre = lineas.index("---", 1)
    assert lineas[0] == "---" and lineas[cierre + 1] == MARCA.format(version="9.9.9")


def test_exporta_y_la_segunda_vez_no_reescribe(tmp_path):
    res = exportar(tmp_path, "1.0.0")
    assert res["estado"] == "completado" and len(res["escritos"]) == 2
    assert (tmp_path / "kbol" / "SKILL.md").read_text(encoding="utf-8") == exportada("kbol", "1.0.0")
    again = exportar(tmp_path, "1.0.0")
    assert again["escritos"] == [] and len(again["iguales"]) == 2


def test_sustituye_una_exportacion_anterior_pero_no_una_skill_propia(tmp_path):
    exportar(tmp_path, "1.0.0", ["kbol"])
    assert exportar(tmp_path, "2.0.0", ["kbol"])["escritos"] == [(tmp_path / "kbol" / "SKILL.md").as_posix()]
    propia = tmp_path / "incorporar-documento" / "SKILL.md"
    propia.parent.mkdir()
    propia.write_text("---\nname: propia\n---\nMía.\n", encoding="utf-8")
    res = exportar(tmp_path, "3.0.0")
    assert res["estado"] == "bloqueado" and res["rechazados"][0]["ruta"] == propia.as_posix()
    assert propia.read_text(encoding="utf-8") == "---\nname: propia\n---\nMía.\n"
    assert "kbol 2.0.0" in (tmp_path / "kbol" / "SKILL.md").read_text(encoding="utf-8")  # no escribió nada


def test_una_skill_desconocida_bloquea(tmp_path):
    assert exportar(tmp_path, "1.0.0", ["otra"])["estado"] == "bloqueado"
    assert not list(tmp_path.iterdir())


def test_la_cli_exporta_con_la_version_instalada(tmp_path):
    orden = [sys.executable, "-m", "kbol.cli", "exportar_skills", str(tmp_path / "skills"), "--skills", "kbol"]
    p = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["resultado"]["estado"] == "completado"
    assert f"kbol {kbol.__version__}" in (tmp_path / "skills" / "kbol" / "SKILL.md").read_text(encoding="utf-8")
    (tmp_path / "skills" / "kbol" / "SKILL.md").write_text("propia\n", encoding="utf-8")
    assert subprocess.run(orden, capture_output=True, text=True, encoding="utf-8").returncode == 2
