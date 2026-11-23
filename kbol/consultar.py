"""Consulta por ID: dado `ID` o `ID#ancla`, el registro con su estado al corte, su autoridad y el texto del ancla.

Es la base del vínculo de una memoria o una nota con el conocimiento canónico: resolver lo que se
cita sin interpretarlo. Un ID canónico devuelve su tipo, su estado al corte de conocimiento, su autoridad (declarada,
heredada o ninguna comprobada), sus relaciones y, con ancla, el texto de la cláusula; en una decisión, además, si esa
cláusula rige en `valido_en`. Un ID heredado se nombra con su estado heredado y no rige. Un ID que no existe, o un
ancla que su registro no tiene, se dice así. Su evidencia son sus apoyos, los mismos que evalúa `soporte`
(`basada_en`, `dependencias`, `sources` y `<hecho ref>`), con la misma regla de vigencia: un apoyo
que no existe, no rige en el corte o no se puede decidir, o un cuerpo cuyas citas no se pueden leer, deja la evidencia
insuficiente con su motivo. Solo lee.
"""

from . import soporte
from .consolidar import _Consulta, consolidar
from .markdown import ErrorDeMarca, clausulas
from .modelo import CAMPOS_DE_TRABAJO, RELACIONES
from .mutabilidad import CERRADOS
from .proyeccion import estado_al_corte
from .sustituciones import avisos_para, no_declaradas
from .tiempo import instante

# Relaciones que se informan: las listas de la cabecera que apuntan a otros registros, salvo los apoyos que son campos
# propios del tipo (`dependencias`, `sources`), que se informan en la evidencia. El responsable va en el trabajo.
# `define` no apunta a otro registro, pero dice qué términos declara una decisión.
_RELACIONES = (*RELACIONES, "modifica", "depende_de", "ocupa", "hitos", "define")


def _anclas(cuerpo):
    try:
        return clausulas(cuerpo or "")
    except ErrorDeMarca:
        return None


def _evidencia(consulta, r, cuerpo):
    """Apoyos del registro con si existen y si rigen; None si no declara ninguno."""
    evaluado = soporte.evaluar(consulta, r, cuerpo)
    if not evaluado["apoyos"] and "cuerpo" not in evaluado:
        return None
    evidencia = {
        "apoyos": [{**a, "existe": a["situacion"] != "ausente"} for a in evaluado["apoyos"]],
        "suficiente": evaluado["soporte"] == "intacto",
    }
    if not evidencia["suficiente"]:
        motivos = [
            f"{a['ref']} {a['situacion']}: {a['motivo']}"
            for a in evaluado["apoyos"]
            if a["situacion"] in soporte.NO_SOSTIENEN
        ]
        evidencia["motivo"] = "; ".join(motivos + ([evaluado["cuerpo"]] if "cuerpo" in evaluado else []))
    return evidencia


def _uno(snapshot, consulta, ref, valido_en, conocido_hasta):
    ident, _, ancla = ref.partition("#")
    if ident not in snapshot.registros:
        if ident in snapshot.heredados:
            ficha = snapshot.heredados[ident]
            return {
                "referencia": ref,
                "encontrado": "heredado",
                "id": ident,
                "tipo": ficha.get("tipo"),
                "ruta": ficha.get("ruta"),
                "estado_heredado": ficha.get("estado_heredado"),
                "estado_propuesto": ficha.get("estado_propuesto"),
                "rige": False,
            }
        return {"referencia": ref, "encontrado": "ausente", "id": ident}
    r, cuerpo = snapshot.registros[ident], snapshot.cuerpos.get(ident)
    salida = {
        "referencia": ref,
        "encontrado": "canonico",
        "id": ident,
        "tipo": r.get("type"),
        "titulo": r.get("title"),
        "ambito": r.get("ambito"),
        "ruta": snapshot.rutas.get(ident),
        "estado": estado_al_corte(r, conocido_hasta),
        "autoridad": {
            "autorizado_por": list(r.get("autorizado_por") or []),
            "ratificaciones": consulta._ratificaciones(r),
            "declaradas": consulta._declaradas(r),
            "aprobaciones": consulta._aprobaciones(r),
            "heredada": consulta._heredada(r),
            "comprobada": False,
        },
        "relaciones": {rel: r[rel] for rel in _RELACIONES if r.get(rel)},
    }
    # Quién la declara sustituida o modificada: la relación vive en el otro registro y aquí se lee al revés.
    inversas = {
        "dejada_obsoleta_por": sorted(i for i, o in snapshot.registros.items() if ident in (o.get("deja_obsoleta") or [])),
        "modificada_por": sorted(m for m, _ in consulta.por_destino.get(ident, []))
        + sorted({m for d, mods in consulta.por_destino.items() if d.startswith(f"{ident}#") for m, _ in mods}),
    }
    inversas = {k: list(dict.fromkeys(v)) for k, v in inversas.items() if v}
    if inversas:
        salida["relaciones_inversas"] = inversas
    trabajo = {k: r[k] for k in CAMPOS_DE_TRABAJO if r.get(k)}
    if trabajo:
        salida["trabajo"] = trabajo
    if r.get("type") == "persona":
        salida["asignado"] = asignado(snapshot, ident, valido_en)
    if ancla:
        anclas = _anclas(cuerpo)
        if anclas is None or ancla not in anclas:
            salida["encontrado"] = "ancla_ausente"
            return salida
        salida["texto"] = anclas[ancla]
    if r.get("type") == "decision":
        vigencia = consolidar(snapshot, [ident], valido_en=valido_en, conocido_hasta=conocido_hasta)
        salida["vigencia"] = vigencia["vigencia"].get(ident)
        if ancla:
            clausula = next((c for c in vigencia["clausulas"] if c.get("referencia") == ref), None)
            if clausula:
                salida["clausula"] = {k: clausula.get(k) for k in ("estado", "texto", "origen", "cadena")}
    evidencia = _evidencia(consulta, r, cuerpo)
    if evidencia:
        salida["evidencia"] = evidencia
    return salida


def _roles_de(persona, cuando):
    """Roles que ocupa la persona en `cuando`; sin corte, los que ocupa sin fecha de fin."""
    t = instante(cuando) if cuando else None
    roles = set()
    for o in persona.get("ocupa") or []:
        if not isinstance(o, dict) or not isinstance(o.get("rol"), str):
            continue
        hasta = o.get("hasta")
        if t is None:
            if hasta is None:
                roles.add(o["rol"])
        elif instante(o["desde"]) <= t and (hasta is None or t < instante(hasta)):
            roles.add(o["rol"])
    return roles


def asignado(snapshot, persona_id, valido_en=None):
    """Hitos y preguntas de los que responde la persona, directamente o por un rol que ocupa.

    Las tareas no se copian en la persona: se leen aquí, de una sola fuente. Lista también si cada uno sigue
    abierto, para separar lo pendiente de lo cerrado.
    """
    persona = snapshot.registros.get(persona_id) or {}
    quien = {persona_id} | _roles_de(persona, valido_en)
    salida = []
    for i, r in sorted(snapshot.registros.items()):
        if r.get("type") in ("hito", "pregunta") and r.get("responsable") in quien:
            estado = r.get("estado")
            salida.append(
                {
                    "id": i,
                    "tipo": r["type"],
                    "titulo": r.get("title"),
                    "estado": estado,
                    "por": r["responsable"],
                    "abierto": estado not in CERRADOS.get(r["type"], ()),
                }
            )
    return salida


def consultar(snapshot, referencias, *, valido_en, conocido_hasta):
    """{cortes, resultados, advertencias} para cada `ID` o `ID#ancla` de `referencias`, en su orden."""
    consulta = _Consulta(snapshot, valido_en, conocido_hasta)
    resultados = [_uno(snapshot, consulta, ref, valido_en, conocido_hasta) for ref in referencias]
    advertencias = list(consulta.advertencias)
    indicios = no_declaradas(snapshot)
    for res in resultados:
        avisos = avisos_para(indicios, [res["id"]])
        if avisos:
            res["avisos_sustitucion"] = avisos
            advertencias += [a for a in avisos if a not in advertencias]
    for res in resultados:
        if res["encontrado"] == "heredado":
            advertencias.append(f"{res['id']} está en formato heredado: se nombra, pero no rige")
        elif res["encontrado"] in ("ausente", "ancla_ausente"):
            advertencias.append(f"{res['referencia']}: {res['encontrado'].replace('_', ' ')}")
        if res.get("evidencia") and not res["evidencia"]["suficiente"]:
            advertencias.append(f"{res['referencia']}: EVIDENCIA_INSUFICIENTE, {res['evidencia']['motivo']}")
    return {
        "cortes": {"valido_en": valido_en, "conocido_hasta": conocido_hasta, "revision": snapshot.revision},
        "resultados": resultados,
        "advertencias": advertencias,
    }
