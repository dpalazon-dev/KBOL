"""Localizadores de cita con perfil (`ancla` de `sources`).

Tres perfiles, cada uno con una sola forma escrita:

- ``lines-v1:<ini>-<fin>``: líneas inclusivas desde 1 de un texto UTF-8.
- ``pdf-v1:p=<n>[;r=x0,y0,x1,y1]``: página física desde 1 y región normalizada entre 0 y 1, origen arriba a la
  izquierda, con hasta cuatro decimales. Las coordenadas se guardan como texto para no perder su forma.
- ``norma-v1:<clave>=<valor>;…``: unidad lógica de una norma, con las claves en orden jerárquico.

Una cita puede combinar la parte lógica y la física: ``<norma-v1:…> @ <pdf-v1:…>``. Las anclas del formato heredado
(``l. 66-84 (…)`` y ``L10-L20``) se leen como ``lines-v1`` marcadas como heredadas; cualquier otra forma libre es
inválida. Este módulo solo valida la forma: que la página, la unidad o el texto existan lo comprueba ``kbol.citas``.
"""

import re
from dataclasses import dataclass

CLAVES_NORMA = ("cons", "anx", "parte", "cap", "sec", "art", "ap", "pto", "let", "num")

_LINEAS = re.compile(r"lines-v1:(\d+)-(\d+)")
_PDF = re.compile(r"pdf-v1:p=(\d+)(?:;r=([^;]+))?")
_COORD = re.compile(r"(?:0|1)(?:\.\d{1,4})?")
_VALOR = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ.]+")
_HEREDADA = re.compile(r"(?:l\.\s*(\d+)(?:\s*-\s*(\d+))?(?:\s*\(.*\))?|L(\d+)-L(\d+))")


class LocalizadorInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Lineas:
    inicio: int
    fin: int


@dataclass(frozen=True)
class Pagina:
    p: int
    region: tuple[str, str, str, str] | None


@dataclass(frozen=True)
class Norma:
    partes: tuple[tuple[str, str], ...]

    def clave(self) -> str:
        return ";".join(f"{k}={v}" for k, v in self.partes)


@dataclass(frozen=True)
class Cita:
    logico: Norma | None
    fisico: Lineas | Pagina | None
    heredada: bool = False


def _lineas(ini: str, fin: str) -> Lineas:
    a, b = int(ini), int(fin)
    if a < 1 or b < a:
        raise LocalizadorInvalido(f"rango de líneas inválido: {ini}-{fin}")
    return Lineas(a, b)


def _pagina(texto: str) -> Pagina:
    m = _PDF.fullmatch(texto)
    if not m:
        raise LocalizadorInvalido(f"selector pdf-v1 mal formado: {texto!r}")
    p = int(m.group(1))
    if p < 1:
        raise LocalizadorInvalido("la página física empieza en 1")
    if m.group(2) is None:
        return Pagina(p, None)
    coords = m.group(2).split(",")
    if len(coords) != 4 or not all(_COORD.fullmatch(c) for c in coords):
        raise LocalizadorInvalido(f"región inválida: {m.group(2)!r} (cuatro valores entre 0 y 1, hasta 4 decimales)")
    x0, y0, x1, y1 = (float(c) for c in coords)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise LocalizadorInvalido(f"región inválida: {m.group(2)!r} (x0 < x1 y y0 < y1 dentro de 0-1)")
    return Pagina(p, tuple(coords))


def _norma(texto: str) -> Norma:
    cuerpo = texto[len("norma-v1:") :]
    partes = []
    ultimo = -1
    for trozo in cuerpo.split(";"):
        clave, sep, valor = trozo.partition("=")
        if not sep or not _VALOR.fullmatch(valor):
            raise LocalizadorInvalido(f"parte de norma-v1 mal formada: {trozo!r}")
        if clave not in CLAVES_NORMA:
            raise LocalizadorInvalido(f"clave desconocida en norma-v1: {clave!r}")
        orden = CLAVES_NORMA.index(clave)
        if orden <= ultimo:
            raise LocalizadorInvalido(f"clave fuera de orden o repetida en norma-v1: {clave!r}")
        ultimo = orden
        partes.append((clave, valor))
    return Norma(tuple(partes))


def _simple(texto: str) -> Norma | Lineas | Pagina:
    if texto.startswith("norma-v1:"):
        return _norma(texto)
    if texto.startswith("pdf-v1:"):
        return _pagina(texto)
    m = _LINEAS.fullmatch(texto)
    if m:
        return _lineas(m.group(1), m.group(2))
    raise LocalizadorInvalido(f"localizador sin perfil conocido: {texto!r}")


def parsear(ancla: str) -> Cita:
    """Lee un `ancla`; lanza `LocalizadorInvalido` si no es un localizador de los perfiles ni una forma heredada."""
    texto = (ancla or "").strip()
    if not texto:
        raise LocalizadorInvalido("ancla vacía")
    m = _HEREDADA.fullmatch(texto)
    if m:
        if m.group(1) is not None:
            return Cita(None, _lineas(m.group(1), m.group(2) or m.group(1)), heredada=True)
        return Cita(None, _lineas(m.group(3), m.group(4)), heredada=True)
    trozos = [t.strip() for t in texto.split(" @ ")]
    if len(trozos) > 2:
        raise LocalizadorInvalido("una cita combina como mucho una parte lógica y una física")
    piezas = [_simple(t) for t in trozos]
    if len(piezas) == 1:
        (pieza,) = piezas
        return Cita(pieza, None) if isinstance(pieza, Norma) else Cita(None, pieza)
    logico, fisico = piezas
    if not isinstance(logico, Norma) or not isinstance(fisico, Pagina):
        raise LocalizadorInvalido("la cita combinada es norma-v1 @ pdf-v1")
    return Cita(logico, fisico)


def _formatear_simple(pieza: Norma | Lineas | Pagina) -> str:
    if isinstance(pieza, Norma):
        return "norma-v1:" + pieza.clave()
    if isinstance(pieza, Lineas):
        return f"lines-v1:{pieza.inicio}-{pieza.fin}"
    return f"pdf-v1:p={pieza.p}" + (f";r={','.join(pieza.region)}" if pieza.region else "")


def formatear(cita: Cita) -> str:
    """Forma canónica del localizador; una cita heredada se escribe ya como `lines-v1`."""
    piezas = [p for p in (cita.logico, cita.fisico) if p is not None]
    if not piezas:
        raise LocalizadorInvalido("cita sin localizador")
    return " @ ".join(_formatear_simple(p) for p in piezas)
