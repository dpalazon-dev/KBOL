"""Norm profile: the input texts are Spanish regulations, as published by EUR-Lex and the BOE."""

from di.fidelity import measure, split_words, terms
from di.structure import structure_from_docling

PAGE = {"size": {"width": 600.0, "height": 800.0}, "page_no": 1}


def _text(i, text, label="text", marker=None, page=1, top=700.0):
    item = {
        "self_ref": f"#/texts/{i}",
        "label": label,
        "text": text,
        "prov": [
            {"page_no": page, "bbox": {"l": 60.0, "t": top, "r": 540.0, "b": top - 20, "coord_origin": "BOTTOMLEFT"}}
        ],
        "children": [],
    }
    if marker:
        item["marker"] = marker
    return item


def _doc(items, headers=()):
    texts = list(items) + list(headers)
    return {
        "pages": {"1": PAGE, "2": {**PAGE, "page_no": 2}},
        "texts": texts,
        "tables": [],
        "groups": [],
        "body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(items))]},
    }


def _keys(st):
    return [u["key"] for u in st["units"]]


def test_article_paragraphs_letters_and_roman_numerals():
    items = [
        _text(0, "(1) Considerando primero"),
        _text(1, "(2) Considerando segundo"),
        _text(2, "Artículo 14", "section_header"),
        _text(3, "Los fabricantes notificarán.", "list_item", "1."),
        _text(4, "A efectos de la notificación:", "list_item", "2."),
        _text(5, "una alerta temprana;", "list_item", "a)"),
        _text(6, "un informe final que incluya:", "list_item", "c)"),
        _text(7, "una descripción,", "list_item", "i)"),
        _text(8, "detalles de la actualización.", "list_item", "ii)"),
        _text(9, "Los actos no se aplicarán, salvo urgencia.", "text"),
        _text(10, "ANEXO I", "section_header", page=2),
        _text(11, "Parte I", "section_header", page=2),
        _text(12, "Los productos se diseñarán.", "list_item", "1)", page=2),
        _text(13, "Sobre la base de la evaluación:", "list_item", "2)", page=2),
        _text(14, "actualizaciones automáticas, cuando proceda;", "list_item", "c)", page=2),
    ]
    st = structure_from_docling(_doc(items), "a" * 64)
    keys = _keys(st)
    assert keys == [
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
    u = {x["key"]: x for x in st["units"]}
    assert "detalles de la actualización" in u["art=14;ap=2;let=c"]["text"]
    assert "salvo urgencia" in u["art=14;ap=2"]["text"]
    assert "salvo urgencia" not in u["art=14;ap=2;let=c"]["text"]
    assert u["anx=I;parte=I;pto=2;let=c"]["pages"] == [2]
    assert u["art=14;ap=1"]["regions"][0]["r"] == ["0.1000", "0.1250", "0.9000", "0.1500"]


def test_letter_i_after_h_is_a_letter():
    items = [_text(0, "Artículo 3", "section_header")] + [
        _text(i + 1, f"texto {m}", "list_item", f"{m})") for i, m in enumerate("abcdefghij")
    ]
    keys = _keys(structure_from_docling(_doc(items), "a" * 64))
    assert "art=3;let=i" in keys and "art=3;let=j" in keys
    assert not any("num=" in c for c in keys)


def test_a_heading_in_a_page_header_is_recovered_with_a_warning():
    items = [
        _text(0, "ANEXO I", "section_header"),
        _text(1, "Clase I", "section_header"),
        _text(2, "1. Gestores", page=1),
        _text(3, "1. Hipervisores", page=2),
        _text(4, "2. Cortafuegos", page=2),
    ]
    header = [_text(5, "Clase II", "page_header", page=2, top=790.0)]
    st = structure_from_docling(_doc(items, header), "a" * 64)
    assert "anx=I;sec=II;pto=2" in _keys(st)
    assert st["warnings"] and "Clase II" in st["warnings"][0]


def test_measure_detects_date_negation_absence_and_ambiguity():
    st = {
        "units": [
            {"key": "art=1", "level": 0, "text": "Será aplicable a partir del 11 de diciembre de 2027."},
            {"key": "art=2", "level": 0, "text": "El presente Reglamento es aplicable a los equipos."},
            {"key": "art=4", "level": 0, "text": "uno"},
            {"key": "art=4", "level": 0, "text": "dos"},
        ]
    }
    editor = {
        "art=1": "Será aplicable a partir del 11 de diciembre de 2027 y del 11 de junio de 2026.",
        "art=2": "El presente Reglamento no es aplicable a los equipos.",
        "art=3": "Ausente.",
        "art=4": "uno",
    }
    res = measure(st, editor)
    failures = {f["key"]: f for f in res["failures"]}
    assert failures["art=1"]["lost_dates"] == ["11 de junio de 2026"]
    assert failures["art=2"]["differing_terms"]["no"] == [1, 0]
    assert failures["art=3"]["status"] == "missing"
    assert failures["art=4"]["status"] == "ambiguous"


def test_split_words_and_terms():
    assert split_words("el fabricante notificará", "el fabri cante notifi cará") == 2
    assert terms("No obstante, salvo que no proceda")["no"] == 2
    assert terms("No obstante, salvo que no proceda")["no obstante"] == 1


def _two_column_norm():
    """Two articles in columns that Docling delivers with the second before the first."""

    def box(left, top, right, bottom):
        return {"l": left * 600, "t": top * 800, "r": right * 600, "b": bottom * 800, "coord_origin": "TOPLEFT"}

    def text(i, content, label, position):
        return {
            "self_ref": f"#/texts/{i}",
            "label": label,
            "text": content,
            "prov": [{"page_no": 1, "bbox": box(*position)}],
            "children": [],
        }

    items = [
        text(0, "Artículo 2", "section_header", (0.52, 0.1, 0.92, 0.13)),
        text(1, "Definiciones aplicables al presente Reglamento.", "text", (0.52, 0.15, 0.92, 0.5)),
        text(2, "Artículo 1", "section_header", (0.08, 0.1, 0.48, 0.13)),
        text(3, "Objeto del presente Reglamento.", "text", (0.08, 0.15, 0.48, 0.5)),
    ]
    return _doc(items)


def test_without_reorder_the_output_does_not_change_and_with_reorder_it_is_corrected_and_declared():
    doc = _two_column_norm()
    without = structure_from_docling(doc, "a" * 64)
    assert _keys(without) == ["art=2", "art=1"]
    assert sorted(without) == ["docling_sha256", "original_sha256", "pages", "profile", "segmenter", "units", "warnings"]
    assert without["warnings"] == []
    with_reorder = structure_from_docling(doc, "a" * 64, reorder=True)
    assert _keys(with_reorder) == ["art=1", "art=2"]
    assert with_reorder["order_corrected"] is True
    assert any("page 1: reading order corrected" in a for a in with_reorder["warnings"])
    assert "Objeto del presente Reglamento." in with_reorder["units"][0]["text"]
