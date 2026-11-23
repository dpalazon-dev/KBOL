"""A PDF that is not a regulation: its generic structure and the resolution of its citations with the core resolver."""

import hashlib

from di.generic import generic_structure
from di.locate import locate

from kbol.citations import resolve_pdf
from kbol.locator import InvalidLocator, parse_

ORIGINAL = b"%PDF-1.7 test report"
SHA = hashlib.sha256(ORIGINAL).hexdigest()
WIDTH, HEIGHT = 600.0, 800.0


def _box(left, top, right, bottom):
    """Box with the origin at the top left, in fractions of the page."""
    return {"l": left * WIDTH, "t": top * HEIGHT, "r": right * WIDTH, "b": bottom * HEIGHT, "coord_origin": "TOPLEFT"}


def _text(i, text, label="text", page=1, box=(0.1, 0.1, 0.9, 0.15), marker=None, children=()):
    item = {
        "self_ref": f"#/texts/{i}",
        "label": label,
        "text": text,
        "prov": [{"page_no": page, "bbox": _box(*box)}],
        "children": [{"$ref": h} for h in children],
    }
    if marker:
        item["marker"] = marker
    return item


def _cell(text, row, col, header=False, box=(0.1, 0.5, 0.2, 0.52)):
    return {
        "text": text,
        "start_row_offset_idx": row,
        "start_col_offset_idx": col,
        "column_header": header,
        "bbox": _box(*box),
    }


def _table(i, rows, page=1, box=(0.1, 0.5, 0.9, 0.7), children=()):
    return {
        "self_ref": f"#/tables/{i}",
        "label": "table",
        "prov": [{"page_no": page, "bbox": _box(*box)}],
        "children": [{"$ref": h} for h in children],
        "data": {"grid": rows},
    }


def _doc(body, texts, tables=(), figures=(), pages=2):
    return {
        "pages": {str(p): {"size": {"width": WIDTH, "height": HEIGHT}, "page_no": p} for p in range(1, pages + 1)},
        "texts": list(texts),
        "tables": list(tables),
        "pictures": list(figures),
        "groups": [],
        "body": {"children": [{"$ref": r} for r in body]},
    }


def _report():
    texts = [
        _text(0, "Performance report", "title"),
        _text(1, "This report summarizes the measurements of the campaign.", box=(0.1, 0.2, 0.9, 0.25)),
        _text(2, "1 Results", "section_header", box=(0.1, 0.3, 0.9, 0.33)),
        _text(3, "The method reduces training time 547 times on average.", box=(0.1, 0.35, 0.9, 0.4)),
        _text(4, "Table 1: Datasets", "caption", box=(0.1, 0.45, 0.9, 0.48)),
        _text(5, "2 Conclusions", "section_header", page=2),
        _text(6, "No regressions were observed.", page=2, box=(0.1, 0.2, 0.9, 0.25)),
        _text(7, "Page 1 of 2", "page_footer", box=(0.1, 0.95, 0.9, 0.98)),
    ]
    table = _table(
        0,
        [
            [_cell("Dataset", 0, 0, True), _cell("Samples", 0, 1, True)],
            [_cell("SWaT", 1, 0), _cell("496800", 1, 1)],
        ],
        children=["#/texts/4"],
    )
    body = ["#/texts/0", "#/texts/1", "#/texts/2", "#/texts/3", "#/tables/0", "#/texts/5", "#/texts/6"]
    return _doc(body, texts, [table])


def _anchor(doc, literal):
    (match,) = locate(doc, literal)
    (region,) = match
    return f"pdf-v1:p={region['p']};r={','.join(region['r'])}"


def _resolve(st, anchor, literal, original_path=None):
    r = resolve_pdf(parse_(anchor), original_sha256=SHA, original_path=original_path, structure=st, literal=literal)
    return r.state


def test_sections_tables_and_pages():
    st = generic_structure(_report(), SHA, correct=False)
    assert st["profile"] == "structure-v1"
    units = {u["key"]: u for u in st["units"]}
    assert list(units) == ["section=1;page=1", "section=2;page=1", "section=2;table=1", "section=3;page=2"]
    assert units["section=1;page=1"]["title"] == "Performance report"
    assert units["section=2;page=1"]["pages"] == [1] and units["section=3;page=2"]["pages"] == [2]
    assert "547 times" in units["section=2;page=1"]["text"]
    assert "Dataset | Samples" in units["section=2;page=1"]["text"]
    assert "Dataset | Samples" in units["section=2;table=1"]["text"]
    assert "Table 1: Datasets" in units["section=2;table=1"]["text"]
    assert "Page 1 of 2" not in "".join(u["text"] for u in st["units"])
    assert units["section=2;table=1"]["regions"] == [{"p": 1, "r": ["0.1000", "0.4500", "0.9000", "0.7000"]}]


def test_a_citation_of_a_pdf_that_is_not_a_regulation_resolves():
    doc = _report()
    st = generic_structure(doc, SHA, correct=False)
    literal = "reduces training time 547 times"
    # Without the original on this machine integrity is not checked, but the structure conforms.
    assert _resolve(st, _anchor(doc, literal), literal) == "uncheckable"


def test_a_citation_resolved_with_the_original(tmp_path):
    doc = _report()
    st = generic_structure(doc, SHA, correct=False)
    path = tmp_path / "original.pdf"
    path.write_bytes(ORIGINAL)
    literal = "496800"
    assert _resolve(st, _anchor(doc, literal), literal, original_path=path) == "resolved"


def test_wrong_page_or_invented_literal_stay_broken():
    doc = _report()
    st = generic_structure(doc, SHA, correct=False)
    literal = "reduces training time 547 times"
    assert _resolve(st, "pdf-v1:p=2", literal) == "broken"
    assert _resolve(st, "pdf-v1:p=1", "reduces training time 600 times") == "broken"
    assert _resolve(st, "pdf-v1:p=3", literal) == "broken"


def test_generic_keys_are_not_a_norm_locator():
    st = generic_structure(_report(), SHA, correct=False)
    for unit in st["units"]:
        try:
            parse_(f"norm-v1:{unit['key']}")
        except InvalidLocator:
            continue
        raise AssertionError(f"{unit['key']} can be cited as norm-v1")


def test_content_before_the_first_heading():
    texts = [_text(0, "Text without a previous heading."), _text(1, "1 Scope", "section_header", box=(0.1, 0.3, 0.9, 0.33))]
    st = generic_structure(_doc(["#/texts/0", "#/texts/1"], texts), SHA, correct=False)
    assert [(u["key"], u["title"]) for u in st["units"]] == [
        ("section=0;page=1", None),
        ("section=1;page=1", "1 Scope"),
    ]


def test_wrong_page_within_the_same_section_is_broken():
    texts = [
        _text(0, "1 Method", "section_header"),
        _text(1, "The first phase trains the two autoencoders.", box=(0.1, 0.2, 0.9, 0.3)),
        _text(2, "The second phase is adversarial.", page=2, box=(0.1, 0.1, 0.9, 0.2)),
    ]
    split = _text(3, "This paragraph starts on one page and ends on the next one.", page=2, box=(0.1, 0.8, 0.9, 0.9))
    split["prov"].append({"page_no": 3, "bbox": _box(0.1, 0.1, 0.9, 0.15)})
    doc = _doc([f"#/texts/{i}" for i in range(4)], [*texts, split], pages=3)
    st = generic_structure(doc, SHA)
    assert [u["key"] for u in st["units"]] == ["section=1;page=1", "section=1;page=2", "section=1;page=3"]
    assert _resolve(st, "pdf-v1:p=2", "The second phase is adversarial") == "uncheckable"
    assert _resolve(st, "pdf-v1:p=1", "The second phase is adversarial") == "broken"
    # The paragraph split between pages 2 and 3 is cited on either of them, and on no other.
    for page, state in ((2, "uncheckable"), (3, "uncheckable"), (1, "broken")):
        assert _resolve(st, f"pdf-v1:p={page}", "ends on the next one") == state


def _two_columns():
    """A two-column page that Docling gets wrong: the introduction before the abstract and the table far from its text."""
    left, right = (0.08, 0.48), (0.52, 0.92)
    texts = [
        _text(0, "Anomaly detection", "title", box=(0.1, 0.05, 0.9, 0.1)),
        _text(1, "1 INTRODUCTION", "section_header", box=(right[0], 0.15, right[1], 0.18)),
        _text(2, "Monitoring is a challenge.", box=(right[0], 0.2, right[1], 0.5)),
        _text(3, "ABSTRACT", "section_header", box=(left[0], 0.15, left[1], 0.18)),
        _text(4, "We propose a method.", box=(left[0], 0.2, left[1], 0.5)),
        _text(5, "2 DATA", "section_header", box=(left[0], 0.55, left[1], 0.58)),
        _text(6, "Table 1 describes the datasets.", box=(left[0], 0.6, left[1], 0.9)),
        _text(7, "Algorithm 1 Training", "section_header", box=(right[0], 0.55, right[1], 0.58)),
        _text(8, "repeat until convergence", "code", box=(right[0], 0.6, right[1], 0.7)),
        _text(9, "3 METHOD", "section_header", page=2, box=(left[0], 0.1, left[1], 0.13)),
        _text(10, "It is trained in two phases.", page=2, box=(left[0], 0.15, left[1], 0.4)),
        _text(11, "Table 1: Datasets", "caption", page=2, box=(right[0], 0.1, right[1], 0.13)),
    ]
    table = _table(
        0, [[_cell("SWaT", 0, 0), _cell("51", 0, 1)]], page=2, box=(right[0], 0.15, right[1], 0.3), children=["#/texts/11"]
    )
    body = [f"#/texts/{i}" for i in range(11)] + ["#/tables/0"]
    return _doc(body, texts, [table])


def test_two_columns_are_read_left_then_right():
    st = generic_structure(_two_columns(), SHA)
    sections = [u for u in st["units"] if u["level"] == 0 and u["pages"] == [1]]
    assert [u["title"] for u in sections] == ["Anomaly detection", "ABSTRACT", "2 DATA", "1 INTRODUCTION"]
    by_title = {u["title"]: u for u in sections}
    assert "We propose a method." in by_title["ABSTRACT"]["text"]
    assert "Monitoring is a challenge." in by_title["1 INTRODUCTION"]["text"]
    assert any("page 1: reading order corrected" in a for a in st["warnings"])


def test_an_algorithm_label_does_not_open_a_section_and_the_table_goes_with_whoever_mentions_it():
    st = generic_structure(_two_columns(), SHA)
    units = {u["key"]: u for u in st["units"]}
    assert not any(u.get("title", "").startswith("Algorithm") for u in st["units"] if u.get("title"))
    data = next(c for c, u in units.items() if u.get("title") == "2 DATA").split(";")[0]
    assert f"{data};table=1" in units
    assert "Table 1 describes" in units[f"{data};page=1"]["text"]
    assert "SWaT | 51" in units[f"{data};page=2"]["text"]
    assert any("is a label" in a for a in st["warnings"]) and any("tables or figures" in a for a in st["warnings"])


def test_without_correcting_docling_order_is_kept():
    st = generic_structure(_two_columns(), SHA, correct=False)
    titles = [u["title"] for u in st["units"] if u["level"] == 0]
    assert titles[:3] == ["Anomaly detection", "1 INTRODUCTION", "ABSTRACT"]
    assert "Algorithm 1 Training" in titles and st["warnings"] == []


def test_a_single_column_with_short_lines_is_read_top_to_bottom():
    texts = [
        _text(0, "Subject", box=(0.1, 0.1, 0.3, 0.13)),
        _text(1, "Madrid, 3 May", box=(0.6, 0.15, 0.9, 0.18)),
        _text(2, "Dear customer:", box=(0.1, 0.2, 0.35, 0.23)),
        _text(3, "Please find attached the requested report with the measurements of the campaign.", box=(0.1, 0.25, 0.9, 0.4)),
    ]
    st = generic_structure(_doc([f"#/texts/{i}" for i in (3, 2, 1, 0)], texts), SHA)
    assert st["units"][0]["text"].split("\n") == [t["text"] for t in texts]


def test_three_columns_are_left_alone():
    boxes = [(0.05, 0.1, 0.32, 0.9), (0.36, 0.1, 0.64, 0.9), (0.68, 0.1, 0.95, 0.9)]
    texts = [_text(i, f"column {i}", box=c) for i, c in enumerate(boxes)]
    st = generic_structure(_doc(["#/texts/2", "#/texts/0", "#/texts/1"], texts), SHA)
    assert st["units"][0]["text"].split("\n") == ["column 2", "column 0", "column 1"]
    assert any("layout not recognized" in a for a in st["warnings"])


def test_a_piece_without_a_box_that_opens_the_section_goes_to_the_first_page_with_a_box():
    without_box = _text(0, "Preliminary note without position.")
    without_box["prov"] = []
    texts = [without_box, _text(1, "First paragraph with position.", page=2)]
    st = generic_structure(_doc(["#/texts/0", "#/texts/1"], texts), SHA)
    (unit,) = st["units"]
    assert unit["key"] == "section=0;page=2"
    assert unit["text"] == "Preliminary note without position.\nFirst paragraph with position."


def test_next_page_within_a_multi_page_document_is_broken():
    doc = _report()
    st = generic_structure(doc, SHA)
    assert _resolve(st, "pdf-v1:p=1", "No regressions were observed") == "broken"
    assert _resolve(st, "pdf-v1:p=2", "No regressions were observed") == "uncheckable"


def test_a_word_file_hangs_content_from_its_headings_and_each_heading_opens_a_section():
    """Docling nests a Word file: title › heading › paragraphs and tables, without pages or boxes."""

    def node(i, label, text, children=()):
        return {"self_ref": f"#/texts/{i}", "label": label, "text": text, "prov": [],
                "children": [{"$ref": h} for h in children]}

    texts = [
        node(0, "title", "Engineering plan", ["#/texts/1", "#/texts/3"]),
        node(1, "section_header", "1 Goal", ["#/texts/2"]),
        node(2, "text", "Detect leaks in the network."),
        node(3, "section_header", "2 Risks", ["#/texts/4"]),
        node(4, "text", "The pilot does not cover Murcia."),
    ]
    st = generic_structure(_doc(["#/texts/0"], texts, pages=0), SHA)
    assert [(u["key"], u["title"]) for u in st["units"]] == [
        ("section=1", "Engineering plan"),
        ("section=2", "1 Goal"),
        ("section=3", "2 Risks"),
    ]
    assert "The pilot does not cover Murcia." in st["units"][2]["text"]
    assert "The pilot does not cover Murcia." not in st["units"][0]["text"]
