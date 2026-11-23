"""Paquete de aprobación: lo que la persona ve antes de aprobar, con los digests que la puerta comprueba.

La prueba que importa es de extremo a extremo: el esqueleto del paquete, completado con lo que aporta quien recoge la
aprobación, integra; si el contenido cambia después, caduca; y si la puerta fuera a bloquear, el paquete bloquea antes
con el mismo código.
"""

import json
import subprocess
import sys

import pytest
from conftest import CUERPO_DECISION, cuerpo_de, decision, evento, registro
from test_importacion import CUERPO as CUERPO_ADR
from test_importacion import HEREDADA, IMPORTACION, QD_HEREDADA, adr
from test_integrar import ACEPTAR, Repo, activo, canonico, proponer, solicitud

from kbol.core import parse, serializar
from kbol.declarada import CAMPOS, MECANISMO, VerificadorDeclarado
from kbol.integrar import ACTOR, integrar
from kbol.paquete import preparar_aprobacion, presentar

INSTANTE = "2026-11-05T18:00:00Z"
VALIDO = "2026-11-06T00:00:00Z"
# Sin estado_anterior: la puerta lo rellena antes de calcular el digest, y el paquete tiene que hacer lo mismo.
ACEPTAR_SIN_ANTERIOR = [{"estado_nuevo": "aceptada", "valido_desde": "2026-11-05T00:00:00Z"}]
CREADO = "2026-10-03T00:00:00Z"


def _creado():
    return evento(
        "creacion",
        evento_id="E0",
        estado_anterior=None,
        estado_nuevo="propuesta",
        registrado_en=CREADO,
        valido_desde=CREADO,
    )


@pytest.fixture
def entorno(tmp_path):
    repo = Repo(tmp_path / "repo")
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    per = activo(
        "persona",
        "PER-H",
        naturaleza="humana",
        identidad_ref="declarada:h",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    a, ca = decision("DEC-A", {"C1": "Lunes."}, registrado=CREADO, autorizado_por=["ROL-OP"])
    p, cp = decision("DEC-P", {"C1": "Martes."}, registrado=CREADO, estado="propuesta", autorizado_por=["ROL-OP"])
    he = registro("hecho", id="HE-P", basada_en=[], eventos=[_creado()])
    for ident, r, c in (("ROL-OP", rol, ""), ("PER-H", per, ""), ("DEC-A", a, ca), ("DEC-P", p, cp), ("HE-P", he, "")):
        repo.escribir(f"kb/{ident}.md", canonico(r, c))
    repo.escribir("kb/ADR-0001.md", HEREDADA)
    repo.escribir("kb/QD-001.md", QD_HEREDADA)
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def dec_x(**campos):
    return registro("decision", id="DEC-X", autorizado_por=["ROL-OP"], **campos), CUERPO_DECISION


def paquete(repo, base, prop, op="op-1", **kw):
    return preparar_aprobacion(
        repo.raiz, carpeta="kb", operacion_id=op, base=base, propuesta=prop, valido_en=VALIDO, **kw
    )


def firmar(esqueleto):
    """Lo que aporta quien recoge la aprobación: el generador no lo escribe."""
    return {**esqueleto, "identidad": "declarada:h", "sesion": "sesión de prueba", "instante": INSTANTE, "cita": "Sí"}


def integrar_con(repo, base, prop, recibos, aprobaciones, op="op-1", modo="toda"):
    return integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=aprobaciones,
        verificador=VerificadorDeclarado(repo.raiz),
        recibos=recibos,
        aprobacion=modo,
        actor="claude-code/opus-5.5" if modo == "decisiva" else ACTOR,
    )


def _creacion(repo, base, op):
    r, c = dec_x()
    return proponer(repo, base, {"kb/DEC-X.md": serializar(r, c)}), "DEC-X"


def _transicion(repo, base, op):
    r, c = dec_x()
    return proponer(
        repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud(op, {"DEC-X": ACEPTAR_SIN_ANTERIOR})}
    ), "DEC-X"


def _importacion(repo, base, op):
    peticion = {"operacion_id": op, "efectos": {}, "importaciones": {"ADR-0001": IMPORTACION}}
    archivos = {"kb/ADR-0001.md": serializar(adr(), CUERPO_ADR), f"kb/_solicitudes/{op}.json": json.dumps(peticion)}
    return proponer(repo, base, archivos), "ADR-0001"


CASOS = {"creacion": _creacion, "transicion": _transicion, "importacion": _importacion}


def _ratificaciones(repo, ident):
    meta, _ = parse(repo.git("show", f"canon:kb/{ident}.md") + "\n")
    return [e["aprobacion"] for e in meta["eventos"] if e["tipo_evento"] == "ratificacion"]


@pytest.mark.parametrize("modo", ["toda", "decisiva"])
@pytest.mark.parametrize("caso", sorted(CASOS))
def test_el_esqueleto_completado_integra_con_los_mismos_digests(entorno, caso, modo):
    repo, base, recibos = entorno
    prop, ident = CASOS[caso](repo, base, "op-1")
    paq = paquete(repo, base, prop)
    assert paq["estado"] == "completado", paq
    assert [r["id"] for r in paq["registros"]] == [ident]
    [esqueleto] = paq["aprobaciones"]
    assert esqueleto["base_mostrada"] == base and set(esqueleto["digests"]) == {ident}
    res = integrar_con(repo, base, prop, recibos, [firmar(esqueleto)], modo=modo)
    assert res["estado"] == "integrado", res
    assert res["registros"] == [ident]
    # Los digests del paquete son los que la puerta recalculó y dejó en la ratificación y en el recibo.
    digest = paq["registros"][0]["digest"]
    assert esqueleto["digests"][ident] == digest
    ratificaciones = _ratificaciones(repo, ident)
    assert all(a["digest"] == digest for a in ratificaciones)
    for detalle in res.get("aprobaciones_detalle", []):
        assert detalle["comprobante"]["digests"] == esqueleto["digests"]
    if caso == "transicion":
        assert len(ratificaciones) == 1 and paq["registros"][0]["decisivo"]
        assert res["decisivos"] == [ident]
    else:
        assert not paq["registros"][0]["decisivo"]
        assert res["decisivos"] == ([ident] if modo == "toda" else [])


def test_la_transicion_lleva_el_estado_anterior_que_rellena_la_puerta(entorno):
    repo, base, _ = entorno
    prop, _ = _transicion(repo, base, "op-1")
    [r] = paquete(repo, base, prop)["registros"]
    assert r["efectos"] == [{**ACEPTAR_SIN_ANTERIOR[0], "estado_anterior": "propuesta"}]
    assert r["motivos_decisivo"] == ["transición a aceptada"] and r["cambio"] == "nuevo"


def test_la_importacion_muestra_lo_que_se_aprueba_y_el_estado_heredado(entorno):
    repo, base, _ = entorno
    prop, _ = _importacion(repo, base, "op-1")
    [r] = paquete(repo, base, prop)["registros"]
    assert r["cambio"] == "importado"
    assert r["importacion"] == {**IMPORTACION, "estado_heredado": "Aceptada"}


def test_contenido_cambiado_despues_del_paquete_caduca_la_aprobacion(entorno):
    repo, base, recibos = entorno
    prop, _ = _transicion(repo, base, "op-1")
    esqueleto = paquete(repo, base, prop)["aprobaciones"][0]
    r, c = dec_x(title="Otro título")
    otra = proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud("op-1", {"DEC-X": ACEPTAR_SIN_ANTERIOR})})
    res = integrar_con(repo, base, otra, recibos, [firmar(esqueleto)])
    assert res["estado"] == "bloqueado" and res["codigo"] == "APROBACION_CADUCADA", res
    assert repo.git("rev-parse", "canon") == base


def _reescribe_clausula_aceptada(repo, base):
    texto = repo.git("show", f"{base}:kb/DEC-A.md") + "\n"
    return proponer(repo, base, {"kb/DEC-A.md": texto.replace("Lunes.", "Martes.")})


def _transicion_imposible(repo, base):
    r, c = dec_x()
    efecto = [{"estado_anterior": "aceptada", "estado_nuevo": "rechazada", "valido_desde": "2026-11-05T00:00:00Z"}]
    return proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud("op-1", {"DEC-X": efecto})})


def _toca_algo_que_no_es_registro(repo, base):
    r, c = dec_x()
    return proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), "README.md": "otro\n"})


@pytest.mark.parametrize("hacer", [_reescribe_clausula_aceptada, _transicion_imposible, _toca_algo_que_no_es_registro])
def test_lo_que_la_puerta_bloquearia_el_paquete_lo_bloquea_antes_con_el_mismo_codigo(entorno, hacer):
    repo, base, recibos = entorno
    prop = hacer(repo, base)
    paq = paquete(repo, base, prop)
    puerta = integrar_con(repo, base, prop, recibos, [])
    assert paq["estado"] == puerta["estado"] == "bloqueado", (paq, puerta)
    assert (paq["codigo"], paq["motivo"]) == (puerta["codigo"], puerta["motivo"])
    assert "registros" not in paq and "aprobaciones" not in paq


def test_un_conflicto_normativo_bloquea_el_paquete(entorno):
    repo, base, _ = entorno
    archivos = {}
    for ident, texto in (("DEC-B", "Martes."), ("DEC-D", "Jueves.")):
        r = registro(
            "decision",
            id=ident,
            autorizado_por=["ROL-OP"],
            modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": f"{ident}#C1"}],
        )
        archivos[f"kb/{ident}.md"] = serializar(r, cuerpo_de({"C1": texto}))
    prop = proponer(repo, base, {**archivos, **solicitud("op-1", {"DEC-B": ACEPTAR, "DEC-D": ACEPTAR})})
    paq = paquete(repo, base, prop)
    assert paq["estado"] == "bloqueado" and paq["codigo"] == "CONFLICTO_NORMATIVO", paq


def test_el_esqueleto_deja_vacio_lo_que_aporta_quien_aprueba(entorno):
    repo, base, _ = entorno
    prop, _ = _creacion(repo, base, "op-1")
    [esqueleto] = paquete(repo, base, prop)["aprobaciones"]
    assert set(esqueleto) == set(CAMPOS) and esqueleto["mecanismo"] == MECANISMO
    assert all(esqueleto[k] is None for k in ("identidad", "sesion", "instante", "cita"))


def test_una_clausula_cambiada_muestra_el_texto_de_antes_y_el_nuevo(entorno):
    repo, base, _ = entorno
    texto = repo.git("show", f"{base}:kb/DEC-P.md") + "\n"
    clausula = '<clausula id="C1">\nMartes.\n</clausula>'
    assert texto.count(clausula) == 1
    nuevo = texto.replace(clausula, clausula.replace("Martes.", "Miércoles.")).replace("title: Título", "title: Nuevo")
    prop = proponer(repo, base, {"kb/DEC-P.md": nuevo})
    [r] = paquete(repo, base, prop)["registros"]
    assert r["cambio"] == "modificado"
    assert r["clausulas"] == [{"ancla": "C1", "cambio": "cambiada", "antes": "Martes.", "despues": "Miércoles."}]
    assert r["cabecera"] == [{"campo": "title", "antes": "Título", "despues": "Nuevo"}]


def test_una_modificacion_muestra_el_texto_que_rige_junto_al_nuevo(entorno):
    repo, base, _ = entorno
    r = registro(
        "decision",
        id="DEC-B",
        autorizado_por=["ROL-OP"],
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
    )
    prop = proponer(repo, base, {"kb/DEC-B.md": serializar(r, cuerpo_de({"C1": "Martes."}))})
    paq = paquete(repo, base, prop)
    [reg] = paq["registros"]
    assert reg["modifica"] == [
        {
            "destino": "DEC-A#C1",
            "tipo": "sustitucion",
            "por": "DEC-B#C1",
            "texto_actual": "Lunes.",
            "texto_nuevo": "Martes.",
        }
    ]
    assert reg["clausulas"] == [{"ancla": "C1", "cambio": "nueva", "despues": "Martes."}]
    assert {"campo": "modifica", "antes": None, "despues": r["modifica"]} in reg["cabecera"]
    assert not any(c["campo"] in ("eventos", "estado", "id") for c in reg["cabecera"])


def test_un_apoyo_que_no_rige_se_muestra_como_tal(entorno):
    repo, base, _ = entorno
    r, c = dec_x(basada_en=["HE-P"])
    prop = proponer(repo, base, {"kb/DEC-X.md": serializar(r, c)})
    [reg] = paquete(repo, base, prop)["registros"]
    assert reg["soporte"] == "roto"
    [apoyo] = reg["apoyos"]
    assert apoyo["ref"] == "HE-P" and apoyo["campo"] == "basada_en" and apoyo["situacion"] == "no_rige"


def test_el_impacto_es_el_que_dejaria_el_recibo(entorno):
    repo, base, recibos = entorno
    texto = repo.git("show", f"{base}:kb/HE-P.md") + "\n"
    campos = {"estado": "propuesta", "basada_en": ["HE-P"], "autorizado_por": ["ROL-OP"]}
    r, c = decision("DEC-X", {"C1": "Jueves."}, registrado=CREADO, **campos)
    base2 = proponer(repo, base, {"kb/DEC-X.md": canonico(r, c)})
    repo.git("update-ref", "refs/heads/canon", base2, base)  # DEC-X ya consume HE-P en la base
    prop = proponer(repo, base2, {"kb/HE-P.md": texto.replace("Título", "Otro")})
    paq = paquete(repo, base2, prop)
    assert paq["estado"] == "completado", paq
    assert [a["afectado"] for a in paq["impacto"]["afectados"]] == ["DEC-X"]
    res = integrar_con(repo, base2, prop, recibos, [firmar(paq["aprobaciones"][0])])
    assert res["estado"] == "integrado", res
    assert res["impacto"]["afectados"] == paq["impacto"]["afectados"]


def test_sin_registros_tocados_no_hay_nada_que_aprobar(entorno):
    repo, base, _ = entorno
    prop = proponer(repo, base, {"kb/_solicitudes/op-1.json": json.dumps({"operacion_id": "op-1", "efectos": {}})})
    paq = paquete(repo, base, prop)
    assert paq["estado"] == "completado" and paq["registros"] == [], paq
    assert paq["aprobaciones"][0]["digests"] == {}


def test_solo_lee(entorno):
    repo, base, _ = entorno
    prop, _ = _transicion(repo, base, "op-1")
    refs = repo.git("for-each-ref")
    paquete(repo, base, prop)
    assert repo.git("for-each-ref") == refs and repo.git("status", "--porcelain") == ""


def test_un_corte_sin_zona_bloquea(entorno):
    repo, base, _ = entorno
    prop, _ = _creacion(repo, base, "op-1")
    paq = preparar_aprobacion(
        repo.raiz, carpeta="kb", operacion_id="op-1", base=base, propuesta=prop, valido_en="2026-11-06"
    )
    assert paq["estado"] == "bloqueado" and paq["codigo"] == "TIEMPO_AMBIGUO"


def test_la_presentacion_dice_lo_que_cambia_y_lo_que_no_se_evaluo(entorno):
    repo, base, _ = entorno
    r = registro(
        "decision",
        id="DEC-B",
        autorizado_por=["ROL-OP"],
        basada_en=["HE-P"],
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
    )
    archivos = {"kb/DEC-B.md": serializar(r, cuerpo_de({"C1": "Martes."})), **solicitud("op-1", {"DEC-B": ACEPTAR})}
    paq = paquete(repo, base, proponer(repo, base, archivos))
    texto = presentar(paq)
    assert "Modifica DEC-A#C1 (sustitucion): ahora «Lunes.» → «Martes.»" in texto
    assert "Efecto: propuesta → aceptada desde 2026-11-05T00:00:00Z" in texto
    assert "Decisivo: transición a aceptada" in texto
    assert "HE-P (basada_en): no_rige" in texto
    assert paq["registros"][0]["digest"] in texto and "No evaluado:" in texto
    assert "---" not in texto and "eventos" not in texto


def kbol(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


def _cli(repo, base, prop, *extra):
    return kbol(
        "preparar_aprobacion",
        str(repo.raiz),
        "--carpeta",
        "kb",
        "--operacion-id",
        "op-1",
        "--base",
        base,
        "--propuesta",
        prop,
        "--valido-en",
        VALIDO,
        *extra,
    )


def test_cli_devuelve_el_sobre_con_el_paquete(entorno):
    repo, base, recibos = entorno
    prop, _ = _transicion(repo, base, "op-1")
    codigo, salida = _cli(repo, base, prop)
    sobre = json.loads(salida)
    assert codigo == 0 and sobre["operacion"] == "preparar_aprobacion", sobre
    assert sobre["resultado"]["estado"] == "completado" and sobre["revision"] == prop
    assert sobre["valido_en"] == VALIDO and "no_evaluado" not in sobre["resultado"]
    assert any("autenticidad" in n for n in sobre["cobertura"]["no_evaluado"])
    [esqueleto] = sobre["resultado"]["aprobaciones"]
    assert integrar_con(repo, base, prop, recibos, [firmar(esqueleto)])["estado"] == "integrado"


def test_cli_en_texto(entorno):
    repo, base, _ = entorno
    prop, _ = _transicion(repo, base, "op-1")
    codigo, salida = _cli(repo, base, prop, "--texto")
    assert codigo == 0 and salida.startswith("Paquete de aprobación de op-1"), salida
    assert "DEC-X (decision, nuevo)" in salida and "Digest: " in salida


def test_cli_bloqueado_sale_con_dos(entorno):
    repo, base, _ = entorno
    codigo, salida = _cli(repo, base, _reescribe_clausula_aceptada(repo, base))
    sobre = json.loads(salida)
    assert codigo == 2 and sobre["resultado"]["codigo"] == "ESQUEMA_INVALIDO", sobre


def test_cli_sin_registros_tocados_es_parcial(entorno):
    repo, base, _ = entorno
    prop = proponer(repo, base, {"kb/_solicitudes/op-1.json": json.dumps({"operacion_id": "op-1", "efectos": {}})})
    codigo, salida = _cli(repo, base, prop)
    sobre = json.loads(salida)
    assert codigo == 3 and sobre["resultado"]["estado"] == "parcial", sobre
    assert any("nada que aprobar" in a for a in sobre["advertencias"])


def test_cli_sin_entradas_obligatorias_bloquea(entorno):
    repo, base, _ = entorno
    codigo, salida = kbol("preparar_aprobacion", str(repo.raiz), "--carpeta", "kb", "--base", base)
    sobre = json.loads(salida)
    assert codigo == 2 and "--operacion-id" in sobre["resultado"]["motivo"]
