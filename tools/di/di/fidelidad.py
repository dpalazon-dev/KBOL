"""Fidelidad de una estructura extraída del PDF frente a la versión estructurada del editor.

Mide por unidad de norma (clave `norma-v1`): si la unidad existe y es única, cuánto de su texto conserva (recuerdo
de palabras), si conserva sus fechas y si conserva sus negaciones y excepciones. Mide además el orden de los
artículos y, para el documento entero, el recuerdo de palabras y las palabras partidas, que comparan Docling con la
línea base de pypdf. Una cifra global no compensa una negación perdida en una unidad: el informe lista cada fallo.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .almacen import leer
from .editor import unidades_editor_boe, unidades_editor_eurlex

TERMINOS = ("no", "salvo", "excepto", "sin perjuicio", "no obstante", "cuando proceda", "a menos que", "ni")
_FECHA = re.compile(
    r"\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+\d{4}\b|\b\d{1,2}\.\d{1,2}\.\d{4}\b"
)
_PALABRA = re.compile(r"[0-9a-záéíóúüñ]+")


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto).replace("­", "").lower()
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    return re.sub(r"\s+", " ", t)


def palabras(texto: str) -> Counter:
    return Counter(_PALABRA.findall(_norm(texto)))


def recuerdo(referencia: str, extraido: str) -> float:
    ref, ext = palabras(referencia), palabras(extraido)
    total = sum(ref.values())
    return 1.0 if total == 0 else sum((ref & ext).values()) / total


def fechas(texto: str) -> set[str]:
    return set(_FECHA.findall(_norm(texto)))


def terminos(texto: str) -> dict[str, int]:
    t = f" {_norm(texto)} "
    return {term: len(re.findall(rf"(?<![0-9a-záéíóúüñ]){re.escape(term)}(?![0-9a-záéíóúüñ])", t)) for term in TERMINOS}


def partidas(referencia: str, extraido: str) -> int:
    """Palabras del editor que faltan en la extracción pero aparecen al unir dos trozos consecutivos de ella."""
    ref = set(palabras(referencia))
    trozos = _PALABRA.findall(_norm(extraido))
    presentes = set(trozos)
    unidas = {a + b for a, b in zip(trozos, trozos[1:], strict=False)}
    return sum(1 for w in ref - presentes if w in unidas)


def _orden(claves: list[str]) -> float:
    """Fracción de artículos en orden creciente (subsecuencia creciente más larga sobre su número)."""
    nums = [int(c[4:]) for c in claves if re.fullmatch(r"art=\d+", c)]
    if not nums:
        return 1.0
    colas: list[int] = []
    for n in nums:
        i = next((j for j, v in enumerate(colas) if v >= n), len(colas))
        colas[i : i + 1] = [n]
    return len(colas) / len(nums)


def medir(estructura: dict, editor: dict[str, str], texto_base: str | None = None) -> dict:
    por_clave: dict[str, list[dict]] = {}
    for u in estructura["unidades"]:
        por_clave.setdefault(u["clave"], []).append(u)
    filas, fallos = [], []
    for clave, ref in editor.items():
        candidatas = por_clave.get(clave, [])
        fila = {
            "clave": clave,
            "estado": "ausente" if not candidatas else ("ambigua" if len(candidatas) > 1 else "unica"),
        }
        if len(candidatas) == 1:
            ext = candidatas[0]["texto"]
            fila["recuerdo"] = round(recuerdo(ref, ext), 4)
            fila["fechas_perdidas"] = sorted(fechas(ref) - fechas(ext))
            t_ref, t_ext = terminos(ref), terminos(ext)
            fila["terminos_distintos"] = {k: [t_ref[k], t_ext[k]] for k in TERMINOS if t_ref[k] != t_ext[k]}
            if fila["fechas_perdidas"] or fila["terminos_distintos"] or fila["recuerdo"] < 0.98:
                fallos.append(fila)
        else:
            fallos.append(fila)
        filas.append(fila)
    texto_editor = "\n".join(v for k, v in editor.items() if ";" not in k)
    texto_docling = "\n".join(u["texto"] for u in estructura["unidades"] if u.get("nivel", 0) == 0)
    unicas = [f for f in filas if f["estado"] == "unica"]
    resumen = {
        "unidades_editor": len(editor),
        "encontradas_unicas": len(unicas),
        "ausentes": sum(1 for f in filas if f["estado"] == "ausente"),
        "ambiguas": sum(1 for f in filas if f["estado"] == "ambigua"),
        "con_fechas_perdidas": sum(1 for f in unicas if f["fechas_perdidas"]),
        "con_terminos_distintos": sum(1 for f in unicas if f["terminos_distintos"]),
        "recuerdo_medio": round(sum(f["recuerdo"] for f in unicas) / len(unicas), 4) if unicas else None,
        "orden_articulos": round(_orden([u["clave"] for u in estructura["unidades"]]), 4),
        "documento": {
            "docling": {
                "recuerdo": round(recuerdo(texto_editor, texto_docling), 4),
                "partidas": partidas(texto_editor, texto_docling),
            },
        },
    }
    if texto_base is not None:
        resumen["documento"]["pypdf"] = {
            "recuerdo": round(recuerdo(texto_editor, texto_base), 4),
            "partidas": partidas(texto_editor, texto_base),
        }
    return {"resumen": resumen, "fallos": fallos, "filas": filas}


def texto_pypdf(datos: bytes) -> str:
    import io

    import pypdf

    lector = pypdf.PdfReader(io.BytesIO(datos))
    return "\n".join(p.extract_text() or "" for p in lector.pages)


def medir_en_almacen(
    huella_estructura: str, huella_editor: str, tipo: str, huella_original: str, almacen: Path
) -> dict:
    estructura = json.loads(leer(huella_estructura, almacen))
    documento = leer(huella_editor, almacen).decode("utf-8")
    editor = unidades_editor_eurlex(documento) if tipo == "eurlex" else unidades_editor_boe(documento)
    res = medir(estructura, editor, texto_pypdf(leer(huella_original, almacen)))
    res["entradas"] = {
        "estructura": huella_estructura,
        "editor": huella_editor,
        "tipo": tipo,
        "original": huella_original,
    }
    return res
