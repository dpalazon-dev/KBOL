"""The whole chain for a PDF, with Docling and pypdf replaced by doubles at their border."""

import json

import pytest
from di import add as module
from di import crosscheck
from di.locate import locate
from di.store import read, save
from test_generic import _report

from kbol.citations import resolve_pdf
from kbol.locator import parse_

PAGES = {
    1: "Performance report\nThis report summarizes the measurements of the campaign.\n1 Results\n"
    "The method reduces training time 547 times on average.\nDataset Samples\nSWaT 496800\n"
    "Table 1: Datasets\nPage 1 of 2",
    2: "2 Conclusions\nNo regressions were observed.",
}


def _test_docling(fingerprint, store, extension=".pdf"):
    data = json.dumps(_report(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    sha, _ = save(data, store)
    return {"sha256": sha, "derived_from": fingerprint, "processor": "docling", "version": "test", "pages": 2}


def _add(tmp_path, monkeypatch, pages=PAGES):
    monkeypatch.setattr(module, "process", _test_docling)
    monkeypatch.setattr(crosscheck, "text_by_page", lambda data: pages)
    origin = tmp_path / "report.pdf"
    origin.write_bytes(b"%PDF-1.7 report")
    store = tmp_path / "store"
    return module.add(origin, store), store, origin


def test_add_leaves_a_representation_the_resolver_accepts(tmp_path, monkeypatch):
    res, store, origin = _add(tmp_path, monkeypatch)
    assert res["review"] == []
    assert res["structure"]["derived_from"] == res["docling"]["sha256"]
    assert res["structure"]["original"] == res["original"]["sha256"]
    structure = json.loads(read(res["structure"]["sha256"], store))
    doc = json.loads(read(res["docling"]["sha256"], store))
    literal = "reduces training time 547 times"
    region = locate(doc, literal)[0][0]
    anchor = f"pdf-v1:p={region['p']};r={','.join(region['r'])}"
    r = resolve_pdf(
        parse_(anchor), original_sha256=res["original"]["sha256"], original_path=origin, structure=structure, literal=literal
    )
    assert r.state == "resolved"
    report = json.loads(read(res["crosscheck"]["sha256"], store))
    assert report["inputs"]["structure"] == res["structure"]["sha256"]


def test_add_says_what_to_review_when_the_pdf_has_a_number_the_structure_lacks(tmp_path, monkeypatch):
    pages = {**PAGES, 1: PAGES[1] + "\nWADI 1048571"}
    res, _, _ = _add(tmp_path, monkeypatch, pages)
    assert any("numbers: 1 from the PDF missing" in warning for warning in res["review"])


def test_adding_the_same_pdf_twice_duplicates_nothing(tmp_path, monkeypatch):
    first, store, _ = _add(tmp_path, monkeypatch)
    objects = sorted(p.name for p in (store / "sha256").iterdir())
    second, _, _ = _add(tmp_path, monkeypatch)
    assert sorted(p.name for p in (store / "sha256").iterdir()) == objects
    assert second["structure"]["sha256"] == first["structure"]["sha256"]


def test_add_with_a_name_generates_the_document_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "process", _test_docling)
    monkeypatch.setattr(crosscheck, "text_by_page", lambda data: PAGES)
    origin = tmp_path / "report.pdf"
    origin.write_bytes(b"%PDF-1.7 report")
    res = module.add(origin, tmp_path / "state" / "store", name="report")
    folder = tmp_path / "state" / "documents" / "report"
    assert res["folder"]["folder"] == str(folder)
    assert (folder / "report.pdf").read_bytes() == b"%PDF-1.7 report"
    assert (folder / "index.md").exists() and (folder / "resources" / "tables" / "table-1.md").exists()


def test_html_goes_through_markitdown_and_is_cited_by_lines(tmp_path):
    origin = tmp_path / "advisory.html"
    origin.write_text(
        "<html><body><h1>Security advisory</h1><p>The manufacturer will not fix the vulnerability.</p></body></html>",
        encoding="utf-8",
    )
    store = tmp_path / "store"
    res = module.add(origin, store)
    assert "docling" not in res and "structure" not in res
    markdown = read(res["markdown"]["sha256"], store).decode("utf-8")
    assert "# Security advisory" in markdown and "will not fix the vulnerability" in markdown
    assert res["markdown"]["derived_from"] == res["original"]["sha256"]
    assert res["original"]["media_type"] == "text/html"


def test_unsupported_format(tmp_path):
    origin = tmp_path / "note.txt"
    origin.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported format"):
        module.add(origin, tmp_path / "store")


def test_an_origin_without_extension_comes_in_as_pdf(tmp_path, monkeypatch):
    """The URL of a PDF on EUR-Lex has no extension: it is treated as PDF, as before other formats were supported."""
    seen = []

    def process(fingerprint, store, extension=".pdf"):
        seen.append(extension)
        return _test_docling(fingerprint, store, extension)

    monkeypatch.setattr(module, "process", process)
    monkeypatch.setattr(crosscheck, "text_by_page", lambda data: PAGES)
    origin = tmp_path / "CELEX-32024R2847"
    origin.write_bytes(b"%PDF-1.7 norm")
    res = module.add(origin, tmp_path / "store")
    assert seen == [".pdf"] and res["original"]["media_type"] == "application/pdf" and "crosscheck" in res


def test_the_declared_format_overrides_the_extension(tmp_path):
    origin = tmp_path / "advisory.php"
    origin.write_text("<html><body><h1>Advisory</h1><p>No patch.</p></body></html>", encoding="utf-8")
    store = tmp_path / "store"
    res = module.add(origin, store, fmt="html")
    assert res["original"]["media_type"] == "text/html"
    assert "# Advisory" in read(res["markdown"]["sha256"], store).decode("utf-8")
    with pytest.raises(ValueError, match="unsupported format"):
        module.add(origin, store, fmt="txt")
