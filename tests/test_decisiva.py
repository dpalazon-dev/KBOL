"""Modo de aprobación `decisiva`: solo lo decisivo pide aprobación; todo lleva su actor.

Elección local no conforme (docs/elecciones.md, «Mecanismos no conformes»): lo que no decide nada (una propuesta
nueva, una relación, empezar un hito, resolver una pregunta) entra sin aprobación, con el actor de la operación en
cada evento. Aceptar o rechazar una decisión, autorizar, cerrar o cancelar un plan o un hito, cambiar personas o
roles e importar una sustitución o un cierre siguen exigiendo la aprobación de quien decide.
"""

# ruff: noqa: F811  (el fixture entorno se importa de test_declarada)

import json

from conftest import registro
from test_declarada import ACEPTAR, aceptacion, dec_x, declarada, entorno  # noqa: F401
from test_integrar import proponer, solicitud

from kbol.core import parse, serializar
from kbol.declarada import VerificadorDeclarado
from kbol.integrar import ACTOR, es_decisivo, integrar

AGENTE = "claude-code/opus-5.5"


def llamar(repo, base, prop, recibos, revisiones=(), op="op-1", actor=AGENTE, aprobacion="decisiva"):
    return integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=list(revisiones),
        verificador=VerificadorDeclarado(repo.raiz),
        recibos=recibos,
        aprobacion=aprobacion,
        actor=actor,
    )


def pregunta():
    return registro("pregunta", id="Q-N", responsable="ROL-OP"), "Texto.\n"


def test_lo_no_decisivo_entra_sin_aprobacion_con_el_actor_en_cada_evento(entorno):
    repo, base, recibos = entorno
    r, c = pregunta()
    prop = proponer(repo, base, {"kb/Q-N.md": serializar(r, c)})
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "integrado", res
    assert res["decisivos"] == [] and res["actor"] == AGENTE and res["modo_aprobacion"] == "decisiva"
    meta, _ = parse(repo.git("show", "canon:kb/Q-N.md") + "\n")
    assert [e["tipo_evento"] for e in meta["eventos"]] == ["creacion"]
    assert meta["eventos"][0]["actor"] == AGENTE
    mensaje = repo.git("log", "-1", "--format=%B", "canon")
    assert f"Actor: {AGENTE}" in mensaje and "Aprobacion: decisiva" in mensaje


def test_aceptar_una_decision_sin_aprobacion_se_rechaza_tambien_en_modo_decisivo(entorno):
    repo, base, recibos = entorno
    res = llamar(repo, base, aceptacion(repo, base), recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE"
    assert repo.git("rev-parse", "canon") == base


def test_aceptar_con_la_aprobacion_de_quien_decide_integra_y_ratifica(entorno):
    repo, base, recibos = entorno
    res = llamar(repo, base, aceptacion(repo, base), recibos, [declarada(base)])
    assert res["estado"] == "integrado", res
    assert res["decisivos"] == ["DEC-X"]
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    tipos = [e["tipo_evento"] for e in meta["eventos"]]
    assert tipos == ["creacion", "ratificacion", "transicion"] and meta["estado"] == "aceptada"
    rat = meta["eventos"][1]
    assert rat["actor"] == AGENTE and rat["aprobacion"]["actor"] == "human:PER-H"


def test_una_operacion_mezclada_solo_ratifica_lo_decisivo(entorno):
    repo, base, recibos = entorno
    r, c = dec_x()
    q, cq = pregunta()
    archivos = {
        "kb/DEC-X.md": serializar(r, c),
        "kb/Q-N.md": serializar(q, cq),
        **solicitud("op-1", {"DEC-X": ACEPTAR}),
    }
    res = llamar(repo, base, proponer(repo, base, archivos), recibos, [declarada(base)])
    assert res["estado"] == "integrado", res
    assert res["decisivos"] == ["DEC-X"]
    meta, _ = parse(repo.git("show", "canon:kb/Q-N.md") + "\n")
    assert [e["tipo_evento"] for e in meta["eventos"]] == ["creacion"]


def test_el_modo_de_siempre_sigue_pidiendo_aprobacion_para_todo(entorno):
    repo, base, recibos = entorno
    r, c = pregunta()
    prop = proponer(repo, base, {"kb/Q-N.md": serializar(r, c)})
    res = llamar(repo, base, prop, recibos, aprobacion="toda", actor=ACTOR)
    assert res["estado"] == "bloqueado"


def test_actor_y_modo_invalidos_se_rechazan_sin_escribir(entorno):
    repo, base, recibos = entorno
    r, c = pregunta()
    prop = proponer(repo, base, {"kb/Q-N.md": serializar(r, c)})
    for kw in ({"actor": "alguien sin forma"}, {"actor": "x\ny/z"}, {"aprobacion": "ninguna"}):
        res = llamar(repo, base, prop, recibos, **kw)
        assert res["estado"] == "bloqueado", kw
    assert repo.git("rev-parse", "canon") == base


def test_que_es_decisivo():
    dec = {"type": "decision"}
    hito = {"type": "hito"}
    q = {"type": "pregunta"}
    assert es_decisivo("D", dec, {"D": [{"estado_nuevo": "aceptada"}]}, [], {})
    assert es_decisivo("H", hito, {"H": [{"estado_nuevo": "autorizado"}]}, [], {})
    assert not es_decisivo("H", hito, {"H": [{"estado_nuevo": "en_curso"}]}, [], {})
    assert not es_decisivo("Q", q, {"Q": [{"estado_nuevo": "resuelta"}]}, [], {})
    assert es_decisivo("P", {"type": "persona"}, {}, ["P"], {})
    assert es_decisivo("P", {"type": "persona"}, {"P": [{"estado_nuevo": "activa"}]}, [], {})
    assert es_decisivo("R", {"type": "rol"}, {"R": [{"estado_nuevo": "retirada"}]}, [], {})
    assert es_decisivo("HE", {"type": "hecho"}, {"HE": [{"estado_nuevo": "aceptada"}]}, [], {})
    assert es_decisivo("A", dec, {}, [], {"A": {"decisiva": ["el heredado declara a quién sustituye"]}})
    assert es_decisivo("A", {**dec, "deja_obsoleta": ["ADR-1"]}, {}, [], {"A": {}})
    assert not es_decisivo("A", {**dec, "afecta_a": ["ADR-1"]}, {}, [], {"A": {}})
    assert not es_decisivo("A", {**dec, "deja_obsoleta": ["ADR-1"]}, {}, [], {})


def test_la_solicitud_del_modo_decisivo_tiene_otra_huella_que_la_de_siempre(entorno):
    """Repetir la operación en otro modo no reutiliza su recibo: la huella incluye el modo y el actor."""
    repo, base, recibos = entorno
    r, c = pregunta()
    prop = proponer(repo, base, {"kb/Q-N.md": serializar(r, c)})
    primera = llamar(repo, base, prop, recibos)
    assert primera["estado"] == "integrado"
    otra = llamar(repo, base, prop, recibos, actor="process:otro")
    assert otra["estado"] == "bloqueado"
    assert json.loads((recibos / "op-1.json").read_text(encoding="utf-8"))["actor"] == AGENTE
