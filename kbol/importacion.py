"""Guarda de la importación de un registro heredado: traducir el formato sin añadir contenido ni significado.

Una importación es correcta si el registro propuesto dice lo mismo que su heredado de la base y nada más:

- el cuerpo es el heredado, las mismas palabras en el mismo orden, salvo las marcas de cláusula que lo envuelven y
  una sección final «Procedencia heredada», que se regenera desde sus campos y tiene que coincidir sin contar los
  espacios en blanco (solo su línea de origen y un bloque YAML con campos del heredado y su mismo valor);
- si además conserva las líneas del heredado, las marcas solo caen entre líneas; si las redistribuye
  (`redistribuye`), una marca puede partir una frase y cambiar lo que rige en cada cláusula, así que quien
  integra la trata como decisiva;
- el título, la descripción y el ámbito son los del heredado;
- ningún texto del registro es nuevo: cada cadena aparece en el archivo heredado o es uno de los textos fijos de la
  migración («sin extraer…», «no consta…», el alcance de las tareas); los IDs de las relaciones, también, salvo los
  hitos de un plan, que son los suyos.

No juzga si la traducción es la mejor: eso lo revisa quien hace la migración. Impide que se cuele contenido.
"""

import re

import yaml

from .core import ErrorDeFormato, parse

SIN_EXTRAER = "sin extraer"
NO_CONSTA = "no consta en el registro heredado"
ALCANCE_TAREAS = "las tareas del cuerpo"
TITULO_PROCEDENCIA = "## Procedencia heredada"
# Campos que no se comparan como texto: identidad y forma (los valida el esquema), proyecciones y la política de la
# instalación (rol que autoriza y responsable), que la migración asigna y la persona aprueba.
SIN_TEXTO = frozenset(
    {"id", "type", "clase", "estado", "autor", "eventos", "sources", "autorizado_por", "responsable", "title"}
)
SIN_TEXTO |= {"description", "ambito"}  # se comparan aparte, con el heredado
# Valores de vocabulario cerrado o identificadores locales: no son contenido.
CERRADOS = frozenset({"subtipo", "metodo", "tipo", "condicion", "criterio_id", "verificacion_id", "precision"})
_MARCA = re.compile(r'^\s*(<clausula id="[^"]+">|</clausula>)\s*$')
_PROCEDENCIA = re.compile(r"^## Procedencia heredada\s*$", re.MULTILINE)


def seccion_procedencia(ruta, campos):
    """La sección «Procedencia heredada» exacta para esos campos del heredado; la usa quien migra y la guarda."""
    texto = f"{TITULO_PROCEDENCIA}\n\nImportado de `{ruta}`."
    if campos:
        bloque = yaml.safe_dump(campos, allow_unicode=True, sort_keys=True, default_flow_style=False, width=10**6)
        texto += f"\n\n```yaml\n{bloque}```"
    return texto + "\n"


def _normal(texto):
    """El texto sin tener en cuenta los espacios en blanco: las marcas piden líneas en blanco alrededor y una
    partición puede redistribuir saltos de línea, pero ninguna palabra cambia."""
    return " ".join(texto.split())


def _lineas(texto):
    return [" ".join(linea.split()) for linea in texto.replace("\r\n", "\n").split("\n") if linea.strip()]


def redistribuye(cuerpo, texto_heredado):
    """True si el cuerpo importado tiene las palabras del heredado pero no sus líneas: una marca parte una línea."""
    try:
        _, cuerpo_heredado = parse(texto_heredado)
    except ErrorDeFormato:
        return True
    antes, _ = _partes(cuerpo)
    sin = [linea for linea in antes.split("\n") if not _MARCA.match(linea)]
    return _lineas("\n".join(sin)) != _lineas(cuerpo_heredado)


def _partes(cuerpo):
    m = _PROCEDENCIA.search(cuerpo)
    return (cuerpo[: m.start()], cuerpo[m.start() :]) if m else (cuerpo, None)


def _sin_marcas(texto):
    return _normal("\n".join(linea for linea in texto.split("\n") if not _MARCA.match(linea)))


def _procedencia(seccion, ruta, meta):
    """None si la sección es exactamente la regenerada desde sus campos; si no, el motivo."""
    lineas = seccion.replace("\r\n", "\n").rstrip("\n").split("\n")
    campos = {}
    if "```yaml" in lineas:
        i = lineas.index("```yaml")
        if lineas.count("```yaml") != 1 or lineas[-1] != "```" or lineas.count("```") != 1:
            return "el bloque YAML de la procedencia no tiene la forma esperada"
        try:
            campos = yaml.safe_load("\n".join(lineas[i + 1 : -1]))
        except yaml.YAMLError:
            return "el bloque YAML de la procedencia es ilegible"
        if not isinstance(campos, dict):
            return "el bloque YAML de la procedencia no es un mapa de campos"
    for k, v in campos.items():
        if k not in meta or meta[k] != v:
            return f"la procedencia dice {k!r} con un valor que el heredado no tiene"
    if _normal(seccion) != _normal(seccion_procedencia(ruta, campos)):
        return "la procedencia lleva texto que no es su línea de origen ni sus campos"
    return None


def _cadenas(valor, clave=None):
    if isinstance(valor, str):
        yield clave, valor
    elif isinstance(valor, dict):
        for k, v in valor.items():
            yield from _cadenas(v, k)
    elif isinstance(valor, list):
        for v in valor:
            yield from _cadenas(v, clave)


def _fija(texto):
    return texto.startswith((SIN_EXTRAER, NO_CONSTA)) or texto == ALCANCE_TAREAS


def comprobar(registro, cuerpo, texto_heredado, ruta):
    """Lista de motivos por los que la importación no es una traducción fiel; vacía si lo es."""
    try:
        meta, cuerpo_heredado = parse(texto_heredado)
    except ErrorDeFormato as exc:
        return [f"el heredado de la base es ilegible: {exc}"]
    motivos = []
    if registro.get("title") != meta.get("title"):
        motivos.append("la importación cambia title")
    if registro.get("description") != meta.get("description", meta.get("title")):
        motivos.append("la importación cambia description")
    if "ambito" in meta and registro.get("ambito") != meta["ambito"]:
        motivos.append("la importación cambia ambito")
    antes, seccion = _partes(cuerpo)
    if _sin_marcas(antes) != _normal(cuerpo_heredado):
        motivos.append("el cuerpo importado no es el heredado salvo las marcas de cláusula")
    if seccion is not None:
        motivo = _procedencia(seccion, ruta, meta)
        if motivo:
            motivos.append(motivo)
    propio = registro.get("id", "")
    # Los valores del heredado ya interpretados: un texto entre comillas dobles de YAML lleva escapes (\") que no
    # aparecen tal cual en el archivo, pero es contenido del heredado.
    valores = {texto for _, texto in _cadenas(meta)}
    for clave, texto in _cadenas({k: v for k, v in registro.items() if k not in SIN_TEXTO}):
        if clave in CERRADOS or not texto or _fija(texto):
            continue
        if clave == "hitos" and re.fullmatch(rf"{re.escape(propio)}-H\d+", texto):
            continue
        if texto.startswith(f"{propio}#"):
            continue  # una cláusula del propio registro (la `por` de una modificación)
        if texto not in valores and texto.split("#", 1)[0] not in texto_heredado:
            motivos.append(f"{clave}: {texto[:60]!r} no está en el heredado: la importación no añade contenido")
    return motivos
