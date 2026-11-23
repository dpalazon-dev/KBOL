"""Document context of the generic structure: hierarchy, part type, tables with headers and references."""

from di.context import cited_references, hierarchy, part_type, table_cells
from di.generic import generic_structure
from test_generic import SHA, _box, _doc, _text


def _cell(text, row, col, header=False, row_header=False, rows=1, cols=1):
    return {
        "text": text,
        "start_row_offset_idx": row,
        "end_row_offset_idx": row + rows,
        "start_col_offset_idx": col,
        "end_col_offset_idx": col + cols,
        "row_span": rows,
        "col_span": cols,
        "column_header": header,
        "row_header": row_header,
        "bbox": _box(0.1 + 0.05 * col, 0.5 + 0.02 * row, 0.14 + 0.05 * col, 0.52 + 0.02 * row),
    }


def _grid(cells, num_rows, num_cols):
    """Docling's grid: each row with one cell per column; a merged cell is repeated in each slot it spans."""
    grid = [[None] * num_cols for _ in range(num_rows)]
    for c in cells:
        for f in range(c["start_row_offset_idx"], c["end_row_offset_idx"]):
            for k in range(c["start_col_offset_idx"], c["end_col_offset_idx"]):
                grid[f][k] = c
    return grid


def _results_table():
    """Like Table 2 of USAD: two levels of merged headers, row label and a second block below."""
    cells = [
        _cell("Methods", 0, 0, header=True, rows=2),
        _cell("SWaT", 0, 1, header=True, cols=2),
        _cell("WADI", 0, 3, header=True),
        _cell("Without", 1, 1, header=True),
        _cell("With", 1, 2, header=True),
        _cell("Without", 1, 3, header=False),  # Docling sometimes misses a header cell
        _cell("AE", 2, 0, row_header=True),
        _cell("0.7697", 2, 1),
        _cell("0.8233", 2, 2),
        _cell("0.2315", 2, 3),
        _cell("USAD", 3, 0, row_header=True),
        _cell("0.7917", 3, 1),
        _cell("0.8460", 3, 2),
        _cell("0.2328", 3, 3),
        _cell("Methods", 4, 0, header=True),
        _cell("SMD", 4, 1, header=True, cols=3),
        _cell("USAD", 5, 0, row_header=True),
        _cell("0.9382", 5, 1),
        _cell("0.9463", 5, 2),
        _cell("0.9109", 5, 3),
    ]
    return {"data": {"grid": _grid(cells, 6, 4), "num_rows": 6, "num_cols": 4}, "prov": [{"page_no": 1}]}


def test_each_table_value_carries_its_headers_and_its_row():
    cells = {(tuple(c["row_label"]), tuple(c["headers"])): c["text"] for c in table_cells(_results_table())}
    assert cells[(("USAD",), ("SWaT", "Without"))] == "0.7917"
    assert cells[(("AE",), ("SWaT", "With"))] == "0.8233"
    assert cells[(("USAD",), ("WADI", "Without"))] == "0.2328"


def test_a_second_header_block_replaces_the_first():
    cells = [c for c in table_cells(_results_table()) if c["text"] == "0.9382"]
    assert [c["headers"] for c in cells] == [["SMD"]]


def test_a_value_cell_keeps_its_position():
    (c,) = [c for c in table_cells(_results_table()) if c["text"] == "0.7917"]
    assert (c["row"], c["col"], c["p"]) == (3, 1, 1)


def test_a_table_without_headers_gives_cells_without_headers():
    cells = [_cell("a", 0, 0), _cell("b", 0, 1)]
    table = {"data": {"grid": _grid(cells, 1, 2), "num_rows": 1, "num_cols": 2}, "prov": [{"page_no": 2}]}
    assert [(c["text"], c["headers"], c["row_label"]) for c in table_cells(table)] == [("a", [], []), ("b", [], ["a"])]


def test_hierarchy_by_numbering():
    titles = [
        "Anomaly detection",
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
    j = hierarchy(titles)
    assert [x["number"] for x in j] == [None, None, "1", "5", "5.1", "5.1.1", "5.3", None, "A", "A.1"]
    assert [x["depth"] for x in j] == [1, 1, 1, 1, 2, 3, 2, 1, 1, 2]
    assert j[5]["parent"] == 4 and j[4]["parent"] == 3 and j[6]["parent"] == 3 and j[9]["parent"] == 8
    assert j[2]["parent"] is None


def test_a_letter_only_numbers_an_appendix():
    j = hierarchy(["1 Introduction", "A Novel Approach to Detection", "REFERENCES", "B Proofs"])
    assert [x["number"] for x in j] == ["1", None, None, "B"]


def test_a_number_without_a_parent_hangs_from_the_root():
    j = hierarchy(["2.3 Orphan"])
    assert j[0]["parent"] is None and j[0]["depth"] == 2


def test_part_type():
    assert part_type("ABSTRACT") == "abstract"
    assert part_type("1 Introduction") == "introduction"
    assert part_type("2 RELATED WORK") == "related_work"
    assert part_type("3 Method") == "method"
    assert part_type("5 EXPERIMENTS AND RESULTS") == "experiments"
    assert part_type("6 CONCLUSIONS") == "conclusions"
    assert part_type("REFERENCES") == "references"
    assert part_type("A SUPPLEMENTARY MATERIAL FOR REPRODUCIBILITY") == "appendix"
    assert part_type("Acknowledgments") == "acknowledgments"
    assert part_type("5.3 Training time") is None


def test_part_type_of_spanish_headings():
    """Documents in Spanish are processed too: their headings are recognized with the same part types."""
    assert part_type("RESUMEN") == "abstract"
    assert part_type("1 Introducción") == "introduction"
    assert part_type("2 Estado del arte") == "related_work"
    assert part_type("3 Método") == "method"
    assert part_type("6 Conclusiones") == "conclusions"
    assert part_type("Bibliografía") == "references"
    assert part_type("Anexo A") == "appendix"
    assert part_type("Agradecimientos") == "acknowledgments"


def test_numeric_references_and_ranges():
    assert cited_references("as in [2] and [15, 21], and in [3-5].") == ["2", "15", "21", "3", "4", "5"]
    assert cited_references("the equation [x] and the interval [0, 1] are not citations") == []


def test_author_year_references():
    keys = cited_references("according to (Feng et al. 2021; Ma and Li 2022) and Wang et al. (2022a)", author_year=True)
    assert keys == ["feng 2021", "ma 2022", "wang 2022a"]


def _paper():
    texts = [
        _text(0, "Anomaly detection", "title", box=(0.1, 0.02, 0.9, 0.05)),
        _text(1, "ABSTRACT", "section_header", box=(0.1, 0.06, 0.9, 0.08)),
        _text(2, "We propose a method.", box=(0.1, 0.09, 0.9, 0.12)),
        _text(3, "5 EXPERIMENTS AND RESULTS", "section_header", box=(0.1, 0.13, 0.9, 0.15)),
        _text(4, "5.3 Training time", "section_header", box=(0.1, 0.16, 0.9, 0.18)),
        _text(5, "We follow the protocol of [2] and [1]; Table 1 summarizes the data.", box=(0.1, 0.19, 0.9, 0.25)),
        _text(6, "REFERENCES", "section_header", page=2, box=(0.1, 0.05, 0.9, 0.08)),
        _text(7, "Audibert et al. 2020. USAD.", "list_item", page=2, box=(0.1, 0.1, 0.9, 0.12), marker="[1]"),
        _text(8, "Goh et al. 2017. SWaT.", "list_item", page=2, box=(0.1, 0.13, 0.9, 0.15), marker="[2]"),
        _text(9, "Table 1: Results", "caption", box=(0.1, 0.3, 0.9, 0.32)),
    ]
    table = _results_table()
    table.update(self_ref="#/tables/0", label="table", children=[{"$ref": "#/texts/9"}])
    table["prov"] = [{"page_no": 1, "bbox": _box(0.1, 0.33, 0.9, 0.6)}]
    body = [f"#/texts/{i}" for i in range(9)] + ["#/tables/0"]
    return _doc(body, texts, [table])


def test_the_structure_carries_path_type_and_references_of_each_section():
    st = generic_structure(_paper(), SHA)
    by_title = {u["title"]: u for u in st["units"] if u["level"] == 0}
    sec = by_title["5.3 Training time"]
    assert sec["path"] == ["5 EXPERIMENTS AND RESULTS", "5.3 Training time"]
    assert sec["number"] == "5.3" and sec["part_type"] == "experiments"
    assert sec["parent"] == by_title["5 EXPERIMENTS AND RESULTS"]["key"].split(";")[0]
    assert sec["references"] == ["2", "1"]
    assert by_title["ABSTRACT"]["part_type"] == "abstract"
    refs = {r["key"]: r for r in st["references"]}
    assert refs["2"]["text"].startswith("Goh et al. 2017") and refs["2"]["pages"] == [2]


def test_the_table_of_the_structure_has_cells_with_headers_and_the_section_that_mentions_it():
    st = generic_structure(_paper(), SHA)
    (table,) = [u for u in st["units"] if ";table=" in u["key"]]
    assert table["caption"] == "Table 1: Results"
    assert table["path"] == ["5 EXPERIMENTS AND RESULTS", "5.3 Training time"]
    cell = next(c for c in table["cells"] if c["row_label"] == ["USAD"] and c["headers"] == ["SWaT", "Without"])
    assert cell["text"] == "0.7917"
    # The text of the table is still the PDF's: the headers are not mixed into what is cited.
    assert "SWaT / Without" not in table["text"]


def test_a_citation_without_an_entry_in_the_bibliography_is_warned():
    """The bibliography has [1] and [3]; the text cites [2], which was lost when reading the PDF."""
    doc = _paper()
    doc["texts"][8]["marker"] = "[3]"
    st = generic_structure(doc, SHA)
    assert any("citations without an entry in the bibliography: [2]" in a for a in st["warnings"])


def test_headings_with_control_characters_or_glued_words():
    assert part_type("2 Background") == "related_work"
    assert part_type("3 Method") == "method"
    assert part_type("2 RELATEDWORK") == "related_work"
    assert part_type("3 INTRODUCING THE UCR ANOMALY ARCHIVE") is None
    assert part_type("8 Discussion and Conclusion") == "conclusions"
    assert hierarchy(["3 Method"])[0]["number"] == "3"


def test_a_numbered_item_that_does_not_advance_hangs_from_the_last_section():
    j = hierarchy(["3 Method", "3.3 Scoring", "1. Discrimination", "2. Reconstruction", "4 Attacks"])
    assert [x["number"] for x in j] == ["3", "3.3", None, None, "4"]
    assert j[2]["parent"] == 1 and j[3]["parent"] == 1 and j[2]["steps_back"] is True
    assert j[4]["parent"] is None and j[4]["depth"] == 1


def test_brackets_with_numbers_greater_than_the_bibliography_are_not_citations():
    assert cited_references("sizes [50, 100] and the citation [3]", maximum=21) == ["3"]


def test_bibliography_entry_with_a_dot_marker():
    from di.context import entry_key

    assert entry_key("G. Jonathan et al., Anomaly detection.", "1.") == ("1", True)
    assert entry_key("Abdulaal A, Liu Z (2021) Practical approach", "") == ("abdulaal 2021", False)


def test_inside_an_appendix_everything_is_appendix():
    texts = [
        _text(0, "REFERENCES", "section_header", box=(0.1, 0.05, 0.9, 0.08)),
        _text(1, "A SUPPLEMENTARY MATERIAL", "section_header", box=(0.1, 0.1, 0.9, 0.12)),
        _text(2, "A.1 Experimental Setting", "section_header", box=(0.1, 0.13, 0.9, 0.15)),
        _text(3, "We use a GPU.", box=(0.1, 0.16, 0.9, 0.2)),
    ]
    st = generic_structure(_doc([f"#/texts/{i}" for i in range(4)], texts), SHA)
    (u,) = [u for u in st["units"] if u["title"] == "A.1 Experimental Setting"]
    assert u["part_type"] == "appendix" and u["number"] == "A.1"


def test_an_unmarked_first_row_of_text_over_numbers_is_a_header():
    cells = [_cell("Method", 0, 0), _cell("Precision", 0, 1), _cell("USAD", 1, 0), _cell("0.7448", 1, 1)]
    table = {"data": {"grid": _grid(cells, 2, 2), "num_rows": 2, "num_cols": 2}, "prov": [{"page_no": 9}]}
    assert [(c["text"], c["headers"], c["row_label"]) for c in table_cells(table)] == [
        ("USAD", ["Method"], []),
        ("0.7448", ["Precision"], ["USAD"]),
    ]


def test_a_text_only_table_does_not_invent_headers():
    cells = [_cell("Attack", 0, 0), _cell("Effect", 0, 1), _cell("Injection", 1, 0), _cell("Overflows", 1, 1)]
    table = {"data": {"grid": _grid(cells, 2, 2), "num_rows": 2, "num_cols": 2}, "prov": [{"page_no": 1}]}
    assert all(c["headers"] == [] for c in table_cells(table))
