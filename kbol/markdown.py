"""Marcas de cláusula y de afirmación del contrato concreto.

`<clausula id="C1">` abre una cláusula en una línea propia y `</clausula>` la cierra en otra; no se anidan y el
identificador es único. `<hecho id="H1" evidencia="…" fuente="…">…</hecho>` marca una afirmación en línea y
`<hecho ref="HE-…">…</hecho>` cita un registro de hecho. Las marcas dentro de bloques de código, de código en línea o
escapadas con barra inversa no se interpretan.
"""

import re

from .modelo import ANCLA

_APERTURA = re.compile(rf'^<clausula id="({ANCLA})">$')
_CIERRE = "</clausula>"
_MARCA = re.compile(r"^\s*</?clausula\b")
_HECHO = re.compile(r"(?<!\\)<hecho\b([^>]*)>(.*?)(?<!\\)</hecho>", re.S)
_APERTURA_HECHO = re.compile(r"(?<!\\)<hecho\b")
_ATRIBUTO = re.compile(r'\s+([a-z_]+)="([^"]*)"')
_CODIGO_EN_LINEA = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_PARRAFO = re.compile(r"(\n[ \t]*\n)")
_ID_HECHO = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(?!\n)$")


class ErrorDeMarca(ValueError):
    """Marca de cláusula o de afirmación mal formada."""


def _lineas_de_codigo(cuerpo):
    from markdown_it import MarkdownIt  # al usarlo: importarlo cuesta lo que una orden entera

    excluidas = set()
    for token in MarkdownIt().parse(cuerpo):
        if token.type in ("fence", "code_block") and token.map:
            excluidas.update(range(*token.map))
    return excluidas


def _texto_sin_codigo(cuerpo):
    excluidas = _lineas_de_codigo(cuerpo)
    lineas = ["" if i in excluidas else linea for i, linea in enumerate(cuerpo.split("\n"))]
    # El código en línea no cruza una línea en blanco: se busca párrafo a párrafo.
    trozos = _PARRAFO.split("\n".join(lineas))
    return "".join(
        t if i % 2 else _CODIGO_EN_LINEA.sub(lambda m: " " * len(m.group(0)), t) for i, t in enumerate(trozos)
    )


def clausulas(cuerpo):
    """{ancla: texto} en orden de aparición."""
    lineas = cuerpo.replace("\r\n", "\n").split("\n")
    excluidas = _lineas_de_codigo("\n".join(lineas))
    encontradas, actual, inicio = {}, None, 0
    for i, linea in enumerate(lineas):
        if i in excluidas:
            continue
        m = _APERTURA.match(linea)
        if m:
            ancla = m.group(1)
            if actual is not None:
                raise ErrorDeMarca(f"línea {i + 1}: cláusula anidada en {actual}")
            if ancla in encontradas:
                raise ErrorDeMarca(f"línea {i + 1}: cláusula repetida {ancla}")
            actual, inicio = ancla, i + 1
        elif linea == _CIERRE:
            if actual is None:
                raise ErrorDeMarca(f"línea {i + 1}: cierre sin apertura")
            encontradas[actual] = "\n".join(lineas[inicio:i]).strip("\n")
            actual = None
        elif _MARCA.match(linea):
            raise ErrorDeMarca(f"línea {i + 1}: marca de cláusula mal formada")
    if actual is not None:
        raise ErrorDeMarca(f"cláusula {actual} sin cierre")
    return encontradas


def _atributos(texto):
    pos, atributos = 0, {}
    for m in _ATRIBUTO.finditer(texto):
        if m.start() != pos or m.group(1) in atributos:
            raise ErrorDeMarca(f"atributos de hecho mal formados: {texto!r}")
        atributos[m.group(1)] = m.group(2)
        pos = m.end()
    if texto[pos:].strip():
        raise ErrorDeMarca(f"atributos de hecho mal formados: {texto!r}")
    return atributos


def hechos(cuerpo):
    """Afirmaciones marcadas, en orden. Valida su forma; evidencia y fuente las valida el esquema."""
    texto = _texto_sin_codigo(cuerpo)
    resultado, vistos, consumido = [], set(), 0
    for m in _HECHO.finditer(texto):
        if _APERTURA_HECHO.search(texto, consumido, m.start()):
            raise ErrorDeMarca("marca de hecho sin cierre")
        interior = m.group(2)
        if _APERTURA_HECHO.search(interior):
            raise ErrorDeMarca("marcas de hecho anidadas")
        atributos = _atributos(m.group(1))
        if set(atributos) == {"ref"}:
            resultado.append({"ref": atributos["ref"], "texto": interior})
        elif set(atributos) == {"id", "evidencia", "fuente"}:
            if not _ID_HECHO.match(atributos["id"]) or atributos["id"] in vistos:
                raise ErrorDeMarca(f"identificador de hecho inválido o repetido: {atributos['id']}")
            vistos.add(atributos["id"])
            resultado.append({**atributos, "texto": interior})
        else:
            raise ErrorDeMarca(f"un hecho lleva id, evidencia y fuente, o solo ref: {sorted(atributos)}")
        consumido = m.end()
    if _APERTURA_HECHO.search(texto, consumido):
        raise ErrorDeMarca("marca de hecho sin cierre")
    return resultado
