"""Proyección total de `status` (VAL-08), calculada para una revisión y dos cortes temporales explícitos.

`status` describe estabilidad para intercambio; no es verdad, permiso ni calidad. Nadie lo escribe a mano. Las
consultas reconstruyen el estado desde los eventos admitidos: un registro sin historial admitido no tiene proyección,
y la cabecera actual nunca sustituye al historial.
"""

from dataclasses import dataclass, field

from .eventos import ErrorDeHistorial, admitidos, estado_en, rige_en, validez_efectiva
from .modelo import EFECTIVO

DEPRECADOS = {"rechazada", "descartada", "retirada", "retirado", "cancelado"}
BORRADOR = {
    "decision": {"propuesta"},
    "hecho": {"propuesta"},
    "persona": {"propuesta"},
    "rol": {"propuesta"},
    "entidad": {"propuesta"},
    "plan": {"propuesto"},
    "hito": {"propuesto"},
    "sintesis": {"borrador"},
    "hipotesis": {"abierta"},
    "supuesto": {"activo"},
}


@dataclass(frozen=True)
class Snapshot:
    """Registros de una revisión canónica identificada, por ID, con sus cuerpos si se cargaron."""

    registros: dict
    revision: str
    cuerpos: dict = field(default_factory=dict)
    rutas: dict = field(default_factory=dict)
    # Registros del formato heredado leídos por compatibilidad (snapshot.cargar con heredados=True): fichas de la
    # migración en seco, sin historial admitido. Nunca entran en `registros` ni rigen.
    heredados: dict = field(default_factory=dict)


def estado_al_corte(registro, conocido_hasta):
    """Estado conocido al corte desde el historial admitido; None si no constaba o no tiene historial."""
    return estado_en(registro.get("eventos") or [], conocido_hasta, registro["type"])


def rige(registro, valido_en, conocido_hasta):
    """True si el registro está en su estado efectivo y su validez cubre `valido_en`. Puede lanzar TIEMPO_AMBIGUO."""
    tipo = registro["type"]
    if tipo not in EFECTIVO:
        return False
    if tipo == "fuente":
        return estado_al_corte(registro, conocido_hasta) == "registrada"
    validez = validez_efectiva(registro.get("eventos") or [], tipo, conocido_hasta)
    return validez is not None and rige_en(*validez, valido_en)


def entro_en_vigor(registro, valido_en, conocido_hasta):
    """True si el registro llegó a su estado efectivo y su validez empezó en o antes de `valido_en`.

    Que después lo sustituyan o venza no cambia la respuesta: una sucesión completa que entró en vigor no se deshace
    sola. Puede lanzar TIEMPO_AMBIGUO.
    """
    tipo = registro["type"]
    if tipo == "fuente":
        return estado_al_corte(registro, conocido_hasta) in ("registrada", "retirada")
    validez = validez_efectiva(registro.get("eventos") or [], tipo, conocido_hasta)
    return validez is not None and rige_en(validez[0], None, valido_en)


def _sucesoras(registro, snapshot, valido_en, conocido_hasta, advertencias):
    efectivas = []
    for r in snapshot.registros.values():
        if r.get("type") != registro["type"] or registro["id"] not in (r.get("deja_obsoleta") or []):
            continue
        try:
            if entro_en_vigor(r, valido_en, conocido_hasta):
                efectivas.append(r["id"])
        except ErrorDeHistorial as exc:
            advertencias.append(f"{exc.codigo}: sucesora {r['id']} sin vigencia determinable ({exc})")
    return efectivas


def proyectar(registro, snapshot, *, valido_en, conocido_hasta):
    """{status, estado, sucesoras, advertencias}. `status` es None si el registro no constaba en el corte."""
    tipo = registro["type"]
    advertencias = []
    resultado = {"status": None, "estado": None, "sucesoras": [], "advertencias": advertencias}
    if not admitidos(registro.get("eventos") or []):
        advertencias.append("sin historial admitido: el estado escrito en la cabecera no se proyecta")
        return resultado
    try:
        estado = estado_al_corte(registro, conocido_hasta)
    except ErrorDeHistorial as exc:
        advertencias.append(f"{exc.codigo}: historial incoherente ({exc})")
        return resultado
    resultado["estado"] = estado
    if estado is None:
        advertencias.append("el registro no constaba al corte de conocimiento")
        return resultado
    resultado["sucesoras"] = _sucesoras(registro, snapshot, valido_en, conocido_hasta, advertencias)
    if (
        registro.get("clase") == "archivo"
        or estado in DEPRECADOS
        or (tipo == "hipotesis" and estado == "refutada")
        or resultado["sucesoras"]
    ):
        resultado["status"] = "deprecated"
    elif estado in BORRADOR.get(tipo, ()) or (
        tipo in ("decision", "hecho")
        and estado == "aceptada"
        and _entrada_futura(registro, valido_en, conocido_hasta, advertencias)
    ):
        resultado["status"] = "draft"
    else:
        resultado["status"] = "stable"
    return resultado


def proyectar_status(registro, snapshot, *, valido_en, conocido_hasta):
    """`draft`, `stable`, `deprecated` o None (sin historial admitido o no constaba en el corte)."""
    return proyectar(registro, snapshot, valido_en=valido_en, conocido_hasta=conocido_hasta)["status"]


def _entrada_futura(registro, valido_en, conocido_hasta, advertencias):
    """Regla 3: aceptada con inicio de validez posterior a `valido_en`. Una validez ya vencida no es futura.

    Si el inicio tiene precisión de día y la consulta cae en la ventana ambigua, se trata como futura (`draft`):
    no se presenta como en vigor lo que puede no estarlo todavía.
    """
    validez = validez_efectiva(registro.get("eventos") or [], registro["type"], conocido_hasta)
    if validez is None:
        return False
    try:
        return not rige_en(validez[0], None, valido_en)
    except ErrorDeHistorial as exc:
        advertencias.append(f"{exc.codigo}: {exc}")
        return True
