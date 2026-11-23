"""Crosscheck of a structure with the per-page text of a second extractor."""

from di.crosscheck import coverage, crosscheck, furniture_by_page, missing_numbers


def _structure(units, pages=(1, 2)):
    return {"pages": [{"p": p} for p in pages], "units": units}


def _unit(key, page, text, level=0):
    return {"key": key, "level": level, "pages": [page], "text": text}


BASE = {
    1: "Performance report\nThe method reduces the time 547 times.\nDataset Samples\nSWaT 496800\nWADI 1048571\n3",
    2: "Conclusions\nNo regressions were observed in 12 trials.\n4",
}
FURNITURE = {1: "3", 2: "4"}


def _faithful():
    return [
        _unit("section=1;page=1", 1, "Performance report\nThe method reduces the time 547 times.\nDataset | Samples\nSWaT | 496800\nWADI | 1048571"),
        _unit("section=1;table=1", 1, "Dataset | Samples\nSWaT | 496800\nWADI | 1048571", level=1),
        _unit("section=2;page=2", 2, "Conclusions\nNo regressions were observed in 12 trials."),
    ]


def test_a_faithful_structure_has_no_failures():
    res = crosscheck(_structure(_faithful()), BASE, FURNITURE)
    assert res["failures"] == []
    assert res["summary"]["document_recall"] == 1.0 and res["summary"]["document_support"] == 1.0
    assert res["tables"] == [{"key": "section=1;table=1", "pages": [1], "numbers": 2, "unsupported_numbers": []}]


def test_a_number_lost_in_a_table_is_flagged():
    units = _faithful()
    units[0]["text"] = units[0]["text"].replace("1048571", "")
    res = crosscheck(_structure(units), BASE, FURNITURE)
    (failure,) = res["failures"]
    assert failure["p"] == 1 and failure["missing_numbers"] == ["1048571"]
    assert res["summary"]["missing_numbers"] == 1


def test_an_altered_number_is_flagged_both_ways_and_in_its_table():
    units = _faithful()
    for u in units[:2]:
        u["text"] = u["text"].replace("496800", "496900")
    res = crosscheck(_structure(units), BASE, FURNITURE)
    (failure,) = res["failures"]
    assert failure["missing_numbers"] == ["496800"] and failure["unsupported_numbers"] == ["496900"]
    assert res["tables"][0]["unsupported_numbers"] == ["496900"]
    assert res["summary"]["tables_with_unsupported_numbers"] == 1


def test_a_lost_paragraph_lowers_the_recall_of_its_page():
    units = _faithful()
    units[2]["text"] = "Conclusions"
    res = crosscheck(_structure(units), BASE, FURNITURE)
    assert res["summary"]["pages_with_low_recall"] == [2]
    assert res["pages"][0]["recall"] == 1.0


def test_text_the_pdf_does_not_have_nearby_lowers_the_support():
    units = _faithful() + [_unit("section=3;page=4", 4, "This text belongs to an appendix that the PDF does not have here.")]
    base = {**BASE, 3: "", 4: ""}
    res = crosscheck(_structure(units, pages=(1, 2, 3, 4)), base, FURNITURE)
    assert res["summary"]["pages_with_low_support"] == [4]


def test_a_page_without_a_text_layer_is_declared():
    res = crosscheck(_structure(_faithful(), pages=(1, 2, 3)), {**BASE, 3: ""}, FURNITURE)
    assert res["summary"]["pages_without_text_layer"] == [3]
    assert [f["p"] for f in res["failures"]] == [3]


def test_furniture_does_not_count_as_a_loss():
    without = crosscheck(_structure(_faithful()), BASE)
    assert [f["missing_numbers"] for f in without["failures"]] == [["3"], ["4"]]
    assert crosscheck(_structure(_faithful()), BASE, FURNITURE)["failures"] == []


def test_words_split_or_glued_by_the_second_extractor_are_not_a_failure():
    assert coverage("the manu facturer will noti fy", "The manufacturer will notify") == 1.0
    assert coverage("themanufacturer will notify", "The manufacturer will notify") == 1.0
    assert coverage("the manufacturer will report", "The manufacturer will notify") < 1.0


def test_short_numbers_require_an_exact_match():
    assert missing_numbers("value 51", "value 0.5123") == ["51"]
    assert missing_numbers("0.9903 0.6295", "0.99030.6295") == []


def test_furniture_by_page():
    doc = {
        "texts": [
            {"label": "page_header", "text": "Official Journal", "prov": [{"page_no": 2}]},
            {"label": "page_footer", "text": "17", "prov": [{"page_no": 2}]},
            {"label": "text", "text": "body", "prov": [{"page_no": 2}]},
        ]
    }
    assert furniture_by_page(doc) == {2: "Official Journal\n17"}


def test_a_lost_paragraph_lowers_the_recall_even_if_its_words_are_elsewhere():
    base = {1: "The manufacturer will report the incident.\nThe manufacturer will report the incident to the authority."}
    units = [_unit("section=1;page=1", 1, "The manufacturer will report the incident to the authority.")]
    res = crosscheck(_structure(units, pages=(1,)), base)
    assert res["pages"][0]["recall"] < 0.7
    assert res["summary"]["pages_with_low_recall"] == [1]


def test_support_does_not_detect_text_on_the_next_page():
    """Declared limit: a text placed on the page next to its own is supported."""
    base = {1: "First page with its own content.", 2: "Second page with some other different content."}
    units = [
        _unit("section=1;page=1", 1, "First page with its own content.\nSecond page with some other different content."),
    ]
    res = crosscheck(_structure(units), base)
    assert res["pages"][0]["support"] == 1.0
    assert res["summary"]["pages_with_low_recall"] == [2]
