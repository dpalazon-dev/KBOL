"""Instantes ISO 8601 con zona y fechas de día, sin depender del reloj del entorno."""

import re
from datetime import date, datetime, timezone

_INSTANTE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?(Z|[+-]\d{2}:\d{2})")
_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")


def instante(texto):
    """Convierte un instante con zona en datetime aware; ValueError si falta la zona o no es válido."""
    m = _INSTANTE.fullmatch(texto) if isinstance(texto, str) else None
    if not m:
        raise ValueError(f"no es un instante ISO 8601 con zona: {texto!r}")
    dia, hh, mm, ss, frac, zona = m.groups()
    micro = (frac or "0")[:6].ljust(6, "0")
    zona = "+00:00" if zona == "Z" else zona
    return datetime.fromisoformat(f"{dia}T{hh}:{mm}:{ss or '00'}.{micro}{zona}").astimezone(timezone.utc)


def es_instante(texto):
    try:
        instante(texto)
        return True
    except ValueError:
        return False


def es_fecha(texto):
    if not (isinstance(texto, str) and _FECHA.fullmatch(texto)):
        return False
    try:
        date.fromisoformat(texto)
        return True
    except ValueError:
        return False


def es_instante_o_fecha(texto):
    return es_instante(texto) or es_fecha(texto)


def comparable(texto):
    """Instante para ordenar: una fecha cuenta desde su medianoche UTC; quien la compare declara la ambigüedad."""
    if es_fecha(texto):
        return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)
    return instante(texto)
