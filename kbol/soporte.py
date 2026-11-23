"""Consulta `soporte`: si rige en los dos cortes lo que sostiene a cada registro, y qué cambió.

Los apoyos de un registro son sus `basada_en`, las `dependencias` de una síntesis, las fuentes citadas en
`sources[].resource` y las citas `<hecho ref>` de su cuerpo. Cada apoyo se evalúa con
`dependencias.rige_al_corte`, la misma regla que usan las dependencias y la evidencia de `consultar`, y lleva el campo
del que sale. El resumen de un registro se deriva así:

- `roto` si algún apoyo `no_rige` o está `ausente`;
- si no, `indeterminado` si alguno es `indeterminado` o el cuerpo tiene una marca mal formada (sus citas no se
  conocen);
- si no, `intacto` si tiene algún apoyo, y `sin_apoyos` si no tiene ninguno.

`heredado` y `sin_vigencia` no rompen por sí solos, pero se listan. Una síntesis citada informa su estado al corte
(`sin_vigencia`); sus propios apoyos no se recorren desde quien la cita, se leen en su propia entrada. Así no hace
falta guarda de ciclos.

Solo lee: no cambia estados, no satisface ni incumple una dependencia y no bloquea trabajo. Lo que hace quien
responde del registro con un apoyo roto queda fuera de esta consulta.
"""

from collections import Counter

from .consolidar import _Consulta
from .dependencias import AUSENTE, INDETERMINADO, NO_RIGE, RIGE_SI, rige_al_corte
from .eventos import ErrorDeHistorial
from .markdown import ErrorDeMarca, hechos
from .proyeccion import estado_al_corte
from .referencias import aristas

# Campos de la cabecera que sostienen un registro (los de rasgo `evidencia` en `modelo.REFERENCIAS`), en el orden en
# que se informan. Las citas del cuerpo van al final.
CAMPOS = ("basada_en", "dependencias", "sources")
ROTOS = (NO_RIGE, AUSENTE)
# Situaciones de un apoyo que no sostienen: rompen el soporte o lo dejan indeterminado.
NO_SOSTIENEN = (*ROTOS, INDETERMINADO)


def apoyos(registro, cuerpo):
    """([(campo, referencia)], aviso): los apoyos declarados, sin repetir, y el error del cuerpo si no se pudo leer.

    `campo` es `basada_en`, `dependencias`, `sources` o `cuerpo` (una cita `<hecho ref>`). Una marca mal formada no
    se calla: el aviso lo dice y las citas del cuerpo quedan sin conocer.
    """
    vistos = []
    for campo, ref in aristas(registro):
        if campo in CAMPOS and (campo, ref) not in vistos:
            vistos.append((campo, ref))
    vistos.sort(key=lambda par: CAMPOS.index(par[0]))
    try:
        citas = [h["ref"] for h in hechos(cuerpo or "") if "ref" in h]
    except ErrorDeMarca as exc:
        return vistos, f"cuerpo mal formado, sus citas no se conocen ({exc})"
    for ref in citas:
        if ("cuerpo", ref) not in vistos:
            vistos.append(("cuerpo", ref))
    return vistos, None


RETIRADOS = ("retirada", "retirado")


def resumen(evaluados, aviso=None):
    """`roto`, `indeterminado`, `intacto` o `sin_apoyos` según las situaciones de los apoyos (véase el módulo)."""
    situaciones = {a["situacion"] for a in evaluados}
    # Un apoyo sin estado efectivo (una síntesis, una entidad) no rompe por sí solo, salvo que conste retirado.
    retirado = any(a["situacion"] == "sin_vigencia" and a.get("estado") in RETIRADOS for a in evaluados)
    if situaciones & set(ROTOS) or retirado:
        return "roto"
    if INDETERMINADO in situaciones or aviso:
        return "indeterminado"
    return "intacto" if evaluados else "sin_apoyos"


def evaluar(consulta, registro, cuerpo):
    """{apoyos, soporte} de un registro en los cortes de `consulta` (un `consolidar._Consulta`), y `cuerpo` si falló."""
    lista, aviso = apoyos(registro, cuerpo)
    evaluados = [{"ref": ref, "campo": campo, **rige_al_corte(consulta, ref)} for campo, ref in lista]
    salida = {"apoyos": evaluados, "soporte": resumen(evaluados, aviso)}
    if aviso:
        salida["cuerpo"] = aviso
        consulta.avisar(f"{registro.get('id')}: {aviso}")
    return salida


def soporte(snapshot, *, valido_en, conocido_hasta, ids=None):
    """{cortes, registros, recuento, registros_examinados, ausentes, heredados, advertencias}.

    Sin `ids`, todos los registros del snapshot. Cada registro: {id, tipo, estado, apoyos, soporte}, y cada apoyo:
    {ref, campo, situacion, motivo, codigo} con, si se conocen, `estado`, `transicion`, `cadena`, `origen` y
    `sucesoras`. `conocido_hasta=None` usa todo el historial admitido y lo avisa.
    """
    consulta = _Consulta(snapshot, valido_en, conocido_hasta)
    if conocido_hasta is None:
        consulta.avisar("sin corte de conocimiento: se usa todo el historial admitido de la revisión")
    # Sin `ids`, también los heredados: no se examinan, y decirlo evita dar por completa una base que no lo está.
    todos = sorted([*snapshot.registros, *snapshot.heredados])
    pedidos = todos if ids is None else list(dict.fromkeys(i.partition("#")[0] for i in ids))
    registros, ausentes, heredados = [], [], []
    for ident in pedidos:
        r = snapshot.registros.get(ident)
        if r is None:
            if ident in snapshot.heredados:
                ficha = snapshot.heredados[ident]
                heredados.append(ficha)
                consulta.avisar(f"{ident}: formato heredado ({ficha['estado_heredado']}); sin historial admitido")
            else:
                ausentes.append(ident)
            continue
        try:
            estado = estado_al_corte(r, conocido_hasta)
        except ErrorDeHistorial as exc:
            estado = None
            consulta.avisar(f"{exc.codigo}: {ident}: historial incoherente ({exc})")
        evaluado = evaluar(consulta, r, snapshot.cuerpos.get(ident))
        registros.append({"id": ident, "tipo": r.get("type"), "estado": estado, **evaluado})
    return {
        "cortes": {"valido_en": valido_en, "conocido_hasta": conocido_hasta, "revision": snapshot.revision},
        "registros": registros,
        "recuento": dict(sorted(Counter(r["soporte"] for r in registros).items())),
        "registros_examinados": len(registros),
        "ausentes": ausentes,
        "heredados": heredados,
        "advertencias": consulta.advertencias,
    }


def _explicacion(antes, despues):
    """Lo que explica el cambio: la cadena, el origen o las sucesoras del lado que no rige, y la transición."""
    lado = despues if despues["situacion"] != RIGE_SI else antes
    explicacion = {k: lado[k] for k in ("cadena", "origen", "sucesoras") if k in lado}
    if antes.get("transicion") != despues.get("transicion"):
        explicacion["transicion"] = {"antes": antes.get("transicion"), "despues": despues.get("transicion")}
    elif lado.get("transicion"):
        explicacion["transicion"] = lado["transicion"]
    return explicacion


def _sin_clave(apoyo):
    return {k: v for k, v in apoyo.items() if k not in ("ref", "campo")}


def delta(snapshot, antes, despues, ids=None):
    """Apoyos cuya situación cambia entre dos pares de cortes, con lo que lo explica.

    `antes` y `despues` son {valido_en, conocido_hasta}. Devuelve {antes, despues, cambios, registros,
    registros_examinados, ausentes, heredados, advertencias}: `cambios` lista {id, ref, campo, antes, despues,
    explicacion} y `registros`, los registros cuyo resumen cambia. Los apoyos son los mismos en los dos cortes,
    porque salen del mismo snapshot.
    """
    a = soporte(snapshot, ids=ids, **antes)
    d = soporte(snapshot, ids=ids, **despues)
    previos = {r["id"]: r for r in a["registros"]}
    cambios, registros = [], []
    for rd in d["registros"]:
        ra = previos[rd["id"]]
        if ra["soporte"] != rd["soporte"]:
            registros.append({"id": rd["id"], "antes": ra["soporte"], "despues": rd["soporte"]})
        por_clave = {(x["campo"], x["ref"]): x for x in ra["apoyos"]}
        for y in rd["apoyos"]:
            x = por_clave[(y["campo"], y["ref"])]
            if x["situacion"] != y["situacion"]:
                cambios.append(
                    {
                        "id": rd["id"],
                        "ref": y["ref"],
                        "campo": y["campo"],
                        "antes": _sin_clave(x),
                        "despues": _sin_clave(y),
                        "explicacion": _explicacion(x, y),
                    }
                )
    comunes = [t for t in a["advertencias"] if t in d["advertencias"]]
    advertencias = comunes + [f"antes: {t}" for t in a["advertencias"] if t not in comunes]
    advertencias += [f"después: {t}" for t in d["advertencias"] if t not in comunes]
    return {
        "antes": a["cortes"],
        "despues": d["cortes"],
        "cambios": cambios,
        "registros": registros,
        "registros_examinados": d["registros_examinados"],
        "ausentes": d["ausentes"],
        "heredados": d["heredados"],
        "advertencias": advertencias,
    }
