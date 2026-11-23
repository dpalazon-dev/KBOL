"""Consulta `soporte`: si rige en los dos cortes lo que sostiene a cada registro, y qué cambió."""

import copy

from conftest import decision, evento, registro

from kbol.proyeccion import Snapshot
from kbol.soporte import apoyos, delta, soporte

T1, T2, T3, T4, T5 = (f"2026-11-0{d}T00:00:00Z" for d in (1, 2, 3, 4, 5))
ANTES = dict(valido_en="2026-11-03T12:00:00Z", conocido_hasta="2026-11-03T12:00:00Z")
DESPUES = dict(valido_en="2026-11-10T12:00:00Z", conocido_hasta="2026-11-10T12:00:00Z")


def historial(tipo, ident, *pasos, **campos):
    """Registro con un evento de estado por paso (estado, registrado_en[, valido_desde])."""
    eventos, previo = [], None
    for i, (estado, t, *desde) in enumerate(pasos):
        eventos.append(
            evento(
                "creacion" if previo is None else "transicion",
                evento_id=f"E{i}",
                estado_anterior=previo,
                estado_nuevo=estado,
                registrado_en=t,
                valido_desde=desde[0] if desde else t,
            )
        )
        previo = estado
    return registro(tipo, id=ident, estado=previo, eventos=eventos, **campos)


def hecho(ident, t=T1, desde=None, **campos):
    return historial("hecho", ident, ("propuesta", t), ("aceptada", t, desde or t), **campos)


def sintesis(ident, dependencias):
    return historial("sintesis", ident, ("borrador", T1), dependencias=dependencias)


def snap(*pares, heredados=None):
    regs, cuerpos = {}, {}
    for par in pares:
        r, c = par if isinstance(par, tuple) else (par, "")
        regs[r["id"]], cuerpos[r["id"]] = r, c
    return Snapshot(regs, "r1", cuerpos, {}, heredados or {})


def entrada(res, ident):
    return next(r for r in res["registros"] if r["id"] == ident)


def apoyo(res, ident, ref):
    return next(a for a in entrada(res, ident)["apoyos"] if a["ref"] == ref)


def caso_de_banco(**modificacion):
    """Síntesis que depende de DEC-A#C1; DEC-B, aceptada después, la sustituye o deroga. La síntesis no cambia."""
    a = decision("DEC-A", {"C1": "Lunes."}, registrado=T1)
    b = decision("DEC-B", {"C1": "Martes."}, registrado=T5, modifica=[{"destino": "DEC-A#C1", **modificacion}])
    return snap(a, b, (sintesis("SIN-A", ["DEC-A#C1"]), "Resumen: el informe se entrega los lunes."))


def test_sintesis_cuyo_texto_no_cambia_pero_pierde_vigencia():
    s = caso_de_banco(tipo="sustitucion", por="DEC-B#C1")
    antes, despues = soporte(s, **ANTES), soporte(s, **DESPUES)
    assert apoyo(antes, "SIN-A", "DEC-A#C1")["situacion"] == "rige"
    assert entrada(antes, "SIN-A")["soporte"] == "intacto"
    a = apoyo(despues, "SIN-A", "DEC-A#C1")
    assert a["situacion"] == "no_rige" and a["campo"] == "dependencias" and "DEC-B#C1" in a["motivo"]
    assert a["cadena"] == ["DEC-A#C1", "DEC-B#C1"] and a["origen"] == "DEC-B#C1"
    assert entrada(despues, "SIN-A")["soporte"] == "roto" and entrada(despues, "SIN-A")["estado"] == "borrador"
    d = delta(s, ANTES, DESPUES)
    (cambio,) = d["cambios"]
    assert (cambio["id"], cambio["ref"], cambio["antes"]["situacion"], cambio["despues"]["situacion"]) == (
        "SIN-A",
        "DEC-A#C1",
        "rige",
        "no_rige",
    )
    assert cambio["explicacion"]["cadena"] == ["DEC-A#C1", "DEC-B#C1"]
    assert {"id": "SIN-A", "antes": "intacto", "despues": "roto"} in d["registros"]


def test_clausula_derogada_nombra_la_decision_que_la_deroga():
    s = caso_de_banco(tipo="derogacion", por="DEC-B")
    a = apoyo(soporte(s, **DESPUES), "SIN-A", "DEC-A#C1")
    assert a["situacion"] == "no_rige" and a["origen"] == "DEC-B" and "derogada" in a["motivo"]
    assert delta(s, ANTES, DESPUES)["cambios"][0]["explicacion"]["origen"] == "DEC-B"


def test_validez_que_termina_antes_del_corte_explica_la_transicion():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado=T1, hasta=T5)
    s = snap(a, sintesis("SIN-A", ["DEC-A#C1"]))
    assert apoyo(soporte(s, **ANTES), "SIN-A", "DEC-A#C1")["situacion"] == "rige"
    assert apoyo(soporte(s, **DESPUES), "SIN-A", "DEC-A#C1")["situacion"] == "no_rige"
    (cambio,) = delta(s, ANTES, DESPUES)["cambios"]
    assert cambio["explicacion"]["transicion"]["valido_hasta"] == T5


def test_hecho_sucedido_no_rige_y_nombra_a_su_sucesor():
    s = snap(hecho("HE-A"), hecho("HE-B", t=T5, deja_obsoleta=["HE-A"]), hecho("HE-X", basada_en=["HE-A"]))
    assert apoyo(soporte(s, **ANTES), "HE-X", "HE-A")["situacion"] == "rige"
    a = apoyo(soporte(s, **DESPUES), "HE-X", "HE-A")
    assert a["situacion"] == "no_rige" and a["sucesoras"] == ["HE-B"]
    assert delta(s, ANTES, DESPUES)["cambios"][0]["explicacion"]["sucesoras"] == ["HE-B"]


def test_fuente_retirada_no_rige_en_basada_en_ni_en_sources():
    f = historial("fuente", "F-A", ("registrada", T1), ("retirada", T5))
    x = hecho("HE-X", basada_en=["F-A"], sources=[{"id": "s1", "resource": "F-A"}])
    s = snap(f, x)
    res = soporte(s, **DESPUES)
    assert [(a["campo"], a["situacion"]) for a in entrada(res, "HE-X")["apoyos"]] == [
        ("basada_en", "no_rige"),
        ("sources", "no_rige"),
    ]
    assert "retirada" in apoyo(res, "HE-X", "F-A")["motivo"]
    assert entrada(soporte(s, **ANTES), "HE-X")["soporte"] == "intacto"


def test_correccion_tardia_cambia_la_respuesta_con_el_corte_de_conocimiento():
    # HE-B se incorpora el día 5 con efecto desde el día 2: lo sabido el día 4 aún no la incluye.
    b = hecho("HE-B", t=T5, desde=T2, deja_obsoleta=["HE-A"])
    s = snap(hecho("HE-A"), b, hecho("HE-X", basada_en=["HE-A"]))
    valido = "2026-11-10T12:00:00Z"
    sabido_el_4 = dict(valido_en=valido, conocido_hasta=T4)
    sabido_el_10 = dict(valido_en=valido, conocido_hasta=valido)
    assert apoyo(soporte(s, **sabido_el_4), "HE-X", "HE-A")["situacion"] == "rige"
    assert apoyo(soporte(s, **sabido_el_10), "HE-X", "HE-A")["situacion"] == "no_rige"
    assert delta(s, sabido_el_4, sabido_el_10)["cambios"][0]["explicacion"]["sucesoras"] == ["HE-B"]


def test_tiempo_con_precision_de_dia_es_indeterminado():
    s = snap(hecho("HE-A", desde="2026-11-10"), hecho("HE-X", basada_en=["HE-A"]))
    res = soporte(s, **DESPUES)
    a = apoyo(res, "HE-X", "HE-A")
    assert a["situacion"] == "indeterminado" and a["codigo"] == "TIEMPO_AMBIGUO"
    assert entrada(res, "HE-X")["soporte"] == "indeterminado"


def test_sucesora_con_tiempo_ambiguo_deja_el_apoyo_indeterminado():
    b = hecho("HE-B", t=T5, desde="2026-11-10", deja_obsoleta=["HE-A"])
    a = apoyo(soporte(snap(hecho("HE-A"), b, hecho("HE-X", basada_en=["HE-A"])), **DESPUES), "HE-X", "HE-A")
    assert a["situacion"] == "indeterminado" and a["sucesoras"] == ["HE-B"]


def test_destino_ausente_rompe_el_soporte():
    res = soporte(snap(hecho("HE-X", basada_en=["F-NO"])), **DESPUES)
    a = apoyo(res, "HE-X", "F-NO")
    assert a["situacion"] == "ausente" and a["codigo"] == "REFERENCIA_AUSENTE"
    assert entrada(res, "HE-X")["soporte"] == "roto"


def test_decision_propuesta_como_apoyo_no_rige():
    p = decision("DEC-P", {"C1": "x"}, estado="propuesta")
    a = apoyo(soporte(snap(p, sintesis("SIN-A", ["DEC-P#C1"])), **DESPUES), "SIN-A", "DEC-P#C1")
    assert a["situacion"] == "no_rige" and a["estado"] == "propuesta"


def test_cita_de_hecho_en_el_cuerpo_cuenta_como_apoyo():
    x = (hecho("HE-X", basada_en=[]), 'Según <hecho ref="HE-A">el caudal</hecho>, basta.')
    res = soporte(snap(hecho("HE-A"), x), **DESPUES)
    assert [(a["campo"], a["ref"], a["situacion"]) for a in entrada(res, "HE-X")["apoyos"]] == [
        ("cuerpo", "HE-A", "rige")
    ]


def test_marca_mal_formada_se_informa_y_no_se_calla():
    x = (hecho("HE-X", basada_en=["HE-A"]), 'Según <hecho ref="HE-B">sin cierre.')
    assert apoyos(*x)[1] and "cuerpo mal formado" in apoyos(*x)[1]
    res = soporte(snap(hecho("HE-A"), x), **DESPUES)
    e = entrada(res, "HE-X")
    assert "cuerpo mal formado" in e["cuerpo"] and e["soporte"] == "indeterminado"
    assert any("HE-X" in t and "cuerpo mal formado" in t for t in res["advertencias"])


def test_sintesis_citada_informa_su_estado_sin_vigencia_y_heredado_no_rompe():
    heredada = {"id": "ADR-0001", "tipo": "decision", "ruta": "d.md", "estado_heredado": "Aceptada"}
    s = snap(sintesis("SIN-A", []), sintesis("SIN-B", ["SIN-A", "ADR-0001"]), heredados={"ADR-0001": heredada})
    res = soporte(s, **DESPUES)
    assert [(a["ref"], a["situacion"], a.get("estado")) for a in entrada(res, "SIN-B")["apoyos"]] == [
        ("SIN-A", "sin_vigencia", "borrador"),
        ("ADR-0001", "heredado", "Aceptada"),
    ]
    assert entrada(res, "SIN-B")["soporte"] == "intacto" and entrada(res, "SIN-A")["soporte"] == "sin_apoyos"


def test_ids_filtra_y_nombra_los_ausentes():
    res = soporte(caso_de_banco(tipo="sustitucion", por="DEC-B#C1"), **DESPUES, ids=["SIN-A", "SIN-NO"])
    assert [r["id"] for r in res["registros"]] == ["SIN-A"] and res["ausentes"] == ["SIN-NO"]
    assert res["registros_examinados"] == 1 and res["recuento"] == {"roto": 1}


def test_la_consulta_no_cambia_el_snapshot():
    s = caso_de_banco(tipo="sustitucion", por="DEC-B#C1")
    registros, cuerpos = copy.deepcopy(s.registros), copy.deepcopy(s.cuerpos)
    soporte(s, **DESPUES)
    delta(s, ANTES, DESPUES)
    assert s.registros == registros and s.cuerpos == cuerpos


def test_sintesis_retirada_como_apoyo_rompe_el_soporte():
    """Un apoyo sin estado efectivo no rompe por sí solo, pero uno que consta retirado sí."""
    retirada = historial("sintesis", "SIN-A", ("borrador", T1), ("retirada", T1), dependencias=[])
    res = soporte(snap(retirada, sintesis("SIN-B", ["SIN-A"])), **DESPUES)
    assert apoyo(res, "SIN-B", "SIN-A")["situacion"] == "sin_vigencia"
    assert apoyo(res, "SIN-B", "SIN-A")["estado"] == "retirada" and entrada(res, "SIN-B")["soporte"] == "roto"


def test_sin_ids_los_heredados_se_nombran_y_no_se_examinan():
    heredada = {"id": "ADR-0001", "tipo": "decision", "ruta": "d.md", "estado_heredado": "Aceptada"}
    res = soporte(snap(sintesis("SIN-A", []), heredados={"ADR-0001": heredada}), **DESPUES)
    assert [r["id"] for r in res["registros"]] == ["SIN-A"] and res["registros_examinados"] == 1
    assert res["heredados"] == [heredada]
