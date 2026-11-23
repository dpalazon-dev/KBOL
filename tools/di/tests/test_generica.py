"""Un PDF que no es una norma: su estructura genérica y la resolución de sus citas con el resolutor del núcleo."""

import hashlib

from di.generica import estructura_generica
from di.localizar import localizar

from kbol.citas import resolver_pdf
from kbol.localizador import LocalizadorInvalido, parsear

ORIGINAL = b"%PDF-1.7 informe de prueba"
SHA = hashlib.sha256(ORIGINAL).hexdigest()
ANCHO, ALTO = 600.0, 800.0


def _caja(izq, arriba, der, abajo):
    """Caja con origen arriba a la izquierda, en fracciones de la página."""
    return {"l": izq * ANCHO, "t": arriba * ALTO, "r": der * ANCHO, "b": abajo * ALTO, "coord_origin": "TOPLEFT"}


def _texto(i, texto, etiqueta="text", page=1, caja=(0.1, 0.1, 0.9, 0.15), marker=None, hijos=()):
    item = {
        "self_ref": f"#/texts/{i}",
        "label": etiqueta,
        "text": texto,
        "prov": [{"page_no": page, "bbox": _caja(*caja)}],
        "children": [{"$ref": h} for h in hijos],
    }
    if marker:
        item["marker"] = marker
    return item


def _celda(texto, fila, col, cabecera=False, caja=(0.1, 0.5, 0.2, 0.52)):
    return {
        "text": texto,
        "start_row_offset_idx": fila,
        "start_col_offset_idx": col,
        "column_header": cabecera,
        "bbox": _caja(*caja),
    }


def _tabla(i, filas, page=1, caja=(0.1, 0.5, 0.9, 0.7), hijos=()):
    return {
        "self_ref": f"#/tables/{i}",
        "label": "table",
        "prov": [{"page_no": page, "bbox": _caja(*caja)}],
        "children": [{"$ref": h} for h in hijos],
        "data": {"grid": filas},
    }


def _doc(cuerpo, textos, tablas=(), figuras=(), paginas=2):
    return {
        "pages": {str(p): {"size": {"width": ANCHO, "height": ALTO}, "page_no": p} for p in range(1, paginas + 1)},
        "texts": list(textos),
        "tables": list(tablas),
        "pictures": list(figuras),
        "groups": [],
        "body": {"children": [{"$ref": r} for r in cuerpo]},
    }


def _informe():
    textos = [
        _texto(0, "Informe de rendimiento", "title"),
        _texto(1, "Este informe resume las mediciones de la campaña.", caja=(0.1, 0.2, 0.9, 0.25)),
        _texto(2, "1 Resultados", "section_header", caja=(0.1, 0.3, 0.9, 0.33)),
        _texto(3, "El método reduce el tiempo de entrenamiento 547 veces de media.", caja=(0.1, 0.35, 0.9, 0.4)),
        _texto(4, "Tabla 1: Conjuntos de datos", "caption", caja=(0.1, 0.45, 0.9, 0.48)),
        _texto(5, "2 Conclusiones", "section_header", page=2),
        _texto(6, "No se observaron regresiones.", page=2, caja=(0.1, 0.2, 0.9, 0.25)),
        _texto(7, "Página 1 de 2", "page_footer", caja=(0.1, 0.95, 0.9, 0.98)),
    ]
    tabla = _tabla(
        0,
        [
            [_celda("Conjunto", 0, 0, True), _celda("Muestras", 0, 1, True)],
            [_celda("SWaT", 1, 0), _celda("496800", 1, 1)],
        ],
        hijos=["#/texts/4"],
    )
    cuerpo = ["#/texts/0", "#/texts/1", "#/texts/2", "#/texts/3", "#/tables/0", "#/texts/5", "#/texts/6"]
    return _doc(cuerpo, textos, [tabla])


def _ancla(doc, literal):
    (hallazgo,) = localizar(doc, literal)
    (region,) = hallazgo
    return f"pdf-v1:p={region['p']};r={','.join(region['r'])}"


def _resolver(est, ancla, literal):
    return resolver_pdf(parsear(ancla), sha256_original=SHA, ruta_original=None, estructura=est, literal=literal)


def test_secciones_tablas_y_paginas():
    est = estructura_generica(_informe(), SHA, corregir=False)
    assert est["perfil"] == "estructura-v1"
    unidades = {u["clave"]: u for u in est["unidades"]}
    assert list(unidades) == ["seccion=1;pagina=1", "seccion=2;pagina=1", "seccion=2;tabla=1", "seccion=3;pagina=2"]
    assert unidades["seccion=1;pagina=1"]["titulo"] == "Informe de rendimiento"
    assert unidades["seccion=2;pagina=1"]["paginas"] == [1] and unidades["seccion=3;pagina=2"]["paginas"] == [2]
    assert "547 veces" in unidades["seccion=2;pagina=1"]["texto"]
    assert "Conjunto | Muestras" in unidades["seccion=2;pagina=1"]["texto"]
    assert "Conjunto | Muestras" in unidades["seccion=2;tabla=1"]["texto"]
    assert "Tabla 1: Conjuntos de datos" in unidades["seccion=2;tabla=1"]["texto"]
    assert "Página 1 de 2" not in "".join(u["texto"] for u in est["unidades"])
    assert unidades["seccion=2;tabla=1"]["regiones"] == [{"p": 1, "r": ["0.1000", "0.4500", "0.9000", "0.7000"]}]


def test_cita_de_un_pdf_que_no_es_norma_se_resuelve():
    doc = _informe()
    est = estructura_generica(doc, SHA, corregir=False)
    literal = "reduce el tiempo de entrenamiento 547 veces"
    resultado = _resolver(est, _ancla(doc, literal), literal)
    # Sin el original en esta máquina la integridad no se comprueba, pero la estructura es conforme.
    assert resultado.estado == "no_comprobable" and "estructura conforme" in resultado.motivo


def test_cita_resuelta_con_el_original(tmp_path):
    doc = _informe()
    est = estructura_generica(doc, SHA, corregir=False)
    ruta = tmp_path / "original.pdf"
    ruta.write_bytes(ORIGINAL)
    literal = "496800"
    r = resolver_pdf(
        parsear(_ancla(doc, literal)), sha256_original=SHA, ruta_original=ruta, estructura=est, literal=literal
    )
    assert r.estado == "resuelta"


def test_pagina_equivocada_o_literal_inventado_siguen_rotas():
    doc = _informe()
    est = estructura_generica(doc, SHA, corregir=False)
    literal = "reduce el tiempo de entrenamiento 547 veces"
    assert _resolver(est, "pdf-v1:p=2", literal).estado == "rota"
    assert _resolver(est, "pdf-v1:p=1", "reduce el tiempo de entrenamiento 600 veces").estado == "rota"
    assert _resolver(est, "pdf-v1:p=3", literal).estado == "rota"


def test_las_claves_genericas_no_son_un_localizador_de_norma():
    est = estructura_generica(_informe(), SHA, corregir=False)
    for unidad in est["unidades"]:
        try:
            parsear(f"norma-v1:{unidad['clave']}")
        except LocalizadorInvalido:
            continue
        raise AssertionError(f"{unidad['clave']} se puede citar como norma-v1")


def test_contenido_antes_del_primer_titulo():
    textos = [_texto(0, "Texto sin título previo."), _texto(1, "1 Alcance", "section_header", caja=(0.1, 0.3, 0.9, 0.33))]
    est = estructura_generica(_doc(["#/texts/0", "#/texts/1"], textos), SHA, corregir=False)
    assert [(u["clave"], u["titulo"]) for u in est["unidades"]] == [
        ("seccion=0;pagina=1", None),
        ("seccion=1;pagina=1", "1 Alcance"),
    ]


def test_pagina_equivocada_dentro_de_la_misma_seccion_es_rota():
    textos = [
        _texto(0, "1 Método", "section_header"),
        _texto(1, "La primera fase entrena los dos autoencoders.", caja=(0.1, 0.2, 0.9, 0.3)),
        _texto(2, "La segunda fase es adversaria.", page=2, caja=(0.1, 0.1, 0.9, 0.2)),
    ]
    partido = _texto(3, "Este párrafo empieza en una página y termina en la siguiente.", page=2, caja=(0.1, 0.8, 0.9, 0.9))
    partido["prov"].append({"page_no": 3, "bbox": _caja(0.1, 0.1, 0.9, 0.15)})
    doc = _doc([f"#/texts/{i}" for i in range(4)], [*textos, partido], paginas=3)
    est = estructura_generica(doc, SHA)
    assert [u["clave"] for u in est["unidades"]] == ["seccion=1;pagina=1", "seccion=1;pagina=2", "seccion=1;pagina=3"]
    assert _resolver(est, "pdf-v1:p=2", "La segunda fase es adversaria").estado == "no_comprobable"
    assert _resolver(est, "pdf-v1:p=1", "La segunda fase es adversaria").estado == "rota"
    # El párrafo partido entre las páginas 2 y 3 se cita en cualquiera de las dos, y en ninguna otra.
    for pagina, estado in ((2, "no_comprobable"), (3, "no_comprobable"), (1, "rota")):
        assert _resolver(est, f"pdf-v1:p={pagina}", "termina en la siguiente").estado == estado


def _dos_columnas():
    """Página a dos columnas que Docling entrega mal: la introducción antes del resumen y la tabla lejos de su texto."""
    izq, der = (0.08, 0.48), (0.52, 0.92)
    textos = [
        _texto(0, "Detección de anomalías", "title", caja=(0.1, 0.05, 0.9, 0.1)),
        _texto(1, "1 INTRODUCCIÓN", "section_header", caja=(der[0], 0.15, der[1], 0.18)),
        _texto(2, "La supervisión es un reto.", caja=(der[0], 0.2, der[1], 0.5)),
        _texto(3, "RESUMEN", "section_header", caja=(izq[0], 0.15, izq[1], 0.18)),
        _texto(4, "Proponemos un método.", caja=(izq[0], 0.2, izq[1], 0.5)),
        _texto(5, "2 DATOS", "section_header", caja=(izq[0], 0.55, izq[1], 0.58)),
        _texto(6, "La Tabla 1 describe los conjuntos.", caja=(izq[0], 0.6, izq[1], 0.9)),
        _texto(7, "Algorithm 1 Entrenamiento", "section_header", caja=(der[0], 0.55, der[1], 0.58)),
        _texto(8, "repetir hasta converger", "code", caja=(der[0], 0.6, der[1], 0.7)),
        _texto(9, "3 MÉTODO", "section_header", page=2, caja=(izq[0], 0.1, izq[1], 0.13)),
        _texto(10, "Se entrena en dos fases.", page=2, caja=(izq[0], 0.15, izq[1], 0.4)),
        _texto(11, "Tabla 1: Conjuntos", "caption", page=2, caja=(der[0], 0.1, der[1], 0.13)),
    ]
    tabla = _tabla(
        0, [[_celda("SWaT", 0, 0), _celda("51", 0, 1)]], page=2, caja=(der[0], 0.15, der[1], 0.3), hijos=["#/texts/11"]
    )
    cuerpo = [f"#/texts/{i}" for i in range(11)] + ["#/tables/0"]
    return _doc(cuerpo, textos, [tabla])


def test_dos_columnas_se_leen_izquierda_y_luego_derecha():
    est = estructura_generica(_dos_columnas(), SHA)
    secciones = [u for u in est["unidades"] if u["nivel"] == 0 and u["paginas"] == [1]]
    assert [u["titulo"] for u in secciones] == ["Detección de anomalías", "RESUMEN", "2 DATOS", "1 INTRODUCCIÓN"]
    por_titulo = {u["titulo"]: u for u in secciones}
    assert "Proponemos un método." in por_titulo["RESUMEN"]["texto"]
    assert "La supervisión es un reto." in por_titulo["1 INTRODUCCIÓN"]["texto"]
    assert any("página 1: orden de lectura corregido" in a for a in est["avisos"])


def test_rotulo_de_algoritmo_no_abre_seccion_y_la_tabla_va_con_quien_la_menciona():
    est = estructura_generica(_dos_columnas(), SHA)
    unidades = {u["clave"]: u for u in est["unidades"]}
    assert not any(u.get("titulo", "").startswith("Algorithm") for u in est["unidades"] if u.get("titulo"))
    datos = next(c for c, u in unidades.items() if u.get("titulo") == "2 DATOS").split(";")[0]
    assert f"{datos};tabla=1" in unidades
    assert "La Tabla 1 describe" in unidades[f"{datos};pagina=1"]["texto"]
    assert "SWaT | 51" in unidades[f"{datos};pagina=2"]["texto"]
    assert any("rótulo" in a for a in est["avisos"]) and any("tablas o figuras" in a for a in est["avisos"])


def test_sin_corregir_se_conserva_el_orden_de_docling():
    est = estructura_generica(_dos_columnas(), SHA, corregir=False)
    titulos = [u["titulo"] for u in est["unidades"] if u["nivel"] == 0]
    assert titulos[:3] == ["Detección de anomalías", "1 INTRODUCCIÓN", "RESUMEN"]
    assert "Algorithm 1 Entrenamiento" in titulos and est["avisos"] == []


def test_una_columna_con_lineas_cortas_se_lee_de_arriba_abajo():
    textos = [
        _texto(0, "Asunto", caja=(0.1, 0.1, 0.3, 0.13)),
        _texto(1, "Madrid, 3 de mayo", caja=(0.6, 0.15, 0.9, 0.18)),
        _texto(2, "Estimado cliente:", caja=(0.1, 0.2, 0.35, 0.23)),
        _texto(3, "Le remitimos el informe solicitado con las mediciones de la campaña.", caja=(0.1, 0.25, 0.9, 0.4)),
    ]
    est = estructura_generica(_doc([f"#/texts/{i}" for i in (3, 2, 1, 0)], textos), SHA)
    assert est["unidades"][0]["texto"].split("\n") == [t["text"] for t in textos]


def test_tres_columnas_no_se_tocan():
    cajas = [(0.05, 0.1, 0.32, 0.9), (0.36, 0.1, 0.64, 0.9), (0.68, 0.1, 0.95, 0.9)]
    textos = [_texto(i, f"columna {i}", caja=c) for i, c in enumerate(cajas)]
    est = estructura_generica(_doc(["#/texts/2", "#/texts/0", "#/texts/1"], textos), SHA)
    assert est["unidades"][0]["texto"].split("\n") == ["columna 2", "columna 0", "columna 1"]
    assert any("maquetación no reconocida" in a for a in est["avisos"])


def test_pieza_sin_caja_que_abre_la_seccion_va_a_la_primera_pagina_con_caja():
    sin_caja = _texto(0, "Nota previa sin posición.")
    sin_caja["prov"] = []
    textos = [sin_caja, _texto(1, "Primer párrafo con posición.", page=2)]
    est = estructura_generica(_doc(["#/texts/0", "#/texts/1"], textos), SHA)
    (unidad,) = est["unidades"]
    assert unidad["clave"] == "seccion=0;pagina=2"
    assert unidad["texto"] == "Nota previa sin posición.\nPrimer párrafo con posición."


def test_pagina_contigua_dentro_de_un_documento_de_varias_paginas_es_rota():
    doc = _informe()
    est = estructura_generica(doc, SHA)
    assert _resolver(est, "pdf-v1:p=1", "No se observaron regresiones").estado == "rota"
    assert _resolver(est, "pdf-v1:p=2", "No se observaron regresiones").estado == "no_comprobable"


def test_un_word_cuelga_el_contenido_de_sus_titulos_y_cada_titulo_abre_seccion():
    """Docling anida un Word: título › encabezado › párrafos y tablas, sin páginas ni cajas."""

    def nodo(i, etiqueta, texto, hijos=()):
        return {"self_ref": f"#/texts/{i}", "label": etiqueta, "text": texto, "prov": [],
                "children": [{"$ref": h} for h in hijos]}

    textos = [
        nodo(0, "title", "Plan de ingeniería", ["#/texts/1", "#/texts/3"]),
        nodo(1, "section_header", "1 Objetivo", ["#/texts/2"]),
        nodo(2, "text", "Detectar fugas en la red."),
        nodo(3, "section_header", "2 Riesgos", ["#/texts/4"]),
        nodo(4, "text", "El piloto no cubre Murcia."),
    ]
    est = estructura_generica(_doc(["#/texts/0"], textos, paginas=0), SHA)
    assert [(u["clave"], u["titulo"]) for u in est["unidades"]] == [
        ("seccion=1", "Plan de ingeniería"),
        ("seccion=2", "1 Objetivo"),
        ("seccion=3", "2 Riesgos"),
    ]
    assert "El piloto no cubre Murcia." in est["unidades"][2]["texto"]
    assert "El piloto no cubre Murcia." not in est["unidades"][0]["texto"]
