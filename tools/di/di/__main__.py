"""Usage: python -m di add ORIGIN [--name N] | project SHA256 --name N | capture | process | structure | fidelity | locate

`add` chains the others for a PDF, a Word file, a spreadsheet, a PowerPoint or an HTML file; with `--name`, it also
generates the navigable folder of the document. The store is KBOL_STORE or $KBOL_STATE/$KBOL_REPOSITORY/store
(without those variables, ~/.kbol/default/store). Each command writes its result as JSON to the output.
"""

import argparse
import json
import sys
from pathlib import Path

from .store import capture, default_store


def main(argv=None):
    p = argparse.ArgumentParser(prog="di")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("add", help="captures, processes, structures and crosschecks a document; with --name, its folder")
    i.add_argument("origin")
    i.add_argument("--name", help="short name of the document folder (usad, cra…)")
    i.add_argument("--destination", help="folder where to create it; by default, documents/ next to the store")
    i.add_argument("--format", help="pdf, docx, pptx, xlsx or html, if the origin does not say; without extension, pdf")
    pj = sub.add_parser("project", help="generates the navigable folder of a document from its structure")
    pj.add_argument("structure_sha256")
    pj.add_argument("--name", required=True)
    pj.add_argument("--destination")
    pj.add_argument("--markdown", help="sha256 of the Markdown of a document without pages, for the lines of each section")
    c = sub.add_parser("capture")
    c.add_argument("origin")
    c.add_argument("--media-type")
    pr = sub.add_parser("process")
    pr.add_argument("sha256")
    pr.add_argument("--format", default=".pdf", help=".pdf, .docx, .pptx, .xlsx or .html")
    e = sub.add_parser("structure")
    e.add_argument("docling_sha256")
    e.add_argument("--original", required=True)
    e.add_argument("--profile", choices=["norm", "generic"], default="norm")
    e.add_argument("--reorder", action="store_true", help="norm profile: corrects Docling's reading order")
    e.add_argument(
        "--no-correct",
        action="store_true",
        help="generic profile: without correcting the order, the labels or the section of tables and figures",
    )
    f = sub.add_parser("fidelity")
    f.add_argument("structure_sha256")
    f.add_argument("--editor", help="sha256 of the EUR-Lex HTML or the BOE XML; without it, crosscheck with pypdf")
    f.add_argument("--type", choices=["eurlex", "boe"])
    f.add_argument("--original", required=True)
    lo = sub.add_parser("locate")
    lo.add_argument("docling_sha256")
    lo.add_argument("literal")
    a = p.parse_args(argv)
    store = default_store()
    if a.command == "add":
        from .add import add

        res = add(a.origin, store, name=a.name, destination=Path(a.destination) if a.destination else None,
                  fmt=a.format)
    elif a.command == "project":
        from .project import project_in_store
        from .store import read

        markdown = read(a.markdown, store).decode("utf-8") if a.markdown else None
        res = project_in_store(a.structure_sha256, a.name, store, Path(a.destination) if a.destination else None,
                               markdown=markdown, markdown_sha256=a.markdown)
    elif a.command == "capture":
        res = capture(a.origin, store, media_type=a.media_type)
    elif a.command == "process":
        from .process import process

        res = process(a.sha256, store, a.format)
    elif a.command == "structure":
        if a.profile == "generic":
            if a.reorder:
                p.error("--reorder belongs to the norm profile; the generic one corrects the order unless --no-correct")
            from .generic import generic_in_store

            res = generic_in_store(a.docling_sha256, a.original, store, correct=not a.no_correct)
        else:
            if a.no_correct:
                p.error("--no-correct belongs to the generic profile; the norm one does not correct the order unless --reorder")
            from .structure import structure_in_store

            res = structure_in_store(a.docling_sha256, a.original, store, reorder=a.reorder)
    elif a.command == "locate":
        from .locate import locate_in_store

        res = locate_in_store(a.docling_sha256, a.literal, store)
    elif a.editor:
        if not a.type:
            p.error("--editor needs --type eurlex or boe")
        from .fidelity import measure_in_store

        res = measure_in_store(a.structure_sha256, a.editor, a.type, a.original, store)
    else:
        if a.type:
            p.error("--type goes with --editor; without an editor the crosscheck is with pypdf")
        from .crosscheck import crosscheck_in_store

        res = crosscheck_in_store(a.structure_sha256, a.original, store)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
