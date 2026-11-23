"""Vocabulario del dominio: los términos que declaran las decisiones que rigen, y quién los usa.

Una decisión declara términos con la relación `define`: cada entrada nombra una cláusula de esa decisión, el término,
su clase, su descripción y, si los tiene, sus alias. Un término rige en unos cortes cuando esa cláusula rige en ellos
con el texto de esa decisión (C1): no sustituida, derogada ni sin regla. En este incremento la única clase es la de
entidad (C3).

- Mundo cerrado (C2). Desde que rige un término, o puede regir porque su vigencia no se decide, la clase es un mundo
  cerrado para toda la instalación, sea cual sea el ámbito de la decisión que lo define, y lo sigue siendo aunque
  después se retiren todos. Sin ninguno, mundo abierto: no se señala nada sobre clases y la cobertura lo dice.
- Indeterminado (C5). Un término con una definición de vigencia ambigua o con la cláusula en conflicto, con dos
  definiciones distintas, o que comparte nombre o alias con otro término, no rige: se señala aparte.
- Retirado. Un término cuya definición rigió y ya no rige (su decisión se retiró, o su cláusula se sustituyó, se
  derogó o quedó sin regla) y que ninguna otra definición vigente recoge.
- Ámbitos (C3). No son vocabulario: los válidos son los `ambitos` de los roles activos en los cortes.

Solo lee. Un término no declarado se señala con sus usos: no invalida ningún registro ni lo saca de una consulta, no
concede autoridad, no cambia qué rige ni satisface una dependencia (C2, C7). Quien bloquea es la puerta de
integración, y solo el paso de una entidad a `activa` (C4).
"""

from .consolidar import AMBIGUA, RETIRADA, RIGE, _Consulta
from .eventos import ErrorDeHistorial, historial_de_estado, rige_en
from .proyeccion import DEPRECADOS, estado_al_corte

MUNDO_ABIERTO = "vocabulario no declarado: mundo abierto"
# Situación de un nombre usado como clase de entidad.
VIGENTE, ABIERTO, NO_DECLARADO, INDETERMINADO, RETIRADO = (
    "vigente",
    "abierto",
    "no_declarado",
    "indeterminado",
    "retirado",
)


def _definicion(ident, entrada, rige):
    alias = entrada.get("alias") if isinstance(entrada.get("alias"), list) else []
    return {
        "termino": entrada.get("termino"),
        "clase": entrada.get("clase"),
        "descripcion": entrada.get("descripcion"),
        "alias": sorted(set(alias)),
        "decision": ident,
        "clausula": entrada.get("clausula"),
        "referencia": f"{ident}#{entrada.get('clausula')}",
        "rige": rige,
    }


def _contenido(d):
    return d["clase"], d["descripcion"], tuple(d["alias"])


def _definiciones(consulta):
    """(rigen, dudosas, pasadas): las entradas de `define` según rija su cláusula con el texto de su decisión."""
    rigen, dudosas, pasadas = [], [], []
    for ident in sorted(consulta.regs):
        entradas = [e for e in consulta.regs[ident].get("define") or [] if isinstance(e, dict)]
        if not entradas:
            continue
        situacion = consulta.situacion(ident)
        for e in entradas:
            referencia = f"{ident}#{e.get('clausula')}"
            if situacion == AMBIGUA:
                dudosas.append(_definicion(ident, e, False))
            elif situacion == RETIRADA:
                pasadas.append(_definicion(ident, e, False))
            elif situacion == RIGE:
                res = consulta.resolver(referencia)
                if res["estado"] in ("ambigua", "conflicto"):
                    dudosas.append(_definicion(ident, e, False))
                elif res["estado"] == "vigente" and res.get("origen") == referencia:
                    rigen.append(_definicion(ident, e, True))
                elif res["estado"] in ("vigente", "derogada", "sin_regla"):
                    pasadas.append(_definicion(ident, e, False))
    return rigen, dudosas, pasadas


def _rol_activo(rol, valido_en, conocido_hasta):
    """True si el último paso del rol al corte de conocimiento es `activa` y su validez cubre `valido_en`."""
    cadena = historial_de_estado(rol.get("eventos") or [], conocido_hasta, "rol")
    if not cadena or cadena[-1][1]["estado_nuevo"] != "activa":
        return False
    paso = cadena[-1][1]
    return rige_en(paso.get("valido_desde"), paso.get("valido_hasta"), valido_en)


def _ambitos(consulta):
    ambitos = set()
    for ident, r in sorted(consulta.snap.registros.items()):
        if r.get("type") != "rol":
            continue
        try:
            activo = _rol_activo(r, consulta.valido_en, consulta.conocido_hasta)
        except ErrorDeHistorial as exc:
            consulta.avisar(f"{exc.codigo}: {ident}: no se decide si el rol está activo ({exc})")
            continue
        if activo:
            ambitos.update(a for a in r.get("ambitos") or [] if isinstance(a, str))
    return sorted(ambitos)


def vigente(snapshot, *, valido_en, conocido_hasta):
    """Vocabulario del dominio en los dos cortes.

    Devuelve {cortes, clases, alias, indeterminados, retirados, ambitos, declarado, advertencias}: `clases` es
    {término: {decision, clausula, descripcion, alias}} con los términos de clase de entidad que rigen; `alias`,
    {alias: término}; `indeterminados`, [{termino, motivo, definiciones, alias}] (C5); `retirados`, [{termino,
    definiciones, alias}]; `ambitos`, los de los roles activos en los cortes (C3); `declarado`, si la clase es un mundo
    cerrado (C2): algún término rige, puede regir o rigió. `definiciones` son las cláusulas `ID#ancla` que los definen.
    """
    consulta = _Consulta(snapshot, valido_en, conocido_hasta)
    if conocido_hasta is None:
        consulta.avisar("sin corte de conocimiento: se usa todo el historial admitido de la revisión")
    rigen, dudosas, pasadas = _definiciones(consulta)
    por_termino, nombres = {}, {}
    for d in rigen + dudosas:
        por_termino.setdefault(d["termino"], []).append(d)
        for nombre in (d["termino"], *d["alias"]):
            nombres.setdefault(nombre, set()).add(d["termino"])
    clases, indeterminados = {}, []
    for termino in sorted(por_termino):
        defs = por_termino[termino]
        ciertas = [d for d in defs if d["rige"]]
        choques = sorted({n for d in defs for n in (d["termino"], *d["alias"]) if len(nombres[n]) > 1})
        if not ciertas:
            motivo = "su vigencia no se puede decidir"
        elif len({_contenido(d) for d in defs}) > 1:
            motivo = "tiene dos definiciones distintas que rigen o pueden regir"
        elif choques:
            motivo = f"comparte nombre con otro término: {', '.join(choques)}"
        else:
            d = ciertas[0]
            clases[termino] = {k: d[k] for k in ("decision", "clausula", "descripcion", "alias")}
            continue
        indeterminados.append(
            {
                "termino": termino,
                "motivo": motivo,
                "definiciones": sorted({d["referencia"] for d in defs}),
                "alias": sorted({a for d in defs for a in d["alias"]}),
            }
        )
    retirados = {}
    for d in pasadas:
        if d["termino"] in nombres:
            continue  # otra definición vigente o dudosa lo recoge, quizá como alias de un término renombrado
        r = retirados.setdefault(d["termino"], {"termino": d["termino"], "definiciones": [], "alias": []})
        r["definiciones"] = sorted({*r["definiciones"], d["referencia"]})
        r["alias"] = sorted({*r["alias"], *(a for a in d["alias"] if a not in nombres)})
    return {
        "cortes": {"valido_en": valido_en, "conocido_hasta": conocido_hasta, "revision": snapshot.revision},
        "clases": clases,
        "alias": {a: t for t, c in clases.items() for a in c["alias"]},
        "indeterminados": indeterminados,
        "retirados": [retirados[t] for t in sorted(retirados)],
        "ambitos": _ambitos(consulta),
        "declarado": bool(rigen or dudosas or pasadas),
        "advertencias": consulta.advertencias,
    }


def situacion(vocabulario, nombre):
    """(situación, término) de `nombre` como clase de entidad en `vocabulario` (el de `vigente`).

    `vigente` si rige, directamente o por un alias; `abierto` si no hay vocabulario declarado; si no, `indeterminado`,
    `retirado` o `no_declarado`.
    """
    if not vocabulario["declarado"]:
        return ABIERTO, nombre
    termino = vocabulario["alias"].get(nombre, nombre)
    if termino in vocabulario["clases"]:
        return VIGENTE, termino
    for clave, valor in (("indeterminados", INDETERMINADO), ("retirados", RETIRADO)):
        for t in vocabulario[clave]:
            if nombre == t["termino"] or nombre in t["alias"]:
                return valor, t["termino"]
    return NO_DECLARADO, nombre


def constan(snapshot, *, conocido_hasta):
    """(registros que constan al corte y no están cerrados por retirada, rechazo o cancelación, advertencias)."""
    registros, advertencias = [], []
    for ident in sorted(snapshot.registros):
        r = snapshot.registros[ident]
        try:
            estado = estado_al_corte(r, conocido_hasta)
        except ErrorDeHistorial as exc:
            advertencias.append(f"{exc.codigo}: {ident}: historial incoherente, no se revisa ({exc})")
            continue
        if estado is not None and estado not in DEPRECADOS:
            registros.append((ident, r))
    return registros, advertencias


def revisar(snapshot, vocabulario, *, conocido_hasta):
    """Usos del vocabulario en la base: señala, nunca invalida (C2).

    Revisa los registros que constan al corte de conocimiento y no están retirados, rechazados ni cancelados.
    Devuelve {no_declarados, indeterminados, retirados_en_uso, ambitos_sin_rol, registros_examinados, cobertura,
    advertencias}: `no_declarados` y `retirados_en_uso` son [{termino, usos}] con los IDs de las entidades que los
    usan; `indeterminados`, cada término indeterminado con su motivo, sus definiciones y sus usos, aunque no tenga
    ninguno; `ambitos_sin_rol`, [{ambito, usos}] de los registros cuyo ámbito no cubre ningún rol activo (C3). En
    mundo abierto no dice nada de clases y `cobertura` lo declara.
    """
    registros, advertencias = constan(snapshot, conocido_hasta=conocido_hasta)
    validos = set(vocabulario["ambitos"])
    por_situacion = {NO_DECLARADO: {}, INDETERMINADO: {}, RETIRADO: {}}
    ambitos = {}
    for ident, r in registros:
        ambito = r.get("ambito")
        if isinstance(ambito, str) and ambito not in validos:
            ambitos.setdefault(ambito, []).append(ident)
        if r.get("type") == "entidad":
            valor, termino = situacion(vocabulario, r.get("clase_entidad"))
            if valor in por_situacion:
                por_situacion[valor].setdefault(termino, []).append(ident)
    usados = por_situacion[INDETERMINADO]
    return {
        "no_declarados": [{"termino": t, "usos": u} for t, u in sorted(por_situacion[NO_DECLARADO].items())],
        "indeterminados": [{**t, "usos": usados.get(t["termino"], [])} for t in vocabulario["indeterminados"]],
        "retirados_en_uso": [{"termino": t, "usos": u} for t, u in sorted(por_situacion[RETIRADO].items())],
        "ambitos_sin_rol": [{"ambito": a, "usos": u} for a, u in sorted(ambitos.items())],
        "registros_examinados": len(registros),
        "cobertura": [] if vocabulario["declarado"] else [MUNDO_ABIERTO],
        "advertencias": advertencias,
    }
