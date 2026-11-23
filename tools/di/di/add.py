"""A document, from origin to citable representation and navigable folder, in a single command.

By format:

- PDF: capture, Docling (with figures as images), generic structure, crosscheck with pypdf.
- PowerPoint: the same without crosscheck; each slide is a page and is cited like a PDF.
- Word and spreadsheet: Docling, generic structure without pages and its Markdown export, which is the
  representation cited by lines.
- HTML: MarkItDown to Markdown, which is its only representation; cited by lines.

The format comes from the origin's extension; `fmt` declares it by hand when the origin has none or a misleading
one, and an origin with neither extension nor declared format is treated as PDF, as before other formats were
supported.

With `name`, it also generates the document folder (`di.project`). Returns what the source records need and what
to check before citing. It does not write records or judge quality.
"""

import json
from pathlib import Path

from .crosscheck import crosscheck_in_store
from .generic import generic_in_store
from .process import FORMATS, HTML, process
from .store import capture, read, save

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
    ".htm": "text/html",
}


def _extension(origin: str | Path) -> str:
    return Path(str(origin).split("?")[0]).suffix.lower()


def _format(origin: str | Path, fmt: str | None) -> str:
    """The extension that decides processing: the declared one, the origin's or, if the origin has none, PDF."""
    # An origin without extension (the URL of a PDF on EUR-Lex) always came in as PDF, and still does.
    extension = "." + fmt.strip().lower().lstrip(".") if fmt else _extension(origin) or ".pdf"
    if extension not in FORMATS:
        supported = ", ".join(sorted(FORMATS))
        raise ValueError(f"unsupported format: {extension}; supported: {supported}. Declare it with --format if the origin does not say")
    return extension


def add(
    origin: str | Path,
    store: Path,
    name: str | None = None,
    destination: Path | None = None,
    fmt: str | None = None,
) -> dict:
    extension = _format(origin, fmt)
    original = capture(origin, store, media_type=MEDIA_TYPES[extension])
    processed = process(original["sha256"], store, extension)
    output: dict = {"original": original, "review": []}
    if extension in HTML:
        output["markdown"] = processed["markdown"]
        output["processed"] = {k: v for k, v in processed.items() if k != "markdown"}
        output["review"].append("HTML converted with MarkItDown: no structure or folder; cited by lines of the Markdown")
        return output

    output["docling"] = {k: v for k, v in processed.items() if k != "markdown"}
    if "markdown" in processed:
        output["markdown"] = processed["markdown"]
    structure = generic_in_store(processed["sha256"], original["sha256"], store)
    output["structure"] = structure
    if extension == ".pdf":
        report = crosscheck_in_store(structure["sha256"], original["sha256"], store)
        data = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        report_sha256, _ = save(data, store)
        summary = report["summary"]
        output["crosscheck"] = {"sha256": report_sha256, "summary": summary, "limits": report["limits"]}
        review = output["review"]
        if summary["pages_without_text_layer"]:
            review.append(f"pages without a text layer, not measurable: {summary['pages_without_text_layer']}")
        if summary["pages_with_low_recall"]:
            review.append(f"pages where the structure loses text: {summary['pages_with_low_recall']}")
        if summary["pages_with_low_support"]:
            review.append(f"pages with text that pypdf does not see there: {summary['pages_with_low_support']}")
        if summary["missing_numbers"] or summary["unsupported_numbers"]:
            pages = [f["p"] for f in report["pages"] if f["missing_numbers"] or f["unsupported_numbers"]]
            review.append(
                f"numbers: {summary['missing_numbers']} from the PDF missing in the structure and "
                f"{summary['unsupported_numbers']} from the structure unsupported by the PDF, on pages {pages}"
            )
        if structure["pages_without_unit"]:
            review.append(f"pages without any unit: {structure['pages_without_unit']}")
    else:
        output["review"].append(f"{extension}: no second reading to crosscheck against; review what you cite by eye")
    if name:
        from .project import project_in_store

        markdown = read(processed["markdown"]["sha256"], store).decode("utf-8") if "markdown" in processed else None
        output["folder"] = project_in_store(
            structure["sha256"], name, store, destination, markdown=markdown,
            markdown_sha256=processed.get("markdown", {}).get("sha256"),
        )
    return output
