"""VAL-07: evaluación de las condiciones de `depende_de` y consulta de hitos listos.

Una dependencia se satisface solo por su condición tipada, nunca porque el destino exista. Un hito cancelado no
satisface `completado_con_evidencia`: para seguir sin él, el dependiente cambia su `depende_de` por una propuesta
revisada. Mientras no exista el registro de verificaciones, tampoco la satisface un hito completado, y una fuente no
satisface `disponible_con_integridad`: ambas fallan cerradas. Un plan propuesto no bloquea por asociación un hito,
pero el hito necesita su propia autorización vigente.

`rige_al_corte` es la única definición de qué rige en dos cortes: la usan `aceptada_y_vigente`, la consulta `soporte` y
la evidencia de `consultar`.
"""

from .consolidar import AMBIGUA, RETIRADA, RIGE, _Consulta, vigencia_de
from .eventos import ErrorDeHistorial, admitidos, historial_de_estado, rige_en
from .modelo import EFECTIVO
from .proyeccion import entro_en_vigor, estado_al_corte, rige

# Situación de lo que sostiene a un registro en los dos cortes.
RIGE_SI, NO_RIGE, INDETERMINADO, AUSENTE, HEREDADO, SIN_VIGENCIA = (
    "rige",
    "no_rige",
    "indeterminado",
    "ausente",
    "heredado",
    "sin_vigencia",
)

TIPO_DE_CONDICION = {
    "aceptada_y_vigente": ("decision", "hecho"),
    "resuelta": ("pregunta",),
    "completado_con_evidencia": ("hito",),
    "disponible_con_integridad": ("fuente",),
}


def _resultado(dep, satisfecha, motivo, codigo=None, advertencias=None):
    return {
        "destino": dep.get("destino"),
        "condicion": dep.get("condicion"),
        "satisfecha": satisfecha,
        "codigo": codigo,
        "motivo": motivo,
        "advertencias": advertencias or [],
    }


def _una(dep, snapshot, valido_en, conocido_hasta):
    destino, condicion = dep.get("destino", ""), dep.get("condicion")
    ident = destino.partition("#")[0]
    objetivo = snapshot.registros.get(ident)
    if objetivo is None and ident in snapshot.heredados:
        ficha = snapshot.heredados[ident]
        if ficha["tipo"] not in TIPO_DE_CONDICION.get(condicion, ()):
            return _resultado(dep, False, f"{condicion} no se aplica a un {ficha['tipo']}", "ESQUEMA_INVALIDO")
        heredado = ficha["estado_heredado"]
        motivo = f"{ident} está en formato heredado ({heredado}): sin historial admitido no cumple ninguna condición"
        return _resultado(dep, False, motivo)
    if objetivo is None:
        return _resultado(dep, False, f"{ident} no existe en la revisión {snapshot.revision}", "REFERENCIA_AUSENTE")
    if objetivo.get("type") not in TIPO_DE_CONDICION.get(condicion, ()):
        return _resultado(dep, False, f"{condicion} no se aplica a un {objetivo.get('type')}", "ESQUEMA_INVALIDO")
    if not admitidos(objetivo.get("eventos") or []):
        return _resultado(dep, False, f"{ident} no tiene historial admitido")
    try:
        estado = estado_al_corte(objetivo, conocido_hasta)
    except ErrorDeHistorial as exc:
        return _resultado(dep, False, str(exc), exc.codigo)
    if estado is None:
        return _resultado(dep, False, f"{ident} no constaba al corte de conocimiento")
    if condicion == "resuelta":
        return _resultado(dep, estado == "resuelta", f"{ident} está {estado}")
    if condicion == "completado_con_evidencia":
        if estado == "completado":
            # Falla cerrado: los resultados por criterio vivirán en el registro de ejecución (VAL-12), aún sin construir.
            motivo = f"{ident} completado, pero su evidencia por criterio no se puede comprobar todavía"
            return _resultado(dep, False, motivo, "EVIDENCIA_INSUFICIENTE")
        motivo = f"{ident} está {estado}" + ("; cancelar no equivale a cumplir" if estado == "cancelado" else "")
        return _resultado(dep, False, motivo)
    if condicion == "disponible_con_integridad":
        if estado != "registrada":
            return _resultado(dep, False, f"{ident} está {estado}")
        return _resultado(dep, False, "la integridad de la fuente no se ha comprobado", "INTEGRIDAD_NO_COMPROBADA")
    return _aceptada_y_vigente(dep, objetivo, snapshot, valido_en, conocido_hasta)


def _aceptada_y_vigente(dep, objetivo, snapshot, valido_en, conocido_hasta):
    consulta = _Consulta(snapshot, valido_en, conocido_hasta)
    if objetivo["type"] == "decision" and conocido_hasta is None:
        consulta.avisar("sin corte de conocimiento: se usa todo el historial admitido de la revisión")
    res = rige_al_corte(consulta, dep["destino"])
    return _resultado(dep, res["situacion"] == RIGE_SI, res["motivo"], res["codigo"], list(consulta.advertencias))


def _respuesta(situacion, motivo, codigo=None, **detalle):
    return {"situacion": situacion, "motivo": motivo, "codigo": codigo, **{k: v for k, v in detalle.items() if v}}


def _transicion(paso):
    """Último evento de estado al corte: explica un cambio de situación entre dos cortes."""
    claves = ("evento_id", "tipo_evento", "estado_nuevo", "registrado_en", "valido_desde", "valido_hasta")
    return {k: paso[k] for k in claves if paso.get(k) is not None}


def _sucesion(registro, consulta):
    """(sucesoras que ya entraron en vigor, sucesoras cuya vigencia no se puede decidir), por `deja_obsoleta`."""
    efectivas, dudosas = [], []
    for otro in sorted(consulta.snap.registros.values(), key=lambda r: r["id"]):
        if otro.get("type") != registro["type"] or registro["id"] not in (otro.get("deja_obsoleta") or []):
            continue
        try:
            if entro_en_vigor(otro, consulta.valido_en, consulta.conocido_hasta):
                efectivas.append(otro["id"])
        except ErrorDeHistorial as exc:
            dudosas.append(otro["id"])
            consulta.avisar(f"{exc.codigo}: sucesora {otro['id']} sin vigencia determinable ({exc})")
    return efectivas, dudosas


def _hecho_o_fuente(consulta, objetivo, estado):
    ident = objetivo["id"]
    try:
        vigente = rige(objetivo, consulta.valido_en, consulta.conocido_hasta)
    except ErrorDeHistorial as exc:
        return _respuesta(INDETERMINADO, str(exc), exc.codigo)
    sucesoras, dudosas = _sucesion(objetivo, consulta)
    if not vigente:
        detalle = f" (está {estado})" if estado != EFECTIVO[objetivo["type"]] else f" en {consulta.valido_en}"
        return _respuesta(NO_RIGE, f"{ident} no rige{detalle}", sucesoras=sucesoras)
    if sucesoras:
        return _respuesta(NO_RIGE, f"{ident} no rige: lo deja obsoleto {', '.join(sucesoras)}", sucesoras=sucesoras)
    if dudosas:
        motivo = f"{ident}: no se decide si lo deja obsoleto {', '.join(dudosas)}"
        return _respuesta(INDETERMINADO, motivo, "TIEMPO_AMBIGUO", sucesoras=dudosas)
    return _respuesta(RIGE_SI, f"{ident} rige")


def _clausula(entrada):
    """Cadena de sustituciones y origen de una cláusula resuelta, si la cadena va más allá de ella misma."""
    cadena = entrada.get("cadena") or []
    return {"cadena": cadena if len(cadena) > 1 else None, "origen": entrada.get("origen")}


def _decision(consulta, objetivo, referencia):
    ident, _, ancla = referencia.partition("#")
    sit = consulta.situacion(ident)
    vigencia, entradas = vigencia_de(consulta, ident)
    entrada = None
    if ancla and sit == RIGE and ancla in (consulta.anclas(ident) or {}):
        entrada = consulta.resolver(referencia)
    if vigencia not in ("total", "parcial"):
        motivo = f"{ident} {vigencia}" + (f": {referencia} está {entrada['estado']}" if entrada else "")
        dudosa = sit == AMBIGUA or any(e["estado"] in ("ambigua", "conflicto") for e in entradas)
        sucesoras = _sucesion(objetivo, consulta)[0] if sit == RETIRADA else None
        detalle = _clausula(entrada) if entrada else {}
        return _respuesta(INDETERMINADO if dudosa else NO_RIGE, motivo, sucesoras=sucesoras, **detalle)
    if not ancla:
        return _respuesta(RIGE_SI, f"{ident} rige ({vigencia})")
    if entrada is None:
        return _respuesta(AUSENTE, f"{referencia} no está en el consolidado", "REFERENCIA_AUSENTE")
    detalle = _clausula(entrada)
    if entrada["estado"] == "conflicto":
        return _respuesta(INDETERMINADO, f"{referencia} está en conflicto", "CONFLICTO_NORMATIVO", **detalle)
    if entrada["estado"] == "ambigua":
        return _respuesta(INDETERMINADO, f"{referencia} está ambigua", **detalle)
    if entrada["estado"] != "vigente":
        return _respuesta(NO_RIGE, f"{referencia} está {entrada['estado']}", **detalle)
    if entrada["origen"] != referencia:
        return _respuesta(NO_RIGE, f"{referencia} sustituida por {entrada['origen']}: revisar el impacto", **detalle)
    return _respuesta(RIGE_SI, f"{referencia} rige")


def rige_al_corte(consulta, referencia):
    """Si rige `ID` o `ID#ancla` en los cortes de `consulta` (un `consolidar._Consulta`): la definición única.

    La usan las dependencias (`aceptada_y_vigente`), la consulta `soporte` y la evidencia de `consultar`
   . Devuelve {situacion, motivo, codigo} y, cuando se conocen, `estado` al corte de conocimiento,
    `transicion` (el último evento de estado al corte), `cadena` y `origen` de una cláusula sustituida o derogada y
    `sucesoras`. `situacion` es `rige`, `no_rige`, `indeterminado` (tiempo ambiguo, historial incoherente o conflicto:
    nunca una situación supuesta), `ausente`, `heredado` (se nombra, pero no rige) o `sin_vigencia` (un tipo sin
    estado efectivo, como una síntesis, que solo informa su estado). Una fuente rige si está registrada y ninguna
    sucesora ha entrado en vigor; un hecho, si está aceptado, su validez cubre `valido_en` y ninguna sucesora ha
    entrado en vigor; una decisión o una cláusula, según el consolidado. Solo lee.
    """
    snapshot = consulta.snap
    ident = referencia.partition("#")[0]
    objetivo = snapshot.registros.get(ident)
    if objetivo is None:
        if ident in snapshot.heredados:
            heredado = snapshot.heredados[ident].get("estado_heredado")
            motivo = f"{ident} está en formato heredado ({heredado}): se nombra, pero no rige"
            return _respuesta(HEREDADO, motivo, estado=heredado)
        return _respuesta(AUSENTE, f"{ident} no existe en la revisión {snapshot.revision}", "REFERENCIA_AUSENTE")
    if not admitidos(objetivo.get("eventos") or []):
        return _respuesta(NO_RIGE, f"{ident} no tiene historial admitido")
    tipo = objetivo.get("type")
    try:
        cadena = historial_de_estado(objetivo["eventos"], consulta.conocido_hasta, tipo)
    except ErrorDeHistorial as exc:
        return _respuesta(INDETERMINADO, f"{ident}: historial incoherente ({exc})", exc.codigo)
    if not cadena:
        return _respuesta(NO_RIGE, f"{ident} no constaba al corte de conocimiento")
    estado = cadena[-1][1]["estado_nuevo"]
    if tipo not in EFECTIVO:
        res = _respuesta(SIN_VIGENCIA, f"{ident} es un registro de tipo {tipo}, sin vigencia propia: está {estado}")
    elif tipo == "decision":
        res = _decision(consulta, objetivo, referencia)
    else:
        res = _hecho_o_fuente(consulta, objetivo, estado)
    return {**res, "estado": estado, "transicion": _transicion(cadena[-1][1])}


def evaluar(registro, snapshot, *, valido_en, conocido_hasta):
    """Resultado por dependencia declarada en `registro`, en el orden escrito."""
    return [
        _una(dep, snapshot, valido_en, conocido_hasta)
        for dep in registro.get("depende_de") or []
        if isinstance(dep, dict)
    ]


def listos(snapshot, *, valido_en, conocido_hasta):
    """Hitos autorizados al corte con todas sus dependencias satisfechas, y los autorizados que siguen bloqueados."""
    out = {"listos": [], "bloqueados": [], "hitos_examinados": 0, "advertencias": []}
    for ident in sorted(snapshot.registros):
        r = snapshot.registros[ident]
        if r.get("type") != "hito":
            continue
        out["hitos_examinados"] += 1
        if not admitidos(r.get("eventos") or []):
            out["advertencias"].append(f"{ident}: sin historial admitido; su autorización no consta")
            continue
        try:
            cadena = historial_de_estado(r["eventos"], conocido_hasta, "hito")
            if not cadena or cadena[-1][1]["estado_nuevo"] != "autorizado":
                continue
            paso = cadena[-1][1]
            if not rige_en(paso.get("valido_desde"), paso.get("valido_hasta"), valido_en):
                out["advertencias"].append(f"{ident}: autorizado, pero su autorización no está vigente en {valido_en}")
                continue
        except ErrorDeHistorial as exc:
            out["advertencias"].append(f"{exc.codigo}: {ident}: {exc}")
            continue
        deps = evaluar(r, snapshot, valido_en=valido_en, conocido_hasta=conocido_hasta)
        pendientes = [d for d in deps if not d["satisfecha"]]
        destino = out["bloqueados"] if pendientes else out["listos"]
        destino.append({"id": ident, "dependencias": deps, "pendientes": pendientes})
    for ident, ficha in sorted(snapshot.heredados.items()):
        if ficha["tipo"] == "hito":
            out["advertencias"].append(
                f"{ident}: formato heredado ({ficha['estado_heredado']}); su autorización no consta en un historial "
                "admitido"
            )
    return out
