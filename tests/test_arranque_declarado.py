"""Arranque declarado de la raíz: la persona declara que es la raíz y el agente cita sus palabras.

Mismas garantías que el arranque con GitHub salvo una: nadie verifica la identidad. El comprobante lo dice, y la raíz
queda establecida igual, de modo que no hay un segundo arranque por ningún canal.
"""

import json

import pytest
from conftest import CUERPO_DECISION, registro
from test_arranque import ROL, cuenta, leer
from test_integrar import ACEPTAR, Repo, proponer, solicitud

from kbol.arranque import MECANISMO_DECLARADO, arrancar
from kbol.core import serializar
from kbol.declarada import MECANISMO, VerificadorDeclarado
from kbol.digest import digest
from kbol.integrar import integrar
from kbol.schema import validar

CITA = "Soy David y arranco la raíz de la instalación"


@pytest.fixture
def raiz(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.escribir("README.md", "x\n")
    repo.escribir("kb/ROL-RAIZ.md", serializar(registro("rol", id="ROL-RAIZ", **ROL), ""))
    persona = registro(
        "persona",
        id="PER-D",
        naturaleza="humana",
        identidad_ref="declarada:d",
        ocupa=[{"rol": "ROL-RAIZ", "desde": "2026-10-01T00:00:00Z"}],
    )
    repo.escribir("kb/PER-D.md", serializar(persona, ""))
    base = repo.commit("raíz propuesta")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def declaracion(**cambios):
    datos = {"identidad": "declarada:d", "sesion": "sesión kbol-e9", "instante": "2026-11-05T19:00:00Z", "cita": CITA}
    return {**datos, **cambios}


def llamar(repo, base, recibos, op="arranque-1", **kw):
    argumentos = dict(
        rama="canon",
        carpeta="kb",
        base_esperada=base,
        persona="PER-D",
        roles=["ROL-RAIZ"],
        declaracion=declaracion(),
        recibos=recibos,
        operacion_id=op,
    )
    argumentos.update(kw)
    return arrancar(repo.raiz, **argumentos)


def test_arranque_declarado_activa_la_raiz_y_dice_que_no_esta_autenticado(raiz):
    repo, base, recibos = raiz
    res = llamar(repo, base, recibos)
    assert res["estado"] == "arrancado", res
    for ruta in ("kb/ROL-RAIZ.md", "kb/PER-D.md"):
        meta, cuerpo = leer(repo, ruta)
        assert meta["estado"] == "activa" and validar(meta, cuerpo, modo="canonico") == []
        evidencia = meta["eventos"][1]["evidencia_evento"]
        assert evidencia["mecanismo"] == MECANISMO_DECLARADO
        assert CITA in evidencia["comprobante"] and "sin autenticar" in evidencia["comprobante"]
    recibo = json.loads((recibos / "arranque-1.json").read_text(encoding="utf-8"))
    assert recibo["cuenta"]["identidad"] == "declarada:d" and recibo["cuenta"]["autenticada"] is False
    assert recibo["cuenta"]["cita"] == CITA
    assert "Arranque: declarada:d" in repo.git("log", "-1", "--format=%B", "canon")


def test_la_identidad_declarada_tiene_que_ser_la_de_la_persona(raiz):
    repo, base, recibos = raiz
    res = llamar(repo, base, recibos, declaracion=declaracion(identidad="declarada:otro"))
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize(
    "cambio",
    [{"identidad": "d"}, {"cita": " "}, {"sesion": ""}, {"instante": "2026-11-05"}, {"otro": "campo"}],
)
def test_una_declaracion_mal_formada_no_arranca(raiz, cambio):
    repo, base, recibos = raiz
    res = llamar(repo, base, recibos, declaracion=declaracion(**cambio))
    assert res["estado"] == "bloqueado", res
    assert repo.git("rev-parse", "canon") == base


def test_un_canal_y_solo_uno(raiz):
    repo, base, recibos = raiz
    ambos = llamar(repo, base, recibos, cliente=cuenta())
    ninguno = llamar(repo, base, recibos, declaracion=None)
    assert ambos["estado"] == ninguno["estado"] == "bloqueado"
    assert repo.git("rev-parse", "canon") == base


def test_tras_el_arranque_declarado_no_hay_otro_arranque_por_ningun_canal(raiz):
    repo, base, recibos = raiz
    canon = llamar(repo, base, recibos)["revision_integrada"]
    otro = llamar(repo, canon, recibos, op="arranque-2")
    github = llamar(repo, canon, recibos, op="arranque-3", declaracion=None, cliente=cuenta())
    assert otro["codigo"] == github["codigo"] == "RAIZ_YA_ESTABLECIDA"
    assert repo.git("rev-parse", "canon") == canon


def test_despues_la_integracion_acepta_con_una_aprobacion_declarada_de_la_raiz(raiz):
    repo, base, recibos = raiz
    arranque = llamar(repo, base, recibos)
    canon = arranque["revision_integrada"]
    r = registro("decision", id="DEC-X", autorizado_por=["ROL-RAIZ"])
    prop = proponer(
        repo, canon, {"kb/DEC-X.md": serializar(r, CUERPO_DECISION), **solicitud("op-1", {"DEC-X": ACEPTAR})}
    )
    aprobacion = {
        "mecanismo": MECANISMO,
        "identidad": "declarada:d",
        "sesion": "sesión kbol-e9",
        "instante": arranque["registrado_en"],
        "cita": "Acepto DEC-X",
        "base_mostrada": canon,
        "digests": {"DEC-X": digest(r, CUERPO_DECISION, ACEPTAR)},
    }
    res = integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id="op-1",
        base_esperada=canon,
        propuesta_rev=prop,
        revisiones=[aprobacion],
        verificador=VerificadorDeclarado(repo.raiz),
        recibos=recibos,
    )
    assert res["estado"] == "integrado", res
    meta, _ = leer(repo, "kb/DEC-X.md")
    assert meta["estado"] == "aceptada"
