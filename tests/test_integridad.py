"""Integridad de las fuentes (`kbol integridad`): coincide, alterada, ausente o no comprobada, con su causa."""

import hashlib
import json
import subprocess

import pytest
from conftest import registro

from kbol.cli import main
from kbol.core import serializar
from kbol.integridad import comprobar, comprobar_fuente

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
CONTENIDO = b"%PDF-1.7 original de prueba\r\ncon saltos de Windows\r\n"
SHA = hashlib.sha256(CONTENIDO).hexdigest()
OTRA = "b" * 64


def git(raiz, *args):
    p = subprocess.run(["git", "-C", str(raiz), *GIT, *args], check=True, capture_output=True, text=True)
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """Repositorio con un original versionado tal cual (sin normalizar saltos) y su revisión."""
    raiz = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    (raiz / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    (raiz / "originales").mkdir()
    (raiz / "originales" / "informe.pdf").write_bytes(CONTENIDO)
    (raiz / "kb").mkdir()
    git(raiz, "add", "-A")
    git(raiz, "commit", "-q", "-m", "base")
    return raiz, git(raiz, "rev-parse", "HEAD")


@pytest.fixture
def almacen(tmp_path):
    carpeta = tmp_path / "almacen"
    (carpeta / "sha256").mkdir(parents=True)
    (carpeta / "sha256" / SHA).write_bytes(CONTENIDO)
    return carpeta


def fuente(ident, ubicacion, sha256=SHA):
    return registro("fuente", id=ident, ubicacion=ubicacion, sha256=sha256)


def guardar(raiz, r):
    (raiz / "kb" / f"{r['id']}.md").write_text(serializar(r, ""), encoding="utf-8", newline="\n")


def kb(capsys, *args):
    codigo = main(list(args))
    return codigo, json.loads(capsys.readouterr().out)


# ── Una fuente ──────────────────────────────────────────────────────────────


def test_ruta_de_la_raiz(repo):
    raiz, _ = repo
    assert comprobar_fuente(raiz, fuente("F-A", "originales/informe.pdf")) == ("coincide", None)
    estado, causa = comprobar_fuente(raiz, fuente("F-A", "originales/informe.pdf", OTRA))
    assert estado == "alterada" and "árbol de trabajo" in causa
    estado, causa = comprobar_fuente(raiz, fuente("F-A", "originales/no-esta.pdf"))
    assert estado == "ausente" and "no existe" in causa


def test_los_bytes_no_se_normalizan(repo):
    raiz, _ = repo
    (raiz / "originales" / "informe.pdf").write_bytes(CONTENIDO.replace(b"\r\n", b"\n"))
    assert comprobar_fuente(raiz, fuente("F-A", "originales/informe.pdf"))[0] == "alterada"


def test_revision_anclada_de_git(repo):
    raiz, rev = repo
    ubicacion = f"git:{rev}:originales/informe.pdf"
    assert comprobar_fuente(raiz, fuente("F-A", ubicacion)) == ("coincide", None)
    # La revisión anclada no cambia aunque el árbol de trabajo cambie o pierda el archivo.
    (raiz / "originales" / "informe.pdf").unlink()
    assert comprobar_fuente(raiz, fuente("F-A", ubicacion)) == ("coincide", None)
    assert comprobar_fuente(raiz, fuente("F-A", ubicacion, OTRA))[0] == "alterada"
    estado, causa = comprobar_fuente(raiz, fuente("F-A", f"git:{rev}:originales/otro.pdf"))
    assert estado == "ausente" and rev[:12] in causa


def test_una_carpeta_de_la_revision_no_es_un_original_alterado(repo):
    raiz, rev = repo
    estado, causa = comprobar_fuente(raiz, fuente("F-A", f"git:{rev}:originales"))
    assert estado == "ausente" and "no es un archivo" in causa


def test_una_revision_que_no_esta_en_el_clon_no_es_una_acusacion(repo):
    raiz, _ = repo
    estado, causa = comprobar_fuente(raiz, fuente("F-A", "git:" + "0" * 40 + ":originales/informe.pdf"))
    assert estado == "no_comprobada" and "no está en este clon" in causa


def test_una_revision_sin_anclar_no_se_comprueba(repo):
    raiz, _ = repo
    estado, causa = comprobar_fuente(raiz, fuente("F-A", "git:main:originales/informe.pdf"))
    assert estado == "no_comprobada" and "SHA completo" in causa


def test_clon_superficial_sin_la_revision(repo, tmp_path):
    raiz, rev = repo
    (raiz / "otro.txt").write_text("x\n", encoding="utf-8")
    git(raiz, "add", "-A")
    git(raiz, "commit", "-q", "-m", "segundo")
    clon = tmp_path / "clon"
    subprocess.run(["git", "clone", "-q", "--depth", "1", raiz.as_uri(), str(clon)], check=True)
    estado, causa = comprobar_fuente(clon, fuente("F-A", f"git:{rev}:originales/informe.pdf"))
    assert estado == "no_comprobada" and "clon superficial" in causa


def test_almacen(repo, almacen, tmp_path):
    raiz, _ = repo
    ubicacion = f"almacen:sha256/{SHA}"
    assert comprobar_fuente(raiz, fuente("F-A", ubicacion), almacen) == ("coincide", None)
    estado, causa = comprobar_fuente(raiz, fuente("F-A", ubicacion))
    assert estado == "no_comprobada" and "no se indicó el almacén" in causa
    estado, causa = comprobar_fuente(raiz, fuente("F-A", ubicacion), tmp_path / "otro-almacen")
    assert estado == "no_comprobada" and "no está en el almacén de esta máquina" in causa
    (almacen / "sha256" / SHA).write_bytes(b"otro contenido")
    estado, causa = comprobar_fuente(raiz, fuente("F-A", ubicacion), almacen)
    assert estado == "alterada" and "objeto del almacén" in causa


def test_la_ubicacion_del_almacen_nombra_la_huella_de_la_fuente(repo, almacen):
    raiz, _ = repo
    estado, causa = comprobar_fuente(raiz, fuente("F-A", f"almacen:sha256/{SHA}", OTRA), almacen)
    assert estado == "alterada" and "no es la de la fuente" in causa


@pytest.mark.parametrize(
    "ubicacion",
    ["https://ejemplo.org/informe.pdf", "C:/Users/alguien/informe.pdf", "/srv/informe.pdf", "../fuera/informe.pdf"],
)
def test_lo_que_no_se_puede_mirar_no_se_comprueba(repo, ubicacion):
    raiz, _ = repo
    assert comprobar_fuente(raiz, fuente("F-A", ubicacion))[0] == "no_comprobada"


# ── Las fuentes de una carpeta ──────────────────────────────────────────────


def test_una_fila_por_fuente_con_el_recuento(repo, almacen):
    raiz, rev = repo
    guardar(raiz, fuente("F-A", "originales/informe.pdf"))
    guardar(raiz, fuente("F-B", f"git:{rev}:originales/informe.pdf", OTRA))
    guardar(raiz, fuente("F-C", f"almacen:sha256/{OTRA}", OTRA))
    guardar(raiz, registro("pregunta"))
    res = comprobar(raiz, "kb", almacen)
    assert [(f["id"], f["estado"]) for f in res["fuentes"]] == [
        ("F-A", "coincide"),
        ("F-B", "alterada"),
        ("F-C", "no_comprobada"),
    ]
    assert res["fuentes"][0] == {
        "id": "F-A",
        "ruta": "kb/F-A.md",
        "ubicacion": "originales/informe.pdf",
        "estado": "coincide",
        "causa": None,
    }
    assert res["recuento"] == {"coincide": 1, "alterada": 1, "ausente": 0, "no_comprobada": 1}
    assert res["cobertura"]["leidos"] == 4


def test_cli_todas_coinciden(repo, almacen, capsys):
    raiz, rev = repo
    guardar(raiz, fuente("F-A", "originales/informe.pdf"))
    guardar(raiz, fuente("F-B", f"git:{rev}:originales/informe.pdf"))
    guardar(raiz, fuente("F-C", f"almacen:sha256/{SHA}"))
    codigo, out = kb(capsys, "integridad", str(raiz), "--carpeta", "kb", "--almacen", str(almacen))
    assert codigo == 0 and out["operacion"] == "integridad" and out["resultado"]["estado"] == "completado", out
    assert out["resultado"]["recuento"]["coincide"] == 3 and "codigo" not in out["resultado"]
    assert "última comprobación válida de cada fuente" in out["cobertura"]["no_evaluado"]
    assert out["cobertura"]["registros_leidos"] == 3


def test_cli_una_fuente_rota_es_fallido_con_su_codigo(repo, capsys):
    raiz, _ = repo
    guardar(raiz, fuente("F-A", "originales/informe.pdf"))
    guardar(raiz, fuente("F-B", "originales/no-esta.pdf"))
    guardar(raiz, fuente("F-C", f"almacen:sha256/{SHA}"))
    codigo, out = kb(capsys, "integridad", str(raiz), "--carpeta", "kb")
    assert codigo == 1 and out["resultado"]["estado"] == "fallido", out
    assert out["resultado"]["codigo"] == "INTEGRIDAD_ROTA"
    assert out["resultado"]["recuento"] == {"coincide": 1, "alterada": 0, "ausente": 1, "no_comprobada": 1}
    assert any(a.startswith("F-B (originales/no-esta.pdf): ausente") for a in out["advertencias"])
    assert any(a.startswith("F-C ") and "no_comprobada" in a for a in out["advertencias"])


def test_cli_sin_comprobar_es_parcial_y_no_rota(repo, capsys):
    raiz, _ = repo
    guardar(raiz, fuente("F-A", "originales/informe.pdf"))
    guardar(raiz, fuente("F-C", f"almacen:sha256/{SHA}"))
    codigo, out = kb(capsys, "integridad", str(raiz), "--carpeta", "kb")
    assert codigo == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["codigo"] == "INTEGRIDAD_NO_COMPROBADA"


def test_cli_una_fuente_que_no_carga_deja_la_comprobacion_parcial(repo, capsys):
    raiz, _ = repo
    guardar(raiz, fuente("F-A", "originales/informe.pdf"))
    (raiz / "kb" / "F-ROTA.md").write_text("---\nid: [sin cerrar\n---\n", encoding="utf-8")
    codigo, out = kb(capsys, "integridad", str(raiz), "--carpeta", "kb")
    assert codigo == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["recuento"]["coincide"] == 1 and out["cobertura"]["truncado"] is True
    assert "codigo" not in out["resultado"]


def test_cli_sin_fuentes_es_parcial_y_sin_carpeta_fallido(repo, capsys):
    raiz, _ = repo
    guardar(raiz, registro("pregunta"))
    codigo, out = kb(capsys, "integridad", str(raiz), "--carpeta", "kb")
    assert codigo == 3 and out["resultado"]["fuentes"] == [], out
    assert any("ninguna fuente" in a for a in out["advertencias"])
    codigo, out = kb(capsys, "integridad", str(raiz), "--carpeta", "no-existe")
    assert codigo == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE", out
