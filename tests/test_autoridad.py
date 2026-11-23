"""VAL-04 y ESC-03: la aprobación vale por identidad verificada, autoridad previa y el diff exacto revisado."""

import copy

import pytest
from conftest import CUERPO_DECISION, evento, registro

from kbol.autoridad import evaluar
from kbol.digest import digest
from kbol.github import ClienteGitHub, ErrorDeVerificacion, VerificadorGitHub
from kbol.proyeccion import Snapshot

EFECTOS = [{"estado_anterior": "propuesta", "estado_nuevo": "aceptada", "valido_desde": "2026-11-05T00:00:00Z"}]
REV, BASE = "c" * 40, "b" * 40
REVISION = {"mecanismo": "github-review", "pull": 1, "review_id": 11}


def activo(tipo, ident, **campos):
    ev = [
        evento(
            "creacion",
            evento_id="E0",
            estado_anterior=None,
            estado_nuevo="propuesta",
            registrado_en="2026-10-01T00:00:00Z",
            valido_desde="2026-10-01T00:00:00Z",
        ),
        evento(
            evento_id="E1",
            estado_anterior="propuesta",
            estado_nuevo="activa",
            registrado_en="2026-10-02T00:00:00Z",
            valido_desde="2026-10-02T00:00:00Z",
        ),
    ]
    return registro(tipo, id=ident, estado="activa", eventos=ev, **campos)


def humana(ident="PER-H", cuenta=101, roles=("ROL-OP",), hasta=None):
    ocupa = [{"rol": r, "desde": "2026-10-02T00:00:00Z", **({"hasta": hasta} if hasta else {})} for r in roles]
    return activo("persona", ident, naturaleza="humana", identidad_ref=f"github:{cuenta}", ocupa=ocupa)


def politica(*extra):
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    agente = activo("persona", "PER-AG", naturaleza="agente", identidad_ref="github:900", ocupa=[])
    regs = {r["id"]: r for r in (rol, humana(), agente)}
    regs.update({r["id"]: r for r in extra})
    return Snapshot(regs, "base1")


def propuesta(**cambios):
    return registro("decision", id="DEC-X", autorizado_por=["ROL-OP"], **cambios)


class Cliente(ClienteGitHub):
    """Sustituye solo la llamada HTTP: el resto del verificador es el real."""

    def __init__(self, respuestas):
        super().__init__(token="t")
        self.respuestas = respuestas
        self.llamadas = []

    def get(self, ruta):
        self.llamadas.append(ruta)
        return copy.deepcopy(self.respuestas[ruta])


def respuestas_github(revisiones, head, base, ref="main", cronologia=()):
    """Respuestas de la API para la PR 1: la PR, sus revisiones en orden y su cronología."""
    return {
        "/repos/o/r/pulls/1": {"head": {"sha": head}, "base": {"sha": base, "ref": ref}},
        "/repos/o/r/pulls/1/reviews?per_page=100&page=1": [{"id": k, **v} for k, v in revisiones.items()],
        "/repos/o/r/issues/1/timeline?per_page=100&page=1": list(cronologia),
    }


def verificador(revisiones=None, head=REV, base=BASE, **kw):
    cliente = Cliente(respuestas_github(revisiones or {11: review()}, head, base, **kw))
    return VerificadorGitHub(cliente, "o/r", "main")


def review(user=101, estado="APPROVED", commit=REV, cuando="2026-11-04T10:00:00Z"):
    return {"user": {"id": user}, "state": estado, "commit_id": commit, "submitted_at": cuando}


def evaluar_x(r=None, cuerpo=CUERPO_DECISION, efectos=EFECTOS, revisiones=(REVISION,), pol=None, ver=None, **kw):
    r = r or propuesta()
    return evaluar(r, cuerpo, efectos, list(revisiones), pol or politica(), ver or verificador(), REV, BASE, **kw)


def test_esc03_1_verified_escrito_por_el_agente_no_es_aprobacion():
    r = propuesta(verified=[{"by": "human:david", "at": "2026-11-04T10:00:00Z", "digest": "a" * 64}])
    res = evaluar_x(r, revisiones=[])
    assert res["autorizado"] is False and res["codigo"] == "AUTORIDAD_INSUFICIENTE"


def test_esc03_2_aprobacion_por_canal_confiable_con_datos_verificados():
    res = evaluar_x()
    assert res["autorizado"] is True and res["codigo"] is None
    (ap,) = res["aprobaciones"]
    assert ap == {
        "aprobacion_id": "github-review:o/r#1/11",
        "actor": "human:PER-H",
        "identidad_ref": "github:101",
        "roles": ["ROL-OP"],
        "digest": digest(propuesta(), CUERPO_DECISION, EFECTOS),
        "revision_base": BASE,
        "aprobada_en": "2026-11-04T10:00:00Z",
        "politica_revision": "base1",
        "comprobante": {"mecanismo": "github-review", "repositorio": "o/r", "pull": 1, "review_id": 11},
    }


@pytest.mark.parametrize("ver", [dict(head="d" * 40), dict(revisiones={11: review(commit="d" * 40)})])
def test_esc03_3_contenido_cambiado_tras_revisar_caduca(ver):
    res = evaluar_x(ver=verificador(**ver))
    assert res["autorizado"] is False and res["codigo"] == "APROBACION_CADUCADA"


def test_la_pr_debe_comparar_con_la_base_esperada():
    res = evaluar_x(ver=verificador(base="e" * 40))
    assert res["autorizado"] is False and res["codigo"] == "AUTORIDAD_INSUFICIENTE"


def test_esc03_4_un_agente_no_ratifica():
    res = evaluar_x(ver=verificador({11: review(user=900)}))
    assert res["autorizado"] is False
    agente = activo(
        "persona",
        "PER-AG",
        naturaleza="agente",
        identidad_ref="github:900",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    res = evaluar_x(pol=politica(agente), ver=verificador({11: review(user=900)}))
    assert res["autorizado"] is False and res["revisiones"][0]["motivo"] == "un agente no ratifica"


def test_cuenta_sin_persona_en_la_politica():
    assert evaluar_x(ver=verificador({11: review(user=555)}))["autorizado"] is False


@pytest.mark.parametrize("estado", ["CHANGES_REQUESTED", "DISMISSED", "COMMENTED"])
def test_revision_no_aprobatoria(estado):
    assert evaluar_x(ver=verificador({11: review(estado=estado)}))["autorizado"] is False


def test_revision_sin_instante_valido():
    assert evaluar_x(ver=verificador({11: review(cuando=None)}))["autorizado"] is False
    assert evaluar_x(ver=verificador({11: review(cuando="ayer")}))["autorizado"] is False


def test_rol_fuera_de_ambito_y_ocupacion_vencida():
    assert evaluar_x(propuesta(ambito="finanzas"))["autorizado"] is False
    vencida = humana(hasta="2026-11-01T00:00:00Z")
    assert evaluar_x(pol=politica(vencida))["autorizado"] is False


def test_revocacion_entre_la_revision_y_la_integracion():
    # Ocupaba el rol al revisar (10:00) pero ya no al integrar (13:00): se revalida al integrar.
    vence = humana(hasta="2026-11-04T12:00:00Z")
    assert evaluar_x(pol=politica(vence))["autorizado"] is True
    res = evaluar_x(pol=politica(vence), revalidar_en="2026-11-04T13:00:00Z")
    assert res["autorizado"] is False


def test_solo_cuentan_los_roles_que_ocupa():
    gob = activo("rol", "ROL-GOB", ambitos=["sistema"], capacidades=["gobernar_politica"], regla_aprobacion="uno")
    (ap,) = evaluar_x(pol=politica(gob))["aprobaciones"]
    assert ap["roles"] == ["ROL-OP"]


def test_regla_todos_y_quorum():
    h2 = humana("PER-H2", 102)
    v = verificador({11: review(), 13: review(user=102)})
    todos = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="todos")
    otra = {**REVISION, "review_id": 13}
    assert evaluar_x(pol=politica(todos, h2), ver=v)["autorizado"] is False
    assert evaluar_x(pol=politica(todos, h2), ver=v, revisiones=[REVISION, otra])["autorizado"] is True
    quorum = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion={"quorum": 2})
    repetida = evaluar_x(pol=politica(quorum, h2), ver=v, revisiones=[REVISION, REVISION])
    assert repetida["autorizado"] is False  # la misma persona no cuenta dos veces


def test_cambio_de_politica_exige_rol_de_gobierno():
    gob = activo("rol", "ROL-GOB", ambitos=["sistema"], capacidades=["gobernar_politica"], regla_aprobacion="uno")
    nuevo_rol = registro(
        "rol", id="ROL-NUEVO", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno"
    )
    efectos = [{"estado_anterior": "propuesta", "estado_nuevo": "activa", "valido_desde": "2026-11-05T00:00:00Z"}]
    assert evaluar_x(nuevo_rol, "", efectos, pol=politica(gob))["autorizado"] is False
    con = evaluar_x(nuevo_rol, "", efectos, pol=politica(gob, humana(roles=("ROL-OP", "ROL-GOB"))))
    assert con["autorizado"] is True and con["aprobaciones"][0]["roles"] == ["ROL-GOB"]


def test_sin_token_el_verificador_no_esta_habilitado(monkeypatch):
    monkeypatch.delenv("KB_GITHUB_TOKEN", raising=False)
    with pytest.raises(ErrorDeVerificacion, match="no habilitado"):
        ClienteGitHub.desde_entorno()
    assert "SECRETO-123" not in repr(ClienteGitHub("SECRETO-123"))


@pytest.mark.parametrize("repo", ["o/r/tarball/main?", "o", "../x/y", "o/r#1"])
def test_repositorio_configurado_validado(repo):
    with pytest.raises(ErrorDeVerificacion):
        VerificadorGitHub(Cliente({}), repo, "main")


def test_aprobacion_retirada_despues_por_la_misma_persona_no_vale():
    # GitHub cuenta la última postura de cada cuenta: citar la aprobación antigua no sirve.
    v = verificador({11: review(), 12: review(estado="CHANGES_REQUESTED", cuando="2026-11-04T11:00:00Z")})
    res = evaluar_x(ver=v)
    assert res["autorizado"] is False and "cambió o retiró" in res["revisiones"][0]["motivo"]
    # Un comentario posterior no cambia la postura.
    v = verificador({11: review(), 12: review(estado="COMMENTED", cuando="2026-11-04T11:00:00Z")})
    assert evaluar_x(ver=v)["autorizado"] is True


def test_pr_contra_otra_rama_o_con_base_cambiada_despues():
    assert evaluar_x(ver=verificador(ref="otra"))["autorizado"] is False
    cambio = [{"event": "base_ref_changed", "created_at": "2026-11-04T12:00:00Z"}]
    assert evaluar_x(ver=verificador(cronologia=cambio))["autorizado"] is False
    antes = [{"event": "base_ref_changed", "created_at": "2026-11-04T09:00:00Z"}]
    assert evaluar_x(ver=verificador(cronologia=antes))["autorizado"] is True


def test_revision_que_no_esta_en_la_pr():
    assert evaluar_x(revisiones=[{**REVISION, "review_id": 99}])["autorizado"] is False


def test_paginacion_de_revisiones():
    muchas = {2000 + i: review(user=1000 + i, estado="COMMENTED") for i in range(100)}
    respuestas = respuestas_github(muchas, REV, BASE)
    respuestas["/repos/o/r/pulls/1/reviews?per_page=100&page=2"] = [{"id": 11, **review()}]
    del muchas
    cliente = Cliente(respuestas)
    res = evaluar_x(ver=VerificadorGitHub(cliente, "o/r", "main"))
    assert res["autorizado"] is True and "/repos/o/r/pulls/1/reviews?per_page=100&page=2" in cliente.llamadas


def test_revision_repetida_cuenta_una_vez():
    res = evaluar_x(revisiones=[REVISION, dict(REVISION)])
    assert res["autorizado"] is True and len(res["aprobaciones"]) == 1


@pytest.mark.parametrize(
    "ref",
    [
        {"mecanismo": "otro", "pull": 1, "review_id": 11},
        {"mecanismo": "github-review", "pull": "1", "review_id": 11},
        "texto",
    ],
)
def test_referencia_de_revision_mal_formada(ref):
    assert evaluar_x(revisiones=[ref])["autorizado"] is False
