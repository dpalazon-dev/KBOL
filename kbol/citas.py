"""Resolutor de citas: comprueba que cada `sources[]` de un registro apunta a algo que existe en la versión citada.

Para un PDF, la cita combina una unidad lógica (`norma-v1`) y una página con región opcional (`pdf-v1`), y se
resuelve contra la representación `estructura-v1` que fija `representacion_id`. Para un texto, se resuelven líneas
(`lines-v1`, o las anclas del formato heredado) contra el blob de la revisión anclada. El núcleo no lee PDF: la
página existe si la estructura, derivada de ese original por su huella, la declara.

Un documento sin páginas (Word, hoja de cálculo, HTML) se cita por líneas de su representación en texto: con
`representacion_id`, las líneas se resuelven contra esa representación, que debe ser de texto y derivar del
original citado, directamente o a través de otras derivaciones. Sin `representacion_id`, contra el original.

Estados: `resuelta`; `rota` (huella distinta, página, unidad o texto que no están); `inconsistente` (la unidad no
está en la página o la región citadas); `ambigua` (la unidad aparece más de una vez); `no_comprobable` (falta el
original o la representación en esta máquina, o el ancla no tiene perfil: integridad sin comprobar, no un fallo).
"""

import hashlib
import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .core import ErrorDeFormato, parse
from .localizador import Cita, Lineas, LocalizadorInvalido, Pagina, parsear
from .snapshot import entorno_git

ESTADOS = ("resuelta", "rota", "inconsistente", "ambigua", "no_comprobable")
_COMILLAS = str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'"})
_ESPACIOS = re.compile(r"\s+")


@dataclass(frozen=True)
class Resultado:
    estado: str
    motivo: str


def normalizar(texto: str) -> str:
    """Forma comparable de un texto: NFKC, sin guion de partición ni guion blando, comillas rectas, minúsculas."""
    t = unicodedata.normalize("NFKC", texto).replace("­", "")
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    return _ESPACIOS.sub(" ", t.translate(_COMILLAS)).strip().lower()


def _contiene(texto: str, literal: str) -> str | None:
    """`exacta`, `sin espacios` o None, según aparezca la cita literal normalizada."""
    t, lit = normalizar(texto), normalizar(literal)
    if lit in t:
        return "exacta"
    if lit.replace(" ", "") in t.replace(" ", ""):
        return "sin espacios"
    return None


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _solapan(a, b) -> bool:
    ax0, ay0, ax1, ay1 = (float(v) for v in a)
    bx0, by0, bx1, by1 = (float(v) for v in b)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def resolver_pdf(
    cita: Cita, *, sha256_original: str, ruta_original: Path | None, estructura: dict, literal: str | None
) -> Resultado:
    if estructura.get("perfil") != "estructura-v1":
        return Resultado("rota", "la representación no es estructura-v1")
    if estructura.get("original_sha256") != sha256_original:
        return Resultado("rota", "la representación no deriva de este original (huella distinta)")
    if not isinstance(cita.fisico, Pagina):
        return Resultado("rota", "la cita de un PDF necesita la página física (pdf-v1)")
    pagina = cita.fisico
    if pagina.p not in {pg["p"] for pg in estructura.get("paginas", [])}:
        return Resultado("rota", f"la página {pagina.p} no existe en la representación")

    if cita.logico is not None:
        clave = cita.logico.clave()
        unidades = [u for u in estructura.get("unidades", []) if u["clave"] == clave]
        if not unidades:
            return Resultado("rota", f"la unidad {clave} no existe en la representación")
        if len(unidades) > 1:
            return Resultado("ambigua", f"la unidad {clave} aparece {len(unidades)} veces")
        (unidad,) = unidades
        if pagina.p not in unidad["paginas"]:
            return Resultado(
                "inconsistente", f"la unidad {clave} está en {unidad['paginas']}, no en la página {pagina.p}"
            )
        regiones = [r["r"] for r in unidad.get("regiones", []) if r["p"] == pagina.p]
        if pagina.region and regiones and not any(_solapan(pagina.region, r) for r in regiones):
            return Resultado("inconsistente", f"la región citada no toca la unidad {clave} en la página {pagina.p}")
        texto = unidad["texto"]
    else:
        texto = "\n".join(u["texto"] for u in estructura.get("unidades", []) if pagina.p in u["paginas"])

    notas = []
    if literal:
        modo = _contiene(texto, literal)
        if modo is None:
            return Resultado("rota", "la cita literal no aparece en la unidad citada")
        if modo == "sin espacios":
            notas.append("la cita literal coincide sin espacios (palabras partidas en la representación)")

    if ruta_original is None or not Path(ruta_original).exists():
        return Resultado("no_comprobable", "; ".join(["estructura conforme; original no disponible", *notas]))
    if _sha256(Path(ruta_original).read_bytes()) != sha256_original:
        return Resultado("rota", "el original del almacén no tiene la huella de la fuente")
    return Resultado("resuelta", "; ".join(notas) or "resuelta")


def resolver_lineas(cita: Cita, *, texto: str, sha256_esperado: str, literal: str | None = None) -> Resultado:
    prefijo = "ancla heredada; " if cita.heredada else ""
    if not isinstance(cita.fisico, Lineas) or cita.logico is not None:
        return Resultado("rota", "una fuente de texto se cita por líneas")
    if _sha256(texto.encode("utf-8")) != sha256_esperado:
        return Resultado("rota", prefijo + "el texto no tiene la huella de la fuente")
    lineas = texto.splitlines()
    ini, fin = cita.fisico.inicio, cita.fisico.fin
    if fin > len(lineas):
        return Resultado("rota", prefijo + f"líneas {ini}-{fin} fuera del texto ({len(lineas)} líneas)")
    if literal and _contiene("\n".join(lineas[ini - 1 : fin]), literal) is None:
        return Resultado("rota", prefijo + "la cita literal no aparece en esas líneas")
    return Resultado("resuelta", prefijo + "resuelta")


def _leer_ubicacion(raiz: Path, ubicacion: str, almacen: Path | None) -> bytes | None:
    if ubicacion.startswith("almacen:"):
        if almacen is None:
            return None
        ruta = Path(almacen) / ubicacion[len("almacen:") :]
        return ruta.read_bytes() if ruta.is_file() else None
    if ubicacion.startswith("git:"):
        _, rev, ruta = ubicacion.split(":", 2)
        p = subprocess.run(["git", "-C", str(raiz), "show", f"{rev}:{ruta}"], capture_output=True, env=entorno_git())
        return p.stdout if p.returncode == 0 else None
    return None


def _registros(raiz: Path, carpetas: list[str]):
    for carpeta in carpetas:
        if not (raiz / carpeta).is_dir():
            raise FileNotFoundError(f"no existe la carpeta: {carpeta}")
        for ruta in sorted((raiz / carpeta).rglob("*.md")):
            try:
                cabecera, _ = parse(ruta.read_text(encoding="utf-8"))
            except (ErrorDeFormato, UnicodeDecodeError):
                continue
            if cabecera.get("id"):
                yield ruta, cabecera


def _deriva_de(fuentes: dict, derivada_id: str, original_id: str, limite: int = 8) -> bool:
    """Si la derivación sale del original siguiendo `derivada_de`, sin ciclos y con una profundidad acotada."""
    pendientes, vistas = [(derivada_id, 0)], set()
    while pendientes:
        actual, nivel = pendientes.pop()
        if actual in vistas or nivel > limite:
            continue
        vistas.add(actual)
        padres = (fuentes.get(actual) or {}).get("derivada_de") or []
        if original_id in padres:
            return True
        pendientes.extend((p, nivel + 1) for p in padres if isinstance(p, str))
    return False


def _resolver_lineas_en_representacion(raiz, fuentes, src, cita, fuente, datos_original, almacen) -> Resultado:
    derivada = fuentes.get(src["representacion_id"])
    if derivada is None:
        return Resultado("rota", "la representación citada no es una fuente existente")
    if not _deriva_de(fuentes, derivada["id"], fuente["id"]):
        return Resultado("rota", "la representación no deriva del original citado")
    formato = str(derivada.get("formato") or "text/")
    if not formato.startswith("text/"):
        return Resultado("rota", f"una cita por líneas necesita una representación de texto, no {formato}")
    rep = _leer_ubicacion(raiz, derivada.get("ubicacion", ""), almacen)
    if rep is None:
        return Resultado("no_comprobable", "representación no disponible en esta máquina")
    try:
        texto = rep.decode("utf-8")
    except UnicodeDecodeError:
        return Resultado("rota", "la representación no es texto UTF-8")
    r = resolver_lineas(cita, texto=texto, sha256_esperado=derivada.get("sha256"), literal=src.get("contexto"))
    if r.estado != "resuelta":
        return r
    if datos_original is None:
        return Resultado("no_comprobable", "representación conforme; original no disponible")
    if _sha256(datos_original) != fuente.get("sha256"):
        return Resultado("rota", "el original no tiene la huella de la fuente")
    return r


def _resolver_fuente(raiz, fuentes, src, almacen) -> Resultado:
    fuente = fuentes.get(src.get("resource"))
    if fuente is None:
        return Resultado("rota", f"la fuente {src.get('resource')} no existe")
    try:
        cita = parsear(src.get("ancla", ""))
    except LocalizadorInvalido as exc:
        return Resultado("no_comprobable", f"ancla sin perfil: {exc}")
    sha_fuente = fuente.get("sha256")
    if src.get("hash") and src["hash"] != sha_fuente:
        return Resultado("rota", "la huella de la cita no es la de la fuente")
    datos = _leer_ubicacion(raiz, fuente.get("ubicacion", ""), almacen)
    if isinstance(cita.fisico, Lineas) and src.get("representacion_id"):
        return _resolver_lineas_en_representacion(raiz, fuentes, src, cita, fuente, datos, almacen)
    if isinstance(cita.fisico, Lineas):
        if datos is None:
            return Resultado("no_comprobable", "texto de la fuente no disponible")
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError:
            return Resultado("rota", "la fuente no es texto UTF-8")
        return resolver_lineas(cita, texto=texto, sha256_esperado=sha_fuente, literal=src.get("contexto"))
    derivada = fuentes.get(src.get("representacion_id"))
    if derivada is None:
        return Resultado("rota", "la cita de un PDF necesita representacion_id hacia una fuente existente")
    est_bytes = _leer_ubicacion(raiz, derivada.get("ubicacion", ""), almacen)
    if est_bytes is None:
        return Resultado("no_comprobable", "representación no disponible en esta máquina")
    if _sha256(est_bytes) != derivada.get("sha256"):
        return Resultado("rota", "la representación no tiene la huella de su fuente derivada")
    ruta_original = None
    if datos is not None and fuente.get("ubicacion", "").startswith("almacen:"):
        ruta_original = Path(almacen) / fuente["ubicacion"][len("almacen:") :]
    return resolver_pdf(
        cita,
        sha256_original=sha_fuente,
        ruta_original=ruta_original,
        estructura=json.loads(est_bytes),
        literal=src.get("contexto"),
    )


def comprobar(raiz: Path, carpetas: list[str], almacen: Path | None) -> dict:
    """Resuelve cada `sources[]` de los registros de las carpetas; una fila por cita y el recuento por estado."""
    raiz = Path(raiz)
    registros = list(_registros(raiz, carpetas))
    fuentes = {c["id"]: c for _, c in registros if str(c["id"]).startswith("F-")}
    filas = []
    for ruta, cabecera in registros:
        for src in cabecera.get("sources") or []:
            if not isinstance(src, dict):
                continue
            r = _resolver_fuente(raiz, fuentes, src, almacen)
            filas.append(
                {
                    "registro": cabecera["id"],
                    "ruta": ruta.relative_to(raiz).as_posix(),
                    "source": src.get("id"),
                    "fuente": src.get("resource"),
                    "ancla": src.get("ancla"),
                    "estado": r.estado,
                    "motivo": r.motivo,
                }
            )
    recuento = {e: sum(1 for f in filas if f["estado"] == e) for e in ESTADOS}
    return {"filas": filas, "recuento": recuento}
