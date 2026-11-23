"""Arranque de la raíz de confianza: una sola vez, con la cuenta verificada, y después la integración normal (E4)."""

import json

import pytest
from conftest import CUERPO_DECISION, registro
from test_integrar import ACEPTAR, REVISION, Cliente, Repo, canonico, proponer, solicitud, verificador

from kbol.arranque import arrancar
from kbol.core import parse, serializar
from kbol.integrar import integrar
from kbol.schema import validar

ROL = dict(ambitos=["operaciones"], capacidades=["ratificar", "gobernar_politica"], regla_aprobacion="uno")


def persona(**cambios):
    datos = dict(
        id="PER-D",
        naturaleza="humana",
        identidad_ref="github:101",
        ocupa=[{"rol": "ROL-RAIZ", "desde": "2026-10-01T00:00:00Z"}],
    )
    return registro("persona", **{**datos, **cambios})


@pytest.fixture
def raiz(tmp_path):
    """Repositorio con la raíz propuesta (un rol que gobierna la política y la persona que lo ocupa)."""
    repo = Repo(tmp_path / "repo")
    repo.escribir("README.md", "x\n")
    repo.escribir("kb/ROL-RAIZ.md", serializar(registro("rol", id="ROL-RAIZ", **ROL), ""))
    repo.escribir("kb/PER-D.md", serializar(persona(), ""))
    base = repo.commit("raíz propuesta")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def cuenta(ident=101, login="david", tipo="User"):
    return Cliente({"/user": {"id": ident, "login": login, "type": tipo}})


def llamar(repo, base, recibos, op="arranque-1", cliente=None, **kw):
    argumentos = dict(
        rama="canon",
        carpeta="kb",
        base_esperada=base,
        persona="PER-D",
        roles=["ROL-RAIZ"],
        cliente=cliente or cuenta(),
        recibos=recibos,
        operacion_id=op,
    )
    argumentos.update(kw)
    return arrancar(repo.raiz, **argumentos)


def revisado_despues(ver, desde):
    """El verificador con la revisión fechada en el instante del arranque: antes, la persona aún no estaba activa."""
    for revision in ver.cliente.respuestas["/repos/o/r/pulls/1/reviews?per_page=100&page=1"]:
        revision["submitted_at"] = desde
    return ver


def leer(repo, ruta, rev="canon"):
    return parse(repo.git("show", f"{rev}:{ruta}") + "\n")


def test_arranque_valido_activa_la_raiz_con_eventos_admitidos(raiz):
    repo, base, recibos = raiz
    res = llamar(repo, base, recibos)
    assert res["estado"] == "arrancado", res
    canon = repo.git("rev-parse", "canon")
    assert res["revision_integrada"] == canon and repo.git("log", "-1", "--format=%P", "canon").split() == [base]
    mensaje = repo.git("log", "-1", "--format=%B", "canon")
    assert "Operacion-Id: arranque-1" in mensaje and "Arranque: github:101" in mensaje and f"Base: {base}" in mensaje
    for ruta in ("kb/ROL-RAIZ.md", "kb/PER-D.md"):
        meta, cuerpo = leer(repo, ruta)
        assert meta["estado"] == "activa"
        assert [e["tipo_evento"] for e in meta["eventos"]] == ["creacion", "transicion"]
        assert all(e["registrado_en"] for e in meta["eventos"])
        assert meta["eventos"][1]["evidencia_evento"]["mecanismo"] == "arranque-github-user"
        assert "github:101 (david)" in meta["eventos"][1]["evidencia_evento"]["comprobante"]
        assert validar(meta, cuerpo, modo="canonico") == []
    recibo = json.loads((recibos / "arranque-1.json").read_text(encoding="utf-8"))
    assert recibo["revision_integrada"] == canon and recibo["cuenta"] == {"id": 101, "login": "david"}
    assert recibo["registros"] == ["ROL-RAIZ", "PER-D"]


def test_despues_del_arranque_la_integracion_normal_acepta_con_esa_persona(raiz):
    repo, base, recibos = raiz
    arranque = llamar(repo, base, recibos)
    canon = arranque["revision_integrada"]
    r = registro("decision", id="DEC-X", autorizado_por=["ROL-RAIZ"])
    prop = proponer(
        repo, canon, {"kb/DEC-X.md": serializar(r, CUERPO_DECISION), **solicitud("op-1", {"DEC-X": ACEPTAR})}
    )
    res = integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id="op-1",
        base_esperada=canon,
        propuesta_rev=prop,
        revisiones=[REVISION],
        verificador=revisado_despues(verificador(prop, canon, user=101), arranque["registrado_en"]),
        recibos=recibos,
    )
    assert res["estado"] == "integrado", res
    meta, _ = leer(repo, "kb/DEC-X.md")
    assert meta["estado"] == "aceptada" and meta["eventos"][1]["aprobacion"]["actor"] == "human:PER-D"


def test_la_raiz_solo_se_arranca_una_vez(raiz):
    repo, base, recibos = raiz
    canon = llamar(repo, base, recibos)["revision_integrada"]
    res = llamar(repo, canon, recibos, op="arranque-2")
    assert res["estado"] == "bloqueado" and res["codigo"] == "RAIZ_YA_ESTABLECIDA"
    assert repo.git("rev-parse", "canon") == canon


@pytest.mark.parametrize(
    "cliente, codigo",
    [
        (cuenta(ident=202), "AUTORIDAD_INSUFICIENTE"),  # el token es de otra cuenta
        (cuenta(tipo="Bot"), "AUTORIDAD_INSUFICIENTE"),  # una cuenta que no es de una persona
        (Cliente({"/user": {"login": "david"}}), "AUTORIDAD_INSUFICIENTE"),  # sin id
    ],
)
def test_la_cuenta_verificada_debe_ser_la_de_la_persona(raiz, cliente, codigo):
    repo, base, recibos = raiz
    res = llamar(repo, base, recibos, cliente=cliente)
    assert res["estado"] == "bloqueado" and res["codigo"] == codigo
    assert repo.git("rev-parse", "canon") == base and not (recibos / "arranque-1.json").exists()


@pytest.mark.parametrize(
    "rol, per, motivo",
    [
        (dict(capacidades=["ratificar"]), {}, "gobierna la política"),
        ({}, dict(naturaleza="agente"), "humana"),
        ({}, dict(ocupa=[]), "no ocupa"),
        ({}, dict(ocupa=[{"rol": "ROL-RAIZ", "desde": "2099-01-01T00:00:00Z"}]), "no ocupa"),
    ],
)
def test_la_raiz_propuesta_ha_de_ser_coherente(tmp_path, rol, per, motivo):
    repo = Repo(tmp_path / "repo")
    repo.escribir("kb/ROL-RAIZ.md", serializar(registro("rol", id="ROL-RAIZ", **{**ROL, **rol}), ""))
    repo.escribir("kb/PER-D.md", serializar(persona(**per), ""))
    base = repo.commit("raíz")
    repo.git("branch", "canon")
    res = llamar(repo, base, tmp_path / "recibos")
    assert res["estado"] == "bloqueado" and motivo in res["motivo"], res
    assert repo.git("rev-parse", "canon") == base


def test_un_registro_de_la_raiz_con_historial_no_se_arranca(tmp_path):
    from test_integrar import activo

    repo = Repo(tmp_path / "repo")
    repo.escribir(
        "kb/ROL-RAIZ.md", canonico(activo("rol", "ROL-RAIZ", ambitos=["operaciones"], capacidades=["ratificar"]))
    )
    repo.escribir("kb/PER-D.md", serializar(persona(), ""))
    base = repo.commit("raíz")
    repo.git("branch", "canon")
    res = llamar(repo, base, tmp_path / "recibos")
    assert res["estado"] == "bloqueado" and "propuesta" in res["motivo"]


def test_base_cambiada_no_arranca(raiz):
    repo, base, recibos = raiz
    repo.git("checkout", "-q", "canon")
    repo.escribir("README.md", "y\n")
    otra = repo.commit("otro")
    repo.git("checkout", "-q", "main")
    res = llamar(repo, base, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "BASE_CAMBIADA"
    assert repo.git("rev-parse", "canon") == otra


def test_otros_registros_sin_historial_impiden_el_arranque(raiz):
    # Tras el arranque la integración carga la base en modo canónico: una propuesta escrita a mano la bloquearía.
    repo, base, recibos = raiz
    repo.git("checkout", "-q", "canon")
    repo.escribir(
        "kb/DEC-P.md", serializar(registro("decision", id="DEC-P", autorizado_por=["ROL-RAIZ"]), CUERPO_DECISION)
    )
    con_propuesta = repo.commit("propuesta escrita a mano")
    repo.git("checkout", "-q", "main")
    res = llamar(repo, con_propuesta, recibos)
    assert res["estado"] == "bloqueado" and "DEC-P" in res["motivo"]
    assert repo.git("rev-parse", "canon") == con_propuesta


def test_retirar_el_rol_raiz_no_permite_un_segundo_arranque(tmp_path):
    from conftest import evento
    from test_integrar import activo

    repo = Repo(tmp_path / "repo")
    rol = activo("rol", "ROL-RAIZ", **ROL)
    rol["eventos"].append(
        evento(
            evento_id="E2",
            estado_anterior="activa",
            estado_nuevo="retirada",
            registrado_en="2026-10-03T00:00:00Z",
            valido_desde="2026-10-03T00:00:00Z",
        )
    )
    rol["estado"] = "retirada"
    repo.escribir("kb/ROL-RAIZ.md", canonico(rol))
    # Alguien con permiso de escritura deja una raíz nueva propuesta, con otra cuenta.
    repo.escribir("kb/ROL-2.md", serializar(registro("rol", id="ROL-2", **ROL), ""))
    otra = persona(id="PER-X", identidad_ref="github:666", ocupa=[{"rol": "ROL-2", "desde": "2026-10-01T00:00:00Z"}])
    repo.escribir("kb/PER-X.md", serializar(otra, ""))
    base = repo.commit("raíz retirada y raíz nueva propuesta")
    repo.git("branch", "canon")
    res = llamar(repo, base, tmp_path / "r", persona="PER-X", roles=["ROL-2"], cliente=cuenta(ident=666))
    assert res["estado"] == "bloqueado" and res["codigo"] == "RAIZ_YA_ESTABLECIDA"


def test_no_deja_una_base_que_la_integracion_no_cargaria(raiz):
    from conftest import evento

    repo, base, recibos = raiz
    repo.git("checkout", "-q", "canon")
    # Un evento admitido, pero un estado escrito que su historial no materializa: pasa como propuesta, no como canónico.
    d = registro(
        "decision",
        id="DEC-L",
        autorizado_por=["ROL-RAIZ"],
        estado="aceptada",
        eventos=[evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")],
    )
    repo.escribir("kb/DEC-L.md", serializar(d, CUERPO_DECISION))
    base = repo.commit("decisión con historial incoherente")
    repo.git("checkout", "-q", "main")
    res = llamar(repo, base, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO" and "canónica" in res["motivo"]
    assert repo.git("rev-parse", "canon") == base and not (recibos / "arranque-1.json").exists()


def test_no_sobrescribe_un_recibo_ni_acepta_entradas_mal_formadas(raiz):
    repo, base, recibos = raiz
    recibos.mkdir()
    (recibos / "arranque-1.json").write_text("{}", encoding="utf-8")
    assert llamar(repo, base, recibos)["estado"] == "bloqueado"
    assert (recibos / "arranque-1.json").read_text(encoding="utf-8") == "{}"
    assert llamar(repo, base, recibos, op="arranque-2", roles="ROL-RAIZ")["estado"] == "bloqueado"
    assert repo.git("rev-parse", "canon") == base


def test_la_rama_cambia_durante_la_verificacion(raiz):
    repo, base, recibos = raiz

    class ClienteQueMueve:
        def get(self, ruta):
            repo.git("checkout", "-q", "canon")
            repo.escribir("README.md", "carrera\n")
            self.otra = repo.commit("escritura concurrente")
            repo.git("checkout", "-q", "main")
            return {"id": 101, "login": "david", "type": "User"}

    cliente = ClienteQueMueve()
    res = llamar(repo, base, recibos, cliente=cliente)
    assert res["codigo"] == "BASE_CAMBIADA" and repo.git("rev-parse", "canon") == cliente.otra
    assert not (recibos / "arranque-1.json").exists()


def test_tras_el_arranque_nadie_se_da_la_identidad_de_la_raiz(raiz):
    # La propuesta cambia la cuenta de la persona raíz a github:555 y aprueba esa cuenta: con la política de la
    # propuesta pasaría; con la de la base, que es la que vale, github:555 no es nadie.
    repo, base, recibos = raiz
    arranque = llamar(repo, base, recibos)
    canon = arranque["revision_integrada"]
    meta, cuerpo = leer(repo, "kb/PER-D.md")
    prop = proponer(repo, canon, {"kb/PER-D.md": canonico({**meta, "identidad_ref": "github:555"}, cuerpo)})
    res = integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id="op-1",
        base_esperada=canon,
        propuesta_rev=prop,
        revisiones=[REVISION],
        verificador=revisado_despues(verificador(prop, canon, user=555), arranque["registrado_en"]),
        recibos=recibos,
    )
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res
    [revision] = res["autoridad"]["revisiones"]
    assert "github:555 no corresponde a una única persona activa en la política base" in revision["motivo"]
    assert repo.git("log", "-1", "--format=%ae", arranque["revision_integrada"]) == "arranque@localhost"
