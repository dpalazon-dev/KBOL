"""Contraste de una estructura con un segundo extractor del mismo PDF, para documentos sin versión del editor.

Sin un texto de referencia publicado, lo que se puede medir es el acuerdo entre dos lecturas independientes de la
capa de texto: la de Docling, ya segmentada en `estructura-v1`, y la de pypdf, página a página. Por página se mide
en los dos sentidos: qué parte de lo que lee pypdf está en la estructura (`recuerdo`: lo que Docling pudo perder) y
qué parte de la estructura está en lo que lee pypdf (`respaldo`: texto que no está en el PDF, o que está lejos de
su página). Las cifras se miran aparte y una a una, porque un porcentaje alto no compensa un número perdido.

El respaldo de una página se busca en ella y en sus dos vecinas, porque un párrafo partido entre páginas está entero
en las dos unidades: por eso no detecta un texto colocado en la página contigua a la suya. La comparación se hace por
tramos de letras seguidas dentro de cada línea, sin espacios, para que no dependa de cómo parte las palabras ni de
en qué orden lee los bloques cada lector. No es una medida de verdad: los dos extractores leen la misma capa de
texto y comparten sus errores, no mide el orden de lectura ni el sentido, y una página sin capa de texto (escaneada)
no se puede medir y se declara aparte.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .almacen import leer

UMBRAL = 0.98
_TRAMO = 6
_PALABRA = re.compile(r"[^\W_]+")
_CIFRA = re.compile(r"\d+(?:[.,]\d+)*")
_MOBILIARIO = {"page_header", "page_footer"}


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto).replace("­", "").lower()
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)


def _pegado(texto: str) -> str:
    return "".join(_PALABRA.findall(_norm(texto)))


def _cubierto(referencia: str, extraido: str) -> tuple[int, int]:
    """(hallados, total) de los tramos de `_TRAMO` letras o cifras seguidas de cada línea de la referencia.

    Los tramos se toman sin espacios ni puntuación, así que no importa cómo parta o una las palabras cada lector, y
    dentro de una línea, así que tampoco importa en qué orden lea cada uno los bloques. Cuenta apariciones: un
    párrafo que la referencia tiene dos veces y lo extraído una sola queda cubierto a medias.
    """
    destino = _pegado(extraido)
    disponibles = Counter(destino[i : i + _TRAMO] for i in range(len(destino) - _TRAMO + 1))
    hallados = total = 0
    for linea in referencia.splitlines():
        pegada = _pegado(linea)
        if not pegada:
            continue
        if len(pegada) < _TRAMO:
            total += 1
            hallados += pegada in destino
            continue
        for i in range(len(pegada) - _TRAMO + 1):
            tramo = pegada[i : i + _TRAMO]
            total += 1
            if disponibles[tramo] > 0:
                disponibles[tramo] -= 1
                hallados += 1
    return hallados, total


def cobertura(referencia: str, extraido: str) -> float:
    """Fracción de la referencia que está en lo extraído; 1.0 si la referencia no tiene texto."""
    hallados, total = _cubierto(referencia, extraido)
    return 1.0 if total == 0 else hallados / total


def cifras(texto: str) -> set[str]:
    return set(_CIFRA.findall(_norm(texto)))


def cifras_que_faltan(referencia: str, extraido: str) -> list[str]:
    """Cifras de la referencia que no están en lo extraído; una de cuatro o más caracteres vale también pegada a otra."""
    presentes = cifras(extraido)
    pegado = re.sub(r"\s+", "", _norm(extraido))
    return sorted(c for c in cifras(referencia) - presentes if len(c) < 4 or c not in pegado)


def texto_por_pagina(datos: bytes) -> dict[int, str]:
    import io

    import pypdf

    lector = pypdf.PdfReader(io.BytesIO(datos))
    return {i: (p.extract_text() or "") for i, p in enumerate(lector.pages, start=1)}


def mobiliario_por_pagina(doc: dict) -> dict[int, str]:
    """Texto de las cabeceras y pies de cada página del DoclingDocument: está en el PDF y no en la estructura."""
    salida: dict[int, list[str]] = {}
    for item in doc.get("texts", []):
        if item.get("label") in _MOBILIARIO and item.get("prov"):
            salida.setdefault(item["prov"][0]["page_no"], []).append(item.get("text") or "")
    return {p: "\n".join(t) for p, t in salida.items()}


def contrastar(estructura: dict, base: dict[int, str], mobiliario: dict[int, str] | None = None) -> dict:
    mobiliario = mobiliario or {}
    cuerpo: dict[int, list[str]] = {}
    for u in estructura["unidades"]:
        if u.get("nivel", 0) == 0:
            for p in u["paginas"]:
                cuerpo.setdefault(p, []).append(u["texto"])
    paginas, fallos = [], []
    recuerdo_total, respaldo_total = [0, 0], [0, 0]
    for pagina in sorted(p["p"] for p in estructura["paginas"]):
        referencia = base.get(pagina, "")
        extraido = "\n".join(cuerpo.get(pagina, []))
        con_mobiliario = extraido + "\n" + mobiliario.get(pagina, "")
        # Un párrafo partido entre páginas está entero en las dos unidades: se respalda con las páginas vecinas.
        vecinas = "\n".join(base.get(p, "") for p in (pagina - 1, pagina, pagina + 1))
        recuerdo, respaldo = _cubierto(referencia, con_mobiliario), _cubierto(extraido, vecinas)
        for acumulado, (hallados, total) in ((recuerdo_total, recuerdo), (respaldo_total, respaldo)):
            acumulado[0] += hallados
            acumulado[1] += total
        fila = {
            "p": pagina,
            "caracteres_base": len(_pegado(referencia)),
            "caracteres_estructura": len(_pegado(extraido)),
            "recuerdo": round(recuerdo[0] / recuerdo[1], 4) if recuerdo[1] else 1.0,
            "respaldo": round(respaldo[0] / respaldo[1], 4) if respaldo[1] else 1.0,
            "cifras_ausentes": cifras_que_faltan(referencia, con_mobiliario),
            "cifras_sin_respaldo": cifras_que_faltan(extraido, vecinas),
        }
        if not fila["caracteres_base"]:
            fila["sin_capa_de_texto"] = True
        paginas.append(fila)
        if (
            fila.get("sin_capa_de_texto")
            or fila["recuerdo"] < UMBRAL
            or fila["respaldo"] < UMBRAL
            or fila["cifras_ausentes"]
            or fila["cifras_sin_respaldo"]
        ):
            fallos.append(fila)
    tablas = []
    for u in estructura["unidades"]:
        if ";tabla=" in u["clave"]:
            respaldo = "\n".join(base.get(p, "") for p in u["paginas"])
            tablas.append(
                {
                    "clave": u["clave"],
                    "paginas": u["paginas"],
                    "cifras": len(cifras(u["texto"])),
                    "cifras_sin_respaldo": cifras_que_faltan(u["texto"], respaldo),
                }
            )
    resumen = {
        "paginas": len(paginas),
        "paginas_sin_capa_de_texto": [f["p"] for f in paginas if f.get("sin_capa_de_texto")],
        # Suma de las páginas: comparar el documento de una vez contaría dos veces los párrafos partidos.
        "recuerdo_documento": round(recuerdo_total[0] / recuerdo_total[1], 4) if recuerdo_total[1] else 1.0,
        "respaldo_documento": round(respaldo_total[0] / respaldo_total[1], 4) if respaldo_total[1] else 1.0,
        "umbral": UMBRAL,
        "paginas_con_recuerdo_bajo": [f["p"] for f in paginas if f["recuerdo"] < UMBRAL],
        "paginas_con_respaldo_bajo": [f["p"] for f in paginas if f["respaldo"] < UMBRAL],
        "cifras_ausentes": sum(len(f["cifras_ausentes"]) for f in paginas),
        "cifras_sin_respaldo": sum(len(f["cifras_sin_respaldo"]) for f in paginas),
        "tablas": len(tablas),
        "tablas_con_cifras_sin_respaldo": sum(1 for t in tablas if t["cifras_sin_respaldo"]),
    }
    limites = [
        "pypdf y Docling leen la misma capa de texto: un error de esa capa no se detecta",
        "no mide el orden de lectura, la asignación a secciones ni el sentido",
        "el respaldo se busca en la página y sus dos vecinas: no detecta un texto colocado en la página contigua",
        "las tablas se miden por sus cifras, no celda a celda ni por la posición de cada valor",
    ]
    return {"resumen": resumen, "fallos": fallos, "paginas": paginas, "tablas": tablas, "limites": limites}


def contrastar_en_almacen(huella_estructura: str, huella_original: str, almacen: Path) -> dict:
    estructura = json.loads(leer(huella_estructura, almacen))
    mobiliario = None
    if estructura.get("docling_sha256"):
        mobiliario = mobiliario_por_pagina(json.loads(leer(estructura["docling_sha256"], almacen)))
    res = contrastar(estructura, texto_por_pagina(leer(huella_original, almacen)), mobiliario)
    res["entradas"] = {"estructura": huella_estructura, "original": huella_original, "base": "pypdf"}
    return res
