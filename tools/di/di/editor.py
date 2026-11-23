"""Norm units according to the publisher's structured version: EUR-Lex HTML and BOE XML.

It is the reference against which the PDF extraction is measured, not citable evidence. The keys are those of
`norm-v1` (`cons`, `anx`, `art`, `ap`, `let`) and each unit carries its full text, including its children's. What
the publisher does not structure (the inner points of a EUR-Lex annex) is measured at the level of the whole annex.

The BOE patterns and element classes (`articulo`, `anexo_num`, `Artículo n.`, `ANEXO X`) are the publisher's own
markup and Spanish wording, read as input.
"""

import html
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

_VOID = {"area", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
_EURLEX_ID = re.compile(r"rct_(\d+)|art_(\d+)|(\d{3})\.(\d{3})|anx_([IVXLC]+)")
_LETTER = re.compile(r"^([a-zñ])\)$")
_ROMAN = re.compile(r"^(i{1,3}|iv|vi{0,3}|ix|x)\)$")
# Footnotes, their calls and table headers: the extracted structure does not count them either.
_SKIP = {"oj-note", "oj-super", "oj-tbl-hdr"}


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "root", "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1]["children"].append(data)


def _text(node) -> str:
    parts = []

    def visit(n):
        if isinstance(n, str):
            parts.append(n)
            return
        if _SKIP & set(n["attrs"].get("class", "").split()):
            return
        for h in n["children"]:
            visit(h)
        if n["tag"] in ("p", "div", "tr", "li"):
            parts.append("\n")

    visit(node)
    return re.sub(r"[ \t  ]+", " ", "".join(parts)).strip()


def _walk(node):
    yield node
    for h in node["children"]:
        if not isinstance(h, str):
            yield from _walk(h)


def editor_units_eurlex(document: str) -> dict[str, str]:
    tree = _Tree()
    tree.feed(document)
    units: dict[str, str] = {}
    for node in _walk(tree.root):
        m = _EURLEX_ID.fullmatch(node["attrs"].get("id", ""))
        if not m:
            continue
        cons, art, art_ap, ap, anx = m.groups()
        if cons:
            key = f"cons={cons}"
        elif art:
            key = f"art={art}"
        elif anx:
            key = f"anx={anx}"
        else:
            key = f"art={int(art_ap)};ap={int(ap)}"
        if art or art_ap:
            _markers(node, key, units)
        units[key] = _text(node)
    return units


def _rows(node):
    """Table rows under `node` without entering cells (nested tables) or other subdivisions with an id."""
    for h in node["children"]:
        if isinstance(h, str):
            continue
        if h["tag"] == "tr":
            yield h
        elif h["tag"] != "td" and not _EURLEX_ID.fullmatch(h["attrs"].get("id", "")):
            yield from _rows(h)


def _markers(node, key: str, units: dict[str, str]):
    """Letters `a)` of the direct rows and, inside each letter, nested Roman numerals `i)` (`num`)."""
    for row in _rows(node):
        cells = [n for n in row["children"] if not isinstance(n, str) and n["tag"] == "td"]
        if len(cells) < 2:
            continue
        marker = _text(cells[0])
        if letter := _LETTER.match(marker):
            sub = f"{key};let={letter.group(1)}"
            units[sub] = _text(cells[1])
            for row2 in _rows(cells[1]):
                cells2 = [n for n in row2["children"] if not isinstance(n, str) and n["tag"] == "td"]
                if len(cells2) >= 2 and (roman := _ROMAN.match(_text(cells2[0]))):
                    units[f"{sub};num={roman.group(1)}"] = _text(cells2[1])
        elif roman := _ROMAN.match(marker):
            units[f"{key};num={roman.group(1)}"] = _text(cells[1])


_ARTICLE = re.compile(r"Artículo\s+(\d+)\.")
_PARAGRAPH = re.compile(r"^(\d+)\.\s")
_LETTER_BOE = re.compile(r"^([a-zñ])\)\s")
_ANNEX = re.compile(r"ANEXO\s+([IVXLC]+)$")


def editor_units_boe(document: str) -> dict[str, str]:
    body = ET.fromstring(document).find("texto")
    units: dict[str, list[str]] = {}
    open_keys: list[str] = []
    for p in body.iter("p"):
        css_class = p.get("class", "")
        content = html.unescape("".join(p.itertext())).replace(" ", " ").replace(" ", " ").strip()
        if not content:
            continue
        if css_class == "articulo":
            m = _ARTICLE.match(content)
            open_keys = [f"art={m.group(1)}"] if m else []
        elif css_class == "anexo_num":
            m = _ANNEX.match(content)
            open_keys = [f"anx={m.group(1)}"] if m else []
        elif css_class in ("capitulo_num", "firma_rey", "firma_ministro") or content.startswith("Disposición "):
            open_keys = []
        elif open_keys and open_keys[0].startswith("art="):
            ap, letter = _PARAGRAPH.match(content), _LETTER_BOE.match(content)
            if ap:
                open_keys = [open_keys[0], f"{open_keys[0]};ap={ap.group(1)}"]
            elif letter:
                base = next((k for k in open_keys if ";ap=" in k and ";let=" not in k), open_keys[0])
                open_keys = [k for k in open_keys if ";let=" not in k] + [f"{base};let={letter.group(1)}"]
        for key in open_keys:
            units.setdefault(key, []).append(content)
    return {k: "\n".join(v) for k, v in units.items()}
