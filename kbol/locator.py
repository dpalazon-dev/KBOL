"""Citation locators with a profile (`anchor` of `sources`).

Three profiles, each with a single written form:

- ``lines-v1:<ini>-<end>``: inclusive lines from 1 of a UTF-8 text.
- ``pdf-v1:p=<n>[;r=x0,y0,x1,y1]``: physical page from 1 and a region normalized between 0 and 1, origin at the top
  left, with up to four decimals. The coordinates are kept as text so as not to lose their form.
- ``norm-v1:<key>=<value>;…``: logical unit of a norm, with the keys in hierarchical order.

A citation may combine the logical and the physical part: ``<norm-v1:…> @ <pdf-v1:…>``. The anchors of the legacy
format (``l. 66-84 (…)`` and ``L10-L20``) are read as ``lines-v1`` marked as legacy; any other free form is invalid.
This module only validates the form: whether the page, the unit or the text exist is checked by ``kbol.citations``.

The ``norm-v1`` keys name the units of Spanish and EU legal texts as written in Spanish (``cons`` recital, ``anx``
annex, ``parte`` part, ``cap`` chapter, ``sec`` section, ``art`` article, ``ap`` paragraph, ``pto`` point, ``let``
letter, ``num`` number): they are data of the profile, shared with ``tools/di``, and are not translated.
"""

import re
from dataclasses import dataclass

NORM_KEYS = ("cons", "anx", "parte", "cap", "sec", "art", "ap", "pto", "let", "num")
_NORM = "norm-v1:"

_LINES = re.compile(r"lines-v1:(\d+)-(\d+)")
_PDF = re.compile(r"pdf-v1:p=(\d+)(?:;r=([^;]+))?")
_COORD = re.compile(r"(?:0|1)(?:\.\d{1,4})?")
_VALUE = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ.]+")
_LEGACY = re.compile(r"(?:l\.\s*(\d+)(?:\s*-\s*(\d+))?(?:\s*\(.*\))?|L(\d+)-L(\d+))")


class InvalidLocator(ValueError):
    pass


@dataclass(frozen=True)
class Lines:
    start: int
    end: int


@dataclass(frozen=True)
class Page:
    p: int
    region: tuple[str, str, str, str] | None


@dataclass(frozen=True)
class Norm:
    parts: tuple[tuple[str, str], ...]

    def key(self) -> str:
        return ";".join(f"{k}={v}" for k, v in self.parts)


@dataclass(frozen=True)
class Citation:
    logical: Norm | None
    physical: Lines | Page | None
    inherited: bool = False


def _lines(ini: str, end: str) -> Lines:
    a, b = int(ini), int(end)
    if a < 1 or b < a:
        raise InvalidLocator(f"invalid line range: {ini}-{end}")
    return Lines(a, b)


def _page(text: str) -> Page:
    m = _PDF.fullmatch(text)
    if not m:
        raise InvalidLocator(f"malformed pdf-v1 selector: {text!r}")
    p = int(m.group(1))
    if p < 1:
        raise InvalidLocator("the physical page starts at 1")
    if m.group(2) is None:
        return Page(p, None)
    coords = m.group(2).split(",")
    if len(coords) != 4 or not all(_COORD.fullmatch(c) for c in coords):
        raise InvalidLocator(f"invalid region: {m.group(2)!r} (four values between 0 and 1, up to 4 decimals)")
    x0, y0, x1, y1 = (float(c) for c in coords)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise InvalidLocator(f"invalid region: {m.group(2)!r} (x0 < x1 and y0 < y1 within 0-1)")
    return Page(p, tuple(coords))


def _norm(text: str) -> Norm:
    body = text[len(_NORM) :]
    parts = []
    last = -1
    for chunk in body.split(";"):
        key, sep, value = chunk.partition("=")
        if not sep or not _VALUE.fullmatch(value):
            raise InvalidLocator(f"malformed norm-v1 part: {chunk!r}")
        if key not in NORM_KEYS:
            raise InvalidLocator(f"unknown key in norm-v1: {key!r}")
        order = NORM_KEYS.index(key)
        if order <= last:
            raise InvalidLocator(f"key out of order or repeated in norm-v1: {key!r}")
        last = order
        parts.append((key, value))
    return Norm(tuple(parts))


def _simple(text: str) -> Norm | Lines | Page:
    if text.startswith(_NORM):
        return _norm(text)
    if text.startswith("pdf-v1:"):
        return _page(text)
    m = _LINES.fullmatch(text)
    if m:
        return _lines(m.group(1), m.group(2))
    raise InvalidLocator(f"locator without a known profile: {text!r}")


def parse_(anchor: str) -> Citation:
    """Reads an `anchor`; raises `InvalidLocator` if it is neither a locator of the profiles nor a legacy form."""
    text = (anchor or "").strip()
    if not text:
        raise InvalidLocator("empty anchor")
    m = _LEGACY.fullmatch(text)
    if m:
        if m.group(1) is not None:
            return Citation(None, _lines(m.group(1), m.group(2) or m.group(1)), inherited=True)
        return Citation(None, _lines(m.group(3), m.group(4)), inherited=True)
    chunks = [t.strip() for t in text.split(" @ ")]
    if len(chunks) > 2:
        raise InvalidLocator("a citation combines at most one logical and one physical part")
    pieces = [_simple(t) for t in chunks]
    if len(pieces) == 1:
        (piece,) = pieces
        return Citation(piece, None) if isinstance(piece, Norm) else Citation(None, piece)
    logical, physical = pieces
    if not isinstance(logical, Norm) or not isinstance(physical, Page):
        raise InvalidLocator("the combined citation is norm-v1 @ pdf-v1")
    return Citation(logical, physical)


def _format_simple(piece: Norm | Lines | Page) -> str:
    if isinstance(piece, Norm):
        return _NORM + piece.key()
    if isinstance(piece, Lines):
        return f"lines-v1:{piece.start}-{piece.end}"
    return f"pdf-v1:p={piece.p}" + (f";r={','.join(piece.region)}" if piece.region else "")


def format_(citation: Citation) -> str:
    """Canonical form of the locator; a legacy citation is already written as `lines-v1`."""
    pieces = [p for p in (citation.logical, citation.physical) if p is not None]
    if not pieces:
        raise InvalidLocator("citation without locator")
    return " @ ".join(_format_simple(p) for p in pieces)
