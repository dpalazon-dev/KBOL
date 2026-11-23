"""VAL-01: forma de un registro aislado (cabecera, campos por tipo, relaciones, eventos y marcas del cuerpo).

Validar la forma no establece autoridad, vigencia ni admisión de eventos: esas comprobaciones necesitan la política,
la base y el mecanismo de integración. Las referencias entre registros se comprueban en `referencias.py`.

Modos:
- `propuesta` (por defecto): campos desconocidos son error; la decisión necesita cláusulas.
- `canonico`: además, el estado escrito debe coincidir con el historial admitido.
- `intercambio`: campos desconocidos se conservan y solo avisan.
"""

from functools import cache

from . import modelo as m
from .eventos import ErrorDeHistorial, estado_en
from .markdown import ErrorDeMarca, clausulas, hechos
from .tiempo import comparable, es_fecha, es_instante, es_instante_o_fecha


@cache
def _formatos():
    """Comprobador de formatos. jsonschema se importa al validar, no al cargar el módulo: su importación cuesta más
    que muchas órdenes enteras que no validan nada."""
    from jsonschema import FormatChecker

    formatos = FormatChecker(formats=())
    formatos.checks("instante")(es_instante)
    formatos.checks("fecha")(es_fecha)
    formatos.checks("instante-o-fecha")(es_instante_o_fecha)
    return formatos


TEXTO = {"type": "string", "minLength": 1}
LINEA = {"type": "string", "minLength": 1, "pattern": r"^[^\r\n]*(?!\n)$"}
TEXTOS = {"type": "array", "items": TEXTO}
ID = {"type": "string", "pattern": m.RE_ID.pattern}
ID_ANCLA = {"type": "string", "pattern": m.RE_ID_ANCLA.pattern}
IDS = {"type": "array", "items": ID}
IDS_ANCLA = {"type": "array", "items": ID_ANCLA}
ACTOR = {"type": "string", "pattern": r"^(human:\S+|process:\S+|[^\s/:]+/[^\s/]+)(?!\n)$"}
SHA256 = {"type": "string", "pattern": r"^[0-9a-f]{64}(?!\n)$"}
INSTANTE = {"type": "string", "format": "instante"}
INSTANTE_O_FECHA = {"type": "string", "format": "instante-o-fecha"}
ENTERO = {"type": "integer"}


def objeto(requeridos, opcionales=None, **extra):
    props = {**requeridos, **(opcionales or {})}
    return {"type": "object", "required": list(requeridos), "properties": props, "additionalProperties": False, **extra}


EVIDENCIA_EVENTO = objeto({"mecanismo": TEXTO, "comprobante": TEXTO})
FUENTE_CITADA = objeto(
    {"id": TEXTO, "resource": ID},
    {"ancla": TEXTO, "representacion_id": ID, "hash": SHA256, "contexto": TEXTO},
)
EVALUACION = objeto(
    {
        "evaluacion_id": TEXTO,
        "sujeto_id": ID,
        "digest_o_huella": SHA256,
        "dimensiones": {**TEXTOS, "minItems": 1},
        "metodo": TEXTO,
        "actor": ACTOR,
        "realizada_en": INSTANTE,
        "resultado": {"enum": list(m.RESULTADO_EVALUACION)},
        "evidencia_ref": TEXTO,
        "limitaciones": TEXTO,
    }
)
APROBACION = objeto(
    {
        "aprobacion_id": TEXTO,
        "actor": ACTOR,
        "identidad_ref": TEXTO,
        "roles": {**IDS, "minItems": 1},
        "digest": SHA256,
        "revision_base": TEXTO,
        "aprobada_en": INSTANTE,
        "politica_revision": TEXTO,
        "comprobante": {"anyOf": [TEXTO, {"type": "object", "minProperties": 1}]},
    }
)
LIMITE = {"anyOf": [TEXTO, {"type": "object", "minProperties": 1}]}

COMUNES_EVENTO = {
    "evento_id": TEXTO,
    "tipo_evento": {"enum": list(m.EVENTOS)},
    "actor": ACTOR,
    "registrado_en": {"anyOf": [INSTANTE, {"type": "null"}]},
    "valido_desde": INSTANTE,
    "motivo": TEXTO,
    "evidencia_evento": EVIDENCIA_EVENTO,
}
OPCIONALES_EVENTO = {"valido_hasta": INSTANTE}
EVENTO_POR_CLASE = {
    "creacion": ({"estado_anterior": {"type": "null"}, "estado_nuevo": TEXTO}, {}),
    "transicion": ({"estado_anterior": TEXTO, "estado_nuevo": TEXTO}, {}),
    "importacion": (
        {
            "estado_anterior": {"type": "null"},
            "estado_nuevo": TEXTO,
            "estado_heredado": TEXTO,
            "procedencia": objeto({"ruta": TEXTO, "revision": TEXTO}),
            "valido_desde": {"anyOf": [INSTANTE_O_FECHA, {"type": "null"}]},
        },
        {
            "precision": {"enum": list(m.PRECISIONES) + ["desconocida"]},
            "autoridad_heredada": {
                "anyOf": [
                    {"type": "null"},
                    objeto({"texto": TEXTO, "clasificacion": {"enum": ["comprobada", "pendiente", "insuficiente"]}}),
                ]
            },
        },
    ),
    "ratificacion": ({"aprobacion": APROBACION}, {}),
    "revocacion_aprobacion": ({"aprobacion_id": TEXTO}, {}),
    "evaluacion": ({"evaluacion": EVALUACION}, {}),
    "cambio_ocupacion": ({"rol": ID, "desde": INSTANTE}, {"hasta": INSTANTE}),
    "resolucion_impacto": (
        {"afectado": ID_ANCLA, "causa": TEXTO, "resolucion": {"enum": ["actualizado", "no_afecta", "pendiente"]}},
        {"responsable": ID, "plazo": INSTANTE_O_FECHA},
    ),
}


def esquema_evento(clase):
    requeridos, opcionales = EVENTO_POR_CLASE[clase]
    return objeto({**COMUNES_EVENTO, **requeridos}, {**OPCIONALES_EVENTO, **opcionales})


RELACION_OBJETO = {
    "modifica": {
        "type": "array",
        "items": objeto(
            {"destino": ID_ANCLA, "tipo": {"enum": ["sustitucion", "derogacion", "adicion"]}},
            {"por": ID_ANCLA, "posicion": TEXTO},
        ),
    },
    "depende_de": {"type": "array", "items": objeto({"destino": ID_ANCLA, "condicion": {"enum": list(m.CONDICIONES)}})},
    "ocupa": {"type": "array", "items": objeto({"rol": ID, "desde": INSTANTE}, {"hasta": INSTANTE})},
    "veta": {"type": "array", "items": objeto({"patron": TEXTO, "ambito": TEXTO, "uso": TEXTO, "exclusiones": TEXTOS})},
    "define": {
        "type": "array",
        "items": objeto(
            {
                "clausula": {"type": "string", "pattern": m.RE_ANCLA.pattern},
                "termino": LINEA,
                "clase": {"enum": list(m.CLASES_DE_TERMINO)},
                "descripcion": TEXTO,
            },
            {"alias": {"type": "array", "items": LINEA}},
        ),
    },
}

COMUNES = {
    "id": ID,
    "type": {"enum": list(m.TIPOS)},
    "clase": {"enum": list(m.CLASES)},
    "title": LINEA,
    "description": LINEA,
    "ambito": TEXTO,
    "estado": TEXTO,
    "autor": ACTOR,
    "eventos": {"type": "array", "items": {"type": "object", "required": ["tipo_evento"]}},
    "sources": {"type": "array", "items": FUENTE_CITADA},
}
OPCIONALES_COMUNES = {
    "generated": objeto({"by": TEXTO, "at": INSTANTE}),
    "verified": {"type": "array", "items": objeto({"by": ACTOR, "at": INSTANTE, "digest": SHA256})},
    "stale_after": INSTANTE,
    "status": {"enum": ["draft", "stable", "deprecated"]},
}
CALIDAD = {
    "type": "object",
    "minProperties": 1,
    "additionalProperties": {
        "anyOf": [
            {"const": "no_evaluado"},
            objeto({"metodo": TEXTO, "resultado": {"enum": list(m.RESULTADO_EVALUACION)}, "limites": TEXTO}),
        ]
    },
}
_FUENTE_COMUN = {
    "subtipo": {"enum": ["original", "derivada"]},
    "ubicacion": TEXTO,
    "formato": TEXTO,
    "sha256": SHA256,
    "acceso": TEXTO,
}
ACEPTACION = objeto(
    {
        "criterio_id": TEXTO,
        "descripcion": TEXTO,
        "metodo": {"enum": list(m.METODOS_ACEPTACION)},
        "obligatorio": {"type": "boolean"},
    },
    {"rubrica": TEXTO, "resolucion_desacuerdo": TEXTO},
)
VERIFICACION = objeto(
    {
        "verificacion_id": TEXTO,
        "criterio_id": TEXTO,
        "ejecutor": TEXTO,
        "entrada": {"type": ["object", "array"]},
        "entorno_ref": TEXTO,
        "timeout": {**ENTERO, "minimum": 1},
        "efectos_permitidos": TEXTOS,
    }
)
ALTERNATIVA = objeto({"id": TEXTO, "descripcion": TEXTO, "seleccionada": {"type": "boolean"}, "motivo": TEXTO})

# Campos propios por tipo: (requeridos, opcionales). Las relaciones admitidas se añaden desde modelo.RELACIONES.
POR_TIPO = {
    "fuente": (_FUENTE_COMUN, {"evaluaciones": {"type": "array", "items": EVALUACION}}),
    "hecho": (
        {
            "afirmacion": TEXTO,
            "clase_evidencia": {"enum": list(m.CLASES_EVIDENCIA)},
            "precision": {"enum": list(m.PRECISIONES)},
        },
        {"fecha": INSTANTE_O_FECHA, "intervalo": objeto({"desde": INSTANTE_O_FECHA}, {"hasta": INSTANTE_O_FECHA})},
    ),
    "decision": (
        {"alternativas": {"type": "array", "items": ALTERNATIVA}, "criterios": TEXTOS, "justificacion": TEXTO},
        {"sin_alternativas_motivo": TEXTO, "implementacion": {"enum": list(m.IMPLEMENTACION)}},
    ),
    "persona": ({"naturaleza": {"enum": ["humana", "agente"]}, "identidad_ref": TEXTO}, {}),
    "rol": (
        {
            "ambitos": {**TEXTOS, "minItems": 1},
            "capacidades": {**TEXTOS, "minItems": 1},
            "regla_aprobacion": {"anyOf": [{"enum": ["uno", "todos"]}, objeto({"quorum": {**ENTERO, "minimum": 1}})]},
        },
        {},
    ),
    "pregunta": (
        {
            "subtipo": {"enum": ["incognita", "incidencia", "discrepancia"]},
            "responsable": ID,
            "condicion_cierre": TEXTO,
        },
        {"plazo": INSTANTE_O_FECHA, "evidencia": TEXTOS},
    ),
    "hipotesis": (
        {"afirmacion": TEXTO, "plan_prueba": TEXTO, "criterio_refutacion": TEXTO, "consecuencia_si_falla": TEXTO},
        {},
    ),
    "supuesto": ({"afirmacion": TEXTO, "revisar_en": INSTANTE_O_FECHA, "consecuencia_si_falla": TEXTO}, {}),
    "entidad": ({"nombre": TEXTO, "alias": TEXTOS, "clase_entidad": TEXTO}, {}),
    "plan": ({"objetivo": TEXTO, "hitos": IDS, "restricciones": TEXTOS}, {}),
    "hito": (
        {
            "objetivo": TEXTO,
            "alcance": TEXTO,
            "aceptacion": {"type": "array", "items": ACEPTACION, "minItems": 1},
            "tolerancias": objeto({}, {"tiempo": LIMITE, "coste": LIMITE, "recursos": LIMITE, "alcance": LIMITE}),
            "verificaciones": {"type": "array", "items": VERIFICACION},
        },
        {"responsable": ID, "evidencia": TEXTOS},
    ),
    "sintesis": ({"dependencias": IDS_ANCLA, "evaluaciones": {"type": "array", "items": EVALUACION}}, {}),
}
DERIVADA = {
    "derivada_de": {**IDS, "minItems": 1},
    "procesador": TEXTO,
    "version_procesador": TEXTO,
    "configuracion_ref": TEXTO,
    "procesado_en": INSTANTE,
    "procesamiento": {"enum": list(m.PROCESAMIENTO)},
    "calidad": CALIDAD,
}
# Relaciones obligatorias por tipo (tabla «Contratos concretos»).
RELACIONES_REQUERIDAS = {
    "hecho": ("basada_en",),
    "decision": ("autorizado_por",),
    "persona": ("ocupa",),
    "plan": ("autorizado_por",),
    "hito": ("autorizado_por",),
}
# Nombres del contrato que ningún término del dominio puede llevar: tipos, campos y relaciones.
# Se comparan sin distinguir mayúsculas: `Entidad` también nombra un tipo.
RESERVADOS = frozenset(
    n.casefold()
    for n in (
        *m.TIPOS,
        *COMUNES,
        *OPCIONALES_COMUNES,
        *(c for requeridos, opcionales in POR_TIPO.values() for c in (*requeridos, *opcionales)),
        *DERIVADA,
        "origen",
        *m.REFERENCIAS,
    )
)


def campos_de(tipo, subtipo=None):
    """(esquema de propiedades, requeridos) para un tipo."""
    requeridos, opcionales = POR_TIPO[tipo]
    props = {**COMUNES, **OPCIONALES_COMUNES, **requeridos, **opcionales}
    req = list(COMUNES) + list(requeridos)
    for rel, regla in m.RELACIONES.items():
        if tipo in regla["origen"]:
            props[rel] = {**IDS_ANCLA, "minItems": 1} if rel == "autorizado_por" else IDS_ANCLA
    for rel, origenes in m.RELACIONES_OBJETO.items():
        if tipo in origenes:
            props[rel] = RELACION_OBJETO[rel]
    req += list(RELACIONES_REQUERIDAS.get(tipo, ()))
    if tipo == "fuente":
        if subtipo == "derivada":
            props.update(DERIVADA)
            req += list(DERIVADA)
            props.pop("origen", None)
        else:
            props["origen"] = TEXTO
            props.pop("derivada_de", None)
            req.append("origen")
    return props, req


def _hallazgo(codigo, ruta, mensaje, severidad="error"):
    return {"codigo": codigo, "ruta": ruta, "mensaje": mensaje, "severidad": severidad}


def _ruta(error):
    return "/" + "/".join(str(p) for p in error.absolute_path)


def _jsonschema(esquema, instancia, prefijo=""):
    from jsonschema import Draft202012Validator

    return [
        _hallazgo("ESQUEMA_INVALIDO", prefijo + _ruta(e), e.message)
        for e in Draft202012Validator(esquema, format_checker=_formatos()).iter_errors(instancia)
    ]


def _repetidos(items, clave, ruta):
    vistos, out = set(), []
    for i, it in enumerate(items):
        if isinstance(it, dict) and clave in it:
            if it[clave] in vistos:
                out.append(_hallazgo("ESQUEMA_INVALIDO", f"{ruta}/{i}/{clave}", f"{clave} repetido: {it[clave]}"))
            vistos.add(it[clave])
    return out


def validar(registro, cuerpo="", modo="propuesta"):
    """Lista de hallazgos {codigo, ruta, mensaje, severidad}. Vacía si la forma es válida en el modo pedido."""
    if modo not in ("propuesta", "canonico", "intercambio"):
        raise ValueError(f"modo desconocido: {modo}")
    if not isinstance(registro, dict):
        return [_hallazgo("ESQUEMA_INVALIDO", "/", "la cabecera debe ser un mapa")]
    tipo = registro.get("type")
    if tipo not in m.TIPOS:
        return _jsonschema({"type": "object", "required": list(COMUNES), "properties": COMUNES}, registro)

    props, req = campos_de(tipo, registro.get("subtipo"))
    esquema = {"type": "object", "required": req, "properties": props}
    out = _jsonschema(esquema, registro)
    for campo in registro:
        if campo not in props:
            sev = "aviso" if modo == "intercambio" else "error"
            out.append(_hallazgo("ESQUEMA_INVALIDO", f"/{campo}", f"campo no declarado para {tipo}", sev))

    out += _decimales(registro, "")
    out += _identidad(registro, tipo)
    if registro.get("estado") not in m.ESTADOS[tipo]:
        out.append(_hallazgo("ESQUEMA_INVALIDO", "/estado", f"{registro.get('estado')!r} no es un estado de {tipo}"))
    elif modo == "propuesta" and registro.get("eventos") == [] and registro["estado"] != m.INICIAL[tipo]:
        out.append(
            _hallazgo(
                "ESQUEMA_INVALIDO", "/estado", f"una propuesta nueva está en {m.INICIAL[tipo]!r}; el cambio se solicita"
            )
        )
    out += _relaciones(registro, tipo)
    out += _por_tipo(registro, tipo)
    out += _eventos(registro, tipo, modo)
    out += _cuerpo(registro, tipo, cuerpo, modo)
    return out


def _decimales(valor, ruta):
    """Los valores numéricos son enteros exactos; los decimales van como texto (también 600.0)."""
    if isinstance(valor, float):
        return [_hallazgo("ESQUEMA_INVALIDO", ruta or "/", "los decimales se escriben como texto")]
    if isinstance(valor, dict):
        return [h for k, v in valor.items() for h in _decimales(v, f"{ruta}/{k}")]
    if isinstance(valor, list):
        return [h for i, v in enumerate(valor) for h in _decimales(v, f"{ruta}/{i}")]
    return []


def _ordenado(desde, hasta, ruta):
    if not (
        isinstance(desde, str) and isinstance(hasta, str) and es_instante_o_fecha(desde) and es_instante_o_fecha(hasta)
    ):
        return []
    if comparable(hasta) <= comparable(desde):
        return [_hallazgo("ESQUEMA_INVALIDO", ruta, f"el fin {hasta} no es posterior al inicio {desde}")]
    return []


def _identidad(registro, tipo):
    ident = registro.get("id")
    if not isinstance(ident, str):
        return []
    impuesto = m.tipo_de_id(ident)
    if impuesto is None:
        return [_hallazgo("ESQUEMA_INVALIDO", "/id", f"el prefijo de {ident} no corresponde a ningún tipo")]
    if impuesto != tipo:
        return [_hallazgo("ESQUEMA_INVALIDO", "/id", f"{ident} es un ID de {impuesto}, no de {tipo}")]
    return []


def _relaciones(registro, tipo):
    out = []
    for rel, regla in m.RELACIONES.items():
        valores = registro.get(rel)
        if not isinstance(valores, list):
            continue
        for i, dest in enumerate(valores):
            if not isinstance(dest, str):
                continue
            con_ancla = "#" in dest
            if regla["ancla"] == "obligatoria" and not con_ancla:
                out.append(_hallazgo("ESQUEMA_INVALIDO", f"/{rel}/{i}", f"{rel} apunta a una cláusula: ID#ancla"))
            if regla["ancla"] == "prohibida" and con_ancla:
                out.append(
                    _hallazgo("ESQUEMA_INVALIDO", f"/{rel}/{i}", f"{rel} apunta a un registro, no a una cláusula")
                )
            esperado = (tipo,) if regla["destino"] == "mismo" else regla["destino"]
            real = m.tipo_de_id(dest)
            if esperado and real is not None and real not in esperado:
                out.append(_hallazgo("ESQUEMA_INVALIDO", f"/{rel}/{i}", f"{rel} no admite un destino de tipo {real}"))
    for i, mod in enumerate(registro.get("modifica") or []):
        if not isinstance(mod, dict):
            continue
        tipo_mod, destino, por = mod.get("tipo"), str(mod.get("destino", "")), mod.get("por")
        ruta = f"/modifica/{i}"
        if tipo_mod in ("sustitucion", "adicion") and not por:
            out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, f"{tipo_mod} exige por"))
        if tipo_mod == "derogacion" and por is not None:
            out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, "derogación no admite por"))
        if tipo_mod in ("sustitucion", "derogacion") and "#" not in destino:
            out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, f"{tipo_mod} exige destino ID#ancla"))
        if tipo_mod == "adicion":
            if "#" in destino:
                out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, "adición apunta a una decisión, no a una cláusula"))
            if not mod.get("posicion"):
                out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, "adición exige posición lógica explícita"))
        elif "posicion" in mod:
            out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, "posicion solo se admite en una adición"))
        if por and not str(por).startswith(f"{registro.get('id')}#"):
            out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, "por identifica una cláusula del propio registro"))
        if m.tipo_de_id(destino) not in (None, "decision"):
            out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, "modifica apunta a una decisión"))
    for i, dep in enumerate(registro.get("depende_de") or []):
        if isinstance(dep, dict) and dep.get("destino") == registro.get("id"):
            out.append(_hallazgo("CONFLICTO_NORMATIVO", f"/depende_de/{i}", "un registro no depende de sí mismo"))
    return out


def _por_tipo(registro, tipo):
    out = []
    out += _repetidos(registro.get("sources") or [], "id", "/sources")
    if tipo == "decision":
        alts = registro.get("alternativas")
        if isinstance(alts, list):
            out += _repetidos(alts, "id", "/alternativas")
            motivo = registro.get("sin_alternativas_motivo")
            if not alts and not motivo:
                out.append(
                    _hallazgo("ESQUEMA_INVALIDO", "/sin_alternativas_motivo", "sin alternativas hay que decir por qué")
                )
            if alts and motivo:
                out.append(_hallazgo("ESQUEMA_INVALIDO", "/sin_alternativas_motivo", "solo cuando no hay alternativas"))
            if alts and not any(isinstance(a, dict) and a.get("seleccionada") is True for a in alts):
                out.append(_hallazgo("ESQUEMA_INVALIDO", "/alternativas", "ninguna alternativa está seleccionada"))
        out += _nombres_definidos(registro.get("define") or [])
    if tipo == "hecho":
        tiene = [k for k in ("fecha", "intervalo") if k in registro]
        if len(tiene) != 1:
            out.append(_hallazgo("ESQUEMA_INVALIDO", "/fecha", "un hecho lleva fecha o intervalo, uno de los dos"))
        intervalo = registro.get("intervalo")
        if isinstance(intervalo, dict):
            out += _ordenado(intervalo.get("desde"), intervalo.get("hasta"), "/intervalo")
    for i, occ in enumerate(registro.get("ocupa") or []):
        if isinstance(occ, dict):
            out += _ordenado(occ.get("desde"), occ.get("hasta"), f"/ocupa/{i}")
    if tipo == "hito":
        acept = registro.get("aceptacion") or []
        verif = registro.get("verificaciones") or []
        out += _repetidos(acept, "criterio_id", "/aceptacion")
        out += _repetidos(verif, "verificacion_id", "/verificaciones")
        criterios = {a.get("criterio_id") for a in acept if isinstance(a, dict)}
        for i, v in enumerate(verif):
            if isinstance(v, dict) and v.get("criterio_id") not in criterios:
                out.append(_hallazgo("REFERENCIA_AUSENTE", f"/verificaciones/{i}/criterio_id", "criterio inexistente"))
        for i, a in enumerate(acept):
            asistida = isinstance(a, dict) and a.get("metodo") == "evaluacion_ia_asistida"
            if asistida and not (a.get("rubrica") and a.get("resolucion_desacuerdo")):
                out.append(
                    _hallazgo(
                        "ESQUEMA_INVALIDO",
                        f"/aceptacion/{i}",
                        "la evaluación asistida exige rúbrica y resolución humana del desacuerdo",
                    )
                )
    return out


def _nombres_definidos(entradas):
    """Términos y alias de `define`: ninguno es un nombre del contrato y ninguno se repite en el registro."""
    out, vistos = [], set()
    for i, e in enumerate(entradas):
        if not isinstance(e, dict):
            continue
        alias = e.get("alias") if isinstance(e.get("alias"), list) else []
        nombres = [("termino", e.get("termino"))] + [(f"alias/{j}", a) for j, a in enumerate(alias)]
        for campo, nombre in nombres:
            if not isinstance(nombre, str):
                continue
            ruta = f"/define/{i}/{campo}"
            if nombre != nombre.strip():
                out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, f"{nombre!r} lleva espacios al principio o al final"))
            if nombre.strip().casefold() in RESERVADOS:
                out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, f"{nombre!r} es un tipo, un campo o una relación"))
            if nombre in vistos:
                out.append(_hallazgo("ESQUEMA_INVALIDO", ruta, f"{nombre!r} ya está definido en este registro"))
            vistos.add(nombre)
    return out


def _eventos(registro, tipo, modo):
    eventos = registro.get("eventos")
    if not isinstance(eventos, list):
        return []
    out = _repetidos(eventos, "evento_id", "/eventos")
    for i, ev in enumerate(eventos):
        clase = ev.get("tipo_evento") if isinstance(ev, dict) else None
        if clase not in EVENTO_POR_CLASE:
            out.append(_hallazgo("ESQUEMA_INVALIDO", f"/eventos/{i}", f"tipo_evento desconocido: {clase!r}"))
            continue
        out += _jsonschema(esquema_evento(clase), ev, f"/eventos/{i}")
        for campo in ("estado_anterior", "estado_nuevo"):
            valor = ev.get(campo)
            if valor is not None and valor not in m.ESTADOS[tipo]:
                out.append(
                    _hallazgo("ESQUEMA_INVALIDO", f"/eventos/{i}/{campo}", f"{valor!r} no es un estado de {tipo}")
                )
        out += _ordenado(ev.get("valido_desde"), ev.get("valido_hasta"), f"/eventos/{i}")
    if modo == "canonico" and not out:
        out += _historial_canonico(eventos, registro, tipo)
    return out


def _historial_canonico(eventos, registro, tipo):
    """Un registro canónico materializa su estado desde eventos admitidos, empezando por creación o importación."""
    locales = [i for i, ev in enumerate(eventos) if ev.get("registrado_en") is None]
    if locales:
        return [
            _hallazgo("ESQUEMA_INVALIDO", f"/eventos/{i}", "evento local no admitido en un registro canónico")
            for i in locales
        ]
    if not any(ev.get("tipo_evento") in m.EVENTOS_DE_ESTADO for ev in eventos):
        return [_hallazgo("ESQUEMA_INVALIDO", "/eventos", "sin creación ni importación: el estado no tiene historial")]
    try:
        materializado = estado_en(eventos, None, tipo)
    except (ErrorDeHistorial, ValueError) as exc:
        return [_hallazgo(getattr(exc, "codigo", "ESQUEMA_INVALIDO"), "/eventos", str(exc))]
    out = []
    if materializado != registro.get("estado"):
        out.append(_hallazgo("ESQUEMA_INVALIDO", "/estado", f"el historial admitido da {materializado!r}"))
    if tipo == "decision":
        out += _aceptacion_ratificada(eventos)
    return out


def _aceptacion_ratificada(eventos):
    """Aceptar una decisión exige una ratificación previa no revocada. Su autenticidad la comprueba la integración."""
    vigentes, out = set(), []
    for i, ev in enumerate(eventos):
        clase = ev.get("tipo_evento")
        if clase == "ratificacion":
            vigentes.add(ev["aprobacion"]["aprobacion_id"])
        elif clase == "revocacion_aprobacion":
            vigentes.discard(ev.get("aprobacion_id"))
        elif clase == "transicion" and ev.get("estado_nuevo") == "aceptada" and not vigentes:
            out.append(
                _hallazgo("AUTORIDAD_INSUFICIENTE", f"/eventos/{i}", "aceptación sin ratificación previa vigente")
            )
    return out


def _cuerpo(registro, tipo, cuerpo, modo):
    out = []
    try:
        anclas = clausulas(cuerpo)
    except ErrorDeMarca as exc:
        return [_hallazgo("ESQUEMA_INVALIDO", "cuerpo", str(exc))]
    if tipo == "decision" and modo != "intercambio" and not anclas:
        out.append(_hallazgo("ESQUEMA_INVALIDO", "cuerpo", "una decisión expresa sus reglas en cláusulas"))
    propio = f"{registro.get('id')}#"
    for i, mod in enumerate(registro.get("modifica") or []):
        por = mod.get("por") if isinstance(mod, dict) else None
        if isinstance(por, str) and por.startswith(propio) and por[len(propio) :] not in anclas:
            out.append(_hallazgo("REFERENCIA_AUSENTE", f"/modifica/{i}/por", f"la cláusula {por} no está en el cuerpo"))
    for i, e in enumerate(registro.get("define") or []):
        clausula = e.get("clausula") if isinstance(e, dict) else None
        if isinstance(clausula, str) and clausula not in anclas:
            out.append(
                _hallazgo("REFERENCIA_AUSENTE", f"/define/{i}/clausula", f"la cláusula {clausula} no está en el cuerpo")
            )
    try:
        marcas = hechos(cuerpo)
    except ErrorDeMarca as exc:
        return out + [_hallazgo("ESQUEMA_INVALIDO", "cuerpo", str(exc))]
    citas = {s.get("id") for s in registro.get("sources") or [] if isinstance(s, dict)}
    for h in marcas:
        if "ref" in h:
            if m.tipo_de_id(h["ref"]) != "hecho" or not m.RE_ID.match(h["ref"]):
                out.append(_hallazgo("ESQUEMA_INVALIDO", "cuerpo", f"ref de hecho inválida: {h['ref']}"))
            continue
        if h["evidencia"] not in m.CLASES_EVIDENCIA:
            out.append(
                _hallazgo(
                    "ESQUEMA_INVALIDO", "cuerpo", f"clase de evidencia desconocida en {h['id']}: {h['evidencia']}"
                )
            )
        if h["fuente"] not in citas:
            out.append(
                _hallazgo(
                    "REFERENCIA_AUSENTE",
                    "cuerpo",
                    f"el hecho {h['id']} cita la fuente {h['fuente']}, que no está en sources",
                )
            )
    return out
