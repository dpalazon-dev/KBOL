"""Reading order of the blocks of a DoclingDocument when Docling gets it wrong.

Works page by page with the position of each top-level block, ignoring headers and footers. A block that crosses
the centre of the page separates bands, except a centred line that shares its height with other blocks, which is
read as one more of its line; within a band, if there are blocks left and right that overlap in height and some
spans more than a couple of lines (two columns), the left column is read and then the right one; otherwise, top to
bottom, and left to right within the same line. A page whose layout does not fit (a tall, narrow block crossing
the centre next to others, like a third column) is left as Docling gave it.

It does not read the content or decide which section anything belongs to: it only reorders, and every reordered
page is recorded in the warnings. That the result is better than Docling's is measured, not assumed.
"""

from .structure import _region

_MARGIN = 0.02
_SEPARATOR_WIDTH = 0.45
# Height, as a fraction of the page, below which a block is one or two lines and not a column.
_LINE_HEIGHT = 0.04
_FURNITURE = {"page_header", "page_footer"}


def _position(doc: dict, item: dict) -> tuple[int, list[float]] | None:
    """Page and region of the block; None if it has none or if it is a header or footer, which do not count for layout."""
    if not item.get("prov") or item.get("label") in _FURNITURE:
        return None
    prov = item["prov"][0]
    size = doc["pages"][str(prov["page_no"])]["size"]
    return prov["page_no"], _region(prov["bbox"], size["width"], size["height"])


def _overlap_in_height(a: list[float], b: list[float]) -> bool:
    return a[1] < b[3] and b[1] < a[3]


def _top_to_bottom(band: list[tuple[dict, list[float]]]) -> list[tuple[dict, list[float]]]:
    """By height; the blocks of the same line (the centre of one falls within the height of the first), left to right."""
    lines: list[list[tuple[dict, list[float]]]] = []
    for pair in sorted(band, key=lambda p: p[1][1]):
        centre = (pair[1][1] + pair[1][3]) / 2
        if lines and lines[-1][0][1][1] <= centre <= lines[-1][0][1][3]:
            lines[-1].append(pair)
        else:
            lines.append([pair])
    return [pair for line in lines for pair in sorted(line, key=lambda p: p[1][0])]


def _order_page(blocks: list[tuple[dict, list[float]]]) -> list[dict] | None:
    """The blocks of a page in reading order, or None if the layout does not fit."""
    crossing, columns = [], []
    for block, r in blocks:
        crosses = r[0] < 0.5 - _MARGIN and r[2] > 0.5 + _MARGIN
        (crossing if crosses else columns).append((block, r))
    separators = []
    for pair in crossing:
        s = pair[1]
        if s[2] - s[0] >= _SEPARATOR_WIDTH or not any(_overlap_in_height(s, c) for _, c in columns):
            separators.append(pair)
        elif s[3] - s[1] < _LINE_HEIGHT:
            columns.append(pair)  # a centred line next to others, like that of a header
        else:
            return None  # a tall, narrow block in the centre: third column or another layout
    separators.sort(key=lambda pair: pair[1][1])
    bands: list[list[tuple[dict, list[float]]]] = [[] for _ in range(len(separators) + 1)]
    for block, r in columns:
        bands[sum(1 for _, s in separators if s[1] <= r[1])].append((block, r))
    output: list[dict] = []
    for i, band in enumerate(bands):
        left = [pair for pair in band if pair[1][2] <= 0.5 + _MARGIN]
        right = [pair for pair in band if pair[1][2] > 0.5 + _MARGIN]
        two_columns = any(
            _overlap_in_height(a, b) and max(a[3] - a[1], b[3] - b[1]) >= _LINE_HEIGHT
            for _, a in left
            for _, b in right
        )
        order = _top_to_bottom(left) + _top_to_bottom(right) if two_columns else _top_to_bottom(band)
        output.extend(block for block, _ in order)
        if i < len(separators):
            output.append(separators[i][0])
    return output


def ordered_refs(doc: dict) -> tuple[list[str], list[str]]:
    """References of the top-level elements of the body, with groups unpacked, in reading order."""
    blocks = []

    def visit(node):
        for child in node.get("children", []):
            _, kind, index = child["$ref"].split("/")
            item = doc[kind][int(index)]
            if kind == "groups":
                visit(item)
            else:
                blocks.append({"ref": child["$ref"], "item": item})

    visit(doc["body"])
    ordered, warnings = reorder(doc, blocks)
    return [b["ref"] for b in ordered], warnings


def reorder(doc: dict, blocks: list[dict]) -> tuple[list[dict], list[str]]:
    """The reordered blocks and one warning for each page that changes or that is left untouched for not fitting.

    A block without a position travels attached to the previous one. The order between pages is the page number.
    """
    by_page: dict[int, list[tuple[dict, list[float]]]] = {}
    attached: dict[int, list[dict]] = {}
    output: list[dict] = []
    warnings: list[str] = []
    last = None
    for block in blocks:
        pos = _position(doc, block["item"])
        if pos is not None:
            by_page.setdefault(pos[0], []).append((block, pos[1]))
            last = block
        elif last is None:
            output.append(block)
        else:
            attached.setdefault(id(last), []).append(block)
    for page in sorted(by_page):
        original = [b for b, _ in by_page[page]]
        new = _order_page(by_page[page])
        if new is None:
            warnings.append(f"page {page}: layout not recognized; Docling's order is kept")
            new = original
        elif [b["ref"] for b in new] != [b["ref"] for b in original]:
            moved = sum(1 for a, b in zip(new, original, strict=True) if a["ref"] != b["ref"])
            warnings.append(f"page {page}: reading order corrected ({moved} of {len(original)} blocks)")
        for block in new:
            output.append(block)
            output.extend(attached.get(id(block), []))
    return output, warnings
