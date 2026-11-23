"""La tabla de referencias de `modelo` es la única fuente de los nombres de relaciones y campos con destino.

Las vistas que se derivan de ella conservan los valores y el orden que tenían escritos a mano (revisión 6278bfc): aquí
están congelados. El orden se compara donde se observa: en las tuplas que se recorren para informar y en las claves
de los mapas que se recorren.
"""

from kbol import consultar, impacto, modelo, mutabilidad, referencias, soporte
from kbol.modelo import CICLOS, FORMAS, REFERENCIAS, TIPOS

RELACIONES = {
    "resuelta_por": {"origen": ("pregunta",), "destino": ("decision",), "ancla": "prohibida"},
    "cuestiona": {"origen": ("pregunta",), "destino": ("decision",), "ancla": "obligatoria"},
    "deja_obsoleta": {"origen": ("decision", "hecho", "fuente"), "destino": "mismo", "ancla": "prohibida"},
    "pone_a_prueba": {"origen": ("hipotesis",), "destino": ("decision",), "ancla": "obligatoria"},
    "basada_en": {
        "origen": ("decision", "hecho", "hipotesis", "pregunta"),
        "destino": ("fuente", "hecho"),
        "ancla": "opcional",
    },
    "derivada_de": {"origen": ("fuente",), "destino": ("fuente",), "ancla": "prohibida"},
    "afecta_a": {"origen": ("decision", "hecho", "pregunta"), "destino": None, "ancla": "opcional"},
    "autorizado_por": {"origen": ("decision", "plan", "hito"), "destino": ("rol",), "ancla": "prohibida"},
    "cierra": {"origen": ("hito",), "destino": ("pregunta",), "ancla": "prohibida"},
    "avanza": {"origen": ("hito",), "destino": ("pregunta",), "ancla": "prohibida"},
    "somete_a_prueba": {"origen": ("hito",), "destino": ("hipotesis",), "ancla": "prohibida"},
    "produce": {"origen": ("hito",), "destino": None, "ancla": "opcional"},
    "se_apoya_en": {"origen": ("plan",), "destino": ("decision",), "ancla": "opcional"},
}
VINCULOS = ("cierra", "avanza", "somete_a_prueba", "produce", "se_apoya_en")
RELACIONES_OBJETO = {
    "modifica": ("decision",),
    "depende_de": ("pregunta", "decision", "plan", "hito"),
    "ocupa": ("persona",),
    "veta": ("decision",),
    "define": ("decision",),
}
SIN_CICLOS = ("deja_obsoleta", "modifica", "derivada_de", "depende_de")
CONSUMO = (
    "depende_de",
    "basada_en",
    "dependencias",
    "sources",
    "cuestiona",
    "pone_a_prueba",
    "derivada_de",
    "resuelta_por",
    "autorizado_por",
    "ocupa",
    "se_apoya_en",
    "cierra",
    "avanza",
    "somete_a_prueba",
    "produce",
)
DESTINO_ESPERADO = {
    "ocupa": ("rol",),
    "hitos": ("hito",),
    "responsable": ("rol", "persona"),
    "modifica": ("decision",),
    "cuerpo": ("hecho",),
}
RELACIONES_CONSULTA = (*RELACIONES, "modifica", "depende_de", "ocupa", "hitos", "define")
LIBRES = {"title", "description", "generated", "verified", "stale_after", "status", "evaluaciones", "eventos"}
LIBRES |= set(VINCULOS) | {"responsable", "evidencia", "implementacion"}
APOYOS = ("basada_en", "dependencias", "sources")


def test_las_vistas_de_modelo_conservan_valores_y_orden():
    assert modelo.RELACIONES == RELACIONES and list(modelo.RELACIONES) == list(RELACIONES)
    assert modelo.RELACIONES_OBJETO == RELACIONES_OBJETO and list(modelo.RELACIONES_OBJETO) == list(RELACIONES_OBJETO)
    assert modelo.VINCULOS == VINCULOS
    # El orden de SIN_CICLOS es el de los hallazgos de ciclo en `validar_snapshot`.
    assert modelo.SIN_CICLOS == SIN_CICLOS


def test_las_vistas_de_los_consumidores_conservan_valores_y_orden():
    # `impacto` solo pregunta si alguna referencia coincide: el orden de CONSUMO no se observa.
    assert isinstance(impacto.CONSUMO, tuple) and set(impacto.CONSUMO) == set(CONSUMO)
    assert len(impacto.CONSUMO) == len(CONSUMO)
    assert referencias.DESTINO_ESPERADO == DESTINO_ESPERADO
    # El orden de las relaciones es el de la salida de `consultar`.
    assert consultar._RELACIONES == RELACIONES_CONSULTA
    assert mutabilidad.LIBRES == LIBRES
    assert soporte.CAMPOS == APOYOS


def test_aristas_recorre_en_el_orden_de_siempre():
    sintesis = {
        "type": "sintesis",
        "dependencias": ["HE-1", 7],
        "sources": [{"id": "s1", "resource": "F-1"}, {"id": "s2"}, "F-x"],
        "resuelta_por": ["DEC-1"],
        "basada_en": ["F-2"],
        "se_apoya_en": ["DEC-2"],
        "modifica": [{"destino": "DEC-3#C1"}, {"destino": None}],
        "depende_de": [{"destino": "Q-1"}],
        "ocupa": [{"rol": "ROL-1"}],
        "veta": [{"patron": "x"}],
        "responsable": "ROL-2",
        "hitos": ["HI-1"],
    }
    cuerpo = '<hecho ref="HE-2">texto</hecho>'
    assert list(referencias.aristas(sintesis, cuerpo)) == [
        ("dependencias", "HE-1"),
        ("sources", "F-1"),
        ("cuerpo", "HE-2"),
        ("resuelta_por", "DEC-1"),
        ("basada_en", "F-2"),
        ("se_apoya_en", "DEC-2"),
        ("modifica", "DEC-3#C1"),
        ("depende_de", "Q-1"),
        ("ocupa", "ROL-1"),
    ]
    # Los campos propios solo cuentan en los tipos que los declaran; las relaciones, en cualquiera.
    plan = {"type": "plan", "hitos": ["HI-1"], "responsable": "ROL-2", "dependencias": ["HE-1"], "cuestiona": ["X"]}
    assert list(referencias.aristas(plan)) == [("cuestiona", "X"), ("hitos", "HI-1")]
    pregunta = {"type": "pregunta", "responsable": "ROL-2", "hitos": ["HI-1"]}
    assert list(referencias.aristas(pregunta)) == [("responsable", "ROL-2")]
    # Sin cuerpo no hay citas; con una marca rota tampoco, y no es un error.
    assert ("cuerpo", "HE-2") not in list(referencias.aristas(sintesis))
    assert ("cuerpo", "HE-2") not in list(referencias.aristas(sintesis, '<hecho ref="HE-2">sin cierre'))


def test_cada_entrada_de_la_tabla_tiene_una_forma_coherente():
    for campo, r in REFERENCIAS.items():
        assert r.forma in FORMAS, campo
        assert r.origen is None or (r.origen and set(r.origen) <= set(TIPOS)), campo
        assert r.destino in (None, "mismo") or (r.destino and set(r.destino) <= set(TIPOS)), campo
        assert r.sin_ciclos in (None, *CICLOS), campo
        if r.forma != "objetos":
            assert r.clave is None, campo
        tiene_destino = r.forma != "objetos" or r.clave is not None
        if tiene_destino:
            assert r.ancla in ("prohibida", "obligatoria", "opcional"), campo
        else:
            # Un objeto sin clave de destino (`veta`) no apunta a nada: ni ancla, ni tipo, ni efectos en el grafo.
            assert r.ancla is None and r.destino is None, campo
            assert not (r.consumo or r.sin_ciclos or r.evidencia), campo
        if r.relacion:
            # La forma de una relación la da la tabla: lista de IDs o de objetos, con sus tipos de origen.
            assert r.forma in ("ids", "objetos") and r.origen, campo
        else:
            # Un campo propio no tiene regla de ciclos ni la forma de lista de objetos sin destino.
            assert r.sin_ciclos is None, campo


def test_los_literales_ordenados_no_se_apartan_de_la_tabla():
    """El orden de informe se escribe a mano; el contenido lo fija la tabla."""
    evidencia = {c for c, r in REFERENCIAS.items() if r.evidencia and r.forma != "cuerpo"}
    assert set(soporte.CAMPOS) == evidencia
    assert set(consultar._RELACIONES) <= set(REFERENCIAS)
