"""Digest contractual del contenido aprobable («Digest y aprobación», núcleo 0.7).

Objeto: id, type, clase, title, description, ambito, autor, cuerpo, campos y efectos_solicitados. `campos` contiene
todos los campos de contenido y relaciones excepto los excluidos por regla explícita: eventos, proyecciones
(`estado` materializado, `status`, `stale_after`), `verified` y evaluaciones. Serialización: claves ordenadas por
código Unicode, arrays en su orden, sin espacios, UTF-8 sin BOM, sin normalización Unicode, saltos del cuerpo en LF y
solo enteros exactos. Digest = SHA-256 de esos bytes.
"""

import hashlib
import json

from .core import normalizar_cuerpo
from .tiempo import es_instante

SUPERIORES = ("id", "type", "clase", "title", "description", "ambito", "autor")
EXCLUIDOS = frozenset(SUPERIORES) | {"eventos", "estado", "status", "stale_after", "verified", "evaluaciones"}


def _comprobar(valor, ruta="$"):
    if isinstance(valor, bool) or valor is None or isinstance(valor, (int, str)):
        return
    if isinstance(valor, float):
        raise ValueError(f"{ruta}: los decimales se serializan como texto")
    if isinstance(valor, dict):
        for k, v in valor.items():
            if not isinstance(k, str):
                raise ValueError(f"{ruta}: clave no textual {k!r}")
            _comprobar(v, f"{ruta}.{k}")
        return
    if isinstance(valor, list):
        for i, v in enumerate(valor):
            _comprobar(v, f"{ruta}[{i}]")
        return
    raise ValueError(f"{ruta}: tipo no serializable {type(valor).__name__}")


def bytes_canonicos(objeto):
    _comprobar(objeto)
    texto = json.dumps(objeto, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return texto.encode("utf-8")


CAMPOS_EFECTO = {"estado_anterior", "estado_nuevo", "valido_desde", "valido_hasta"}


def comprobar_efectos(efectos):
    """Transiciones solicitadas con sus fechas de validez; sin los instantes de incorporación, aún desconocidos."""
    if not isinstance(efectos, list):
        raise ValueError("efectos_solicitados es una lista de transiciones")
    for i, ef in enumerate(efectos):
        if not isinstance(ef, dict) or not {"estado_nuevo", "valido_desde"} <= ef.keys() or set(ef) - CAMPOS_EFECTO:
            raise ValueError(f"efecto {i}: lleva estado_nuevo y valido_desde, y solo {sorted(CAMPOS_EFECTO)}")
        for campo in ("valido_desde", "valido_hasta"):
            if campo in ef and not es_instante(ef[campo]):
                raise ValueError(f"efecto {i}: {campo} no es un instante con zona")


def objeto_aprobable(registro, cuerpo, efectos_solicitados, importacion=None):
    comprobar_efectos(efectos_solicitados)
    obj = {k: registro.get(k) for k in SUPERIORES}
    obj["cuerpo"] = normalizar_cuerpo(cuerpo)
    obj["campos"] = {k: v for k, v in registro.items() if k not in EXCLUIDOS}
    obj["efectos_solicitados"] = efectos_solicitados
    if importacion is not None:  # solo en una importación: los vectores publicados no la llevan
        obj["importacion"] = importacion
    return obj


def digest(registro, cuerpo, efectos_solicitados, importacion=None):
    objeto = objeto_aprobable(registro, cuerpo, efectos_solicitados, importacion)
    return hashlib.sha256(bytes_canonicos(objeto)).hexdigest()
