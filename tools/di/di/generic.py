"""Generic segmentation of a DoclingDocument (`structure-v1`) for a PDF that is not a regulation.

The units come from what Docling labels in any document. Each heading opens a section (numbered from 1 in order of
appearance; 0 is whatever precedes the first heading), and the section is split by page:
`section=<n>;page=<p>` contains only what that section has on that page, with the text of its tables and figures.
Each table and each figure with a caption is also a unit of its own (`section=<n>;table=<m>`, `;figure=<m>`),
numbered as in the DoclingDocument.

These keys are not a `norm-v1` locator: a citation of this profile is only physical (`pdf-v1`, page and region),
and the core resolver checks it against the text of the units on that page. That is why it is split by page: with
one unit per whole section, a citation with the wrong page within the same section would pass. Page headers and
footers are left out.

With `correct` (the default) three corrections are applied, each noted in `warnings`: the reading order of
`di.order`, that an algorithm, table or figure label or a repeated heading does not open a section, and that each
table or figure goes to the section that mentions it. Without `correct` none is applied: order and headings are
Docling's. A table that Docling delivers as a single element straddling two pages is attributed to the first one.
"""

import hashlib
import json
import re
from pathlib import Path

from .context import (
    cited_references,
    clean_title,
    entry_key,
    hierarchy,
    part_type,
    table_cells,
)
from .order import reorder
from .store import read, save
from .structure import _GLYPH, _fmt, _region, _resolve

_FURNITURE = {"page_header", "page_footer"}
_HEADINGS = {"section_header", "title"}
_FLOATS = {"table", "picture"}
# An algorithm, table or figure label that Docling labels as a heading does not open a section. Input word lists:
# the labels as written in English and Spanish documents.
_LABEL = re.compile(r"^\s*(algorithm|algoritmo|table|tabla|cuadro|fig(?:ure|ura)?\.?)\s*\d", re.IGNORECASE)
_MENTION = re.compile(r"\b(table|tabla|cuadro|fig(?:ure|ura)?\.?)\s*(\d+)", re.IGNORECASE)
VERSION = "0.2"


def _float_kind(word: str) -> str:
    return "figure" if word.lower().startswith("fig") else "table"


def _comparable(text: str) -> str:
    return re.sub(r"\W+", "", text).lower()


def _rows(table: dict) -> list[dict]:
    """One piece per table row, with the header. A merged cell counts once, where it starts."""
    page = table["prov"][0]["page_no"] if table.get("prov") else None
    seen, pieces = set(), []
    for row in table.get("data", {}).get("grid", []):
        texts, boxes = [], []
        for cell in row:
            origin = (cell.get("start_row_offset_idx"), cell.get("start_col_offset_idx"))
            if origin in seen:
                continue
            seen.add(origin)
            text = (cell.get("text") or "").strip()
            if text:
                texts.append(text)
                if cell.get("bbox") and page is not None:
                    boxes.append((page, cell["bbox"]))
        if texts:
            pieces.append({"text": " | ".join(texts), "boxes": boxes})
    return pieces


def _pieces(doc: dict, item: dict) -> list[dict]:
    """Text and boxes of the element and of what it contains, in Docling's order."""
    if item.get("label") in _FURNITURE or item.get("content_layer", "body") != "body":
        return []
    pieces = []
    boxes = [(p["page_no"], p["bbox"]) for p in item.get("prov", [])]
    if item.get("label") == "table":
        pieces.append({"text": "", "boxes": boxes})
        pieces.extend(_rows(item))
    elif item.get("text"):
        marker = (item.get("marker") or "").strip()
        raw = item["text"].replace(_GLYPH, " ")
        pieces.append({"text": f"{marker} {raw}".strip() if marker else raw, "boxes": boxes})
    elif boxes:
        pieces.append({"text": "", "boxes": boxes})
    for child in item.get("children", []):
        pieces.extend(_pieces(doc, _resolve(doc, child["$ref"])))
    return pieces


def blocks(doc: dict) -> list[dict]:
    """Body elements, with groups and headings with content unpacked: the unit that is ordered and assigned."""
    output = []

    def visit(node):
        for child in node.get("children", []):
            item = _resolve(doc, child["$ref"])
            if item["self_ref"].startswith("#/groups/"):
                visit(item)
                continue
            if item.get("label") in _HEADINGS and item.get("children"):
                # In a Word file, Docling hangs what goes below each heading from it: the heading is one block and
                # its content the following ones; otherwise the whole document would be the block of its first heading.
                own = _pieces(doc, {**item, "children": []})
                if own:
                    output.append({"ref": item["self_ref"], "label": item.get("label"), "item": item, "pieces": own})
                visit(item)
                continue
            pieces = _pieces(doc, item)
            if pieces:
                output.append({"ref": item["self_ref"], "label": item.get("label"), "item": item, "pieces": pieces})

    visit(doc["body"])
    return output


def _caption(doc: dict, item: dict) -> str | None:
    for child in item.get("children", []):
        candidate = _resolve(doc, child["$ref"])
        if candidate.get("label") == "caption" and candidate.get("text"):
            return candidate["text"]
    return None


def _by_page(pieces: list[dict]) -> list[tuple[int, list[dict]]]:
    """The pieces of a section spread over pages, each one only with its boxes on that page.

    A paragraph split across two pages goes whole to both: a quote from any of its sentences resolves on either.
    A piece without a box goes with the previous one or, if it opens the section, with the first one that has a
    page; in a section without any box there is no page to take it to and its text enters no unit.
    """
    spread: dict[int, list[dict]] = {}
    last: list[int] = []
    without_page: list[dict] = []
    for piece in pieces:
        own = sorted({page for page, _ in piece["boxes"]}) or last
        if not own:
            without_page.append(piece)
            continue
        for page in own:
            target = spread.setdefault(page, [])
            if without_page:
                target.extend({"text": p["text"], "boxes": []} for p in without_page)
                without_page = []
            boxes = [(pg, box) for pg, box in piece["boxes"] if pg == page]
            target.append({"text": piece["text"], "boxes": boxes})
        last = own
    return sorted(spread.items())


def _unit(key: str, level: int, pieces: list[dict], pages: dict, **extra) -> dict:
    by_page: dict[int, list[list[float]]] = {}
    for piece in pieces:
        for page, box in piece["boxes"]:
            size = pages[str(page)]["size"]
            by_page.setdefault(page, []).append(_region(box, size["width"], size["height"]))
    regions = []
    for page, rs in sorted(by_page.items()):
        x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
        x1, y1 = max(r[2] for r in rs), max(r[3] for r in rs)
        regions.append({"p": page, "r": [_fmt(x0), _fmt(y0), _fmt(max(x1, x0 + 0.0001)), _fmt(max(y1, y0 + 0.0001))]})
    return {
        "key": key,
        "level": level,
        "pages": sorted(by_page),
        "regions": regions,
        "text": "\n".join(p["text"] for p in pieces if p["text"]),
        **extra,
    }


def _reassign_floats(doc: dict, sections: list[dict]) -> list[str]:
    """Moves each table or figure with a numbered caption to the first section whose text mentions it.

    On the page, a float lands next to whatever is beside it, which is not always the section that discusses it.
    Without a numbered caption or a mention in the text, it stays where the reading order left it.
    """
    mentions: dict[tuple[str, str], int] = {}
    for i, section in enumerate(sections):
        for block in section["blocks"]:
            if block["label"] in _FLOATS or block["label"] in _HEADINGS:
                continue
            for word, number in _MENTION.findall(block["item"].get("text") or ""):
                mentions.setdefault((_float_kind(word), number), i)
    moved = 0
    for i, section in enumerate(sections):
        for block in list(section["blocks"]):
            if block["label"] not in _FLOATS:
                continue
            m = _MENTION.match((_caption(doc, block["item"]) or "").strip())
            target = mentions.get((_float_kind(m.group(1)), m.group(2))) if m else None
            if target is not None and target != i:
                section["blocks"].remove(block)
                sections[target]["blocks"].append(block)
                moved += 1
    return [f"{moved} tables or figures moved to the section that mentions them"] if moved else []


def generic_structure(
    doc: dict, original_sha256: str, docling_sha256: str | None = None, correct: bool = True
) -> dict:
    a = analyze(doc, correct)
    sections, keys, context, warnings = a["sections"], a["keys"], a["context"], a["warnings"]
    bibliography, author_year, maximum = a["bibliography"], a["author_year"], a["maximum"]
    cited: list[str] = []
    units = []
    for key, section, ctx in zip(keys, sections, context, strict=True):
        pieces = [p for b in section["blocks"] for p in b["pieces"]]
        parts = _by_page(pieces)
        if not parts and any(p["text"] for p in pieces):
            parts = [(None, pieces)]  # document without pages (Word, HTML): one unit per section
        for page, part in parts:
            suffix = f";page={page}" if page is not None else ""
            unit = _unit(f"{key}{suffix}", 0, part, doc.get("pages", {}), title=section["title"], **ctx)
            refs = [] if ctx["part_type"] == "references" else cited_references(unit["text"], author_year, maximum)
            unit["references"] = refs
            cited.extend(refs)
            units.append(unit)
        for block in section["blocks"]:
            index = int(block["ref"].rsplit("/", 1)[1]) + 1
            caption = _caption(doc, block["item"])
            if block["label"] == "table":
                unit = _unit(f"{key};table={index}", 1, block["pieces"], doc.get("pages", {}), caption=caption)
                unit.update(path=ctx["path"], part_type=ctx["part_type"], cells=table_cells(block["item"]))
                units.append(unit)
            elif block["label"] == "picture" and caption:
                unit = _unit(f"{key};figure={index}", 1, block["pieces"], doc.get("pages", {}), caption=caption)
                unit.update(path=ctx["path"], part_type=ctx["part_type"])
                units.append(unit)
    if bibliography:
        known = {r["key"] for r in bibliography}
        loose = [c for c in dict.fromkeys(cited) if c not in known]
        if loose:
            fmt = "({})" if author_year else "[{}]"
            warnings.append("citations without an entry in the bibliography: " + ", ".join(fmt.format(c) for c in loose[:20]))
    elif cited:
        warnings.append(f"{len(set(cited))} citations to the bibliography, but no references section is recognized")
    pages = [
        {"p": int(k), "width": v["size"]["width"], "height": v["size"]["height"]}
        for k, v in sorted(doc.get("pages", {}).items(), key=lambda kv: int(kv[0]))
    ]
    return {
        "profile": "structure-v1",
        "keys": "generic-v1",
        "original_sha256": original_sha256,
        "docling_sha256": docling_sha256,
        "segmenter": f"kbol-di/generic {VERSION}",
        "order_corrected": correct,
        "pages": pages,
        "units": units,
        "references": bibliography,
        "warnings": warnings,
    }


def analyze(doc: dict, correct: bool = True) -> dict:
    """Sections of the document with their blocks in reading order, their context and the bibliography.

    It is the computation shared by the structure and the document folder (`di.project`): both come from here and
    cannot tell different things about the same DoclingDocument.
    """
    warnings: list[str] = []
    items = blocks(doc)
    if correct:
        items, warnings = reorder(doc, items)
    sections: list[dict] = []
    previous = None
    for block in items:
        is_heading = block["label"] in _HEADINGS
        if is_heading and correct:
            title = block["item"]["text"]
            if _LABEL.match(title):
                is_heading = False
                warnings.append(f"«{title.strip()[:60]}» is a label, it does not open a section ({block['ref']})")
            elif previous is not None and _comparable(title) == previous:
                is_heading = False
                warnings.append(f"repeated heading «{title.strip()[:60]}», it does not open another section ({block['ref']})")
        if is_heading:
            previous = _comparable(block["item"]["text"])
            sections.append({"title": clean_title(block["item"]["text"]), "blocks": []})
        elif not sections:
            sections.append({"title": None, "blocks": []})
        sections[-1]["blocks"].append(block)
    if correct:
        warnings.extend(_reassign_floats(doc, sections))

    first = 0 if sections and sections[0]["title"] is None else 1
    keys = [f"section={n}" for n in range(first, first + len(sections))]
    context = _section_context(sections, keys)
    bibliography, author_year = _bibliography(sections, keys)
    maximum = max((int(r["key"]) for r in bibliography if r["key"].isdigit()), default=None)
    stepping_back = [s["title"] for s, c in zip(sections, context, strict=True) if c.pop("steps_back", False)]
    if stepping_back:
        warnings.append(
            f"{len(stepping_back)} numbered headings that do not advance, treated as items of the previous section: "
            + "; ".join(f"«{t[:40]}»" for t in stepping_back[:5])
        )
    return {
        "sections": sections,
        "keys": keys,
        "context": context,
        "bibliography": bibliography,
        "author_year": author_year,
        "maximum": maximum,
        "warnings": warnings,
    }


def _section_context(sections: list[dict], keys: list[str]) -> list[dict]:
    """Number, depth, parent, heading path and part type of each section.

    A section without a type of its own inherits its parent's ("5.3 Training time" within "5 Experiments" is
    experiments); a section numbered with a letter after the bibliography is an appendix.
    """
    titles = [s["title"] for s in sections]
    levels = hierarchy(titles)
    output: list[dict] = []
    for title, level in zip(titles, levels, strict=True):
        parent = level["parent"]
        kind = part_type(title)
        if kind is None and level["number"] and level["number"][0].isalpha():
            kind = "appendix"
        if parent is not None and (kind is None or output[parent]["part_type"] in ("appendix", "references")):
            kind = output[parent]["part_type"]
        path = ([*output[parent]["path"]] if parent is not None else []) + ([title] if title else [])
        output.append(
            {
                "number": level["number"],
                "depth": level["depth"],
                "parent": keys[parent] if parent is not None else None,
                "path": path,
                "part_type": kind,
                "steps_back": level.get("steps_back", False),
            }
        )
    return output


def _bibliography(sections: list[dict], keys: list[str]) -> tuple[list[dict], bool]:
    """Entries of the references sections, with their key, text, pages and section; and whether they are author-year.

    An entry is numeric if it has a "[n]" marker; if none has it, the key is "first surname year" and the text's
    citations are looked for in that style. An entry without a recognizable key is left out.
    """
    entries, numeric = [], 0
    for key, section in zip(keys, sections, strict=True):
        if part_type(section["title"]) != "references":
            continue
        for block in section["blocks"]:
            item = block["item"]
            if block["label"] not in ("list_item", "text") or not item.get("text"):
                continue
            ref, is_numeric = entry_key(item["text"], item.get("marker"))
            if ref is None:
                continue
            numeric += is_numeric
            pages = sorted({p["page_no"] for p in item.get("prov", [])})
            entries.append({"key": ref, "text": item["text"].strip(), "pages": pages, "section": key})
    return entries, bool(entries) and numeric == 0


def _code_fingerprint() -> str:
    """Joint fingerprint of the modules that decide the output, in this order."""
    folder = Path(__file__).parent
    return hashlib.sha256(b"".join((folder / n).read_bytes() for n in ("generic.py", "context.py", "order.py", "structure.py"))).hexdigest()


def generic_in_store(docling_sha256: str, original_sha256: str, store: Path, correct: bool = True) -> dict:
    doc = json.loads(read(docling_sha256, store))
    st = generic_structure(doc, original_sha256, docling_sha256, correct=correct)
    data = json.dumps(st, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint, _ = save(data, store)
    return {
        "sha256": fingerprint,
        "derived_from": docling_sha256,
        "original": original_sha256,
        "processor": "kbol-di/generic",
        "version": VERSION,
        "code_sha256": _code_fingerprint(),
        "configuration": {"correct": correct},
        "units": len(st["units"]),
        "sections": len({u["key"].split(";")[0] for u in st["units"]}),
        "pages_without_unit": sorted(
            {p["p"] for p in st["pages"]} - {p for u in st["units"] for p in u["pages"]}
        ),
        "warnings": st["warnings"],
    }
