"""Unidades de norma según la versión estructurada del editor: HTML de EUR-Lex y XML del BOE.

Es la referencia con que se mide la extracción del PDF, no evidencia citable. Las claves son las de `norma-v1`
(`cons`, `anx`, `art`, `ap`, `let`) y cada unidad lleva su texto completo, con el de sus hijas. Lo que el editor no
estructura (los puntos internos de un anexo de EUR-Lex) se mide al nivel del anexo entero.
"""

import html
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

_VACIOS = {"area", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
_ID_EURLEX = re.compile(r"rct_(\d+)|art_(\d+)|(\d{3})\.(\d{3})|anx_([IVXLC]+)")
_LETRA = re.compile(r"^([a-zñ])\)$")
_ROMANO = re.compile(r"^(i{1,3}|iv|vi{0,3}|ix|x)\)$")
# Notas al pie, sus llamadas y cabeceras de tabla: la estructura extraída tampoco las cuenta.
_OMITIR = {"oj-note", "oj-super", "oj-tbl-hdr"}


class _Arbol(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = {"tag": "raiz", "attrs": {}, "hijos": []}
        self.pila = [self.raiz]

    def handle_starttag(self, tag, attrs):
        nodo = {"tag": tag, "attrs": dict(attrs), "hijos": []}
        self.pila[-1]["hijos"].append(nodo)
        if tag not in _VACIOS:
            self.pila.append(nodo)

    def handle_endtag(self, tag):
        for i in range(len(self.pila) - 1, 0, -1):
            if self.pila[i]["tag"] == tag:
                del self.pila[i:]
                return

    def handle_data(self, data):
        self.pila[-1]["hijos"].append(data)


def _texto(nodo) -> str:
    partes = []

    def visitar(n):
        if isinstance(n, str):
            partes.append(n)
            return
        if _OMITIR & set(n["attrs"].get("class", "").split()):
            return
        for h in n["hijos"]:
            visitar(h)
        if n["tag"] in ("p", "div", "tr", "li"):
            partes.append("\n")

    visitar(nodo)
    return re.sub(r"[ \t  ]+", " ", "".join(partes)).strip()


def _recorrer(nodo):
    yield nodo
    for h in nodo["hijos"]:
        if not isinstance(h, str):
            yield from _recorrer(h)


def unidades_editor_eurlex(documento: str) -> dict[str, str]:
    arbol = _Arbol()
    arbol.feed(documento)
    unidades: dict[str, str] = {}
    for nodo in _recorrer(arbol.raiz):
        m = _ID_EURLEX.fullmatch(nodo["attrs"].get("id", ""))
        if not m:
            continue
        cons, art, art_ap, ap, anx = m.groups()
        if cons:
            clave = f"cons={cons}"
        elif art:
            clave = f"art={art}"
        elif anx:
            clave = f"anx={anx}"
        else:
            clave = f"art={int(art_ap)};ap={int(ap)}"
        if art or art_ap:
            _marcas(nodo, clave, unidades)
        unidades[clave] = _texto(nodo)
    return unidades


def _filas(nodo):
    """Filas de tabla bajo `nodo` sin entrar en celdas (tablas anidadas) ni en otras subdivisiones con id."""
    for h in nodo["hijos"]:
        if isinstance(h, str):
            continue
        if h["tag"] == "tr":
            yield h
        elif h["tag"] != "td" and not _ID_EURLEX.fullmatch(h["attrs"].get("id", "")):
            yield from _filas(h)


def _marcas(nodo, clave: str, unidades: dict[str, str]):
    """Letras `a)` de las filas directas y, dentro de cada letra, numerales romanos `i)` anidados (`num`)."""
    for fila in _filas(nodo):
        celdas = [n for n in fila["hijos"] if not isinstance(n, str) and n["tag"] == "td"]
        if len(celdas) < 2:
            continue
        marca = _texto(celdas[0])
        if letra := _LETRA.match(marca):
            sub = f"{clave};let={letra.group(1)}"
            unidades[sub] = _texto(celdas[1])
            for fila2 in _filas(celdas[1]):
                celdas2 = [n for n in fila2["hijos"] if not isinstance(n, str) and n["tag"] == "td"]
                if len(celdas2) >= 2 and (romano := _ROMANO.match(_texto(celdas2[0]))):
                    unidades[f"{sub};num={romano.group(1)}"] = _texto(celdas2[1])
        elif romano := _ROMANO.match(marca):
            unidades[f"{clave};num={romano.group(1)}"] = _texto(celdas[1])


_ARTICULO = re.compile(r"Artículo\s+(\d+)\.")
_APARTADO = re.compile(r"^(\d+)\.\s")
_LETRA_BOE = re.compile(r"^([a-zñ])\)\s")
_ANEXO = re.compile(r"ANEXO\s+([IVXLC]+)$")


def unidades_editor_boe(documento: str) -> dict[str, str]:
    texto = ET.fromstring(documento).find("texto")
    unidades: dict[str, list[str]] = {}
    abiertas: list[str] = []
    for p in texto.iter("p"):
        clase = p.get("class", "")
        contenido = html.unescape("".join(p.itertext())).replace(" ", " ").replace(" ", " ").strip()
        if not contenido:
            continue
        if clase == "articulo":
            m = _ARTICULO.match(contenido)
            abiertas = [f"art={m.group(1)}"] if m else []
        elif clase == "anexo_num":
            m = _ANEXO.match(contenido)
            abiertas = [f"anx={m.group(1)}"] if m else []
        elif clase in ("capitulo_num", "firma_rey", "firma_ministro") or contenido.startswith("Disposición "):
            abiertas = []
        elif abiertas and abiertas[0].startswith("art="):
            ap, letra = _APARTADO.match(contenido), _LETRA_BOE.match(contenido)
            if ap:
                abiertas = [abiertas[0], f"{abiertas[0]};ap={ap.group(1)}"]
            elif letra:
                base = next((k for k in abiertas if ";ap=" in k and ";let=" not in k), abiertas[0])
                abiertas = [k for k in abiertas if ";let=" not in k] + [f"{base};let={letra.group(1)}"]
        for clave in abiertas:
            unidades.setdefault(clave, []).append(contenido)
    return {k: "\n".join(v) for k, v in unidades.items()}
