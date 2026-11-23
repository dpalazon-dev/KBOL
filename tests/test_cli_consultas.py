"""CLI `consolidar` y `listos` sobre un snapshot del disco o de una revisión de git."""

import json
import subprocess
import sys

from conftest import decision, evento, registro

from kbol.core import serializar
from kbol.snapshot import cargar


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def escribir_esc01(carpeta, martes=True, rol_valido=False):
    a = decision("DEC-A", {"C1": "Lunes.", "C2": "Datos verificados."}, registrado="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Martes." if martes else "Jueves."},
        registrado="2026-11-02T00:00:00Z",
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
    )
    creacion = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")
    rol = registro("rol", eventos=[creacion] if rol_valido else [])
    carpeta.mkdir(parents=True, exist_ok=True)
    for (r, c), nombre in ((a, "DEC-A"), (b, "DEC-B")):
        (carpeta / f"{nombre}.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")
    (carpeta / "ROL.md").write_text(serializar(rol, ""), encoding="utf-8", newline="\n")
    (carpeta / "heredado.md").write_text("---\ntype: Decisión\nid: ADR-0001\n---\n", encoding="utf-8")


def textos(out):
    return [c["texto"] for c in out["resultado"]["clausulas"] if c["estado"] == "vigente"]


def test_consolidar_desde_disco(tmp_path):
    escribir_esc01(tmp_path / "kb")
    code, out = kb(
        "consolidar", str(tmp_path), "--carpeta", "kb", "--ids", "DEC-A", "--valido-en", "2026-11-03T12:00:00Z"
    )
    # El rol sin historial no es canónico: queda fuera y la consulta es parcial; el heredado se omite.
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert textos(out) == ["Martes.", "Datos verificados."]
    assert out["valido_en"] == "2026-11-03T12:00:00Z" and out["conocido_hasta"] is None
    assert out["revision"] == "disco" and any("disco" in a for a in out["advertencias"])
    assert any("corte de conocimiento" in a for a in out["advertencias"])
    assert out["cobertura"]["registros_leidos"] == 2 and out["cobertura"]["omitidos"] == 1
    assert out["cobertura"]["truncado"] is True
    assert [i["ruta"] for i in out["cobertura"]["invalidos"]] == ["kb/ROL.md"]


def test_consolidar_exige_reloj_explicito_y_bien_formado(tmp_path):
    escribir_esc01(tmp_path)
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A")
    assert code == 2 and "valido-en" in out["resultado"]["motivo"]
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", "2026-11-03")
    assert code == 2 and out["resultado"]["codigo"] == "TIEMPO_AMBIGUO"


def test_revision_de_git_ignora_cambios_sin_integrar(tmp_path):
    repo = tmp_path / "repo"
    escribir_esc01(repo / "kb", rol_valido=True)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    rev = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    escribir_esc01(repo / "kb", martes=False, rol_valido=True)  # cambio en el disco, sin commit
    snap, _ = cargar(repo, "kb", rev)
    assert snap.revision == rev and "Martes." in snap.cuerpos["DEC-B"]
    code, out = kb(
        "consolidar",
        str(repo),
        "--carpeta",
        "kb",
        "--revision",
        rev,
        "--ids",
        "DEC-A",
        "--valido-en",
        "2026-11-03T12:00:00Z",
    )
    assert code == 0 and textos(out)[0] == "Martes." and out["revision"] == rev


def test_listos_por_cli(tmp_path):
    (tmp_path / "vacio").mkdir()
    code, out = kb(
        "listos",
        str(tmp_path / "vacio"),
        "--valido-en",
        "2026-11-03T12:00:00Z",
        "--conocido-hasta",
        "2026-11-03T12:00:00Z",
    )
    # Una carpeta sin hitos no se examinó: no es un «nada listo» correcto.
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["listos"] == [] and out["resultado"]["hitos_examinados"] == 0
    assert out["conocido_hasta"] == "2026-11-03T12:00:00Z"
    assert any("ningún hito examinado" in a for a in out["advertencias"])
