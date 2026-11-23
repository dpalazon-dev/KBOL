"""Varias carpetas canónicas en una instalación: un snapshot sobre su unión, con una sola raíz.

La política vive en la primera carpeta, que también guarda las solicitudes; los registros pueden estar en cualquiera.
Referencias, IDs únicos, mutabilidad y autoridad se comprueban sobre la unión, y una operación puede tocar varias.
"""

import json

import pytest
from conftest import CUERPO_DECISION, registro
from test_integrar import ACEPTAR, Repo, activo, canonico, proponer

from kbol.core import parse, serializar
from kbol.declarada import MECANISMO, VerificadorDeclarado
from kbol.digest import digest
from kbol.integrar import integrar
from kbol.snapshot import cargar

CARPETAS = ["kb", "docs/decisions"]


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
    repo.escribir("docs/decisions/README.md", "---\ntype: Portada\ntitle: Decisiones\n---\nNo es un registro.\n")
    repo.escribir("docs/otra/nota.md", "---\ntype: Guía\ntitle: n\n---\n")
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def aprobacion(base, digests):
    return {
        "mecanismo": MECANISMO,
        "identidad": "declarada:h",
        "sesion": "s",
        "instante": "2026-11-05T12:00:00Z",
        "cita": "Apruebo la operación",
        "base_mostrada": base,
        "digests": digests,
    }


def integrar_en(repo, base, recibos, archivos, digests, op="op-1", carpeta=None):
    prop = proponer(repo, base, archivos)
    return integrar(
        repo.raiz,
        rama="canon",
        carpeta=CARPETAS if carpeta is None else carpeta,
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=[aprobacion(base, digests)],
        verificador=VerificadorDeclarado(repo.raiz),
        recibos=recibos,
    )


def test_un_registro_en_otra_carpeta_se_integra_con_la_politica_de_la_primera(entorno):
    repo, base, recibos = entorno
    r = registro("decision", id="DEC-Y", autorizado_por=["ROL-OP"])
    archivos = {
        "docs/decisions/DEC-Y.md": serializar(r, CUERPO_DECISION),
        "kb/_solicitudes/op-1.json": json.dumps({"operacion_id": "op-1", "efectos": {"DEC-Y": ACEPTAR}}),
    }
    res = integrar_en(repo, base, recibos, archivos, {"DEC-Y": digest(r, CUERPO_DECISION, ACEPTAR)})
    assert res["estado"] == "integrado", res
    meta, _ = parse(repo.git("show", "canon:docs/decisions/DEC-Y.md") + "\n")
    assert meta["estado"] == "aceptada"


def test_una_referencia_entre_carpetas_se_resuelve_y_una_operacion_toca_las_dos(entorno):
    repo, base, recibos = entorno
    y = registro("decision", id="DEC-Y", autorizado_por=["ROL-OP"])
    z = registro("decision", id="DEC-Z", autorizado_por=["ROL-OP"], afecta_a=["DEC-Y#C1"])
    archivos = {
        "docs/decisions/DEC-Y.md": serializar(y, CUERPO_DECISION),
        "kb/DEC-Z.md": serializar(z, CUERPO_DECISION),
    }
    digests = {"DEC-Y": digest(y, CUERPO_DECISION, []), "DEC-Z": digest(z, CUERPO_DECISION, [])}
    res = integrar_en(repo, base, recibos, archivos, digests)
    assert res["estado"] == "integrado", res
    assert sorted(res["registros"]) == ["DEC-Y", "DEC-Z"]


def test_la_carga_une_las_carpetas_y_un_id_repetido_entre_ellas_no_carga_completa(entorno):
    repo, base, _ = entorno
    r = registro("decision", id="DEC-Y", autorizado_por=["ROL-OP"])
    repo.git("checkout", "-q", "-b", "rep", base)
    repo.escribir("kb/DEC-Y.md", serializar(r, CUERPO_DECISION))
    repo.escribir("docs/decisions/DEC-Y.md", serializar(r, CUERPO_DECISION))
    rev = repo.commit("repetido")
    repo.git("checkout", "-q", "main")
    snap, cobertura = cargar(repo.raiz, CARPETAS, base)
    assert set(snap.registros) == {"ROL-OP", "PER-H"} and cobertura["estado"] == "completo"
    _, repetido = cargar(repo.raiz, CARPETAS, rev, modo="propuesta")
    assert repetido["estado"] != "completo"


def test_fuera_de_las_carpetas_no_se_toca_nada(entorno):
    repo, base, recibos = entorno
    archivos = {"docs/otra/nota.md": "---\ntype: Guía\ntitle: otra\n---\n"}
    res = integrar_en(repo, base, recibos, archivos, {})
    assert res["estado"] == "bloqueado"


@pytest.mark.parametrize(
    "carpeta",
    [[], ["kb", "kb"], ["docs", "docs/decisions"], ["kb", "../fuera"], ["kb", ""], "kb\\x", [1]],
)
def test_carpetas_mal_formadas_o_solapadas_se_rechazan(entorno, carpeta):
    repo, base, recibos = entorno
    res = integrar_en(repo, base, recibos, {"kb/x.md": "x\n"}, {}, carpeta=carpeta)
    assert res["estado"] == "bloqueado"
    assert repo.git("rev-parse", "canon") == base


def test_una_sola_carpeta_como_texto_sigue_valiendo(entorno):
    repo, base, recibos = entorno
    r = registro("decision", id="DEC-Y", autorizado_por=["ROL-OP"])
    res = integrar_en(
        repo,
        base,
        recibos,
        {"kb/DEC-Y.md": serializar(r, CUERPO_DECISION)},
        {"DEC-Y": digest(r, CUERPO_DECISION, [])},
        carpeta="kb",
    )
    assert res["estado"] == "integrado", res
