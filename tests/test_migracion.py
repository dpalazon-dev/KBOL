"""Migración en seco del formato heredado: trazable, sin inventar historia ni autoridad."""

from pathlib import Path

import pytest

from kbol.migracion import inspeccionar, inspeccionar_carpeta

HEREDADOS = Path(__file__).parent / "heredados"


def leer(nombre):
    return (HEREDADOS / f"{nombre}.txt").read_text(encoding="utf-8")


def informe(nombre):
    return inspeccionar(leer(nombre), ruta=f"docs/{nombre}", revision="23fef059")


def test_conserva_original_y_no_fabrica_eventos_admitidos():
    r = informe("0063-una-copia-de-trabajo-por-sesion.md")
    assert r["original"] == leer("0063-una-copia-de-trabajo-por-sesion.md")
    assert r["id"] == "ADR-0063" and r["tipo"] == "decision" and r["estado_propuesto"] == "aceptada"
    ev = r["evento_importacion"]
    assert ev["tipo_evento"] == "importacion" and ev["registrado_en"] is None
    assert ev["valido_desde"] == "2026-10-30" and ev["precision"] == "dia"
    assert ev["procedencia"] == {
        "ruta": "docs/0063-una-copia-de-trabajo-por-sesion.md",
        "revision": "23fef059",
    }
    # La aprobación heredada es una declaración, no una ratificación autenticada.
    assert r["autoridad_heredada"] == {"texto": "Responsable, 30 oct 2026", "clasificacion": "insuficiente"}
    assert r["requiere_revision"]


def test_sustitucion_parcial_exige_revision_individual():
    r = informe("0001-catalogo-por-modulos-independientes.md")
    assert r["estado_propuesto"] == "aceptada"
    assert {
        "campo": "modifica",
        "candidatos": ["ADR-0010"],
        "motivo": "sustitución parcial en prosa: anclas y alcance sin determinar",
    } in r["ambiguedades"]
    assert r["requiere_revision"]


@pytest.mark.parametrize(
    "nombre,estado,ambiguo",
    [
        ("QD-184.md", "resuelta", False),
        ("QD-045.md", "resuelta", True),  # cierre factual sin fuente registrada
        ("QD-054.md", "abierta", True),  # «En revisión» no existe en el contrato
        ("QD-112.md", "descartada", False),
        ("PL-001.md", "autorizado", True),  # «En curso» no existe para planes
        ("PL-001-H3.md", "propuesto", True),  # Pendiente: la autorización del hito no consta
        ("PL-001-H6.md", "completado", True),  # Cumplido sin aceptación humana acreditada
    ],
)
def test_mapeo_de_estados(nombre, estado, ambiguo):
    r = informe(nombre)
    assert r["estado_propuesto"] == estado
    assert bool(r["ambiguedades"]) is ambiguo, r["ambiguedades"]


def test_relacion_de_cierre_se_propone_como_candidata():
    r = informe("QD-184.md")
    assert r["relaciones_propuestas"]["resuelta_por"] == ["ADR-0063"]


def test_no_registros_quedan_fuera():
    r = inspeccionar("---\ntype: Esquema\ntitle: X\n---\n", ruta="docs/x/esquema.md", revision="r")
    assert r["tipo"] is None and r["resultado"] == "fuera_de_alcance"


def test_indices_generados_son_vistas_fuera_de_alcance():
    r = inspeccionar("* [ADR-0001](0001.md)\n", ruta="docs/decisions/index.md", revision="r")
    assert r["resultado"] == "fuera_de_alcance"


def test_cabecera_ilegible_se_informa_sin_caer():
    r = inspeccionar("---\na: [\n---\n", ruta="docs/x.md", revision="r")
    assert r["resultado"] == "fallido" and r["codigo"] == "ESQUEMA_INVALIDO"


def test_carpeta_produce_resumen_sin_escribir(tmp_path):
    for p in HEREDADOS.glob("*.md.txt"):
        (tmp_path / p.name[: -len(".txt")]).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    antes = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    res = inspeccionar_carpeta(tmp_path, revision="23fef059")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == antes
    assert res["resumen"]["total"] == 10
    assert res["resumen"]["requieren_revision"] >= 6
