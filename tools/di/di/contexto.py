"""Contexto documental de un PDF: lo que dice dónde está cada cosa dentro del documento, sin interpretar su contenido.

Cuatro piezas, todas sacadas de lo que Docling ya entrega o del propio texto:

- `jerarquia`: número, profundidad y padre de cada título, a partir de su numeración («5.3» cuelga de «5»; «A.1»,
  de «A»). Docling marca todos los títulos con el mismo nivel, así que la numeración es la única fuente.
- `tipo_de_parte`: resumen, introducción, método, resultados, referencias… por las primeras palabras del título.
- `celdas_de_tabla`: cada dato de una tabla con las cabeceras de su columna y la etiqueta de su fila, resueltas a
  través de las celdas combinadas.
- `referencias_citadas`: las llamadas a la bibliografía de un texto, numéricas («[15, 21]», «[3-5]») o de autor y
  año («(Feng et al. 2021)»).

Nada de esto decide qué afirma el documento: es el andamio sobre el que se escriben después hechos y relaciones.
"""

import re
import unicodedata

_NUMERO = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+\S")
_LETRA = re.compile(r"^\s*([A-H](?:\.\d+)*)\.?\s+\S")
_TIPOS = (
    ("resumen", ("abstract", "resumen")),
    ("introduccion", ("introduction", "introduccion")),
    ("trabajos_relacionados", ("related work", "background", "state of the art", "estado del arte", "antecedentes",
                               "trabajos relacionados", "literature review", "revision de la literatura")),
    ("metodo", ("method", "methodology", "proposed", "approach", "metodo", "metodolog", "propuesta")),
    ("experimentos", ("experiment", "evaluation", "experimental", "evaluacion")),
    ("resultados", ("result", "discussion", "resultado", "discusion")),
    ("conclusiones", ("conclu",)),
    ("referencias", ("references", "bibliography", "referencias", "bibliografia")),
    ("anexo", ("appendix", "appendices", "supplementary", "anexo", "apendice")),
    ("agradecimientos", ("acknowledg", "agradecimiento")),
)
_CITA_NUMERICA = re.compile(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]")
_APELLIDO = r"[A-ZÁÉÍÓÚÑ][\w'’-]+"
_OTROS = rf"(?:\s+et\s+al\.?|\s+(?:and|&|y)\s+{_APELLIDO})?"
_PARENTESIS = re.compile(r"\(([^()]*\d{4}[a-z]?[^()]*)\)")
_PARTE_PARENTESIS = re.compile(rf"^\s*(?:e\.g\.,?\s*|see\s+|cf\.\s*|véase\s+)?({_APELLIDO}){_OTROS},?\s+(\d{{4}}[a-z]?)\s*$")
_NARRATIVA = re.compile(rf"({_APELLIDO}){_OTROS}\s+\((\d{{4}}[a-z]?)\)")
_ANIO_ENTRADA = re.compile(r"\((\d{4}[a-z]?)\)|\b(\d{4}[a-z]?)\.")


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def limpiar_titulo(titulo: str | None) -> str | None:
    """El título sin caracteres de control (algunas editoriales meten un \\x07 tras el número) ni espacios de más."""
    if titulo is None:
        return None
    return re.sub(r"\s+", " ", "".join(ch for ch in titulo if unicodedata.category(ch) != "Cc" or ch.isspace())).strip()


def _sin_numero(titulo: str) -> str:
    return re.sub(r"^\s*(?:\d+(?:\.\d+)*|[A-H](?:\.\d+)*)\.?\s+", "", limpiar_titulo(titulo) or "")


def tipo_de_parte(titulo: str | None) -> str | None:
    """Tipo de parte por las primeras palabras del título, sin su numeración; None si no es ninguna conocida.

    Se compara sin espacios, porque Docling a veces pega palabras de un título («RELATEDWORK»). Un título que
    habla de conclusiones lo es aunque empiece por otra cosa («Discussion and Conclusion»).
    """
    if not titulo:
        return None
    inicio = re.sub(r"\s+", "", _sin_tildes(_sin_numero(titulo)))
    if "conclu" in inicio and not inicio.startswith(("references", "referencias", "bibliograf")):
        return "conclusiones"
    for tipo, claves in _TIPOS:
        if any(inicio.startswith(c.replace(" ", "")) for c in claves):
            return tipo
    return None


def jerarquia(titulos: list[str | None]) -> list[dict]:
    """Número, profundidad y padre (índice en la lista) de cada título.

    Un título sin numeración está en el primer nivel. Una letra sola («A», «B») solo numera un anexo: vale si lleva
    subnumeración («A.1») o si ya ha pasado la bibliografía o un anexo; si no, «A Novel Approach» sería el anexo A.
    Un número cuyo padre no aparece cuelga de la raíz con la profundidad que indica su numeración.

    Un número de primer nivel que no avanza respecto al anterior («1.» después de «3.3») no es una sección sino un
    apartado numerado que Docling tomó por título: pierde el número, cuelga de la última sección numerada y se marca
    con `retrocede`.
    """
    salida: list[dict] = []
    tras_bibliografia = False
    ultimo_principal = 0
    ultima_numerada = None
    for titulo in map(limpiar_titulo, titulos):
        numero = None
        if titulo:
            if (m := _NUMERO.match(titulo)) or (m := _LETRA.match(titulo)) and ("." in m.group(1) or tras_bibliografia):
                numero = m.group(1)
            if tipo_de_parte(titulo) in ("referencias", "anexo"):
                tras_bibliografia = True
        if numero and numero.isdigit():
            if int(numero) <= ultimo_principal and ultima_numerada is not None:
                padre = ultima_numerada
                salida.append({"numero": None, "profundidad": salida[padre]["profundidad"] + 1, "padre": padre,
                               "retrocede": True})
                continue
            ultimo_principal = int(numero)
        padre = None
        if numero and "." in numero:
            prefijo = numero.rsplit(".", 1)[0]
            padre = next((i for i in range(len(salida) - 1, -1, -1) if salida[i]["numero"] == prefijo), None)
        profundidad = (numero.count(".") + 1) if numero else (1 if titulo else 0)
        if numero:
            ultima_numerada = len(salida)
        salida.append({"numero": numero, "profundidad": profundidad, "padre": padre})
    return salida


def _es_fila_de_cabecera(unicas: list[dict]) -> bool:
    con_texto = [c for c in unicas if (c.get("text") or "").strip()]
    return bool(con_texto) and 2 * sum(1 for c in con_texto if c.get("column_header")) >= len(con_texto)


_DATO = re.compile(r"^[\d\s.,:;±%()+\-–/x×*]+$")


def _primera_fila_sin_marcar(grid: list[list]) -> bool:
    """Docling no marcó ninguna cabecera, la primera fila es todo texto y alguna de las siguientes trae números."""
    if not grid or any(c and c.get("column_header") for fila in grid for c in fila):
        return False
    primera = [(c.get("text") or "").strip() for c in grid[0] if c]
    if not any(primera) or any(_DATO.match(t) for t in primera if t):
        return False
    return any(_DATO.match((c.get("text") or "").strip()) for fila in grid[1:] for c in fila if c and (c.get("text") or "").strip())


def _origen(celda: dict) -> tuple:
    return (celda.get("start_row_offset_idx"), celda.get("start_col_offset_idx"))


def celdas_de_tabla(tabla: dict) -> list[dict]:
    """Cada dato de la tabla con la página, su posición, las cabeceras de su columna y la etiqueta de su fila.

    Una fila es de cabecera si la mayoría de sus celdas lo son (Docling a veces no marca alguna); si Docling no
    marcó ninguna, lo es la primera cuando es todo texto y debajo hay números. Las cabeceras de
    una columna son las de las filas de cabecera seguidas que preceden al dato: una tabla con dos bloques, cada uno
    con su cabecera, se resuelve por bloques. La etiqueta de fila son las celdas marcadas como cabecera de fila o,
    si no hay ninguna, la primera columna.
    """
    grid = tabla.get("data", {}).get("grid") or []
    pagina = tabla["prov"][0]["page_no"] if tabla.get("prov") else None
    primera_es_cabecera = _primera_fila_sin_marcar(grid)
    bloque: list[list[dict | None]] = []
    previa_de_datos = True
    vistas: set[tuple] = set()
    salida = []
    for fila in grid:
        unicas = []
        for celda in fila:
            if celda is not None and all(_origen(celda) != _origen(u) for u in unicas):
                unicas.append(celda)
        if _es_fila_de_cabecera(unicas) or (primera_es_cabecera and fila is grid[0]):
            if previa_de_datos:
                bloque = []
            bloque.append(fila)
            previa_de_datos = False
            continue
        previa_de_datos = True
        de_fila = [c for c in unicas if c.get("row_header") and (c.get("text") or "").strip()]
        columnas_etiqueta = {k for c in de_fila for k in range(c["start_col_offset_idx"], c["end_col_offset_idx"])}
        if de_fila:
            etiqueta = [c["text"].strip() for c in sorted(de_fila, key=lambda c: c["start_col_offset_idx"])]
        else:
            primera = fila[0] if fila and fila[0] is not None else None
            etiqueta = [primera["text"].strip()] if primera and (primera.get("text") or "").strip() else []
        for k, celda in enumerate(fila):
            if celda is None or not (celda.get("text") or "").strip() or _origen(celda) in vistas:
                continue
            vistas.add(_origen(celda))
            if k in columnas_etiqueta:
                continue
            cabeceras: list[str] = []
            anterior = None
            for cabecera in bloque:
                c = cabecera[k] if k < len(cabecera) else None
                if c is None or _origen(c) == anterior or not (c.get("text") or "").strip():
                    continue
                anterior = _origen(c)
                cabeceras.append(c["text"].strip())
            salida.append(
                {
                    "f": celda["start_row_offset_idx"],
                    "c": celda["start_col_offset_idx"],
                    "p": pagina,
                    "texto": celda["text"].strip(),
                    "cabeceras": cabeceras,
                    "fila": [] if (not de_fila and k == 0) else etiqueta,
                }
            )
    return salida


def _clave_autor(apellido: str, anio: str) -> str:
    return f"{_sin_tildes(apellido)} {anio}"


def referencias_citadas(texto: str, autor_anio: bool = False, maximo: int | None = None) -> list[str]:
    """Claves de bibliografía que cita un texto, en orden de aparición y sin repetir.

    Numéricas: «[2]», «[15, 21]», «[3-5]»; un corchete con un 0, o con un número mayor que `maximo` (la última
    entrada de la bibliografía), no es una cita sino un intervalo o una lista de valores («[0, 1]», «[50, 100]»).
    Con `autor_anio`, «(Feng et al. 2021; Ma and Li 2022)» y «Wang et al. (2022a)», como «primer apellido año».
    """
    halladas: list[tuple[int, str]] = []
    if autor_anio:
        for m in _PARENTESIS.finditer(texto):
            for parte in m.group(1).split(";"):
                if p := _PARTE_PARENTESIS.match(parte):
                    halladas.append((m.start(), _clave_autor(p.group(1), p.group(2))))
        halladas.extend((m.start(), _clave_autor(m.group(1), m.group(2))) for m in _NARRATIVA.finditer(texto))
    else:
        for m in _CITA_NUMERICA.finditer(texto):
            numeros = []
            for trozo in re.split(r"\s*,\s*", m.group(1)):
                if (r := re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", trozo)) and 0 <= int(r.group(2)) - int(r.group(1)) <= 50:
                    numeros.extend(str(n) for n in range(int(r.group(1)), int(r.group(2)) + 1))
                else:
                    numeros.extend(re.findall(r"\d+", trozo))
            if "0" not in numeros and (maximo is None or all(int(n) <= maximo for n in numeros)):
                halladas.extend((m.start(), n) for n in numeros)
    vistas, salida = set(), []
    for _, clave in sorted(halladas, key=lambda par: par[0]):
        if clave not in vistas:
            vistas.add(clave)
            salida.append(clave)
    return salida


def clave_de_entrada(texto: str, marcador: str | None) -> tuple[str | None, bool]:
    """(clave, es_numerica) de una entrada de bibliografía: «[17]» o «17.» por su marcador, o «primer apellido año»."""
    if m := re.fullmatch(r"\s*\[?(\d+)[\].]?\s*", marcador or ""):
        return m.group(1), True
    if m := re.match(r"^\s*\[(\d+)\]", texto):
        return m.group(1), True
    apellido = re.match(rf"^\s*({_APELLIDO})", texto)
    anio = _ANIO_ENTRADA.search(texto)
    if apellido and anio:
        return _clave_autor(apellido.group(1), anio.group(1) or anio.group(2)), False
    return None, False
