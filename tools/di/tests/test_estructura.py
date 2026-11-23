from di.estructura import estructura_desde_docling
from di.fidelidad import medir, partidas, terminos

PAGINA = {"size": {"width": 600.0, "height": 800.0}, "page_no": 1}


def _texto(i, texto, etiqueta="text", marker=None, page=1, top=700.0):
    item = {
        "self_ref": f"#/texts/{i}",
        "label": etiqueta,
        "text": texto,
        "prov": [
            {"page_no": page, "bbox": {"l": 60.0, "t": top, "r": 540.0, "b": top - 20, "coord_origin": "BOTTOMLEFT"}}
        ],
        "children": [],
    }
    if marker:
        item["marker"] = marker
    return item


def _doc(items, cabeceras=()):
    textos = list(items) + list(cabeceras)
    return {
        "pages": {"1": PAGINA, "2": {**PAGINA, "page_no": 2}},
        "texts": textos,
        "tables": [],
        "groups": [],
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(items))]},
    }


def _claves(est):
    return [u["clave"] for u in est["unidades"]]


def test_articulo_apartados_letras_y_romanos():
    items = [
        _texto(0, "(1) Considerando primero"),
        _texto(1, "(2) Considerando segundo"),
        _texto(2, "Artículo 14", "section_header"),
        _texto(3, "Los fabricantes notificarán.", "list_item", "1."),
        _texto(4, "A efectos de la notificación:", "list_item", "2."),
        _texto(5, "una alerta temprana;", "list_item", "a)"),
        _texto(6, "un informe final que incluya:", "list_item", "c)"),
        _texto(7, "una descripción,", "list_item", "i)"),
        _texto(8, "detalles de la actualización.", "list_item", "ii)"),
        _texto(9, "Los actos no se aplicarán, salvo urgencia.", "text"),
        _texto(10, "ANEXO I", "section_header", page=2),
        _texto(11, "Parte I", "section_header", page=2),
        _texto(12, "Los productos se diseñarán.", "list_item", "1)", page=2),
        _texto(13, "Sobre la base de la evaluación:", "list_item", "2)", page=2),
        _texto(14, "actualizaciones automáticas, cuando proceda;", "list_item", "c)", page=2),
    ]
    est = estructura_desde_docling(_doc(items), "a" * 64)
    claves = _claves(est)
    assert claves == [
        "cons=1",
        "cons=2",
        "art=14",
        "art=14;ap=1",
        "art=14;ap=2",
        "art=14;ap=2;let=a",
        "art=14;ap=2;let=c",
        "art=14;ap=2;let=c;num=i",
        "art=14;ap=2;let=c;num=ii",
        "anx=I",
        "anx=I;parte=I",
        "anx=I;parte=I;pto=1",
        "anx=I;parte=I;pto=2",
        "anx=I;parte=I;pto=2;let=c",
    ]
    u = {x["clave"]: x for x in est["unidades"]}
    assert "detalles de la actualización" in u["art=14;ap=2;let=c"]["texto"]
    assert "salvo urgencia" in u["art=14;ap=2"]["texto"]
    assert "salvo urgencia" not in u["art=14;ap=2;let=c"]["texto"]
    assert u["anx=I;parte=I;pto=2;let=c"]["paginas"] == [2]
    assert u["art=14;ap=1"]["regiones"][0]["r"] == ["0.1000", "0.1250", "0.9000", "0.1500"]


def test_letra_i_tras_h_es_letra():
    items = [_texto(0, "Artículo 3", "section_header")] + [
        _texto(i + 1, f"texto {m}", "list_item", f"{m})") for i, m in enumerate("abcdefghij")
    ]
    claves = _claves(estructura_desde_docling(_doc(items), "a" * 64))
    assert "art=3;let=i" in claves and "art=3;let=j" in claves
    assert not any("num=" in c for c in claves)


def test_encabezado_en_cabecera_de_pagina_se_recupera_con_aviso():
    items = [
        _texto(0, "ANEXO I", "section_header"),
        _texto(1, "Clase I", "section_header"),
        _texto(2, "1. Gestores", page=1),
        _texto(3, "1. Hipervisores", page=2),
        _texto(4, "2. Cortafuegos", page=2),
    ]
    cabecera = [_texto(5, "Clase II", "page_header", page=2, top=790.0)]
    est = estructura_desde_docling(_doc(items, cabecera), "a" * 64)
    assert "anx=I;sec=II;pto=2" in _claves(est)
    assert est["avisos"] and "Clase II" in est["avisos"][0]


def test_medir_detecta_fecha_negacion_ausencia_y_ambiguedad():
    est = {
        "unidades": [
            {"clave": "art=1", "nivel": 0, "texto": "Será aplicable a partir del 11 de diciembre de 2027."},
            {"clave": "art=2", "nivel": 0, "texto": "El presente Reglamento es aplicable a los equipos."},
            {"clave": "art=4", "nivel": 0, "texto": "uno"},
            {"clave": "art=4", "nivel": 0, "texto": "dos"},
        ]
    }
    editor = {
        "art=1": "Será aplicable a partir del 11 de diciembre de 2027 y del 11 de junio de 2026.",
        "art=2": "El presente Reglamento no es aplicable a los equipos.",
        "art=3": "Ausente.",
        "art=4": "uno",
    }
    res = medir(est, editor)
    fallos = {f["clave"]: f for f in res["fallos"]}
    assert fallos["art=1"]["fechas_perdidas"] == ["11 de junio de 2026"]
    assert fallos["art=2"]["terminos_distintos"]["no"] == [1, 0]
    assert fallos["art=3"]["estado"] == "ausente"
    assert fallos["art=4"]["estado"] == "ambigua"


def test_partidas_y_terminos():
    assert partidas("el fabricante notificará", "el fabri cante notifi cará") == 2
    assert terminos("No obstante, salvo que no proceda")["no"] == 2
    assert terminos("No obstante, salvo que no proceda")["no obstante"] == 1


def _norma_a_dos_columnas():
    """Dos artículos en columnas que Docling entrega con el segundo delante del primero."""

    def caja(izq, arriba, der, abajo):
        return {"l": izq * 600, "t": arriba * 800, "r": der * 600, "b": abajo * 800, "coord_origin": "TOPLEFT"}

    def texto(i, contenido, etiqueta, posicion):
        return {
            "self_ref": f"#/texts/{i}",
            "label": etiqueta,
            "text": contenido,
            "prov": [{"page_no": 1, "bbox": caja(*posicion)}],
            "children": [],
        }

    items = [
        texto(0, "Artículo 2", "section_header", (0.52, 0.1, 0.92, 0.13)),
        texto(1, "Definiciones aplicables al presente Reglamento.", "text", (0.52, 0.15, 0.92, 0.5)),
        texto(2, "Artículo 1", "section_header", (0.08, 0.1, 0.48, 0.13)),
        texto(3, "Objeto del presente Reglamento.", "text", (0.08, 0.15, 0.48, 0.5)),
    ]
    return _doc(items)


def test_sin_ordenar_la_salida_no_cambia_y_con_ordenar_se_corrige_y_se_declara():
    doc = _norma_a_dos_columnas()
    sin = estructura_desde_docling(doc, "a" * 64)
    assert _claves(sin) == ["art=2", "art=1"]
    assert sorted(sin) == ["avisos", "docling_sha256", "original_sha256", "paginas", "perfil", "segmentador", "unidades"]
    assert sin["avisos"] == []
    con = estructura_desde_docling(doc, "a" * 64, ordenar=True)
    assert _claves(con) == ["art=1", "art=2"]
    assert con["orden_corregido"] is True
    assert any("página 1: orden de lectura corregido" in a for a in con["avisos"])
    assert "Objeto del presente Reglamento." in con["unidades"][0]["texto"]
