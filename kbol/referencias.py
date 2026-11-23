"""VAL-02 y VAL-07 sobre un snapshot: referencias resolubles, tipo de destino, anclas y ciclos prohibidos.

Un ciclo entre relaciones de contexto (`afecta_a`, `resuelta_por`, `basada_en`) es legítimo; se prohíben en la
sucesión (`deja_obsoleta` y `modifica`), la derivación (`derivada_de`) y la dependencia ejecutable (`depende_de`).
Un ancla cuyo cuerpo no se cargó en el snapshot no se da por buena: queda como aviso de cobertura.
"""

from . import modelo as m
from .markdown import ErrorDeMarca, clausulas, hechos


def _hallazgo(codigo, origen, campo, mensaje, severidad="error"):
    return {"codigo": codigo, "ruta": f"{origen}/{campo}", "mensaje": mensaje, "severidad": severidad}


def aristas(registro, cuerpo=None):
    """(campo, destino) de cada referencia del registro, en el orden de `modelo.REFERENCIAS`; solo destinos de texto.

    Una relación se recorre en cualquier registro que la declare (su sitio lo vigila el esquema); un campo propio,
    solo en los tipos que lo declaran. Las citas `<hecho ref>` se leen si se da el cuerpo, con el campo `cuerpo`;
    una marca mal formada las deja sin leer, sin error: lo dice el esquema.
    """
    tipo = registro.get("type")
    for campo, ref in m.REFERENCIAS.items():
        if not ref.relacion and ref.origen is not None and tipo not in ref.origen:
            continue
        if ref.forma == "cuerpo":
            if cuerpo is not None:
                try:
                    for h in hechos(cuerpo):
                        if "ref" in h:
                            yield campo, h["ref"]
                except ErrorDeMarca:
                    pass
        elif ref.forma == "id":
            if isinstance(registro.get(campo), str):
                yield campo, registro[campo]
        elif ref.forma == "ids":
            for d in registro.get(campo) or []:
                if isinstance(d, str):
                    yield campo, d
        elif ref.clave is not None:
            for v in registro.get(campo) or []:
                if isinstance(v, dict) and isinstance(v.get(ref.clave), str):
                    yield campo, v[ref.clave]


# Tipo de destino de las referencias que no son relaciones de lista; las de lista lo toman de `modelo.RELACIONES`.
DESTINO_ESPERADO = {c: r.destino for c, r in m.REFERENCIAS.items() if c not in m.RELACIONES and r.destino}


def validar_snapshot(snapshot):
    regs = snapshot.registros
    out = []
    anclas = {}
    for ident, cuerpo in snapshot.cuerpos.items():
        try:
            anclas[ident] = set(clausulas(cuerpo))
        except ErrorDeMarca:
            anclas[ident] = set()
    for origen, r in regs.items():
        for campo, destino in aristas(r, snapshot.cuerpos.get(origen)):
            ident, _, ancla = destino.partition("#")
            if ident not in regs:
                if ident in snapshot.heredados:
                    # Durante la migración del corpus: el destino existe, en formato heredado. No rige ni
                    # satisface dependencias, pero la referencia se resuelve; se avisa, no se bloquea.
                    motivo = f"{ident} está en formato heredado: se resuelve, pero no sirve de destino normativo"
                    out.append(_hallazgo("REFERENCIA_AUSENTE", origen, campo, motivo, "aviso"))
                else:
                    motivo = f"{ident} no existe en la revisión {snapshot.revision}"
                    out.append(_hallazgo("REFERENCIA_AUSENTE", origen, campo, motivo))
                continue
            real = regs[ident].get("type")
            regla = m.RELACIONES.get(campo, {})
            esperado = DESTINO_ESPERADO.get(campo) or (
                (r.get("type"),) if regla.get("destino") == "mismo" else regla.get("destino")
            )
            if esperado and real not in esperado:
                out.append(_hallazgo("ESQUEMA_INVALIDO", origen, campo, f"{campo} no admite un destino de tipo {real}"))
            if ancla and ident not in snapshot.cuerpos:
                out.append(
                    _hallazgo(None, origen, campo, f"{destino}: cuerpo no cargado, ancla no comprobada", "aviso")
                )
            elif ancla and ancla not in anclas.get(ident, set()):
                out.append(_hallazgo("REFERENCIA_AUSENTE", origen, campo, f"{destino}: la cláusula no existe"))
    for rel in m.SIN_CICLOS:
        out += _ciclos(regs, rel)
    return out


def _sucesores(registro, rel):
    for valor in registro.get(rel) or []:
        destino = valor.get("destino") if isinstance(valor, dict) else valor
        if isinstance(destino, str):
            yield destino.split("#", 1)[0]


def _ciclos(regs, rel):
    out, color = [], {}

    def visitar(nodo, camino):
        color[nodo] = 1
        for sig in _sucesores(regs.get(nodo, {}), rel):
            if sig not in regs:
                continue
            if color.get(sig) == 1:
                ciclo = camino[camino.index(sig) :] + [sig]
                out.append(_hallazgo("CONFLICTO_NORMATIVO", nodo, rel, "ciclo prohibido: " + " → ".join(ciclo)))
            elif color.get(sig) is None:
                visitar(sig, camino + [sig])
        color[nodo] = 2

    for nodo in sorted(regs):
        if color.get(nodo) is None:
            visitar(nodo, [nodo])
    return out
