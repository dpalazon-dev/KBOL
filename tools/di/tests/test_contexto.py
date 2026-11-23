"""Contexto documental de la estructura genérica: jerarquía, tipo de parte, tablas con cabeceras y referencias."""

from di.contexto import celdas_de_tabla, jerarquia, referencias_citadas, tipo_de_parte
from di.generica import estructura_generica
from test_generica import SHA, _caja, _doc, _texto


def _celda(texto, fila, col, cabecera=False, de_fila=False, filas=1, cols=1):
    return {
        "text": texto,
        "start_row_offset_idx": fila,
        "end_row_offset_idx": fila + filas,
        "start_col_offset_idx": col,
        "end_col_offset_idx": col + cols,
        "row_span": filas,
        "col_span": cols,
        "column_header": cabecera,
        "row_header": de_fila,
        "bbox": _caja(0.1 + 0.05 * col, 0.5 + 0.02 * fila, 0.14 + 0.05 * col, 0.52 + 0.02 * fila),
    }


def _rejilla(celdas, num_filas, num_cols):
    """La rejilla de Docling: cada fila con una celda por columna; una combinada se repite en cada hueco que ocupa."""
    grid = [[None] * num_cols for _ in range(num_filas)]
    for c in celdas:
        for f in range(c["start_row_offset_idx"], c["end_row_offset_idx"]):
            for k in range(c["start_col_offset_idx"], c["end_col_offset_idx"]):
                grid[f][k] = c
    return grid


def _tabla_resultados():
    """Como la Tabla 2 de USAD: dos niveles de cabecera combinados, etiqueta de fila y un segundo bloque debajo."""
    celdas = [
        _celda("Métodos", 0, 0, cabecera=True, filas=2),
        _celda("SWaT", 0, 1, cabecera=True, cols=2),
        _celda("WADI", 0, 3, cabecera=True),
        _celda("Sin ajuste", 1, 1, cabecera=True),
        _celda("Con ajuste", 1, 2, cabecera=True),
        _celda("Sin ajuste", 1, 3, cabecera=False),  # Docling a veces no marca una celda de cabecera
        _celda("AE", 2, 0, de_fila=True),
        _celda("0.7697", 2, 1),
        _celda("0.8233", 2, 2),
        _celda("0.2315", 2, 3),
        _celda("USAD", 3, 0, de_fila=True),
        _celda("0.7917", 3, 1),
        _celda("0.8460", 3, 2),
        _celda("0.2328", 3, 3),
        _celda("Métodos", 4, 0, cabecera=True),
        _celda("SMD", 4, 1, cabecera=True, cols=3),
        _celda("USAD", 5, 0, de_fila=True),
        _celda("0.9382", 5, 1),
        _celda("0.9463", 5, 2),
        _celda("0.9109", 5, 3),
    ]
    return {"data": {"grid": _rejilla(celdas, 6, 4), "num_rows": 6, "num_cols": 4}, "prov": [{"page_no": 1}]}


def test_cada_dato_de_la_tabla_lleva_sus_cabeceras_y_su_fila():
    celdas = {(tuple(c["fila"]), tuple(c["cabeceras"])): c["texto"] for c in celdas_de_tabla(_tabla_resultados())}
    assert celdas[(("USAD",), ("SWaT", "Sin ajuste"))] == "0.7917"
    assert celdas[(("AE",), ("SWaT", "Con ajuste"))] == "0.8233"
    assert celdas[(("USAD",), ("WADI", "Sin ajuste"))] == "0.2328"


def test_un_segundo_bloque_de_cabeceras_sustituye_al_primero():
    celdas = [c for c in celdas_de_tabla(_tabla_resultados()) if c["texto"] == "0.9382"]
    assert [c["cabeceras"] for c in celdas] == [["SMD"]]


def test_celda_de_dato_conserva_su_posicion():
    (c,) = [c for c in celdas_de_tabla(_tabla_resultados()) if c["texto"] == "0.7917"]
    assert (c["f"], c["c"], c["p"]) == (3, 1, 1)


def test_tabla_sin_cabeceras_da_celdas_sin_cabecera():
    celdas = [_celda("a", 0, 0), _celda("b", 0, 1)]
    tabla = {"data": {"grid": _rejilla(celdas, 1, 2), "num_rows": 1, "num_cols": 2}, "prov": [{"page_no": 2}]}
    assert [(c["texto"], c["cabeceras"], c["fila"]) for c in celdas_de_tabla(tabla)] == [("a", [], []), ("b", [], ["a"])]


def test_jerarquia_por_numeracion():
    titulos = [
        "Detección de anomalías",
        "ABSTRACT",
        "1 INTRODUCTION",
        "5 EXPERIMENTS AND RESULTS",
        "5.1 Overall performance",
        "5.1.1 Point-wise",
        "5.3 Training time",
        "REFERENCES",
        "A SUPPLEMENTARY MATERIAL",
        "A.1 Experimental Setting",
    ]
    j = jerarquia(titulos)
    assert [x["numero"] for x in j] == [None, None, "1", "5", "5.1", "5.1.1", "5.3", None, "A", "A.1"]
    assert [x["profundidad"] for x in j] == [1, 1, 1, 1, 2, 3, 2, 1, 1, 2]
    assert j[5]["padre"] == 4 and j[4]["padre"] == 3 and j[6]["padre"] == 3 and j[9]["padre"] == 8
    assert j[2]["padre"] is None


def test_una_letra_solo_numera_un_anexo():
    j = jerarquia(["1 Introducción", "A Novel Approach to Detection", "REFERENCES", "B Proofs"])
    assert [x["numero"] for x in j] == ["1", None, None, "B"]


def test_numero_sin_padre_cuelga_de_la_raiz():
    j = jerarquia(["2.3 Huérfano"])
    assert j[0]["padre"] is None and j[0]["profundidad"] == 2


def test_tipo_de_parte():
    assert tipo_de_parte("ABSTRACT") == "resumen"
    assert tipo_de_parte("1 Introducción") == "introduccion"
    assert tipo_de_parte("2 RELATED WORK") == "trabajos_relacionados"
    assert tipo_de_parte("3 Method") == "metodo"
    assert tipo_de_parte("5 EXPERIMENTS AND RESULTS") == "experimentos"
    assert tipo_de_parte("6 CONCLUSIONS") == "conclusiones"
    assert tipo_de_parte("REFERENCES") == "referencias"
    assert tipo_de_parte("A SUPPLEMENTARY MATERIAL FOR REPRODUCIBILITY") == "anexo"
    assert tipo_de_parte("5.3 Training time") is None


def test_referencias_numericas_y_rangos():
    assert referencias_citadas("como en [2] y [15, 21], y en [3-5].") == ["2", "15", "21", "3", "4", "5"]
    assert referencias_citadas("la ecuación [x] y el intervalo [0, 1] no son citas") == []


def test_referencias_autor_anio():
    claves = referencias_citadas("según (Feng et al. 2021; Ma and Li 2022) y Wang et al. (2022a)", autor_anio=True)
    assert claves == ["feng 2021", "ma 2022", "wang 2022a"]


def _paper():
    textos = [
        _texto(0, "Detección de anomalías", "title", caja=(0.1, 0.02, 0.9, 0.05)),
        _texto(1, "ABSTRACT", "section_header", caja=(0.1, 0.06, 0.9, 0.08)),
        _texto(2, "Proponemos un método.", caja=(0.1, 0.09, 0.9, 0.12)),
        _texto(3, "5 EXPERIMENTS AND RESULTS", "section_header", caja=(0.1, 0.13, 0.9, 0.15)),
        _texto(4, "5.3 Training time", "section_header", caja=(0.1, 0.16, 0.9, 0.18)),
        _texto(5, "Seguimos el protocolo de [2] y [1]; la Tabla 1 resume los datos.", caja=(0.1, 0.19, 0.9, 0.25)),
        _texto(6, "REFERENCES", "section_header", page=2, caja=(0.1, 0.05, 0.9, 0.08)),
        _texto(7, "Audibert et al. 2020. USAD.", "list_item", page=2, caja=(0.1, 0.1, 0.9, 0.12), marker="[1]"),
        _texto(8, "Goh et al. 2017. SWaT.", "list_item", page=2, caja=(0.1, 0.13, 0.9, 0.15), marker="[2]"),
        _texto(9, "Tabla 1: Resultados", "caption", caja=(0.1, 0.3, 0.9, 0.32)),
    ]
    tabla = _tabla_resultados()
    tabla.update(self_ref="#/tables/0", label="table", children=[{"$ref": "#/texts/9"}])
    tabla["prov"] = [{"page_no": 1, "bbox": _caja(0.1, 0.33, 0.9, 0.6)}]
    cuerpo = [f"#/texts/{i}" for i in range(9)] + ["#/tables/0"]
    return _doc(cuerpo, textos, [tabla])


def test_la_estructura_lleva_ruta_tipo_y_referencias_de_cada_seccion():
    est = estructura_generica(_paper(), SHA)
    por_titulo = {u["titulo"]: u for u in est["unidades"] if u["nivel"] == 0}
    sec = por_titulo["5.3 Training time"]
    assert sec["ruta"] == ["5 EXPERIMENTS AND RESULTS", "5.3 Training time"]
    assert sec["numero"] == "5.3" and sec["tipo"] == "experimentos"
    assert sec["padre"] == por_titulo["5 EXPERIMENTS AND RESULTS"]["clave"].split(";")[0]
    assert sec["referencias"] == ["2", "1"]
    assert por_titulo["ABSTRACT"]["tipo"] == "resumen"
    refs = {r["clave"]: r for r in est["referencias"]}
    assert refs["2"]["texto"].startswith("Goh et al. 2017") and refs["2"]["paginas"] == [2]


def test_la_tabla_de_la_estructura_trae_celdas_con_cabeceras_y_la_seccion_que_la_menciona():
    est = estructura_generica(_paper(), SHA)
    (tabla,) = [u for u in est["unidades"] if ";tabla=" in u["clave"]]
    assert tabla["leyenda"] == "Tabla 1: Resultados"
    assert tabla["ruta"] == ["5 EXPERIMENTS AND RESULTS", "5.3 Training time"]
    celda = next(c for c in tabla["celdas"] if c["fila"] == ["USAD"] and c["cabeceras"] == ["SWaT", "Sin ajuste"])
    assert celda["texto"] == "0.7917"
    # El texto de la tabla sigue siendo el del PDF: las cabeceras no se mezclan en lo que se cita.
    assert "SWaT / Sin ajuste" not in tabla["texto"]


def test_cita_sin_entrada_en_la_bibliografia_se_avisa():
    """La bibliografía tiene [1] y [3]; el texto cita [2], que se perdió al leer el PDF."""
    doc = _paper()
    doc["texts"][8]["marker"] = "[3]"
    est = estructura_generica(doc, SHA)
    assert any("citas sin entrada en la bibliografía: [2]" in a for a in est["avisos"])


def test_titulos_con_caracteres_de_control_o_palabras_pegadas():
    assert tipo_de_parte("2 Background") == "trabajos_relacionados"
    assert tipo_de_parte("3 Method") == "metodo"
    assert tipo_de_parte("2 RELATEDWORK") == "trabajos_relacionados"
    assert tipo_de_parte("3 INTRODUCING THE UCR ANOMALY ARCHIVE") is None
    assert tipo_de_parte("8 Discussion and Conclusion") == "conclusiones"
    assert jerarquia(["3 Method"])[0]["numero"] == "3"


def test_apartado_numerado_que_no_avanza_cuelga_de_la_ultima_seccion():
    j = jerarquia(["3 Método", "3.3 Puntuación", "1. Discriminación", "2. Reconstrucción", "4 Ataques"])
    assert [x["numero"] for x in j] == ["3", "3.3", None, None, "4"]
    assert j[2]["padre"] == 1 and j[3]["padre"] == 1 and j[2]["retrocede"] is True
    assert j[4]["padre"] is None and j[4]["profundidad"] == 1


def test_corchetes_con_numeros_mayores_que_la_bibliografia_no_son_citas():
    assert referencias_citadas("tamaños [50, 100] y la cita [3]", maximo=21) == ["3"]


def test_entrada_de_bibliografia_con_marcador_de_punto():
    from di.contexto import clave_de_entrada

    assert clave_de_entrada("G. Jonathan et al., Anomaly detection.", "1.") == ("1", True)
    assert clave_de_entrada("Abdulaal A, Liu Z (2021) Practical approach", "") == ("abdulaal 2021", False)


def test_dentro_de_un_anexo_todo_es_anexo():
    textos = [
        _texto(0, "REFERENCES", "section_header", caja=(0.1, 0.05, 0.9, 0.08)),
        _texto(1, "A SUPPLEMENTARY MATERIAL", "section_header", caja=(0.1, 0.1, 0.9, 0.12)),
        _texto(2, "A.1 Experimental Setting", "section_header", caja=(0.1, 0.13, 0.9, 0.15)),
        _texto(3, "Usamos una GPU.", caja=(0.1, 0.16, 0.9, 0.2)),
    ]
    est = estructura_generica(_doc([f"#/texts/{i}" for i in range(4)], textos), SHA)
    (u,) = [u for u in est["unidades"] if u["titulo"] == "A.1 Experimental Setting"]
    assert u["tipo"] == "anexo" and u["numero"] == "A.1"


def test_primera_fila_de_texto_sin_marcar_sobre_numeros_es_cabecera():
    celdas = [_celda("Método", 0, 0), _celda("Precisión", 0, 1), _celda("USAD", 1, 0), _celda("0.7448", 1, 1)]
    tabla = {"data": {"grid": _rejilla(celdas, 2, 2), "num_rows": 2, "num_cols": 2}, "prov": [{"page_no": 9}]}
    assert [(c["texto"], c["cabeceras"], c["fila"]) for c in celdas_de_tabla(tabla)] == [
        ("USAD", ["Método"], []),
        ("0.7448", ["Precisión"], ["USAD"]),
    ]


def test_tabla_solo_de_texto_no_inventa_cabeceras():
    celdas = [_celda("Ataque", 0, 0), _celda("Efecto", 0, 1), _celda("Inyección", 1, 0), _celda("Desborda", 1, 1)]
    tabla = {"data": {"grid": _rejilla(celdas, 2, 2), "num_rows": 2, "num_cols": 2}, "prov": [{"page_no": 1}]}
    assert all(c["cabeceras"] == [] for c in celdas_de_tabla(tabla))
