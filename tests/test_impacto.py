"""VAL-09 y RES-05: un cambio identifica a sus consumidores, con causa, camino y responsable."""

import copy

from conftest import decision, registro

from kbol.impacto import impacto
from kbol.proyeccion import Snapshot


def snap(pares, revision):
    return Snapshot({r["id"]: r for r, _ in pares}, revision, {r["id"]: c for r, c in pares})


def por_afectado(res):
    return {a["afectado"]: a for a in res["afectados"]}


def base():
    a = decision("DEC-A", {"C1": "Lunes.", "C2": "Verificados."})
    h = (registro("hito", id="HI-H", depende_de=[{"destino": "DEC-A#C1", "condicion": "aceptada_y_vigente"}]), "")
    h2 = (registro("hito", id="HI-H2", depende_de=[{"destino": "HI-H", "condicion": "completado_con_evidencia"}]), "")
    s = (registro("sintesis", id="SIN-S", dependencias=["DEC-A#C1"]), "")
    q = (registro("pregunta", id="Q-Q", cuestiona=["DEC-A#C2"]), "")
    otro = (registro("hito", id="HI-OTRO"), "")
    return [a, h, h2, s, q, otro]


def test_modificacion_de_clausula_llega_a_sus_consumidores_y_sigue_el_camino():
    b = snap(base(), "b")
    nueva = decision(
        "DEC-B", {"C1": "Martes."}, modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}]
    )
    p = snap(base() + [nueva], "p")
    res = impacto(b, p)
    af = por_afectado(res)
    assert set(af) == {"HI-H", "HI-H2", "SIN-S"}
    assert af["HI-H"]["camino"] == ["DEC-B", "DEC-A#C1", "HI-H"]
    assert af["HI-H2"]["camino"] == ["DEC-B", "DEC-A#C1", "HI-H", "HI-H2"]
    assert af["SIN-S"]["desfasada"] is True and af["HI-H"]["desfasada"] is False
    assert af["HI-H"]["responsable"] == ["ROL-EJEMPLO"] and af["HI-H"]["resolucion"] == "pendiente"
    assert res["cambiados"] == ["DEC-B"]


def test_sin_aristas_declaradas_no_se_inventa_impacto():
    b = snap(base(), "b")
    p = copy.deepcopy(b)
    p.registros["HI-OTRO"]["title"] = "Otro título"
    res = impacto(b, Snapshot(p.registros, "p", p.cuerpos))
    assert res["cambiados"] == ["HI-OTRO"] and res["afectados"] == []


def test_nueva_version_de_fuente_marca_a_quien_cita_la_anterior():
    fa = registro("fuente", id="F-A")
    he = registro("hecho", id="HE-A", basada_en=["F-A"], sources=[{"id": "s1", "resource": "F-A"}])
    b = snap([(fa, ""), (he, "")], "b")
    fb = registro("fuente", id="F-B", sha256="c" * 64, deja_obsoleta=["F-A"])
    p = snap([(fa, ""), (he, ""), (fb, "")], "p")
    af = por_afectado(impacto(b, p))
    assert set(af) == {"HE-A"} and af["HE-A"]["camino"] == ["F-B", "F-A", "HE-A"]


def test_derogacion_de_toda_la_decision_y_afecta_a():
    b = snap(base(), "b")
    nueva = decision("DEC-B", {"C1": "M."}, deja_obsoleta=["DEC-A"], afecta_a=["HI-OTRO"])
    af = por_afectado(impacto(b, snap(base() + [nueva], "p")))
    assert {"HI-H", "HI-H2", "SIN-S", "Q-Q", "HI-OTRO"} <= set(af)
    assert af["HI-OTRO"]["camino"] == ["DEC-B", "HI-OTRO"]


def test_rol_cambiado_y_hecho_citado_en_el_cuerpo():
    rol = registro("rol", id="ROL-EJEMPLO")
    dec = registro("decision", id="DEC-A")  # autorizado_por ROL-EJEMPLO
    per = registro("persona", id="PER-A")  # ocupa ROL-EJEMPLO
    he = registro("hecho", id="HE-A")
    q = registro("pregunta", id="Q-Z")
    pares = [(rol, ""), (dec, ""), (per, ""), (he, ""), (q, 'Ver <hecho ref="HE-A">la medida</hecho>.')]
    b = snap(pares, "b")
    p = copy.deepcopy(b)
    p.registros["ROL-EJEMPLO"]["capacidades"] = ["ratificar", "otra"]
    p.registros["HE-A"]["afirmacion"] = "Otra"
    af = por_afectado(impacto(b, Snapshot(p.registros, "p", p.cuerpos)))
    assert {"DEC-A", "PER-A", "Q-Z"} <= set(af)
    assert af["Q-Z"]["camino"] == ["HE-A", "Q-Z"]


def test_ciclos_de_consumo_no_cuelgan():
    x = registro("hito", id="HI-X", depende_de=[{"destino": "HI-Y", "condicion": "completado_con_evidencia"}])
    y = registro("hito", id="HI-Y", depende_de=[{"destino": "HI-X", "condicion": "completado_con_evidencia"}])
    b = snap([(x, ""), (y, "")], "b")
    p = copy.deepcopy(b)
    p.registros["HI-X"]["alcance"] = "otro"
    res = impacto(b, Snapshot(p.registros, "p", p.cuerpos))
    assert {a["afectado"] for a in res["afectados"]} == {"HI-Y"}
