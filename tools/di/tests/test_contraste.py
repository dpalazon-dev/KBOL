"""Contraste de una estructura con el texto por página de un segundo extractor."""

from di.contraste import cifras_que_faltan, cobertura, contrastar, mobiliario_por_pagina


def _estructura(unidades, paginas=(1, 2)):
    return {"paginas": [{"p": p} for p in paginas], "unidades": unidades}


def _unidad(clave, pagina, texto, nivel=0):
    return {"clave": clave, "nivel": nivel, "paginas": [pagina], "texto": texto}


BASE = {
    1: "Informe de rendimiento\nEl método reduce el tiempo 547 veces.\nConjunto Muestras\nSWaT 496800\nWADI 1048571\n3",
    2: "Conclusiones\nNo se observaron regresiones en 12 ensayos.\n4",
}
MOBILIARIO = {1: "3", 2: "4"}


def _fiel():
    return [
        _unidad("seccion=1;pagina=1", 1, "Informe de rendimiento\nEl método reduce el tiempo 547 veces.\nConjunto | Muestras\nSWaT | 496800\nWADI | 1048571"),
        _unidad("seccion=1;tabla=1", 1, "Conjunto | Muestras\nSWaT | 496800\nWADI | 1048571", nivel=1),
        _unidad("seccion=2;pagina=2", 2, "Conclusiones\nNo se observaron regresiones en 12 ensayos."),
    ]


def test_estructura_fiel_no_tiene_fallos():
    res = contrastar(_estructura(_fiel()), BASE, MOBILIARIO)
    assert res["fallos"] == []
    assert res["resumen"]["recuerdo_documento"] == 1.0 and res["resumen"]["respaldo_documento"] == 1.0
    assert res["tablas"] == [{"clave": "seccion=1;tabla=1", "paginas": [1], "cifras": 2, "cifras_sin_respaldo": []}]


def test_cifra_perdida_en_una_tabla_se_senala():
    unidades = _fiel()
    unidades[0]["texto"] = unidades[0]["texto"].replace("1048571", "")
    res = contrastar(_estructura(unidades), BASE, MOBILIARIO)
    (fallo,) = res["fallos"]
    assert fallo["p"] == 1 and fallo["cifras_ausentes"] == ["1048571"]
    assert res["resumen"]["cifras_ausentes"] == 1


def test_cifra_alterada_se_senala_en_los_dos_sentidos_y_en_su_tabla():
    unidades = _fiel()
    for u in unidades[:2]:
        u["texto"] = u["texto"].replace("496800", "496900")
    res = contrastar(_estructura(unidades), BASE, MOBILIARIO)
    (fallo,) = res["fallos"]
    assert fallo["cifras_ausentes"] == ["496800"] and fallo["cifras_sin_respaldo"] == ["496900"]
    assert res["tablas"][0]["cifras_sin_respaldo"] == ["496900"]
    assert res["resumen"]["tablas_con_cifras_sin_respaldo"] == 1


def test_parrafo_perdido_baja_el_recuerdo_de_su_pagina():
    unidades = _fiel()
    unidades[2]["texto"] = "Conclusiones"
    res = contrastar(_estructura(unidades), BASE, MOBILIARIO)
    assert res["resumen"]["paginas_con_recuerdo_bajo"] == [2]
    assert res["paginas"][0]["recuerdo"] == 1.0


def test_texto_que_el_pdf_no_tiene_ni_cerca_baja_el_respaldo():
    unidades = _fiel() + [_unidad("seccion=3;pagina=4", 4, "Este texto pertenece a un anexo que el PDF no tiene aquí.")]
    base = {**BASE, 3: "", 4: ""}
    res = contrastar(_estructura(unidades, paginas=(1, 2, 3, 4)), base, MOBILIARIO)
    assert res["resumen"]["paginas_con_respaldo_bajo"] == [4]


def test_pagina_sin_capa_de_texto_se_declara():
    res = contrastar(_estructura(_fiel(), paginas=(1, 2, 3)), {**BASE, 3: ""}, MOBILIARIO)
    assert res["resumen"]["paginas_sin_capa_de_texto"] == [3]
    assert [f["p"] for f in res["fallos"]] == [3]


def test_el_mobiliario_no_cuenta_como_perdida():
    sin = contrastar(_estructura(_fiel()), BASE)
    assert [f["cifras_ausentes"] for f in sin["fallos"]] == [["3"], ["4"]]
    assert contrastar(_estructura(_fiel()), BASE, MOBILIARIO)["fallos"] == []


def test_palabras_partidas_o_pegadas_por_el_segundo_extractor_no_son_un_fallo():
    assert cobertura("el fabri cante notifi cará", "El fabricante notificará") == 1.0
    assert cobertura("elfabricante notificará", "El fabricante notificará") == 1.0
    assert cobertura("el fabricante informará", "El fabricante notificará") < 1.0


def test_cifras_cortas_exigen_coincidencia_exacta():
    assert cifras_que_faltan("valor 51", "valor 0.5123") == ["51"]
    assert cifras_que_faltan("0.9903 0.6295", "0.99030.6295") == []


def test_mobiliario_por_pagina():
    doc = {
        "texts": [
            {"label": "page_header", "text": "Diario Oficial", "prov": [{"page_no": 2}]},
            {"label": "page_footer", "text": "17", "prov": [{"page_no": 2}]},
            {"label": "text", "text": "cuerpo", "prov": [{"page_no": 2}]},
        ]
    }
    assert mobiliario_por_pagina(doc) == {2: "Diario Oficial\n17"}


def test_parrafo_perdido_baja_el_recuerdo_aunque_sus_palabras_esten_en_otra_parte():
    base = {1: "El fabricante notificará el incidente.\nEl fabricante notificará el incidente a la autoridad."}
    unidades = [_unidad("seccion=1;pagina=1", 1, "El fabricante notificará el incidente a la autoridad.")]
    res = contrastar(_estructura(unidades, paginas=(1,)), base)
    assert res["paginas"][0]["recuerdo"] < 0.7
    assert res["resumen"]["paginas_con_recuerdo_bajo"] == [1]


def test_el_respaldo_no_detecta_texto_en_la_pagina_contigua():
    """Límite declarado: un texto colocado en la página vecina a la suya queda respaldado."""
    base = {1: "Primera página con su contenido propio.", 2: "Segunda página con otro contenido distinto."}
    unidades = [
        _unidad("seccion=1;pagina=1", 1, "Primera página con su contenido propio.\nSegunda página con otro contenido distinto."),
    ]
    res = contrastar(_estructura(unidades), base)
    assert res["paginas"][0]["respaldo"] == 1.0
    assert res["resumen"]["paginas_con_recuerdo_bajo"] == [2]
