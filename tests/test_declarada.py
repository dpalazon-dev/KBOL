"""Aprobación declarada (RES-02 parcial): la persona aprueba en la conversación y el agente cita sus palabras.

El verificador no autentica a nadie: da por buena la identidad declarada y lo dice en el comprobante. Lo que sí
comprueba la integración es lo mismo que con cualquier canal: que la aprobación cubre exactamente lo que se integra
(los digests mostrados), que la persona es humana, activa y ocupa el rol en la política base, y que la base mostrada
precede a la actual.
"""

import json

import pytest
from conftest import CUERPO_DECISION, decision, registro
from test_integrar import ACEPTAR, Repo, activo, canonico, proponer, solicitud

from kbol.consolidar import consolidar
from kbol.core import parse, serializar
from kbol.declarada import MECANISMO, VerificadorDeclarado
from kbol.digest import digest
from kbol.integrar import integrar
from kbol.schema import validar
from kbol.snapshot import cargar
from kbol.verificacion import ErrorDeVerificacion

INSTANTE = "2026-11-05T18:00:00Z"
CITA = "Apruebo aceptar DEC-X tal como está"


@pytest.fixture
def entorno(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.escribir("README.md", "x\n")
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    per = activo(
        "persona",
        "PER-H",
        naturaleza="humana",
        identidad_ref="declarada:h",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    sin_rol = activo("persona", "PER-N", naturaleza="humana", identidad_ref="declarada:n", ocupa=[])
    ag = activo(
        "persona",
        "PER-AG",
        naturaleza="agente",
        identidad_ref="declarada:agente",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    a, ca = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-10-03T00:00:00Z", autorizado_por=["ROL-OP"])
    for ident, r, c in (("ROL-OP", rol, ""), ("PER-H", per, ""), ("PER-N", sin_rol, ""), ("PER-AG", ag, "")):
        repo.escribir(f"kb/{ident}.md", canonico(r, c))
    repo.escribir("kb/DEC-A.md", canonico(a, ca))
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def dec_x():
    return registro("decision", id="DEC-X", autorizado_por=["ROL-OP"]), CUERPO_DECISION


def aceptacion(repo, base, op="op-1"):
    r, c = dec_x()
    return proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud(op, {"DEC-X": ACEPTAR})})


def declarada(base, identidad="declarada:h", digests=None, **cambios):
    revision = {
        "mecanismo": MECANISMO,
        "identidad": identidad,
        "sesion": "sesión de Claude Code kbol-e9",
        "instante": INSTANTE,
        "cita": CITA,
        "base_mostrada": base,
        "digests": {"DEC-X": digest(*dec_x(), ACEPTAR)} if digests is None else digests,
    }
    revision.update(cambios)
    return revision


def llamar(repo, base, prop, recibos, revisiones, op="op-1"):
    return integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=revisiones,
        verificador=VerificadorDeclarado(repo.raiz),
        recibos=recibos,
    )


def test_aprobacion_declarada_integra_y_deja_la_cita_en_ratificacion_recibo_y_trailer(entorno):
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, [declarada(base)])
    assert res["estado"] == "integrado", res
    meta, cuerpo = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert meta["estado"] == "aceptada"
    assert validar(meta, cuerpo, modo="canonico") == []
    ratificacion = next(e for e in meta["eventos"] if e["tipo_evento"] == "ratificacion")
    ap = ratificacion["aprobacion"]
    assert ap["actor"] == "human:PER-H" and ap["identidad_ref"] == "declarada:h"
    assert ap["comprobante"]["cita"] == CITA and ap["comprobante"]["autenticada"] is False
    assert ap["aprobada_en"] == INSTANTE
    assert ratificacion["evidencia_evento"]["mecanismo"] == MECANISMO
    assert CITA in ratificacion["evidencia_evento"]["comprobante"]
    assert "sin autenticar" in ratificacion["evidencia_evento"]["comprobante"]
    recibo = json.loads((recibos / "op-1.json").read_text(encoding="utf-8"))
    detalle = recibo["aprobaciones_detalle"]
    assert len(detalle) == 1 and detalle[0]["comprobante"]["cita"] == CITA
    mensaje = repo.git("log", "-1", "--format=%B", "canon")
    revisiones = next(linea for linea in mensaje.splitlines() if linea.startswith("Revisiones: "))
    assert revisiones == f"Revisiones: {ap['aprobacion_id']}" and "\n" not in ap["aprobacion_id"]
    assert ap["aprobacion_id"].startswith(f"{MECANISMO}:")


def test_consolidar_dice_que_lo_que_rige_se_apoya_en_una_aprobacion_declarada(entorno):
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, [declarada(base)])
    snap, cobertura = cargar(repo.raiz, "kb", res["revision_integrada"])
    assert cobertura["estado"] == "completo", cobertura
    salida = consolidar(snap, ["DEC-X"], valido_en="2026-11-06T00:00:00Z", conocido_hasta=None)
    clausula = next(c for c in salida["clausulas"] if c["referencia"] == "DEC-X#C1")
    autoridad = clausula["autoridad"]
    assert autoridad["comprobada"] is False
    assert autoridad["declaradas"] == autoridad["ratificaciones"] and len(autoridad["declaradas"]) == 1


def test_una_propuesta_sin_efectos_deja_la_aprobacion_en_recibo_y_trailer_sin_ratificar(entorno):
    repo, base, recibos = entorno
    r, c = dec_x()
    prop = proponer(repo, base, {"kb/DEC-X.md": serializar(r, c)})
    res = llamar(repo, base, prop, recibos, [declarada(base, digests={"DEC-X": digest(r, c, [])})])
    assert res["estado"] == "integrado", res
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert [e["tipo_evento"] for e in meta["eventos"]] == ["creacion"]
    recibo = json.loads((recibos / "op-1.json").read_text(encoding="utf-8"))
    assert recibo["aprobaciones_detalle"][0]["comprobante"]["cita"] == CITA


def test_digests_distintos_de_lo_mostrado_caducan_la_aprobacion(entorno):
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, [declarada(base, digests={"DEC-X": "0" * 64})])
    assert res["estado"] == "bloqueado" and res["codigo"] == "APROBACION_CADUCADA", res
    assert repo.git("rev-parse", "canon") == base


def test_un_registro_tocado_sin_digest_mostrado_no_esta_aprobado(entorno):
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, [declarada(base, digests={})])
    assert res["estado"] == "bloqueado" and res["codigo"] == "APROBACION_CADUCADA", res


def test_una_base_mostrada_que_no_precede_a_la_actual_no_vale(entorno):
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    ajena = proponer(repo, base, {"README.md": "otra\n"})
    res = llamar(repo, base, prop, recibos, [declarada(ajena)])
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res


@pytest.mark.parametrize("identidad", ["declarada:n", "declarada:agente", "declarada:nadie"])
def test_sin_rol_agente_o_desconocida_no_aprueba(entorno, identidad):
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, [declarada(base, identidad=identidad)])
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res


def test_una_persona_no_se_da_el_rol_que_usa_para_aprobar(entorno):
    repo, base, recibos = entorno
    meta, cuerpo = parse(repo.git("show", f"{base}:kb/PER-N.md") + "\n")
    meta["ocupa"] = [{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}]
    r, c = dec_x()
    archivos = {"kb/PER-N.md": serializar(meta, cuerpo, modo="canonico"), "kb/DEC-X.md": serializar(r, c)}
    prop = proponer(repo, base, {**archivos, **solicitud("op-1", {"DEC-X": ACEPTAR})})
    digests = {"DEC-X": digest(r, c, ACEPTAR), "PER-N": digest(meta, cuerpo, [])}
    res = llamar(repo, base, prop, recibos, [declarada(base, identidad="declarada:n", digests=digests)])
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res


@pytest.mark.parametrize(
    "cambio",
    [
        {"mecanismo": "github-review"},
        {"identidad": "h"},
        {"identidad": "declarada:"},
        {"sesion": ""},
        {"cita": "  "},
        {"instante": "2026-11-05"},
        {"instante": "2026-11-05T18:00:00"},
        {"base_mostrada": "abc"},
        {"digests": ["DEC-X"]},
        {"digests": {"DEC-X": "corto"}},
    ],
)
def test_una_aprobacion_mal_formada_no_se_verifica(entorno, cambio):
    repo, base, _ = entorno
    with pytest.raises(ErrorDeVerificacion):
        VerificadorDeclarado(repo.raiz).verificar(declarada(base, **cambio), base, base)


def test_la_misma_aprobacion_con_los_digests_en_otro_orden_cuenta_una_vez(entorno):
    repo, base, recibos = entorno
    r, c = dec_x()
    otro = {**dec_x()[0], "id": "DEC-Y"}
    archivos = {"kb/DEC-X.md": serializar(r, c), "kb/DEC-Y.md": serializar(otro, c)}
    prop = proponer(repo, base, {**archivos, **solicitud("op-1", {"DEC-X": ACEPTAR})})
    uno = {"DEC-X": digest(r, c, ACEPTAR), "DEC-Y": digest(otro, c, [])}
    dos = {"DEC-Y": uno["DEC-Y"], "DEC-X": uno["DEC-X"]}
    res = llamar(repo, base, prop, recibos, [declarada(base, digests=uno), declarada(base, digests=dos)])
    assert res["estado"] == "integrado", res
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert [e["tipo_evento"] for e in meta["eventos"]].count("ratificacion") == 1


def test_un_instante_en_el_futuro_no_se_verifica(entorno):
    repo, base, _ = entorno
    with pytest.raises(ErrorDeVerificacion):
        VerificadorDeclarado(repo.raiz).verificar(declarada(base, instante="2999-01-01T00:00:00Z"), base, base)


def test_sin_repositorio_el_verificador_no_se_crea():
    with pytest.raises(ErrorDeVerificacion):
        VerificadorDeclarado(None)


def test_el_comprobante_nunca_dice_que_esta_autenticado(entorno):
    repo, base, _ = entorno
    v = VerificadorDeclarado(repo.raiz).verificar(declarada(base), base, base)
    assert v["comprobante"]["autenticada"] is False and v["identidad"] == "declarada:h"
    assert v["instante"] == INSTANTE and v["digests"] == declarada(base)["digests"]
