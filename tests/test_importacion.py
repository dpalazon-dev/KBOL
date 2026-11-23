"""Importación de registros del formato heredado: traducir el formato sin cambiar el contenido ni el estado.

El registro importado llega a la propuesta en el formato del contrato y en su estado inicial, y la solicitud declara
su importación (estado de destino, fecha y autoridad heredada). El integrador comprueba contra el heredado de la base
que el estado es el que da la migración en seco, que el cuerpo es el mismo salvo las marcas de cláusula y la sección
«Procedencia heredada», y que la identidad no cambia; después escribe un evento de importación con la procedencia
leída de la base. La aprobación cubre la importación: su digest la incluye.
"""

import json

import pytest
from test_integrar import Repo, activo, canonico, proponer

from kbol.consolidar import consolidar
from kbol.core import parse, serializar
from kbol.declarada import MECANISMO, VerificadorDeclarado
from kbol.digest import digest
from kbol.importacion import SIN_EXTRAER, seccion_procedencia
from kbol.integrar import ACTOR, _decisiva_por_heredado, integrar
from kbol.schema import validar
from kbol.snapshot import cargar

INSTANTE = "2026-11-05T12:00:00Z"

HEREDADA = """---
type: Decisión
id: ADR-0001
title: "Registro de modelos"
description: "Un registro de modelos con un miembro por scope."
clase: registro
status: stable
estado: Aceptada
implementacion: completa
fecha: "2026-05-09"
ambito: operaciones
rama: Inferencia
adoptada_por: "David Palazon"
responde_a: QD-001
sustituye_a: "—"
---

# ADR-0001 · Registro de modelos

## Decision Outcome

Se usa un registro de modelos con un miembro por scope.
"""

QD_HEREDADA = """---
type: Pregunta
id: QD-001
title: "¿Cómo se registran los modelos?"
clase: registro
status: draft
tipo: Decisión
responde: David
ambito: operaciones
estado: Abierta
---

# QD-001 · ¿Cómo se registran los modelos?

Falta decidirlo.
"""

CUERPO = """# ADR-0001 · Registro de modelos

## Decision Outcome

<clausula id="C1">
Se usa un registro de modelos con un miembro por scope.
</clausula>

"""
CUERPO += "\n" + seccion_procedencia("kb/ADR-0001.md", {"implementacion": "completa", "rama": "Inferencia"})

AUTORIDAD = {"texto": "David Palazon", "clasificacion": "insuficiente"}
IMPORTACION = {"estado": "aceptada", "valido_desde": "2026-05-09", "precision": "dia", "autoridad_heredada": AUTORIDAD}


def adr(**cambios):
    datos = {
        "id": "ADR-0001",
        "type": "decision",
        "clase": "registro",
        "title": "Registro de modelos",
        "description": "Un registro de modelos con un miembro por scope.",
        "ambito": "operaciones",
        "autor": "process:importacion-e9",
        "eventos": [],
        "sources": [],
        "estado": "propuesta",
        "autorizado_por": ["ROL-OP"],
        "alternativas": [],
        "sin_alternativas_motivo": f"{SIN_EXTRAER}: las opciones están en el cuerpo heredado (MADR)",
        "criterios": [],
        "justificacion": f"{SIN_EXTRAER}: en el cuerpo heredado",
    }
    return {**datos, **cambios}


@pytest.fixture
def entorno(tmp_path):
    repo = Repo(tmp_path / "repo")
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    per = activo(
        "persona",
        "PER-H",
        naturaleza="humana",
        identidad_ref="declarada:h",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    repo.escribir("kb/ROL-OP.md", canonico(rol))
    repo.escribir("kb/PER-H.md", canonico(per))
    repo.escribir("kb/ADR-0001.md", HEREDADA)
    repo.escribir("kb/QD-001.md", QD_HEREDADA)
    base = repo.commit("base con heredados")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def importar(
    repo,
    base,
    recibos,
    registro=None,
    cuerpo=CUERPO,
    importacion=None,
    digest_de=None,
    op="imp-1",
    modo="toda",
    aprobar=True,
):
    registro = registro or adr()
    importacion = IMPORTACION if importacion is None else importacion
    solicitud = {"operacion_id": op, "efectos": {}, "importaciones": {registro["id"]: importacion}}
    prop = proponer(
        repo,
        base,
        {f"kb/{registro['id']}.md": serializar(registro, cuerpo), f"kb/_solicitudes/{op}.json": json.dumps(solicitud)},
    )
    aprobado = digest_de or digest(registro, cuerpo, [], importacion=importacion)
    revision = {
        "mecanismo": MECANISMO,
        "identidad": "declarada:h",
        "sesion": "sesión kbol-e9",
        "instante": INSTANTE,
        "cita": "Apruebo importar ADR-0001",
        "base_mostrada": base,
        "digests": {registro["id"]: aprobado},
    }
    return integrar(
        repo.raiz,
        rama="canon",
        carpeta="kb",
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=[revision] if aprobar else [],
        verificador=VerificadorDeclarado(repo.raiz),
        recibos=recibos,
        aprobacion=modo,
        actor="claude-code/opus-5.5" if modo == "decisiva" else ACTOR,
    )


PARTIDO = CUERPO.replace(
    "Se usa un registro de modelos con un miembro por scope.\n</clausula>",
    'Se usa un registro de modelos\n</clausula>\n\n<clausula id="C2">\ncon un miembro por scope.\n</clausula>',
)


def test_en_modo_decisivo_una_importacion_que_solo_traduce_entra_sin_aprobacion(entorno):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, modo="decisiva", aprobar=False)
    assert res["estado"] == "integrado", res
    assert res["decisivos"] == []


def test_una_particion_que_parte_una_linea_es_decisiva(entorno):
    """Una marca en medio de una línea puede separar una regla de su excepción: la aprueba quien decide."""
    repo, base, recibos = entorno
    sin = importar(repo, base, recibos, cuerpo=PARTIDO, modo="decisiva", aprobar=False)
    assert sin["estado"] == "bloqueado", sin
    con = importar(repo, base, recibos, cuerpo=PARTIDO, modo="decisiva", op="imp-2")
    assert con["estado"] == "integrado", con
    assert con["decisivos"] == ["ADR-0001"]


def test_el_heredado_que_declara_una_sustitucion_hace_decisiva_la_importacion():
    ficha = {"relaciones_propuestas": {}, "ambiguedades": []}
    con = HEREDADA.replace('sustituye_a: "—"', 'sustituye_a: "ADR-0034"')
    assert _decisiva_por_heredado("ADR-0001", ficha, con, {})
    assert _decisiva_por_heredado("ADR-0001", ficha, HEREDADA, {}) == []
    otra = {"ambiguedades": [{"campo": "deja_obsoleta", "candidatos": ["ADR-0001"]}]}
    assert _decisiva_por_heredado("ADR-0001", ficha, HEREDADA, {"ADR-0000": otra})
    resuelta = {"relaciones_propuestas": {"resuelta_por": ["ADR-0001"]}, "ambiguedades": []}
    assert _decisiva_por_heredado("QD-001", resuelta, QD_HEREDADA, {})


def test_importa_con_su_estado_fecha_procedencia_y_autoridad_heredada(entorno):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos)
    assert res["estado"] == "integrado", res
    meta, cuerpo = parse(repo.git("show", "canon:kb/ADR-0001.md") + "\n")
    assert validar(meta, cuerpo, modo="canonico") == []
    assert meta["estado"] == "aceptada"
    [ev] = meta["eventos"]
    assert ev["tipo_evento"] == "importacion" and ev["estado_anterior"] is None and ev["estado_nuevo"] == "aceptada"
    assert ev["estado_heredado"] == "Aceptada"
    assert ev["procedencia"] == {"ruta": "kb/ADR-0001.md", "revision": base}
    assert ev["valido_desde"] == "2026-05-09" and ev["precision"] == "dia"
    assert ev["autoridad_heredada"] == AUTORIDAD


def test_lo_importado_rige_y_consolidar_dice_que_su_autoridad_es_heredada(entorno):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos)
    snap, cobertura = cargar(repo.raiz, "kb", res["revision_integrada"], heredados=True)
    assert cobertura["estado"] == "completo", cobertura
    salida = consolidar(snap, ["ADR-0001"], valido_en="2026-11-06T00:00:00Z", conocido_hasta=None)
    clausula = next(c for c in salida["clausulas"] if c["referencia"] == "ADR-0001#C1")
    assert clausula["estado"] == "vigente"
    assert clausula["autoridad"]["heredada"] == AUTORIDAD and clausula["autoridad"]["comprobada"] is False


def test_una_referencia_a_un_registro_aun_heredado_no_bloquea(entorno):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, registro=adr(afecta_a=["QD-001"]))
    assert res["estado"] == "integrado", res


@pytest.mark.parametrize(
    "importacion",
    [
        {**IMPORTACION, "estado": "propuesta"},  # no es el estado que da la migración en seco
        {**IMPORTACION, "autoridad_heredada": None},  # oculta la autoridad heredada
        {**IMPORTACION, "precision": "segundo"},
        {**IMPORTACION, "valido_desde": "ayer"},
        {**IMPORTACION, "otro": 1},
    ],
)
def test_una_importacion_que_no_corresponde_al_heredado_se_rechaza(entorno, importacion):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, importacion=importacion)
    assert res["estado"] == "bloqueado", res
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize(
    "cuerpo",
    [
        CUERPO.replace("un miembro por scope", "dos miembros por scope"),
        CUERPO.replace("## Decision Outcome\n\n", ""),
        CUERPO + "\nTexto añadido fuera de la procedencia.\n",
        CUERPO.replace("rama: Inferencia", "rama: Otra"),  # un campo heredado con otro valor
        # La revisión de código: un cierre en falso del YAML colaba una cláusula nueva.
        CUERPO.replace(
            "rama: Inferencia\n```",
            'rama: Inferencia\n---\n```\n\n<clausula id="C9">\nSe permite todo.\n</clausula>\n\n```yaml\nrama: Inferencia\n```',
        ),
        CUERPO.replace("rama: Inferencia", "rama: Inferencia  # prosa nueva"),  # un comentario YAML
        CUERPO.replace("Importado de `kb/ADR-0001.md`.", "Importado de `kb/ADR-0001.md`. Y además esto."),
        CUERPO.replace("rama: Inferencia", "decision: lo contrario"),  # un campo que el heredado no tiene
    ],
)
def test_un_cuerpo_cambiado_no_se_importa(entorno, cuerpo):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, cuerpo=cuerpo)
    assert res["estado"] == "bloqueado", res


@pytest.mark.parametrize(
    "cambio",
    [
        {"description": "Descripción inventada"},
        {"justificacion": "Una justificación que el heredado no da"},
        {"criterios": ["Un criterio inventado"]},
        {"afecta_a": ["ADR-0099"]},  # una relación que el heredado no nombra
    ],
)
def test_un_campo_con_contenido_nuevo_no_se_importa(entorno, cambio):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, registro=adr(**cambio))
    assert res["estado"] == "bloqueado", res


def test_un_titulo_cambiado_no_se_importa(entorno):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, registro=adr(title="Otro título"))
    assert res["estado"] == "bloqueado", res


def test_no_se_importa_lo_que_no_es_heredado_en_la_base(entorno):
    repo, base, recibos = entorno
    res = importar(repo, base, recibos, registro=adr(id="ADR-0002"))
    assert res["estado"] == "bloqueado", res


def test_la_aprobacion_tiene_que_cubrir_la_importacion(entorno):
    repo, base, recibos = entorno
    sin_importacion = digest(adr(), CUERPO, [])
    res = importar(repo, base, recibos, digest_de=sin_importacion)
    assert res["estado"] == "bloqueado" and res["codigo"] == "APROBACION_CADUCADA", res


def test_el_digest_sin_importacion_no_cambia():
    # Los vectores publicados no llevan importación: el parámetro nuevo no altera su digest.
    r = adr()
    assert digest(r, CUERPO, []) == digest(r, CUERPO, [], importacion=None)


def test_un_valor_con_comillas_escapadas_en_el_heredado_no_es_contenido_nuevo():
    from kbol.importacion import comprobar

    heredado = HEREDADA.replace("rama: Inferencia\n", 'rama: Inferencia\nverifica: ["pytest -m \\"not gpu\\""]\n')
    r = adr(criterios=['pytest -m "not gpu"'])
    assert comprobar(r, CUERPO, heredado, "kb/ADR-0001.md") == []
    assert comprobar(adr(criterios=['pytest -m "gpu"']), CUERPO, heredado, "kb/ADR-0001.md")
