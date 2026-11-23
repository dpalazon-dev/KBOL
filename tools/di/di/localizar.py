"""Página y región exactas de una cita literal en un DoclingDocument, para escribir el `pdf-v1` de una cita.

Busca la cita normalizada en cada texto y celda de tabla del cuerpo; si no está en un solo elemento, prueba en
ventanas de elementos consecutivos (una cita que cruza dos párrafos o un salto de página). Devuelve una región por
página, envolvente de los elementos que la contienen. No decide qué cita es la buena: si hay varias, las da todas.
"""

import json
import re
import unicodedata
from pathlib import Path

from .almacen import leer
from .estructura import _GLIFO, _IGNORAR, _fmt, _region, _resolver


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto.replace(_GLIFO, " ")).replace("­", "").lower()
    t = t.translate(str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"'}))
    return re.sub(r"\s+", "", t)


def _piezas(doc: dict) -> list[tuple[str, list]]:
    piezas = []

    def visitar(nodo):
        for hijo in nodo.get("children", []):
            item = _resolver(doc, hijo["$ref"])
            if item.get("label") == "table":
                pagina = item["prov"][0]["page_no"]
                for fila in item["data"]["grid"]:
                    for c in fila:
                        if c.get("text") and c.get("bbox"):
                            piezas.append((c["text"], [(pagina, c["bbox"])]))
                continue
            if item.get("label") not in _IGNORAR and item.get("text"):
                marcador = (item.get("marker") or "").strip()
                piezas.append((f"{marcador} {item['text']}", [(p["page_no"], p["bbox"]) for p in item.get("prov", [])]))
            visitar(item)

    visitar(doc["body"])
    return piezas


def localizar(doc: dict, literal: str, ventana: int = 3) -> list[dict]:
    objetivo = _norm(literal)
    piezas = _piezas(doc)
    for ancho in range(1, ventana + 1):
        hallazgos = []
        for i in range(len(piezas) - ancho + 1):
            grupo = piezas[i : i + ancho]
            if objetivo in _norm("".join(t for t, _ in grupo)):
                por_pagina: dict[int, list] = {}
                for _, cajas in grupo:
                    for pagina, caja in cajas:
                        tam = doc["pages"][str(pagina)]["size"]
                        por_pagina.setdefault(pagina, []).append(_region(caja, tam["width"], tam["height"]))
                hallazgos.append(
                    [
                        {
                            "p": p,
                            "r": [_fmt(min(r[0] for r in rs)), _fmt(min(r[1] for r in rs)), _fmt(max(r[2] for r in rs)), _fmt(max(r[3] for r in rs))],
                        }
                        for p, rs in sorted(por_pagina.items())
                    ]
                )
        if hallazgos:
            return hallazgos
    return []


def localizar_en_almacen(huella_docling: str, literal: str, almacen: Path) -> list:
    return localizar(json.loads(leer(huella_docling, almacen)), literal)
