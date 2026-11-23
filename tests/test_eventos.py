"""Estado materializado desde eventos y proyección total de `status` (VAL-08)."""

import pytest
from conftest import CUERPO_DECISION, evento, registro

from kbol.eventos import ErrorDeHistorial, estado_en
from kbol.proyeccion import Snapshot, proyectar_status
from kbol.schema import validar


def creacion(estado, t="2026-11-01T00:00:00Z", eid="E0"):
    return evento("creacion", evento_id=eid, estado_anterior=None, estado_nuevo=estado, registrado_en=t, valido_desde=t)


def paso(a, b, t, valido=None, eid="E1"):
    return evento(estado_anterior=a, estado_nuevo=b, registrado_en=t, valido_desde=valido or t, evento_id=eid)


def test_estado_reconstruido_al_corte_de_conocimiento():
    ev = [creacion("propuesta"), paso("propuesta", "aceptada", "2026-11-10T09:00:00Z", "2026-11-15T00:00:00Z")]
    assert estado_en(ev, "2026-11-05T00:00:00Z") == "propuesta"
    assert estado_en(ev, "2026-11-10T09:00:00Z") == "aceptada"
    assert estado_en(ev, "2026-10-01T00:00:00Z") is None


def test_historial_incoherente_se_rechaza():
    with pytest.raises(ErrorDeHistorial):
        estado_en([paso("propuesta", "aceptada", "2026-11-02T00:00:00Z")], None)  # sin creación
    with pytest.raises(ErrorDeHistorial):
        estado_en([creacion("propuesta"), paso("rechazada", "aceptada", "2026-11-02T00:00:00Z")], None)
    with pytest.raises(ErrorDeHistorial):  # registrado fuera de orden
        estado_en(
            [creacion("propuesta", "2026-11-05T00:00:00Z"), paso("propuesta", "aceptada", "2026-11-02T00:00:00Z")], None
        )


def test_estado_escrito_debe_coincidir_con_el_historial():
    ev = [creacion("propuesta")]
    assert validar(registro("decision", estado="aceptada", eventos=ev), CUERPO_DECISION, modo="canonico")
    assert validar(registro("decision", estado="propuesta", eventos=ev), CUERPO_DECISION, modo="canonico") == []


def test_reapertura_sin_politica_rechazada():
    ev = [
        creacion("abierta"),
        paso("abierta", "resuelta", "2026-11-02T00:00:00Z"),
        paso("resuelta", "abierta", "2026-11-03T00:00:00Z", eid="E2"),
    ]
    assert validar(registro("pregunta", estado="abierta", eventos=ev), modo="canonico")


def _snap(*registros):
    return Snapshot({r["id"]: r for r in registros}, revision="r1")


def test_proyeccion_reglas_en_orden():
    T = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")
    acept = registro(
        "decision",
        estado="aceptada",
        eventos=[creacion("propuesta"), paso("propuesta", "aceptada", "2026-11-02T00:00:00Z")],
    )
    assert proyectar_status(acept, _snap(acept), **T) == "stable"
    assert proyectar_status({**acept, "clase": "archivo"}, _snap(acept), **T) == "deprecated"
    futura = registro(
        "decision",
        estado="aceptada",
        eventos=[creacion("propuesta"), paso("propuesta", "aceptada", "2026-11-02T00:00:00Z", "2026-12-01T00:00:00Z")],
    )
    assert proyectar_status(futura, _snap(futura), **T) == "draft"
    vencida = registro(
        "decision",
        estado="aceptada",
        eventos=[
            creacion("propuesta"),
            {**paso("propuesta", "aceptada", "2026-11-02T00:00:00Z"), "valido_hasta": "2026-11-10T00:00:00Z"},
        ],
    )
    assert proyectar_status(vencida, _snap(vencida), **T) == "stable"  # vencida no es futura (regla 3)

    def con_historial(tipo, *estados):
        ev = [creacion(estados[0])]
        for i, (a, b) in enumerate(zip(estados, estados[1:]), start=1):
            ev.append(paso(a, b, f"2026-11-0{i + 1}T00:00:00Z", eid=f"E{i}"))
        return registro(tipo, estado=estados[-1], eventos=ev)

    casos = [
        (con_historial("pregunta", "abierta"), "stable"),  # abierta es estable como registro
        (con_historial("hipotesis", "abierta"), "draft"),
        (con_historial("supuesto", "activo"), "draft"),
        (con_historial("hipotesis", "abierta", "refutada"), "deprecated"),
        (con_historial("rol", "propuesta", "activa"), "stable"),
        (con_historial("hito", "propuesto", "cancelado"), "deprecated"),
        (con_historial("sintesis", "borrador", "vigente"), "stable"),
    ]
    for r, esperado in casos:
        assert proyectar_status(r, _snap(r), **T) == esperado, (r["type"], r["estado"])


def test_sucesion_completa_vigente_deprecia():
    T = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")
    a = registro(
        "decision",
        id="DEC-A",
        estado="aceptada",
        eventos=[creacion("propuesta"), paso("propuesta", "aceptada", "2026-11-01T00:00:00Z")],
    )
    b = registro(
        "decision",
        id="DEC-B",
        estado="aceptada",
        deja_obsoleta=["DEC-A"],
        eventos=[creacion("propuesta"), paso("propuesta", "aceptada", "2026-11-02T00:00:00Z")],
    )
    assert proyectar_status(a, _snap(a, b), **T) == "deprecated"
    # Una sucesora solo propuesta no deprecia.
    bp = {**b, "estado": "propuesta", "eventos": [creacion("propuesta")]}
    assert proyectar_status(a, _snap(a, bp), **T) == "stable"
    # Una sucesora aceptada pero futura tampoco.
    bf = {
        **b,
        "eventos": [
            creacion("propuesta"),
            paso("propuesta", "aceptada", "2026-11-02T00:00:00Z", "2026-12-01T00:00:00Z"),
        ],
    }
    assert proyectar_status(a, _snap(a, bf), **T) == "stable"
    # Conocimiento anterior a la incorporación de la sucesora.
    assert (
        proyectar_status(a, _snap(a, b), valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-01T12:00:00Z")
        == "stable"
    )


def test_proyeccion_exige_cortes_explicitos():
    with pytest.raises(TypeError):
        proyectar_status(registro("pregunta"), _snap())
