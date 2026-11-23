"""VAL-09 y RES-05: consumidores afectados por un cambio, con causa, camino y responsable.

Compara una revisión final con su base. Parte de los registros cambiados o nuevos y de los destinos normativos de
esos cambios (`modifica`, `deja_obsoleta`, `afecta_a`) y recorre las referencias declaradas hacia quien las consume.
No promete encontrar dependencias escondidas en prosa: sin arista declarada no hay impacto calculado, lo que no
demuestra independencia. Cada afectado queda `pendiente` hasta que su responsable lo resuelva.
"""

from collections import deque

from .markdown import ErrorDeMarca, hechos
from .modelo import REFERENCIAS

MAX_SALTOS = 10
# Campos de la cabecera por los que un registro consume a otro (`consumo` en `modelo.REFERENCIAS`). Un rol que
# cambia afecta a lo que autoriza y a quien lo ocupa; el plan consume la decisión en que se apoya y el hito, lo que
# cierra, avanza, somete a prueba o produce. Las citas `<hecho ref>` del cuerpo también consumen; se leen aparte.
CONSUMO = tuple(c for c, r in REFERENCIAS.items() if r.consumo and r.forma != "cuerpo")


def _referencias(r, cuerpo):
    for campo in CONSUMO:
        for v in r.get(campo) or []:
            destino = (v.get("destino") or v.get("resource") or v.get("rol")) if isinstance(v, dict) else v
            if isinstance(destino, str):
                yield destino
    try:
        yield from (h["ref"] for h in hechos(cuerpo or "") if "ref" in h)
    except ErrorDeMarca:
        return


def _coincide(punto, ref):
    p, _, pa = punto.partition("#")
    r, _, ra = ref.partition("#")
    return p == r and (not pa or not ra or pa == ra)


def _responsable(r):
    if r.get("type") in ("pregunta", "hito") and r.get("responsable"):
        return [r["responsable"]]
    return list(r.get("autorizado_por") or []) or None


def impacto(base, final):
    """{base, revision, cambiados, afectados, advertencias} del paso de `base` a `final`."""
    cambiados = sorted(
        i
        for i, r in final.registros.items()
        if base.registros.get(i) != r or base.cuerpos.get(i) != final.cuerpos.get(i)
    )
    res = {
        "base": base.revision,
        "revision": final.revision,
        "cambiados": cambiados,
        "afectados": [],
        "advertencias": [],
    }
    cola, vistos = deque(), set(cambiados)

    def afectar(ident, camino):
        r = final.registros.get(ident)
        if r is None or ident in vistos:
            return
        vistos.add(ident)
        res["afectados"].append(
            {
                "afectado": ident,
                "tipo": r.get("type"),
                "causa": f"cambio en {camino[-2]}",
                "camino": camino,
                "responsable": _responsable(r),
                "resolucion": "pendiente",
                "desfasada": r.get("type") == "sintesis",
            }
        )
        cola.append((ident, camino))

    for c in cambiados:
        r = final.registros[c]
        cola.append((c, [c]))
        for mod in r.get("modifica") or []:
            if isinstance(mod, dict) and isinstance(mod.get("destino"), str):
                cola.append((mod["destino"], [c, mod["destino"]]))
        for d in r.get("deja_obsoleta") or []:
            cola.append((d, [c, d]))
        for d in r.get("afecta_a") or []:
            afectar(d.split("#", 1)[0], [c, d])
    while cola:
        punto, camino = cola.popleft()
        if len(camino) > MAX_SALTOS:
            res["advertencias"].append(f"impacto truncado a {MAX_SALTOS} saltos en {' → '.join(camino)}")
            continue
        for ident in sorted(final.registros):
            refs = _referencias(final.registros[ident], final.cuerpos.get(ident))
            if any(_coincide(punto, ref) for ref in refs):
                afectar(ident, camino + [ident])
    return res
