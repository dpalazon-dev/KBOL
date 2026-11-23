"""Segmentation of a DoclingDocument into norm units (`structure-v1`), the representation that KBOL cites.

Walks the body in reading order and opens units on the drafting patterns of EU and BOE regulations: recitals
`(n)`, `Artículo n`, paragraphs `n.`, points `n)` or annex `n.`, letters `a)`, `ANEXO X`, `Parte X` and `Clase X`
(key `sec`). Each element is added to every open unit, so a unit contains its children. The region of a unit on
each page is the bounding box of its elements, normalized and with the origin at the top left. A heading that
Docling left as a page header or footer only enters if it matches a structural pattern, at the start of its page,
and is recorded in `warnings`: it is a correction of the segmentation, not of the original.

The patterns match the Spanish text of the documents (EUR-Lex in Spanish and the BOE); the unit keys are the
`norm-v1` keys of the locator.
"""

import hashlib
import json
import re
from pathlib import Path

from .store import read, save

# Input patterns: headings as written in Spanish EU and BOE texts.
_ARTICLE = re.compile(r"^Art[íi]culo\s+(\d+)\b")
_ANNEX = re.compile(r"^ANEXO\s+([IVXLC]+)\b")
_PART = re.compile(r"^PARTE\s+([IVXLC]+)\b", re.IGNORECASE)
_CLASS = re.compile(r"^Clase\s+([IVXLC]+)\b")
_CHAPTER = re.compile(r"^CAP[ÍI]TULO\s+([IVXLC]+)\b", re.IGNORECASE)
_RECITAL = re.compile(r"^\((\d+)\)\s*")
_PARAGRAPH = re.compile(r"^(\d+)\.(?!\d)\s*")
_POINT = re.compile(r"^(\d+)\)\s*")
_LETTER = re.compile(r"^([a-zñ])\)\s*")
_ROMAN = re.compile(r"^(i{1,3}|iv|vi{0,3}|ix|x)\)\s*")
_STRUCTURAL = (_ARTICLE, _ANNEX, _PART, _CLASS, _CHAPTER)
# Docling 2.142.1 reads the em space U+2003 of BOE PDFs as U+0840 (Mandaic letter).
_GLYPH = "ࡀ"
_IGNORE = {"page_header", "page_footer", "footnote"}
# Date of the Official Journal header that Docling sometimes leaves in the body: it is a page header.
_HEADER_DATE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")
# Closing formulas of a regulation ("Done at", "HAS ADOPTED"), as written in Spanish.
_CLOSING = ("Hecho en ", "HA ADOPTADO", "HAN ADOPTADO")


def _resolve(doc: dict, ref: str) -> dict:
    _, kind, index = ref.split("/")
    return doc[kind][int(index)]


def _table_text(table: dict) -> list[tuple[str, list]]:
    """Rows of a table without the header: (text of the row, cells with a box).

    A merged cell appears in every row it spans: it is skipped when it repeats the one in the previous row in the
    same column, so its text is not counted twice. Without its number, the next row continues the open unit.
    """
    rows, previous = [], {}
    for row in table["data"]["grid"]:
        if any(c.get("column_header") for c in row):
            continue
        seen, texts, current = set(), [], {}
        for c in row:
            t = c["text"].strip()
            col = c.get("start_col_offset_idx")
            current[col] = t
            if t and t not in seen and previous.get(col) != t:
                seen.add(t)
                texts.append(t)
        previous = current
        if texts:
            rows.append((" | ".join(texts), row))
    return rows


def _elements(doc: dict, reorder: bool = False):
    """(text, [(page, box, origin)]) in reading order, with the structural headings recovered.

    With `reorder`, the order of the top-level elements is that of `di.order` and not Docling's.
    """
    sequence = []
    replacements = [0]
    root, order_warnings = doc["body"], []
    if reorder:
        from .order import ordered_refs

        refs, order_warnings = ordered_refs(doc)
        root = {"children": [{"$ref": r} for r in refs]}

    def visit(node):
        for child in node.get("children", []):
            item = _resolve(doc, child["$ref"])
            label = item.get("label")
            if label == "table":
                page = item["prov"][0]["page_no"] if item.get("prov") else None
                for text, cells in _table_text(item):
                    boxes = [(page, c["bbox"]) for c in cells if c.get("bbox")]
                    sequence.append({"text": text, "boxes": boxes, "table": True})
                continue
            if label not in _IGNORE and item.get("text") and not _HEADER_DATE.match(item["text"].strip()):
                marker = (item.get("marker") or "").strip()
                raw = item["text"]
                if _GLYPH in raw:
                    replacements[0] += raw.count(_GLYPH)
                    raw = raw.replace(_GLYPH, " ")
                text = f"{marker} {raw}".strip() if marker else raw
                boxes = [(p["page_no"], p["bbox"]) for p in item.get("prov", [])]
                sequence.append({"text": text, "boxes": boxes, "table": False, "list": label == "list_item"})
            visit(item)

    visit(root)
    warnings = list(order_warnings)
    if replacements[0]:
        warnings.append(
            f"glyph U+0840 replaced by a space in {replacements[0]} places (Docling reads the em space U+2003 that way)"
        )
    for item in doc["texts"]:
        if item.get("label") in ("page_header", "page_footer") and any(p.match(item["text"]) for p in _STRUCTURAL):
            page = item["prov"][0]["page_no"]
            pos = next((i for i, e in enumerate(sequence) if e["boxes"] and e["boxes"][0][0] >= page), len(sequence))
            sequence.insert(pos, {"text": item["text"], "boxes": [(page, item["prov"][0]["bbox"])], "table": False})
            warnings.append(f"heading «{item['text']}» recovered from {item['label']} ({item['self_ref']}, page {page})")
    return sequence, warnings


def _region(box: dict, width: float, height: float) -> list[float]:
    left, right = box["l"], box["r"]
    if box.get("coord_origin", "BOTTOMLEFT") == "BOTTOMLEFT":
        y0, y1 = height - box["t"], height - box["b"]
    else:
        y0, y1 = box["t"], box["b"]
    x0, x1 = sorted((left / width, right / width))
    y0, y1 = sorted((y0 / height, y1 / height))
    return [max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)]


def _fmt(value: float) -> str:
    return f"{value:.4f}"


class _Builder:
    def __init__(self, pages: dict):
        self.pages = pages
        self.units: list[dict] = []
        self.open_units: dict[str, dict] = {}

    def open(self, level_keys: list[tuple[str, str]], keep: int):
        """Closes the open units below `keep` parts and opens the new key."""
        current = sorted(self.open_units.values(), key=lambda u: u["level"])
        self.open_units = {u["key"]: u for u in current if u["level"] < keep}
        key = ";".join(f"{k}={v}" for k, v in level_keys)
        unit = {"key": key, "level": len(level_keys) - 1, "parts": level_keys, "boxes": [], "text": []}
        self.units.append(unit)
        self.open_units[key] = unit
        return unit

    def close_markers(self):
        self.open_units = {k: u for k, u in self.open_units.items() if not {"let", "num"} & set(dict(u["parts"]))}

    def close_all(self):
        self.open_units = {}

    def root(self):
        return min(self.open_units.values(), key=lambda u: u["level"]) if self.open_units else None

    def leaf(self):
        return max(self.open_units.values(), key=lambda u: u["level"]) if self.open_units else None

    def add(self, element: dict):
        for u in self.open_units.values():
            u["text"].append(element["text"])
            u["boxes"].extend(element["boxes"])

    def drop_index(self) -> list[str]:
        """Removes the single-element units (the heading) whose key repeats: they are table-of-contents entries."""
        count: dict[str, int] = {}
        for u in self.units:
            count[u["key"]] = count.get(u["key"], 0) + 1
        drop = [u for u in self.units if count[u["key"]] > 1 and len(u["text"]) == 1]
        self.units = [u for u in self.units if u not in drop]
        return [u["key"] for u in drop]

    def output(self) -> list[dict]:
        res = []
        for u in self.units:
            by_page: dict[int, list[list[float]]] = {}
            for page, box in u["boxes"]:
                size = self.pages[str(page)]["size"]
                by_page.setdefault(page, []).append(_region(box, size["width"], size["height"]))
            regions = []
            for page, rs in sorted(by_page.items()):
                x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
                x1, y1 = max(r[2] for r in rs), max(r[3] for r in rs)
                regions.append(
                    {"p": page, "r": [_fmt(x0), _fmt(y0), _fmt(max(x1, x0 + 0.0001)), _fmt(max(y1, y0 + 0.0001))]}
                )
            res.append(
                {
                    "key": u["key"],
                    "level": u["level"],
                    "pages": sorted(by_page),
                    "regions": regions,
                    "text": "\n".join(u["text"]),
                }
            )
        return res


def _is_roman(leaf: dict | None, marker: str) -> bool:
    """`i)` is a letter if it follows `h)`; `v)` and `x)`, if they follow `u)` and `w)`. Otherwise, with a letter open, it is a numeral."""
    if leaf is None:
        return False
    parts = dict(leaf["parts"])
    letter = parts.get("let")
    if letter is None:
        return False
    return not (len(marker) == 1 and "num" not in parts and ord(marker) == ord(letter) + 1)


def structure_from_docling(
    doc: dict, original_sha256: str, docling_sha256: str | None = None, reorder: bool = False
) -> dict:
    sequence, warnings = _elements(doc, reorder)
    c = _Builder(doc["pages"])
    for e in sequence:
        t = e["text"].strip()
        root = c.root()
        if not e["table"] and (m := _ARTICLE.match(t)):
            c.open([("art", m.group(1))], 0)
        elif not e["table"] and (m := _ANNEX.match(t)):
            c.open([("anx", m.group(1))], 0)
        elif _CHAPTER.match(t) or t.startswith(_CLOSING):
            c.close_all()
            continue
        elif root and root["parts"][0][0] == "anx" and (m := _PART.match(t) or _CLASS.match(t)):
            key = "parte" if _PART.match(t) else "sec"
            c.open([root["parts"][0], (key, m.group(1))], 1)
        elif (root is None or root["parts"][0][0] == "cons") and (m := _RECITAL.match(t)):
            c.open([("cons", m.group(1))], 0)
        elif root and root["parts"][0][0] == "art" and (m := _PARAGRAPH.match(t)) and not e["table"]:
            c.open([root["parts"][0], ("ap", m.group(1))], 1)
        elif (
            root
            and root["parts"][0][0] in ("art", "anx")
            and (m := _POINT.match(t) or (_PARAGRAPH.match(t) if root["parts"][0][0] == "anx" else None))
        ):
            base = [p for p in c.leaf()["parts"] if p[0] in ("anx", "parte", "sec", "art", "ap")]
            existing = ";".join(f"{k}={v}" for k, v in [*base, ("pto", m.group(1))])
            if existing in c.open_units:
                pass  # merged cell repeated in the next row: same unit
            else:
                c.open([*base, ("pto", m.group(1))], len(base))
        elif root and (m := _ROMAN.match(t)) and _is_roman(c.leaf(), m.group(1)):
            base = [p for p in c.leaf()["parts"] if p[0] != "num"]
            c.open([*base, ("num", m.group(1))], len(base))
        elif root and (m := _LETTER.match(t)):
            base = [p for p in c.leaf()["parts"] if p[0] not in ("let", "num")]
            c.open([*base, ("let", m.group(1))], len(base))
        elif (
            root
            and not e["table"]
            and not e.get("list")
            and c.leaf()
            and {"let", "num"} & set(dict(c.leaf()["parts"]))
        ):
            c.close_markers()  # paragraph without a marker after a list: back to the paragraph
        c.add(e)
    index = c.drop_index()
    if index:
        warnings.append(f"{len(index)} table-of-contents entries dropped (heading-only unit with a repeated key)")
    pages = [
        {"p": int(k), "width": v["size"]["width"], "height": v["size"]["height"]}
        for k, v in sorted(doc["pages"].items(), key=lambda kv: int(kv[0]))
    ]
    st = {
        "profile": "structure-v1",
        "original_sha256": original_sha256,
        "docling_sha256": docling_sha256,
        "segmenter": "kbol-di/structure 0.1",
        "pages": pages,
        "units": c.output(),
        "warnings": warnings,
    }
    if reorder:  # without the option, the output keeps the keys it always had
        st["order_corrected"] = True
    return st


def structure_in_store(docling_sha256: str, original_sha256: str, store: Path, reorder: bool = False) -> dict:
    doc = json.loads(read(docling_sha256, store))
    st = structure_from_docling(doc, original_sha256, docling_sha256, reorder=reorder)
    data = json.dumps(st, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint, _ = save(data, store)
    keys = [u["key"] for u in st["units"]]
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    code = Path(__file__).read_bytes()
    if reorder:
        code += (Path(__file__).parent / "order.py").read_bytes()
    return {
        "sha256": fingerprint,
        "derived_from": docling_sha256,
        "original": original_sha256,
        "processor": "kbol-di/structure",
        "version": "0.1",
        "code_sha256": hashlib.sha256(code).hexdigest(),
        "configuration": {"reorder": reorder},
        "units": len(keys),
        "repeated": repeated,
        "warnings": st["warnings"],
    }
