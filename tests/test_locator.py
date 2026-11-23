import pytest

from kbol.locator import Citation, InvalidLocator, Lines, Norm, Page, format_, parse_

COMBINED = "norm-v1:art=14;ap=2;let=a @ pdf-v1:p=37;r=0.1120,0.4300,0.8870,0.5120"


def test_round_trip_norm_pdf():
    citation = parse_(COMBINED)
    assert citation.logical == Norm((("art", "14"), ("ap", "2"), ("let", "a")))
    assert citation.physical == Page(37, ("0.1120", "0.4300", "0.8870", "0.5120"))
    assert citation.inherited is False
    assert citation.logical.key() == "art=14;ap=2;let=a"
    assert format_(citation) == COMBINED


def test_logical_only_and_page_only():
    assert parse_("norm-v1:anx=I;parte=I;pto=2;let=c") == Citation(
        Norm((("anx", "I"), ("parte", "I"), ("pto", "2"), ("let", "c"))), None
    )
    assert parse_("pdf-v1:p=3") == Citation(None, Page(3, None))
    assert format_(parse_("pdf-v1:p=3")) == "pdf-v1:p=3"


def test_lines():
    citation = parse_("lines-v1:10-18")
    assert citation == Citation(None, Lines(10, 18))
    assert format_(citation) == "lines-v1:10-18"


@pytest.mark.parametrize(
    "anchor, start, end",
    [("l. 66-84 (§3, consumption map)", 66, 84), ("L10-L20", 10, 20), ("l. 161-167", 161, 167), ("l. 106", 106, 106)],
)
def test_legacy(anchor, start, end):
    citation = parse_(anchor)
    assert citation.physical == Lines(start, end)
    assert citation.inherited is True


@pytest.mark.parametrize(
    "anchor",
    [
        "pdf-v1:p=1;r=0.1,0.2,1.2,0.3",  # outside 0-1
        "pdf-v1:p=1;r=0.5,0.2,0.4,0.3",  # x0 >= x1
        "pdf-v1:p=1;r=0.1,0.3,0.4,0.3",  # y0 >= y1
        "pdf-v1:p=1;r=0.12345,0.2,0.4,0.3",  # more than four decimals
        "pdf-v1:p=1;r=0.1,0.2,0.4",  # three coordinates
    ],
)
def test_invalid_region(anchor):
    with pytest.raises(InvalidLocator):
        parse_(anchor)


@pytest.mark.parametrize(
    "anchor",
    [
        "pdf-v1:p=0",
        "norm-v1:ap=2;art=14",  # key order
        "norm-v1:art=14;foo=2",  # unknown key
        "norm-v1:art=14;art=15",  # repeated key
        "norm-v1:art=",  # empty value
        "lines-v1:20-10",
        "lines-v1:0-3",
        "norm-v1:art=14 @ lines-v1:1-2",  # logical with lines
        "pdf-v1:p=3 @ pdf-v1:p=4",
        "",
        "l. 30-40 and l. 135-147",  # two ranges: not a locator
    ],
)
def test_invalid(anchor):
    with pytest.raises(InvalidLocator):
        parse_(anchor)
