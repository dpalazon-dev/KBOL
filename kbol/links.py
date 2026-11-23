"""Navigable links of the Markdown documents of a repository: paths, fragments and anchors.

It applies «Persistent instructions, procedures and resolvable references» of the contract: a reference that does not
resolve is not a reference. It holds for any Markdown file in the repository, whether or not it is a record:

- an internal link leads to a file or folder that exists with the same capitalization (Windows does not tell them
  apart; GitHub and Linux do); a path that starts with «/» is read from the root, as on GitHub;
- a fragment (`#anchor`) towards a `.md` exists in the target, as an explicit anchor (`id=` in any tag, `name=` in
  `<a>`) or as the anchor GitHub derives from a heading; explicit anchors are not repeated;
- a local absolute path (`C:/…`) is not a link someone else can follow;
- examples inside code blocks or inline code are not links.

External links (`https:`, `mailto:`), targets outside the root and fragments of a file that is not Markdown are not
checked. The analysis is of real Markdown (markdown-it), not of regular expressions over lines.

What exists is what git sees in the root: the versioned files and the new ones not ignored, with the capitalization
of the index. The installation may declare in its configuration (`links`) the folders that are not reviewed
(`exclude`: literal copies of other people's documents, whose links point to where they were) and the debt (`debt`:
broken links of documents that are no longer rewritten). The debt does not block, and the debt that stops failing is
reported so that it can be removed.
"""

import collections
import posixpath
import re
import subprocess
import unicodedata
from functools import cache
from pathlib import Path
from urllib.parse import unquote

from .snapshot import git_environment


@cache
def _md():
    """CommonMark parser, imported when used and not when the CLI loads."""
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark")


_SCHEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")  # https:, mailto:; a single letter would be a Windows drive
_UNIT = re.compile(r"^[A-Za-z]:[\\/]")
_LABEL = re.compile(r"<([A-Za-z][\w-]*)\b([^>]*)>")
_ID_ATTRIBUTE = re.compile(r"""(?<![\w-])id\s*=\s*["']([^"']+)["']""")
_NAME_ATTRIBUTE = re.compile(r"""(?<![\w-])name\s*=\s*["']([^"']+)["']""")


def _without_header(text):
    """The text with the YAML header blanked (keeping the lines): its closing «---» is not a heading."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join([""] * (i + 1) + lines[i + 1 :])
    return text


def _tokens(text):
    return _md().parse(_without_header(text))


def slug(title):
    """The anchor GitHub gives a heading: lowercase, keeps letters, marks, numbers, «_», «-» and spaces (which become
    hyphens) and removes the rest (punctuation, symbols, emojis)."""
    kept = (
        c
        for c in title.strip().lower()
        if c in " -" or unicodedata.category(c)[0] in "LMN" or unicodedata.category(c) == "Pc"
    )
    return "".join(kept).replace(" ", "-")


def _html_ids(html):
    """The anchors a piece of HTML declares: `id=` in any tag and `name=` in `<a>`, once per tag."""
    ids = []
    for label, attributes in _LABEL.findall(html):
        own = set(_ID_ATTRIBUTE.findall(attributes))
        if label.lower() == "a":
            own |= set(_NAME_ATTRIBUTE.findall(attributes))
        ids += sorted(own)
    return ids


def anchors(text):
    """(anchors of the document, repeated explicit anchors as (line, id))."""
    tokens = _tokens(text)
    seen = collections.Counter()
    all_, explicit_ids, repeated = set(), set(), []

    def explicit(ident, line):
        if ident in explicit_ids:
            repeated.append((line, ident))
        explicit_ids.add(ident)
        all_.add(ident)

    for i, t in enumerate(tokens):
        line = t.map[0] + 1 if t.map else 0
        if t.type == "heading_open":
            children = tokens[i + 1].children or []
            base = slug("".join(h.content for h in children if h.type in ("text", "code_inline")))
            n = seen[base]
            seen[base] += 1
            all_.add(base if n == 0 else f"{base}-{n}")
        elif t.type == "html_block":
            for ident in _html_ids(t.content):
                explicit(ident, line)
        elif t.type == "inline":
            for h in t.children or []:
                if h.type == "html_inline":
                    for ident in _html_ids(h.content):
                        explicit(ident, line)
    return all_, repeated


class _Cursor:
    """Searches forward where each element of a block appears, to give its line in reading order."""

    def __init__(self, lines, start, end):
        self.lines, self.end = lines, end
        self.line, self.column = start, 0

    def search(self, candidates):
        for n in range(self.line, self.end):
            since = self.column if n == self.line else 0
            positions = [p for c in candidates if c and (p := self.lines[n].find(c, since)) >= 0]
            if positions:
                self.line, self.column = n, min(positions) + 1
                return n + 1
        return self.line + 1  # it does not appear as is (escapes, references): the line the block is at


def links(text):
    """(line, decoded target) of each link and image, outside code blocks and inline code."""
    lines = text.split("\n")
    found = []
    for t in _tokens(text):
        if t.type != "inline" or not t.map:
            continue
        cursor = _Cursor(lines, *t.map)
        for h in t.children or []:
            if h.type == "link_open":
                target = str(h.attrs.get("href", ""))
            elif h.type == "image":
                target = str(h.attrs.get("src", ""))
            else:
                continue
            readable = unquote(target)
            line = cursor.search([f"]({d}" for d in (readable, target)] + [f"](<{readable}", f"]: {readable}"])
            found.append((line, readable))
    return found


def _resolve(origin, path):
    """The root path a target leads to: from the document's folder, or from the root if it starts with «/»; without
    «?query»; «.» is the root."""
    path = path.split("?", 1)[0]
    base = "" if path.startswith("/") else posixpath.dirname(origin)
    return posixpath.normpath(posixpath.join(base, path.lstrip("/"))).rstrip("/") or "."


def review(docs, existing, read, debt=frozenset()):
    """{errors, links, debt_used} of the documents `{path: text}`.

    `existing` are the root paths with their capitalization; `read` gives the text of a target (None if it cannot).
    The debt is pairs (document, decoded target) already broken, which count as used and not as errors.
    """
    folders = {"."}
    for path in existing:
        parts = path.split("/")[:-1]
        folders.update("/".join(parts[: i + 1]) for i in range(len(parts)))
    spelled = {r.lower(): r for r in existing | folders}
    cache, errors, used, total = {}, [], set(), 0

    def note(origin, line, target, message):
        if (origin, target) in debt:
            used.add((origin, target))
        else:
            errors.append({"path": origin, "line": line, "target": target, "message": message})

    def anchors_of(path):
        if path not in cache:
            text = read(path)
            if text is None:
                return None
            cache[path] = anchors(text)[0]
        return cache[path]

    for origin, text in docs.items():
        for line, ident in anchors(text)[1]:
            note(origin, line, f"#{ident}", f"the explicit anchor «{ident}» is repeated")
        for line, target in links(text):
            total += 1
            if _UNIT.match(target):
                note(origin, line, target, f"«{target}»: local absolute path; use a relative path")
                continue
            if not target or _SCHEMA.match(target):
                continue
            path, _, fragment = target.partition("#")
            goal = _resolve(origin, path) if path.split("?", 1)[0] else origin
            if goal.startswith(".."):
                continue
            if goal not in existing and goal not in folders:
                right = spelled.get(goal.lower())
                detail = f"does not exist; it is spelled {right}" if right else "does not exist"
                note(origin, line, target, f"«{target}»: {goal} {detail}")
                continue
            if fragment and goal.endswith(".md"):
                available = anchors_of(goal)
                if available is not None and fragment not in available:
                    note(origin, line, target, f"«{target}»: {goal} has no anchor «{fragment}»")
    return {"errors": errors, "links": total, "debt_used": used}


def configuration(installation):
    """(excluded folders, debt as pairs) that the installation declares in `links`; ValueError if malformed."""
    declared = installation.get("links", {}) if isinstance(installation, dict) else None
    if not isinstance(declared, dict) or set(declared) - {"exclude", "debt"}:
        raise ValueError("links is an object with exclude and debt")
    exclude = declared.get("exclude", [])
    if not isinstance(exclude, list) or any(not isinstance(c, str) or not c.strip("./") for c in exclude):
        raise ValueError("links.exclude is a list of folders or files of the root")
    debt = declared.get("debt", [])
    if not isinstance(debt, list) or any(
        not isinstance(d, dict)
        or set(d) != {"document", "target"}
        or not all(isinstance(v, str) and v for v in d.values())
        for d in debt
    ):
        raise ValueError("links.debt is a list of {document, target}")
    return [_normal(c) for c in exclude], {(_normal(d["document"]), d["target"]) for d in debt}


def _normal(path):
    return posixpath.normpath(path.replace("\\", "/")).strip("/")


def _inside(path, folders):
    return any(c == "." or path == c or path.startswith(c + "/") for c in folders)


def _git_paths(root):
    """What git sees under the root and is still on disk: versioned or new and not ignored, with the index's
    capitalization."""
    command = ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    p = subprocess.run(command, capture_output=True, env=git_environment())
    if p.returncode != 0:
        raise ValueError(f"{root} is not a git working tree: it is unknown which paths exist")
    return {r for r in p.stdout.decode("utf-8").split("\0") if r and (Path(root) / r).exists()}


def check(root, folders=(".",), exclude=(), debt=frozenset()):
    """Reviews the `.md` files of the root's folders, except the excluded ones.

    {documents, links, errors, debt_used, debt_left, unreadable}. Targets are looked up in the whole root, also in
    what is excluded and outside the folders: what is not reviewed can still be linked.
    """
    root = Path(root)
    folders = [_normal(c) for c in folders]
    for c in folders:
        if not (root / c).is_dir():
            raise FileNotFoundError(f"the folder does not exist: {c}")
    existing = _git_paths(root)

    def read(path):
        try:
            return (root / path).read_bytes().decode("utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError):
            return None

    docs, unreadable = {}, []
    for path in sorted(existing):
        if not path.endswith(".md") or not _inside(path, folders) or _inside(path, exclude):
            continue
        text = read(path)
        if text is None:
            unreadable.append(path)
        else:
            docs[path] = text
    res = review(docs, existing, lambda r: docs.get(r) or read(r), debt)

    def pairs(set_):
        return [{"document": d, "target": e} for d, e in sorted(set_)]

    return {
        "documents": len(docs),
        "links": res["links"],
        "errors": res["errors"],
        "debt_used": pairs(res["debt_used"]),
        "debt_left": pairs(set(debt) - res["debt_used"]),
        "unreadable": unreadable,
    }
