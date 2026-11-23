"""Segmentación genérica de un DoclingDocument (`estructura-v1`) para un PDF que no es una norma.

Las unidades salen de lo que Docling etiqueta en cualquier documento. Cada título abre una sección (numeradas desde
1 por orden de aparición; la 0 es lo que precede al primer título), y la sección se parte por página:
`seccion=<n>;pagina=<p>` contiene solo lo que esa sección tiene en esa página, con el texto de sus tablas y figuras.
Cada tabla y cada figura con leyenda es además una unidad propia (`seccion=<n>;tabla=<m>`, `;figura=<m>`), numerada
como en el DoclingDocument.

Estas claves no son un localizador `norma-v1`: una cita de este perfil es solo física (`pdf-v1`, página y región), y
el resolutor del núcleo la comprueba contra el texto de las unidades de esa página. Por eso se parte por página: con
una unidad por sección entera, una cita con la página equivocada dentro de la misma sección se daría por buena. Las
cabeceras y pies de página quedan fuera.

Con `corregir` (por defecto) se aplican tres correcciones, cada una anotada en `avisos`: el orden de lectura de
`di.orden`, que un rótulo de algoritmo, tabla o figura o un título repetido no abran sección, y que cada tabla o
figura vaya a la sección que la menciona. Sin `corregir` no se aplica ninguna: orden y títulos son los de Docling.
Una tabla que Docling entrega como un solo elemento a caballo entre dos páginas se atribuye a la primera.
"""

import hashlib
import json
import re
from pathlib import Path

from .almacen import guardar, leer
from .contexto import (
    celdas_de_tabla,
    clave_de_entrada,
    jerarquia,
    limpiar_titulo,
    referencias_citadas,
    tipo_de_parte,
)
from .estructura import _GLIFO, _fmt, _region, _resolver
from .orden import ordenar

_MOBILIARIO = {"page_header", "page_footer"}
_TITULOS = {"section_header", "title"}
_FLOTANTES = {"table", "picture"}
# Un rótulo de algoritmo, tabla o figura que Docling etiqueta como título no abre sección.
_ROTULO = re.compile(r"^\s*(algorithm|algoritmo|table|tabla|cuadro|fig(?:ure|ura)?\.?)\s*\d", re.IGNORECASE)
_MENCION = re.compile(r"\b(table|tabla|cuadro|fig(?:ure|ura)?\.?)\s*(\d+)", re.IGNORECASE)
VERSION = "0.2"


def _tipo_flotante(palabra: str) -> str:
    return "figura" if palabra.lower().startswith("fig") else "tabla"


def _comparable(texto: str) -> str:
    return re.sub(r"\W+", "", texto).lower()


def _filas(tabla: dict) -> list[dict]:
    """Una pieza por fila de la tabla, con la cabecera. Una celda combinada cuenta una vez, donde empieza."""
    pagina = tabla["prov"][0]["page_no"] if tabla.get("prov") else None
    vistas, piezas = set(), []
    for fila in tabla.get("data", {}).get("grid", []):
        textos, cajas = [], []
        for celda in fila:
            origen = (celda.get("start_row_offset_idx"), celda.get("start_col_offset_idx"))
            if origen in vistas:
                continue
            vistas.add(origen)
            texto = (celda.get("text") or "").strip()
            if texto:
                textos.append(texto)
                if celda.get("bbox") and pagina is not None:
                    cajas.append((pagina, celda["bbox"]))
        if textos:
            piezas.append({"texto": " | ".join(textos), "cajas": cajas})
    return piezas


def _piezas(doc: dict, item: dict) -> list[dict]:
    """Texto y cajas del elemento y de lo que contiene, en el orden de Docling."""
    if item.get("label") in _MOBILIARIO or item.get("content_layer", "body") != "body":
        return []
    piezas = []
    cajas = [(p["page_no"], p["bbox"]) for p in item.get("prov", [])]
    if item.get("label") == "table":
        piezas.append({"texto": "", "cajas": cajas})
        piezas.extend(_filas(item))
    elif item.get("text"):
        marcador = (item.get("marker") or "").strip()
        crudo = item["text"].replace(_GLIFO, " ")
        piezas.append({"texto": f"{marcador} {crudo}".strip() if marcador else crudo, "cajas": cajas})
    elif cajas:
        piezas.append({"texto": "", "cajas": cajas})
    for hijo in item.get("children", []):
        piezas.extend(_piezas(doc, _resolver(doc, hijo["$ref"])))
    return piezas


def bloques(doc: dict) -> list[dict]:
    """Elementos del cuerpo, con los grupos y los títulos con contenido deshechos: la unidad que se ordena y se asigna."""
    salida = []

    def visitar(nodo):
        for hijo in nodo.get("children", []):
            item = _resolver(doc, hijo["$ref"])
            if item["self_ref"].startswith("#/groups/"):
                visitar(item)
                continue
            if item.get("label") in _TITULOS and item.get("children"):
                # En un Word, Docling cuelga de cada título lo que va debajo: el título es un bloque y su contenido,
                # los siguientes; si no, todo el documento sería el bloque de su primer título.
                propias = _piezas(doc, {**item, "children": []})
                if propias:
                    salida.append({"ref": item["self_ref"], "etiqueta": item.get("label"), "item": item, "piezas": propias})
                visitar(item)
                continue
            piezas = _piezas(doc, item)
            if piezas:
                salida.append({"ref": item["self_ref"], "etiqueta": item.get("label"), "item": item, "piezas": piezas})

    visitar(doc["body"])
    return salida


def _leyenda(doc: dict, item: dict) -> str | None:
    for hijo in item.get("children", []):
        candidato = _resolver(doc, hijo["$ref"])
        if candidato.get("label") == "caption" and candidato.get("text"):
            return candidato["text"]
    return None


def _por_pagina(piezas: list[dict]) -> list[tuple[int, list[dict]]]:
    """Las piezas de una sección repartidas por página, cada una solo con sus cajas de esa página.

    Un párrafo partido entre dos páginas va entero a las dos: la cita de cualquiera de sus frases se resuelve en
    ambas. Una pieza sin caja acompaña a la anterior o, si abre la sección, a la primera que tenga página; en una
    sección sin ninguna caja no hay página a la que llevarla y su texto no entra en ninguna unidad.
    """
    reparto: dict[int, list[dict]] = {}
    ultimas: list[int] = []
    sin_pagina: list[dict] = []
    for pieza in piezas:
        propias = sorted({pagina for pagina, _ in pieza["cajas"]}) or ultimas
        if not propias:
            sin_pagina.append(pieza)
            continue
        for pagina in propias:
            destino = reparto.setdefault(pagina, [])
            if sin_pagina:
                destino.extend({"texto": p["texto"], "cajas": []} for p in sin_pagina)
                sin_pagina = []
            cajas = [(pg, caja) for pg, caja in pieza["cajas"] if pg == pagina]
            destino.append({"texto": pieza["texto"], "cajas": cajas})
        ultimas = propias
    return sorted(reparto.items())


def _unidad(clave: str, nivel: int, piezas: list[dict], paginas: dict, **extra) -> dict:
    por_pagina: dict[int, list[list[float]]] = {}
    for pieza in piezas:
        for pagina, caja in pieza["cajas"]:
            tam = paginas[str(pagina)]["size"]
            por_pagina.setdefault(pagina, []).append(_region(caja, tam["width"], tam["height"]))
    regiones = []
    for pagina, rs in sorted(por_pagina.items()):
        x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
        x1, y1 = max(r[2] for r in rs), max(r[3] for r in rs)
        regiones.append({"p": pagina, "r": [_fmt(x0), _fmt(y0), _fmt(max(x1, x0 + 0.0001)), _fmt(max(y1, y0 + 0.0001))]})
    return {
        "clave": clave,
        "nivel": nivel,
        "paginas": sorted(por_pagina),
        "regiones": regiones,
        "texto": "\n".join(p["texto"] for p in piezas if p["texto"]),
        **extra,
    }


def _reasignar_flotantes(doc: dict, secciones: list[dict]) -> list[str]:
    """Lleva cada tabla o figura con leyenda numerada a la primera sección cuyo texto la menciona.

    En la página, un flotante cae junto a lo que tiene al lado, que no siempre es la sección que lo discute. Sin
    leyenda numerada o sin mención en el texto, se queda donde lo dejó el orden de lectura.
    """
    menciones: dict[tuple[str, str], int] = {}
    for i, seccion in enumerate(secciones):
        for bloque in seccion["bloques"]:
            if bloque["etiqueta"] in _FLOTANTES or bloque["etiqueta"] in _TITULOS:
                continue
            for palabra, numero in _MENCION.findall(bloque["item"].get("text") or ""):
                menciones.setdefault((_tipo_flotante(palabra), numero), i)
    movidos = 0
    for i, seccion in enumerate(secciones):
        for bloque in list(seccion["bloques"]):
            if bloque["etiqueta"] not in _FLOTANTES:
                continue
            m = _MENCION.match((_leyenda(doc, bloque["item"]) or "").strip())
            destino = menciones.get((_tipo_flotante(m.group(1)), m.group(2))) if m else None
            if destino is not None and destino != i:
                seccion["bloques"].remove(bloque)
                secciones[destino]["bloques"].append(bloque)
                movidos += 1
    return [f"{movidos} tablas o figuras llevadas a la sección que las menciona"] if movidos else []


def estructura_generica(
    doc: dict, original_sha256: str, docling_sha256: str | None = None, corregir: bool = True
) -> dict:
    a = analizar(doc, corregir)
    secciones, claves, contexto, avisos = a["secciones"], a["claves"], a["contexto"], a["avisos"]
    bibliografia, autor_anio, maximo = a["bibliografia"], a["autor_anio"], a["maximo"]
    citadas: list[str] = []
    unidades = []
    for clave, seccion, ctx in zip(claves, secciones, contexto, strict=True):
        piezas = [p for b in seccion["bloques"] for p in b["piezas"]]
        partes = _por_pagina(piezas)
        if not partes and any(p["texto"] for p in piezas):
            partes = [(None, piezas)]  # documento sin páginas (Word, HTML): una unidad por sección
        for pagina, parte in partes:
            sufijo = f";pagina={pagina}" if pagina is not None else ""
            unidad = _unidad(f"{clave}{sufijo}", 0, parte, doc.get("pages", {}), titulo=seccion["titulo"], **ctx)
            refs = [] if ctx["tipo"] == "referencias" else referencias_citadas(unidad["texto"], autor_anio, maximo)
            unidad["referencias"] = refs
            citadas.extend(refs)
            unidades.append(unidad)
        for bloque in seccion["bloques"]:
            indice = int(bloque["ref"].rsplit("/", 1)[1]) + 1
            leyenda = _leyenda(doc, bloque["item"])
            if bloque["etiqueta"] == "table":
                unidad = _unidad(f"{clave};tabla={indice}", 1, bloque["piezas"], doc.get("pages", {}), leyenda=leyenda)
                unidad.update(ruta=ctx["ruta"], tipo=ctx["tipo"], celdas=celdas_de_tabla(bloque["item"]))
                unidades.append(unidad)
            elif bloque["etiqueta"] == "picture" and leyenda:
                unidad = _unidad(f"{clave};figura={indice}", 1, bloque["piezas"], doc.get("pages", {}), leyenda=leyenda)
                unidad.update(ruta=ctx["ruta"], tipo=ctx["tipo"])
                unidades.append(unidad)
    if bibliografia:
        conocidas = {r["clave"] for r in bibliografia}
        sueltas = [c for c in dict.fromkeys(citadas) if c not in conocidas]
        if sueltas:
            formato = "({})" if autor_anio else "[{}]"
            avisos.append("citas sin entrada en la bibliografía: " + ", ".join(formato.format(c) for c in sueltas[:20]))
    elif citadas:
        avisos.append(f"{len(set(citadas))} citas a la bibliografía, pero no se reconoce ninguna sección de referencias")
    paginas = [
        {"p": int(k), "ancho": v["size"]["width"], "alto": v["size"]["height"]}
        for k, v in sorted(doc.get("pages", {}).items(), key=lambda kv: int(kv[0]))
    ]
    return {
        "perfil": "estructura-v1",
        "claves": "generica-v1",
        "original_sha256": original_sha256,
        "docling_sha256": docling_sha256,
        "segmentador": f"kbol-di/generica {VERSION}",
        "orden_corregido": corregir,
        "paginas": paginas,
        "unidades": unidades,
        "referencias": bibliografia,
        "avisos": avisos,
    }


def analizar(doc: dict, corregir: bool = True) -> dict:
    """Secciones del documento con sus bloques en orden de lectura, su contexto y la bibliografía.

    Es el cálculo común de la estructura y de la carpeta del documento (`di.proyectar`): las dos salen de aquí y
    no pueden contar cosas distintas del mismo DoclingDocument.
    """
    avisos: list[str] = []
    lista = bloques(doc)
    if corregir:
        lista, avisos = ordenar(doc, lista)
    secciones: list[dict] = []
    anterior = None
    for bloque in lista:
        es_titulo = bloque["etiqueta"] in _TITULOS
        if es_titulo and corregir:
            titulo = bloque["item"]["text"]
            if _ROTULO.match(titulo):
                es_titulo = False
                avisos.append(f"«{titulo.strip()[:60]}» es un rótulo, no abre sección ({bloque['ref']})")
            elif anterior is not None and _comparable(titulo) == anterior:
                es_titulo = False
                avisos.append(f"título repetido «{titulo.strip()[:60]}», no abre otra sección ({bloque['ref']})")
        if es_titulo:
            anterior = _comparable(bloque["item"]["text"])
            secciones.append({"titulo": limpiar_titulo(bloque["item"]["text"]), "bloques": []})
        elif not secciones:
            secciones.append({"titulo": None, "bloques": []})
        secciones[-1]["bloques"].append(bloque)
    if corregir:
        avisos.extend(_reasignar_flotantes(doc, secciones))

    primera = 0 if secciones and secciones[0]["titulo"] is None else 1
    claves = [f"seccion={n}" for n in range(primera, primera + len(secciones))]
    contexto = _contexto_de_secciones(secciones, claves)
    bibliografia, autor_anio = _bibliografia(secciones, claves)
    maximo = max((int(r["clave"]) for r in bibliografia if r["clave"].isdigit()), default=None)
    retroceden = [s["titulo"] for s, c in zip(secciones, contexto, strict=True) if c.pop("retrocede", False)]
    if retroceden:
        avisos.append(
            f"{len(retroceden)} títulos numerados que no avanzan, tratados como apartados de la sección anterior: "
            + "; ".join(f"«{t[:40]}»" for t in retroceden[:5])
        )
    return {
        "secciones": secciones,
        "claves": claves,
        "contexto": contexto,
        "bibliografia": bibliografia,
        "autor_anio": autor_anio,
        "maximo": maximo,
        "avisos": avisos,
    }


def _contexto_de_secciones(secciones: list[dict], claves: list[str]) -> list[dict]:
    """Número, profundidad, padre, ruta de títulos y tipo de parte de cada sección.

    Una sección sin tipo propio hereda el de su padre («5.3 Training time» dentro de «5 Experiments» es de
    experimentos); una numerada con letra tras la bibliografía es un anexo.
    """
    titulos = [s["titulo"] for s in secciones]
    niveles = jerarquia(titulos)
    salida: list[dict] = []
    for titulo, nivel in zip(titulos, niveles, strict=True):
        padre = nivel["padre"]
        tipo = tipo_de_parte(titulo)
        if tipo is None and nivel["numero"] and nivel["numero"][0].isalpha():
            tipo = "anexo"
        if padre is not None and (tipo is None or salida[padre]["tipo"] in ("anexo", "referencias")):
            tipo = salida[padre]["tipo"]
        ruta = ([*salida[padre]["ruta"]] if padre is not None else []) + ([titulo] if titulo else [])
        salida.append(
            {
                "numero": nivel["numero"],
                "profundidad": nivel["profundidad"],
                "padre": claves[padre] if padre is not None else None,
                "ruta": ruta,
                "tipo": tipo,
                "retrocede": nivel.get("retrocede", False),
            }
        )
    return salida


def _bibliografia(secciones: list[dict], claves: list[str]) -> tuple[list[dict], bool]:
    """Entradas de las secciones de referencias, con su clave, texto, páginas y sección; y si son de autor y año.

    Una entrada es numérica si lleva marcador «[n]»; si ninguna lo lleva, la clave es «primer apellido año» y las
    citas del texto se buscan con ese estilo. Una entrada sin clave reconocible no entra.
    """
    entradas, numericas = [], 0
    for clave, seccion in zip(claves, secciones, strict=True):
        if tipo_de_parte(seccion["titulo"]) != "referencias":
            continue
        for bloque in seccion["bloques"]:
            item = bloque["item"]
            if bloque["etiqueta"] not in ("list_item", "text") or not item.get("text"):
                continue
            ref, es_numerica = clave_de_entrada(item["text"], item.get("marker"))
            if ref is None:
                continue
            numericas += es_numerica
            paginas = sorted({p["page_no"] for p in item.get("prov", [])})
            entradas.append({"clave": ref, "texto": item["text"].strip(), "paginas": paginas, "seccion": clave})
    return entradas, bool(entradas) and numericas == 0


def _huella_codigo() -> str:
    """Huella conjunta de los módulos que deciden la salida, en este orden."""
    carpeta = Path(__file__).parent
    return hashlib.sha256(b"".join((carpeta / n).read_bytes() for n in ("generica.py", "contexto.py", "orden.py", "estructura.py"))).hexdigest()


def generica_en_almacen(huella_docling: str, huella_original: str, almacen: Path, corregir: bool = True) -> dict:
    doc = json.loads(leer(huella_docling, almacen))
    est = estructura_generica(doc, huella_original, huella_docling, corregir=corregir)
    datos = json.dumps(est, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    huella, _ = guardar(datos, almacen)
    return {
        "sha256": huella,
        "derivada_de": huella_docling,
        "original": huella_original,
        "procesador": "kbol-di/generica",
        "version": VERSION,
        "codigo_sha256": _huella_codigo(),
        "configuracion": {"corregir": corregir},
        "unidades": len(est["unidades"]),
        "secciones": len({u["clave"].split(";")[0] for u in est["unidades"]}),
        "paginas_sin_unidad": sorted(
            {p["p"] for p in est["paginas"]} - {p for u in est["unidades"] for p in u["paginas"]}
        ),
        "avisos": est["avisos"],
    }
