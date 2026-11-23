"""Procesado de un original del almacén, en local y en CPU: Docling para PDF y ofimática, MarkItDown para HTML.

La salida es el JSON nativo de DoclingDocument (`export_to_dict`), serializado de forma determinista y guardado en
el mismo almacén. Un documento sin páginas (Word, hoja de cálculo) se cita por líneas, así que se guarda además su
exportación a Markdown, que es la representación de texto que resuelve `kbol citas`. Un HTML no pasa por Docling:
MarkItDown lo convierte a Markdown y esa es su única representación.

La ejecución devuelve lo que necesita la fuente derivada: procesador, versiones exactas, configuración y tiempo.
Que el proceso termine no dice nada de su fidelidad: eso lo miden `di.fidelidad` y `di.contraste`.
"""

import io
import json
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from .almacen import guardar, leer

# Las figuras se exportan como imagen (a doble resolución) para que la carpeta del documento las tenga. Las cuatro
# normas del primer piloto se procesaron sin ellas: su configuración era la anterior, sin las dos últimas claves.
CONFIGURACION = {
    "do_ocr": False,
    "do_table_structure": True,
    "table_mode": "accurate",
    "device": "cpu",
    "generate_picture_images": True,
    "images_scale": 2.0,
}
OFIMATICA = {".docx": "DOCX", ".pptx": "PPTX", ".xlsx": "XLSX"}
SIN_PAGINAS = {".docx", ".xlsx"}
HTML = {".html", ".htm"}
FORMATOS = {".pdf", *OFIMATICA, *HTML}


def _ahora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _guardar_json(documento: dict, almacen: Path) -> str:
    salida = json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return guardar(salida, almacen)[0]


def procesar(huella: str, almacen: Path, extension: str = ".pdf") -> dict:
    extension = extension.lower()
    if extension not in FORMATOS:
        raise ValueError(f"formato no admitido: {extension} (admitidos: {', '.join(sorted(FORMATOS))})")
    if extension in HTML:
        return _procesar_html(huella, almacen)
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if extension == ".pdf":
        opciones = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
        opciones.table_structure_options.mode = TableFormerMode.ACCURATE
        opciones.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
        opciones.generate_picture_images = CONFIGURACION["generate_picture_images"]
        opciones.images_scale = CONFIGURACION["images_scale"]
        conversor = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opciones)})
        configuracion = CONFIGURACION
    else:
        conversor = DocumentConverter(allowed_formats=[getattr(InputFormat, OFIMATICA[extension])])
        configuracion = {"formato": OFIMATICA[extension], "opciones": "las de Docling por defecto"}

    datos = leer(huella, almacen)
    inicio = time.monotonic()
    resultado = conversor.convert(DocumentStream(name=f"{huella}{extension}", stream=io.BytesIO(datos)))
    segundos = round(time.monotonic() - inicio, 1)
    documento = resultado.document.export_to_dict()
    salida = {
        "sha256": _guardar_json(documento, almacen),
        "derivada_de": huella,
        "procesador": "docling",
        "version": version("docling"),
        "versiones": {p: version(p) for p in ("docling", "docling-core", "docling-parse", "docling-ibm-models")},
        "configuracion": configuracion,
        "formato_original": extension,
        "estado": str(resultado.status.value) if hasattr(resultado.status, "value") else str(resultado.status),
        "procesado_en": _ahora(),
        "segundos": segundos,
        "paginas": len(documento.get("pages", {})),
    }
    if extension in SIN_PAGINAS:
        markdown = resultado.document.export_to_markdown().encode("utf-8")
        salida["markdown"] = {
            "sha256": guardar(markdown, almacen)[0],
            "derivada_de": salida["sha256"],
            "procesador": "docling export_to_markdown",
            "formato": "text/markdown",
            "lineas": markdown.decode("utf-8").count("\n") + 1,
        }
    return salida


def _procesar_html(huella: str, almacen: Path) -> dict:
    from markitdown import MarkItDown, StreamInfo

    datos = leer(huella, almacen)
    inicio = time.monotonic()
    resultado = MarkItDown(enable_plugins=False).convert_stream(
        io.BytesIO(datos), stream_info=StreamInfo(extension=".html", mimetype="text/html")
    )
    segundos = round(time.monotonic() - inicio, 1)
    markdown = resultado.text_content.encode("utf-8")
    sha, _ = guardar(markdown, almacen)
    return {
        "sha256": None,
        "derivada_de": huella,
        "procesador": "markitdown",
        "version": version("markitdown"),
        "configuracion": {"enable_plugins": False},
        "formato_original": ".html",
        "estado": "success",
        "procesado_en": _ahora(),
        "segundos": segundos,
        "paginas": 0,
        "markdown": {
            "sha256": sha,
            "derivada_de": huella,
            "procesador": "markitdown",
            "formato": "text/markdown",
            "lineas": markdown.decode("utf-8").count("\n") + 1,
        },
    }
