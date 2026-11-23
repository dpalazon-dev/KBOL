"""VAL-01: esquema común, por tipo, anidado y por clase de evento."""

import pytest
from conftest import CUERPO_DECISION, POR_TIPO, T0, evento, registro

from kbol.schema import validar


def codigos(hallazgos):
    return {h["codigo"] for h in hallazgos}


def rutas(hallazgos):
    return {h["ruta"] for h in hallazgos}


@pytest.mark.parametrize("tipo", sorted(POR_TIPO))
def test_registro_minimo_valido_por_tipo(tipo):
    cuerpo = CUERPO_DECISION if tipo == "decision" else ""
    assert validar(registro(tipo), cuerpo) == []


def test_ejemplo_del_contrato_valida_como_propuesta():
    # «Ejemplo completo de propuesta de decisión», KB-DPP núcleo 0.7.
    r = registro("decision", title="Calendario de entrega del informe")
    cuerpo = '<clausula id="C1">\nEl informe se entrega los martes.\n</clausula>\n\n<clausula id="C2">\nEl informe solo incluye datos verificados.\n</clausula>\n'
    assert validar(r, cuerpo) == []


@pytest.mark.parametrize(
    "campo", ["id", "type", "clase", "title", "description", "ambito", "estado", "autor", "eventos", "sources"]
)
def test_comunes_obligatorios(campo):
    r = registro("pregunta")
    del r[campo]
    assert "ESQUEMA_INVALIDO" in codigos(validar(r))


@pytest.mark.parametrize(
    "cambio",
    [
        {"description": "dos\nlíneas"},
        {"clase": "otra"},
        {"estado": "aceptada"},  # no es estado de pregunta
        {"autor": "David"},  # actor sin forma human:/process:/productor/versión
        {"sources": [{"id": "s1"}]},
        {"sources": [{"id": "s1", "resource": "F-A", "extra": 1}]},
        {"sources": [{"id": "s1", "resource": "F-A"}, {"id": "s1", "resource": "F-B"}]},
        {"sources": [{"id": "s1", "resource": "F-A", "hash": "corto"}]},
        {"responsable": ["ROL-A"]},
        {"subtipo": "otra"},
        {"plazo": "mañana"},
        {"id": "DEC-A"},  # prefijo de otro tipo
        {"id": "sin-prefijo"},
    ],
)
def test_valores_incorrectos_rechazados(cambio):
    assert validar(registro("pregunta", **cambio))


def test_campo_desconocido_bloquea_en_canonico_y_avisa_en_intercambio():
    r = registro("pregunta", extra="x")
    assert codigos(validar(r, modo="canonico")) == {"ESQUEMA_INVALIDO"}
    avisos = validar(r, modo="intercambio")
    assert avisos and all(h["severidad"] == "aviso" for h in avisos)


def test_campo_de_otro_tipo_es_desconocido():
    # resuelta_por solo sale de una pregunta; modifica, de una decisión.
    assert validar(registro("hecho", resuelta_por=["DEC-A"]))
    assert validar(registro("pregunta", modifica=[]))


def test_yaml_1_1_no_cuela_booleanos_por_texto():
    # «no» leído por PyYAML es False: el esquema lo rechaza en lugar de aceptarlo como alias.
    assert validar(registro("entidad", alias=[False]))


def test_enteros_exactos_y_sin_decimales():
    v = POR_TIPO["hito"]["verificaciones"][0]
    assert validar(registro("hito", verificaciones=[{**v, "timeout": 1.5}]))
    assert validar(registro("hito", verificaciones=[{**v, "timeout": True}]))


def test_fuente_original_y_derivada():
    assert validar(registro("fuente", sha256="A" * 64))
    assert validar(registro("fuente", subtipo="derivada"))
    derivada = registro(
        "fuente",
        id="F-AR",
        subtipo="derivada",
        derivada_de=["F-A"],
        procesador="docling",
        version_procesador="2.1.0",
        configuracion_ref="perfil:tablas",
        procesado_en="2026-11-02T10:00:00+01:00",
        procesamiento="parcial",
        calidad={
            "tablas": {"metodo": "muestra", "resultado": "parcial", "limites": "columna 3"},
            "figuras": "no_evaluado",
        },
    )
    del derivada["origen"]
    assert validar(derivada) == []
    assert validar({**derivada, "procesamiento": "terminado"})
    assert validar({**derivada, "calidad": {"tablas": {"resultado": 0}}})


def test_decision_sin_alternativas_exige_motivo_y_seleccion():
    assert validar(registro("decision", alternativas=[]), CUERPO_DECISION)
    assert (
        validar(registro("decision", alternativas=[], sin_alternativas_motivo="Corrección demostrada"), CUERPO_DECISION)
        == []
    )
    alts = [dict(a, seleccionada=False) for a in POR_TIPO["decision"]["alternativas"]]
    assert validar(registro("decision", alternativas=alts), CUERPO_DECISION)
    assert validar(registro("decision", autorizado_por=[]), CUERPO_DECISION)


def test_decision_canonica_necesita_clausulas_y_cuerpo_bien_formado():
    assert validar(registro("decision"), "texto libre", modo="canonico")
    assert validar(registro("decision"), '<clausula id="C1">\nabierta', modo="intercambio")


def test_relaciones_tipadas():
    r = registro("decision")
    ok = [{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-EJEMPLO#C1"}]
    assert validar({**r, "modifica": ok}, CUERPO_DECISION) == []
    for malo in (
        [{"destino": "DEC-A#C1", "tipo": "sustitucion"}],
        [{"destino": "DEC-A#C1", "tipo": "derogacion", "por": "DEC-EJEMPLO#C1"}],
        [{"destino": "DEC-A", "tipo": "sustitucion", "por": "DEC-EJEMPLO#C1"}],  # sustitución exige ancla
        [{"destino": "DEC-A#C1", "tipo": "otra", "por": "DEC-EJEMPLO#C1"}],
    ):
        assert validar({**r, "modifica": malo}, CUERPO_DECISION), malo
    assert (
        validar(
            {
                **r,
                "modifica": [
                    {"destino": "DEC-A", "tipo": "adicion", "por": "DEC-EJEMPLO#C1", "posicion": "tras DEC-A#C2"}
                ],
            },
            CUERPO_DECISION,
        )
        == []
    )
    assert validar(registro("hito", depende_de=[{"destino": "HI-B", "condicion": "completado_con_evidencia"}])) == []
    assert validar(registro("hito", depende_de=[{"destino": "HI-B", "condicion": "existe"}]))
    assert validar(registro("hito", depende_de=["HI-B"]))
    assert validar(registro("pregunta", cuestiona=["DEC-A"]))  # cuestiona apunta a una cláusula
    assert validar(registro("pregunta", cuestiona=["DEC-A#C1"])) == []
    assert validar(registro("pregunta", resuelta_por=["Q-B"]))  # resuelve una decisión
    assert (
        validar(
            registro(
                "decision",
                veta=[{"patron": "tenant", "ambito": "producto", "uso": "contenido operativo", "exclusiones": []}],
            ),
            CUERPO_DECISION,
        )
        == []
    )


def test_rol_regla_de_aprobacion():
    for ok in ("uno", "todos", {"quorum": 2}):
        assert validar(registro("rol", regla_aprobacion=ok)) == []
    for malo in ("mayoria", {"quorum": 0}, {"quorum": "2"}):
        assert validar(registro("rol", regla_aprobacion=malo))


def test_hito_aceptacion_y_verificaciones():
    k = POR_TIPO["hito"]["aceptacion"][0]
    v = POR_TIPO["hito"]["verificaciones"][0]
    assert validar(registro("hito", verificaciones=[{**v, "criterio_id": "K9"}]))  # criterio inexistente
    assert validar(registro("hito", aceptacion=[{**k, "metodo": "evaluacion_ia_asistida"}]))  # sin rúbrica
    ia = {**k, "metodo": "evaluacion_ia_asistida", "rubrica": "R", "resolucion_desacuerdo": "Decide David"}
    assert validar(registro("hito", aceptacion=[ia])) == []
    assert validar(registro("hito", tolerancias={"velocidad": "alta"}))


def test_eventos_por_clase():
    t = evento(estado_anterior=None, estado_nuevo="abierta", tipo_evento="creacion")
    assert validar(registro("pregunta", eventos=[t])) == []
    assert validar(registro("pregunta", eventos=[{**t, "extra": 1}]))
    assert validar(registro("pregunta", eventos=[{**t, "registrado_en": "nonsense"}]))
    assert validar(registro("pregunta", eventos=[{**t, "registrado_en": "2026-11-03T10:00:00"}]))  # sin zona
    assert validar(registro("pregunta", eventos=[{**t, "evidencia_evento": "texto"}]))
    aprob = dict(
        aprobacion_id="AP1",
        actor="human:david",
        identidad_ref="github:1",
        roles=["ROL-EJEMPLO"],
        digest="b" * 64,
        revision_base="23fef059",
        aprobada_en=T0,
        politica_revision="23fef059",
        comprobante={"mecanismo": "github-review", "id": "1"},
    )
    rat = evento("ratificacion", evento_id="E2", aprobacion=aprob)
    assert validar(registro("decision", eventos=[rat]), CUERPO_DECISION) == []
    assert validar(registro("decision", eventos=[{**rat, "aprobacion": {**aprob, "digest": "x"}}]), CUERPO_DECISION)


def test_eventos_con_id_repetido():
    t = evento("creacion", estado_anterior=None, estado_nuevo="abierta")
    assert validar(registro("pregunta", eventos=[t, t]))


def test_hecho_exige_fecha_o_intervalo_con_precision():
    r = registro("hecho")
    del r["fecha"]
    assert validar(r)
    assert validar({**r, "intervalo": {"desde": "2026-10-01"}, "precision": "dia"}) == []
    assert validar({**r, "fecha": "2026-10-30", "precision": "segundos"})


def test_marcas_de_hecho_en_cuerpo_validadas():
    r = registro("decision", sources=[{"id": "s1", "resource": "F-A"}])
    cuerpo = CUERPO_DECISION + '\n<hecho id="H1" evidencia="declarado" fuente="s1">Caudal 5 m3/h</hecho>\n'
    assert validar(r, cuerpo) == []
    assert validar(r, cuerpo.replace('fuente="s1"', 'fuente="s9"'))
    assert validar(r, cuerpo.replace("declarado", "certero"))
