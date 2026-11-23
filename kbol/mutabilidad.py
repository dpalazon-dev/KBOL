"""VAL-03: una propuesta comparada con la revisión base (matriz de mutabilidad del núcleo 0.7).

- Ningún registro se borra ni cambia de tipo; el estado no se edita: se solicita como efecto.
- Los eventos son append-only y solo los añade la integración: la propuesta los conserva tal como están en la base.
- Un registro cerrado (`CERRADOS`) no cambia su contenido, sus cláusulas ni sus afirmaciones marcadas; título,
  descripción y prosa sin marcas sí pueden cambiar.
- Un plan o un hito autorizados no cambian lo que cubre su autorización sin autorizarse de nuevo.
- La huella y el formato de una fuente no cambian; su ubicación sí, con comprobación de integridad.
- Las tareas de un hito (cláusulas `CT*`) no se borran, reescriben ni renumeran: solo se marca su casilla, y en un
  hito cerrado ni eso. Las citas a `ID#CTn` tienen que seguir apuntando al mismo texto.
- Cambiar roles, ocupaciones, identidades o el acceso a una fuente requiere la autoridad de la política anterior: se
  marca para esa comprobación, que no hace este módulo.
"""

import re

from .markdown import ErrorDeMarca, clausulas, hechos
from .modelo import CAMPOS_DE_TRABAJO, REFERENCIAS

LIBRES = {"title", "description", "generated", "verified", "stale_after", "status", "evaluaciones", "eventos"}
# Vínculos y campos de trabajo: cambiarlos no reabre un cierre ni una autorización, porque no cambian lo que rige.
LIBRES |= {c for c, r in REFERENCIAS.items() if r.libre} | set(CAMPOS_DE_TRABAJO)
# Estados de cierre por tipo: el contenido ya no se edita; se revisa con un sucesor o una transición motivada.
CERRADOS = {
    "decision": {"aceptada", "rechazada"},
    "hecho": {"aceptada", "rechazada"},
    "pregunta": {"resuelta", "descartada"},
    "hipotesis": {"validada", "refutada", "retirada"},
    "supuesto": {"retirado"},
    "plan": {"cerrado", "cancelado"},
    "hito": {"completado", "cancelado"},
    "fuente": {"retirada"},
    "persona": {"retirada"},
    "rol": {"retirada"},
    "entidad": {"retirada"},
    "sintesis": {"retirada"},
}
# Lo que cubre una autorización vigente: cambiarlo exige autorizar de nuevo.
AUTORIZADOS = {
    "plan": ({"autorizado"}, {"objetivo", "restricciones", "autorizado_por", "hitos"}),
    "hito": (
        {"autorizado", "en_curso"},
        {"objetivo", "alcance", "autorizado_por", "aceptacion", "tolerancias", "verificaciones", "depende_de"},
    ),
}
INMUTABLES_FUENTE = {
    "formato",
    "sha256",
    "subtipo",
    "derivada_de",
    "procesador",
    "version_procesador",
    "configuracion_ref",
    "procesado_en",
}
POLITICA = {
    "rol": {"ambitos", "capacidades", "regla_aprobacion", "estado"},
    "persona": {"ocupa", "naturaleza", "identidad_ref"},
    "fuente": {"acceso"},
}


_CASILLA = re.compile(r"^(\s*[-*+]\s+)\[[ xX]\]", re.MULTILINE)


def _sin_casilla(texto):
    return _CASILLA.sub(r"\1[ ]", texto)


def _tareas(ident, cuerpo_antes, cuerpo_despues, cerrado, h):
    """Cada tarea `CT*` de la base sigue en la propuesta con el mismo texto; solo cambia su casilla, si no está cerrado."""
    todas = _anclas(cuerpo_antes)
    if todas is None:  # la base no se deja leer: no se da por bueno ningún cambio de sus tareas
        h.append(_h(ident, "cuerpo", "las marcas del hito en la base están rotas: no se comprueban sus tareas"))
        return
    antes = {k: v for k, v in todas.items() if k.startswith("CT")}
    if not antes:
        return
    despues = _anclas(cuerpo_despues)
    if despues is None:
        h.append(_h(ident, "cuerpo", "las marcas de las tareas están rotas: una tarea no se pierde"))
        return
    for ancla, texto in antes.items():
        if ancla not in despues:
            h.append(_h(ident, "cuerpo", f"la tarea {ancla} no se borra ni se renumera: puede estar citada"))
        elif cerrado and despues[ancla] != texto:
            h.append(_h(ident, "cuerpo", f"la tarea {ancla} es de un hito cerrado: no se marca ni se cambia"))
        elif _sin_casilla(despues[ancla]) != _sin_casilla(texto):
            h.append(_h(ident, "cuerpo", f"la tarea {ancla} no se reescribe: solo se marca su casilla"))


def _h(ident, campo, mensaje, severidad="error", codigo="ESQUEMA_INVALIDO", control="VAL-03"):
    ruta = f"{ident}/{campo}" if campo else ident
    return {"codigo": codigo, "ruta": ruta, "mensaje": mensaje, "severidad": severidad, "control": control}


def _anclas(cuerpo):
    try:
        return clausulas(cuerpo or "")
    except ErrorDeMarca:
        return None


def _hechos(cuerpo):
    try:
        return hechos(cuerpo or "")
    except ErrorDeMarca:
        return None


def comparar(base, propuesta):
    """{hallazgos, nuevos, modificados, cambios_de_politica} de `propuesta` frente a `base`."""
    out = {"hallazgos": [], "nuevos": [], "modificados": [], "cambios_de_politica": [], "base": base.revision}
    h = out["hallazgos"]
    for ident, antes in sorted(base.registros.items()):
        despues = propuesta.registros.get(ident)
        if despues is None:
            h.append(_h(ident, None, "un registro no se borra: cambia su estado"))
            continue
        if despues == antes and propuesta.cuerpos.get(ident) == base.cuerpos.get(ident):
            continue
        out["modificados"].append(ident)
        _comparar_uno(ident, antes, despues, base.cuerpos.get(ident), propuesta.cuerpos.get(ident), out)
    for ident in sorted(set(propuesta.registros) - set(base.registros)):
        out["nuevos"].append(ident)
        nuevo = propuesta.registros[ident]
        if nuevo.get("eventos"):
            h.append(_h(ident, "eventos", "un registro nuevo no trae eventos: los añade la integración"))
        if nuevo.get("type") in POLITICA:
            out["cambios_de_politica"].append(ident)
            h.append(
                _h(
                    ident,
                    None,
                    "alta de identidad o rol: requiere autoridad previa",
                    "requiere_autoridad",
                    "AUTORIDAD_INSUFICIENTE",
                    "VAL-04",
                )
            )
    return out


def _comparar_uno(ident, antes, despues, cuerpo_antes, cuerpo_despues, out):
    h = out["hallazgos"]
    tipo = antes.get("type")
    if despues.get("type") != tipo:
        h.append(_h(ident, "type", "un registro no cambia de tipo"))
        return
    if despues.get("estado") != antes.get("estado"):
        h.append(_h(ident, "estado", "el estado no se edita: la transición se solicita y la produce la integración"))
    ev_a, ev_d = antes.get("eventos") or [], despues.get("eventos") or []
    if ev_d[: len(ev_a)] != ev_a:
        h.append(_h(ident, "eventos", "los eventos admitidos no se modifican ni se eliminan"))
    elif len(ev_d) > len(ev_a):
        h.append(_h(ident, "eventos", "los eventos nuevos los añade la integración, no la propuesta"))
    cambiados = sorted(k for k in set(antes) | set(despues) if antes.get(k) != despues.get(k))
    if tipo in CERRADOS and antes.get("estado") in CERRADOS[tipo]:
        for campo in cambiados:
            if campo not in LIBRES and campo != "estado":
                h.append(
                    _h(ident, campo, f"contenido protegido de un {tipo} {antes['estado']}: se cambia con un sucesor")
                )
        if tipo == "decision":
            a, d = _anclas(cuerpo_antes), _anclas(cuerpo_despues)
            if d is None or a != d:
                h.append(
                    _h(ident, "cuerpo", "las cláusulas de una decisión cerrada no se reescriben, eliminan ni añaden")
                )
        if _hechos(cuerpo_antes) != _hechos(cuerpo_despues):
            h.append(
                _h(ident, "cuerpo", "una afirmación marcada de un registro cerrado se corrige con otra y sucesión")
            )
    if tipo == "hito":
        _tareas(ident, cuerpo_antes, cuerpo_despues, antes.get("estado") in CERRADOS["hito"], h)
    if tipo in AUTORIZADOS and antes.get("estado") in AUTORIZADOS[tipo][0]:
        for campo in cambiados:
            if campo in AUTORIZADOS[tipo][1]:
                h.append(
                    _h(
                        ident,
                        campo,
                        f"lo cubre la autorización de un {tipo} {antes['estado']}: hay que autorizar de nuevo",
                    )
                )
    if tipo == "fuente":
        for campo in cambiados:
            if campo in INMUTABLES_FUENTE:
                h.append(_h(ident, campo, "el contenido de una fuente es inmutable: otra versión es otra fuente"))
        if "ubicacion" in cambiados:
            h.append(
                _h(
                    ident,
                    "ubicacion",
                    "puntero movido: comprobar que la nueva ubicación conserva la huella (VAL-10)",
                    "aviso",
                    None,
                    "VAL-10",
                )
            )
    if tipo in POLITICA and any(c in POLITICA[tipo] for c in cambiados):
        out["cambios_de_politica"].append(ident)
        h.append(
            _h(
                ident,
                None,
                "cambio de política: lo autoriza la política anterior",
                "requiere_autoridad",
                "AUTORIDAD_INSUFICIENTE",
                "VAL-04",
            )
        )
