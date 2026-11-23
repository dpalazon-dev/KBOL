"""Fidelity of a structure extracted from the PDF against the publisher's structured version.

Measures per norm unit (`norm-v1` key): whether the unit exists and is unique, how much of its text it keeps (word
recall), whether it keeps its dates and whether it keeps its negations and exceptions. It also measures the order
of the articles and, for the whole document, word recall and split words, which compare Docling with the pypdf
baseline. A global figure does not make up for a negation lost in one unit: the report lists every failure.

The negation terms and the date pattern match the Spanish text of the regulations measured so far.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .editor import editor_units_boe, editor_units_eurlex
from .store import read

# Input word lists: negations and exceptions, and dates, as written in Spanish legal text.
TERMS = ("no", "salvo", "excepto", "sin perjuicio", "no obstante", "cuando proceda", "a menos que", "ni")
_DATE = re.compile(
    r"\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+\d{4}\b|\b\d{1,2}\.\d{1,2}\.\d{4}\b"
)
_WORD = re.compile(r"[0-9a-záéíóúüñ]+")


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).replace("­", "").lower()
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    return re.sub(r"\s+", " ", t)


def words(text: str) -> Counter:
    return Counter(_WORD.findall(_norm(text)))


def recall(reference: str, extracted: str) -> float:
    ref, ext = words(reference), words(extracted)
    total = sum(ref.values())
    return 1.0 if total == 0 else sum((ref & ext).values()) / total


def dates(text: str) -> set[str]:
    return set(_DATE.findall(_norm(text)))


def terms(text: str) -> dict[str, int]:
    t = f" {_norm(text)} "
    return {term: len(re.findall(rf"(?<![0-9a-záéíóúüñ]){re.escape(term)}(?![0-9a-záéíóúüñ])", t)) for term in TERMS}


def split_words(reference: str, extracted: str) -> int:
    """Publisher words missing from the extraction that appear when joining two consecutive pieces of it."""
    ref = set(words(reference))
    pieces = _WORD.findall(_norm(extracted))
    present = set(pieces)
    joined = {a + b for a, b in zip(pieces, pieces[1:], strict=False)}
    return sum(1 for w in ref - present if w in joined)


def _order(keys: list[str]) -> float:
    """Fraction of articles in increasing order (longest increasing subsequence over their number)."""
    nums = [int(c[4:]) for c in keys if re.fullmatch(r"art=\d+", c)]
    if not nums:
        return 1.0
    tails: list[int] = []
    for n in nums:
        i = next((j for j, v in enumerate(tails) if v >= n), len(tails))
        tails[i : i + 1] = [n]
    return len(tails) / len(nums)


def measure(structure: dict, editor: dict[str, str], base_text: str | None = None) -> dict:
    by_key: dict[str, list[dict]] = {}
    for u in structure["units"]:
        by_key.setdefault(u["key"], []).append(u)
    rows, failures = [], []
    for key, ref in editor.items():
        candidates = by_key.get(key, [])
        row = {
            "key": key,
            "status": "missing" if not candidates else ("ambiguous" if len(candidates) > 1 else "unique"),
        }
        if len(candidates) == 1:
            ext = candidates[0]["text"]
            row["recall"] = round(recall(ref, ext), 4)
            row["lost_dates"] = sorted(dates(ref) - dates(ext))
            t_ref, t_ext = terms(ref), terms(ext)
            row["differing_terms"] = {k: [t_ref[k], t_ext[k]] for k in TERMS if t_ref[k] != t_ext[k]}
            if row["lost_dates"] or row["differing_terms"] or row["recall"] < 0.98:
                failures.append(row)
        else:
            failures.append(row)
        rows.append(row)
    editor_text = "\n".join(v for k, v in editor.items() if ";" not in k)
    docling_text = "\n".join(u["text"] for u in structure["units"] if u.get("level", 0) == 0)
    unique = [f for f in rows if f["status"] == "unique"]
    summary = {
        "editor_units": len(editor),
        "unique_found": len(unique),
        "missing": sum(1 for f in rows if f["status"] == "missing"),
        "ambiguous": sum(1 for f in rows if f["status"] == "ambiguous"),
        "with_lost_dates": sum(1 for f in unique if f["lost_dates"]),
        "with_differing_terms": sum(1 for f in unique if f["differing_terms"]),
        "mean_recall": round(sum(f["recall"] for f in unique) / len(unique), 4) if unique else None,
        "article_order": round(_order([u["key"] for u in structure["units"]]), 4),
        "document": {
            "docling": {
                "recall": round(recall(editor_text, docling_text), 4),
                "split_words": split_words(editor_text, docling_text),
            },
        },
    }
    if base_text is not None:
        summary["document"]["pypdf"] = {
            "recall": round(recall(editor_text, base_text), 4),
            "split_words": split_words(editor_text, base_text),
        }
    return {"summary": summary, "failures": failures, "rows": rows}


def pypdf_text(data: bytes) -> str:
    import io

    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def measure_in_store(
    structure_sha256: str, editor_sha256: str, kind: str, original_sha256: str, store: Path
) -> dict:
    structure = json.loads(read(structure_sha256, store))
    document = read(editor_sha256, store).decode("utf-8")
    editor = editor_units_eurlex(document) if kind == "eurlex" else editor_units_boe(document)
    res = measure(structure, editor, pypdf_text(read(original_sha256, store)))
    res["inputs"] = {
        "structure": structure_sha256,
        "editor": editor_sha256,
        "type": kind,
        "original": original_sha256,
    }
    return res
