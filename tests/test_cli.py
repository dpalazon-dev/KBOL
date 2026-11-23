"""Sobre contractual de la CLI: mismos campos en todas las operaciones y fallo cerrado."""

import json
import subprocess
import sys

import pytest
from conftest import CUERPO_DECISION, registro

from kbol.core import serializar

CAMPOS = {
    "operacion",
    "operacion_id",
    "revision",
    "valido_en",
    "conocido_hasta",
    "resultado",
    "advertencias",
    "cobertura",
}


def kb(*args, cwd=None):
    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8", cwd=cwd
    )
    return p.returncode, json.loads(p.stdout)


def test_validar_registro_valido(tmp_path):
    f = tmp_path / "DEC-EJEMPLO.md"
    f.write_text(serializar(registro("decision"), CUERPO_DECISION), encoding="utf-8", newline="\n")
    code, out = kb("validar", str(f))
    assert code == 0 and set(out) == CAMPOS
    assert out["operacion"] == "validar" and out["resultado"]["estado"] == "completado"
    assert out["resultado"]["errores"] == []
    assert out["valido_en"] is None and out["conocido_hasta"] is None
    assert "autoridad" in out["cobertura"]["no_evaluado"]


def test_validar_registro_invalido(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nid: DEC-A\n---\n", encoding="utf-8")
    code, out = kb("validar", str(f))
    assert code == 1 and out["resultado"]["estado"] == "fallido"
    assert {e["codigo"] for e in out["resultado"]["errores"]} == {"ESQUEMA_INVALIDO"}


def test_ruta_ausente_y_argumento_vacio(tmp_path):
    code, out = kb("validar", str(tmp_path / "no.md"))
    assert code == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"
    code, out = kb("validar", "")
    assert code == 2 and out["resultado"]["estado"] == "bloqueado"


@pytest.mark.parametrize("op", ["ingerir"])
def test_capacidades_no_habilitadas_fallan_cerradas(op):
    code, out = kb(op)
    assert code == 2 and set(out) == CAMPOS
    assert out["resultado"] == {
        "estado": "bloqueado",
        "codigo": None,
        "motivo": "capacidad no habilitada en esta versión",
    }


def test_migrar_en_seco_no_escribe(tmp_path):
    f = tmp_path / "QD-1.md"
    texto = "---\ntype: Pregunta\nid: QD-001\nestado: Abierta\n---\nx\n"
    f.write_text(texto, encoding="utf-8")
    code, out = kb("migrar", str(tmp_path), "--revision", "r1")
    assert code == 0 and out["revision"] == "r1"
    assert out["resultado"]["resumen"]["total"] == 1
    assert f.read_text(encoding="utf-8") == texto


def test_digest_de_registro_invalido_o_efectos_malos(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nid: DEC-A\n---\n", encoding="utf-8")
    code, out = kb("digest", str(f))
    assert code == 1 and out["resultado"]["estado"] == "fallido"
    g = tmp_path / "DEC-EJEMPLO.md"
    g.write_text(serializar(registro("decision"), CUERPO_DECISION), encoding="utf-8", newline="\n")
    for contenido in ("{malo", '[{"estado_nuevo": "aceptada", "estado_nuevo": "rechazada"}]', '{"cualquier": 1}'):
        efectos = tmp_path / "efectos.json"
        efectos.write_text(contenido, encoding="utf-8")
        code, out = kb("digest", str(g), "--efectos", str(efectos))
        assert code == 1 and out["resultado"]["codigo"] == "ESQUEMA_INVALIDO", contenido


def test_digest_por_cli(tmp_path):
    f = tmp_path / "DEC-EJEMPLO.md"
    f.write_text(serializar(registro("decision"), CUERPO_DECISION), encoding="utf-8", newline="\n")
    efectos = tmp_path / "efectos.json"
    efectos.write_text("[]", encoding="utf-8")
    code, out = kb("digest", str(f), "--efectos", str(efectos))
    from kbol.digest import digest

    assert code == 0 and out["resultado"]["digest"] == digest(registro("decision"), CUERPO_DECISION, [])


def test_version_dice_la_version_instalada():
    import kbol

    p = subprocess.run([sys.executable, "-m", "kbol.cli", "--version"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and p.stdout.strip() == f"kbol {kbol.__version__}"
