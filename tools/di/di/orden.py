"""Orden de lectura de los bloques de un DoclingDocument cuando Docling lo deja mal.

Trabaja página a página con la posición de cada bloque de primer nivel, sin contar cabeceras ni pies. Un bloque que
cruza el centro de la página separa bandas, salvo un renglón centrado que comparte altura con otros bloques, que se
lee como uno más de su renglón; dentro de una banda, si hay bloques a izquierda y derecha que se solapan
en altura y alguno ocupa más de un par de líneas (dos columnas), se lee la columna izquierda y después la derecha;
si no, de arriba abajo, y de izquierda a derecha dentro de un mismo renglón. Una página cuya maquetación no encaja
(un bloque alto y estrecho que cruza el centro junto a otros, como una tercera columna) se deja como la dio Docling.

No lee el contenido ni decide a qué sección pertenece nada: solo recoloca, y cada página recolocada queda en los
avisos. Que el resultado sea mejor que el de Docling se mide, no se supone.
"""

from .estructura import _region

_MARGEN = 0.02
_ANCHO_SEPARADOR = 0.45
# Altura, en fracción de página, por debajo de la cual un bloque es una o dos líneas y no una columna.
_ALTO_LINEA = 0.04
_MOBILIARIO = {"page_header", "page_footer"}


def _posicion(doc: dict, item: dict) -> tuple[int, list[float]] | None:
    """Página y región del bloque; None si no tiene o si es cabecera o pie, que no cuentan para la maquetación."""
    if not item.get("prov") or item.get("label") in _MOBILIARIO:
        return None
    prov = item["prov"][0]
    tam = doc["pages"][str(prov["page_no"])]["size"]
    return prov["page_no"], _region(prov["bbox"], tam["width"], tam["height"])


def _solapan_en_altura(a: list[float], b: list[float]) -> bool:
    return a[1] < b[3] and b[1] < a[3]


def _de_arriba_abajo(banda: list[tuple[dict, list[float]]]) -> list[tuple[dict, list[float]]]:
    """Por altura; los bloques de un mismo renglón (el centro de uno cae en la altura del primero), de izquierda a derecha."""
    renglones: list[list[tuple[dict, list[float]]]] = []
    for par in sorted(banda, key=lambda p: p[1][1]):
        centro = (par[1][1] + par[1][3]) / 2
        if renglones and renglones[-1][0][1][1] <= centro <= renglones[-1][0][1][3]:
            renglones[-1].append(par)
        else:
            renglones.append([par])
    return [par for renglon in renglones for par in sorted(renglon, key=lambda p: p[1][0])]


def _ordenar_pagina(bloques: list[tuple[dict, list[float]]]) -> list[dict] | None:
    """Los bloques de una página en orden de lectura, o None si la maquetación no encaja."""
    cruzan, columnas = [], []
    for bloque, r in bloques:
        cruza = r[0] < 0.5 - _MARGEN and r[2] > 0.5 + _MARGEN
        (cruzan if cruza else columnas).append((bloque, r))
    separadores = []
    for par in cruzan:
        s = par[1]
        if s[2] - s[0] >= _ANCHO_SEPARADOR or not any(_solapan_en_altura(s, c) for _, c in columnas):
            separadores.append(par)
        elif s[3] - s[1] < _ALTO_LINEA:
            columnas.append(par)  # un renglón centrado junto a otros, como el de una cabecera
        else:
            return None  # un bloque alto y estrecho en el centro: tercera columna u otra maquetación
    separadores.sort(key=lambda par: par[1][1])
    bandas: list[list[tuple[dict, list[float]]]] = [[] for _ in range(len(separadores) + 1)]
    for bloque, r in columnas:
        bandas[sum(1 for _, s in separadores if s[1] <= r[1])].append((bloque, r))
    salida: list[dict] = []
    for i, banda in enumerate(bandas):
        izquierda = [par for par in banda if par[1][2] <= 0.5 + _MARGEN]
        derecha = [par for par in banda if par[1][2] > 0.5 + _MARGEN]
        dos_columnas = any(
            _solapan_en_altura(a, b) and max(a[3] - a[1], b[3] - b[1]) >= _ALTO_LINEA
            for _, a in izquierda
            for _, b in derecha
        )
        orden = _de_arriba_abajo(izquierda) + _de_arriba_abajo(derecha) if dos_columnas else _de_arriba_abajo(banda)
        salida.extend(bloque for bloque, _ in orden)
        if i < len(separadores):
            salida.append(separadores[i][0])
    return salida


def refs_ordenadas(doc: dict) -> tuple[list[str], list[str]]:
    """Referencias de los elementos de primer nivel del cuerpo, con los grupos deshechos, en orden de lectura."""
    bloques = []

    def visitar(nodo):
        for hijo in nodo.get("children", []):
            _, tipo, indice = hijo["$ref"].split("/")
            item = doc[tipo][int(indice)]
            if tipo == "groups":
                visitar(item)
            else:
                bloques.append({"ref": hijo["$ref"], "item": item})

    visitar(doc["body"])
    ordenados, avisos = ordenar(doc, bloques)
    return [b["ref"] for b in ordenados], avisos


def ordenar(doc: dict, bloques: list[dict]) -> tuple[list[dict], list[str]]:
    """Los bloques recolocados y un aviso por cada página que cambia o que se deja sin tocar por no encajar.

    Un bloque sin posición viaja pegado al anterior. El orden entre páginas es el del número de página.
    """
    por_pagina: dict[int, list[tuple[dict, list[float]]]] = {}
    pegados: dict[int, list[dict]] = {}
    salida: list[dict] = []
    avisos: list[str] = []
    ultimo = None
    for bloque in bloques:
        pos = _posicion(doc, bloque["item"])
        if pos is not None:
            por_pagina.setdefault(pos[0], []).append((bloque, pos[1]))
            ultimo = bloque
        elif ultimo is None:
            salida.append(bloque)
        else:
            pegados.setdefault(id(ultimo), []).append(bloque)
    for pagina in sorted(por_pagina):
        original = [b for b, _ in por_pagina[pagina]]
        nuevo = _ordenar_pagina(por_pagina[pagina])
        if nuevo is None:
            avisos.append(f"página {pagina}: maquetación no reconocida; se conserva el orden de Docling")
            nuevo = original
        elif [b["ref"] for b in nuevo] != [b["ref"] for b in original]:
            movidos = sum(1 for a, b in zip(nuevo, original, strict=True) if a["ref"] != b["ref"])
            avisos.append(f"página {pagina}: orden de lectura corregido ({movidos} de {len(original)} bloques)")
        for bloque in nuevo:
            salida.append(bloque)
            salida.extend(pegados.get(id(bloque), []))
    return salida, avisos
