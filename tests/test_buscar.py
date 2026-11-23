"""Búsqueda léxica (núcleo §8, «Exploración»), sustituciones no declaradas y salida en lenguaje llano.

Repiten en pequeño las preguntas del banco que KBOL no podía responder o respondía mal: P01 (qué rige hoy sobre un
tema, sin ID), P09 (una cifra en un hecho en propuesta, sin ID) y P04 (una decisión que otra sustituye en parte solo
en prosa).
"""

import json

from conftest import decision, evento, registro

from kbol.buscar import buscar, terminos
from kbol.cli import main
from kbol.consolidar import consolidar
from kbol.consultar import consultar
from kbol.core import serializar
from kbol.llano import presentar
from kbol.proyeccion import Snapshot
from kbol.sustituciones import no_declaradas

T = "2026-11-20T12:00:00Z"


def _hecho_propuesto(ident, afirmacion):
    creacion = evento(
        "creacion",
        evento_id="E0",
        estado_anterior=None,
        estado_nuevo="propuesta",
        registrado_en="2026-10-26T00:00:00Z",
        valido_desde="2026-10-26T00:00:00Z",
    )
    return registro("hecho", id=ident, title="Primera pasada del CRA", afirmacion=afirmacion, eventos=[creacion])


def snap():
    """La cadena de herramientas de P01, un hecho en propuesta de P09 y la sustitución en prosa de P04."""
    regs, cuerpos = {}, {}

    def poner(ident, par, titulo):
        r, c = par
        r["title"] = titulo
        regs[ident], cuerpos[ident] = r, c

    poner(
        "ADR-0065",
        decision("ADR-0065", {"C1": "Se retira codebase-memory-mcp; graphify queda como apoyo opcional."}),
        "Retirar codebase-memory-mcp",
    )
    poner(
        "ADR-0077",
        decision(
            "ADR-0077",
            {"C1": "Graphify sobre el árbol de trabajo como apoyo opcional; git grep cierra el impacto."},
            registrado="2026-11-10T00:00:00Z",
            modifica=[{"destino": "ADR-0065#C1", "tipo": "sustitucion", "por": "ADR-0077#C1"}],
        ),
        "Graphify sobre el árbol de trabajo",
    )
    poner(
        "ADR-0005",
        decision("ADR-0005", {"C1": "ConfigCorreo con BaseSettings, en config/correo.py."}),
        "ConfigCorreo con BaseSettings",
    )
    adr16 = decision(
        "ADR-0016",
        {"C1": "ConfigCorreo vive en libs/comun/correo.py; el patrón de ADR-0005 no cambia."},
        afecta_a=["ADR-0005"],
    )
    adr16 = (adr16[0], adr16[1] + "\n\n* Supersedes (partial): ADR-0005 §Implementation path\n")
    poner("ADR-0016", adr16, "ConfigCorreo path supersedes ADR-0005")
    regs["HE-CRA"] = _hecho_propuesto("HE-CRA", "166 requisitos evaluables del CRA en CISO Assistant; no es una certificación.")
    cuerpos["HE-CRA"] = ""
    regs["PER-A"] = registro("persona", id="PER-A", title="David Palazón")
    rutas = {i: f"kb/{i}.md" for i in regs}
    return Snapshot(regs, "r1", cuerpos, rutas)


def test_los_terminos_se_normalizan_sin_tildes_ni_palabras_vacias():
    assert terminos("¿Qué rige hoy en el código, graphify?") == ["rige", "codigo", "graphi"]


def test_p01_sin_id_devuelve_lo_vigente_y_cuenta_lo_sustituido():
    res = buscar(snap(), "¿Qué rige hoy como apoyo, graphify o codebase-memory-mcp?", valido_en=T, conocido_hasta=T)
    refs = [c["referencia"] for c in res["candidatos"]]
    assert refs[0] == "ADR-0077#C1" and "ADR-0065#C1" not in refs
    primero = res["candidatos"][0]
    assert primero["clase"] == "vigente" and primero["estado"] == "aceptada" and "Graphify" in primero["fragmento"]
    assert res["excluidos"]["no_vigente"] == 1
    assert any("--incluir no_vigentes" in a for a in res["advertencias"])
    assert any("no decide qué rige" in a for a in res["advertencias"])


def test_lo_sustituido_solo_sale_si_se_pide_y_dice_que_rige_ahora():
    res = buscar(snap(), "codebase-memory-mcp", valido_en=T, conocido_hasta=T, incluir=["no_vigente"])
    sustituida = next(c for c in res["candidatos"] if c["referencia"] == "ADR-0065#C1")
    assert sustituida["clase"] == "no_vigente" and sustituida["rige_ahora"] == "ADR-0077#C1"


def test_p09_una_propuesta_se_cuenta_y_solo_se_muestra_si_se_pide():
    pregunta = "¿Con cuántos requisitos evaluables quedó la primera pasada del CRA en CISO Assistant?"
    defecto = buscar(snap(), pregunta, valido_en=T, conocido_hasta=T)
    assert defecto["candidatos"] == [] and defecto["excluidos"]["propuesta"] == 1
    assert any("--incluir propuestas" in a for a in defecto["advertencias"])
    con = buscar(snap(), pregunta, valido_en=T, conocido_hasta=T, incluir=["propuesta"])
    hecho = con["candidatos"][0]
    assert hecho["id"] == "HE-CRA" and hecho["clase"] == "propuesta" and "166" in hecho["fragmento"]


def test_sin_terminos_o_sin_coincidencias_se_dice():
    assert any("no tiene términos" in a for a in buscar(snap(), "¿qué?", valido_en=T, conocido_hasta=T)["advertencias"])
    vacia = buscar(snap(), "inexistente", valido_en=T, conocido_hasta=T)
    assert vacia["candidatos"] == [] and any("sin coincidencias" in a for a in vacia["advertencias"])


def test_el_limite_trunca_y_lo_declara():
    res = buscar(snap(), "ConfigCorreo graphify", valido_en=T, conocido_hasta=T, limite=1)
    assert len(res["candidatos"]) == 1 and res["truncado"] is True
    assert any("se muestran 1 de" in a for a in res["advertencias"])


def test_p04_la_sustitucion_en_prosa_se_avisa_sin_cambiar_la_vigencia():
    s = snap()
    assert [(i["registro"], i["destino"]) for i in no_declaradas(s)] == [("ADR-0016", "ADR-0005")]
    salida = consultar(s, ["ADR-0005"], valido_en=T, conocido_hasta=T)
    assert salida["resultados"][0]["vigencia"] == "total"
    assert any("SUSTITUCION_NO_DECLARADA" in a and "ADR-0016" in a for a in salida["advertencias"])
    assert any("SUSTITUCION_NO_DECLARADA" in a for a in consolidar(s, ["ADR-0005"], valido_en=T, conocido_hasta=T)[
        "advertencias"
    ])


def test_una_regularizacion_posterior_apaga_el_aviso():
    s = snap()
    r, c = decision(
        "ADR-0090",
        {"C1": "ConfigCorreo vive en libs/comun/correo.py, como dice ADR-0016."},
        modifica=[{"destino": "ADR-0005#C1", "tipo": "sustitucion", "por": "ADR-0090#C1"}],
    )
    s.registros["ADR-0090"], s.cuerpos["ADR-0090"] = r, c
    assert no_declaradas(s) == []


def test_ni_la_pasiva_ni_la_negacion_ni_una_pregunta_son_indicio():
    s = snap()
    for ident, texto in (
        ("ADR-0100", "* Status: superseded by ADR-0005"),
        ("ADR-0101", "Esta decisión no sustituye a ADR-0005."),
    ):
        r, c = decision(ident, {"C1": "Otra cosa."})
        s.registros[ident], s.cuerpos[ident] = r, c + "\n" + texto
    s.registros["Q-1"] = registro("pregunta", id="Q-1", title="¿Qué sustituye a ADR-0005?")
    assert [(i["registro"], i["destino"]) for i in no_declaradas(s)] == [("ADR-0016", "ADR-0005")]


def _con_aprobacion(s):
    aprob = s.registros["ADR-0077"]["eventos"][1]["aprobacion"]
    aprob["actor"] = "human:PER-A"
    aprob["comprobante"] = {"mecanismo": "declarada", "cita": "Acepto ADR-0077", "autenticada": False}
    return s


def _sobre(op, resultado, advertencias=()):
    return {
        "resultado": {"estado": "completado", **resultado},
        "advertencias": list(advertencias),
        "valido_en": T,
        "conocido_hasta": T,
        "cobertura": {"truncado": False},
    }


def test_llano_dice_la_regla_quien_la_aprobo_y_si_rige_sin_ids():
    s = _con_aprobacion(snap())
    res = consultar(s, ["ADR-0077"], valido_en=T, conocido_hasta=T)
    texto = presentar("consultar", _sobre("consultar", res), s)
    assert "[APROBADA] «Graphify sobre el árbol de trabajo»" in texto
    assert "Rige entera a 20 nov 2026" in texto and "git grep cierra el impacto" in texto
    assert "Aprobación de David Palazón, el 20 nov 2026" not in texto  # la fecha es la de la aprobación, no la consulta
    assert "Aprobación de David Palazón, el 10 nov 2026, con estas palabras: «Acepto ADR-0077»" in texto
    assert "declarada, sin autenticar" in texto
    assert "PER-A" not in texto and "(ADR-0077)" not in texto


def test_llano_con_ids_los_muestra_y_lo_propuesto_se_distingue():
    s = _con_aprobacion(snap())
    res = consultar(s, ["ADR-0077", "HE-CRA"], valido_en=T, conocido_hasta=T)
    texto = presentar("consultar", _sobre("consultar", res), s, con_ids=True)
    assert "«Graphify sobre el árbol de trabajo» (ADR-0077)" in texto and "(PER-A)" in texto
    assert "[HECHO PROPUESTO: sin aceptar] «Primera pasada del CRA» (HE-CRA)" in texto


def test_llano_de_una_busqueda_marca_los_candidatos_y_avisa_de_p04():
    s = snap()
    res = buscar(s, "ConfigCorreo correo", valido_en=T, conocido_hasta=T)
    texto = presentar("buscar", _sobre("buscar", res), s)
    assert texto.count("[CANDIDATO por búsqueda, sin confirmar]") == len(res["candidatos"]) >= 2
    assert "dice sustituirla o derogarla, al menos en parte, sin declararlo" in texto


def test_cli_buscar_exige_texto_y_devuelve_el_sobre(tmp_path, capsys):
    carpeta = tmp_path / "kb"
    carpeta.mkdir()
    for ident in ("ADR-0065", "ADR-0077"):
        r, c = snap().registros[ident], snap().cuerpos[ident]
        (carpeta / f"{ident}.md").write_text(serializar(r, c), encoding="utf-8")
    base = ["buscar", str(tmp_path), "--carpeta", "kb", "--valido-en", T, "--conocido-hasta", T]
    assert main(base) == 2
    assert "necesita --consulta" in capsys.readouterr().out
    assert main([*base, "--consulta", "graphify"]) == 3  # leída del disco, sin revisión: parcial
    sobre = json.loads(capsys.readouterr().out)
    assert sobre["resultado"]["candidatos"][0]["referencia"] == "ADR-0077#C1"
    assert "similitud semántica: la búsqueda es léxica" in sobre["cobertura"]["no_evaluado"]
    assert main([*base, "--consulta", "graphify", "--llano"]) == 3
    assert capsys.readouterr().out.startswith("A fecha 20 nov 2026")
