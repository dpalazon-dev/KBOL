"""Processing of an original in the store, locally and on CPU: Docling for PDF and office files, MarkItDown for HTML.

The output is the native DoclingDocument JSON (`export_to_dict`), serialized deterministically and saved in the
same store. A document without pages (Word, spreadsheet) is cited by lines, so its Markdown export is saved too:
it is the text representation that `kbol citations` resolves. An HTML file does not go through Docling:
MarkItDown converts it to Markdown and that is its only representation.

The run returns what the derived source needs: processor, exact versions, configuration and time. That the
process finishes says nothing about its fidelity: `di.fidelity` and `di.crosscheck` measure that.
"""

import io
import json
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from .store import read, save

# Figures are exported as images (at double resolution) so the document folder has them. The four regulations of
# the first pilot were processed without them: their configuration was the earlier one, without the last two keys.
CONFIGURATION = {
    "do_ocr": False,
    "do_table_structure": True,
    "table_mode": "accurate",
    "device": "cpu",
    "generate_picture_images": True,
    "images_scale": 2.0,
}
OFFICE = {".docx": "DOCX", ".pptx": "PPTX", ".xlsx": "XLSX"}
WITHOUT_PAGES = {".docx", ".xlsx"}
HTML = {".html", ".htm"}
FORMATS = {".pdf", *OFFICE, *HTML}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _save_json(document: dict, store: Path) -> str:
    output = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return save(output, store)[0]


def process(fingerprint: str, store: Path, extension: str = ".pdf") -> dict:
    extension = extension.lower()
    if extension not in FORMATS:
        raise ValueError(f"unsupported format: {extension} (supported: {', '.join(sorted(FORMATS))})")
    if extension in HTML:
        return _process_html(fingerprint, store)
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if extension == ".pdf":
        options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
        options.table_structure_options.mode = TableFormerMode.ACCURATE
        options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
        options.generate_picture_images = CONFIGURATION["generate_picture_images"]
        options.images_scale = CONFIGURATION["images_scale"]
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        configuration = CONFIGURATION
    else:
        converter = DocumentConverter(allowed_formats=[getattr(InputFormat, OFFICE[extension])])
        configuration = {"format": OFFICE[extension], "options": "Docling defaults"}

    data = read(fingerprint, store)
    start = time.monotonic()
    result = converter.convert(DocumentStream(name=f"{fingerprint}{extension}", stream=io.BytesIO(data)))
    seconds = round(time.monotonic() - start, 1)
    document = result.document.export_to_dict()
    output = {
        "sha256": _save_json(document, store),
        "derived_from": fingerprint,
        "processor": "docling",
        "version": version("docling"),
        "versions": {p: version(p) for p in ("docling", "docling-core", "docling-parse", "docling-ibm-models")},
        "configuration": configuration,
        "original_format": extension,
        "status": str(result.status.value) if hasattr(result.status, "value") else str(result.status),
        "processed_at": _now(),
        "seconds": seconds,
        "pages": len(document.get("pages", {})),
    }
    if extension in WITHOUT_PAGES:
        markdown = result.document.export_to_markdown().encode("utf-8")
        output["markdown"] = {
            "sha256": save(markdown, store)[0],
            "derived_from": output["sha256"],
            "processor": "docling export_to_markdown",
            "format": "text/markdown",
            "lines": markdown.decode("utf-8").count("\n") + 1,
        }
    return output


def _process_html(fingerprint: str, store: Path) -> dict:
    from markitdown import MarkItDown, StreamInfo

    data = read(fingerprint, store)
    start = time.monotonic()
    result = MarkItDown(enable_plugins=False).convert_stream(
        io.BytesIO(data), stream_info=StreamInfo(extension=".html", mimetype="text/html")
    )
    seconds = round(time.monotonic() - start, 1)
    markdown = result.text_content.encode("utf-8")
    sha, _ = save(markdown, store)
    return {
        "sha256": None,
        "derived_from": fingerprint,
        "processor": "markitdown",
        "version": version("markitdown"),
        "configuration": {"enable_plugins": False},
        "original_format": ".html",
        "status": "success",
        "processed_at": _now(),
        "seconds": seconds,
        "pages": 0,
        "markdown": {
            "sha256": sha,
            "derived_from": fingerprint,
            "processor": "markitdown",
            "format": "text/markdown",
            "lines": markdown.decode("utf-8").count("\n") + 1,
        },
    }
