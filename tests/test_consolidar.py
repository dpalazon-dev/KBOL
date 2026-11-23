"""RES-01: qué rige. Escenarios ESC-01 y ESC-02 del contrato y casos obligatorios de cláusulas (guía §7)."""

from conftest import decision

from kbol.consolidar import consolidar
from kbol.proyeccion import Snapshot


def snap(*pares):
    return Snapshot({r["id"]: r for r, _ in pares}, revision="r1", cuerpos={r["id"]: c for r, c in pares})


def sust(destino, por):
    return {"destino": destino, "tipo": "sustitucion", "por": por}


def por_ref(res):
    return {c["referencia"]: c for c in res["clausulas"]}


CORTE_ESC01 = dict(valido_en="2026-11-03T12:00:00Z", conocido_hasta="2026-11-03T12:00:00Z")


def esc01(*extra):
    a = decision(
        "DEC-A",
        {"C1": "El informe se entrega los lunes.", "C2": "El informe solo incluye datos verificados."},
        registrado="2026-11-01T00:00:00Z",
    )
    b = decision(
        "DEC-B",
        {"C1": "El informe se entrega los martes."},
        registrado="2026-11-02T00:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-B#C1")],
    )
    c = decision(
        "DEC-C",
        {"C1": "El informe incluye también datos estimados."},
        estado="propuesta",
        modifica=[sust("DEC-A#C2", "DEC-C#C1")],
    )
    return snap(a, b, c, *extra)


def test_esc01_sustitucion_parcial_sin_perder_condiciones():
    res = consolidar(esc01(), ["DEC-A"], **CORTE_ESC01)
    c = por_ref(res)
    assert c["DEC-A#C1"]["estado"] == "vigente" and c["DEC-A#C1"]["texto"] == "El informe se entrega los martes."
    assert c["DEC-A#C1"]["origen"] == "DEC-B#C1" and c["DEC-A#C1"]["cadena"] == ["DEC-A#C1", "DEC-B#C1"]
    assert (
        c["DEC-A#C2"]["texto"] == "El informe solo incluye datos verificados." and c["DEC-A#C2"]["origen"] == "DEC-A#C2"
    )
    assert res["vigencia"] == {"DEC-A": "parcial"}
    assert res["propuestas"] == [
        {"decision": "DEC-C", "modificacion": sust("DEC-A#C2", "DEC-C#C1"), "estado": "propuesta", "vinculante": False}
    ]
    assert res["conflictos"] == []
    # La autoridad del texto que rige es la de la decisión de origen.
    assert c["DEC-A#C1"]["autoridad"]["autorizado_por"] == ["ROL-EJEMPLO"]


def test_esc01_variante_de_conflicto():
    d = decision(
        "DEC-D",
        {"C1": "El informe se entrega los miércoles."},
        registrado="2026-11-02T12:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-D#C1")],
    )
    res = consolidar(esc01(d), ["DEC-A"], **CORTE_ESC01)
    c = por_ref(res)
    assert c["DEC-A#C1"]["estado"] == "conflicto" and "texto" not in c["DEC-A#C1"]
    assert res["conflictos"] == [
        {"codigo": "CONFLICTO_NORMATIVO", "clausula": "DEC-A#C1", "candidatas": ["DEC-B#C1", "DEC-D#C1"]}
    ]
    assert c["DEC-A#C2"]["estado"] == "vigente"  # el conflicto no contamina el resto


def test_sucesion_declarada_resuelve_el_solapamiento():
    d = decision(
        "DEC-D",
        {"C1": "El informe se entrega los miércoles."},
        registrado="2026-11-02T12:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-D#C1")],
        depende_de=[{"destino": "DEC-B", "condicion": "aceptada_y_vigente"}],
    )
    c = por_ref(consolidar(esc01(d), ["DEC-A"], **CORTE_ESC01))
    assert c["DEC-A#C1"]["origen"] == "DEC-D#C1"


def test_cadena_de_sustituciones_conserva_origen():
    e = decision(
        "DEC-E",
        {"C1": "El informe se entrega los jueves."},
        registrado="2026-11-03T00:00:00Z",
        modifica=[sust("DEC-B#C1", "DEC-E#C1")],
    )
    c = por_ref(consolidar(esc01(e), ["DEC-A"], **CORTE_ESC01))
    assert c["DEC-A#C1"]["cadena"] == ["DEC-A#C1", "DEC-B#C1", "DEC-E#C1"] and c["DEC-A#C1"]["origen"] == "DEC-E#C1"


def test_derogar_la_modificadora_no_reactiva_el_texto_anterior():
    f = decision(
        "DEC-F",
        {"C1": "Motivo."},
        registrado="2026-11-03T00:00:00Z",
        modifica=[{"destino": "DEC-B#C1", "tipo": "derogacion"}],
    )
    c = por_ref(consolidar(esc01(f), ["DEC-A"], **CORTE_ESC01))
    assert c["DEC-A#C1"]["estado"] == "derogada" and c["DEC-A#C1"]["origen"] == "DEC-F"
    assert "texto" not in c["DEC-A#C1"]


def test_modificadora_retirada_no_resucita():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        hasta="2026-11-10T00:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-B#C1")],
    )
    res = consolidar(snap(a, b), ["DEC-A"], valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")
    c = por_ref(res)
    assert c["DEC-A#C1"]["estado"] == "sin_regla" and "texto" not in c["DEC-A#C1"]
    assert any("DEC-B" in a for a in res["advertencias"])


def test_modificacion_futura_no_altera_el_consolidado_actual():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        valido="2026-12-01T00:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-B#C1")],
    )
    res = consolidar(snap(a, b), ["DEC-A"], **CORTE_ESC01)
    c = por_ref(res)
    assert c["DEC-A#C1"]["texto"] == "Lunes." and res["vigencia"] == {"DEC-A": "total"}
    assert res["futuras"] == [{"decision": "DEC-B", "valido_desde": "2026-12-01T00:00:00Z"}]


def test_adicion_con_identidad_y_posicion():
    g = decision(
        "DEC-G",
        {"C1": "El informe se publica en el panel."},
        registrado="2026-11-03T00:00:00Z",
        modifica=[{"destino": "DEC-A", "tipo": "adicion", "por": "DEC-G#C1", "posicion": "tras DEC-A#C2"}],
    )
    c = por_ref(consolidar(esc01(g), ["DEC-A"], **CORTE_ESC01))
    assert c["DEC-G#C1"]["estado"] == "vigente" and c["DEC-G#C1"]["posicion"] == "tras DEC-A#C2"
    assert c["DEC-G#C1"]["adicion_a"] == "DEC-A"


def test_decision_no_vigente_no_rige():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z", valido="2026-12-01T00:00:00Z")
    res = consolidar(snap(a), ["DEC-A"], **CORTE_ESC01)
    assert res["clausulas"] == [] and res["vigencia"] == {"DEC-A": "no_vigente"}
    p = decision("DEC-P", {"C1": "x"}, estado="propuesta")
    res = consolidar(snap(p), ["DEC-P"], **CORTE_ESC01)
    assert res["clausulas"] == [] and res["vigencia"] == {"DEC-P": "no_vigente"}


def test_decision_ausente():
    res = consolidar(snap(), ["DEC-X"], **CORTE_ESC01)
    assert res["clausulas"] == [] and res["ausentes"] == ["DEC-X"]


def esc02():
    t = decision(
        "DEC-T", {"C1": "El plazo es de cinco días."}, registrado="2026-11-10T09:00:00Z", valido="2026-11-15T00:00:00Z"
    )
    u = decision(
        "DEC-U",
        {"C1": "El plazo es de siete días."},
        registrado="2026-11-20T09:00:00Z",
        valido="2026-11-12T00:00:00Z",
        modifica=[sust("DEC-T#C1", "DEC-U#C1")],
    )
    return snap(t, u)


def textos(res):
    return [c["texto"] for c in res["clausulas"] if c["estado"] == "vigente"]


def test_esc02_consulta_a_nada_conocido_que_rija():
    res = consolidar(
        esc02(), ["DEC-T", "DEC-U"], valido_en="2026-11-13T12:00:00Z", conocido_hasta="2026-11-14T12:00:00Z"
    )
    assert textos(res) == []
    assert res["futuras"] == [{"decision": "DEC-T", "valido_desde": "2026-11-15T00:00:00Z"}]
    assert res["ausentes"] == []  # DEC-U existe en la revisión, pero no constaba al corte
    assert res["vigencia"]["DEC-U"] == "no_constaba"


def test_esc02_consulta_b_retroactiva():
    res = consolidar(
        esc02(), ["DEC-T", "DEC-U"], valido_en="2026-11-13T12:00:00Z", conocido_hasta="2026-11-21T12:00:00Z"
    )
    assert textos(res) == ["El plazo es de siete días."]
    assert any("retroactiv" in a and "DEC-U" in a for a in res["advertencias"])


def test_esc02_consulta_c_dos_conocimientos():
    antes = consolidar(
        esc02(), ["DEC-T", "DEC-U"], valido_en="2026-11-16T12:00:00Z", conocido_hasta="2026-11-17T12:00:00Z"
    )
    assert textos(antes) == ["El plazo es de cinco días."]
    despues = consolidar(
        esc02(), ["DEC-T", "DEC-U"], valido_en="2026-11-16T12:00:00Z", conocido_hasta="2026-11-21T12:00:00Z"
    )
    assert textos(despues) == ["El plazo es de siete días."]  # una sola vez, aunque llegue por dos caminos


def test_consolidar_no_escribe_ni_muta_el_snapshot():
    s = esc01()
    import copy

    antes = copy.deepcopy(s.registros), copy.deepcopy(s.cuerpos)
    consolidar(s, ["DEC-A"], **CORTE_ESC01)
    assert (s.registros, s.cuerpos) == antes


def test_un_id_con_ancla_consolida_solo_esa_clausula():
    # Línea base del banco, P12: `consolidar --ids ADR-0059#C3` daba la cláusula por ausente.
    res = consolidar(esc01(), ["DEC-A#C1"], **CORTE_ESC01)
    assert [c["referencia"] for c in res["clausulas"]] == ["DEC-A#C1"]
    assert res["clausulas"][0]["origen"] == "DEC-B#C1" and res["vigencia"] == {"DEC-A": "parcial"}
    assert res["ausentes"] == []


def test_un_ancla_que_la_decision_no_tiene_es_ausente():
    res = consolidar(esc01(), ["DEC-A#C9"], **CORTE_ESC01)
    assert res["clausulas"] == [] and res["ausentes"] == ["DEC-A#C9"] and res["vigencia"] == {}
