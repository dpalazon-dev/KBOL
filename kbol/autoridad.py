"""VAL-04: autoridad comprobada para los efectos solicitados sobre un registro (núcleo 0.7, §7 y ESC-03).

La política es la de la revisión base, anterior al cambio: un cambio no puede concederse la autoridad que usa. Quien
pide la integración solo identifica revisiones; el digest lo calcula este módulo desde el contenido y los efectos del
commit revisado, y cada aprobación se construye con lo que verifica el canal de confianza. Una revisión cuenta si
la cuenta verificada corresponde a una única persona humana activa que ocupa un rol requerido en el instante de la
revisión y, si se indica, también en el de la integración (la revocación se revalida al integrar). Después se aplica
la regla de cada rol: `uno`, `todos` o `quorum`.

Capacidades locales: `ratificar` en los ámbitos del rol, y `gobernar_politica` para cambiar roles e identidades.
"""

from .digest import digest
from .eventos import ErrorDeHistorial
from .proyeccion import estado_al_corte
from .tiempo import instante
from .verificacion import ErrorDeVerificacion, clave_de_revision

RATIFICAR, GOBERNAR = "ratificar", "gobernar_politica"


def _activo(registro, cuando):
    try:
        return registro is not None and cuando is not None and estado_al_corte(registro, cuando) == "activa"
    except ErrorDeHistorial:
        return False


def _ocupa(persona, rol, cuando):
    t = instante(cuando)
    for o in persona.get("ocupa") or []:
        if o.get("rol") == rol and instante(o["desde"]) <= t and (o.get("hasta") is None or t < instante(o["hasta"])):
            return True
    return False


def roles_requeridos(registro, politica, cuando, cambio_de_politica=False):
    """(roles, modo, problemas) en el instante `cuando`. `modo`: `cada_uno` (autorizado_por) o `alguno` (implícitos)."""
    roles = {i: r for i, r in politica.registros.items() if r.get("type") == "rol"}
    if registro.get("type") in ("rol", "persona") or cambio_de_politica:
        gob = [i for i, r in roles.items() if GOBERNAR in (r.get("capacidades") or []) and _activo(r, cuando)]
        return gob, "alguno", [] if gob else ["la política base no tiene ningún rol activo que gobierne la política"]
    declarados = registro.get("autorizado_por")
    ambito = registro.get("ambito")
    if declarados:
        problemas = []
        for i in declarados:
            r = roles.get(i)
            if not _activo(r, cuando):
                problemas.append(f"{i} no es un rol activo en la política base")
            elif RATIFICAR not in (r.get("capacidades") or []):
                problemas.append(f"{i} no tiene la capacidad de ratificar")
            elif ambito not in (r.get("ambitos") or []):
                problemas.append(f"{i} no cubre el ámbito {ambito}")
        return list(declarados), "cada_uno", problemas
    implicitos = [
        i
        for i, r in roles.items()
        if RATIFICAR in (r.get("capacidades") or []) and ambito in (r.get("ambitos") or []) and _activo(r, cuando)
    ]
    return implicitos, "alguno", [] if implicitos else [f"ningún rol activo ratifica en el ámbito {ambito}"]


def _humanos_del_rol(politica, rol, instantes):
    return {
        i
        for i, p in politica.registros.items()
        if p.get("type") == "persona"
        and p.get("naturaleza") == "humana"
        and all(_activo(p, t) and _ocupa(p, rol, t) for t in instantes)
    }


def _regla_cumplida(regla, aprobados, ocupantes):
    if regla == "todos":
        return bool(ocupantes) and ocupantes <= aprobados
    if isinstance(regla, dict):
        return len(aprobados) >= regla.get("quorum", 0)
    return len(aprobados) >= 1


def evaluar(
    registro,
    cuerpo,
    efectos,
    revisiones,
    politica,
    verificador,
    propuesta_rev,
    base_rev,
    revalidar_en=None,
    cambio_de_politica=False,
    importacion=None,
):
    """{autorizado, codigo, digest, requeridos, roles, revisiones, aprobaciones, problemas}.

    `aprobaciones` son los objetos de aprobación construidos con datos verificados, listos para su evento.
    """
    d = digest(registro, cuerpo, efectos, importacion=importacion)
    personas = {i: p for i, p in politica.registros.items() if p.get("type") == "persona"}
    verificadas, resultados, vistas = [], [], set()
    for rv in revisiones:
        clave = clave_de_revision(rv)
        if clave in vistas:
            continue  # una revisión citada dos veces es una sola aprobación
        vistas.add(clave)
        res = {"revision": rv, "valida": False, "motivo": None, "codigo": None, "persona": None}
        resultados.append(res)
        try:
            v = verificador.verificar(rv, propuesta_rev, base_rev)
        except ErrorDeVerificacion as exc:
            res["motivo"], res["codigo"] = str(exc), exc.codigo
            continue
        if "digests" in v and v["digests"].get(registro.get("id")) != d:
            res["motivo"] = "lo aprobado no es lo que se integra: el digest mostrado no coincide"
            res["codigo"] = "APROBACION_CADUCADA"
            continue
        res["verificada_en"] = v["instante"]
        cuenta = [
            i for i, p in personas.items() if p.get("identidad_ref") == v["identidad"] and _activo(p, v["instante"])
        ]
        if len(cuenta) != 1:
            res["motivo"] = f"{v['identidad']} no corresponde a una única persona activa en la política base"
            continue
        persona = personas[cuenta[0]]
        res["persona"] = cuenta[0]
        if persona.get("naturaleza") != "humana":
            res["motivo"] = "un agente no ratifica"
            continue
        if revalidar_en is not None and not _activo(persona, revalidar_en):
            res["motivo"] = "la persona ya no está activa al integrar"
            continue
        verificadas.append((res, persona, v))
    cuando = revalidar_en or (max((v["instante"] for _, _, v in verificadas), key=instante) if verificadas else None)
    requeridos, modo, problemas = (
        roles_requeridos(registro, politica, cuando, cambio_de_politica)
        if cuando
        else ([], "alguno", ["ninguna revisión verificada"])
    )
    aprobados, aprobaciones = {}, []
    for res, persona, v in verificadas:
        instantes = [v["instante"]] + ([revalidar_en] if revalidar_en else [])
        ejercidos = [r for r in requeridos if all(_ocupa(persona, r, t) for t in instantes)]
        if not ejercidos:
            res["motivo"] = "no ocupa un rol requerido en el instante de la revisión o al integrar"
            continue
        res["valida"], res["roles"] = True, ejercidos
        for r in ejercidos:
            aprobados.setdefault(r, set()).add(res["persona"])
        c = v["comprobante"]
        aprobacion_id = v.get("aprobacion_id") or f"{c['mecanismo']}:{c['repositorio']}#{c['pull']}/{c['review_id']}"
        if any(a["aprobacion_id"] == aprobacion_id for a in aprobaciones):
            continue  # la misma aprobación, citada de otra forma: cuenta una vez
        aprobaciones.append(
            {
                "aprobacion_id": aprobacion_id,
                "actor": f"human:{res['persona']}",
                "identidad_ref": v["identidad"],
                "roles": ejercidos,
                "digest": d,
                "revision_base": base_rev,
                "aprobada_en": v["instante"],
                "politica_revision": politica.revision,
                "comprobante": c,
            }
        )
    estado_roles = {}
    for r in requeridos:
        regla = (politica.registros.get(r) or {}).get("regla_aprobacion", "uno")
        instantes = [cuando] if cuando else []
        hechos = aprobados.get(r, set())
        ocupantes = _humanos_del_rol(politica, r, instantes) if instantes else set()
        estado_roles[r] = {
            "regla": regla,
            "aprobada_por": sorted(hechos),
            "cumplida": _regla_cumplida(regla, hechos, ocupantes),
        }
    cumplidas = [r for r, e in estado_roles.items() if e["cumplida"]]
    autorizado = (
        bool(requeridos)
        and not problemas
        and (len(cumplidas) == len(requeridos) if modo == "cada_uno" else bool(cumplidas))
    )
    if autorizado:
        codigo = None
    elif not any(x["valida"] for x in resultados) and any(x["codigo"] == "APROBACION_CADUCADA" for x in resultados):
        codigo = "APROBACION_CADUCADA"
    else:
        codigo = "AUTORIDAD_INSUFICIENTE"
    return {
        "autorizado": autorizado,
        "codigo": codigo,
        "digest": d,
        "requeridos": requeridos,
        "modo": modo,
        "roles": estado_roles,
        "revisiones": resultados,
        "aprobaciones": aprobaciones if autorizado else [],
        "problemas": problemas,
        "politica": politica.revision,
    }
