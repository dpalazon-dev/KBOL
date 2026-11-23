"""Citation resolver (`kbol citations`): norm-v1 and pdf-v1 against a structure-v1 representation, and lines.

The norm text of the representation is a Spanish regulation, as in the documents the `norm-v1` profile is made for:
the literal quotes in Spanish (and their accents and hyphenation) are deliberate test data.
"""

import hashlib
import json
import subprocess

import pytest

from kbol.citations import check, normalize, resolve_lines, resolve_pdf
from kbol.cli import main
from kbol.locator import parse_

ORIGINAL = b"%PDF-1.7 test original"
SHA_ORIGINAL = hashlib.sha256(ORIGINAL).hexdigest()


def _structure(**changes):
    structure = {
        "profile": "structure-v1",
        "original_sha256": SHA_ORIGINAL,
        "pages": [{"p": 1, "width": 595.0, "height": 842.0}, {"p": 2, "width": 595.0, "height": 842.0}],
        "units": [
            {
                "key": "art=14",
                "pages": [1, 2],
                "regions": [{"p": 1, "r": ["0.1", "0.5", "0.9", "0.9"]}, {"p": 2, "r": ["0.1", "0.1", "0.9", "0.3"]}],
                "text": "Artículo 14\n1. El fabricante notificará simultáneamente al CSIRT. 2. La obli-\ngación «no» cesa.",
            },
            {
                "key": "art=14;ap=2",
                "pages": [2],
                "regions": [{"p": 2, "r": ["0.1", "0.1", "0.9", "0.3"]}],
                "text": "2. La obli-\ngación «no» cesa.",
            },
            {"key": "art=2", "pages": [1], "regions": [], "text": "Artículo 2 Ámbito"},
            {"key": "art=2", "pages": [2], "regions": [], "text": "Artículo 2 citado en un anexo"},
        ],
    }
    structure.update(changes)
    return structure


@pytest.fixture
def original(tmp_path):
    path = tmp_path / "orig.pdf"
    path.write_bytes(ORIGINAL)
    return path


def _pdf(anchor, original, literal=None, structure=None, sha=SHA_ORIGINAL):
    return resolve_pdf(
        parse_(anchor),
        original_sha256=sha,
        original_path=original,
        structure=structure or _structure(),
        literal=literal,
    )


def test_resolved(original):
    r = _pdf("norm-v1:art=14;ap=2 @ pdf-v1:p=2;r=0.2,0.15,0.5,0.2", original, literal="La obligación «no» cesa")
    assert r.state == "resolved", r.reason


def test_missing_original_is_uncheckable(tmp_path):
    r = _pdf("norm-v1:art=14 @ pdf-v1:p=1", tmp_path / "does-not-exist.pdf")
    assert r.state == "uncheckable"
    r = _pdf("norm-v1:art=14 @ pdf-v1:p=1", None)
    assert r.state == "uncheckable"


def test_different_fingerprint_is_broken(tmp_path):
    other = tmp_path / "other.pdf"
    other.write_bytes(b"other bytes")
    assert _pdf("norm-v1:art=14 @ pdf-v1:p=1", other).state == "broken"


def test_representation_of_another_original(original):
    structure = _structure(original_sha256="0" * 64)
    assert _pdf("norm-v1:art=14 @ pdf-v1:p=1", original, structure=structure).state == "broken"


def test_missing_page(original):
    assert _pdf("norm-v1:art=14 @ pdf-v1:p=9", original).state == "broken"


def test_missing_unit(original):
    assert _pdf("norm-v1:art=15 @ pdf-v1:p=1", original).state == "broken"


def test_unit_on_another_page_is_inconsistent(original):
    assert _pdf("norm-v1:art=14;ap=2 @ pdf-v1:p=1", original).state == "inconsistent"


def test_region_outside_the_unit_is_inconsistent(original):
    r = _pdf("norm-v1:art=14;ap=2 @ pdf-v1:p=2;r=0.1,0.6,0.9,0.8", original)
    assert r.state == "inconsistent"


def test_repeated_key_is_ambiguous(original):
    assert _pdf("norm-v1:art=2 @ pdf-v1:p=1", original).state == "ambiguous"


def test_missing_literal_is_broken(original):
    assert _pdf("norm-v1:art=14 @ pdf-v1:p=1", original, literal="el importador").state == "broken"


def test_missing_page_selector_is_broken(original):
    assert _pdf("norm-v1:art=14", original).state == "broken"


def test_words_split_in_the_representation(original):
    structure = _structure()
    structure["units"][0]["text"] = "El fabri cante notifi cará simultá neamente"
    r = _pdf(
        "norm-v1:art=14 @ pdf-v1:p=1", original, literal="El fabricante notificará simultáneamente", structure=structure
    )
    assert r.state == "resolved"
    assert "without spaces" in r.reason


def test_normalize():
    assert normalize("La obli-\ngación  “no” cesa­") == normalize('la obligación "no" cesa')


TEXT = "one\ntwo\nthree\nfour\n"
SHA_TEXT = hashlib.sha256(TEXT.encode()).hexdigest()


def test_lines():
    assert resolve_lines(parse_("lines-v1:2-3"), text=TEXT, expected_sha256=SHA_TEXT).state == "resolved"
    assert resolve_lines(parse_("lines-v1:2-9"), text=TEXT, expected_sha256=SHA_TEXT).state == "broken"
    assert resolve_lines(parse_("lines-v1:2-3"), text=TEXT, expected_sha256="0" * 64).state == "broken"
    r = resolve_lines(parse_("L2-L3"), text=TEXT, expected_sha256=SHA_TEXT, literal="three")
    assert r.state == "resolved"
    assert "legacy" in r.reason
    r = resolve_lines(parse_("lines-v1:1-2"), text=TEXT, expected_sha256=SHA_TEXT, literal="four")
    assert r.state == "broken"


def _record(path, header):
    lines = ["---"]
    for key, value in header.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines += ["---", "", "# Test", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_check_store_and_git(tmp_path):
    root = tmp_path / "repo"
    (root / "kb").mkdir(parents=True)
    _git(root, "init", "-q")
    (root / "doc.md").write_text(TEXT, encoding="utf-8", newline="\n")
    _git(root, "add", "doc.md")
    _git(root, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "doc")
    rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    store = tmp_path / "store"
    (store / "sha256").mkdir(parents=True)
    (store / "sha256" / SHA_ORIGINAL).write_bytes(ORIGINAL)
    structure = json.dumps(_structure()).encode()
    sha_structure = hashlib.sha256(structure).hexdigest()
    (store / "sha256" / sha_structure).write_bytes(structure)

    _record(
        root / "kb" / "SRC-1.md",
        {"id": "SRC-1", "type": "source", "location": f"store:sha256/{SHA_ORIGINAL}", "sha256": SHA_ORIGINAL},
    )
    _record(
        root / "kb" / "SRC-2.md",
        {"id": "SRC-2", "type": "source", "location": f"store:sha256/{sha_structure}", "sha256": sha_structure},
    )
    _record(
        root / "kb" / "SRC-3.md", {"id": "SRC-3", "type": "source", "location": f"git:{rev}:doc.md", "sha256": SHA_TEXT}
    )
    _record(
        root / "kb" / "FACT-1.md",
        {
            "id": "FACT-1",
            "type": "fact",
            "sources": [
                {
                    "id": "s1",
                    "resource": "SRC-1",
                    "representation_id": "SRC-2",
                    "hash": SHA_ORIGINAL,
                    "anchor": "norm-v1:art=14;ap=2 @ pdf-v1:p=2",
                    "context": "La obligación «no» cesa",
                },
                {"id": "s2", "resource": "SRC-3", "anchor": "l. 2-3", "hash": SHA_TEXT},
                {"id": "s3", "resource": "SRC-3", "anchor": "l. 1-2 and l. 3-4"},
                {"id": "s4", "resource": "SRC-9", "anchor": "lines-v1:1-1"},
            ],
        },
    )
    res = check(root, ["kb"], store)
    states = {f["source"]: f["state"] for f in res["rows"]}
    assert states == {"s1": "resolved", "s2": "resolved", "s3": "uncheckable", "s4": "broken"}
    assert res["count"]["broken"] == 1

    without_store = {f["source"]: f["state"] for f in check(root, ["kb"], None)["rows"]}
    assert without_store["s1"] == "uncheckable"

    assert main(["citations", str(root), "--folder", "kb", "--store", str(store)]) == 3


DOCX = b"PK\x03\x04 test Word document"
SHA_DOCX = hashlib.sha256(DOCX).hexdigest()
DOCLING = b'{"schema_name": "DoclingDocument"}'
SHA_DOCLING = hashlib.sha256(DOCLING).hexdigest()
MARKDOWN = b"# Plan\n\n## Risks\n\nThe pilot does not cover the Murcia plant.\n"
SHA_MARKDOWN = hashlib.sha256(MARKDOWN).hexdigest()


def _document_without_pages(tmp_path, sources, with_original=True, extra_sources=()):
    """A Word file in the store, its DoclingDocument and the Markdown derived from it; a fact that cites by lines."""
    root, store = tmp_path / "repo", tmp_path / "store"
    (root / "kb").mkdir(parents=True)
    (store / "sha256").mkdir(parents=True)
    objects = [(SHA_DOCLING, DOCLING), (SHA_MARKDOWN, MARKDOWN)] + ([(SHA_DOCX, DOCX)] if with_original else [])
    for sha, data in objects:
        (store / "sha256" / sha).write_bytes(data)
    source_records = [
        {"id": "SRC-10", "type": "source", "subtype": "original", "location": f"store:sha256/{SHA_DOCX}", "sha256": SHA_DOCX},
        {"id": "SRC-11", "type": "source", "subtype": "derived", "location": f"store:sha256/{SHA_DOCLING}",
         "sha256": SHA_DOCLING, "format": "application/json", "derived_from": ["SRC-10"]},
        {"id": "SRC-12", "type": "source", "subtype": "derived", "location": f"store:sha256/{SHA_MARKDOWN}",
         "sha256": SHA_MARKDOWN, "format": "text/markdown", "derived_from": ["SRC-11"]},
        *extra_sources,
    ]
    for f in source_records:
        _record(root / "kb" / f"{f['id']}.md", f)
    _record(root / "kb" / "FACT-2.md", {"id": "FACT-2", "type": "fact", "sources": sources})
    return {f["source"]: f for f in check(root, ["kb"], store)["rows"]}


def _citation(anchor, **extra):
    return {"id": "s1", "resource": "SRC-10", "representation_id": "SRC-12", "hash": SHA_DOCX, "anchor": anchor, **extra}


def test_citation_by_lines_against_the_markdown_representation(tmp_path):
    rows = _document_without_pages(tmp_path, [_citation("lines-v1:5-5", context="does not cover the Murcia plant")])
    assert rows["s1"]["state"] == "resolved"


def test_citation_by_lines_against_the_representation_broken_without_the_literal(tmp_path):
    rows = _document_without_pages(tmp_path, [_citation("lines-v1:3-3", context="does not cover the Murcia plant")])
    assert rows["s1"]["state"] == "broken" and "does not appear" in rows["s1"]["reason"]


def test_representation_of_another_document_is_broken(tmp_path):
    other = {"id": "SRC-20", "type": "source", "subtype": "original", "location": "store:sha256/" + "0" * 64,
             "sha256": "0" * 64}
    citation = {"id": "s1", "resource": "SRC-20", "representation_id": "SRC-12", "anchor": "lines-v1:5-5"}
    rows = _document_without_pages(tmp_path, [citation], extra_sources=[other])
    assert rows["s1"]["state"] == "broken" and "does not derive" in rows["s1"]["reason"]


def test_a_representation_that_is_not_text_is_broken(tmp_path):
    citation = _citation("lines-v1:1-1")
    citation["representation_id"] = "SRC-11"
    rows = _document_without_pages(tmp_path, [citation])
    assert rows["s1"]["state"] == "broken" and "text" in rows["s1"]["reason"]


def test_without_the_original_the_citation_by_lines_is_uncheckable(tmp_path):
    rows = _document_without_pages(tmp_path, [_citation("lines-v1:5-5", context="Murcia plant")], with_original=False)
    assert rows["s1"]["state"] == "uncheckable" and "original not available" in rows["s1"]["reason"]


def test_citation_by_lines_without_representation_still_resolves_against_the_original(tmp_path):
    citation = {"id": "s1", "resource": "SRC-12", "anchor": "lines-v1:5-5", "context": "Murcia plant"}
    assert _document_without_pages(tmp_path, [citation])["s1"]["state"] == "resolved"
