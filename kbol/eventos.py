"""Estado materializado desde el historial de eventos admitidos (append-only).

Solo cuentan eventos con `registrado_en`: un evento sin instante de incorporación es local, no está admitido y se
ignora al materializar. Esta función no comprueba la autenticidad de `evidencia_evento`; eso corresponde a la puerta
de integración.
"""

from datetime import timedelta

from .modelo import EFECTIVO, EVENTOS_DE_ESTADO, INICIAL, TRANSICIONES
from .tiempo import comparable, es_fecha, instante

# Una fecha sin zona puede empezar entre UTC−12 y UTC+14: la consulta dentro de esa ventana es ambigua.
_ZONA_MAXIMA = timedelta(hours=14)


class ErrorDeHistorial(ValueError):
    def __init__(self, mensaje, codigo="ESQUEMA_INVALIDO"):
        super().__init__(mensaje)
        self.codigo = codigo


def admitidos(eventos):
    return [ev for ev in eventos if isinstance(ev, dict) and ev.get("registrado_en") is not None]


def _ordenados(eventos):
    anterior = None
    for ev in admitidos(eventos):
        t = instante(ev["registrado_en"])
        if anterior is not None and t < anterior:
            raise ErrorDeHistorial(f"evento {ev.get('evento_id')} registrado antes que el anterior")
        anterior = t
        yield t, ev


def historial_de_estado(eventos, conocido_hasta=None, tipo=None):
    """Eventos de estado admitidos hasta el corte, comprobando la cadena completa; lista de (registrado_en, evento)."""
    corte = instante(conocido_hasta) if conocido_hasta is not None else None
    cadena, estado = [], None
    for t, ev in _ordenados(eventos):
        if ev.get("tipo_evento") not in EVENTOS_DE_ESTADO:
            continue
        previo, nuevo = ev.get("estado_anterior"), ev.get("estado_nuevo")
        if previo != estado:
            raise ErrorDeHistorial(f"evento {ev.get('evento_id')}: parte de {previo!r} y el estado era {estado!r}")
        if tipo is not None:
            if ev["tipo_evento"] == "creacion" and nuevo != INICIAL[tipo]:
                raise ErrorDeHistorial(f"evento {ev.get('evento_id')}: un {tipo} se crea en {INICIAL[tipo]!r}")
            if previo is not None and (previo, nuevo) not in TRANSICIONES[tipo]:
                raise ErrorDeHistorial(
                    f"evento {ev.get('evento_id')}: transición {previo}→{nuevo} no admitida; "
                    "una reapertura exige política explícita"
                )
        estado = nuevo
        if corte is None or t <= corte:
            cadena.append((t, ev))
    return cadena


def estado_en(eventos, conocido_hasta=None, tipo=None):
    """Estado conocido al corte, o None si el registro aún no constaba o no tiene historial admitido."""
    cadena = historial_de_estado(eventos, conocido_hasta, tipo)
    return cadena[-1][1]["estado_nuevo"] if cadena else None


def validez_efectiva(eventos, tipo, conocido_hasta=None):
    """(valido_desde, valido_hasta) del último paso al estado efectivo conocido al corte, o None."""
    cadena = historial_de_estado(eventos, conocido_hasta, tipo)
    if not cadena or cadena[-1][1]["estado_nuevo"] != EFECTIVO.get(tipo):
        return None
    ev = cadena[-1][1]
    return ev.get("valido_desde"), ev.get("valido_hasta")


def rige_en(desde, hasta, valido_en):
    """Intervalo semiabierto [desde, hasta). Una fecha sin hora es ambigua en la ventana de zonas posibles.

    Sin inicio de validez (importación de precisión desconocida) no se puede decidir: TIEMPO_AMBIGUO.
    """
    consulta = instante(valido_en)
    if desde is None:
        raise ErrorDeHistorial("validez sin inicio conocido: no se decide si rige", "TIEMPO_AMBIGUO")
    if es_fecha(desde):
        medianoche = comparable(desde)
        if medianoche - _ZONA_MAXIMA <= consulta < medianoche + _ZONA_MAXIMA:
            raise ErrorDeHistorial(
                f"validez desde {desde} con precisión de día: ambigua en {valido_en}", "TIEMPO_AMBIGUO"
            )
        if consulta < medianoche:
            return False
    elif instante(desde) > consulta:
        return False
    return hasta is None or consulta < instante(hasta)
