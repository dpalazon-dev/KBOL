"""Vocabulario del dominio en la puerta de integración y en el paquete de aprobación.

Rige el vocabulario del árbol final: la decisión que define un término puede entrar con su primer uso. Solo bloquea
el paso de una entidad a `activa` con una clase que no rige en el inicio de validez de ese efecto; lo demás entra con
el aviso en el recibo.
"""

# ruff: noqa: F811  (el fixture se importa de test_integrar)

import pytest
from conftest import decision, registro
from test_integrar import ACEPTAR, _base_con, activo, canonico, entorno, llamar, proponer, solicitud  # noqa: F401
from test_vocabulario import define

from kbol.core import serializar
from kbol.integrar import arbol_final, motivos_decisivos, preparar_solicitud
from kbol.paquete import preparar_aprobacion, presentar
from kbol.schema import validar
from kbol.vocabulario import vigente

ACTIVAR = [{"estado_anterior": "propuesta", "estado_nuevo": "activa", "valido_desde": "2026-11-05T00:00:00Z"}]
CORTE = "2026-11-06T00:00:00Z"


def dec_v(ident="DEC-V", entrada=None):
    """(registro, cuerpo) de una decisión propuesta que define en su C1 `planta` o lo que diga `entrada`."""
    r = registro("decision", id=ident, autorizado_por=["ROL-OP"], define=define(entrada or {}))
    return r, '<clausula id="C1">\nUna planta trata agua.\n</clausula>\n'


def aceptada(ident="DEC-V", **campos):
    return decision(
        ident,
        {"C1": "Una planta trata agua."},
        registrado="2026-10-04T00:00:00Z",
        autorizado_por=["ROL-OP"],
        define=define(campos.pop("define", {})),
        **campos,
    )


def ent(ident, clase):
    return registro("entidad", id=ident, clase_entidad=clase)


def cerrada(repo, base, *extra):
    """Base con `planta` declarada (mundo cerrado) y lo que se añada, ya integrado."""
    archivos = {"kb/DEC-V.md": canonico(*aceptada())}
    for r, c in extra:
        archivos[f"kb/{r['id']}.md"] = canonico(r, c)
    return _base_con(repo, base, archivos)


def propuesta(repo, base, registros, efectos, op="op-1"):
    archivos = {f"kb/{r['id']}.md": serializar(r, c) for r, c in registros}
    return proponer(repo, base, {**archivos, **solicitud(op, efectos)})


def avisos_de_vocabulario(res):
    return [a for a in res["advertencias"] if "clase_entidad" in a or "ámbito" in a]


def test_la_definicion_y_su_primer_uso_entran_en_la_misma_integracion(entorno):
    repo, base, recibos = entorno
    prop = propuesta(repo, base, [dec_v(), (ent("ENT-X", "EDAR"), "")], {"DEC-V": ACEPTAR, "ENT-X": ACTIVAR})
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "integrado", res
    assert avisos_de_vocabulario(res) == []


def test_una_entidad_propuesta_con_un_termino_no_declarado_entra_con_aviso(entorno):
    repo, base, recibos = entorno
    base2 = cerrada(repo, base)
    prop = propuesta(repo, base2, [(ent("ENT-Y", "Planta"), "")], {})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "integrado", res
    assert avisos_de_vocabulario(res) == ["ENT-Y: término no declarado en clase_entidad: 'Planta'"]


def test_activar_una_entidad_con_un_termino_no_declarado_bloquea(entorno):
    repo, base, recibos = entorno
    base2 = cerrada(repo, base)
    prop = propuesta(repo, base2, [(ent("ENT-Y", "Planta"), "")], {"ENT-Y": ACTIVAR})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO", res
    assert res["motivo"].startswith("ENT-Y: término no declarado en clase_entidad: 'Planta'")
    assert repo.git("rev-parse", "canon") == base2 and not (recibos / "op-1.json").exists()


def test_un_termino_que_solo_define_una_decision_propuesta_no_rige(entorno):
    repo, base, recibos = entorno
    base2 = cerrada(repo, base)
    nueva = dec_v("DEC-P", {"termino": "depuradora", "alias": []})
    prop = propuesta(repo, base2, [nueva, (ent("ENT-Y", "depuradora"), "")], {"ENT-Y": ACTIVAR})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO", res
    assert "término no declarado" in res["motivo"] and "'depuradora'" in res["motivo"]


def test_un_termino_indeterminado_cuenta_como_no_declarado(entorno):
    repo, base, recibos = entorno
    base2 = cerrada(repo, base, aceptada("DEC-W", define={"descripcion": "Edificio."}))
    prop = propuesta(repo, base2, [(ent("ENT-Y", "planta"), "")], {"ENT-Y": ACTIVAR})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO", res
    assert res["motivo"].startswith("ENT-Y: término indeterminado en clase_entidad: 'planta'")
    assert repo.git("rev-parse", "canon") == base2


def test_en_mundo_abierto_todo_entra_como_antes(entorno):
    repo, base, recibos = entorno
    prop = propuesta(repo, base, [(ent("ENT-Y", "lo-que-sea"), "")], {"ENT-Y": ACTIVAR})
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "integrado", res
    assert res["advertencias"] == []


def test_retirar_un_termino_en_uso_lista_los_usos_afectados_en_el_recibo(entorno):
    repo, base, recibos = entorno
    base2 = cerrada(repo, base, (activo("entidad", "ENT-1", clase_entidad="planta"), ""))
    deroga = registro(
        "decision",
        id="DEC-W",
        autorizado_por=["ROL-OP"],
        modifica=[{"destino": "DEC-V#C1", "tipo": "derogacion"}],
    )
    prop = propuesta(repo, base2, [(deroga, '<clausula id="C1">\nSe deroga.\n</clausula>\n')], {"DEC-W": ACEPTAR})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "integrado", res
    aviso = "ENT-1: término retirado, que ya no rige en clase_entidad: 'planta'; uso afectado por esta operación"
    assert avisos_de_vocabulario(res) == [aviso]


def _sin_advertencias(voc):
    return {k: v for k, v in voc.items() if k not in ("advertencias", "cortes")}


@pytest.mark.parametrize(
    "caso",
    ["acepta_definicion", "definicion_propuesta", "activa_entidad", "deroga", "entidad_sin_efecto"],
)
def test_el_vocabulario_solo_cambia_con_algo_decisivo(entorno, caso):
    """Invariante: si el vocabulario del árbol final no es el de la base, algún registro tocado es decisivo."""
    repo, base, _ = entorno
    base2 = cerrada(repo, base)
    deroga = registro(
        "decision", id="DEC-W", autorizado_por=["ROL-OP"], modifica=[{"destino": "DEC-V#C1", "tipo": "derogacion"}]
    )
    otra = dec_v("DEC-N", {"termino": "depuradora", "alias": []})
    casos = {
        "acepta_definicion": ([otra], {"DEC-N": ACEPTAR}, True),
        "definicion_propuesta": ([otra], {}, False),
        "activa_entidad": ([(ent("ENT-Y", "planta"), "")], {"ENT-Y": ACTIVAR}, False),
        "deroga": ([(deroga, '<clausula id="C1">\nSe deroga.\n</clausula>\n')], {"DEC-W": ACEPTAR}, True),
        "entidad_sin_efecto": ([(ent("ENT-Y", "Planta"), "")], {}, False),
    }
    registros, efectos, cambia = casos[caso]
    prop = propuesta(repo, base2, registros, efectos)
    p = preparar_solicitud(repo.raiz, carpeta="kb", operacion_id="op-1", base=base2, propuesta=prop)
    final, _, _ = arbol_final(p)
    antes = _sin_advertencias(vigente(p.base_snap, valido_en=CORTE, conocido_hasta=None))
    despues = _sin_advertencias(vigente(final, valido_en=CORTE, conocido_hasta=None))
    assert (antes != despues) == cambia
    if antes != despues:
        assert any(p.motivos_decisivos(i) for i in p.tocados)


def _paquete(repo, base, prop, op="op-1"):
    return preparar_aprobacion(repo.raiz, carpeta="kb", operacion_id=op, base=base, propuesta=prop, valido_en=CORTE)


def test_el_paquete_bloquea_como_la_puerta_y_lista_los_hallazgos(entorno):
    repo, base, recibos = entorno
    base2 = cerrada(repo, base)
    prop = propuesta(repo, base2, [(ent("ENT-Y", "Planta"), "")], {"ENT-Y": ACTIVAR})
    paq = _paquete(repo, base2, prop)
    puerta = llamar(repo, base2, prop, recibos)
    assert paq["estado"] == puerta["estado"] == "bloqueado"
    assert paq["codigo"] == puerta["codigo"] == "ESQUEMA_INVALIDO" and paq["motivo"] == puerta["motivo"]
    sin_efecto = propuesta(repo, base2, [(ent("ENT-Y", "Planta"), "")], {}, op="op-2")
    paq = _paquete(repo, base2, sin_efecto, op="op-2")
    assert paq["estado"] == "completado", paq
    assert paq["vocabulario"] == [
        {"id": "ENT-Y", "campo": "clase_entidad", "valor": "Planta", "situacion": "no_declarado", "tocado": True}
    ]
    texto = presentar(paq)
    assert "Vocabulario del dominio:\n- ENT-Y: término no declarado en clase_entidad: 'Planta'" in texto


def test_el_paquete_sin_hallazgos_no_anade_la_seccion(entorno):
    repo, base, _ = entorno
    prop = propuesta(repo, base, [dec_v(), (ent("ENT-X", "planta"), "")], {"DEC-V": ACEPTAR, "ENT-X": ACTIVAR})
    paq = _paquete(repo, base, prop)
    assert paq["estado"] == "completado" and paq["vocabulario"] == [], paq
    assert "Vocabulario del dominio" not in presentar(paq)


ANTES_DE_DEFINIR = [{"estado_anterior": "propuesta", "estado_nuevo": "activa", "valido_desde": "2026-09-01T00:00:00Z"}]


def test_fechar_la_activacion_antes_de_la_definicion_no_abre_el_mundo(entorno):
    """El inicio de validez lo elige quien propone: con el mundo cerrado al integrar, una clase sin declarar bloquea."""
    repo, base, recibos = entorno
    base2 = cerrada(repo, base)
    prop = propuesta(repo, base2, [(ent("ENT-Y", "Planta"), "")], {"ENT-Y": ANTES_DE_DEFINIR})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO", res
    assert "ENT-Y" in res["motivo"] and "Planta" in res["motivo"]


def test_una_clase_declarada_no_rige_antes_de_su_definicion(entorno):
    """La clase tiene que regir en el inicio de validez del efecto y al integrar (C4), no solo hoy."""
    repo, base, recibos = entorno
    base2 = cerrada(repo, base)
    prop = propuesta(repo, base2, [(ent("ENT-Y", "planta"), "")], {"ENT-Y": ANTES_DE_DEFINIR})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO", res
    assert "2026-09-01" in res["motivo"]


def test_una_importacion_que_trae_define_es_decisiva():
    """Lo que fija el vocabulario pide aprobación también en el modo de solo lo decisivo."""
    con_define, _ = dec_v("DEC-H")
    sin_define = registro("decision", id="DEC-H", autorizado_por=["ROL-OP"])
    assert motivos_decisivos("DEC-H", con_define, {}, set(), {"DEC-H": {}})
    assert not motivos_decisivos("DEC-H", sin_define, {}, set(), {"DEC-H": {}})


@pytest.mark.parametrize("nombre", ["sensor ", " sensor", "entidad "])
def test_un_termino_con_espacios_alrededor_se_rechaza(nombre):
    r, cuerpo = dec_v(entrada={"termino": nombre})
    errores = [h for h in validar(r, cuerpo) if h["severidad"] == "error"]
    assert any("espacios" in h["mensaje"] for h in errores), errores


def test_una_entidad_activa_no_cambia_a_una_clase_que_no_rige(entorno):
    """Activar con una clase declarada y cambiarla después sería activar en dos pasos con una que no rige."""
    repo, base, recibos = entorno
    base2 = cerrada(repo, base, (activo("entidad", "ENT-1", clase_entidad="planta"), ""))
    cambiada = activo("entidad", "ENT-1", clase_entidad="Pozo")
    prop = proponer(repo, base2, {"kb/ENT-1.md": canonico(cambiada, "")})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO", res
    assert "ENT-1" in res["motivo"] and "Pozo" in res["motivo"]


def test_una_entidad_activa_puede_cambiar_a_otra_clase_que_rige(entorno):
    repo, base, recibos = entorno
    v, cuerpo = aceptada(define={"alias": ["estacion"]})
    base2 = _base_con(
        repo,
        base,
        {"kb/DEC-V.md": canonico(v, cuerpo), "kb/ENT-1.md": canonico(activo("entidad", "ENT-1", clase_entidad="planta"), "")},
    )
    prop = proponer(repo, base2, {"kb/ENT-1.md": canonico(activo("entidad", "ENT-1", clase_entidad="estacion"), "")})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "integrado", res
