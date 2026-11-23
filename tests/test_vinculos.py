"""Vínculos y campos de trabajo y lo asignado a una persona.

Un hito cierra, avanza, somete a prueba y produce; un plan se apoya en decisiones; hitos y preguntas tienen
responsable y evidencia; una decisión, su implementación. Son libres: cambiarlos no reabre un cierre ni una
autorización. `impacto` los sigue y `consultar` los muestra, con lo que una persona tiene asignado.
"""

import copy

from conftest import decision, registro
from test_integrar import activo

from kbol.consultar import asignado, consultar
from kbol.impacto import impacto
from kbol.importacion import comprobar
from kbol.mutabilidad import comparar
from kbol.proyeccion import Snapshot
from kbol.referencias import validar_snapshot
from kbol.schema import validar


def snap(pares, revision="r"):
    return Snapshot({r["id"]: r for r, _ in pares}, revision, {r["id"]: c for r, c in pares})


def errores(hallazgos):
    return [h for h in hallazgos if h["severidad"] == "error"]


def hito(**campos):
    return registro("hito", **{"id": "HI-A", **campos})


def test_un_hito_con_sus_vinculos_y_campos_de_trabajo_es_valido():
    r = hito(
        cierra=["Q-A"],
        avanza=["Q-B"],
        somete_a_prueba=["HIP-A"],
        produce=["DEC-EJEMPLO", "DEC-EJEMPLO#C1"],
        responsable="PER-A",
        evidencia=["tests/test_x.py", "commit abc123"],
    )
    assert errores(validar(r, "")) == []
    assert errores(validar(registro("plan", se_apoya_en=["DEC-EJEMPLO#C1"]), "")) == []
    assert errores(validar(registro("pregunta", evidencia=["salida de pytest"]), "")) == []
    d = registro("decision", implementacion="parcial")
    assert errores(validar(d, '<clausula id="C1">\nx\n</clausula>\n')) == []


def test_los_vinculos_exigen_su_tipo_de_destino_y_su_origen():
    assert errores(validar(hito(cierra=["DEC-EJEMPLO"]), ""))
    assert errores(validar(hito(somete_a_prueba=["Q-A"]), ""))
    assert errores(validar(hito(cierra=["Q-A#C1"]), ""))
    assert errores(validar(registro("decision", cierra=["Q-A"]), '<clausula id="C1">\nx\n</clausula>\n'))
    assert errores(validar(registro("decision", implementacion="casi"), '<clausula id="C1">\nx\n</clausula>\n'))


def test_un_vinculo_a_un_registro_que_no_existe_es_un_error_de_referencia():
    s = snap([(hito(cierra=["Q-NO"], responsable="ROL-NO"), "")])
    codigos = {h["ruta"] for h in errores(validar_snapshot(s))}
    assert "HI-A/cierra" in codigos and "HI-A/responsable" in codigos


def test_cambiar_vinculos_no_reabre_un_hito_completado_ni_un_plan_autorizado():
    completado = hito(estado="completado", cierra=["Q-A"])
    plan = registro("plan", estado="autorizado", se_apoya_en=["DEC-EJEMPLO"])
    base = snap([(completado, ""), (plan, "")])
    prop = copy.deepcopy(base)
    prop.registros["HI-A"].update(cierra=["Q-A", "Q-B"], produce=["DEC-EJEMPLO"], evidencia=["commit 1"])
    prop.registros["HI-A"]["responsable"] = "PER-A"
    prop.registros["PL-A"]["se_apoya_en"] = ["DEC-EJEMPLO", "DEC-OTRA"]
    assert errores(comparar(base, Snapshot(prop.registros, "p", prop.cuerpos))["hallazgos"]) == []
    prop.registros["HI-A"]["objetivo"] = "Otro"
    assert errores(comparar(base, Snapshot(prop.registros, "p", prop.cuerpos))["hallazgos"])


def test_impacto_sigue_los_vinculos_de_trabajo():
    a = decision("DEC-A", {"C1": "Lunes."})
    q = (registro("pregunta", id="Q-A"), "")
    h = (hito(cierra=["Q-A"], responsable="PER-A"), "")
    p = (registro("plan", id="PL-A", se_apoya_en=["DEC-A#C1"]), "")
    base = snap([a, q, h, p], "b")
    cambio = copy.deepcopy(q[0])
    cambio["title"] = "Otra"
    res = impacto(base, snap([a, (cambio, ""), h, p], "f"))
    afectados = {x["afectado"]: x for x in res["afectados"]}
    assert set(afectados) == {"HI-A"} and afectados["HI-A"]["responsable"] == ["PER-A"]
    nueva = decision(
        "DEC-B", {"C1": "Martes."}, modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}]
    )
    res = impacto(base, snap([a, q, h, p, nueva], "f"))
    assert "PL-A" in {x["afectado"] for x in res["afectados"]}


def _equipo():
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    david = activo(
        "persona",
        "PER-D",
        naturaleza="humana",
        identidad_ref="declarada:d",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    otro = activo("persona", "PER-J", naturaleza="humana", identidad_ref="declarada:j", ocupa=[])
    return [
        (rol, ""),
        (david, ""),
        (otro, ""),
        (hito(id="HI-1", responsable="PER-D"), ""),
        (hito(id="HI-2", responsable="ROL-OP", estado="completado"), ""),
        (hito(id="HI-3", responsable="PER-J"), ""),
        (registro("pregunta", id="Q-1", responsable="ROL-OP"), ""),
    ]


def test_lo_asignado_a_una_persona_incluye_lo_de_sus_roles_y_dice_si_sigue_abierto():
    s = snap(_equipo())
    lista = {x["id"]: x for x in asignado(s, "PER-D")}
    assert set(lista) == {"HI-1", "HI-2", "Q-1"}
    assert lista["HI-2"]["por"] == "ROL-OP" and lista["HI-2"]["abierto"] is False
    assert lista["HI-1"]["abierto"] is True
    assert [x["id"] for x in asignado(s, "PER-J")] == ["HI-3"]


def test_consultar_una_persona_trae_lo_asignado_y_un_hito_sus_campos_de_trabajo():
    s = Snapshot(*_snap_completo())
    res = consultar(s, ["PER-D", "HI-1"], valido_en=None, conocido_hasta=None)["resultados"]
    assert {x["id"] for x in res[0]["asignado"]} == {"HI-1", "HI-2", "Q-1"}
    assert res[1]["trabajo"] == {"responsable": "PER-D"}


def _snap_completo():
    pares = _equipo()
    return (
        {r["id"]: r for r, _ in pares},
        "r",
        {r["id"]: c for r, c in pares},
        {r["id"]: f"kb/{r['id']}.md" for r, _ in pares},
    )


HEREDADO = """---
type: Decisión
title: T
description: D
---
Chosen option: **Opción A**, porque alinea audiencia con visibilidad: lo que
ve un revisor externo está en `docs/`.
"""


def test_la_guarda_tolera_los_espacios_en_blanco_pero_no_una_palabra_nueva():
    r = {"id": "ADR-0003", "title": "T", "description": "D"}
    reflujo = (
        '<clausula id="C1">\n\nChosen option: **Opción A**, porque alinea audiencia con visibilidad:\n'
        "lo que ve un revisor externo está en `docs/`.\n\n</clausula>\n"
    )
    assert comprobar(r, reflujo, HEREDADO, "docs/decisions/0003.md") == []
    cambiado = reflujo.replace("externo", "interno")
    assert comprobar(r, cambiado, HEREDADO, "docs/decisions/0003.md")
