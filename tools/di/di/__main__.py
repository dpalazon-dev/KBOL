"""Uso: python -m di incorporar ORIGEN [--nombre N] | proyectar HUELLA --nombre N | capturar | procesar | estructura | fidelidad | localizar

`incorporar` encadena las demás para un PDF, un Word, una hoja de cálculo, un PowerPoint o un HTML; con
`--nombre`, genera además la carpeta navegable del documento. El almacén es KBOL_ALMACEN o
$KBOL_ESTADO/$KBOL_REPOSITORIO/almacen (sin esas variables, ~/.kbol/predeterminado/almacen). Cada orden escribe su resultado como JSON en la salida.
"""

import argparse
import json
import sys
from pathlib import Path

from .almacen import almacen_por_defecto, capturar


def main(argv=None):
    p = argparse.ArgumentParser(prog="di")
    sub = p.add_subparsers(dest="orden", required=True)
    i = sub.add_parser("incorporar", help="captura, procesa, estructura y contrasta un documento; con --nombre, su carpeta")
    i.add_argument("origen")
    i.add_argument("--nombre", help="nombre corto de la carpeta del documento (usad, cra…)")
    i.add_argument("--destino", help="carpeta donde crearla; por defecto, documentos/ junto al almacén")
    i.add_argument("--formato", help="pdf, docx, pptx, xlsx o html, si el origen no lo dice; sin extensión, pdf")
    py = sub.add_parser("proyectar", help="genera la carpeta navegable de un documento desde su estructura")
    py.add_argument("huella_estructura")
    py.add_argument("--nombre", required=True)
    py.add_argument("--destino")
    py.add_argument("--markdown", help="huella del Markdown de un documento sin páginas, para las líneas de cada sección")
    c = sub.add_parser("capturar")
    c.add_argument("origen")
    c.add_argument("--medio")
    pr = sub.add_parser("procesar")
    pr.add_argument("huella")
    pr.add_argument("--formato", default=".pdf", help=".pdf, .docx, .pptx, .xlsx o .html")
    e = sub.add_parser("estructura")
    e.add_argument("huella_docling")
    e.add_argument("--original", required=True)
    e.add_argument("--perfil", choices=["norma", "generica"], default="norma")
    e.add_argument("--ordenar", action="store_true", help="perfil norma: corrige el orden de lectura de Docling")
    e.add_argument(
        "--sin-corregir",
        action="store_true",
        help="perfil genérica: sin corregir el orden, los rótulos ni la sección de tablas y figuras",
    )
    f = sub.add_parser("fidelidad")
    f.add_argument("huella_estructura")
    f.add_argument("--editor", help="huella del HTML de EUR-Lex o del XML del BOE; sin ella, contraste con pypdf")
    f.add_argument("--tipo", choices=["eurlex", "boe"])
    f.add_argument("--original", required=True)
    lo = sub.add_parser("localizar")
    lo.add_argument("huella_docling")
    lo.add_argument("literal")
    a = p.parse_args(argv)
    almacen = almacen_por_defecto()
    if a.orden == "incorporar":
        from .incorporar import incorporar

        res = incorporar(a.origen, almacen, nombre=a.nombre, destino=Path(a.destino) if a.destino else None,
                         formato=a.formato)
    elif a.orden == "proyectar":
        from .almacen import leer
        from .proyectar import proyectar_en_almacen

        markdown = leer(a.markdown, almacen).decode("utf-8") if a.markdown else None
        res = proyectar_en_almacen(a.huella_estructura, a.nombre, almacen, Path(a.destino) if a.destino else None,
                                   markdown=markdown, markdown_sha256=a.markdown)
    elif a.orden == "capturar":
        res = capturar(a.origen, almacen, medio=a.medio)
    elif a.orden == "procesar":
        from .procesar import procesar

        res = procesar(a.huella, almacen, a.formato)
    elif a.orden == "estructura":
        if a.perfil == "generica":
            if a.ordenar:
                p.error("--ordenar es del perfil norma; el genérico corrige el orden salvo con --sin-corregir")
            from .generica import generica_en_almacen

            res = generica_en_almacen(a.huella_docling, a.original, almacen, corregir=not a.sin_corregir)
        else:
            if a.sin_corregir:
                p.error("--sin-corregir es del perfil genérica; el de normas no corrige el orden salvo con --ordenar")
            from .estructura import estructura_en_almacen

            res = estructura_en_almacen(a.huella_docling, a.original, almacen, ordenar=a.ordenar)
    elif a.orden == "localizar":
        from .localizar import localizar_en_almacen

        res = localizar_en_almacen(a.huella_docling, a.literal, almacen)
    elif a.editor:
        if not a.tipo:
            p.error("--editor necesita --tipo eurlex o boe")
        from .fidelidad import medir_en_almacen

        res = medir_en_almacen(a.huella_estructura, a.editor, a.tipo, a.original, almacen)
    else:
        if a.tipo:
            p.error("--tipo acompaña a --editor; sin editor se contrasta con pypdf")
        from .contraste import contrastar_en_almacen

        res = contrastar_en_almacen(a.huella_estructura, a.original, almacen)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
