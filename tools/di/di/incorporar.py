"""Un documento, de origen a representación citable y carpeta navegable, en una sola orden.

Según el formato:

- PDF: captura, Docling (con las figuras como imagen), estructura genérica, contraste con pypdf.
- PowerPoint: lo mismo sin contraste; cada diapositiva es una página y se cita como un PDF.
- Word y hoja de cálculo: Docling, estructura genérica sin páginas y su exportación a Markdown, que es la
  representación que se cita por líneas.
- HTML: MarkItDown a Markdown, que es su única representación; se cita por líneas.

El formato sale de la extensión del origen; `formato` lo declara a mano cuando el origen no la trae o engaña, y
un origen sin extensión ni formato declarado se trata como PDF, como antes de admitir otros formatos.

Con `nombre`, genera además la carpeta del documento (`di.proyectar`). Devuelve lo que necesitan las fichas de
fuente y lo que hay que mirar antes de citar. No escribe registros ni decide nada sobre la calidad.
"""

import json
from pathlib import Path

from .almacen import capturar, guardar, leer
from .contraste import contrastar_en_almacen
from .generica import generica_en_almacen
from .procesar import FORMATOS, HTML, procesar

MEDIOS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
    ".htm": "text/html",
}


def _extension(origen: str | Path) -> str:
    return Path(str(origen).split("?")[0]).suffix.lower()


def _formato(origen: str | Path, formato: str | None) -> str:
    """La extensión que decide el procesado: la declarada, la del origen o, si el origen no trae ninguna, PDF."""
    if formato:
        extension = "." + formato.strip().lower().lstrip(".")
    else:
        # Un origen sin extensión (la URL de un PDF en EUR-Lex) siempre entró como PDF, y así sigue.
        extension = _extension(origen) or ".pdf"
    if extension not in FORMATOS:
        admitidos = ", ".join(sorted(FORMATOS))
        raise ValueError(f"formato no admitido: {extension}; admitidos: {admitidos}. Decláralo con --formato si el origen no lo dice")
    return extension


def incorporar(
    origen: str | Path,
    almacen: Path,
    nombre: str | None = None,
    destino: Path | None = None,
    formato: str | None = None,
) -> dict:
    extension = _formato(origen, formato)
    original = capturar(origen, almacen, medio=MEDIOS[extension])
    procesado = procesar(original["sha256"], almacen, extension)
    salida: dict = {"original": original, "revisar": []}
    if extension in HTML:
        salida["markdown"] = procesado["markdown"]
        salida["procesado"] = {k: v for k, v in procesado.items() if k != "markdown"}
        salida["revisar"].append("HTML convertido con MarkItDown: sin estructura ni carpeta; se cita por líneas del Markdown")
        return salida

    salida["docling"] = {k: v for k, v in procesado.items() if k != "markdown"}
    if "markdown" in procesado:
        salida["markdown"] = procesado["markdown"]
    estructura = generica_en_almacen(procesado["sha256"], original["sha256"], almacen)
    salida["estructura"] = estructura
    if extension == ".pdf":
        informe = contrastar_en_almacen(estructura["sha256"], original["sha256"], almacen)
        datos = json.dumps(informe, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        huella_informe, _ = guardar(datos, almacen)
        resumen = informe["resumen"]
        salida["contraste"] = {"sha256": huella_informe, "resumen": resumen, "limites": informe["limites"]}
        revisar = salida["revisar"]
        if resumen["paginas_sin_capa_de_texto"]:
            revisar.append(f"páginas sin capa de texto, no medibles: {resumen['paginas_sin_capa_de_texto']}")
        if resumen["paginas_con_recuerdo_bajo"]:
            revisar.append(f"páginas donde la estructura pierde texto: {resumen['paginas_con_recuerdo_bajo']}")
        if resumen["paginas_con_respaldo_bajo"]:
            revisar.append(f"páginas con texto que pypdf no ve ahí: {resumen['paginas_con_respaldo_bajo']}")
        if resumen["cifras_ausentes"] or resumen["cifras_sin_respaldo"]:
            paginas = [f["p"] for f in informe["paginas"] if f["cifras_ausentes"] or f["cifras_sin_respaldo"]]
            revisar.append(
                f"cifras: {resumen['cifras_ausentes']} del PDF ausentes de la estructura y "
                f"{resumen['cifras_sin_respaldo']} de la estructura sin respaldo en el PDF, en las páginas {paginas}"
            )
        if estructura["paginas_sin_unidad"]:
            revisar.append(f"páginas sin ninguna unidad: {estructura['paginas_sin_unidad']}")
    else:
        salida["revisar"].append(f"{extension}: sin segunda lectura con la que contrastar; revisa a ojo lo que cites")
    if nombre:
        from .proyectar import proyectar_en_almacen

        markdown = leer(procesado["markdown"]["sha256"], almacen).decode("utf-8") if "markdown" in procesado else None
        salida["carpeta"] = proyectar_en_almacen(
            estructura["sha256"], nombre, almacen, destino, markdown=markdown,
            markdown_sha256=procesado.get("markdown", {}).get("sha256"),
        )
    return salida
