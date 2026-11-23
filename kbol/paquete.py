"""Paquete de aprobación: lo que la persona ve antes de aprobar una propuesta.

Solo lee. Para una base, una propuesta y un `operacion_id` devuelve, por registro tocado, qué cambia en la cabecera y
en cada cláusula (y, si `modifica` otra, el texto que rige ahora junto al nuevo), los efectos solicitados, si es
decisivo y por qué, sus apoyos y si rigen en el corte pedido, y su digest; además, el impacto sobre otros registros,
lo que el paquete no evalúa y el esqueleto de la aprobación declarada.

Los digests salen del mismo código que la puerta (`integrar.preparar_solicitud`): la misma normalización de efectos e
importaciones. Si la puerta fuera a bloquear la propuesta por algo que no depende de la aprobación, el paquete se
bloquea antes con el mismo código y motivo (`integrar.arbol_final` hace las comprobaciones del árbol final). El
esqueleto lleva la base mostrada y los digests; la identidad, la sesión, el instante y la cita van vacíos: los aporta
quien recoge la aprobación, y el generador nunca los escribe ni los supone.
"""

import json
import re
import unicodedata

from .declarada import CAMPOS as CAMPOS_DECLARADA
from .declarada import MECANISMO as MECANISMO_DECLARADA
from .digest import EXCLUIDOS, SUPERIORES
from .impacto import impacto
from .integrar import Bloqueo, arbol_final, aviso_de_vocabulario, lo_aprobable, preparar_solicitud
from .markdown import ErrorDeMarca, clausulas
from .soporte import soporte
from .tiempo import es_instante

# Lo que no es contenido que se aprueba: el historial, las proyecciones y las evaluaciones. El estado se muestra como
# efecto solicitado, no como campo.
RUIDO = (EXCLUIDOS - set(SUPERIORES)) | {"id"}
PERSONALES = ("identidad", "sesion", "instante", "cita")
NO_EVALUADO = [
    "autoridad: quién puede aprobar y si la aprobación cumple la regla de su rol (la comprueba la integración)",
    "autenticidad de quien aprueba: una aprobación declarada nunca está autenticada",
    "respaldo semántico de los apoyos y de las citas",
    "apoyos no declarados",
    "apoyos con los efectos de esta operación: se evalúan en la propuesta, antes de integrar",
    "que la rama canónica siga en la base al integrar",
]
_RECORTE = 160


def preparar_aprobacion(repo, *, carpeta, operacion_id, base, propuesta, valido_en, conocido_hasta=None):
    """Paquete de aprobación de una propuesta, o el `bloqueado` de la puerta con su código.

    Devuelve {estado, operacion_id, base, propuesta, cortes, registros, impacto, vocabulario, advertencias,
    no_evaluado, aprobaciones}. `estado` es `completado`; `registros` puede estar vacío si la propuesta no toca
    ninguno. `vocabulario` son los hallazgos de términos y ámbitos que la puerta avisaría en el recibo.
    """
    for nombre, valor in (("valido_en", valido_en), ("conocido_hasta", conocido_hasta)):
        if (valor is not None or nombre == "valido_en") and not es_instante(valor):
            motivo = f"{nombre} no es un instante ISO 8601 con zona"
            return {"operacion_id": operacion_id, "estado": "bloqueado", "codigo": "TIEMPO_AMBIGUO", "motivo": motivo}
    try:
        p = preparar_solicitud(repo, carpeta=carpeta, operacion_id=operacion_id, base=base, propuesta=propuesta)
        final, advertencias, vocabulario = arbol_final(p) if p.tocados else (None, [], [])
    except Bloqueo as b:
        return {"operacion_id": operacion_id, **b.resultado}
    apoyos = soporte(p.prop_snap, valido_en=valido_en, conocido_hasta=conocido_hasta, ids=p.tocados)
    por_id = {r["id"]: r for r in apoyos["registros"]}
    digests = p.digests()
    registros = [_registro(p, i, digests[i], por_id[i]) for i in p.tocados]
    deuda = impacto(p.base_snap, final) if final is not None else {"cambiados": [], "afectados": [], "advertencias": []}
    advertencias = advertencias + apoyos["advertencias"] + deuda.pop("advertencias")
    esqueleto = {k: None for k in CAMPOS_DECLARADA}
    esqueleto.update(mecanismo=MECANISMO_DECLARADA, base_mostrada=base, digests=digests)
    return {
        "estado": "completado",
        "operacion_id": operacion_id,
        "base": base,
        "propuesta": propuesta,
        "cortes": {"valido_en": valido_en, "conocido_hasta": conocido_hasta},
        "registros": registros,
        "impacto": {"cambiados": deuda["cambiados"], "afectados": deuda["afectados"]},
        "vocabulario": vocabulario,
        "advertencias": advertencias,
        "no_evaluado": list(NO_EVALUADO),
        "aprobaciones": [esqueleto],
    }


def _registro(p, ident, digest, apoyos):
    r, c = p.prop_snap.registros[ident], p.prop_snap.cuerpos[ident]
    antes, cuerpo_antes = p.base_snap.registros.get(ident), p.base_snap.cuerpos.get(ident)
    efectos, importacion = lo_aprobable(ident, p.efectos, p.importaciones)
    if importacion is not None:
        importacion = {**importacion, "estado_heredado": p.importaciones[ident]["estado_heredado"]}
    if ident in p.importaciones:
        cambio = "importado"
    elif ident in p.mut["nuevos"]:
        cambio = "nuevo"
    elif ident in p.mut["modificados"]:
        cambio = "modificado"
    else:
        cambio = "solo_efectos"
    motivos = p.motivos_decisivos(ident)
    salida = {
        "id": ident,
        "tipo": r.get("type"),
        "titulo": r.get("title"),
        "ruta": p.prop_snap.rutas[ident],
        "cambio": cambio,
        "cabecera": _cabecera(antes, r),
        "clausulas": _clausulas(cuerpo_antes, c),
        "cuerpo_cambiado": (cuerpo_antes or "") != (c or ""),
        "fuera_de_clausulas": _fuera_de_clausulas(cuerpo_antes, c),
        "cuerpo_ilegible": _anclas(c) is None,
        "modifica": _modifica(p, r),
        "efectos": efectos,
        "importacion": importacion,
        "decisivo": bool(motivos),
        "motivos_decisivo": motivos,
        "apoyos": apoyos["apoyos"],
        "soporte": apoyos["soporte"],
        "digest": digest,
    }
    if "cuerpo" in apoyos:
        salida["aviso_cuerpo"] = apoyos["cuerpo"]
    return salida


def _vacio(valor):
    return valor is None or valor == [] or valor == {} or valor == ""


def _cabecera(antes, despues):
    """[{campo, antes, despues}] de los campos que cambian, en el orden de la propuesta y sin ruido."""
    antes = antes or {}
    campos = [k for k in despues if k not in RUIDO] + [k for k in antes if k not in RUIDO and k not in despues]
    return [
        {"campo": k, "antes": antes.get(k), "despues": despues.get(k)}
        for k in campos
        if antes.get(k) != despues.get(k) and not (_vacio(antes.get(k)) and _vacio(despues.get(k)))
    ]


def _anclas(cuerpo):
    try:
        return clausulas(cuerpo or "")
    except ErrorDeMarca:
        return None


_BLOQUE = re.compile(r"<clausula\b[^>]*>.*?</clausula>", re.DOTALL)


def _fuera_de_clausulas(cuerpo_antes, cuerpo_despues):
    """{antes, despues} del texto del cuerpo que no está en ninguna cláusula, si cambia; None si no cambia.

    El digest cubre todo el cuerpo: lo que queda fuera de las cláusulas también se aprueba y tiene que verse. Se
    obtiene quitando los bloques de cláusula tal como están escritos; ante la duda deja texto de más, no de menos.
    """
    antes, despues = (" ".join(_BLOQUE.sub("", c or "").split()) for c in (cuerpo_antes, cuerpo_despues))
    return {"antes": antes or None, "despues": despues or None} if antes != despues else None


def _clausulas(cuerpo_antes, cuerpo_despues):
    """[{ancla, cambio, antes?, despues?}]: cláusulas nuevas, cambiadas y eliminadas."""
    a, d = _anclas(cuerpo_antes) or {}, _anclas(cuerpo_despues) or {}
    cambios = []
    for ancla, texto in d.items():
        if ancla not in a:
            cambios.append({"ancla": ancla, "cambio": "nueva", "despues": texto})
        elif a[ancla] != texto:
            cambios.append({"ancla": ancla, "cambio": "cambiada", "antes": a[ancla], "despues": texto})
    cambios += [{"ancla": k, "cambio": "eliminada", "antes": v} for k, v in a.items() if k not in d]
    return cambios


def _texto_de(snapshot, referencia):
    """Texto de la cláusula `ID#ancla` en un snapshot, o None si no está."""
    if not isinstance(referencia, str):
        return None
    ident, _, ancla = referencia.partition("#")
    anclas = _anclas(snapshot.cuerpos.get(ident)) if ident in snapshot.cuerpos else None
    return (anclas or {}).get(ancla)


def _modifica(p, registro):
    """Cada `modifica`, con el texto que rige ahora en la base y el que propone poner en su lugar."""
    salida = []
    for mod in registro.get("modifica") or []:
        if not isinstance(mod, dict):
            continue
        salida.append(
            {
                "destino": mod.get("destino"),
                "tipo": mod.get("tipo"),
                "por": mod.get("por"),
                "texto_actual": _texto_de(p.base_snap, mod.get("destino")),
                "texto_nuevo": _texto_de(p.prop_snap, mod.get("por")),
            }
        )
    return salida


def _linea(texto):
    """Una línea para la terminal: sin saltos ni caracteres de control o de formato, que podrían ocultar texto."""
    # Los saltos y tabuladores se pliegan como espacio; el resto de control y de formato (incluidas las marcas
    # bidireccionales) se sustituye, para que nada de lo que se aprueba quede oculto en la terminal.
    visible = "".join(
        " " if c in "\n\r\t" else "\ufffd" if unicodedata.category(c) in ("Cc", "Cf") else c for c in str(texto)
    )
    return " ".join(visible.split())


def _valor(valor):
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    texto = _linea(texto)
    if len(texto) <= _RECORTE:
        return texto
    return f"{texto[:_RECORTE]}… (+{len(texto) - _RECORTE} caracteres, completos en la salida JSON)"


def presentar(paquete):
    """Texto breve para la persona que aprueba: qué cambia, efectos, evidencia, impacto, qué es decisivo, qué no se
    evaluó y los digests. Sin YAML ni diff completo; los textos de las cláusulas, enteros."""
    if paquete["estado"] == "bloqueado":
        return (
            f"Paquete de aprobación de {paquete['operacion_id']}: bloqueado ({paquete['codigo']}): {paquete['motivo']}"
        )
    lineas = [
        f"Paquete de aprobación de {paquete['operacion_id']}: base {paquete['base'][:12]}, "
        f"propuesta {paquete['propuesta'][:12]}, apoyos al {paquete['cortes']['valido_en']}."
    ]
    if not paquete["registros"]:
        lineas.append("La propuesta no cambia ningún registro: no hay nada que aprobar.")
    for r in paquete["registros"]:
        lineas.append(f"{r['id']} ({r['tipo']}, {r['cambio'].replace('_', ' ')}): {_linea(r['titulo'] or '')}")
        if r["cambio"] in ("nuevo", "importado"):
            # Un registro nuevo no tiene «antes»: su cabecera, campo a campo, sin lo que ya dice el encabezado.
            lineas += [
                f"  {c['campo']}: {_valor(c['despues'])}" for c in r["cabecera"] if c["campo"] not in ("type", "title")
            ]
        else:
            lineas += [f"  {c['campo']}: {_valor(c['antes'])} → {_valor(c['despues'])}" for c in r["cabecera"]]
        for c in r["clausulas"]:
            if c["cambio"] == "nueva":
                lineas.append(f"  Cláusula {c['ancla']} nueva: «{_linea(c['despues'])}»")
            elif c["cambio"] == "cambiada":
                lineas.append(f"  Cláusula {c['ancla']} cambiada: «{_linea(c['antes'])}» → «{_linea(c['despues'])}»")
            else:
                lineas.append(f"  Cláusula {c['ancla']} eliminada: «{_linea(c['antes'])}»")
        fuera = r["fuera_de_clausulas"]
        if fuera:
            antes = f"«{_linea(fuera['antes'])}» → " if fuera["antes"] else ""
            despues = f"«{_linea(fuera['despues'])}»" if fuera["despues"] else "(se elimina)"
            lineas.append(f"  Texto fuera de las cláusulas: {antes}{despues}")
        if r["cuerpo_ilegible"]:
            lineas.append("  AVISO: las marcas del cuerpo no se pudieron leer; sus cláusulas no se muestran.")
        for m in r["modifica"]:
            actual = f"«{_linea(m['texto_actual'])}»" if m["texto_actual"] is not None else "(sin texto en la base)"
            nuevo = f" → «{_linea(m['texto_nuevo'])}»" if m["texto_nuevo"] is not None else ""
            lineas.append(f"  Modifica {m['destino']} ({m['tipo']}): ahora {actual}{nuevo}")
        for ef in r["efectos"]:
            hasta = f" hasta {ef['valido_hasta']}" if "valido_hasta" in ef else ""
            lineas.append(f"  Efecto: {ef['estado_anterior']} → {ef['estado_nuevo']} desde {ef['valido_desde']}{hasta}")
        if r["importacion"]:
            imp = r["importacion"]
            lineas.append(
                f"  Importación: {imp['estado_heredado']} → {imp['estado']} desde {imp['valido_desde']} "
                f"({imp['precision']}); autoridad heredada: {_valor(imp['autoridad_heredada'])}"
            )
        if r["decisivo"]:
            lineas.append(f"  Decisivo: {'; '.join(r['motivos_decisivo'])}")
        else:
            lineas.append("  No decisivo.")
        if r["apoyos"]:
            lineas.append(f"  Apoyos ({r['soporte']}):")
            lineas += [f"  - {a['ref']} ({a['campo']}): {a['situacion']}, {_linea(a['motivo'])}" for a in r["apoyos"]]
        else:
            lineas.append("  Sin apoyos declarados.")
        lineas.append(f"  Digest: {r['digest']}")
    afectados = paquete["impacto"]["afectados"]
    if afectados:
        lineas.append("Impacto en otros registros:")
        lineas += [f"- {a['afectado']} ({a['tipo']}): {a['causa']}, por {' → '.join(a['camino'])}" for a in afectados]
    elif paquete["registros"]:
        lineas.append("Impacto: ningún otro registro declara depender de lo que cambia.")
    if paquete["vocabulario"]:
        lineas.append("Vocabulario del dominio:")
        lineas += [f"- {_linea(aviso_de_vocabulario(h))}" for h in paquete["vocabulario"]]
    lineas += [f"Aviso: {a}" for a in paquete["advertencias"]]
    lineas.append("No evaluado: " + "; ".join(paquete["no_evaluado"]) + ".")
    if paquete["registros"]:
        lineas.append(
            f"Aprobación declarada: base mostrada {paquete['base']}; la identidad, la sesión, el instante y la cita los "
            "aporta quien recoge la aprobación."
        )
    return "\n".join(lineas)
