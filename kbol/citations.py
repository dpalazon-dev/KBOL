"""Citation resolver: checks that each `sources[]` entry of a record points to something that exists in the cited
version.

For a PDF, the citation combines a logical unit (`norm-v1`) and a page with an optional region (`pdf-v1`), and it is
resolved against the `structure-v1` representation set by `representation_id`. For a text, lines (`lines-v1`, or the
anchors of the legacy format) are resolved against the blob of the anchored revision. The core does not read PDF: the
page exists if the structure, derived from that original by its fingerprint, declares it.

A document without pages (Word, spreadsheet, HTML) is cited by lines of its text representation: with
`representation_id`, the lines are resolved against that representation, which must be text and derive from the
cited original, directly or through other derivations. Without `representation_id`, against the original.

States: `resolved`; `broken` (different fingerprint, or a page, unit or text that is not there); `inconsistent` (the
unit is not on the cited page or region); `ambiguous` (the unit appears more than once); `uncheckable` (the original
or the representation is missing on this machine, or the anchor has no profile: integrity unchecked, not a failure).
"""

import hashlib
import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .core import FormatError, parse
from .locator import Citation, InvalidLocator, Lines, Page, parse_
from .snapshot import git_environment

STATES = ("resolved", "broken", "inconsistent", "ambiguous", "uncheckable")
_QUOTES = str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'"})
_SPACES = re.compile(r"\s+")
_STORE_PREFIX = "store:"


@dataclass(frozen=True)
class Result:
    state: str
    reason: str


def normalize(text: str) -> str:
    """Comparable form of a text: NFKC, without line-break hyphen or soft hyphen, straight quotes, lowercase."""
    t = unicodedata.normalize("NFKC", text).replace("­", "")
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    return _SPACES.sub(" ", t.translate(_QUOTES)).strip().lower()


def _contains(text: str, literal: str) -> str | None:
    """`exact`, `without_spaces` or None, depending on how the normalized literal quote appears."""
    t, lit = normalize(text), normalize(literal)
    if lit in t:
        return "exact"
    if lit.replace(" ", "") in t.replace(" ", ""):
        return "without_spaces"
    return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _overlap(a, b) -> bool:
    ax0, ay0, ax1, ay1 = (float(v) for v in a)
    bx0, by0, bx1, by1 = (float(v) for v in b)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def resolve_pdf(
    citation: Citation, *, original_sha256: str, original_path: Path | None, structure: dict, literal: str | None
) -> Result:
    if structure.get("profile") != "structure-v1":
        return Result("broken", "the representation is not structure-v1")
    if structure.get("original_sha256") != original_sha256:
        return Result("broken", "the representation does not derive from this original (different fingerprint)")
    if not isinstance(citation.physical, Page):
        return Result("broken", "a PDF citation needs the physical page (pdf-v1)")
    page = citation.physical
    if page.p not in {pg["p"] for pg in structure.get("pages", [])}:
        return Result("broken", f"page {page.p} does not exist in the representation")

    if citation.logical is not None:
        key = citation.logical.key()
        units = [u for u in structure.get("units", []) if u["key"] == key]
        if not units:
            return Result("broken", f"unit {key} does not exist in the representation")
        if len(units) > 1:
            return Result("ambiguous", f"unit {key} appears {len(units)} times")
        (unit,) = units
        if page.p not in unit["pages"]:
            return Result("inconsistent", f"unit {key} is on pages {unit['pages']}, not on page {page.p}")
        regions = [r["r"] for r in unit.get("regions", []) if r["p"] == page.p]
        if page.region and regions and not any(_overlap(page.region, r) for r in regions):
            return Result("inconsistent", f"the cited region does not touch unit {key} on page {page.p}")
        text = unit["text"]
    else:
        text = "\n".join(u["text"] for u in structure.get("units", []) if page.p in u["pages"])

    notes = []
    if literal:
        mode = _contains(text, literal)
        if mode is None:
            return Result("broken", "the literal quote does not appear in the cited unit")
        if mode == "without_spaces":
            notes.append("the literal quote matches without spaces (words split in the representation)")

    if original_path is None or not Path(original_path).exists():
        return Result("uncheckable", "; ".join(["structure conforming; original not available", *notes]))
    if _sha256(Path(original_path).read_bytes()) != original_sha256:
        return Result("broken", "the original in the store does not have the source's fingerprint")
    return Result("resolved", "; ".join(notes) or "resolved")


def resolve_lines(citation: Citation, *, text: str, expected_sha256: str, literal: str | None = None) -> Result:
    prefix = "legacy anchor; " if citation.inherited else ""
    if not isinstance(citation.physical, Lines) or citation.logical is not None:
        return Result("broken", "a text source is cited by lines")
    if _sha256(text.encode("utf-8")) != expected_sha256:
        return Result("broken", prefix + "the text does not have the source's fingerprint")
    lines = text.splitlines()
    ini, end = citation.physical.start, citation.physical.end
    if end > len(lines):
        return Result("broken", prefix + f"lines {ini}-{end} outside the text ({len(lines)} lines)")
    if literal and _contains("\n".join(lines[ini - 1 : end]), literal) is None:
        return Result("broken", prefix + "the literal quote does not appear in those lines")
    return Result("resolved", prefix + "resolved")


def _read_location(root: Path, location: str, store: Path | None) -> bytes | None:
    if location.startswith(_STORE_PREFIX):
        if store is None:
            return None
        path = Path(store) / location[len(_STORE_PREFIX) :]
        return path.read_bytes() if path.is_file() else None
    if location.startswith("git:"):
        _, rev, path = location.split(":", 2)
        p = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True, env=git_environment())
        return p.stdout if p.returncode == 0 else None
    return None


def _records(root: Path, folders: list[str]):
    for folder in folders:
        if not (root / folder).is_dir():
            raise FileNotFoundError(f"the folder does not exist: {folder}")
        for path in sorted((root / folder).rglob("*.md")):
            try:
                header, _ = parse(path.read_text(encoding="utf-8"))
            except (FormatError, UnicodeDecodeError):
                continue
            if header.get("id"):
                yield path, header


def _derives_from(sources: dict, derived_id: str, original_id: str, limit: int = 8) -> bool:
    """Whether the derivation comes from the original following `derived_from`, without cycles and with bounded
    depth."""
    pending, seen = [(derived_id, 0)], set()
    while pending:
        current, level = pending.pop()
        if current in seen or level > limit:
            continue
        seen.add(current)
        parents = (sources.get(current) or {}).get("derived_from") or []
        if original_id in parents:
            return True
        pending.extend((p, level + 1) for p in parents if isinstance(p, str))
    return False


def _resolve_lines_in_representation(root, sources, src, citation, source, original_data, store) -> Result:
    derived = sources.get(src["representation_id"])
    if derived is None:
        return Result("broken", "the cited representation is not an existing source")
    if not _derives_from(sources, derived["id"], source["id"]):
        return Result("broken", "the representation does not derive from the cited original")
    format = str(derived.get("format") or "text/")
    if not format.startswith("text/"):
        return Result("broken", f"a citation by lines needs a text representation, not {format}")
    rep = _read_location(root, derived.get("location", ""), store)
    if rep is None:
        return Result("uncheckable", "representation not available on this machine")
    try:
        text = rep.decode("utf-8")
    except UnicodeDecodeError:
        return Result("broken", "the representation is not UTF-8 text")
    r = resolve_lines(citation, text=text, expected_sha256=derived.get("sha256"), literal=src.get("context"))
    if r.state != "resolved":
        return r
    if original_data is None:
        return Result("uncheckable", "representation conforming; original not available")
    if _sha256(original_data) != source.get("sha256"):
        return Result("broken", "the original does not have the source's fingerprint")
    return r


def _resolve_source(root, sources, src, store) -> Result:
    source = sources.get(src.get("resource"))
    if source is None:
        return Result("broken", f"source {src.get('resource')} does not exist")
    try:
        citation = parse_(src.get("anchor", ""))
    except InvalidLocator as exc:
        return Result("uncheckable", f"anchor without profile: {exc}")
    source_sha = source.get("sha256")
    if src.get("hash") and src["hash"] != source_sha:
        return Result("broken", "the citation's fingerprint is not the source's")
    data = _read_location(root, source.get("location", ""), store)
    if isinstance(citation.physical, Lines) and src.get("representation_id"):
        return _resolve_lines_in_representation(root, sources, src, citation, source, data, store)
    if isinstance(citation.physical, Lines):
        if data is None:
            return Result("uncheckable", "text of the source not available")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return Result("broken", "the source is not UTF-8 text")
        return resolve_lines(citation, text=text, expected_sha256=source_sha, literal=src.get("context"))
    derived = sources.get(src.get("representation_id"))
    if derived is None:
        return Result("broken", "a PDF citation needs representation_id pointing to an existing source")
    structure_bytes = _read_location(root, derived.get("location", ""), store)
    if structure_bytes is None:
        return Result("uncheckable", "representation not available on this machine")
    if _sha256(structure_bytes) != derived.get("sha256"):
        return Result("broken", "the representation does not have the fingerprint of its derived source")
    original_path = None
    if data is not None and source.get("location", "").startswith(_STORE_PREFIX):
        original_path = Path(store) / source["location"][len(_STORE_PREFIX) :]
    return resolve_pdf(
        citation,
        original_sha256=source_sha,
        original_path=original_path,
        structure=json.loads(structure_bytes),
        literal=src.get("context"),
    )


def check(root: Path, folders: list[str], store: Path | None) -> dict:
    """Resolves each `sources[]` entry of the records in the folders; one row per citation and the count per state."""
    root = Path(root)
    records = list(_records(root, folders))
    sources = {c["id"]: c for _, c in records if str(c["id"]).startswith("SRC-")}
    rows = []
    for path, header in records:
        for src in header.get("sources") or []:
            if not isinstance(src, dict):
                continue
            r = _resolve_source(root, sources, src, store)
            rows.append(
                {
                    "record": header["id"],
                    "path": path.relative_to(root).as_posix(),
                    "source": src.get("id"),
                    "resource": src.get("resource"),
                    "anchor": src.get("anchor"),
                    "state": r.state,
                    "reason": r.reason,
                }
            )
    count = {e: sum(1 for f in rows if f["state"] == e) for e in STATES}
    return {"rows": rows, "count": count}
