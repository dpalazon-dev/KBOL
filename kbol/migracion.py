"""Migración en seco del formato heredado (KB-DPP implementación 0.8, §14).

Solo lee. Para cada registro propone tipo, estado, relaciones candidatas y un evento de importación sin instante de
incorporación, que asignará la integración. No inventa aprobaciones ni precisión temporal: la autoridad escrita en
prosa se clasifica, y todo lo que no se traduce uno a uno queda como ambigüedad para revisión humana.

El formato heredado por defecto (`POR_DEFECTO`) es el de ADR numerados, QD, HD, planes e hitos. Un proyecto con la
misma forma y otros IDs o palabras de estado lo declara en su instalación (`formato_heredado`): sus palabras se
traducen a las cabeceras de la tabla heredada, que decide con sus reglas de revisión. Sin declararlo, rige
`POR_DEFECTO`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .core import ErrorDeFormato, parse
from .modelo import TIPO_DE_PREFIJO, TIPOS
from .schema import campos_de

PRODUCTOR = "kbol-migracion/0.2"
TIPO_HEREDADO = {
    "Decisión": "decision",
    "Pregunta": "pregunta",
    "Hipótesis": "hipotesis",
    "Plan": "plan",
    "Hito": "hito",
}
_IDS = re.compile(r"\b(?:ADR-\d{4}|QD-\d{3,}|HD-\d{3,}|PL-\d{3}(?:-H\d+)?)\b")
# Forma completa de un ID del formato heredado por defecto: con fullmatch, ni prefijos ni sufijos.
ID_HEREDADO = re.compile(r"(?:ADR-\d{4}|QD-\d{3,}|HD-\d{3,}|PL-\d{3}(?:-H\d+)?)")
# Nombre de archivo de un registro del formato heredado por defecto: ADR («0063-slug.md», no «2026-05-19-x.md»), QD, HD, plan o hito.
NOMBRE_DE_REGISTRO = re.compile(r"(?:\d{4}-[a-z].*|(?:QD|HD)-\d{3,}|PL-\d{3}(?:-H\d+)?)\.md")
# Cabeceras de estado que entiende la tabla heredada, por tipo: los destinos posibles de una equivalencia.
CABECERAS = {
    "decision": ("Propuesta", "Aceptada", "Rechazada", "Sustituida por"),
    "pregunta": ("Abierta", "Resuelta", "Descartada", "En revisión"),
    "hipotesis": ("Abierta", "En validación", "Validada", "Descartada", "Obsoleta"),
    "plan": ("Propuesto", "Aprobado", "Cerrado", "En curso", "Rechazado", "Abandonado", "Sustituido por"),
    "hito": ("Pendiente", "En curso", "Cumplido", "Descartado"),
}
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Estados cuyo uso normativo exige una autoridad comprobable.
CON_AUTORIDAD = {"aceptada", "autorizado", "en_curso", "completado", "cerrado"}


@dataclass(frozen=True)
class FormatoHeredado:
    """Cómo escribe un proyecto su formato heredado.

    - `tipos`: etiqueta de `type` → tipo del contrato.
    - `ids`: etiqueta → patrón en el que encaja entero el ID de un registro de esa etiqueta.
    - `en_texto`: IDs del formato citados en prosa.
    - `decision`: IDs de decisión, los únicos que valen como `resuelta_por`.
    - `nombres`: nombre de archivo de un registro sin `id`.
    - `equivalencias`: etiqueta → {palabra de estado del proyecto: cabecera de la tabla heredada}.
    - `separadores`: caracteres que cierran la cabecera del estado.
    """

    tipos: dict
    ids: dict
    en_texto: re.Pattern
    decision: re.Pattern
    nombres: re.Pattern
    equivalencias: dict
    separadores: str = "(;"

    def es_registro(self, ruta):
        """True si el nombre del archivo es el de un registro: «0063-….md», «QD-045.md», «DEC-108.md»…

        Un documento con un `type` de registro (un plan de trabajo, una hoja de ruta) pero sin `id` ni nombre de
        registro no es un registro: se omite como cualquier otro documento.
        """
        return bool(self.nombres.fullmatch(Path(ruta).name))

    def id_valido(self, etiqueta, ident):
        return isinstance(ident, str) and etiqueta in self.ids and bool(self.ids[etiqueta].fullmatch(ident))

    def normalizar(self, etiqueta, texto):
        """El estado con su palabra inicial traducida a la cabecera equivalente de la tabla heredada."""
        for palabra, cabecera in sorted(self.equivalencias.get(etiqueta, {}).items(), key=lambda p: -len(p[0])):
            resto = texto[len(palabra) :]
            if texto.startswith(palabra) and not (resto[:1].isalnum() or resto[:1] == "_"):
                return cabecera + resto
        return texto


POR_DEFECTO = FormatoHeredado(
    tipos=TIPO_HEREDADO,
    ids=dict.fromkeys(TIPO_HEREDADO, ID_HEREDADO),
    en_texto=_IDS,
    decision=re.compile(r"ADR-\d{4}"),
    nombres=NOMBRE_DE_REGISTRO,
    equivalencias={},
)


def formato_de(instalacion):
    """El formato heredado que declara la instalación (`formato_heredado`), o `POR_DEFECTO` si no declara ninguno.

    ValueError si la declaración está mal formada: mejor no leer nada que leer con un formato a medias.
    """
    f = instalacion.get("formato_heredado") if isinstance(instalacion, dict) else None
    if f is None:
        return POR_DEFECTO
    if not isinstance(f, dict):
        raise ValueError("formato_heredado es un objeto")
    for clave in f:
        if clave not in ("registros", "separadores"):
            raise ValueError(f"formato_heredado: clave desconocida {clave!r}")
    registros = f.get("registros")
    if not isinstance(registros, dict) or not registros:
        raise ValueError("formato_heredado.registros asocia al menos una etiqueta de type con su tipo y su id")
    separadores = f.get("separadores", "(;")
    if not isinstance(separadores, str) or not separadores:
        raise ValueError("formato_heredado.separadores es una cadena no vacía")
    tipos, ids, equivalencias, patrones, de_decision = {}, {}, {}, [], []
    for etiqueta, d in registros.items():
        donde = f"formato_heredado.registros[{etiqueta!r}]"
        if etiqueta in TIPOS:
            raise ValueError(f"{donde}: {etiqueta!r} es un tipo del perfil, no una etiqueta heredada")
        if not isinstance(d, dict):
            raise ValueError(f"{donde} es un objeto con tipo, id y, si hace falta, equivalencias")
        for clave in d:
            if clave not in ("tipo", "id", "equivalencias"):
                raise ValueError(f"{donde}: clave desconocida {clave!r}")
        tipo, patron, equivale = d.get("tipo"), d.get("id"), d.get("equivalencias", {})
        if tipo not in CABECERAS:
            raise ValueError(f"{donde}: el tipo {tipo!r} no admite formato heredado ({', '.join(CABECERAS)})")
        if not isinstance(patron, str):
            raise ValueError(f"{donde}: id es el patrón de sus IDs")
        try:
            ids[etiqueta] = re.compile(patron)
        except re.error as exc:
            raise ValueError(f"{donde}: patrón de id inválido: {exc}") from None
        prefijo = re.match(r"([A-Z]{1,4})-", patron)
        if not prefijo:
            raise ValueError(f"{donde}: el patrón de id empieza por un prefijo literal en mayúsculas y un guion")
        if TIPO_DE_PREFIJO.get(prefijo.group(1), tipo) != tipo:
            raise ValueError(f"{donde}: el prefijo {prefijo.group(1)}- es de otro tipo del contrato")
        if not isinstance(equivale, dict):
            raise ValueError(f"{donde}: equivalencias es un objeto")
        for palabra, cabecera in equivale.items():
            if not palabra or cabecera not in CABECERAS[tipo]:
                raise ValueError(
                    f"{donde}: equivalencia {palabra!r} → {cabecera!r}: la tabla heredada no tiene esa cabecera "
                    f"para {tipo} ({', '.join(CABECERAS[tipo])})"
                )
        tipos[etiqueta], equivalencias[etiqueta] = tipo, dict(equivale)
        patrones.append(f"(?:{patron})")
        if tipo == "decision":
            de_decision.append(f"(?:{patron})")
    todos = "|".join(patrones)
    return FormatoHeredado(
        tipos=tipos,
        ids=ids,
        en_texto=re.compile(rf"\b(?:{todos})\b"),
        decision=re.compile("|".join(de_decision) or r"(?!)"),
        nombres=re.compile(rf"(?:{todos})\.md"),
        equivalencias=equivalencias,
        separadores=separadores,
    )


def _resuelta_por(formato, campo, ids_del_estado):
    """Decisiones candidatas: las del campo `resuelta_por` (texto o lista) y después las que cita el estado."""
    textos = campo if isinstance(campo, list) else [campo]
    del_campo = []
    for texto in (t for t in textos if isinstance(t, str)):
        del_campo += [x.group(0) for x in formato.en_texto.finditer(texto) if formato.decision.fullmatch(x.group(0))]
    del_campo = list(dict.fromkeys(del_campo))
    return del_campo + [i for i in ids_del_estado if formato.decision.fullmatch(i) and i not in del_campo]


def _amb(campo, motivo, candidatos=()):
    return {"campo": campo, "candidatos": list(candidatos), "motivo": motivo}


def _mapear(tipo, texto, formato=POR_DEFECTO, resuelta_por=None):
    """(estado propuesto o None, ambigüedades, relaciones propuestas).

    `resuelta_por` es el campo homónimo del registro heredado, si lo trae: un texto o una lista de textos.
    """
    t = texto.strip()
    cab = re.split(f"[{re.escape(formato.separadores)}]", t, maxsplit=1)[0].strip()
    ids = [x.group(0) for x in formato.en_texto.finditer(t)]
    amb, rel = [], {}
    if tipo == "decision":
        if t.startswith("Aceptada; sustituida en parte por"):
            amb.append(_amb("modifica", "sustitución parcial en prosa: anclas y alcance sin determinar", ids))
            return "aceptada", amb, rel
        if t.startswith("Sustituida por"):
            amb.append(
                _amb("deja_obsoleta", "sucesión declarada en la sustituida; la relación se escribe en la sucesora", ids)
            )
            return "aceptada", amb, rel
        estado = {"Propuesta": "propuesta", "Aceptada": "aceptada", "Rechazada": "rechazada"}.get(cab)
    elif tipo == "pregunta":
        if cab == "Resuelta" and "hecho:" in t:
            amb.append(_amb("basada_en", "cierre factual sin fuente registrada: hace falta una fuente o un hecho"))
            return "resuelta", amb, rel
        if cab == "Resuelta":
            rel["resuelta_por"] = _resuelta_por(formato, resuelta_por, ids)
            if not rel["resuelta_por"]:
                amb.append(_amb("resuelta_por", "resuelta sin decisión identificable"))
            return "resuelta", amb, rel
        if cab == "En revisión":
            amb.append(_amb("estado", "«En revisión» no existe en el contrato; se conserva abierta"))
            return "abierta", amb, rel
        estado = {"Abierta": "abierta", "Descartada": "descartada"}.get(cab)
    elif tipo == "hipotesis":
        if cab == "En validación":
            amb.append(_amb("estado", "«En validación» no existe en el contrato; se conserva abierta"))
            return "abierta", amb, rel
        if cab == "Validada":
            amb.append(_amb("estado", "validada solo bajo las condiciones probadas: revisar protocolo y evidencia"))
            return "validada", amb, rel
        if cab in ("Descartada", "Obsoleta"):
            amb.append(_amb("estado", f"«{cab}» puede ser refutada o retirada: decidir con la evidencia", ids))
            return "retirada", amb, rel
        estado = {"Abierta": "abierta"}.get(cab)
    elif tipo == "plan":
        if cab == "En curso":
            amb.append(_amb("estado", "«En curso» no existe para planes; el avance vive en los hitos"))
            return "autorizado", amb, rel
        if cab in ("Rechazado", "Abandonado") or t.startswith("Sustituido por"):
            amb.append(_amb("estado", f"«{cab}» se representa como cancelado; conservar el motivo", ids))
            return "cancelado", amb, rel
        estado = {"Propuesto": "propuesto", "Aprobado": "autorizado", "Cerrado": "cerrado"}.get(cab)
    elif tipo == "hito":
        if cab == "Pendiente":
            amb.append(_amb("estado", "la autorización propia del hito no consta; la del plan no basta"))
            return "propuesto", amb, rel
        if cab == "En curso":
            amb.append(_amb("estado", "en curso sin autorización del hito acreditada"))
            return "en_curso", amb, rel
        if cab == "Cumplido":
            amb.append(
                _amb(
                    "estado",
                    "completado exige aceptación por criterio y evidencia sobre la revisión probada; revisar evidencia y verifica",
                )
            )
            return "completado", amb, rel
        estado = {"Descartado": "cancelado"}.get(cab)
    else:
        estado = None
    if estado is None:
        amb.append(_amb("estado", f"estado heredado sin correspondencia: {t!r}"))
    return estado, amb, rel


def _autoridad(meta):
    texto = meta.get("adoptada_por") or meta.get("aprobado_por")
    if not isinstance(texto, str) or texto.strip() in ("", "—"):
        return None
    clase = "pendiente" if texto.strip().lower().startswith("pendiente") else "insuficiente"
    return {"texto": texto, "clasificacion": clase}


def inspeccionar(texto, ruta, revision, formato=POR_DEFECTO):
    base = {"ruta": ruta, "revision": revision, "original": texto}
    if Path(ruta).name == "index.md":
        return {**base, "resultado": "fuera_de_alcance", "tipo": None, "motivo": "índice generado: vista, no registro"}
    try:
        meta, _ = parse(texto)
    except ErrorDeFormato as exc:
        return {**base, "resultado": "fallido", "codigo": "ESQUEMA_INVALIDO", "mensaje": str(exc), "tipo": None}
    tipo = formato.tipos.get(meta.get("type"))
    if tipo is None:
        return {
            **base,
            "resultado": "fuera_de_alcance",
            "tipo": None,
            "motivo": f"type {meta.get('type')!r} no es un registro",
        }
    heredado = str(meta.get("estado", ""))
    normalizado = formato.normalizar(meta.get("type"), heredado.strip())
    estado, amb, rel = _mapear(tipo, normalizado, formato, meta.get("resuelta_por"))
    fecha = meta.get("fecha")
    con_dia = isinstance(fecha, str) and bool(_FECHA.match(fecha))
    autoridad = _autoridad(meta)
    props, _ = campos_de(tipo)
    evento = {
        "evento_id": None,
        "tipo_evento": "importacion",
        "actor": PRODUCTOR,
        "registrado_en": None,
        "valido_desde": fecha if con_dia else None,
        "precision": "dia" if con_dia else "desconocida",
        "motivo": "importación del formato heredado",
        "estado_anterior": None,
        "estado_nuevo": estado,
        "estado_heredado": heredado,
        "procedencia": {"ruta": ruta, "revision": revision},
        "evidencia_evento": None,
    }
    requiere = (
        bool(amb)
        or estado is None
        or (
            estado in CON_AUTORIDAD
            and (autoridad is None or autoridad["clasificacion"] != "comprobada")
            and tipo != "pregunta"
        )
    )
    return {
        **base,
        "resultado": "propuesto",
        "id": meta.get("id"),
        "tipo": tipo,
        "estado_heredado": heredado,
        "estado_propuesto": estado,
        "ambiguedades": amb,
        "relaciones_propuestas": rel,
        "autoridad_heredada": autoridad,
        "evento_importacion": evento,
        "campos_sin_destino": sorted(k for k in meta if k not in props),
        "requiere_revision": requiere,
    }


def inspeccionar_carpeta(carpeta, revision, formato=POR_DEFECTO):
    carpeta = Path(carpeta)
    archivos = [carpeta] if carpeta.is_file() else sorted(carpeta.rglob("*.md"))
    informes = [
        inspeccionar(
            p.read_text(encoding="utf-8"),
            p.relative_to(carpeta.parent if carpeta.is_file() else carpeta).as_posix(),
            revision,
            formato,
        )
        for p in archivos
    ]
    resumen = {
        "total": len(informes),
        "propuestos": sum(i["resultado"] == "propuesto" for i in informes),
        "fuera_de_alcance": sum(i["resultado"] == "fuera_de_alcance" for i in informes),
        "fallidos": sum(i["resultado"] == "fallido" for i in informes),
        "requieren_revision": sum(bool(i.get("requiere_revision")) for i in informes),
    }
    return {"resumen": resumen, "informes": informes}
