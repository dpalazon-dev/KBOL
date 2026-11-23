"""The navigable folder of a document, generated from its DoclingDocument and its structure."""

import base64

import pytest
import yaml
from di.generic import generic_structure
from di.project import ForeignFolder, project
from test_context import _paper
from test_generic import SHA, _box

# 1x1 pixel PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _with_figure(doc):
    doc["texts"].append(
        {"self_ref": "#/texts/10", "label": "caption", "text": "Figure 1: Architecture", "children": [],
         "prov": [{"page_no": 1, "bbox": _box(0.1, 0.62, 0.9, 0.64)}]}
    )
    doc["pictures"].append(
        {"self_ref": "#/pictures/0", "label": "picture", "children": [{"$ref": "#/texts/10"}],
         "prov": [{"page_no": 1, "bbox": _box(0.1, 0.65, 0.9, 0.9)}],
         "image": {"uri": "data:image/png;base64," + base64.b64encode(PNG).decode(), "mimetype": "image/png"}}
    )
    doc["body"]["children"].insert(6, {"$ref": "#/pictures/0"})
    doc["texts"][5]["text"] += " Figure 1 shows the architecture."
    return doc


def _header(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    header, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(header), body


@pytest.fixture
def folder(tmp_path):
    doc = _with_figure(_paper())
    st = generic_structure(doc, SHA)
    res = project(doc, st, b"%PDF original", "paper.pdf", "paper", tmp_path, structure_sha256="e" * 64)
    return tmp_path / "paper", res


def test_folder_with_original_index_contents_and_resources(folder):
    root, res = folder
    assert (root / "paper.pdf").read_bytes() == b"%PDF original"
    assert (root / "index.md").exists()
    names = sorted(p.name for p in (root / "contents").iterdir())
    assert names == [
        "01-anomaly-detection.md",
        "02-abstract.md",
        "03-5-experiments-and-results.md",
        "04-5-3-training-time.md",
        "05-references.md",
    ]
    assert (root / "resources" / "tables" / "table-1.md").exists()
    assert (root / "resources" / "figures" / "figure-1.png").read_bytes() == PNG
    assert (root / "resources" / "bibliography.md").exists()
    assert res["contents"] == 5 and res["tables"] == 1 and res["figures"] == 1


def test_each_content_file_carries_its_context_in_the_header(folder):
    root, _ = folder
    meta, body = _header(root / "contents" / "04-5-3-training-time.md")
    assert meta["id"] == "paper#section=4"
    assert meta["type"] == "section" and meta["document"] == "paper"
    assert meta["title"] == "5.3 Training time" and meta["number"] == "5.3"
    assert meta["path"] == ["5 EXPERIMENTS AND RESULTS", "5.3 Training time"]
    assert meta["part_type"] == "experiments" and meta["parent"] == "paper#section=3"
    assert meta["pages"] == [1]
    assert meta["references"] == ["2", "1"]
    assert meta["resources"] == ["table-1", "figure-1"]
    assert meta["origin"]["structure_sha256"] == "e" * 64
    assert meta["origin"]["units"] == ["section=4;page=1", "section=4;table=1", "section=4;figure=1"]
    assert meta["generated"]["by"].startswith("kbol-di/project")
    assert meta["description"].startswith("We follow the protocol")


def test_the_body_keeps_the_text_and_marks_pages_references_and_resources(folder):
    root, _ = folder
    _, body = _header(root / "contents" / "04-5-3-training-time.md")
    assert body.lstrip().startswith("# 5.3 Training time")
    assert '<page n="1"/>' in body
    assert 'We follow the protocol of <ref key="2">[2]</ref> and <ref key="1">[1]</ref>' in body
    assert '<resource type="table" id="table-1" ref="../resources/tables/table-1.md">Table 1: Results</resource>' in body
    assert '<resource type="figure" id="figure-1" ref="../resources/figures/figure-1.md">Figure 1: Architecture</resource>' in body


def test_the_parent_lists_its_children(folder):
    root, _ = folder
    meta, _ = _header(root / "contents" / "03-5-experiments-and-results.md")
    assert meta["children"] == ["paper#section=4"]


def test_the_table_has_its_markdown_and_each_value_with_its_context(folder):
    root, _ = folder
    meta, body = _header(root / "resources" / "tables" / "table-1.md")
    assert meta["id"] == "paper#table-1" and meta["type"] == "table"
    assert meta["section"] == "paper#section=4" and meta["unit"] == "section=4;table=1"
    assert meta["title"] == "Table 1: Results"
    assert "| USAD" in body
    assert "- USAD · SWaT › Without = 0.7917 (p. 1)" in body


def test_the_figure_has_its_image_and_its_caption(folder):
    root, _ = folder
    meta, body = _header(root / "resources" / "figures" / "figure-1.md")
    assert meta["type"] == "figure" and meta["image"] == "figure-1.png"
    assert "![Figure 1: Architecture](figure-1.png)" in body


def test_bibliography_with_its_keys(folder):
    root, _ = folder
    _, body = _header(root / "resources" / "bibliography.md")
    assert '<entry key="2">Goh et al. 2017. SWaT.</entry>' in body


def test_the_index_describes_the_document_and_links_everything(folder):
    root, _ = folder
    meta, body = _header(root / "index.md")
    assert meta["id"] == "paper" and meta["type"] == "document"
    assert meta["title"] == "Anomaly detection"
    assert meta["original"] == {"file": "paper.pdf", "sha256": SHA, "pages": 2}
    assert meta["representation"]["structure_sha256"] == "e" * 64
    assert "- [5.3 Training time](contents/04-5-3-training-time.md)" in body
    assert "[Table 1: Results](resources/tables/table-1.md)" in body
    assert "[Figure 1: Architecture](resources/figures/figure-1.md)" in body


def test_projecting_again_replaces_the_generated_folder(tmp_path):
    doc = _paper()
    st = generic_structure(doc, SHA)
    project(doc, st, b"%PDF", "paper.pdf", "paper", tmp_path)
    (tmp_path / "paper" / "contents" / "leftover.md").write_text("x", encoding="utf-8")
    project(doc, st, b"%PDF", "paper.pdf", "paper", tmp_path)
    assert not (tmp_path / "paper" / "contents" / "leftover.md").exists()


def test_it_does_not_delete_a_folder_it_did_not_generate(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "notes.md").write_text("mine", encoding="utf-8")
    doc = _paper()
    with pytest.raises(ForeignFolder):
        project(doc, generic_structure(doc, SHA), b"%PDF", "paper.pdf", "paper", tmp_path)
    assert (tmp_path / "paper" / "notes.md").read_text(encoding="utf-8") == "mine"


def test_a_document_without_pages_has_the_lines_of_each_section_in_its_markdown(tmp_path):
    """A Word file: no pages or positions; each section says which lines it spans in its Markdown, which is what is cited."""
    from test_generic import _doc

    texts = [
        {"self_ref": "#/texts/0", "label": "title", "text": "Engineering plan", "prov": [], "children": []},
        {"self_ref": "#/texts/1", "label": "section_header", "text": "1 Goal", "prov": [], "children": []},
        {"self_ref": "#/texts/2", "label": "text", "text": "Detect leaks.", "prov": [], "children": []},
        {"self_ref": "#/texts/3", "label": "section_header", "text": "2 Risks", "prov": [], "children": []},
        {"self_ref": "#/texts/4", "label": "text", "text": "The pilot does not cover Murcia.", "prov": [], "children": []},
    ]
    doc = _doc([f"#/texts/{i}" for i in range(5)], texts, pages=0)
    markdown = "\n".join(
        ["# Engineering plan", "", "## 1 Goal", "", "Detect leaks.", "", "## 2 Risks", "",
         "The pilot does not cover Murcia.", ""]
    )
    st = generic_structure(doc, SHA)
    assert [u["key"] for u in st["units"]] == ["section=1", "section=2", "section=3"]
    project(doc, st, b"PK", "plan.docx", "plan", tmp_path, markdown=markdown, markdown_sha256="m" * 64)
    meta, body = _header(tmp_path / "plan" / "contents" / "03-2-risks.md")
    assert meta["lines"] == [7, 9] and meta["pages"] == []
    assert markdown.split("\n")[8] == "The pilot does not cover Murcia."
    assert meta["origin"]["markdown_sha256"] == "m" * 64
    assert "<page" not in body
    assert (tmp_path / "plan" / "plan.docx").read_bytes() == b"PK"


def test_the_name_cannot_leave_the_destination_folder(tmp_path):
    doc = _paper()
    st = generic_structure(doc, SHA)
    for name in ("../outside", "a/b", "", ".."):
        with pytest.raises(ValueError, match="folder name"):
            project(doc, st, b"%PDF", "paper.pdf", name, tmp_path / "documents")
    assert not (tmp_path / "outside").exists()
