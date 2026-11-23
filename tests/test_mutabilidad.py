"""VAL-03: qué puede cambiar una propuesta frente a la base (matriz de mutabilidad del núcleo 0.7)."""

import copy

from conftest import decision, evento, registro

from kbol.mutabilidad import comparar
from kbol.proyeccion import Snapshot


def snap(pares, revision):
    return Snapshot({r["id"]: r for r, _ in pares}, revision, {r["id"]: c for r, c in pares})


def errores(res):
    return [h for h in res["hallazgos"] if h["severidad"] == "error"]


def base_y_copia(*pares):
    base = snap(pares, "base")
    return base, copy.deepcopy(base)


def test_sin_cambios_sin_hallazgos():
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    res = comparar(base, Snapshot(prop.registros, "prop", prop.cuerpos))
    assert res["hallazgos"] == [] and res["modificados"] == [] and res["nuevos"] == []


def test_clausula_aceptada_no_se_reescribe_ni_se_elimina_ni_se_anade():
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes.", "C2": "Datos verificados."}))
    for cuerpo in (
        '<clausula id="C1">\nMartes.\n</clausula>\n<clausula id="C2">\nDatos verificados.\n</clausula>\n',
        '<clausula id="C1">\nLunes.\n</clausula>\n',
        '<clausula id="C1">\nLunes.\n</clausula>\n<clausula id="C2">\nDatos verificados.\n</clausula>\n<clausula id="C3">\nX.\n</clausula>\n',
    ):
        prop.cuerpos["DEC-A"] = cuerpo
        assert any(h["control"] == "VAL-03" for h in errores(comparar(base, prop))), cuerpo


def test_prosa_fuera_de_clausulas_titulo_y_descripcion_si_cambian():
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    prop.cuerpos["DEC-A"] = "Contexto nuevo.\n\n" + prop.cuerpos["DEC-A"]
    prop.registros["DEC-A"]["title"] = "Título corregido"
    prop.registros["DEC-A"]["description"] = "Descripción corregida."
    res = comparar(base, prop)
    assert errores(res) == [] and res["modificados"] == ["DEC-A"]


def test_campos_normativos_de_una_aceptada_protegidos():
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    prop.registros["DEC-A"]["autorizado_por"] = ["ROL-OTRO"]
    prop.registros["DEC-A"]["modifica"] = [{"destino": "DEC-Z#C1", "tipo": "derogacion"}]
    rutas = {h["ruta"] for h in errores(comparar(base, prop))}
    assert {"DEC-A/autorizado_por", "DEC-A/modifica"} <= rutas


def test_una_propuesta_se_edita_libremente():
    base, prop = base_y_copia(decision("DEC-P", {"C1": "x"}, estado="propuesta"))
    prop.cuerpos["DEC-P"] = '<clausula id="C1">\ny\n</clausula>\n'
    prop.registros["DEC-P"]["criterios"] = ["otro"]
    assert errores(comparar(base, prop)) == []


def test_eventos_append_only_y_solo_de_la_integracion():
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    prop.registros["DEC-A"]["eventos"][0]["motivo"] = "reescrito"
    assert any("eventos" in h["ruta"] for h in errores(comparar(base, prop)))
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    prop.registros["DEC-A"]["eventos"].append(
        evento("revocacion_aprobacion", evento_id="E9", registrado_en=None, aprobacion_id="AP-DEC-A")
    )
    assert any("integración" in h["mensaje"] for h in errores(comparar(base, prop)))


def test_estado_no_se_edita():
    base, prop = base_y_copia(decision("DEC-P", {"C1": "x"}, estado="propuesta"))
    prop.registros["DEC-P"]["estado"] = "aceptada"
    assert any(h["ruta"] == "DEC-P/estado" for h in errores(comparar(base, prop)))


def test_registro_no_se_borra_ni_cambia_de_tipo():
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    del prop.registros["DEC-A"]
    assert errores(comparar(base, prop))
    base, prop = base_y_copia(decision("DEC-A", {"C1": "Lunes."}))
    prop.registros["DEC-A"]["type"] = "hecho"
    assert errores(comparar(base, prop))


def test_huella_de_fuente_inmutable_y_puntero_movible():
    f = registro(
        "fuente", eventos=[evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="registrada")]
    )
    base, prop = base_y_copia((f, ""))
    prop.registros["F-A"]["sha256"] = "c" * 64
    assert errores(comparar(base, prop))
    base, prop = base_y_copia((f, ""))
    prop.registros["F-A"]["ubicacion"] = "fuentes/movida/F-A.pdf"
    res = comparar(base, prop)
    assert errores(res) == [] and any("VAL-10" in h["mensaje"] for h in res["hallazgos"])


def test_registro_nuevo_sin_eventos_fabricados():
    base, prop = base_y_copia()
    nuevo, cuerpo = decision("DEC-N", {"C1": "x"}, estado="propuesta")
    prop.registros["DEC-N"], prop.cuerpos["DEC-N"] = nuevo, cuerpo
    res = comparar(base, prop)
    assert res["nuevos"] == ["DEC-N"] and any("integración" in h["mensaje"] for h in errores(res))
    nuevo["eventos"] = []
    assert errores(comparar(base, prop)) == []


def test_cambio_de_politica_se_marca_para_autoridad_previa():
    rol = registro("rol", eventos=[evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")])
    base, prop = base_y_copia((rol, ""))
    prop.registros["ROL-EJEMPLO"]["capacidades"] = ["ratificar", "administrar"]
    res = comparar(base, prop)
    assert res["cambios_de_politica"] == ["ROL-EJEMPLO"]
    assert any(
        h["codigo"] == "AUTORIDAD_INSUFICIENTE" and h["severidad"] == "requiere_autoridad" for h in res["hallazgos"]
    )
