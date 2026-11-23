"""preparar_contexto (KB-DPP implementación 0.8, «Paquete de contexto para una tarea»; ESC-06 y ESC-09).

Solo lectura. Reúne para una tarea lo que la sesión necesita antes de actuar: el objetivo; las restricciones
decisivas (las instrucciones que la instalación declara decisivas, las cláusulas vigentes de las decisiones canónicas
del ámbito con su origen y, como incertidumbres decisivas, las cláusulas en conflicto, ambiguas o sin texto); aparte
y marcadas como no vinculantes, las propuestas del ámbito y los pendientes (preguntas abiertas, también las del
formato heredado si se pide); los procedimientos que declara la instalación, y el relevo de la tarea, que es lo que
la sesión declaró, no conocimiento normativo.

El presupuesto se cuenta en elementos. Las restricciones decisivas nunca se recortan: si no caben, el paquete sale
`parcial` con su motivo. Si la carga de los registros no es completa, el paquete tampoco lo es: sale `parcial` o
`bloqueado`, porque una restricción decisiva puede faltar. Lo no decisivo se recorta en orden (pendientes heredados,
pendientes, propuestas, procedimientos, instrucciones no decisivas) y cada omisión dice por qué. El paquete referencia
y no copia: las instrucciones van como `ruta#ancla` con un resumen. `refrescar_si` dice qué cambios lo invalidan. No
concede autorización: cada efecto revalida su autoridad en el núcleo.
"""

import hashlib
import json
import uuid

from . import relevo as rv
from .consolidar import consolidar
from .eventos import ErrorDeHistorial, admitidos
from .migracion import formato_de
from .proyeccion import estado_al_corte
from .snapshot import cargar
from .verificar import verificaciones_de

# Estados en que un registro es una propuesta (no vinculante) y en que una pregunta sigue pendiente.
PROPUESTOS = {"propuesta", "propuesto", "borrador"}
ABIERTAS = {"abierta"}
# Roles y personas son la política de la instalación, no conocimiento de la tarea: no entran como propuestas.
POLITICA = {"rol", "persona"}
# Estados de cláusula que no se pueden resolver: la sesión debe saber que ahí hay una incertidumbre decisiva.
INCIERTAS = {"conflicto", "ambigua", "sin_regla", "sin_texto"}
# Orden en que se recorta lo no decisivo: lo último de la lista es lo primero que sale.
ORDEN_NO_DECISIVO = ("instruccion", "procedimiento", "propuesta", "pendiente", "pendiente_heredado")
AVISOS_EN_TEXTO = 5


def _ahora():
    return rv._ahora()


def _huella(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _estado(registro, conocido_hasta):
    """Estado para clasificar lo no vinculante: el del historial admitido o, sin historial, el declarado (en modo
    propuesta solo puede ser el inicial del tipo)."""
    if not admitidos(registro.get("eventos") or []):
        return registro.get("estado")
    try:
        return estado_al_corte(registro, conocido_hasta)
    except ErrorDeHistorial:
        return None


def validar_instalacion(instalacion):
    """La configuración de la instalación que usa el paquete; ValueError si no tiene la forma esperada."""
    if not isinstance(instalacion, dict):
        raise ValueError("la configuración de la instalación es un objeto")
    for i in instalacion.get("instrucciones", []):
        if not isinstance(i, dict) or not isinstance(i.get("ref"), str) or not isinstance(i.get("resumen"), str):
            raise ValueError("cada instrucción tiene ref y resumen")
        if not isinstance(i.get("decisiva", False), bool):
            raise ValueError("decisiva es verdadero o falso")
    for p in instalacion.get("procedimientos", []):
        if not isinstance(p, dict) or not isinstance(p.get("ref"), str):
            raise ValueError("cada procedimiento tiene ref")
    verificaciones_de(instalacion)
    formato_de(instalacion)


def preparar_contexto(
    raiz,
    *,
    tarea,
    objetivo,
    ambito,
    carpeta,
    instalacion,
    valido_en,
    conocido_hasta=None,
    revision=None,
    presupuesto=30,
    heredados=None,
    cargado=None,
):
    """Paquete de contexto de la tarea (dict). `instalacion` es la configuración del proyecto ya leída. `cargado` es
    el `(snapshot, cobertura)` de esa misma carpeta y revisión en modo propuesta y con heredados, si quien llama ya lo
    tiene: así dos operaciones sobre los mismos registros los leen una vez."""
    validar_instalacion(instalacion)
    if not isinstance(presupuesto, int) or presupuesto < 0:
        raise ValueError("el presupuesto es un número de elementos, 0 o más")
    # Modo propuesta: una propuesta aún no integrada se nombra como tal, no desaparece como inválida. Lo vigente
    # sigue exigiendo historial admitido (consolidar), así que una propuesta nunca pasa por decisión vigente.
    formato = formato_de(instalacion)
    snapshot, cobertura = cargado or cargar(
        raiz, carpeta, revision, modo="propuesta", heredados=True, formato=formato
    )
    advertencias = list(cobertura["advertencias"])
    del_ambito = {i: r for i, r in snapshot.registros.items() if r.get("ambito") == ambito}

    decisivas = [
        {"origen": i["ref"], "texto": i["resumen"], "decisiva": True}
        for i in instalacion.get("instrucciones", [])
        if i.get("decisiva")
    ]
    # Solo las decisiones con historial admitido pueden regir; las propuestas van aparte.
    vigentes = sorted(i for i, r in del_ambito.items() if r["type"] == "decision" and admitidos(r.get("eventos") or []))
    if vigentes:
        res = consolidar(snapshot, vigentes, valido_en=valido_en, conocido_hasta=conocido_hasta)
        advertencias += res["advertencias"]
        for c in res["clausulas"]:
            if c["estado"] == "vigente":
                decisivas.append({"origen": c["origen"], "texto": c["texto"], "decisiva": True})
            elif c["estado"] in INCIERTAS:
                texto = f"cláusula {c['estado'].replace('_', ' ')}: no se sabe qué rige"
                decisivas.append({"origen": c["referencia"], "texto": texto, "decisiva": True, "incierta": True})
        for c in res["conflictos"]:
            decisivas.append(
                {
                    "origen": c["clausula"],
                    "texto": "conflicto normativo sin resolver",
                    "decisiva": True,
                    "incierta": True,
                }
            )
        for a in res["advertencias"]:
            if a.startswith("CONFLICTO_NORMATIVO"):
                decisivas.append({"origen": "consolidado", "texto": a, "decisiva": True, "incierta": True})

    candidatos = [
        {"tipo": "instruccion", "origen": i["ref"], "texto": i["resumen"], "decisiva": False}
        for i in instalacion.get("instrucciones", [])
        if not i.get("decisiva")
    ]
    candidatos += [{**p, "tipo": "procedimiento"} for p in instalacion.get("procedimientos", [])]
    candidatos += [
        {"tipo": "propuesta", "id": i, "titulo": r.get("title"), "vinculante": False}
        for i, r in sorted(del_ambito.items())
        if r["type"] not in POLITICA and _estado(r, conocido_hasta) in PROPUESTOS
    ]
    candidatos += [
        {"tipo": "pendiente", "id": i, "titulo": r.get("title"), "vinculante": False, "formato": "perfil"}
        for i, r in sorted(del_ambito.items())
        if r["type"] == "pregunta" and _estado(r, conocido_hasta) in ABIERTAS
    ]
    if heredados:
        herencia, cob_h = cargar(raiz, heredados, revision, heredados=True, formato=formato)
        if cob_h["estado"] != "completo":
            advertencias.append(f"lectura del formato heredado {cob_h['estado']}")
        candidatos += [
            {"tipo": "pendiente_heredado", "id": i, "vinculante": False, "formato": "heredado"}
            for i, f in sorted(herencia.heredados.items())
            if f["tipo"] == "pregunta" and f["estado_propuesto"] == "abierta"
        ]

    estado, motivos = "completado", []
    if cobertura["estado"] != "completo":
        # Un registro que no se pudo leer podría llevar una restricción decisiva: el paquete no se da por completo.
        estado = "bloqueado" if cobertura["estado"] == "bloqueado" else "parcial"
        motivos.append(f"la carga de los registros es {cobertura['estado']}: puede faltar una restricción decisiva")
    if not del_ambito:
        estado = "parcial" if estado == "completado" else estado
        motivos.append(f"ningún registro en el ámbito {ambito!r}: ¿está bien escrito?")
    if len(decisivas) > presupuesto:
        estado = "parcial" if estado == "completado" else estado
        motivos.append(
            f"las restricciones decisivas ({len(decisivas)}) no caben en el presupuesto ({presupuesto}): no se recortan"
        )
    libres = max(presupuesto - len(decisivas), 0)
    candidatos.sort(key=lambda c: ORDEN_NO_DECISIVO.index(c["tipo"]))
    incluidos, omitidos = candidatos[:libres], candidatos[libres:]

    rel = rv.relevo(raiz, tarea, rama_canonica=instalacion.get("rama_canonica", "main"))
    git = rel["git"]
    paquete = {
        "paquete_id": str(uuid.uuid4()),
        "tarea": tarea,
        "revision": snapshot.revision,
        "preparado_en": _ahora(),
        "alcance": {"ambito": ambito, "carpeta": carpeta, "proyecto": instalacion.get("proyecto")},
        "cortes": {"valido_en": valido_en, "conocido_hasta": conocido_hasta},
        "estado": estado,
        "motivo": "; ".join(motivos) or None,
        "objetivo": objetivo or rel["objetivo"],
        "restricciones": decisivas + [c for c in incluidos if c["tipo"] == "instruccion"],
        "propuestas": [c for c in incluidos if c["tipo"] == "propuesta"],
        "pendientes": [c for c in incluidos if c["tipo"] in ("pendiente", "pendiente_heredado")],
        "procedimientos": [c for c in incluidos if c["tipo"] == "procedimiento"],
        "relevo": rel,
        "omitidos": [
            {"tipo": c["tipo"], "id": c.get("id") or c.get("origen") or c.get("ref"), "motivo": "presupuesto agotado"}
            for c in omitidos
        ],
        "presupuesto": {"cantidad": presupuesto, "unidad": "elementos", "usados": len(decisivas) + len(incluidos)},
        "cobertura": {
            "estado": cobertura["estado"],
            "leidos": cobertura["leidos"],
            "invalidos": cobertura["invalidos"],
            "no_evaluado": ["autenticidad de las aprobaciones", "integridad de las fuentes"],
        },
        "refrescar_si": [
            {"dato": "revision", "valor": snapshot.revision},
            {"dato": "cabeza", "valor": git.get("cabeza"), "sucia": bool(git.get("cambios_locales"))},
            {"dato": "relevo", "valor": rel.get("actualizado_en")},
            {
                "dato": "registros",
                "valor": {i: _huella([r, snapshot.cuerpos.get(i)]) for i, r in sorted(del_ambito.items())},
            },
            {"dato": "instalacion", "valor": _huella(instalacion)},
            {"dato": "cortes", "valor": {"valido_en": valido_en, "conocido_hasta": conocido_hasta}},
        ],
        "advertencias": advertencias,
    }
    return paquete


def _verificaciones_abiertas(rel):
    return [v for v in rel["verificaciones"] if v.get("resultado") != "pasa" or v.get("desfasada") is not False]


def _con_titulo(elemento, limite=140):
    """«- ID: título», con el título en una línea y recortado: sin él, la sesión solo ve un identificador."""
    titulo = " ".join(str(elemento.get("titulo") or "").split())
    if len(titulo) > limite:
        titulo = titulo[: limite - 1] + "…"
    return f"- {elemento['id']}: {titulo}" if titulo else f"- {elemento['id']}"


def presentar(paquete):
    """Texto breve para inyectar en una sesión: lo decisivo primero; lo no vinculante y lo que declaró la sesión,
    marcados como tales; las condiciones de parada siempre."""
    lineas = [f"Contexto de KBOL para la tarea {paquete['tarea']} (revisión {str(paquete['revision'])[:12]})."]
    if paquete["estado"] != "completado":
        lineas.append(f"Paquete {paquete['estado']}: {paquete['motivo']}")
    if paquete.get("objetivo"):
        lineas.append(f"Objetivo: {paquete['objetivo']}")
    if paquete["restricciones"]:
        lineas.append("Restricciones:")
        lineas += [
            f"- {r['texto']} ({r['origen']}{'' if r['decisiva'] else ', orientativa'})"
            for r in paquete["restricciones"]
        ]
    if paquete["propuestas"]:
        lineas.append("Propuestas (no vinculantes, no autorizan nada):")
        lineas += [_con_titulo(p) for p in paquete["propuestas"]]
    if paquete["pendientes"]:
        lineas.append("Pendientes:")
        lineas += [_con_titulo(p) for p in paquete["pendientes"]]
    if paquete["procedimientos"]:
        lineas += [f"Procedimiento: {p['ref']} ({p.get('cuando', '')})" for p in paquete["procedimientos"]]
    rel = paquete["relevo"]
    if rel["estado"] == "guardado":
        lineas.append(
            f"Relevo de la tarea (declarado por la sesión el {rel['actualizado_en']}; no es normativo ni autoriza "
            f"nada); estado de entrega: {rel['estado_entrega']}."
        )
        aut = rel["autorizacion"] or {}
        if aut.get("referencia"):
            lineas.append(f"  Autorización declarada: {aut['referencia']} (sin verificar)")
        if aut.get("limites"):
            lineas.append("  Límites declarados: " + "; ".join(aut["limites"]))
        for b in rel["bloqueos"]:
            lineas.append(f"  Bloqueo: {b}")
        for p in rel["preguntas"]:
            lineas.append(f"  Pregunta: {p}")
        for v in _verificaciones_abiertas(rel):
            estado = "desfasada" if v.get("desfasada") is True else v["resultado"]
            quien = "anotada por kbol verificar, sin recibo" if v.get("origen") == "kbol" else "declarada por la sesión"
            lineas.append(f"  Verificación {estado} ({quien}): {v['comando']}")
        if rel["siguiente_paso"]:
            lineas.append(f"  Siguiente paso: {rel['siguiente_paso']['accion']}")
        if rel["no_consta"]:
            lineas.append("  No consta: " + ", ".join(rel["no_consta"]))
    if rel["git"].get("cambios_locales"):
        lineas.append(f"Cambios locales sin commitear: {len(rel['git']['cambios_locales'])} archivos.")
    if paquete["omitidos"]:
        lineas.append(f"Omitidos por presupuesto: {len(paquete['omitidos'])} elementos no decisivos.")
    avisos = paquete["advertencias"]
    lineas += [f"Aviso: {a}" for a in avisos[:AVISOS_EN_TEXTO]]
    if len(avisos) > AVISOS_EN_TEXTO:
        lineas.append(f"Avisos omitidos en el texto: {len(avisos) - AVISOS_EN_TEXTO} (salida JSON completa).")
    return "\n".join(lineas)
