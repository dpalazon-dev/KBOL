"""Integridad de las fuentes: el contenido que hay en la `ubicacion` de cada fuente tiene su `sha256`.

Operación `integridad` del contrato («Integridad y actualización»): para cada registro de fuente dice si su contenido
`coincide`, está `alterada` o `ausente`, o si la comprobación no pudo hacerse (`no_comprobada`), con la causa. Se
comparan los bytes tal como están, sin normalizar saltos de línea. Tres formas de ubicación se comprueban:

- `almacen:sha256/<huella>`: el objeto del almacén direccionado por contenido que se indique;
- `git:<revisión de 40 caracteres>:<ruta>`: el blob de esa ruta en esa revisión del repositorio de la raíz;
- una ruta relativa a la raíz: el archivo del árbol de trabajo.

Una fuente está rota (`alterada` o `ausente`) solo cuando se pudo mirar y el contenido es otro o no está. Lo que no
se pudo mirar es `no_comprobada`, no una acusación: sin almacén, un objeto que no está en el almacén de esta máquina
(el almacén es estado local y no se sincroniza), una revisión que no está en este clon, una revisión sin anclar o
una ubicación de otra forma (una URL, una ruta absoluta).

No guarda nada: cada ejecución comprueba de nuevo, y la última comprobación válida de una fuente no se conserva.
"""

import hashlib
import re
import subprocess
from pathlib import Path

from .snapshot import cargar, entorno_git

ESTADOS = ("coincide", "alterada", "ausente", "no_comprobada")
ROTAS = ("alterada", "ausente")
_ALMACEN = re.compile(r"almacen:sha256/([0-9a-f]{64})")
_GIT = re.compile(r"git:([^:]+):(.+)", re.S)
_REVISION = re.compile(r"[0-9a-f]{40}")
_ESQUEMA = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")  # https:, s3:; una sola letra sería una unidad de Windows
_UNIDAD = re.compile(r"[A-Za-z]:[\\/]")


def _git(raiz, *args):
    return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, env=entorno_git())


def _comparar(datos, sha256, que):
    if hashlib.sha256(datos).hexdigest() == sha256:
        return "coincide", None
    return "alterada", f"{que} no tiene la huella de la fuente"


def _en_almacen(huella, sha256, almacen):
    if huella != sha256:
        return "alterada", "la ubicación nombra una huella que no es la de la fuente"
    if almacen is None:
        return "no_comprobada", "no se indicó el almacén"
    objeto = Path(almacen) / "sha256" / huella
    if not objeto.is_file():
        return "no_comprobada", "el objeto no está en el almacén de esta máquina"
    try:
        datos = objeto.read_bytes()
    except OSError as exc:
        return "no_comprobada", f"no se pudo leer el objeto del almacén: {exc}"
    return _comparar(datos, sha256, "el objeto del almacén")


def _en_git(raiz, revision, ruta, sha256):
    if not _REVISION.fullmatch(revision):
        return "no_comprobada", "la revisión no está anclada: se necesita el SHA completo de un commit"
    if _git(raiz, "cat-file", "-e", f"{revision}^{{commit}}").returncode != 0:
        superficial = _git(raiz, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true"
        donde = "clon superficial" if superficial else "puede faltar por traer"
        return "no_comprobada", f"la revisión {revision[:12]} no está en este clon ({donde})"
    # `cat-file blob` y no `show`: de una carpeta, `show` daría su listado y la fuente saldría alterada.
    blob = _git(raiz, "cat-file", "blob", f"{revision}:{ruta}")
    if blob.returncode != 0:
        return "ausente", f"{ruta} no es un archivo de la revisión {revision[:12]}"
    return _comparar(blob.stdout, sha256, f"{ruta} en la revisión {revision[:12]}")


def _en_disco(raiz, ubicacion, sha256):
    raiz = Path(raiz).resolve()
    archivo = (raiz / ubicacion).resolve()
    if raiz != archivo and raiz not in archivo.parents:
        return "no_comprobada", "la ubicación sale de la raíz"
    if not archivo.is_file():
        return "ausente", f"{ubicacion} no existe en el árbol de trabajo"
    try:
        datos = archivo.read_bytes()
    except OSError as exc:
        return "no_comprobada", f"no se pudo leer {ubicacion}: {exc}"
    return _comparar(datos, sha256, f"{ubicacion} en el árbol de trabajo")


def comprobar_fuente(raiz, fuente, almacen=None):
    """(estado, causa) de una fuente; la causa es None si coincide."""
    ubicacion, sha256 = fuente.get("ubicacion"), fuente.get("sha256")
    if not isinstance(ubicacion, str) or not ubicacion or not isinstance(sha256, str):
        return "no_comprobada", "la fuente no declara ubicacion y sha256"
    m = _ALMACEN.fullmatch(ubicacion)
    if m:
        return _en_almacen(m.group(1), sha256, almacen)
    m = _GIT.fullmatch(ubicacion)
    if m:
        return _en_git(raiz, m.group(1), m.group(2), sha256)
    if _UNIDAD.match(ubicacion) or ubicacion.startswith(("/", "\\")):
        return "no_comprobada", "ruta absoluta local: no es una ubicación que otra máquina pueda comprobar"
    if _ESQUEMA.match(ubicacion):
        return "no_comprobada", f"ubicación «{ubicacion.split(':', 1)[0]}:» sin comprobación"
    return _en_disco(raiz, ubicacion, sha256)


def comprobar(raiz, carpeta, almacen=None):
    """{fuentes, recuento, cobertura}: una fila por registro de fuente de las carpetas, con su estado y su causa.

    Lee el disco, como `desvios`: registros con historial y propuestas. Una fuente que no carga (inválida o ilegible)
    queda en la cobertura, que deja de ser completa.
    """
    snapshot, cobertura = cargar(raiz, carpeta, None, modo="propuesta", heredados=True)
    filas = []
    for ident, registro in sorted(snapshot.registros.items()):
        if registro.get("type") != "fuente":
            continue
        estado, causa = comprobar_fuente(raiz, registro, almacen)
        filas.append(
            {
                "id": ident,
                "ruta": snapshot.rutas[ident],
                "ubicacion": registro.get("ubicacion"),
                "estado": estado,
                "causa": causa,
            }
        )
    recuento = {e: sum(1 for f in filas if f["estado"] == e) for e in ESTADOS}
    return {"fuentes": filas, "recuento": recuento, "cobertura": cobertura}
