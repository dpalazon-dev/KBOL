"""Vocabulario cerrado del contrato KB-DPP (núcleo 0.7, «Contratos concretos» y «Contrato de estados»).

Las elecciones locales que el contrato deja abiertas están en docs/elecciones.md.
"""

import re
from dataclasses import dataclass

TIPOS = (
    "fuente",
    "hecho",
    "decision",
    "persona",
    "rol",
    "pregunta",
    "hipotesis",
    "supuesto",
    "entidad",
    "plan",
    "hito",
    "sintesis",
)
PREFIJO = dict(zip(TIPOS, ("F", "HE", "DEC", "PER", "ROL", "Q", "HIP", "SUP", "ENT", "PL", "HI", "SIN")))
TIPO_DE_PREFIJO = {v: k for k, v in PREFIJO.items()}
# IDs del formato heredado por defecto (contrato KB-DPP, «Identidad»): se conservan como identidad.
HEREDADOS = (
    (re.compile(r"^ADR-\d{4}(?!\n)$"), "decision"),
    (re.compile(r"^QD-\d{3,}(?!\n)$"), "pregunta"),
    (re.compile(r"^HD-\d{3,}(?!\n)$"), "hipotesis"),
    (re.compile(r"^PL-\d{3}-H\d+(?!\n)$"), "hito"),
    (re.compile(r"^PL-\d{3}(?!\n)$"), "plan"),
)
CLASES = ("registro", "fuente", "fijo", "vista", "archivo")

ESTADOS = {
    "decision": ("propuesta", "aceptada", "rechazada"),
    "hecho": ("propuesta", "aceptada", "rechazada"),
    "pregunta": ("abierta", "resuelta", "descartada"),
    "hipotesis": ("abierta", "validada", "refutada", "retirada"),
    "supuesto": ("activo", "retirado"),
    "plan": ("propuesto", "autorizado", "cerrado", "cancelado"),
    "hito": ("propuesto", "autorizado", "en_curso", "completado", "cancelado"),
    "fuente": ("registrada", "retirada"),
    "persona": ("propuesta", "activa", "retirada"),
    "rol": ("propuesta", "activa", "retirada"),
    "entidad": ("propuesta", "activa", "retirada"),
    "sintesis": ("borrador", "vigente", "retirada"),
}
INICIAL = {t: e[0] for t, e in ESTADOS.items()}
TRANSICIONES = {
    "decision": {("propuesta", "aceptada"), ("propuesta", "rechazada")},
    "hecho": {("propuesta", "aceptada"), ("propuesta", "rechazada")},
    "pregunta": {("abierta", "resuelta"), ("abierta", "descartada")},
    "hipotesis": {("abierta", "validada"), ("abierta", "refutada"), ("abierta", "retirada")},
    "supuesto": {("activo", "retirado")},
    "plan": {
        ("propuesto", "autorizado"),
        ("propuesto", "cancelado"),
        ("autorizado", "cerrado"),
        ("autorizado", "cancelado"),
    },
    "hito": {
        ("propuesto", "autorizado"),
        ("propuesto", "cancelado"),
        ("autorizado", "en_curso"),
        ("autorizado", "cancelado"),
        ("en_curso", "completado"),
        ("en_curso", "cancelado"),
    },
    "fuente": {("registrada", "retirada")},
    "sintesis": {("borrador", "vigente"), ("borrador", "retirada"), ("vigente", "borrador"), ("vigente", "retirada")},
}
for _t in ("persona", "rol", "entidad"):
    TRANSICIONES[_t] = {("propuesta", "activa"), ("propuesta", "retirada"), ("activa", "retirada")}

# Estado en que el registro rige o existe para la consulta de vigencia.
EFECTIVO = {"decision": "aceptada", "hecho": "aceptada", "fuente": "registrada"}

EVENTOS = (
    "creacion",
    "transicion",
    "ratificacion",
    "revocacion_aprobacion",
    "evaluacion",
    "cambio_ocupacion",
    "resolucion_impacto",
    "importacion",
)
# Eventos que fijan el estado materializado.
EVENTOS_DE_ESTADO = ("creacion", "transicion", "importacion")

CLASES_EVIDENCIA = ("observado", "calculado", "declarado", "modelado", "predicho", "supuesto")
CONDICIONES = ("aceptada_y_vigente", "resuelta", "completado_con_evidencia", "disponible_con_integridad")
PROCESAMIENTO = ("pendiente", "procesado", "parcial", "fallido")
RESULTADO_EVALUACION = ("conforme", "no_conforme", "parcial", "no_evaluado")
METODOS_ACEPTACION = ("comando", "revision_humana", "evaluacion_ia_asistida")
PRECISIONES = ("instante", "minuto", "hora", "dia", "mes", "anio")
# Clases de término del vocabulario del dominio: de momento, solo la clase de entidad.
CLASES_DE_TERMINO = ("clase_entidad",)

CODIGOS = (
    "ESQUEMA_INVALIDO",
    "REFERENCIA_AUSENTE",
    "AUTORIDAD_INSUFICIENTE",
    "APROBACION_CADUCADA",
    "BASE_CAMBIADA",
    "CONFLICTO_NORMATIVO",
    "TIEMPO_AMBIGUO",
    "INTEGRIDAD_ROTA",
    "INTEGRIDAD_NO_COMPROBADA",
    "EVIDENCIA_INSUFICIENTE",
    "ACCESO_DENEGADO",
    "RESULTADO_DESCONOCIDO",
)

FORMAS = ("ids", "objetos", "id", "cuerpo")
# Ciclos prohibidos, en el orden en que se comprueban: sucesión, derivación y dependencia ejecutable.
CICLOS = ("sucesion", "derivacion", "dependencia")


@dataclass(frozen=True)
class Referencia:
    """Un campo que apunta a otros registros: dónde se declara, adónde apunta y cómo lo trata el motor.

    - `origen`: tipos que lo declaran; None, cualquier registro.
    - `destino`: tipos admitidos, `"mismo"` (el tipo del origen) o None (cualquiera, o sin destino).
    - `ancla`: `"prohibida"`, `"obligatoria"` u `"opcional"`; None si no tiene destino.
    - `forma`: `"ids"` (lista de IDs), `"objetos"` (lista de mapas), `"id"` (un ID) o `"cuerpo"` (citas `<hecho ref>`).
    - `clave`: en `"objetos"`, la clave que lleva el destino; None si no lleva ninguno.
    - `relacion`: su forma la da esta tabla (relaciones del núcleo); False si la declara su tipo en el esquema.
    - `consumo`: quien la declara consume el destino; un cambio en el destino le llega como impacto.
    - `sin_ciclos`: la clase de ciclo prohibido (`CICLOS`) a la que pertenece, o None si un ciclo es legítimo.
    - `libre`: cambiarla no reabre un cierre ni una autorización, porque no cambia lo que rige.
    - `evidencia`: el destino sostiene al registro (apoyo de la consulta `soporte`).
    """

    origen: tuple | None
    destino: tuple | str | None
    ancla: str | None
    forma: str = "ids"
    clave: str | None = None
    relacion: bool = True
    consumo: bool = False
    sin_ciclos: str | None = None
    libre: bool = False
    evidencia: bool = False


_R = Referencia
# Referencias entre registros. El orden es el del recorrido y el de los informes.
REFERENCIAS = {
    # Campos propios con destino: su forma la declara su tipo en el esquema.
    "dependencias": _R(("sintesis",), None, "opcional", relacion=False, consumo=True, evidencia=True),
    "sources": _R(None, None, "prohibida", "objetos", "resource", relacion=False, consumo=True, evidencia=True),
    "cuerpo": _R(None, ("hecho",), "prohibida", "cuerpo", relacion=False, consumo=True, evidencia=True),
    # Relaciones: tipos de origen admitidos (tabla «Relaciones» del núcleo) y forma del destino.
    "resuelta_por": _R(("pregunta",), ("decision",), "prohibida", consumo=True),
    "cuestiona": _R(("pregunta",), ("decision",), "obligatoria", consumo=True),
    "deja_obsoleta": _R(("decision", "hecho", "fuente"), "mismo", "prohibida", sin_ciclos="sucesion"),
    "pone_a_prueba": _R(("hipotesis",), ("decision",), "obligatoria", consumo=True),
    "basada_en": _R(
        ("decision", "hecho", "hipotesis", "pregunta"), ("fuente", "hecho"), "opcional", consumo=True, evidencia=True
    ),
    "derivada_de": _R(("fuente",), ("fuente",), "prohibida", consumo=True, sin_ciclos="derivacion"),
    "afecta_a": _R(("decision", "hecho", "pregunta"), None, "opcional"),
    "autorizado_por": _R(("decision", "plan", "hito"), ("rol",), "prohibida", consumo=True),
    # Vínculos de trabajo (elección local, docs/elecciones.md, «Vínculos de trabajo»): no cambian lo que rige.
    "cierra": _R(("hito",), ("pregunta",), "prohibida", consumo=True, libre=True),
    "avanza": _R(("hito",), ("pregunta",), "prohibida", consumo=True, libre=True),
    "somete_a_prueba": _R(("hito",), ("hipotesis",), "prohibida", consumo=True, libre=True),
    "produce": _R(("hito",), None, "opcional", consumo=True, libre=True),
    "se_apoya_en": _R(("plan",), ("decision",), "opcional", consumo=True, libre=True),
    # Relaciones con objetos tipados.
    "modifica": _R(("decision",), ("decision",), "opcional", "objetos", "destino", sin_ciclos="sucesion"),
    "depende_de": _R(
        ("pregunta", "decision", "plan", "hito"),
        None,
        "opcional",
        "objetos",
        "destino",
        consumo=True,
        sin_ciclos="dependencia",
    ),
    "ocupa": _R(("persona",), ("rol",), "prohibida", "objetos", "rol", consumo=True),
    "veta": _R(("decision",), None, None, "objetos"),
    # Términos del dominio que declara una decisión (elección local): sin destino, como `veta`.
    "define": _R(("decision",), None, None, "objetos"),
    # Campos propios de trabajo con destino.
    "responsable": _R(("pregunta", "hito"), ("rol", "persona"), "prohibida", "id", relacion=False, libre=True),
    "hitos": _R(("plan",), ("hito",), "prohibida", relacion=False),
}

# Vistas de la tabla.
RELACIONES = {
    c: {"origen": r.origen, "destino": r.destino, "ancla": r.ancla}
    for c, r in REFERENCIAS.items()
    if r.relacion and r.forma == "ids"
}
VINCULOS = tuple(c for c in RELACIONES if REFERENCIAS[c].libre)
# Campos de trabajo, libres como los vínculos: quién responde, qué lo prueba y cuánto está hecho.
CAMPOS_DE_TRABAJO = ("responsable", "evidencia", "implementacion")
IMPLEMENTACION = ("completa", "parcial", "pendiente", "no aplica")
# Relaciones con objetos tipados: tipos de origen admitidos.
RELACIONES_OBJETO = {c: r.origen for c, r in REFERENCIAS.items() if r.relacion and r.forma == "objetos"}
SIN_CICLOS = tuple(c for clase in CICLOS for c, r in REFERENCIAS.items() if r.sin_ciclos == clase)

ID_UUID = (
    r"(F|HE|DEC|PER|ROL|Q|HIP|SUP|ENT|PL|HI|SIN)-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
ANCLA = r"C[A-Za-z0-9_-]+"
RE_ANCLA = re.compile(rf"^{ANCLA}(?!\n)$")
RE_ID = re.compile(r"^[A-Z]{1,4}-[A-Za-z0-9][A-Za-z0-9_-]*(?!\n)$")
RE_ID_ANCLA = re.compile(rf"^[A-Z]{{1,4}}-[A-Za-z0-9][A-Za-z0-9_-]*(#{ANCLA})?(?!\n)$")


def tipo_de_id(ident):
    """Tipo que impone el ID, o None si no lo impone ninguna convención conocida."""
    if not isinstance(ident, str):
        return None
    base = ident.split("#", 1)[0]
    for patron, tipo in HEREDADOS:
        if patron.match(base):
            return tipo
    prefijo = base.split("-", 1)[0]
    return TIPO_DE_PREFIJO.get(prefijo)
