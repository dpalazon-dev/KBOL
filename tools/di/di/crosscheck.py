"""Crosscheck of a structure with a second extractor of the same PDF, for documents without a publisher's version.

Without a published reference text, what can be measured is the agreement between two independent readings of the
text layer: Docling's, already segmented into `structure-v1`, and pypdf's, page by page. Each page is measured in
both directions: how much of what pypdf reads is in the structure (`recall`: what Docling may have lost) and how
much of the structure is in what pypdf reads (`support`: text that is not in the PDF, or that is far from its
page). Numbers are checked separately and one by one, because a high percentage does not make up for a lost number.

The support of a page is looked for in it and in its two neighbours, because a paragraph split across pages is
whole in both units: that is why it does not detect a text placed on the page next to its own. The comparison is
made on runs of consecutive letters within each line, without spaces, so that it depends neither on how each
reader splits words nor on the order in which it reads the blocks. It is not a measure of truth: both extractors
read the same text layer and share its errors, it does not measure reading order or meaning, and a page without a
text layer (scanned) cannot be measured and is declared separately.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .store import read

THRESHOLD = 0.98
_RUN = 6
_WORD = re.compile(r"[^\W_]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_FURNITURE = {"page_header", "page_footer"}


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).replace("­", "").lower()
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)


def _joined(text: str) -> str:
    return "".join(_WORD.findall(_norm(text)))


def _covered(reference: str, extracted: str) -> tuple[int, int]:
    """(found, total) of the runs of `_RUN` consecutive letters or digits in each line of the reference.

    Runs are taken without spaces or punctuation, so it does not matter how each reader splits or joins words, and
    within a line, so it does not matter either in which order each one reads the blocks. It counts occurrences: a
    paragraph that the reference has twice and the extraction only once is half covered.
    """
    target = _joined(extracted)
    available = Counter(target[i : i + _RUN] for i in range(len(target) - _RUN + 1))
    found = total = 0
    for line in reference.splitlines():
        joined = _joined(line)
        if not joined:
            continue
        if len(joined) < _RUN:
            total += 1
            found += joined in target
            continue
        for i in range(len(joined) - _RUN + 1):
            run = joined[i : i + _RUN]
            total += 1
            if available[run] > 0:
                available[run] -= 1
                found += 1
    return found, total


def coverage(reference: str, extracted: str) -> float:
    """Fraction of the reference that is in the extraction; 1.0 if the reference has no text."""
    found, total = _covered(reference, extracted)
    return 1.0 if total == 0 else found / total


def numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(_norm(text)))


def missing_numbers(reference: str, extracted: str) -> list[str]:
    """Numbers in the reference that are not in the extraction; one of four or more characters also counts when glued to another."""
    present = numbers(extracted)
    glued = re.sub(r"\s+", "", _norm(extracted))
    return sorted(c for c in numbers(reference) - present if len(c) < 4 or c not in glued)


def text_by_page(data: bytes) -> dict[int, str]:
    import io

    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    return {i: (p.extract_text() or "") for i, p in enumerate(reader.pages, start=1)}


def furniture_by_page(doc: dict) -> dict[int, str]:
    """Text of the headers and footers of each page of the DoclingDocument: it is in the PDF and not in the structure."""
    output: dict[int, list[str]] = {}
    for item in doc.get("texts", []):
        if item.get("label") in _FURNITURE and item.get("prov"):
            output.setdefault(item["prov"][0]["page_no"], []).append(item.get("text") or "")
    return {p: "\n".join(t) for p, t in output.items()}


def crosscheck(structure: dict, base: dict[int, str], furniture: dict[int, str] | None = None) -> dict:
    furniture = furniture or {}
    body: dict[int, list[str]] = {}
    for u in structure["units"]:
        if u.get("level", 0) == 0:
            for p in u["pages"]:
                body.setdefault(p, []).append(u["text"])
    pages, failures = [], []
    recall_total, support_total = [0, 0], [0, 0]
    for page in sorted(p["p"] for p in structure["pages"]):
        reference = base.get(page, "")
        extracted = "\n".join(body.get(page, []))
        with_furniture = extracted + "\n" + furniture.get(page, "")
        # A paragraph split across pages is whole in both units: it is supported with the neighbouring pages.
        neighbours = "\n".join(base.get(p, "") for p in (page - 1, page, page + 1))
        recall, support = _covered(reference, with_furniture), _covered(extracted, neighbours)
        for accumulated, (found, total) in ((recall_total, recall), (support_total, support)):
            accumulated[0] += found
            accumulated[1] += total
        row = {
            "p": page,
            "base_chars": len(_joined(reference)),
            "structure_chars": len(_joined(extracted)),
            "recall": round(recall[0] / recall[1], 4) if recall[1] else 1.0,
            "support": round(support[0] / support[1], 4) if support[1] else 1.0,
            "missing_numbers": missing_numbers(reference, with_furniture),
            "unsupported_numbers": missing_numbers(extracted, neighbours),
        }
        if not row["base_chars"]:
            row["no_text_layer"] = True
        pages.append(row)
        if (
            row.get("no_text_layer")
            or row["recall"] < THRESHOLD
            or row["support"] < THRESHOLD
            or row["missing_numbers"]
            or row["unsupported_numbers"]
        ):
            failures.append(row)
    tables = []
    for u in structure["units"]:
        if ";table=" in u["key"]:
            support = "\n".join(base.get(p, "") for p in u["pages"])
            tables.append(
                {
                    "key": u["key"],
                    "pages": u["pages"],
                    "numbers": len(numbers(u["text"])),
                    "unsupported_numbers": missing_numbers(u["text"], support),
                }
            )
    summary = {
        "pages": len(pages),
        "pages_without_text_layer": [f["p"] for f in pages if f.get("no_text_layer")],
        # Sum of the pages: comparing the whole document at once would count split paragraphs twice.
        "document_recall": round(recall_total[0] / recall_total[1], 4) if recall_total[1] else 1.0,
        "document_support": round(support_total[0] / support_total[1], 4) if support_total[1] else 1.0,
        "threshold": THRESHOLD,
        "pages_with_low_recall": [f["p"] for f in pages if f["recall"] < THRESHOLD],
        "pages_with_low_support": [f["p"] for f in pages if f["support"] < THRESHOLD],
        "missing_numbers": sum(len(f["missing_numbers"]) for f in pages),
        "unsupported_numbers": sum(len(f["unsupported_numbers"]) for f in pages),
        "tables": len(tables),
        "tables_with_unsupported_numbers": sum(1 for t in tables if t["unsupported_numbers"]),
    }
    limits = [
        "pypdf and Docling read the same text layer: an error in that layer is not detected",
        "it does not measure reading order, assignment to sections or meaning",
        "support is looked for on the page and its two neighbours: it does not detect a text placed on the next page",
        "tables are measured by their numbers, not cell by cell or by the position of each value",
    ]
    return {"summary": summary, "failures": failures, "pages": pages, "tables": tables, "limits": limits}


def crosscheck_in_store(structure_sha256: str, original_sha256: str, store: Path) -> dict:
    structure = json.loads(read(structure_sha256, store))
    furniture = None
    if structure.get("docling_sha256"):
        furniture = furniture_by_page(json.loads(read(structure["docling_sha256"], store)))
    res = crosscheck(structure, text_by_page(read(original_sha256, store)), furniture)
    res["inputs"] = {"structure": structure_sha256, "original": original_sha256, "base": "pypdf"}
    return res
