"""Enlaces navegables de los documentos Markdown de un repositorio: rutas, fragmentos y anclas.

Aplica «Instrucciones persistentes, procedimientos y referencias resolubles» del contrato: una referencia que no se
resuelve no es una referencia. Vale para cualquier Markdown del repositorio, sea o no un registro:

- un enlace interno lleva a un archivo o carpeta que existe con esas mismas mayúsculas (Windows no las distingue;
  GitHub y Linux, sí); una ruta que empieza por «/» se lee desde la raíz, como en GitHub;
- un fragmento (`#ancla`) hacia un `.md` existe en el destino, como ancla explícita (`id=` en cualquier etiqueta,
  `name=` en `<a>`) o como el ancla que GitHub deriva de un título; las anclas explícitas no se repiten;
- una ruta absoluta local (`C:/…`) no es un enlace que otro pueda seguir;
- los ejemplos dentro de bloques de código o de código en línea no son enlaces.

No se comprueban los enlaces externos (`https:`, `mailto:`), los destinos fuera de la raíz ni los fragmentos de un
archivo que no es Markdown. El análisis es de Markdown real (markdown-it), no de expresiones regulares sobre líneas.

Lo que existe es lo que git ve en la raíz: los archivos versionados y los nuevos sin ignorar, con las mayúsculas del
índice. La instalación puede declarar en su configuración (`enlaces`) las carpetas que no se revisan (`excluir`:
copias literales de documentos ajenos, cuyos enlaces apuntan a donde estaban) y la deuda (`deuda`: enlaces rotos de
documentos que ya no se reescriben). La deuda no bloquea, y la que deja de fallar se avisa para retirarla.
"""

import collections
import posixpath
import re
import subprocess
import unicodedata
from functools import cache
from pathlib import Path
from urllib.parse import unquote

from .snapshot import entorno_git


@cache
def _md():
    """Analizador CommonMark, importado al usarlo y no al cargar la CLI."""
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark")


_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")  # https:, mailto:; una sola letra sería una unidad de Windows
_UNIDAD = re.compile(r"^[A-Za-z]:[\\/]")
_ETIQUETA = re.compile(r"<([A-Za-z][\w-]*)\b([^>]*)>")
_ATRIBUTO_ID = re.compile(r"""(?<![\w-])id\s*=\s*["']([^"']+)["']""")
_ATRIBUTO_NAME = re.compile(r"""(?<![\w-])name\s*=\s*["']([^"']+)["']""")


def _sin_cabecera(texto):
    """El texto con la cabecera YAML en blanco (conservando las líneas): su «---» final no es un título."""
    lineas = texto.split("\n")
    if lineas and lineas[0].strip() == "---":
        for i in range(1, len(lineas)):
            if lineas[i].strip() == "---":
                return "\n".join([""] * (i + 1) + lineas[i + 1 :])
    return texto


def _tokens(texto):
    return _md().parse(_sin_cabecera(texto))


def slug(titulo):
    """El ancla que GitHub da a un título: en minúsculas, conserva letras, marcas, números, «_», «-» y espacios (que
    pasan a guiones) y quita el resto (puntuación, símbolos, emojis)."""
    conservados = (
        c
        for c in titulo.strip().lower()
        if c in " -" or unicodedata.category(c)[0] in "LMN" or unicodedata.category(c) == "Pc"
    )
    return "".join(conservados).replace(" ", "-")


def _ids_html(html):
    """Las anclas que declara un trozo de HTML: `id=` en cualquier etiqueta y `name=` en `<a>`, una vez por etiqueta."""
    ids = []
    for etiqueta, atributos in _ETIQUETA.findall(html):
        propios = set(_ATRIBUTO_ID.findall(atributos))
        if etiqueta.lower() == "a":
            propios |= set(_ATRIBUTO_NAME.findall(atributos))
        ids += sorted(propios)
    return ids


def anclas(texto):
    """(anclas del documento, anclas explícitas repetidas como (línea, id))."""
    tokens = _tokens(texto)
    vistas = collections.Counter()
    todas, explicitas, repetidas = set(), set(), []

    def explicita(ident, linea):
        if ident in explicitas:
            repetidas.append((linea, ident))
        explicitas.add(ident)
        todas.add(ident)

    for i, t in enumerate(tokens):
        linea = t.map[0] + 1 if t.map else 0
        if t.type == "heading_open":
            hijos = tokens[i + 1].children or []
            base = slug("".join(h.content for h in hijos if h.type in ("text", "code_inline")))
            n = vistas[base]
            vistas[base] += 1
            todas.add(base if n == 0 else f"{base}-{n}")
        elif t.type == "html_block":
            for ident in _ids_html(t.content):
                explicita(ident, linea)
        elif t.type == "inline":
            for h in t.children or []:
                if h.type == "html_inline":
                    for ident in _ids_html(h.content):
                        explicita(ident, linea)
    return todas, repetidas


class _Cursor:
    """Busca, avanzando, dónde aparece cada elemento de un bloque para dar su línea en el orden en que se lee."""

    def __init__(self, lineas, inicio, fin):
        self.lineas, self.fin = lineas, fin
        self.linea, self.columna = inicio, 0

    def buscar(self, candidatos):
        for n in range(self.linea, self.fin):
            desde = self.columna if n == self.linea else 0
            posiciones = [p for c in candidatos if c and (p := self.lineas[n].find(c, desde)) >= 0]
            if posiciones:
                self.linea, self.columna = n, min(posiciones) + 1
                return n + 1
        return self.linea + 1  # no aparece tal cual (escapes, referencias): la línea por la que va el bloque


def enlaces(texto):
    """(línea, destino decodificado) de cada enlace e imagen, fuera de bloques de código y de código en línea."""
    lineas = texto.split("\n")
    encontrados = []
    for t in _tokens(texto):
        if t.type != "inline" or not t.map:
            continue
        cursor = _Cursor(lineas, *t.map)
        for h in t.children or []:
            if h.type == "link_open":
                destino = str(h.attrs.get("href", ""))
            elif h.type == "image":
                destino = str(h.attrs.get("src", ""))
            else:
                continue
            legible = unquote(destino)
            linea = cursor.buscar([f"]({d}" for d in (legible, destino)] + [f"](<{legible}", f"]: {legible}"])
            encontrados.append((linea, legible))
    return encontrados


def _resolver(origen, ruta):
    """La ruta de la raíz a la que lleva un destino: desde la carpeta del documento, o desde la raíz si empieza por
    «/»; sin «?consulta»; «.» es la raíz."""
    ruta = ruta.split("?", 1)[0]
    base = "" if ruta.startswith("/") else posixpath.dirname(origen)
    return posixpath.normpath(posixpath.join(base, ruta.lstrip("/"))).rstrip("/") or "."


def revisar(docs, existentes, leer, deuda=frozenset()):
    """{errores, enlaces, deuda_usada} de los documentos `{ruta: texto}`.

    `existentes` son las rutas de la raíz con sus mayúsculas; `leer` da el texto de un destino (None si no se puede).
    La deuda son pares (documento, destino decodificado) ya rotos, que se cuentan como usados y no como errores.
    """
    carpetas = {"."}
    for ruta in existentes:
        partes = ruta.split("/")[:-1]
        carpetas.update("/".join(partes[: i + 1]) for i in range(len(partes)))
    escritas = {r.lower(): r for r in existentes | carpetas}
    cache, errores, usada, total = {}, [], set(), 0

    def anotar(origen, linea, destino, mensaje):
        if (origen, destino) in deuda:
            usada.add((origen, destino))
        else:
            errores.append({"ruta": origen, "linea": linea, "destino": destino, "mensaje": mensaje})

    def anclas_de(ruta):
        if ruta not in cache:
            texto = leer(ruta)
            if texto is None:
                return None
            cache[ruta] = anclas(texto)[0]
        return cache[ruta]

    for origen, texto in docs.items():
        for linea, ident in anclas(texto)[1]:
            anotar(origen, linea, f"#{ident}", f"el ancla explícita «{ident}» está repetida")
        for linea, destino in enlaces(texto):
            total += 1
            if _UNIDAD.match(destino):
                anotar(origen, linea, destino, f"«{destino}»: ruta absoluta local; usa una ruta relativa")
                continue
            if not destino or _ESQUEMA.match(destino):
                continue
            ruta, _, fragmento = destino.partition("#")
            objetivo = _resolver(origen, ruta) if ruta.split("?", 1)[0] else origen
            if objetivo.startswith(".."):
                continue
            if objetivo not in existentes and objetivo not in carpetas:
                correcta = escritas.get(objetivo.lower())
                detalle = f"no existe; se escribe {correcta}" if correcta else "no existe"
                anotar(origen, linea, destino, f"«{destino}»: {objetivo} {detalle}")
                continue
            if fragmento and objetivo.endswith(".md"):
                disponibles = anclas_de(objetivo)
                if disponibles is not None and fragmento not in disponibles:
                    anotar(origen, linea, destino, f"«{destino}»: {objetivo} no tiene el ancla «{fragmento}»")
    return {"errores": errores, "enlaces": total, "deuda_usada": usada}


def configuracion(instalacion):
    """(carpetas excluidas, deuda como pares) que declara la instalación en `enlaces`; ValueError si está mal formada."""
    declarado = instalacion.get("enlaces", {}) if isinstance(instalacion, dict) else None
    if not isinstance(declarado, dict) or set(declarado) - {"excluir", "deuda"}:
        raise ValueError("enlaces es un objeto con excluir y deuda")
    excluir = declarado.get("excluir", [])
    if not isinstance(excluir, list) or any(not isinstance(c, str) or not c.strip("./") for c in excluir):
        raise ValueError("enlaces.excluir es una lista de carpetas o archivos de la raíz")
    deuda = declarado.get("deuda", [])
    if not isinstance(deuda, list) or any(
        not isinstance(d, dict)
        or set(d) != {"documento", "destino"}
        or not all(isinstance(v, str) and v for v in d.values())
        for d in deuda
    ):
        raise ValueError("enlaces.deuda es una lista de {documento, destino}")
    return [_normal(c) for c in excluir], {(_normal(d["documento"]), d["destino"]) for d in deuda}


def _normal(ruta):
    return posixpath.normpath(ruta.replace("\\", "/")).strip("/")


def _dentro(ruta, carpetas):
    return any(c == "." or ruta == c or ruta.startswith(c + "/") for c in carpetas)


def _rutas_de_git(raiz):
    """Lo que git ve bajo la raíz y sigue en el disco: versionado o nuevo sin ignorar, con las mayúsculas del índice."""
    orden = ["git", "-C", str(raiz), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    p = subprocess.run(orden, capture_output=True, env=entorno_git())
    if p.returncode != 0:
        raise ValueError(f"{raiz} no es un árbol de trabajo de git: no se sabe qué rutas existen")
    return {r for r in p.stdout.decode("utf-8").split("\0") if r and (Path(raiz) / r).exists()}


def comprobar(raiz, carpetas=(".",), excluir=(), deuda=frozenset()):
    """Revisa los `.md` de las carpetas de la raíz, salvo los excluidos.

    {documentos, enlaces, errores, deuda_usada, deuda_sobrante, ilegibles}. Los destinos se buscan en toda la raíz,
    también en lo excluido y fuera de las carpetas: lo que no se revisa sigue pudiendo enlazarse.
    """
    raiz = Path(raiz)
    carpetas = [_normal(c) for c in carpetas]
    for c in carpetas:
        if not (raiz / c).is_dir():
            raise FileNotFoundError(f"no existe la carpeta: {c}")
    existentes = _rutas_de_git(raiz)

    def leer(ruta):
        try:
            return (raiz / ruta).read_bytes().decode("utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError):
            return None

    docs, ilegibles = {}, []
    for ruta in sorted(existentes):
        if not ruta.endswith(".md") or not _dentro(ruta, carpetas) or _dentro(ruta, excluir):
            continue
        texto = leer(ruta)
        if texto is None:
            ilegibles.append(ruta)
        else:
            docs[ruta] = texto
    res = revisar(docs, existentes, lambda r: docs.get(r) or leer(r), deuda)

    def pares(conjunto):
        return [{"documento": d, "destino": e} for d, e in sorted(conjunto)]

    return {
        "documentos": len(docs),
        "enlaces": res["enlaces"],
        "errores": res["errores"],
        "deuda_usada": pares(res["deuda_usada"]),
        "deuda_sobrante": pares(set(deuda) - res["deuda_usada"]),
        "ilegibles": ilegibles,
    }
