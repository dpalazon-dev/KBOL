"""Registros mínimos válidos por tipo, con IDs del corpus de prueba del contrato."""

import copy

import pytest

T0 = "2026-11-01T00:00:00Z"
T1 = "2026-11-02T00:00:00Z"

BASE = {
    "clase": "registro",
    "title": "Título",
    "description": "Una línea.",
    "ambito": "operaciones",
    "autor": "agente-ejemplo/1",
    "eventos": [],
    "sources": [],
}

POR_TIPO = {
    "decision": dict(
        id="DEC-EJEMPLO",
        estado="propuesta",
        autorizado_por=["ROL-EJEMPLO"],
        alternativas=[
            dict(id="A", descripcion="Lunes.", seleccionada=False, motivo="Sin día de verificación."),
            dict(id="B", descripcion="Martes.", seleccionada=True, motivo="Reserva el lunes."),
        ],
        criterios=["Datos verificados", "Plazo"],
        justificacion="Reservar un día.",
    ),
    "hecho": dict(
        id="HE-A",
        estado="propuesta",
        afirmacion="La tabla 2 da 5 m3/h.",
        clase_evidencia="observado",
        basada_en=["F-A"],
        fecha="2026-10-30",
        precision="dia",
    ),
    "fuente": dict(
        id="F-A",
        estado="registrada",
        subtipo="original",
        origen="Correo del explotador",
        ubicacion="fuentes/F-A.pdf",
        formato="application/pdf",
        sha256="a" * 64,
        acceso="lectura-comun",
    ),
    "persona": dict(
        id="PER-A",
        estado="propuesta",
        naturaleza="humana",
        identidad_ref="github:1",
        ocupa=[{"rol": "ROL-EJEMPLO", "desde": T0}],
    ),
    "rol": dict(
        id="ROL-EJEMPLO", estado="propuesta", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno"
    ),
    "pregunta": dict(
        id="Q-A", estado="abierta", subtipo="incognita", responsable="ROL-EJEMPLO", condicion_cierre="Medida."
    ),
    "hipotesis": dict(
        id="HIP-A",
        estado="abierta",
        afirmacion="X",
        plan_prueba="Y",
        criterio_refutacion="Z",
        consecuencia_si_falla="W",
    ),
    "supuesto": dict(id="SUP-A", estado="activo", afirmacion="X", revisar_en="2026-12-01", consecuencia_si_falla="W"),
    "entidad": dict(id="ENT-A", estado="propuesta", nombre="Planta", alias=["EDAR"], clase_entidad="instalacion"),
    "plan": dict(
        id="PL-A",
        estado="propuesto",
        objetivo="O",
        hitos=["HI-A"],
        autorizado_por=["ROL-EJEMPLO"],
        restricciones=["No enviar"],
    ),
    "hito": dict(
        id="HI-A",
        estado="propuesto",
        objetivo="Preparar el informe",
        alcance="Rama propia",
        autorizado_por=["ROL-EJEMPLO"],
        aceptacion=[dict(criterio_id="K1", descripcion="Tests", metodo="comando", obligatorio=True)],
        tolerancias={"tiempo": "2h"},
        verificaciones=[
            dict(
                verificacion_id="V1",
                criterio_id="K1",
                ejecutor="pytest",
                entrada={"argv": ["-q"]},
                entorno_ref="local",
                timeout=600,
                efectos_permitidos=[],
            )
        ],
    ),
    "sintesis": dict(id="SIN-A", estado="borrador", dependencias=["DEC-EJEMPLO#C1"], evaluaciones=[]),
}

CUERPO_DECISION = '<clausula id="C1">\nEl informe se entrega los martes.\n</clausula>\n'


def registro(tipo, **cambios):
    r = copy.deepcopy(BASE)
    r["type"] = tipo
    r.update(copy.deepcopy(POR_TIPO[tipo]))
    r.update(cambios)
    return r


def evento(tipo_evento="transicion", **cambios):
    e = dict(
        evento_id="E1",
        tipo_evento=tipo_evento,
        actor="process:integrador",
        registrado_en=T0,
        valido_desde=T0,
        motivo="m",
        evidencia_evento={"mecanismo": "github-review", "comprobante": "review:1"},
    )
    e.update(cambios)
    return e


def cuerpo_de(clausulas):
    return "".join(f'<clausula id="{a}">\n{t}\n</clausula>\n\n' for a, t in clausulas.items())


def decision(ident, clausulas, registrado=T0, valido=None, hasta=None, estado="aceptada", **extra):
    """(registro, cuerpo) de una decisión con historial admitido: creación, ratificación y aceptación."""
    eventos = [
        evento(
            "creacion",
            evento_id="E0",
            estado_anterior=None,
            estado_nuevo="propuesta",
            registrado_en=registrado,
            valido_desde=registrado,
        )
    ]
    if estado == "aceptada":
        aprob = dict(
            aprobacion_id=f"AP-{ident}",
            actor="human:david",
            identidad_ref="github:1",
            roles=["ROL-EJEMPLO"],
            digest="b" * 64,
            revision_base="r0",
            aprobada_en=registrado,
            politica_revision="r0",
            comprobante="review:1",
        )
        eventos.append(
            evento("ratificacion", evento_id="E1", registrado_en=registrado, valido_desde=registrado, aprobacion=aprob)
        )
        paso = evento(
            evento_id="E2",
            estado_anterior="propuesta",
            estado_nuevo="aceptada",
            registrado_en=registrado,
            valido_desde=valido or registrado,
        )
        if hasta:
            paso["valido_hasta"] = hasta
        eventos.append(paso)
    r = registro("decision", id=ident, estado=estado, eventos=eventos, **extra)
    return r, cuerpo_de(clausulas)


@pytest.fixture
def nuevo():
    return registro
