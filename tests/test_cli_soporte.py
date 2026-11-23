"""CLI `soporte`: señala los apoyos que no rigen sin bloquear, y compara dos pares de cortes."""

import json
import subprocess
import sys

import pytest
from conftest import decision, evento, registro
from test_dependencias import con_historial

from kbol.core import serializar

T = "2026-11-10T12:00:00Z"
ANTES = "2026-11-03T12:00:00Z"


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def escribir(carpeta, r, c=""):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{r['id']}.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")


@pytest.fixture
def raiz(tmp_path):
    """Síntesis que depende de DEC-A#C1, sustituida el día 5 por DEC-B#C1."""
    carpeta = tmp_path / "kb"
    creacion = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")
    escribir(carpeta, registro("rol", id="ROL-EJEMPLO", eventos=[creacion]))
    escribir(carpeta, *decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z"))
    escribir(
        carpeta,
        *decision(
            "DEC-B",
            {"C1": "Martes."},
            registrado="2026-11-05T00:00:00Z",
            modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
        ),
    )
    escribir(carpeta, con_historial("sintesis", "borrador", id="SIN-A", dependencias=["DEC-A#C1"]), "Resumen.")
    return tmp_path


def base(raiz):
    return ["soporte", str(raiz), "--carpeta", "kb", "--valido-en", T]


def test_apoyo_roto_se_senala_y_la_salida_es_cero(raiz):
    code, out = kb(*base(raiz))
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    sin = next(r for r in out["resultado"]["registros"] if r["id"] == "SIN-A")
    assert sin["soporte"] == "roto" and sin["apoyos"][0]["situacion"] == "no_rige"
    assert out["resultado"]["registros_examinados"] == 4 and out["valido_en"] == T
    assert "respaldo semántico de los apoyos" in out["cobertura"]["no_evaluado"]


def test_ids_filtra_y_un_id_que_no_existe_es_parcial(raiz):
    code, out = kb(*base(raiz), "--ids", "SIN-A")
    assert code == 0 and [r["id"] for r in out["resultado"]["registros"]] == ["SIN-A"], out
    code, out = kb(*base(raiz), "--ids", "SIN-A", "SIN-NO")
    assert code == 3 and out["resultado"]["estado"] == "parcial" and out["resultado"]["ausentes"] == ["SIN-NO"]
    assert any("SIN-NO" in a for a in out["advertencias"])


def test_ningun_registro_examinado_es_parcial(raiz):
    code, out = kb(*base(raiz), "--ids", "SIN-NO")
    assert code == 3 and out["resultado"]["registros_examinados"] == 0, out
    assert any("ningún registro examinado" in a for a in out["advertencias"])


def test_dos_pares_de_cortes_devuelven_el_cambio_y_su_cadena(raiz):
    code, out = kb(*base(raiz), "--antes-valido-en", ANTES, "--antes-conocido-hasta", ANTES)
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    (cambio,) = out["resultado"]["cambios"]
    assert (cambio["id"], cambio["ref"], cambio["antes"]["situacion"], cambio["despues"]["situacion"]) == (
        "SIN-A",
        "DEC-A#C1",
        "rige",
        "no_rige",
    )
    assert cambio["explicacion"]["cadena"] == ["DEC-A#C1", "DEC-B#C1"]
    assert out["resultado"]["antes"]["valido_en"] == ANTES and out["resultado"]["despues"]["valido_en"] == T


def test_los_cortes_de_antes_se_validan_y_solo_valen_para_soporte(raiz):
    code, out = kb(*base(raiz), "--antes-valido-en", "2026-11-03")
    assert code == 2 and out["resultado"]["codigo"] == "TIEMPO_AMBIGUO", out
    code, out = kb("listos", str(raiz), "--carpeta", "kb", "--valido-en", T, "--antes-valido-en", ANTES)
    assert code == 2 and "solo valen para soporte" in out["resultado"]["motivo"], out
