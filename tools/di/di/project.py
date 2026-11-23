"""Navigable folder of a document: the original, an index, one Markdown file per section and its resources.

```
<destination>/<name>/
  <name>.pdf                     the original, copied from the store
  index.md                       what the document is and what is in the folder
  contents/NN-<title>.md         one section per file, with its context in the YAML header
  resources/tables/table-M.md    each table in Markdown and each value with its headers
  resources/figures/figure-M.*   the image (if Docling exported it) and its record
  resources/bibliography.md      the bibliography entries with their key
```

It is a generated view, not registered knowledge: it comes from the DoclingDocument with the same computation as
the structure (`generic.analyze`), is regenerated whole when the processor changes and is not edited by hand.
Citations are still written and checked against the structure; the header of each file says which units of that
structure it covers. The body keeps the text of the document: what is added are XML marks (`<page n>`,
`<ref key>`, `<resource>`, `<note>`, `<formula>`) that do not change what is read.

The folder contains a copy of the document: it goes outside the repository, in the installation's local state.
"""

import base64
import json
import re
import shutil
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .context import clean_title
from .generic import VERSION as SEGMENTER_VERSION
from .generic import _caption, analyze
from .store import read

VERSION = "0.1"
GENERATOR = f"kbol-di/project {VERSION}"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_IMAGE_EXTENSION = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class ForeignFolder(RuntimeError):
    """The destination folder exists and this tool did not generate it: it is not deleted."""


def _slug(text: str, length: int = 60) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:length].strip("-") or "untitled"


def _write(path: Path, header: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yml = yaml.safe_dump(header, allow_unicode=True, sort_keys=False, width=1000).rstrip("\n")
    path.write_text(f"---\n{yml}\n---\n\n{body.rstrip()}\n", encoding="utf-8", newline="\n")


def _page(item: dict) -> int | None:
    prov = item.get("prov") or []
    return prov[0]["page_no"] if prov else None


def _first_sentence(text: str, length: int = 220) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"(.{20,}?[.!?])(\s|$)", t)
    sentence = m.group(1) if m else t
    return sentence if len(sentence) <= length else sentence[: length - 1].rstrip() + "…"


def _mark_references(text: str, keys: set[str]) -> str:
    """Wraps each "[n]" whose key is in the bibliography; the visible text does not change."""

    def replace(m: re.Match) -> str:
        nums = re.findall(r"\d+", m.group(0))
        if nums and all(n in keys for n in nums) and len(nums) == 1:
            return f'<ref key="{nums[0]}">{m.group(0)}</ref>'
        return m.group(0)

    return re.sub(r"\[\d+\]", replace, text) if keys else text


def _resources(doc: dict, section: dict) -> list[dict]:
    output = []
    for block in section["blocks"]:
        label = block["label"]
        if label not in ("table", "picture"):
            continue
        index = int(block["ref"].rsplit("/", 1)[1]) + 1
        caption = _caption(doc, block["item"])
        if label == "picture" and not caption and not (block["item"].get("image") or {}).get("uri"):
            continue
        kind = "table" if label == "table" else "figure"
        output.append({"type": kind, "id": f"{kind}-{index}", "block": block, "caption": caption, "index": index})
    return output


def _section_body(section: dict, resources: dict, bibliography_keys: set[str]) -> str:
    lines = [f"# {section['title']}"] if section["title"] else []
    current_page = None
    first = True
    for block in section["blocks"]:
        item, label = block["item"], block["label"]
        page = _page(item)
        if page is not None and page != current_page:
            lines.append(f'<page n="{page}"/>')
            current_page = page
        text = (item.get("text") or "").strip()
        if first and label in ("section_header", "title"):
            first = False
            continue
        first = False
        if label in ("table", "picture"):
            r = resources.get(block["ref"])
            if r:
                folder = "tables" if r["type"] == "table" else "figures"
                ref = f"../resources/{folder}/{r['id']}.md"
                lines.append(f'<resource type="{r["type"]}" id="{r["id"]}" ref="{ref}">{r["caption"] or ""}</resource>')
            continue
        if not text:
            continue
        if label in ("section_header", "title"):
            lines.append(f"**{clean_title(text)}**")
        elif label == "list_item":
            marker = (item.get("marker") or "").strip()
            bullet = marker if re.fullmatch(r"\[?\d+[.)\]]?|[a-z][.)]", marker or "") else "-"
            lines.append(f"{bullet} {_mark_references(text, bibliography_keys)}")
        elif label == "code":
            lines.append(f"```\n{text}\n```")
        elif label == "formula":
            lines.append(f"<formula>{text}</formula>")
        elif label == "footnote":
            lines.append(f"<note>{text}</note>")
        else:
            lines.append(_mark_references(text, bibliography_keys))
    return "\n\n".join(lines)


def _markdown_table(table: dict) -> str:
    """Docling's grid as a Markdown table; a merged cell repeats its text in each slot, like Docling."""
    grid = table.get("data", {}).get("grid") or []
    rows = [[re.sub(r"\s+", " ", (c or {}).get("text") or "").replace("|", r"\|").strip() for c in row] for row in grid]
    if not rows:
        return ""
    width = max(len(f) for f in rows)
    rows = [f + [""] * (width - len(f)) for f in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(f) + " |" for f in rows[1:]]
    return "\n".join(lines)


def _lines_by_section(markdown: str, titles: list[str | None]) -> list[list[int] | None]:
    """[start, end] (from 1, inclusive) of each section in the Markdown, looking for its headings in order.

    A section whose heading does not appear has no lines; the previous one extends to the next one that does.
    """
    lines = markdown.split("\n")
    comparable = [re.sub(r"\W+", "", re.sub(r"^#+\s*", "", x)).lower() for x in lines]
    starts: list[int | None] = []
    cursor = 0
    for i, title in enumerate(titles):
        if title is None:
            starts.append(1 if i == 0 else None)
            continue
        target = re.sub(r"\W+", "", title).lower()
        pos = next((k for k in range(cursor, len(lines)) if target and comparable[k] == target), None)
        starts.append(None if pos is None else pos + 1)
        if pos is not None:
            cursor = pos + 1
    output: list[list[int] | None] = []
    for i, start in enumerate(starts):
        if start is None:
            output.append(None)
            continue
        following = next((x for x in starts[i + 1 :] if x is not None), len(lines) + 1)
        end = following - 1
        while end > start and not lines[end - 1].strip():
            end -= 1
        output.append([start, end])
    return output


def _values_with_context(cells: list[dict]) -> str:
    rows = []
    for c in cells:
        row = " · ".join(c["row_label"])
        headers = " › ".join(c["headers"])
        before = " · ".join(x for x in (row, headers) if x)
        page = f" (p. {c['p']})" if c.get("p") else ""
        rows.append(f"- {before} = {c['text']}{page}" if before else f"- {c['text']}{page}")
    return "\n".join(rows)


def _image(item: dict) -> tuple[bytes, str] | None:
    uri = (item.get("image") or {}).get("uri") or ""
    m = re.match(r"data:([\w/+.-]+);base64,(.+)", uri, re.S)
    if not m:
        return None
    return base64.b64decode(m.group(2)), _IMAGE_EXTENSION.get(m.group(1), "png")


def _prepare_destination(folder: Path) -> None:
    if folder.exists():
        index = folder / "index.md"
        generated = index.exists() and f"by: {GENERATOR.split(' ')[0]}" in index.read_text(encoding="utf-8")
        if not generated:
            raise ForeignFolder(f"{folder} exists and is not a folder generated by kbol-di/project")
        shutil.rmtree(folder)
    folder.mkdir(parents=True)


def project(
    doc: dict,
    structure: dict,
    original: bytes,
    original_name: str,
    name: str,
    destination: Path,
    structure_sha256: str | None = None,
    markdown: str | None = None,
    markdown_sha256: str | None = None,
) -> dict:
    """Writes `<destination>/<name>/` and returns what was written. Regenerates the folder if this tool generated it.

    With `markdown` (the text representation of a document without pages), each section says in `lines` which
    lines of that Markdown it spans: that is what is cited with `lines-v1`.
    """
    if not _NAME.fullmatch(name or ""):
        raise ValueError(f"invalid folder name: {name!r} (letters, digits, dot, hyphen and underscore)")
    folder = Path(destination) / name
    _prepare_destination(folder)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    generated = {"by": GENERATOR, "at": now}
    a = analyze(doc, correct=structure.get("order_corrected", True))
    sections, keys, context = a["sections"], a["keys"], a["context"]
    bibliography_keys = {r["key"] for r in a["bibliography"]}
    units_by_section: dict[str, list[str]] = {}
    for u in structure.get("units", []):
        units_by_section.setdefault(u["key"].split(";")[0], []).append(u["key"])
    cells_by_unit = {u["key"]: u.get("cells", []) for u in structure.get("units", [])}
    origin = {
        "original_sha256": structure.get("original_sha256"),
        "structure_sha256": structure_sha256,
        "docling_sha256": structure.get("docling_sha256"),
    }
    if markdown_sha256:
        origin["markdown_sha256"] = markdown_sha256
    lines = _lines_by_section(markdown, [s["title"] for s in sections]) if markdown else [None] * len(sections)
    extension = Path(original_name).suffix.lower() or ".pdf"
    file_name = f"{name}{extension}"
    (folder / file_name).write_bytes(original)

    ids = [f"{name}#{c}" for c in keys]
    children: dict[str, list[str]] = {}
    for i, ctx in enumerate(context):
        if ctx["parent"]:
            children.setdefault(f"{name}#{ctx['parent']}", []).append(ids[i])
    files, tables, figures = [], [], []
    for order, (key, section, ctx) in enumerate(zip(keys, sections, context, strict=True), start=1):
        resources = _resources(doc, section)
        by_ref = {r["block"]["ref"]: r for r in resources}
        body = _section_body(section, by_ref, bibliography_keys)
        plain_text = next(
            (b["item"]["text"] for b in section["blocks"] if b["label"] in ("text", "list_item") and b["item"].get("text")),
            section["title"] or "",
        )
        pages = sorted({p for b in section["blocks"] for p in [_page(b["item"])] if p is not None})
        references = []
        for u in structure.get("units", []):
            if u["key"].split(";")[0] == key:
                references.extend(r for r in u.get("references", []) if r not in references)
        file_name_section = f"{order:02d}-{_slug(section['title'] or 'front-matter')}.md"
        header = {
            "id": f"{name}#{key}",
            "type": "section",
            "title": section["title"] or "(front matter)",
            "description": _first_sentence(plain_text),
            "document": name,
            "number": ctx["number"],
            "depth": ctx["depth"],
            "parent": f"{name}#{ctx['parent']}" if ctx["parent"] else None,
            "children": children.get(f"{name}#{key}", []),
            "path": ctx["path"],
            "part_type": ctx["part_type"],
            "pages": pages,
            **({"lines": lines[order - 1]} if lines[order - 1] else {}),
            "references": references,
            "resources": [r["id"] for r in resources],
            "origin": {**origin, "units": units_by_section.get(key, [])},
            "generated": generated,
        }
        _write(folder / "contents" / file_name_section, header, body)
        files.append({"file": file_name_section, "title": section["title"], "depth": ctx["depth"],
                      "part_type": ctx["part_type"], "pages": pages})
        for r in resources:
            item, unit = r["block"]["item"], f"{key};{r['type']}={r['index']}"
            base = {
                "id": f"{name}#{r['id']}",
                "type": r["type"],
                "title": r["caption"] or r["id"],
                "document": name,
                "section": f"{name}#{key}",
                "path": ctx["path"],
                "pages": sorted({p["page_no"] for p in item.get("prov", [])}),
                "unit": unit if unit in units_by_section.get(key, []) else None,
                "origin": origin,
                "generated": generated,
            }
            if r["type"] == "table":
                cells = cells_by_unit.get(unit, [])
                grid = _markdown_table(item)
                table_body = f"# {r['caption'] or r['id']}\n\n{grid}\n\n## Values with their context\n\n{_values_with_context(cells)}"
                _write(folder / "resources" / "tables" / f"{r['id']}.md", {**base, "cells": len(cells)}, table_body)
                tables.append({**r, "section": files[-1]["file"]})
            else:
                image = _image(item)
                extra = {}
                figure_body = f"# {r['caption'] or r['id']}\n\n"
                if image:
                    data, ext = image
                    (folder / "resources" / "figures").mkdir(parents=True, exist_ok=True)
                    (folder / "resources" / "figures" / f"{r['id']}.{ext}").write_bytes(data)
                    extra["image"] = f"{r['id']}.{ext}"
                    figure_body += f"![{r['caption'] or r['id']}]({r['id']}.{ext})\n"
                else:
                    figure_body += "<no-image/> Docling did not export the image of this figure.\n"
                _write(folder / "resources" / "figures" / f"{r['id']}.md", {**base, **extra}, figure_body)
                figures.append({**r, "section": files[-1]["file"], "image": bool(image)})

    if a["bibliography"]:
        entries = "\n".join(f'- <entry key="{r["key"]}">{r["text"]}</entry>' for r in a["bibliography"])
        _write(
            folder / "resources" / "bibliography.md",
            {"id": f"{name}#bibliography", "type": "bibliography", "title": "Bibliography", "document": name,
             "entries": len(a["bibliography"]), "author_year": a["author_year"], "generated": generated},
            f"# Bibliography\n\n{entries}",
        )

    title = next((clean_title(b["item"]["text"]) for s in sections for b in s["blocks"] if b["label"] == "title"), None)
    title = title or next((s["title"] for s in sections if s["title"]), name)
    abstract = next((s for s, c in zip(sections, context, strict=True) if c["part_type"] == "abstract"), None)
    description = _first_sentence(
        next((b["item"]["text"] for b in abstract["blocks"] if b["label"] == "text"), title) if abstract else title
    )
    contents_index = "\n".join(
        f"{'  ' * max(0, f['depth'] - 1)}- [{f['title'] or '(front matter)'}](contents/{f['file']})"
        + (f" · pp. {f['pages'][0]}–{f['pages'][-1]}" if len(f["pages"]) > 1 else f" · p. {f['pages'][0]}" if f["pages"] else "")
        for f in files
    )
    table_list = "\n".join(f"- [{t['caption'] or t['id']}](resources/tables/{t['id']}.md) · in [{t['section']}](contents/{t['section']})" for t in tables)
    figure_list = "\n".join(
        f"- [{f['caption'] or f['id']}](resources/figures/{f['id']}.md){'' if f['image'] else ' · no image'}" for f in figures
    )
    parts = [
        f"# {title}",
        f"Folder generated by {GENERATOR} from the structure of the document; not edited by hand. "
        f"The original is [{file_name}]({file_name}). Citations are written against the structure, with the page each "
        "file states.",
        f"## Contents\n\n{contents_index}",
    ]
    if tables:
        parts.append(f"## Tables\n\n{table_list}")
    if figures:
        parts.append(f"## Figures\n\n{figure_list}")
    if a["bibliography"]:
        parts.append(f"## Bibliography\n\n[{len(a['bibliography'])} entries](resources/bibliography.md)")
    if structure.get("warnings"):
        parts.append("## Segmentation warnings\n\n" + "\n".join(f"- {x}" for x in structure["warnings"]))
    index_header = {
        "id": name,
        "type": "document",
        "title": title,
        "description": description,
        "original": {"file": file_name, "sha256": structure.get("original_sha256"), "pages": len(structure.get("pages", []))},
        "representation": {**{k: v for k, v in origin.items() if k != "original_sha256"},
                           "segmenter": structure.get("segmenter", f"kbol-di/generic {SEGMENTER_VERSION}")},
        "contents": len(files),
        "tables": len(tables),
        "figures": len(figures),
        "references": len(a["bibliography"]),
        "generated": generated,
    }
    _write(folder / "index.md", index_header, "\n\n".join(parts))
    return {"folder": str(folder), "contents": len(files), "tables": len(tables), "figures": len(figures),
            "figures_without_image": sum(1 for f in figures if not f["image"]), "references": len(a["bibliography"])}


def default_destination(store: Path) -> Path:
    """Next to the store: `<installation state>/documents`."""
    return Path(store).parent / "documents"


def project_in_store(
    structure_sha256: str,
    name: str,
    store: Path,
    destination: Path | None = None,
    markdown: str | None = None,
    markdown_sha256: str | None = None,
) -> dict:
    structure = json.loads(read(structure_sha256, store))
    if not structure.get("docling_sha256"):
        raise ValueError("the structure does not say which DoclingDocument it derives from")
    doc = json.loads(read(structure["docling_sha256"], store))
    original = read(structure["original_sha256"], store)
    meta_path = Path(store) / "meta" / f"{structure['original_sha256']}.json"
    origins = json.loads(meta_path.read_text(encoding="utf-8")).get("origins", []) if meta_path.exists() else []
    original_name = Path(str(origins[0]).split("?")[0]).name if origins else f"{name}.pdf"
    return project(doc, structure, original, original_name, name, destination or default_destination(store),
                   structure_sha256=structure_sha256, markdown=markdown, markdown_sha256=markdown_sha256)
