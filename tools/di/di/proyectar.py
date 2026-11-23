"""Carpeta navegable de un documento: el original, un índice, un Markdown por sección y sus recursos.

```
<destino>/<nombre>/
  <nombre>.pdf                 el original, copiado del almacén
  index.md                     qué es el documento y qué hay en la carpeta
  contenidos/NN-<título>.md    una sección por fichero, con su contexto en la cabecera YAML
  recursos/tablas/tabla-M.md   cada tabla en Markdown y cada dato con sus cabeceras
  recursos/figuras/figura-M.*  la imagen (si Docling la exportó) y su ficha
  recursos/bibliografia.md     las entradas de la bibliografía con su clave
```

Es una vista generada, no conocimiento registrado: sale del DoclingDocument con el mismo cálculo que la estructura
(`generica.analizar`), se regenera entera cuando cambia el procesador y no se edita a mano. Las citas se siguen
escribiendo y comprobando contra la estructura; la cabecera de cada fichero dice qué unidades de esa estructura
cubre. El cuerpo conserva el texto del documento: lo añadido son marcas XML (`<pagina n>`, `<ref clave>`,
`<recurso>`, `<nota>`, `<formula>`) que no cambian lo que se lee.

La carpeta contiene una copia del documento: va fuera del repositorio, en el estado local de la instalación.
"""

import base64
import json
import re
import shutil
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .almacen import leer
from .contexto import limpiar_titulo
from .generica import VERSION as VERSION_SEGMENTADOR
from .generica import _leyenda, analizar

VERSION = "0.1"
GENERADOR = f"kbol-di/proyectar {VERSION}"
_NOMBRE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_EXTENSION_IMAGEN = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class CarpetaAjena(RuntimeError):
    """La carpeta de destino existe y no la generó esta herramienta: no se borra."""


def _slug(texto: str, largo: int = 60) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:largo].strip("-") or "sin-titulo"


def _escribir(ruta: Path, cabecera: dict, cuerpo: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    yml = yaml.safe_dump(cabecera, allow_unicode=True, sort_keys=False, width=1000).rstrip("\n")
    ruta.write_text(f"---\n{yml}\n---\n\n{cuerpo.rstrip()}\n", encoding="utf-8", newline="\n")


def _pagina(item: dict) -> int | None:
    prov = item.get("prov") or []
    return prov[0]["page_no"] if prov else None


def _primera_frase(texto: str, largo: int = 220) -> str:
    t = re.sub(r"\s+", " ", texto).strip()
    m = re.match(r"(.{20,}?[.!?])(\s|$)", t)
    frase = m.group(1) if m else t
    return frase if len(frase) <= largo else frase[: largo - 1].rstrip() + "…"


def _marcar_referencias(texto: str, claves: set[str]) -> str:
    """Envuelve cada «[n]» cuya clave está en la bibliografía; el texto visible no cambia."""

    def sustituir(m: re.Match) -> str:
        numeros = re.findall(r"\d+", m.group(0))
        if numeros and all(n in claves for n in numeros) and len(numeros) == 1:
            return f'<ref clave="{numeros[0]}">{m.group(0)}</ref>'
        return m.group(0)

    return re.sub(r"\[\d+\]", sustituir, texto) if claves else texto


def _recursos(doc: dict, seccion: dict) -> list[dict]:
    salida = []
    for bloque in seccion["bloques"]:
        etiqueta = bloque["etiqueta"]
        if etiqueta not in ("table", "picture"):
            continue
        indice = int(bloque["ref"].rsplit("/", 1)[1]) + 1
        leyenda = _leyenda(doc, bloque["item"])
        if etiqueta == "picture" and not leyenda and not (bloque["item"].get("image") or {}).get("uri"):
            continue
        tipo = "tabla" if etiqueta == "table" else "figura"
        salida.append({"tipo": tipo, "id": f"{tipo}-{indice}", "bloque": bloque, "leyenda": leyenda, "indice": indice})
    return salida


def _cuerpo_de_seccion(seccion: dict, recursos: dict, claves_biblio: set[str]) -> str:
    lineas = [f"# {seccion['titulo']}"] if seccion["titulo"] else []
    pagina_actual = None
    primero = True
    for bloque in seccion["bloques"]:
        item, etiqueta = bloque["item"], bloque["etiqueta"]
        pagina = _pagina(item)
        if pagina is not None and pagina != pagina_actual:
            lineas.append(f'<pagina n="{pagina}"/>')
            pagina_actual = pagina
        texto = (item.get("text") or "").strip()
        if primero and etiqueta in ("section_header", "title"):
            primero = False
            continue
        primero = False
        if etiqueta in ("table", "picture"):
            r = recursos.get(bloque["ref"])
            if r:
                carpeta = "tablas" if r["tipo"] == "tabla" else "figuras"
                ref = f"../recursos/{carpeta}/{r['id']}.md"
                lineas.append(f'<recurso tipo="{r["tipo"]}" id="{r["id"]}" ref="{ref}">{r["leyenda"] or ""}</recurso>')
            continue
        if not texto:
            continue
        if etiqueta in ("section_header", "title"):
            lineas.append(f"**{limpiar_titulo(texto)}**")
        elif etiqueta == "list_item":
            marcador = (item.get("marker") or "").strip()
            vineta = marcador if re.fullmatch(r"\[?\d+[.)\]]?|[a-z][.)]", marcador or "") else "-"
            lineas.append(f"{vineta} {_marcar_referencias(texto, claves_biblio)}")
        elif etiqueta == "code":
            lineas.append(f"```\n{texto}\n```")
        elif etiqueta == "formula":
            lineas.append(f"<formula>{texto}</formula>")
        elif etiqueta == "footnote":
            lineas.append(f"<nota>{texto}</nota>")
        else:
            lineas.append(_marcar_referencias(texto, claves_biblio))
    return "\n\n".join(lineas)


def _tabla_markdown(tabla: dict) -> str:
    """La rejilla de Docling como tabla Markdown; una celda combinada repite su texto en cada hueco, como Docling."""
    grid = tabla.get("data", {}).get("grid") or []
    filas = [[re.sub(r"\s+", " ", (c or {}).get("text") or "").replace("|", r"\|").strip() for c in fila] for fila in grid]
    if not filas:
        return ""
    ancho = max(len(f) for f in filas)
    filas = [f + [""] * (ancho - len(f)) for f in filas]
    lineas = ["| " + " | ".join(filas[0]) + " |", "|" + "---|" * ancho]
    lineas += ["| " + " | ".join(f) + " |" for f in filas[1:]]
    return "\n".join(lineas)


def _lineas_por_seccion(markdown: str, titulos: list[str | None]) -> list[list[int] | None]:
    """[inicio, fin] (desde 1, inclusivos) de cada sección en el Markdown, buscando sus títulos en orden.

    Una sección cuyo título no aparece queda sin líneas; la anterior se alarga hasta la siguiente que sí aparece.
    """
    lineas = markdown.split("\n")
    comparable = [re.sub(r"\W+", "", re.sub(r"^#+\s*", "", x)).lower() for x in lineas]
    inicios: list[int | None] = []
    cursor = 0
    for i, titulo in enumerate(titulos):
        if titulo is None:
            inicios.append(1 if i == 0 else None)
            continue
        objetivo = re.sub(r"\W+", "", titulo).lower()
        pos = next((k for k in range(cursor, len(lineas)) if objetivo and comparable[k] == objetivo), None)
        inicios.append(None if pos is None else pos + 1)
        if pos is not None:
            cursor = pos + 1
    salida: list[list[int] | None] = []
    for i, ini in enumerate(inicios):
        if ini is None:
            salida.append(None)
            continue
        siguiente = next((x for x in inicios[i + 1 :] if x is not None), len(lineas) + 1)
        fin = siguiente - 1
        while fin > ini and not lineas[fin - 1].strip():
            fin -= 1
        salida.append([ini, fin])
    return salida


def _datos_con_contexto(celdas: list[dict]) -> str:
    filas = []
    for c in celdas:
        fila = " · ".join(c["fila"])
        cabeceras = " › ".join(c["cabeceras"])
        delante = " · ".join(x for x in (fila, cabeceras) if x)
        pagina = f" (pág. {c['p']})" if c.get("p") else ""
        filas.append(f"- {delante} = {c['texto']}{pagina}" if delante else f"- {c['texto']}{pagina}")
    return "\n".join(filas)


def _imagen(item: dict) -> tuple[bytes, str] | None:
    uri = (item.get("image") or {}).get("uri") or ""
    m = re.match(r"data:([\w/+.-]+);base64,(.+)", uri, re.S)
    if not m:
        return None
    return base64.b64decode(m.group(2)), _EXTENSION_IMAGEN.get(m.group(1), "png")


def _preparar_destino(carpeta: Path) -> None:
    if carpeta.exists():
        indice = carpeta / "index.md"
        generada = indice.exists() and f"by: {GENERADOR.split(' ')[0]}" in indice.read_text(encoding="utf-8")
        if not generada:
            raise CarpetaAjena(f"{carpeta} existe y no es una carpeta generada por kbol-di/proyectar")
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)


def proyectar(
    doc: dict,
    estructura: dict,
    original: bytes,
    nombre_original: str,
    nombre: str,
    destino: Path,
    estructura_sha256: str | None = None,
    markdown: str | None = None,
    markdown_sha256: str | None = None,
) -> dict:
    """Escribe `<destino>/<nombre>/` y devuelve lo escrito. Regenera la carpeta si la generó esta herramienta.

    Con `markdown` (la representación en texto de un documento sin páginas), cada sección dice en `lineas` qué
    líneas de ese Markdown ocupa: es lo que se cita con `lines-v1`.
    """
    if not _NOMBRE.fullmatch(nombre or ""):
        raise ValueError(f"nombre de carpeta no válido: {nombre!r} (letras, cifras, punto, guion y subrayado)")
    carpeta = Path(destino) / nombre
    _preparar_destino(carpeta)
    ahora = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    generado = {"by": GENERADOR, "at": ahora}
    a = analizar(doc, corregir=estructura.get("orden_corregido", True))
    secciones, claves, contexto = a["secciones"], a["claves"], a["contexto"]
    claves_biblio = {r["clave"] for r in a["bibliografia"]}
    unidades_por_seccion: dict[str, list[str]] = {}
    for u in estructura.get("unidades", []):
        unidades_por_seccion.setdefault(u["clave"].split(";")[0], []).append(u["clave"])
    celdas_por_unidad = {u["clave"]: u.get("celdas", []) for u in estructura.get("unidades", [])}
    origen = {
        "original_sha256": estructura.get("original_sha256"),
        "estructura_sha256": estructura_sha256,
        "docling_sha256": estructura.get("docling_sha256"),
    }
    if markdown_sha256:
        origen["markdown_sha256"] = markdown_sha256
    lineas = _lineas_por_seccion(markdown, [s["titulo"] for s in secciones]) if markdown else [None] * len(secciones)
    extension = Path(nombre_original).suffix.lower() or ".pdf"
    fichero = f"{nombre}{extension}"
    (carpeta / fichero).write_bytes(original)

    ids = [f"{nombre}#{c}" for c in claves]
    hijos: dict[str, list[str]] = {}
    for i, ctx in enumerate(contexto):
        if ctx["padre"]:
            hijos.setdefault(f"{nombre}#{ctx['padre']}", []).append(ids[i])
    ficheros, tablas, figuras = [], [], []
    for orden, (clave, seccion, ctx) in enumerate(zip(claves, secciones, contexto, strict=True), start=1):
        recursos = _recursos(doc, seccion)
        por_ref = {r["bloque"]["ref"]: r for r in recursos}
        cuerpo = _cuerpo_de_seccion(seccion, por_ref, claves_biblio)
        texto_plano = next(
            (b["item"]["text"] for b in seccion["bloques"] if b["etiqueta"] in ("text", "list_item") and b["item"].get("text")),
            seccion["titulo"] or "",
        )
        paginas = sorted({p for b in seccion["bloques"] for p in [_pagina(b["item"])] if p is not None})
        referencias = []
        for u in estructura.get("unidades", []):
            if u["clave"].split(";")[0] == clave:
                referencias.extend(r for r in u.get("referencias", []) if r not in referencias)
        nombre_fichero = f"{orden:02d}-{_slug(seccion['titulo'] or 'preliminares')}.md"
        cabecera = {
            "id": f"{nombre}#{clave}",
            "type": "seccion",
            "title": seccion["titulo"] or "(preliminares)",
            "description": _primera_frase(texto_plano),
            "documento": nombre,
            "numero": ctx["numero"],
            "profundidad": ctx["profundidad"],
            "padre": f"{nombre}#{ctx['padre']}" if ctx["padre"] else None,
            "hijos": hijos.get(f"{nombre}#{clave}", []),
            "ruta": ctx["ruta"],
            "tipo": ctx["tipo"],
            "paginas": paginas,
            **({"lineas": lineas[orden - 1]} if lineas[orden - 1] else {}),
            "referencias": referencias,
            "recursos": [r["id"] for r in recursos],
            "origen": {**origen, "unidades": unidades_por_seccion.get(clave, [])},
            "generated": generado,
        }
        _escribir(carpeta / "contenidos" / nombre_fichero, cabecera, cuerpo)
        ficheros.append({"fichero": nombre_fichero, "titulo": seccion["titulo"], "profundidad": ctx["profundidad"],
                         "tipo": ctx["tipo"], "paginas": paginas})
        for r in recursos:
            item, unidad = r["bloque"]["item"], f"{clave};{r['tipo']}={r['indice']}"
            base = {
                "id": f"{nombre}#{r['id']}",
                "type": r["tipo"],
                "title": r["leyenda"] or r["id"],
                "documento": nombre,
                "seccion": f"{nombre}#{clave}",
                "ruta": ctx["ruta"],
                "paginas": sorted({p["page_no"] for p in item.get("prov", [])}),
                "unidad": unidad if unidad in unidades_por_seccion.get(clave, []) else None,
                "origen": origen,
                "generated": generado,
            }
            if r["tipo"] == "tabla":
                celdas = celdas_por_unidad.get(unidad, [])
                rejilla = _tabla_markdown(item)
                cuerpo_tabla = f"# {r['leyenda'] or r['id']}\n\n{rejilla}\n\n## Datos con su contexto\n\n{_datos_con_contexto(celdas)}"
                _escribir(carpeta / "recursos" / "tablas" / f"{r['id']}.md", {**base, "celdas": len(celdas)}, cuerpo_tabla)
                tablas.append({**r, "seccion": ficheros[-1]["fichero"]})
            else:
                imagen = _imagen(item)
                extra = {}
                cuerpo_figura = f"# {r['leyenda'] or r['id']}\n\n"
                if imagen:
                    datos, ext = imagen
                    (carpeta / "recursos" / "figuras").mkdir(parents=True, exist_ok=True)
                    (carpeta / "recursos" / "figuras" / f"{r['id']}.{ext}").write_bytes(datos)
                    extra["imagen"] = f"{r['id']}.{ext}"
                    cuerpo_figura += f"![{r['leyenda'] or r['id']}]({r['id']}.{ext})\n"
                else:
                    cuerpo_figura += "<sin-imagen/> Docling no exportó la imagen de esta figura.\n"
                _escribir(carpeta / "recursos" / "figuras" / f"{r['id']}.md", {**base, **extra}, cuerpo_figura)
                figuras.append({**r, "seccion": ficheros[-1]["fichero"], "imagen": bool(imagen)})

    if a["bibliografia"]:
        entradas = "\n".join(f'- <entrada clave="{r["clave"]}">{r["texto"]}</entrada>' for r in a["bibliografia"])
        _escribir(
            carpeta / "recursos" / "bibliografia.md",
            {"id": f"{nombre}#bibliografia", "type": "bibliografia", "title": "Bibliografía", "documento": nombre,
             "entradas": len(a["bibliografia"]), "autor_anio": a["autor_anio"], "generated": generado},
            f"# Bibliografía\n\n{entradas}",
        )

    titulo = next((limpiar_titulo(b["item"]["text"]) for s in secciones for b in s["bloques"] if b["etiqueta"] == "title"), None)
    titulo = titulo or next((s["titulo"] for s in secciones if s["titulo"]), nombre)
    resumen = next((s for s, c in zip(secciones, contexto, strict=True) if c["tipo"] == "resumen"), None)
    descripcion = _primera_frase(
        next((b["item"]["text"] for b in resumen["bloques"] if b["etiqueta"] == "text"), titulo) if resumen else titulo
    )
    indice_contenidos = "\n".join(
        f"{'  ' * max(0, f['profundidad'] - 1)}- [{f['titulo'] or '(preliminares)'}](contenidos/{f['fichero']})"
        + (f" · págs. {f['paginas'][0]}–{f['paginas'][-1]}" if len(f["paginas"]) > 1 else f" · pág. {f['paginas'][0]}" if f["paginas"] else "")
        for f in ficheros
    )
    lista_tablas = "\n".join(f"- [{t['leyenda'] or t['id']}](recursos/tablas/{t['id']}.md) · en [{t['seccion']}](contenidos/{t['seccion']})" for t in tablas)
    lista_figuras = "\n".join(
        f"- [{f['leyenda'] or f['id']}](recursos/figuras/{f['id']}.md){'' if f['imagen'] else ' · sin imagen'}" for f in figuras
    )
    partes = [
        f"# {titulo}",
        f"Carpeta generada por {GENERADOR} desde la estructura del documento; no se edita a mano. "
        f"El original es [{fichero}]({fichero}). Las citas se escriben contra la estructura, con la página que dice "
        "cada fichero.",
        f"## Contenidos\n\n{indice_contenidos}",
    ]
    if tablas:
        partes.append(f"## Tablas\n\n{lista_tablas}")
    if figuras:
        partes.append(f"## Figuras\n\n{lista_figuras}")
    if a["bibliografia"]:
        partes.append(f"## Bibliografía\n\n[{len(a['bibliografia'])} entradas](recursos/bibliografia.md)")
    if estructura.get("avisos"):
        partes.append("## Avisos de la segmentación\n\n" + "\n".join(f"- {x}" for x in estructura["avisos"]))
    cabecera_indice = {
        "id": nombre,
        "type": "documento",
        "title": titulo,
        "description": descripcion,
        "original": {"fichero": fichero, "sha256": estructura.get("original_sha256"), "paginas": len(estructura.get("paginas", []))},
        "representacion": {**{k: v for k, v in origen.items() if k != "original_sha256"},
                           "segmentador": estructura.get("segmentador", f"kbol-di/generica {VERSION_SEGMENTADOR}")},
        "contenidos": len(ficheros),
        "tablas": len(tablas),
        "figuras": len(figuras),
        "referencias": len(a["bibliografia"]),
        "generated": generado,
    }
    _escribir(carpeta / "index.md", cabecera_indice, "\n\n".join(partes))
    return {"carpeta": str(carpeta), "contenidos": len(ficheros), "tablas": len(tablas), "figuras": len(figuras),
            "figuras_sin_imagen": sum(1 for f in figuras if not f["imagen"]), "referencias": len(a["bibliografia"])}


def destino_por_defecto(almacen: Path) -> Path:
    """Junto al almacén: `<estado de la instalación>/documentos`."""
    return Path(almacen).parent / "documentos"


def proyectar_en_almacen(
    huella_estructura: str,
    nombre: str,
    almacen: Path,
    destino: Path | None = None,
    markdown: str | None = None,
    markdown_sha256: str | None = None,
) -> dict:
    estructura = json.loads(leer(huella_estructura, almacen))
    if not estructura.get("docling_sha256"):
        raise ValueError("la estructura no dice de qué DoclingDocument deriva")
    doc = json.loads(leer(estructura["docling_sha256"], almacen))
    original = leer(estructura["original_sha256"], almacen)
    meta_ruta = Path(almacen) / "meta" / f"{estructura['original_sha256']}.json"
    origenes = json.loads(meta_ruta.read_text(encoding="utf-8")).get("origenes", []) if meta_ruta.exists() else []
    nombre_original = Path(str(origenes[0]).split("?")[0]).name if origenes else f"{nombre}.pdf"
    return proyectar(doc, estructura, original, nombre_original, nombre, destino or destino_por_defecto(almacen),
                     estructura_sha256=huella_estructura, markdown=markdown, markdown_sha256=markdown_sha256)
