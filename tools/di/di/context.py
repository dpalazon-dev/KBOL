"""Document context of a PDF: what says where each thing is within the document, without interpreting its content.

Four pieces, all taken from what Docling already provides or from the text itself:

- `hierarchy`: number, depth and parent of each heading, from its numbering ("5.3" hangs from "5"; "A.1", from
  "A"). Docling marks all headings with the same level, so the numbering is the only source.
- `part_type`: abstract, introduction, method, results, references… from the first words of the heading.
- `table_cells`: each value of a table with the headers of its column and the label of its row, resolved through
  merged cells.
- `cited_references`: the bibliography calls of a text, numeric ("[15, 21]", "[3-5]") or author-year
  ("(Feng et al. 2021)").

None of this decides what the document claims: it is the scaffolding on which facts and relations are written
later.
"""

import re
import unicodedata

_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+\S")
_LETTER = re.compile(r"^\s*([A-H](?:\.\d+)*)\.?\s+\S")
# Part types and the heading openings that reveal them. The openings are input word lists: they match headings in
# English and in Spanish documents (compared without accents).
_TYPES = (
    ("abstract", ("abstract", "resumen")),
    ("introduction", ("introduction", "introduccion")),
    ("related_work", ("related work", "background", "state of the art", "estado del arte", "antecedentes",
                      "trabajos relacionados", "literature review", "revision de la literatura")),
    ("method", ("method", "methodology", "proposed", "approach", "metodo", "metodolog", "propuesta")),
    ("experiments", ("experiment", "evaluation", "experimental", "evaluacion")),
    ("results", ("result", "discussion", "resultado", "discusion")),
    ("conclusions", ("conclu",)),
    ("references", ("references", "bibliography", "referencias", "bibliografia")),
    ("appendix", ("appendix", "appendices", "supplementary", "anexo", "apendice")),
    ("acknowledgments", ("acknowledg", "agradecimiento")),
)
_REFERENCE_OPENINGS = ("references", "referencias", "bibliograf")
_NUMERIC_CITATION = re.compile(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]")
_SURNAME = r"[A-ZÁÉÍÓÚÑ][\w'’-]+"
# "et al.", "and", "&" and the Spanish "y" join author names; "véase" is the Spanish "see".
_OTHERS = rf"(?:\s+et\s+al\.?|\s+(?:and|&|y)\s+{_SURNAME})?"
_PARENTHESIS = re.compile(r"\(([^()]*\d{4}[a-z]?[^()]*)\)")
_PARENTHESIS_PART = re.compile(rf"^\s*(?:e\.g\.,?\s*|see\s+|cf\.\s*|véase\s+)?({_SURNAME}){_OTHERS},?\s+(\d{{4}}[a-z]?)\s*$")
_NARRATIVE = re.compile(rf"({_SURNAME}){_OTHERS}\s+\((\d{{4}}[a-z]?)\)")
_ENTRY_YEAR = re.compile(r"\((\d{4}[a-z]?)\)|\b(\d{4}[a-z]?)\.")


def _without_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def clean_title(title: str | None) -> str | None:
    """The title without control characters (some publishers put a \\x07 after the number) or extra spaces."""
    if title is None:
        return None
    return re.sub(r"\s+", " ", "".join(ch for ch in title if unicodedata.category(ch) != "Cc" or ch.isspace())).strip()


def _without_number(title: str) -> str:
    return re.sub(r"^\s*(?:\d+(?:\.\d+)*|[A-H](?:\.\d+)*)\.?\s+", "", clean_title(title) or "")


def part_type(title: str | None) -> str | None:
    """Part type from the first words of the heading, without its numbering; None if it is none of the known ones.

    It is compared without spaces, because Docling sometimes glues the words of a heading ("RELATEDWORK"). A
    heading that talks about conclusions is one even if it starts with something else ("Discussion and Conclusion").
    """
    if not title:
        return None
    start = re.sub(r"\s+", "", _without_accents(_without_number(title)))
    if "conclu" in start and not start.startswith(_REFERENCE_OPENINGS):
        return "conclusions"
    for kind, openings in _TYPES:
        if any(start.startswith(c.replace(" ", "")) for c in openings):
            return kind
    return None


def hierarchy(titles: list[str | None]) -> list[dict]:
    """Number, depth and parent (index in the list) of each heading.

    A heading without numbering is at the first level. A single letter ("A", "B") only numbers an appendix: it
    counts if it has subnumbering ("A.1") or if the bibliography or an appendix has already passed; otherwise,
    "A Novel Approach" would be appendix A. A number whose parent does not appear hangs from the root with the
    depth its numbering indicates.

    A first-level number that does not advance from the previous one ("1." after "3.3") is not a section but a
    numbered item that Docling took for a heading: it loses the number, hangs from the last numbered section and is
    marked with `steps_back`.
    """
    output: list[dict] = []
    after_bibliography = False
    last_main = 0
    last_numbered = None
    for title in map(clean_title, titles):
        number = None
        if title:
            if (m := _NUMBER.match(title)) or (m := _LETTER.match(title)) and ("." in m.group(1) or after_bibliography):
                number = m.group(1)
            if part_type(title) in ("references", "appendix"):
                after_bibliography = True
        if number and number.isdigit():
            if int(number) <= last_main and last_numbered is not None:
                parent = last_numbered
                output.append({"number": None, "depth": output[parent]["depth"] + 1, "parent": parent,
                               "steps_back": True})
                continue
            last_main = int(number)
        parent = None
        if number and "." in number:
            prefix = number.rsplit(".", 1)[0]
            parent = next((i for i in range(len(output) - 1, -1, -1) if output[i]["number"] == prefix), None)
        depth = (number.count(".") + 1) if number else (1 if title else 0)
        if number:
            last_numbered = len(output)
        output.append({"number": number, "depth": depth, "parent": parent})
    return output


def _is_header_row(unique: list[dict]) -> bool:
    with_text = [c for c in unique if (c.get("text") or "").strip()]
    return bool(with_text) and 2 * sum(1 for c in with_text if c.get("column_header")) >= len(with_text)


_VALUE = re.compile(r"^[\d\s.,:;±%()+\-–/x×*]+$")


def _unmarked_first_row(grid: list[list]) -> bool:
    """Docling marked no header, the first row is all text and one of the following ones has numbers."""
    if not grid or any(c and c.get("column_header") for row in grid for c in row):
        return False
    first = [(c.get("text") or "").strip() for c in grid[0] if c]
    if not any(first) or any(_VALUE.match(t) for t in first if t):
        return False
    return any(_VALUE.match((c.get("text") or "").strip()) for row in grid[1:] for c in row if c and (c.get("text") or "").strip())


def _origin(cell: dict) -> tuple:
    return (cell.get("start_row_offset_idx"), cell.get("start_col_offset_idx"))


def table_cells(table: dict) -> list[dict]:
    """Each value of the table with the page, its position, the headers of its column and the label of its row.

    A row is a header row if most of its cells are (Docling sometimes misses one); if Docling marked none, the first
    one is when it is all text and there are numbers below. The headers of a column are those of the consecutive
    header rows preceding the value: a table with two blocks, each with its header, is resolved by blocks. The row
    label is the cells marked as row header or, if there are none, the first column.
    """
    grid = table.get("data", {}).get("grid") or []
    page = table["prov"][0]["page_no"] if table.get("prov") else None
    first_is_header = _unmarked_first_row(grid)
    block: list[list[dict | None]] = []
    previous_was_data = True
    seen: set[tuple] = set()
    output = []
    for row in grid:
        unique = []
        for cell in row:
            if cell is not None and all(_origin(cell) != _origin(u) for u in unique):
                unique.append(cell)
        if _is_header_row(unique) or (first_is_header and row is grid[0]):
            if previous_was_data:
                block = []
            block.append(row)
            previous_was_data = False
            continue
        previous_was_data = True
        row_headers = [c for c in unique if c.get("row_header") and (c.get("text") or "").strip()]
        label_columns = {k for c in row_headers for k in range(c["start_col_offset_idx"], c["end_col_offset_idx"])}
        if row_headers:
            label = [c["text"].strip() for c in sorted(row_headers, key=lambda c: c["start_col_offset_idx"])]
        else:
            first = row[0] if row and row[0] is not None else None
            label = [first["text"].strip()] if first and (first.get("text") or "").strip() else []
        for k, cell in enumerate(row):
            if cell is None or not (cell.get("text") or "").strip() or _origin(cell) in seen:
                continue
            seen.add(_origin(cell))
            if k in label_columns:
                continue
            headers: list[str] = []
            previous = None
            for header in block:
                c = header[k] if k < len(header) else None
                if c is None or _origin(c) == previous or not (c.get("text") or "").strip():
                    continue
                previous = _origin(c)
                headers.append(c["text"].strip())
            output.append(
                {
                    "row": cell["start_row_offset_idx"],
                    "col": cell["start_col_offset_idx"],
                    "p": page,
                    "text": cell["text"].strip(),
                    "headers": headers,
                    "row_label": [] if (not row_headers and k == 0) else label,
                }
            )
    return output


def _author_key(surname: str, year: str) -> str:
    return f"{_without_accents(surname)} {year}"


def cited_references(text: str, author_year: bool = False, maximum: int | None = None) -> list[str]:
    """Bibliography keys cited by a text, in order of appearance and without repeats.

    Numeric: "[2]", "[15, 21]", "[3-5]"; a bracket with a 0, or with a number greater than `maximum` (the last entry
    of the bibliography), is not a citation but an interval or a list of values ("[0, 1]", "[50, 100]").
    With `author_year`, "(Feng et al. 2021; Ma and Li 2022)" and "Wang et al. (2022a)", as "first surname year".
    """
    found: list[tuple[int, str]] = []
    if author_year:
        for m in _PARENTHESIS.finditer(text):
            for part in m.group(1).split(";"):
                if p := _PARENTHESIS_PART.match(part):
                    found.append((m.start(), _author_key(p.group(1), p.group(2))))
        found.extend((m.start(), _author_key(m.group(1), m.group(2))) for m in _NARRATIVE.finditer(text))
    else:
        for m in _NUMERIC_CITATION.finditer(text):
            nums = []
            for piece in re.split(r"\s*,\s*", m.group(1)):
                if (r := re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", piece)) and 0 <= int(r.group(2)) - int(r.group(1)) <= 50:
                    nums.extend(str(n) for n in range(int(r.group(1)), int(r.group(2)) + 1))
                else:
                    nums.extend(re.findall(r"\d+", piece))
            if "0" not in nums and (maximum is None or all(int(n) <= maximum for n in nums)):
                found.extend((m.start(), n) for n in nums)
    seen, output = set(), []
    for _, key in sorted(found, key=lambda pair: pair[0]):
        if key not in seen:
            seen.add(key)
            output.append(key)
    return output


def entry_key(text: str, marker: str | None) -> tuple[str | None, bool]:
    """(key, is_numeric) of a bibliography entry: "[17]" or "17." by its marker, or "first surname year"."""
    if m := re.fullmatch(r"\s*\[?(\d+)[\].]?\s*", marker or ""):
        return m.group(1), True
    if m := re.match(r"^\s*\[(\d+)\]", text):
        return m.group(1), True
    surname = re.match(rf"^\s*({_SURNAME})", text)
    year = _ENTRY_YEAR.search(text)
    if surname and year:
        return _author_key(surname.group(1), year.group(1) or year.group(2)), False
    return None, False
