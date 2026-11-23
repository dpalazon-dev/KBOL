"""Segmentación de un DoclingDocument en unidades de norma (`estructura-v1`), la representación que cita KBOL.

Recorre el cuerpo en orden de lectura y abre unidades por patrones de la redacción normativa de la UE y del BOE:
considerandos `(n)`, `Artículo n`, apartados `n.`, puntos `n)` o `n.` de anexo, letras `a)`, `ANEXO X`, `Parte X` y
`Clase X` (clave `sec`). Cada elemento se añade a todas las unidades abiertas, así que una unidad contiene a sus
hijas. La región de una unidad en cada página es la envolvente de sus elementos, normalizada y con origen arriba a
la izquierda. Un encabezado que Docling dejó como cabecera o pie de página entra solo si coincide con un patrón
estructural, al principio de su página, y queda en `avisos`: es una corrección de la segmentación, no del original.
"""

import hashlib
import json
import re
from pathlib import Path

from .almacen import guardar, leer

_ARTICULO = re.compile(r"^Art[íi]culo\s+(\d+)\b")
_ANEXO = re.compile(r"^ANEXO\s+([IVXLC]+)\b")
_PARTE = re.compile(r"^PARTE\s+([IVXLC]+)\b", re.IGNORECASE)
_CLASE = re.compile(r"^Clase\s+([IVXLC]+)\b")
_CAPITULO = re.compile(r"^CAP[ÍI]TULO\s+([IVXLC]+)\b", re.IGNORECASE)
_CONSIDERANDO = re.compile(r"^\((\d+)\)\s*")
_APARTADO = re.compile(r"^(\d+)\.(?!\d)\s*")
_PUNTO = re.compile(r"^(\d+)\)\s*")
_LETRA = re.compile(r"^([a-zñ])\)\s*")
_ROMANO = re.compile(r"^(i{1,3}|iv|vi{0,3}|ix|x)\)\s*")
_ESTRUCTURAL = (_ARTICULO, _ANEXO, _PARTE, _CLASE, _CAPITULO)
# Docling 2.142.1 lee el espacio largo U+2003 de los PDF del BOE como U+0840 (letra mandea).
_GLIFO = "ࡀ"
_IGNORAR = {"page_header", "page_footer", "footnote"}
# Fecha de la cabecera del Diario Oficial que Docling deja a veces en el cuerpo: es cabecera de página.
_FECHA_CABECERA = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")


def _resolver(doc: dict, ref: str) -> dict:
    _, tipo, indice = ref.split("/")
    return doc[tipo][int(indice)]


def _texto_tabla(tabla: dict) -> list[tuple[str, list]]:
    """Filas de una tabla sin la cabecera: (texto de la fila, celdas con caja).

    Una celda combinada aparece en cada fila que abarca: se omite cuando repite la de la fila anterior en la misma
    columna, para no contar dos veces su texto. Sin su número, la fila siguiente continúa la unidad abierta.
    """
    filas, anterior = [], {}
    for fila in tabla["data"]["grid"]:
        if any(c.get("column_header") for c in fila):
            continue
        vistas, textos, actual = set(), [], {}
        for c in fila:
            t = c["text"].strip()
            col = c.get("start_col_offset_idx")
            actual[col] = t
            if t and t not in vistas and anterior.get(col) != t:
                vistas.add(t)
                textos.append(t)
        anterior = actual
        if textos:
            filas.append((" | ".join(textos), fila))
    return filas


def _elementos(doc: dict, ordenar: bool = False):
    """(texto, [(página, caja, origen)]) en orden de lectura, con los encabezados estructurales recuperados.

    Con `ordenar`, el orden de los elementos de primer nivel es el de `di.orden` y no el de Docling.
    """
    secuencia = []
    sustituciones = [0]
    raiz, avisos_orden = doc["body"], []
    if ordenar:
        from .orden import refs_ordenadas

        refs, avisos_orden = refs_ordenadas(doc)
        raiz = {"children": [{"$ref": r} for r in refs]}

    def visitar(nodo):
        for hijo in nodo.get("children", []):
            item = _resolver(doc, hijo["$ref"])
            etiqueta = item.get("label")
            if etiqueta == "table":
                pagina = item["prov"][0]["page_no"] if item.get("prov") else None
                for texto, celdas in _texto_tabla(item):
                    cajas = [(pagina, c["bbox"]) for c in celdas if c.get("bbox")]
                    secuencia.append({"texto": texto, "cajas": cajas, "tabla": True})
                continue
            if etiqueta not in _IGNORAR and item.get("text") and not _FECHA_CABECERA.match(item["text"].strip()):
                marcador = (item.get("marker") or "").strip()
                crudo = item["text"]
                if _GLIFO in crudo:
                    sustituciones[0] += crudo.count(_GLIFO)
                    crudo = crudo.replace(_GLIFO, " ")
                texto = f"{marcador} {crudo}".strip() if marcador else crudo
                cajas = [(p["page_no"], p["bbox"]) for p in item.get("prov", [])]
                secuencia.append({"texto": texto, "cajas": cajas, "tabla": False, "lista": etiqueta == "list_item"})
            visitar(item)

    visitar(raiz)
    avisos = list(avisos_orden)
    if sustituciones[0]:
        avisos.append(
            f"glifo U+0840 sustituido por espacio en {sustituciones[0]} sitios (Docling lee así el espacio largo U+2003)"
        )
    for item in doc["texts"]:
        if item.get("label") in ("page_header", "page_footer") and any(p.match(item["text"]) for p in _ESTRUCTURAL):
            pagina = item["prov"][0]["page_no"]
            pos = next(
                (i for i, e in enumerate(secuencia) if e["cajas"] and e["cajas"][0][0] >= pagina), len(secuencia)
            )
            secuencia.insert(pos, {"texto": item["text"], "cajas": [(pagina, item["prov"][0]["bbox"])], "tabla": False})
            avisos.append(
                f"encabezado «{item['text']}» recuperado de {item['label']} ({item['self_ref']}, página {pagina})"
            )
    return secuencia, avisos


def _region(caja: dict, ancho: float, alto: float) -> list[float]:
    izq, der = caja["l"], caja["r"]
    if caja.get("coord_origin", "BOTTOMLEFT") == "BOTTOMLEFT":
        y0, y1 = alto - caja["t"], alto - caja["b"]
    else:
        y0, y1 = caja["t"], caja["b"]
    x0, x1 = sorted((izq / ancho, der / ancho))
    y0, y1 = sorted((y0 / alto, y1 / alto))
    return [max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)]


def _fmt(valor: float) -> str:
    return f"{valor:.4f}"


class _Constructor:
    def __init__(self, paginas: dict):
        self.paginas = paginas
        self.unidades: list[dict] = []
        self.abiertas: dict[str, dict] = {}

    def abrir(self, nivel_claves: list[tuple[str, str]], conservar: int):
        """Cierra las abiertas por debajo de `conservar` partes y abre la nueva clave."""
        actuales = sorted(self.abiertas.values(), key=lambda u: u["nivel"])
        self.abiertas = {u["clave"]: u for u in actuales if u["nivel"] < conservar}
        clave = ";".join(f"{k}={v}" for k, v in nivel_claves)
        unidad = {"clave": clave, "nivel": len(nivel_claves) - 1, "partes": nivel_claves, "cajas": [], "texto": []}
        self.unidades.append(unidad)
        self.abiertas[clave] = unidad
        return unidad

    def cerrar_marcas(self):
        self.abiertas = {k: u for k, u in self.abiertas.items() if not {"let", "num"} & set(dict(u["partes"]))}

    def cerrar_todo(self):
        self.abiertas = {}

    def raiz(self):
        return min(self.abiertas.values(), key=lambda u: u["nivel"]) if self.abiertas else None

    def hoja(self):
        return max(self.abiertas.values(), key=lambda u: u["nivel"]) if self.abiertas else None

    def anadir(self, elemento: dict):
        for u in self.abiertas.values():
            u["texto"].append(elemento["texto"])
            u["cajas"].extend(elemento["cajas"])

    def descartar_indice(self) -> list[str]:
        """Quita las unidades de un solo elemento (el encabezado) cuya clave se repite: son entradas del índice."""
        cuenta: dict[str, int] = {}
        for u in self.unidades:
            cuenta[u["clave"]] = cuenta.get(u["clave"], 0) + 1
        quitar = [u for u in self.unidades if cuenta[u["clave"]] > 1 and len(u["texto"]) == 1]
        self.unidades = [u for u in self.unidades if u not in quitar]
        return [u["clave"] for u in quitar]

    def salida(self) -> list[dict]:
        res = []
        for u in self.unidades:
            por_pagina: dict[int, list[list[float]]] = {}
            for pagina, caja in u["cajas"]:
                tam = self.paginas[str(pagina)]["size"]
                por_pagina.setdefault(pagina, []).append(_region(caja, tam["width"], tam["height"]))
            regiones = []
            for pagina, rs in sorted(por_pagina.items()):
                x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
                x1, y1 = max(r[2] for r in rs), max(r[3] for r in rs)
                regiones.append(
                    {"p": pagina, "r": [_fmt(x0), _fmt(y0), _fmt(max(x1, x0 + 0.0001)), _fmt(max(y1, y0 + 0.0001))]}
                )
            res.append(
                {
                    "clave": u["clave"],
                    "nivel": u["nivel"],
                    "paginas": sorted(por_pagina),
                    "regiones": regiones,
                    "texto": "\n".join(u["texto"]),
                }
            )
        return res


def _es_romano(hoja: dict | None, marca: str) -> bool:
    """`i)` es letra si sigue a `h)`; `v)` y `x)`, si siguen a `u)` y `w)`. Si no, con una letra abierta, es numeral."""
    if hoja is None:
        return False
    partes = dict(hoja["partes"])
    letra = partes.get("let")
    if letra is None:
        return False
    return not (len(marca) == 1 and "num" not in partes and ord(marca) == ord(letra) + 1)


def estructura_desde_docling(
    doc: dict, original_sha256: str, docling_sha256: str | None = None, ordenar: bool = False
) -> dict:
    secuencia, avisos = _elementos(doc, ordenar)
    c = _Constructor(doc["pages"])
    for e in secuencia:
        t = e["texto"].strip()
        raiz = c.raiz()
        if not e["tabla"] and (m := _ARTICULO.match(t)):
            c.abrir([("art", m.group(1))], 0)
        elif not e["tabla"] and (m := _ANEXO.match(t)):
            c.abrir([("anx", m.group(1))], 0)
        elif _CAPITULO.match(t) or t.startswith(("Hecho en ", "HA ADOPTADO", "HAN ADOPTADO")):
            c.cerrar_todo()
            continue
        elif raiz and raiz["partes"][0][0] == "anx" and (m := _PARTE.match(t) or _CLASE.match(t)):
            clave = "parte" if _PARTE.match(t) else "sec"
            c.abrir([raiz["partes"][0], (clave, m.group(1))], 1)
        elif (raiz is None or raiz["partes"][0][0] == "cons") and (m := _CONSIDERANDO.match(t)):
            c.abrir([("cons", m.group(1))], 0)
        elif raiz and raiz["partes"][0][0] == "art" and (m := _APARTADO.match(t)) and not e["tabla"]:
            c.abrir([raiz["partes"][0], ("ap", m.group(1))], 1)
        elif (
            raiz
            and raiz["partes"][0][0] in ("art", "anx")
            and (m := _PUNTO.match(t) or (_APARTADO.match(t) if raiz["partes"][0][0] == "anx" else None))
        ):
            base = [p for p in c.hoja()["partes"] if p[0] in ("anx", "parte", "sec", "art", "ap")]
            existente = ";".join(f"{k}={v}" for k, v in [*base, ("pto", m.group(1))])
            if existente in c.abiertas:
                pass  # celda combinada repetida en la fila siguiente: misma unidad
            else:
                c.abrir([*base, ("pto", m.group(1))], len(base))
        elif raiz and (m := _ROMANO.match(t)) and _es_romano(c.hoja(), m.group(1)):
            base = [p for p in c.hoja()["partes"] if p[0] != "num"]
            c.abrir([*base, ("num", m.group(1))], len(base))
        elif raiz and (m := _LETRA.match(t)):
            base = [p for p in c.hoja()["partes"] if p[0] not in ("let", "num")]
            c.abrir([*base, ("let", m.group(1))], len(base))
        elif (
            raiz
            and not e["tabla"]
            and not e.get("lista")
            and c.hoja()
            and {"let", "num"} & set(dict(c.hoja()["partes"]))
        ):
            c.cerrar_marcas()  # párrafo sin marca tras una lista: vuelve al apartado
        c.anadir(e)
    indice = c.descartar_indice()
    if indice:
        avisos.append(f"{len(indice)} entradas de índice descartadas (unidad de solo encabezado con clave repetida)")
    paginas = [
        {"p": int(k), "ancho": v["size"]["width"], "alto": v["size"]["height"]}
        for k, v in sorted(doc["pages"].items(), key=lambda kv: int(kv[0]))
    ]
    est = {
        "perfil": "estructura-v1",
        "original_sha256": original_sha256,
        "docling_sha256": docling_sha256,
        "segmentador": "kbol-di/estructura 0.1",
        "paginas": paginas,
        "unidades": c.salida(),
        "avisos": avisos,
    }
    if ordenar:  # sin la opción, la salida es byte a byte la de las derivaciones ya registradas
        est["orden_corregido"] = True
    return est


def estructura_en_almacen(huella_docling: str, huella_original: str, almacen: Path, ordenar: bool = False) -> dict:
    doc = json.loads(leer(huella_docling, almacen))
    est = estructura_desde_docling(doc, huella_original, huella_docling, ordenar=ordenar)
    datos = json.dumps(est, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    huella, _ = guardar(datos, almacen)
    claves = [u["clave"] for u in est["unidades"]]
    repetidas = sorted({k for k in claves if claves.count(k) > 1})
    codigo = Path(__file__).read_bytes()
    if ordenar:
        codigo += (Path(__file__).parent / "orden.py").read_bytes()
    return {
        "sha256": huella,
        "derivada_de": huella_docling,
        "original": huella_original,
        "procesador": "kbol-di/estructura",
        "version": "0.1",
        "codigo_sha256": hashlib.sha256(codigo).hexdigest(),
        "configuracion": {"ordenar": ordenar},
        "unidades": len(claves),
        "repetidas": repetidas,
        "avisos": est["avisos"],
    }
