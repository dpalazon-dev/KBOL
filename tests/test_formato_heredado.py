"""Formato heredado configurable por instalación.

Los registros de ejemplo son sintéticos, con la forma de los de un proyecto con su propio formato: IDs `DEC-nnn`, `Q-nnn` y `H-nnn`,
estado «Vigente» y prosa de estado separada por punto o coma. Sin `formato_heredado`, la lectura es la del formato por defecto.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from kbol.consolidar import consolidar
from kbol.consultar import consultar
from kbol.migracion import POR_DEFECTO, formato_de, inspeccionar
from kbol.snapshot import cargar

HEREDADOS = Path(__file__).parent / "heredados"
C = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")

FORMATO = {
    "registros": {
        "Decisión": {"tipo": "decision", "id": r"DEC-\d{3,}", "equivalencias": {"Vigente": "Aceptada"}},
        "Pregunta": {"tipo": "pregunta", "id": r"Q-\d{3,}", "equivalencias": {"Draft": "Abierta"}},
        "Hipótesis": {"tipo": "hipotesis", "id": r"H-\d{3,}"},
    },
    "separadores": "(;.,",
}
INSTALACION = {"proyecto": "Negocio", "formato_heredado": FORMATO}


def doc(type_, ident, estado, **extra):
    campos = "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in extra.items())
    cabecera = f"type: {type_}\n" + (f"id: {ident}\n" if ident else "")
    return (
        f"---\n{cabecera}title: Ejemplo\nestado: {json.dumps(estado, ensure_ascii=False)}\n{campos}---\n\n# Ejemplo\n"
    )


DEC_VIGENTE = doc("Decisión", "DEC-108", "Vigente", fecha="27 oct 2026", adoptada_por="Fundadores")
DEC_PARCIAL = doc("Decisión", "DEC-020", "Vigente; sustituida en parte por DEC-117 y DEC-130")
DEC_SUSTITUIDA = doc("Decisión", "DEC-015", "Sustituida por DEC-130")
Q_RESUELTA = doc(
    "Pregunta",
    "Q-087",
    "Resuelta (decisión, 27 oct 2026): el módulo sale (DEC-108). Comunicado (Q-096): en pausa",
    resuelta_por="DEC-108",
)
Q_SOLO_YAML = doc("Pregunta", "Q-010", "Resuelta (decisión, 19 oct 2026)", resuelta_por="DEC-003")
Q_SIN_DECISION = doc("Pregunta", "Q-011", "Resuelta (decisión, 19 oct 2026)", resuelta_por="—")
Q_DRAFT = doc("Pregunta", "Q-012", "Draft")
H_PROSA = doc("Hipótesis", "H-068", "Abierta. Comunicado de la dirección (REU-006): se vio una oportunidad")


def negocio(carpeta, **archivos):
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, texto in archivos.items():
        (carpeta / f"{nombre}.md").write_text(texto, encoding="utf-8", newline="\n")
    return carpeta


def test_sin_formato_declarado_se_lee_el_de_por_defecto():
    assert formato_de({}) is POR_DEFECTO and formato_de({"proyecto": "Faro"}) is POR_DEFECTO


@pytest.mark.parametrize(
    ("cambio", "error"),
    [
        ({"registros": {"decision": {"tipo": "decision", "id": r"DEC-\d+"}}}, "tipo del perfil"),
        ({"registros": {"Reunión": {"tipo": "fuente", "id": r"REU-\d+"}}}, "formato heredado"),
        ({"registros": {"Decisión": {"tipo": "decision", "id": r"\d+"}}}, "prefijo literal"),
        ({"registros": {"Hipótesis": {"tipo": "hipotesis", "id": r"Q-\d+"}}}, "otro tipo"),
        ({"registros": {"Decisión": {"tipo": "decision", "id": r"DEC-(\d+"}}}, "patrón"),
        (
            {"registros": {"Decisión": {"tipo": "decision", "id": r"DEC-\d+", "equivalencias": {"Vigente": "Rige"}}}},
            "Rige",
        ),
        ({"registros": {"Decisión": {"tipo": "decision", "id": r"DEC-\d+", "otra": 1}}}, "otra"),
        ({"registros": {}}, "registros"),
        ({"separadores": ""}, "separadores"),
        ({"extra": True}, "extra"),
    ],
)
def test_una_configuracion_mal_formada_se_rechaza(cambio, error):
    with pytest.raises(ValueError, match=error):
        formato_de({"formato_heredado": {**FORMATO, **cambio}})


def test_vigente_equivale_a_aceptada_y_conserva_las_reglas_de_revision():
    f = formato_de(INSTALACION)
    vigente = inspeccionar(DEC_VIGENTE, "control/decisions/DEC-108.md", "r1", f)
    assert vigente["tipo"] == "decision" and vigente["id"] == "DEC-108"
    assert vigente["estado_heredado"] == "Vigente" and vigente["estado_propuesto"] == "aceptada"
    assert vigente["ambiguedades"] == [] and vigente["requiere_revision"]  # la autoridad en prosa no se comprueba
    parcial = inspeccionar(DEC_PARCIAL, "DEC-020.md", "r1", f)
    [amb] = parcial["ambiguedades"]
    assert parcial["estado_propuesto"] == "aceptada" and amb["campo"] == "modifica"
    assert amb["candidatos"] == ["DEC-117", "DEC-130"]
    sustituida = inspeccionar(DEC_SUSTITUIDA, "DEC-015.md", "r1", f)
    assert sustituida["ambiguedades"][0]["campo"] == "deja_obsoleta"
    assert sustituida["ambiguedades"][0]["candidatos"] == ["DEC-130"]


def test_la_cabecera_se_corta_en_los_separadores_declarados():
    f = formato_de(INSTALACION)
    h = inspeccionar(H_PROSA, "H-068.md", "r1", f)
    assert h["estado_propuesto"] == "abierta" and h["ambiguedades"] == []
    # Con los separadores del formato por defecto, la misma prosa no tiene correspondencia.
    assert inspeccionar(H_PROSA, "H-068.md", "r1")["estado_propuesto"] is None
    assert inspeccionar(Q_DRAFT, "Q-012.md", "r1", f)["estado_propuesto"] == "abierta"


def test_resuelta_por_se_lee_del_campo_y_del_texto():
    f = formato_de(INSTALACION)
    q = inspeccionar(Q_RESUELTA, "Q-087.md", "r1", f)
    assert q["estado_propuesto"] == "resuelta" and q["relaciones_propuestas"] == {"resuelta_por": ["DEC-108"]}
    assert q["ambiguedades"] == []
    solo = inspeccionar(Q_SOLO_YAML, "Q-010.md", "r1", f)
    assert solo["relaciones_propuestas"] == {"resuelta_por": ["DEC-003"]} and solo["ambiguedades"] == []
    sin = inspeccionar(Q_SIN_DECISION, "Q-011.md", "r1", f)
    assert sin["relaciones_propuestas"] == {"resuelta_por": []}
    assert sin["ambiguedades"][0]["motivo"] == "resuelta sin decisión identificable"


def test_resuelta_por_del_campo_tambien_en_el_formato_por_defecto():
    texto = doc("Pregunta", "QD-300", "Resuelta", resuelta_por="ADR-0063")
    assert inspeccionar(texto, "QD-300.md", "r1")["relaciones_propuestas"] == {"resuelta_por": ["ADR-0063"]}


def test_cargar_con_el_formato_declarado_lee_los_heredados(tmp_path):
    negocio(tmp_path / "control", **{"DEC-108": DEC_VIGENTE, "Q-087": Q_RESUELTA, "H-068": H_PROSA})
    sin, cob_sin = cargar(tmp_path, "control", heredados=True)
    assert sin.heredados == {} and len(cob_sin["invalidos"]) == 3 and cob_sin["estado"] == "parcial"
    snap, cob = cargar(tmp_path, "control", heredados=True, formato=formato_de(INSTALACION))
    assert set(snap.heredados) == {"DEC-108", "Q-087", "H-068"} and snap.registros == {}
    assert cob["invalidos"] == [] and cob["estado"] == "completo" and cob["heredados"] == 3
    assert snap.heredados["Q-087"]["relaciones_propuestas"] == {"resuelta_por": ["DEC-108"]}


def test_el_formato_declarado_sustituye_al_de_por_defecto(tmp_path):
    carpeta = negocio(tmp_path / "control", **{"DEC-108": DEC_VIGENTE})
    shutil.copy(HEREDADOS / "QD-054.md.txt", carpeta / "QD-054.md")
    snap, cob = cargar(tmp_path, "control", heredados=True, formato=formato_de(INSTALACION))
    assert set(snap.heredados) == {"DEC-108"}
    assert [i["ruta"] for i in cob["invalidos"]] == ["control/QD-054.md"]


def test_el_id_tiene_que_encajar_en_el_patron_de_su_etiqueta(tmp_path):
    negocio(tmp_path / "control", **{"Q-200": doc("Decisión", "Q-200", "Vigente")})
    snap, cob = cargar(tmp_path, "control", heredados=True, formato=formato_de(INSTALACION))
    assert snap.heredados == {} and cob["invalidos"][0]["motivo"] == "registro heredado sin id válido: 'Q-200'"


def test_sin_id_cuenta_como_registro_si_el_nombre_es_un_id_del_formato(tmp_path):
    negocio(
        tmp_path / "control",
        **{"DEC-005": doc("Decisión", None, "Vigente"), "hoja-de-ruta": doc("Decisión", None, "Vigente")},
    )
    _, cob = cargar(tmp_path, "control", heredados=True, formato=formato_de(INSTALACION))
    assert [i["ruta"] for i in cob["invalidos"]] == ["control/DEC-005.md"] and cob["omitidos"] == 1


def test_un_heredado_leido_con_el_formato_declarado_no_rige(tmp_path):
    negocio(tmp_path / "control", **{"DEC-108": DEC_VIGENTE, "Q-087": Q_RESUELTA})
    snap, _ = cargar(tmp_path, "control", heredados=True, formato=formato_de(INSTALACION))
    res = consolidar(snap, ["DEC-108"], **C)
    assert [f["id"] for f in res["heredados"]] == ["DEC-108"]
    [r] = consultar(snap, ["DEC-108"], **C)["resultados"]
    assert r["encontrado"] == "heredado" and r["rige"] is False and r["estado_propuesto"] == "aceptada"


def kbol(*args):
    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8", check=False
    )
    return json.loads(p.stdout), p.returncode


def test_cli_lee_el_formato_de_la_instalacion(tmp_path):
    negocio(tmp_path / "control", **{"DEC-108": DEC_VIGENTE, "Q-087": Q_RESUELTA, "H-068": H_PROSA})
    instalacion = tmp_path / "instalacion.json"
    instalacion.write_text(json.dumps(INSTALACION), encoding="utf-8")
    comunes = ["--carpeta", "control", "--valido-en", C["valido_en"], "--instalacion", str(instalacion)]
    antes, _ = kbol("listos", str(tmp_path), "--heredados", "--carpeta", "control", "--valido-en", C["valido_en"])
    assert antes["cobertura"]["heredados"] == 0 and len(antes["cobertura"]["invalidos"]) == 3
    listos, codigo = kbol("listos", str(tmp_path), "--heredados", *comunes)
    assert codigo == 3 and listos["cobertura"]["heredados"] == 3 and listos["cobertura"]["invalidos"] == []
    consolidado, _ = kbol("consolidar", str(tmp_path), "--heredados", "--ids", "Q-087", *comunes)
    [q] = consolidado["resultado"]["heredados"]
    assert q["relaciones_propuestas"] == {"resuelta_por": ["DEC-108"]}
    consulta, codigo = kbol("consultar", str(tmp_path), "--ids", "DEC-108", *comunes)
    assert codigo == 3 and consulta["resultado"]["resultados"][0]["rige"] is False
    migrado, codigo = kbol("migrar", str(tmp_path / "control"), "--revision", "r1", "--instalacion", str(instalacion))
    assert codigo == 0 and migrado["resultado"]["resumen"]["propuestos"] == 3


def test_cli_una_instalacion_mal_formada_no_lee_nada(tmp_path):
    negocio(tmp_path / "control", **{"DEC-108": DEC_VIGENTE})
    instalacion = tmp_path / "instalacion.json"
    instalacion.write_text(json.dumps({"formato_heredado": {"registros": {}}}), encoding="utf-8")
    salida, codigo = kbol(
        "listos", str(tmp_path), "--heredados", "--carpeta", "control", "--valido-en", C["valido_en"],
        "--instalacion", str(instalacion),
    )  # fmt: skip
    assert codigo == 1 and salida["resultado"]["codigo"] == "ESQUEMA_INVALIDO"
