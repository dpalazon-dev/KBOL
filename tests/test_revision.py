"""Regresiones de la revisión independiente del 3 nov 2026 (hallazgos HIGH, MEDIUM y LOW)."""

import re

import pytest
from conftest import CUERPO_DECISION, POR_TIPO, evento, registro

from kbol.core import ErrorDeFormato, escribir, nuevo_id, parse, serializar
from kbol.digest import digest
from kbol.eventos import rige_en
from kbol.markdown import hechos
from kbol.modelo import ID_UUID
from kbol.proyeccion import Snapshot, proyectar, proyectar_status
from kbol.referencias import validar_snapshot
from kbol.schema import validar

T = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")


def creacion(estado, t="2026-11-01T00:00:00Z"):
    return evento(
        "creacion", evento_id="E0", estado_anterior=None, estado_nuevo=estado, registrado_en=t, valido_desde=t
    )


def ratificacion(t="2026-11-02T00:00:00Z"):
    aprob = dict(
        aprobacion_id="AP1",
        actor="human:david",
        identidad_ref="github:1",
        roles=["ROL-EJEMPLO"],
        digest="b" * 64,
        revision_base="r0",
        aprobada_en=t,
        politica_revision="r0",
        comprobante="review:1",
    )
    return evento("ratificacion", evento_id="E1", registrado_en=t, valido_desde=t, aprobacion=aprob)


def aceptacion(t="2026-11-02T00:00:00Z", valido=None, **extra):
    return evento(
        evento_id="E2",
        estado_anterior="propuesta",
        estado_nuevo="aceptada",
        registrado_en=t,
        valido_desde=valido or t,
        **extra,
    )


def aceptada(**cambios):
    return registro(
        "decision", estado="aceptada", eventos=[creacion("propuesta"), ratificacion(), aceptacion()], **cambios
    )


@pytest.mark.parametrize(
    "campo,valor",
    [("description", "una línea\n"), ("id", "Q-A\n"), ("autor", "human:x\n"), ("responsable", "ROL-EJEMPLO\n")],
)
def test_patrones_no_admiten_salto_final(campo, valor):
    assert validar(registro("pregunta", **{campo: valor}))


def test_instantes_y_huellas_no_admiten_salto_final():
    ev = creacion("abierta")
    assert validar(registro("pregunta", eventos=[{**ev, "registrado_en": ev["registrado_en"] + "\n"}]))
    assert validar(registro("fuente", sha256="a" * 64 + "\n"))


def test_canonico_exige_historial_desde_creacion():
    assert validar(registro("decision", estado="aceptada"), CUERPO_DECISION, modo="canonico")
    assert validar(registro("decision", eventos=[ratificacion()]), CUERPO_DECISION, modo="canonico")
    assert validar(aceptada(), CUERPO_DECISION, modo="canonico") == []


def test_aceptar_una_decision_exige_ratificacion_previa():
    sin = registro("decision", estado="aceptada", eventos=[creacion("propuesta"), aceptacion()])
    assert validar(sin, CUERPO_DECISION, modo="canonico")


def test_propuesta_nueva_esta_en_estado_inicial():
    assert validar(registro("decision", estado="aceptada"), CUERPO_DECISION)


def test_canonico_no_admite_eventos_locales():
    local = {**creacion("abierta"), "registrado_en": None}
    assert validar(registro("pregunta", eventos=[local]), modo="canonico")
    assert validar(registro("pregunta", eventos=[local])) == []


def test_serializar_canonico_exige_historial():
    with pytest.raises(ErrorDeFormato):
        serializar(registro("decision", estado="aceptada"), CUERPO_DECISION, modo="canonico")
    assert serializar(aceptada(), CUERPO_DECISION, modo="canonico")


def test_sin_historial_no_hay_proyeccion_ni_sucesion():
    a = aceptada(id="DEC-A")
    b_sin = registro("decision", id="DEC-B", estado="aceptada", deja_obsoleta=["DEC-A"])
    snap = Snapshot({"DEC-A": a, "DEC-B": b_sin}, revision="r1")
    assert proyectar_status(a, snap, **T) == "stable"
    assert proyectar_status(b_sin, snap, **T) is None
    assert proyectar(b_sin, snap, **T)["advertencias"]


def test_eventos_locales_se_ignoran_al_proyectar():
    local = {**creacion("abierta"), "registrado_en": None}
    r = registro("pregunta", eventos=[local])
    assert proyectar_status(r, Snapshot({}, "r"), **T) is None


def test_ambiguedad_de_dia_no_rompe_la_proyeccion():
    imp = evento(
        "importacion",
        evento_id="E0",
        estado_anterior=None,
        estado_nuevo="aceptada",
        estado_heredado="Aceptada",
        procedencia={"ruta": "docs/x.md", "revision": "r"},
        valido_desde="2026-11-20",
        precision="dia",
    )
    r = registro("decision", estado="aceptada", eventos=[imp])
    p = proyectar(r, Snapshot({}, "r"), **T)
    assert p["status"] == "draft" and any("TIEMPO_AMBIGUO" in a for a in p["advertencias"])


def test_ambiguedad_de_dia_depende_de_la_zona_desconocida():
    with pytest.raises(ValueError, match="ambigua"):
        rige_en("2026-11-15", None, "2026-11-15T00:30:00+01:00")
    with pytest.raises(ValueError, match="ambigua"):
        rige_en("2026-11-15", None, "2026-11-14T23:30:00-05:00")
    assert rige_en("2026-11-15", None, "2026-11-17T00:00:00Z") is True
    assert rige_en("2026-11-15", None, "2026-11-13T00:00:00Z") is False


def test_decimales_enteros_rechazados_en_cualquier_campo():
    v = POR_TIPO["hito"]["verificaciones"][0]
    assert validar(registro("hito", verificaciones=[{**v, "timeout": 600.0}]))
    assert validar(registro("rol", regla_aprobacion={"quorum": 2.0}))


def test_codigo_en_linea_no_cruza_parrafos():
    cuerpo = 'Pulsa ` para abrir.\n\n<hecho id="H1" evidencia="inventada" fuente="nada">5</hecho>\n\nY ` otra vez.'
    assert hechos(cuerpo)
    assert validar(registro("pregunta"), cuerpo)


def test_digest_valida_efectos():
    r = registro("decision")
    with pytest.raises(ValueError):
        digest(r, CUERPO_DECISION, {"cualquier": "cosa"})
    efecto = {"estado_nuevo": "aceptada", "valido_desde": "2026-11-01T00:00:00Z", "registrado_en": "x"}
    with pytest.raises(ValueError):
        digest(r, CUERPO_DECISION, [efecto])


def test_etiqueta_no_especifica_rechazada():
    with pytest.raises(ErrorDeFormato):
        parse("---\na: ! 123\n---\n")


def test_yaml_1_1_desde_texto():
    meta, _ = parse("---\nalias: [no, yes]\n---\n")
    assert validar(registro("entidad", alias=meta["alias"]))


def test_intervalos_ordenados():
    hecho = registro("hecho")
    del hecho["fecha"]
    hecho["intervalo"] = {"desde": "2026-11-02", "hasta": "2026-11-01"}
    assert validar(hecho)
    mal = aceptacion(valido="2026-12-01T00:00:00Z", valido_hasta="2026-11-01T00:00:00Z")
    r = registro("decision", estado="aceptada", eventos=[creacion("propuesta"), ratificacion(), mal])
    assert validar(r, CUERPO_DECISION)


def test_referencias_adicionales_y_cobertura_de_anclas():
    rol = registro("rol")
    sin = registro("sintesis", dependencias=["DEC-NADA#C1"])
    snap = Snapshot({"ROL-EJEMPLO": rol, "SIN-A": sin}, "r")
    assert "REFERENCIA_AUSENTE" in {h["codigo"] for h in validar_snapshot(snap)}
    fuente = registro("pregunta", sources=[{"id": "s1", "resource": "F-NADA"}])
    assert validar_snapshot(Snapshot({"ROL-EJEMPLO": rol, "Q-A": fuente}, "r"))
    dec = registro("decision")
    q = registro("pregunta", cuestiona=["DEC-EJEMPLO#C99"])
    h = validar_snapshot(Snapshot({"ROL-EJEMPLO": rol, "DEC-EJEMPLO": dec, "Q-A": q}, "r"))
    assert [x["severidad"] for x in h] == ["aviso"]  # cuerpo no cargado: no se pudo comprobar
    assert validar(registro("pregunta"), '<hecho ref="ZZ-1">x</hecho>')


def test_sustitucion_mutua_es_ciclo():
    rol = registro("rol")
    a = registro("decision", id="DEC-A", modifica=[{"destino": "DEC-B#C1", "tipo": "sustitucion", "por": "DEC-A#C1"}])
    b = registro("decision", id="DEC-B", modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}])
    cuerpos = {"DEC-A": CUERPO_DECISION, "DEC-B": CUERPO_DECISION}
    snap = Snapshot({"ROL-EJEMPLO": rol, "DEC-A": a, "DEC-B": b}, "r", cuerpos)
    assert "CONFLICTO_NORMATIVO" in {h["codigo"] for h in validar_snapshot(snap)}


def test_nuevo_id_y_escritura_atomica(tmp_path):
    ident = nuevo_id("decision")
    assert re.fullmatch(ID_UUID, ident)
    f = tmp_path / "d.md"
    escribir(f, registro("decision", id=ident), CUERPO_DECISION.replace("DEC-EJEMPLO", ident))
    meta, cuerpo = parse(f.read_text(encoding="utf-8"))
    assert meta["id"] == ident and cuerpo == CUERPO_DECISION
    assert list(tmp_path.iterdir()) == [f]
    with pytest.raises(ErrorDeFormato):
        escribir(tmp_path / "e.md", registro("decision", extra=1), CUERPO_DECISION)
    assert list(tmp_path.iterdir()) == [f]
