"""Clause and claim markup of the concrete contract.

`<clause id="C1">` opens a clause on its own line and `</clause>` closes it on another; they do not nest and the
identifier is unique. `<fact id="H1" evidence="…" source="…">…</fact>` marks an inline claim and
`<fact ref="FACT-…">…</fact>` cites a fact record. Markup inside code blocks or inline code, or escaped with a
backslash, is not interpreted.
"""

import re

from .model import ANCHOR

_OPENING = re.compile(rf'^<clause id="({ANCHOR})">$')
_CLOSING = "</clause>"
_MARK = re.compile(r"^\s*</?clause\b")
_FACT = re.compile(r"(?<!\\)<fact\b([^>]*)>(.*?)(?<!\\)</fact>", re.S)
_FACT_OPENING = re.compile(r"(?<!\\)<fact\b")
_ATTRIBUTE = re.compile(r'\s+([a-z_]+)="([^"]*)"')
_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_PARAGRAPH = re.compile(r"(\n[ \t]*\n)")
_FACT_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(?!\n)$")


class MarkupError(ValueError):
    """Malformed clause or claim markup."""


def _code_lines(body):
    from markdown_it import MarkdownIt  # on use: importing it costs as much as a whole command

    excluded = set()
    for token in MarkdownIt().parse(body):
        if token.type in ("fence", "code_block") and token.map:
            excluded.update(range(*token.map))
    return excluded


def _text_without_code(body):
    excluded = _code_lines(body)
    lines = ["" if i in excluded else line for i, line in enumerate(body.split("\n"))]
    # Inline code does not cross a blank line: it is searched paragraph by paragraph.
    chunks = _PARAGRAPH.split("\n".join(lines))
    return "".join(
        t if i % 2 else _INLINE_CODE.sub(lambda m: " " * len(m.group(0)), t) for i, t in enumerate(chunks)
    )


def clauses(body):
    """{anchor: text} in order of appearance."""
    lines = body.replace("\r\n", "\n").split("\n")
    excluded = _code_lines("\n".join(lines))
    found, current, start = {}, None, 0
    for i, line in enumerate(lines):
        if i in excluded:
            continue
        m = _OPENING.match(line)
        if m:
            anchor = m.group(1)
            if current is not None:
                raise MarkupError(f"line {i + 1}: clause nested in {current}")
            if anchor in found:
                raise MarkupError(f"line {i + 1}: repeated clause {anchor}")
            current, start = anchor, i + 1
        elif line == _CLOSING:
            if current is None:
                raise MarkupError(f"line {i + 1}: closing without opening")
            found[current] = "\n".join(lines[start:i]).strip("\n")
            current = None
        elif _MARK.match(line):
            raise MarkupError(f"line {i + 1}: malformed clause markup")
    if current is not None:
        raise MarkupError(f"clause {current} without closing")
    return found


def _attributes(text):
    pos, attrs = 0, {}
    for m in _ATTRIBUTE.finditer(text):
        if m.start() != pos or m.group(1) in attrs:
            raise MarkupError(f"malformed fact attributes: {text!r}")
        attrs[m.group(1)] = m.group(2)
        pos = m.end()
    if text[pos:].strip():
        raise MarkupError(f"malformed fact attributes: {text!r}")
    return attrs


def facts(body):
    """Marked claims, in order. Validates their shape; the schema validates evidence and source."""
    text = _text_without_code(body)
    result, seen, consumed = [], set(), 0
    for m in _FACT.finditer(text):
        if _FACT_OPENING.search(text, consumed, m.start()):
            raise MarkupError("fact markup without closing")
        inner = m.group(2)
        if _FACT_OPENING.search(inner):
            raise MarkupError("nested fact markup")
        attrs = _attributes(m.group(1))
        if set(attrs) == {"ref"}:
            result.append({"ref": attrs["ref"], "text": inner})
        elif set(attrs) == {"id", "evidence", "source"}:
            if not _FACT_ID.match(attrs["id"]) or attrs["id"] in seen:
                raise MarkupError(f"invalid or repeated fact identifier: {attrs['id']}")
            seen.add(attrs["id"])
            result.append({**attrs, "text": inner})
        else:
            raise MarkupError(f"a fact carries id, evidence and source, or only ref: {sorted(attrs)}")
        consumed = m.end()
    if _FACT_OPENING.search(text, consumed):
        raise MarkupError("fact markup without closing")
    return result
