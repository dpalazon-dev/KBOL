"""Vocabulario del dominio: esquema de `define`, lo que rige en dos cortes, sus usos y la orden.

La puerta de integración y el paquete de aprobación se prueban en `test_vocabulario_integrar.py`.
"""

import pytest
from conftest import CUERPO_DECISION, decision, registro
from test_integrar import activo
from test_politica_cli import escribir, kb

from kbol.consultar import consultar
from kbol.proyeccion import Snapshot
from kbol.schema import validar
from kbol.vocabulario import MUNDO_ABIERTO, revisar, situacion, vigente

PLANTA = {
    "clausula": "C1",
    "termino": "planta",
    "clase": "clase_entidad",
    "descripcion": "Instalación que trata agua.",
    "alias": ["EDAR"],
}
DESPUES = "2026-11-20T00:00:00Z"


def con_define(*entradas, **cambios):
    return registro("decision", define=[{**PLANTA, **e} for e in entradas], **cambios)


def define(*entradas):
    return [{**PLANTA, **e} for e in entradas]


def snap(*pares):
    return Snapshot({r["id"]: r for r, _ in pares}, "r1", {r["id"]: c for r, c in pares})


def rol():
    return activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno"), ""


def entidad(ident, clase, **campos):
    return activo("entidad", ident, clase_entidad=clase, **campos), ""


def dec_v(**extra):
    return decision("DEC-V", {"C1": "Una planta trata agua."}, define=define({}), autorizado_por=["ROL-OP"], **extra)


# Esquema


def test_un_define_valido_pasa_el_esquema():
    assert validar(con_define({}), CUERPO_DECISION) == []
    sin_alias = {k: v for k, v in PLANTA.items() if k != "alias"}
    assert validar(registro("decision", define=[sin_alias]), CUERPO_DECISION) == []


def test_la_clausula_de_un_define_esta_en_el_cuerpo():
    [h] = validar(con_define({"clausula": "C9"}), CUERPO_DECISION)
    assert h["codigo"] == "REFERENCIA_AUSENTE" and h["ruta"] == "/define/0/clausula"


@pytest.mark.parametrize("nombre", ["basada_en", "decision", "Entidad", "clase_entidad", "define", "ambitos"])
def test_un_termino_no_lleva_el_nombre_de_un_tipo_un_campo_o_una_relacion(nombre):
    for entrada in ({"termino": nombre}, {"alias": [nombre]}):
        hallazgos = validar(con_define(entrada), CUERPO_DECISION)
        assert [h["codigo"] for h in hallazgos] == ["ESQUEMA_INVALIDO"], hallazgos
        assert "tipo, un campo o una relación" in hallazgos[0]["mensaje"]


@pytest.mark.parametrize("cambio", [{"clase": "clase_rol"}, {"ambito": "x"}, {"termino": "dos\nlíneas"}])
def test_clase_desconocida_clave_de_mas_o_termino_de_varias_lineas(cambio):
    assert [h["codigo"] for h in validar(con_define(cambio), CUERPO_DECISION)] == ["ESQUEMA_INVALIDO"]


def test_un_termino_o_un_alias_no_se_repiten_en_el_registro():
    repetido = validar(con_define({}, {"descripcion": "Otra."}), CUERPO_DECISION)
    assert [h["ruta"] for h in repetido] == ["/define/1/termino", "/define/1/alias/0"]
    alias = validar(con_define({}, {"termino": "depuradora", "alias": ["planta"]}), CUERPO_DECISION)
    assert [h["ruta"] for h in alias] == ["/define/1/alias/0"]


def test_define_solo_lo_declara_una_decision():
    hallazgos = validar(registro("entidad", define=define({})), "")
    assert any(h["ruta"] == "/define" and "campo no declarado" in h["mensaje"] for h in hallazgos)


# Lo que rige


def test_un_termino_rige_cuando_su_decision_esta_aceptada():
    voc = vigente(snap(dec_v()), valido_en=DESPUES, conocido_hasta=None)
    assert voc["declarado"] is True
    assert voc["clases"] == {
        "planta": {"decision": "DEC-V", "clausula": "C1", "descripcion": PLANTA["descripcion"], "alias": ["EDAR"]}
    }
    assert voc["alias"] == {"EDAR": "planta"}
    assert situacion(voc, "EDAR") == ("vigente", "planta")
    assert situacion(voc, "Planta") == ("no_declarado", "Planta")


def test_una_decision_propuesta_no_declara_nada():
    voc = vigente(snap(dec_v(estado="propuesta")), valido_en=DESPUES, conocido_hasta=None)
    assert voc["clases"] == {} and voc["declarado"] is False
    assert situacion(voc, "cualquiera") == ("abierto", "cualquiera")


def test_un_termino_rige_en_los_dos_cortes():
    s = snap(dec_v(registrado="2026-11-03T00:00:00Z", valido="2026-11-05T00:00:00Z"))
    # Antes de su inicio de validez, y cuando aún no se conocía, no rige.
    assert vigente(s, valido_en="2026-11-04T00:00:00Z", conocido_hasta=None)["clases"] == {}
    assert vigente(s, valido_en=DESPUES, conocido_hasta="2026-11-02T00:00:00Z")["clases"] == {}
    assert "planta" in vigente(s, valido_en=DESPUES, conocido_hasta="2026-11-04T00:00:00Z")["clases"]


def _modifica(ident, tipo, cuerpo, registrado="2026-11-02T00:00:00Z", **extra):
    mod = {"destino": "DEC-V#C1", "tipo": tipo} | ({"por": f"{ident}#C1"} if tipo == "sustitucion" else {})
    return decision(ident, {"C1": cuerpo}, registrado=registrado, modifica=[mod], **extra)


def test_una_clausula_sustituida_deja_de_definir_y_rige_la_definicion_nueva():
    renombra = _modifica("DEC-W", "sustitucion", "Una planta depuradora.", define=define({"termino": "depuradora"}))
    voc = vigente(snap(dec_v(), renombra), valido_en=DESPUES, conocido_hasta=None)
    assert list(voc["clases"]) == ["depuradora"] and voc["clases"]["depuradora"]["decision"] == "DEC-W"
    assert situacion(voc, "planta") == ("retirado", "planta")
    # Renombrar es sustituir con el nombre anterior como alias (C6): el nombre anterior sigue resolviendo.
    con_alias = _modifica(
        "DEC-W", "sustitucion", "Una planta depuradora.", define=define({"termino": "depuradora", "alias": ["planta"]})
    )
    voc = vigente(snap(dec_v(), con_alias), valido_en=DESPUES, conocido_hasta=None)
    assert situacion(voc, "planta") == ("vigente", "depuradora") and voc["retirados"] == []
    # Antes de que la sustituta se conociera, la definición anterior seguía rigiendo.
    previo = vigente(snap(dec_v(), con_alias), valido_en=DESPUES, conocido_hasta="2026-11-01T12:00:00Z")
    assert list(previo["clases"]) == ["planta"]


def test_una_clausula_derogada_retira_el_termino():
    voc = vigente(snap(dec_v(), _modifica("DEC-W", "derogacion", "Se deroga.")), valido_en=DESPUES, conocido_hasta=None)
    assert voc["clases"] == {} and voc["retirados"] == [
        {"termino": "planta", "definiciones": ["DEC-V#C1"], "alias": ["EDAR"]}
    ]
    assert situacion(voc, "EDAR") == ("retirado", "planta")


def test_dos_definiciones_distintas_que_rigen_dejan_el_termino_indeterminado():
    otra = decision("DEC-W", {"C1": "Otra cosa."}, define=define({"descripcion": "Edificio."}))
    voc = vigente(snap(dec_v(), otra), valido_en=DESPUES, conocido_hasta=None)
    assert voc["clases"] == {} and voc["declarado"] is True
    [ind] = voc["indeterminados"]
    assert ind["termino"] == "planta" and ind["definiciones"] == ["DEC-V#C1", "DEC-W#C1"]
    assert situacion(voc, "planta") == ("indeterminado", "planta")
    # La misma definición en dos decisiones no es un conflicto.
    igual = decision("DEC-W", {"C1": "Lo mismo."}, define=define({}))
    assert "planta" in vigente(snap(dec_v(), igual), valido_en=DESPUES, conocido_hasta=None)["clases"]


def test_un_alias_que_es_otro_termino_deja_indeterminados_los_dos():
    edar = decision("DEC-W", {"C1": "EDAR."}, define=define({"termino": "EDAR", "alias": []}))
    voc = vigente(snap(dec_v(), edar), valido_en=DESPUES, conocido_hasta=None)
    assert voc["clases"] == {} and [i["termino"] for i in voc["indeterminados"]] == ["EDAR", "planta"]


def test_una_validez_de_dia_ambigua_deja_el_termino_indeterminado():
    s = snap(dec_v(registrado="2026-11-03T00:00:00Z", valido="2026-11-05"))
    voc = vigente(s, valido_en="2026-11-05T06:00:00Z", conocido_hasta=None)
    assert voc["clases"] == {} and voc["declarado"] is True
    assert voc["indeterminados"][0]["motivo"] == "su vigencia no se puede decidir"
    assert any("TIEMPO_AMBIGUO" in a for a in voc["advertencias"])


def test_los_ambitos_son_los_de_los_roles_activos():
    propuesto = registro("rol", id="ROL-P", ambitos=["otro"], capacidades=["ratificar"], regla_aprobacion="uno")
    voc = vigente(snap(rol(), (propuesto, "")), valido_en=DESPUES, conocido_hasta=None)
    assert voc["ambitos"] == ["operaciones"]
    # Antes de activarse, el rol no cubre nada.
    assert vigente(snap(rol()), valido_en=DESPUES, conocido_hasta="2026-10-01T12:00:00Z")["ambitos"] == []


# Usos


def test_un_termino_no_declarado_se_senala_con_sus_usos():
    s = snap(rol(), dec_v(), entidad("ENT-1", "planta"), entidad("ENT-2", "Planta"), entidad("ENT-3", "EDAR"))
    voc = vigente(s, valido_en=DESPUES, conocido_hasta=None)
    rev = revisar(s, voc, conocido_hasta=None)
    assert rev["no_declarados"] == [{"termino": "Planta", "usos": ["ENT-2"]}]
    assert rev["indeterminados"] == [] and rev["retirados_en_uso"] == [] and rev["ambitos_sin_rol"] == []
    assert rev["cobertura"] == [] and rev["registros_examinados"] == 5


def test_en_mundo_abierto_no_se_senala_ninguna_clase():
    s = snap(rol(), entidad("ENT-2", "Planta"))
    rev = revisar(s, vigente(s, valido_en=DESPUES, conocido_hasta=None), conocido_hasta=None)
    assert rev["no_declarados"] == [] and rev["cobertura"] == [MUNDO_ABIERTO]


def test_un_termino_indeterminado_se_senala_con_sus_usos():
    otra = decision("DEC-W", {"C1": "Otra cosa."}, define=define({"descripcion": "Edificio."}))
    s = snap(rol(), dec_v(), otra, entidad("ENT-1", "EDAR"))
    rev = revisar(s, vigente(s, valido_en=DESPUES, conocido_hasta=None), conocido_hasta=None)
    assert [(i["termino"], i["usos"]) for i in rev["indeterminados"]] == [("planta", ["ENT-1"])]
    assert rev["no_declarados"] == []


def test_un_termino_retirado_no_saca_ningun_registro_de_la_base():
    s = snap(rol(), dec_v(), _modifica("DEC-W", "derogacion", "Se deroga."), entidad("ENT-1", "planta"))
    rev = revisar(s, vigente(s, valido_en=DESPUES, conocido_hasta=None), conocido_hasta=None)
    assert rev["retirados_en_uso"] == [{"termino": "planta", "usos": ["ENT-1"]}] and rev["no_declarados"] == []
    assert "ENT-1" in s.registros
    [res] = consultar(s, ["ENT-1"], valido_en=DESPUES, conocido_hasta=None)["resultados"]
    assert res["encontrado"] == "canonico" and res["estado"] == "activa"


def test_una_entidad_retirada_ya_no_usa_su_termino():
    retirada = activo("entidad", "ENT-R", clase_entidad="Planta")
    retirada["eventos"].append(
        {**retirada["eventos"][1], "evento_id": "E2", "estado_anterior": "activa", "estado_nuevo": "retirada"}
    )
    s = snap(rol(), dec_v(), (retirada, ""))
    assert revisar(s, vigente(s, valido_en=DESPUES, conocido_hasta=None), conocido_hasta=None)["no_declarados"] == []


def test_un_ambito_sin_rol_activo_se_senala():
    s = snap(rol(), entidad("ENT-1", "planta", ambito="Operaciones"))
    rev = revisar(s, vigente(s, valido_en=DESPUES, conocido_hasta=None), conocido_hasta=None)
    assert rev["ambitos_sin_rol"] == [{"ambito": "Operaciones", "usos": ["ENT-1"]}]


# Orden `vocabulario`


def _kb_vocabulario(raiz, *extra):
    return kb("vocabulario", str(raiz), "--carpeta", "kb", "--valido-en", DESPUES, *extra)


def test_la_orden_vocabulario_dice_lo_que_rige_y_lo_no_declarado(tmp_path):
    carpeta = tmp_path / "kb"
    for r, c in (rol(), dec_v(), entidad("ENT-1", "EDAR"), entidad("ENT-2", "Planta")):
        escribir(carpeta, r["id"], r, c)
    code, out = _kb_vocabulario(tmp_path)
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    res = out["resultado"]
    assert res["declarado"] is True and list(res["clases"]) == ["planta"] and res["alias"] == {"EDAR": "planta"}
    assert res["no_declarados"] == [{"termino": "Planta", "usos": ["ENT-2"]}]
    assert res["indeterminados"] == [] and res["ambitos_sin_rol"] == [] and res["ambitos"] == ["operaciones"]
    assert MUNDO_ABIERTO not in out["cobertura"]["no_evaluado"]
    # Con --ids no: la orden revisa toda la base.
    code, out = _kb_vocabulario(tmp_path, "--ids", "ENT-1")
    assert code == 2 and out["resultado"]["estado"] == "bloqueado"


def test_la_orden_vocabulario_en_mundo_abierto_lo_dice(tmp_path):
    carpeta = tmp_path / "kb"
    for r, c in (rol(), entidad("ENT-2", "Planta")):
        escribir(carpeta, r["id"], r, c)
    code, out = _kb_vocabulario(tmp_path, "--conocido-hasta", DESPUES)
    assert code == 0 and out["resultado"]["declarado"] is False, out
    assert out["resultado"]["no_declarados"] == [] and MUNDO_ABIERTO in out["cobertura"]["no_evaluado"]


def test_la_orden_vocabulario_sin_registros_es_parcial(tmp_path):
    (tmp_path / "kb").mkdir()
    code, out = _kb_vocabulario(tmp_path)
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert any("ningún registro examinado" in a for a in out["advertencias"])

