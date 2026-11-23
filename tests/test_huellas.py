"""Huellas y desvíos: la integración guarda la huella de lo que escribe y `desvios` avisa de lo
que se editó fuera del flujo, sin bloquear."""

# ruff: noqa: F811  (el fixture entorno se importa de test_declarada)

import json
import subprocess
import sys

from test_decisiva import llamar, pregunta
from test_declarada import entorno  # noqa: F401
from test_integrar import proponer

from kbol.core import serializar
from kbol.huellas import ARCHIVO, desvios, huella


def integrar_pregunta(repo, base, recibos):
    r, c = pregunta()
    res = llamar(repo, base, proponer(repo, base, {"kb/Q-N.md": serializar(r, c)}), recibos)
    assert res["estado"] == "integrado", res
    return res


def test_la_integracion_guarda_la_huella_de_lo_que_escribe(entorno):
    repo, base, recibos = entorno
    integrar_pregunta(repo, base, recibos)
    guardadas = json.loads(repo.git("show", f"canon:kb/{ARCHIVO}"))
    assert guardadas["Q-N"] == {"ruta": "kb/Q-N.md", "sha256": huella(repo.git("show", "canon:kb/Q-N.md") + "\n")}
    assert set(guardadas) == {"Q-N"}


def test_una_propuesta_no_puede_tocar_las_huellas(entorno):
    repo, base, recibos = entorno
    r, c = pregunta()
    prop = proponer(repo, base, {"kb/Q-N.md": serializar(r, c), f"kb/{ARCHIVO}": "{}\n"})
    assert llamar(repo, base, prop, recibos)["estado"] == "bloqueado"


def test_desvios_avisa_de_una_edicion_a_mano_y_de_lo_que_no_tiene_huella(entorno):
    repo, base, recibos = entorno
    integrar_pregunta(repo, base, recibos)
    repo.git("checkout", "-q", "canon")
    res = desvios(repo.raiz, "kb", rama="canon")
    sin = {a["id"] for a in res["avisos"] if a["motivo"] == "sin_huella"}
    assert "Q-N" not in sin and "PER-H" in sin  # los de la base no pasaron por esta integración
    assert not [a for a in res["avisos"] if a["motivo"] == "distinta"]
    ruta = repo.raiz / "kb" / "Q-N.md"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("Texto.", "Texto cambiado a mano."), encoding="utf-8")
    distinta = [a for a in desvios(repo.raiz, "kb", rama="canon")["avisos"] if a["motivo"] == "distinta"]
    assert distinta == [{"id": "Q-N", "ruta": "kb/Q-N.md", "motivo": "distinta", "ultima_integrada": "canon:kb/Q-N.md"}]


def test_en_preparado_compara_el_indice_y_no_el_disco(entorno):
    repo, base, recibos = entorno
    integrar_pregunta(repo, base, recibos)
    repo.git("checkout", "-q", "canon")
    ruta = repo.raiz / "kb" / "Q-N.md"
    original = ruta.read_text(encoding="utf-8")
    ruta.write_text(original.replace("Texto.", "Otro."), encoding="utf-8")
    assert not [a for a in desvios(repo.raiz, "kb", preparado=True)["avisos"] if a["motivo"] == "distinta"]
    repo.git("add", "kb/Q-N.md")
    assert [a["id"] for a in desvios(repo.raiz, "kb", preparado=True)["avisos"] if a["motivo"] == "distinta"] == ["Q-N"]


def test_los_saltos_de_linea_no_cambian_la_huella():
    assert huella("a\r\nb\n") == huella("a\nb\n") == huella(b"a\nb\n")


def test_la_cli_avisa_sin_bloquear(entorno):
    repo, base, recibos = entorno
    integrar_pregunta(repo, base, recibos)
    repo.git("checkout", "-q", "canon")
    ruta = repo.raiz / "kb" / "Q-N.md"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("Texto.", "Otro."), encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "desvios", str(repo.raiz), "--carpeta", "kb", "--rama-canonica", "canon"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0, p.stderr
    sobre = json.loads(p.stdout)
    assert sobre["resultado"]["estado"] == "completado" and sobre["resultado"]["comprobados"] > 0
    assert "Q-N" in {a["id"] for a in sobre["resultado"]["avisos"]}
    assert sobre["advertencias"]


def test_la_puerta_de_huellas_reconoce_los_mismos_correos_que_integrar_y_arranque():
    from kbol.arranque import _IDENTIDAD_ARRANQUE
    from kbol.huellas import CORREOS_DE_LA_PUERTA
    from kbol.integrar import CORREO

    assert {CORREO, _IDENTIDAD_ARRANQUE["GIT_COMMITTER_EMAIL"]} == CORREOS_DE_LA_PUERTA


def test_un_commit_directo_a_la_rama_canonica_sale_fuera_del_flujo(entorno):
    from kbol.huellas import commits_fuera_del_flujo

    repo, base, recibos = entorno
    assert commits_fuera_del_flujo(repo.raiz, "kb", "canon") == {"evaluado": False, "desde": None, "commits": []}
    res = integrar_pregunta(repo, base, recibos)
    limpio = commits_fuera_del_flujo(repo.raiz, "kb", "canon")
    assert limpio == {"evaluado": True, "desde": res["revision_integrada"], "commits": []}
    repo.git("checkout", "-q", "canon")
    repo.escribir("README.md", "otro\n")
    repo.commit("fuera de registros: no cuenta")
    repo.escribir("kb/nota.txt", "a mano\n")
    directo = repo.commit("a mano en registros")
    fuera = commits_fuera_del_flujo(repo.raiz, "kb", "canon")
    assert [c["commit"] for c in fuera["commits"]] == [directo]
    assert fuera["commits"][0]["asunto"] == "a mano en registros"
    assert commits_fuera_del_flujo(repo.raiz, "kb", "no-existe")["evaluado"] is False


def test_la_cli_avisa_de_los_commits_fuera_del_flujo_sin_bloquear(entorno):
    repo, base, recibos = entorno
    integrar_pregunta(repo, base, recibos)
    repo.git("checkout", "-q", "canon")
    repo.escribir("kb/nota.txt", "a mano\n")
    directo = repo.commit("a mano en registros")
    orden = [sys.executable, "-m", "kbol.cli", "desvios", str(repo.raiz), "--carpeta", "kb"]
    p = subprocess.run([*orden, "--rama-canonica", "canon"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    sobre = json.loads(p.stdout)
    assert [c["commit"] for c in sobre["resultado"]["commits_fuera_del_flujo"]] == [directo]
    assert any("sin pasar por la puerta" in a for a in sobre["advertencias"])
    sin_rama = json.loads(subprocess.run(orden, capture_output=True, text=True, encoding="utf-8").stdout)
    assert "commits_fuera_del_flujo" not in sin_rama["resultado"]
    assert "commits de la rama canónica" in sin_rama["cobertura"]["no_evaluado"]
