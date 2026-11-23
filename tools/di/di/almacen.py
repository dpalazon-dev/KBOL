"""Almacén de originales y representaciones direccionado por contenido.

Cada objeto vive en `<almacen>/sha256/<huella>` y nunca se sobrescribe: otra versión es otro objeto. Junto a él,
`<almacen>/meta/<huella>.json` guarda de dónde salió y cuándo se capturó por primera vez. La identidad de la fuente
no es la huella: es el registro `F-…` que la cita; el almacén solo garantiza que los bytes son los que dice.
"""

import hashlib
import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

AGENTE = "kbol-di/0.1 (+captura de normativa publica)"
# Estado local que usa el almacén cuando no se da KBOL_REPOSITORIO.
REPOSITORIO_POR_DEFECTO = "predeterminado"
_REPOSITORIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class ErrorDeIntegridad(RuntimeError):
    pass


def _ahora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _leer_origen(origen: str | Path) -> bytes:
    texto = str(origen)
    if texto.startswith(("https://", "http://")):
        peticion = urllib.request.Request(texto, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(peticion, timeout=120) as resp:  # noqa: S310 - URL dada por el operador
            return resp.read()
    return Path(origen).read_bytes()


def guardar(datos: bytes, almacen: Path) -> tuple[str, Path]:
    """Escribe los bytes en su sitio si no estaban y comprueba la huella al releer. Devuelve (huella, ruta)."""
    huella = hashlib.sha256(datos).hexdigest()
    destino = Path(almacen) / "sha256" / huella
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        if hashlib.sha256(destino.read_bytes()).hexdigest() != huella:
            raise ErrorDeIntegridad(f"el objeto {destino} no tiene la huella de su nombre")
        return huella, destino
    temporal = destino.with_suffix(".tmp")
    temporal.write_bytes(datos)
    os.replace(temporal, destino)
    if hashlib.sha256(destino.read_bytes()).hexdigest() != huella:
        raise ErrorDeIntegridad(f"la relectura de {destino} no coincide")
    return huella, destino


def capturar(origen: str | Path, almacen: Path, medio: str | None = None) -> dict:
    """Captura un original (URL o archivo). Un reintento con los mismos bytes devuelve la captura primera."""
    datos = _leer_origen(origen)
    huella, _ = guardar(datos, almacen)
    meta_ruta = Path(almacen) / "meta" / f"{huella}.json"
    meta_ruta.parent.mkdir(parents=True, exist_ok=True)
    if meta_ruta.exists():
        meta = json.loads(meta_ruta.read_text(encoding="utf-8"))
        if str(origen) not in meta["origenes"]:
            meta["origenes"].append(str(origen))
            meta_ruta.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return meta
    meta = {
        "sha256": huella,
        "bytes": len(datos),
        "ruta": f"sha256/{huella}",
        "medio": medio,
        "origenes": [str(origen)],
        "capturado_en": _ahora(),
    }
    meta_ruta.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def leer(huella: str, almacen: Path) -> bytes:
    ruta = Path(almacen) / "sha256" / huella
    datos = ruta.read_bytes()
    if hashlib.sha256(datos).hexdigest() != huella:
        raise ErrorDeIntegridad(f"el objeto {ruta} no tiene la huella de su nombre")
    return datos


def almacen_por_defecto() -> Path:
    """KBOL_ALMACEN o el almacén del estado local de la instalación: `$KBOL_ESTADO/<repositorio>/almacen`.

    El repositorio es el nombre del estado local de la instalación (el `integracion.repositorio` que usa
    `kbol proponer`) y se da en KBOL_REPOSITORIO. Sin él vale `REPOSITORIO_POR_DEFECTO`: las órdenes se lanzan desde
    `tools/di`, no desde la instalación, así que no hay de dónde deducirlo.
    """
    if os.environ.get("KBOL_ALMACEN"):
        return Path(os.environ["KBOL_ALMACEN"])
    repositorio = os.environ.get("KBOL_REPOSITORIO") or REPOSITORIO_POR_DEFECTO
    if not _REPOSITORIO.fullmatch(repositorio):
        raise ValueError(f"KBOL_REPOSITORIO no es un nombre de carpeta: {repositorio!r}")
    return Path(os.environ.get("KBOL_ESTADO") or Path.home() / ".kbol") / repositorio / "almacen"
