"""CLI `impacto`: consumidores afectados por el paso de una revisión base a otra (E5, consulta de solo lectura)."""

import json
import subprocess
import sys

from conftest import decision, evento, registro

from kbol.core import serializar

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def escribir(carpeta, nombre, r, c=""):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{nombre}.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")


def commit(repo, mensaje):
    subprocess.run(["git", "-C", str(repo), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), *GIT, "commit", "-q", "-m", mensaje], check=True)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def repo_con_consumidor(tmp_path):
    """Base: DEC-A, DEC-C que depende de DEC-A#C1 y el rol. Después: DEC-B sustituye DEC-A#C1."""
    repo, kb_ = tmp_path / "repo", tmp_path / "repo" / "kb"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    creacion = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")
    escribir(kb_, "ROL", registro("rol", eventos=[creacion]))
    escribir(kb_, "DEC-A", *decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z"))
    consumidor = decision(
        "DEC-C",
        {"C1": "El informe sale el día fijado."},
        registrado="2026-11-01T00:00:00Z",
        depende_de=[{"destino": "DEC-A#C1", "condicion": "aceptada_y_vigente"}],
    )
    escribir(kb_, "DEC-C", *consumidor)
    base = commit(repo, "base")
    nueva = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
    )
    escribir(kb_, "DEC-B", *nueva)
    return repo, base, commit(repo, "sustitución")


def test_impacto_entre_dos_revisiones(tmp_path):
    repo, base, final = repo_con_consumidor(tmp_path)
    code, out = kb("impacto", str(repo), "--carpeta", "kb", "--base", base, "--revision", final)
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    assert out["resultado"]["cambiados"] == ["DEC-B"]
    [afectado] = out["resultado"]["afectados"]
    assert afectado["afectado"] == "DEC-C" and afectado["camino"] == ["DEC-B", "DEC-A#C1", "DEC-C"]
    assert afectado["resolucion"] == "pendiente"
    assert out["revision"] == final and out["resultado"]["base"] == base


def test_impacto_exige_la_base(tmp_path):
    repo, _, final = repo_con_consumidor(tmp_path)
    code, out = kb("impacto", str(repo), "--carpeta", "kb", "--revision", final)
    assert code == 2 and "--base" in out["resultado"]["motivo"]


def test_impacto_contra_el_disco_lo_declara(tmp_path):
    repo, base, _ = repo_con_consumidor(tmp_path)
    code, out = kb("impacto", str(repo), "--carpeta", "kb", "--base", base)
    assert code == 0 and out["revision"] == "disco"
    assert any("disco" in a for a in out["advertencias"])


def test_impacto_con_una_base_que_no_existe(tmp_path):
    repo, _, final = repo_con_consumidor(tmp_path)
    code, out = kb("impacto", str(repo), "--carpeta", "kb", "--base", "0" * 40, "--revision", final)
    assert code == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"
