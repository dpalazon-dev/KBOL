"""Exact page and region of a literal quote in a DoclingDocument, to write the `pdf-v1` of a citation.

Looks for the normalized quote in every text and table cell of the body; if it is not in a single element, it
tries windows of consecutive elements (a quote that crosses two paragraphs or a page break). Returns one region
per page, the bounding box of the elements that contain it. It does not decide which match is the right one: if
there are several, it returns them all.
"""

import json
import re
import unicodedata
from pathlib import Path

from .store import read
from .structure import _GLYPH, _IGNORE, _fmt, _region, _resolve


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text.replace(_GLYPH, " ")).replace("­", "").lower()
    t = t.translate(str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"'}))
    return re.sub(r"\s+", "", t)


def _pieces(doc: dict) -> list[tuple[str, list]]:
    pieces = []

    def visit(node):
        for child in node.get("children", []):
            item = _resolve(doc, child["$ref"])
            if item.get("label") == "table":
                page = item["prov"][0]["page_no"]
                for row in item["data"]["grid"]:
                    for c in row:
                        if c.get("text") and c.get("bbox"):
                            pieces.append((c["text"], [(page, c["bbox"])]))
                continue
            if item.get("label") not in _IGNORE and item.get("text"):
                marker = (item.get("marker") or "").strip()
                pieces.append((f"{marker} {item['text']}", [(p["page_no"], p["bbox"]) for p in item.get("prov", [])]))
            visit(item)

    visit(doc["body"])
    return pieces


def locate(doc: dict, literal: str, window: int = 3) -> list[dict]:
    target = _norm(literal)
    pieces = _pieces(doc)
    for width in range(1, window + 1):
        matches = []
        for i in range(len(pieces) - width + 1):
            group = pieces[i : i + width]
            if target in _norm("".join(t for t, _ in group)):
                by_page: dict[int, list] = {}
                for _, boxes in group:
                    for page, box in boxes:
                        size = doc["pages"][str(page)]["size"]
                        by_page.setdefault(page, []).append(_region(box, size["width"], size["height"]))
                matches.append(
                    [
                        {
                            "p": p,
                            "r": [_fmt(min(r[0] for r in rs)), _fmt(min(r[1] for r in rs)), _fmt(max(r[2] for r in rs)), _fmt(max(r[3] for r in rs))],
                        }
                        for p, rs in sorted(by_page.items())
                    ]
                )
        if matches:
            return matches
    return []


def locate_in_store(docling_sha256: str, literal: str, store: Path) -> list:
    return locate(json.loads(read(docling_sha256, store)), literal)
