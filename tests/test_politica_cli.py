"""Política de la CLI: una operación que no examina nada no termina `completado`.

Dos niveles: una tabla que obliga a que toda operación habilitada diga qué devuelve ante una entrada vacía, y pruebas
puntuales de cada caso que la decisión nombra.
"""

# ruff: noqa: F811  (los fixtures se importan de otros módulos de tests)

import json
import subprocess
import sys

import pytest
from conftest import decision, evento, registro
from test_cli_impacto import kb as kb_impacto
from test_cli_impacto import repo_con_consumidor
from test_declarada import entorno  # noqa: F401
from test_huellas import integrar_pregunta
from test_verificar import INSTALACION, commit, kb_verificar, repo  # noqa: F401

from kbol import cli
from kbol.core import serializar

T = "2026-11-03T12:00:00Z"
GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


@pytest.fixture
def vacio(tmp_path):
    """Repositorio con un commit y una carpeta `kb` sin registros: nada que examinar."""
    raiz = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    (raiz / "a.txt").write_text("uno\n", encoding="utf-8")
    (raiz / "kb").mkdir()
    (raiz / "kb" / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(raiz), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), *GIT, "commit", "-q", "-m", "base"], check=True)
    return raiz


# Operación -> (argumentos sobre la raíz vacía, estado natural de una entrada vacía). Una operación nueva en
# HABILITADAS no pasa sin su fila: lo que importa es que lo vacío nunca se lea como éxito.
def _tabla(r):
    kb_ = str(r / "kb")
    consulta = [str(r), "--carpeta", "kb", "--valido-en", T]
    return {
        "validar": (["validar", kb_], "fallido"),
        "migrar": (["migrar", kb_, "--revision", "HEAD"], "parcial"),
        "digest": (["digest", kb_], "fallido"),
        "consolidar": (["consolidar", *consulta, "--ids", "DEC-X"], "parcial"),
        "listos": (["listos", *consulta], "parcial"),
        "impacto": (["impacto", str(r), "--carpeta", "kb", "--base", "HEAD"], "parcial"),
        "relevo": (["relevo", str(r)], "bloqueado"),
        "preparar_contexto": (["preparar_contexto", str(r)], "bloqueado"),
        "verificar": (["verificar", str(r)], "bloqueado"),
        "consultar": (["consultar", *consulta, "--ids", "DEC-X"], "parcial"),
        "buscar": (["buscar", *consulta, "--consulta", "nada"], "parcial"),
        "integrar": (["integrar", str(r)], "bloqueado"),
        "arranque": (["arranque", str(r)], "bloqueado"),
        "desvios": (["desvios", str(r), "--carpeta", "kb"], "parcial"),
        "citas": (["citas", str(r), "--carpeta", "kb"], "parcial"),
        "enlaces": (["enlaces", str(r)], "parcial"),
        "integridad": (["integridad", str(r), "--carpeta", "kb"], "parcial"),
        "soporte": (["soporte", *consulta], "parcial"),
        "preparar_aprobacion": (["preparar_aprobacion", str(r)], "bloqueado"),
        "vocabulario": (["vocabulario", *consulta], "parcial"),
        "sesion": (["sesion", str(r)], "bloqueado"),
        "proponer": (["proponer", str(r)], "bloqueado"),
        "exportar_skills": (["exportar_skills", str(r / "skills"), "--skills"], "bloqueado"),
    }


def test_la_tabla_cubre_exactamente_las_operaciones_habilitadas(vacio):
    assert set(_tabla(vacio)) == set(cli.HABILITADAS)


@pytest.mark.parametrize("op", cli.HABILITADAS)
def test_una_entrada_vacia_nunca_es_completado(vacio, op):
    args, esperado = _tabla(vacio)[op]
    code, out = kb(*args)
    assert out["resultado"]["estado"] == esperado, out
    assert out["resultado"]["estado"] != "completado" and code != 0
    assert code == {"fallido": 1, "bloqueado": 2, "parcial": 3}[esperado]


def escribir(carpeta, nombre, r, c=""):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{nombre}.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")


def test_consolidar_con_un_id_ausente_es_parcial(tmp_path):
    creacion = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")
    escribir(tmp_path / "kb", "ROL", registro("rol", eventos=[creacion]))
    escribir(tmp_path / "kb", "DEC-A", *decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z"))
    base = ["consolidar", str(tmp_path), "--carpeta", "kb", "--valido-en", T]
    code, out = kb(*base, "--ids", "DEC-A")
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    code, out = kb(*base, "--ids", "DEC-A", "DEC-NO")
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["ausentes"] == ["DEC-NO"]
    assert any("DEC-NO" in a for a in out["advertencias"])


def test_citas_sobre_una_carpeta_que_no_existe_es_fallido(tmp_path):
    code, out = kb("citas", str(tmp_path), "--carpeta", "no-existe")
    assert code == 1 and out["resultado"]["estado"] == "fallido", out
    assert out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"


def test_citas_sobre_una_carpeta_vacia_es_parcial_con_el_motivo(tmp_path):
    (tmp_path / "kb").mkdir()
    code, out = kb("citas", str(tmp_path), "--carpeta", "kb")
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["filas"] == [] and any("ninguna cita" in a for a in out["advertencias"])


def test_citas_busca_en_las_subcarpetas(tmp_path):
    sub = tmp_path / "kb" / "sub" / "mas"
    sub.mkdir(parents=True)
    (sub / "DEC-1.md").write_text("---\nid: DEC-1\nsources:\n- id: s1\n  resource: F-nada\n---\n", encoding="utf-8")
    code, out = kb("citas", str(tmp_path), "--carpeta", "kb")
    assert [f["registro"] for f in out["resultado"]["filas"]] == ["DEC-1"], out
    assert out["resultado"]["filas"][0]["estado"] == "rota" and code == 3


def test_desvios_sin_registros_comprobados_es_parcial_y_declara_la_cobertura(vacio):
    code, out = kb("desvios", str(vacio), "--carpeta", "kb")
    assert code == 3 and out["resultado"]["estado"] == "parcial" and out["resultado"]["comprobados"] == 0, out
    assert any("ningún registro" in a for a in out["advertencias"])
    assert out["cobertura"]["registros_leidos"] == 0 and "truncado" in out["cobertura"]


def test_desvios_con_desvios_avisa_y_sigue_en_cero(entorno):
    repo_, base, recibos = entorno
    integrar_pregunta(repo_, base, recibos)
    repo_.git("checkout", "-q", "canon")
    ruta = repo_.raiz / "kb" / "Q-N.md"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("Texto.", "Otro."), encoding="utf-8")
    code, out = kb("desvios", str(repo_.raiz), "--carpeta", "kb", "--rama-canonica", "canon")
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    assert out["resultado"]["comprobados"] > 0 and out["resultado"]["avisos"] and out["advertencias"]
    assert out["cobertura"]["registros_leidos"] > 0


def test_desvios_con_un_registro_ilegible_es_parcial(entorno):
    """El estado no contradice a la cobertura: lo que no se pudo leer podía tener un desvío."""
    repo_, base, recibos = entorno
    integrar_pregunta(repo_, base, recibos)
    repo_.git("checkout", "-q", "canon")
    (repo_.raiz / "kb" / "roto.md").write_text("---\nid: [sin cerrar\n---\n", encoding="utf-8")
    code, out = kb("desvios", str(repo_.raiz), "--carpeta", "kb", "--rama-canonica", "canon")
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["comprobados"] > 0 and out["cobertura"]["truncado"] is True


def test_migrar_una_carpeta_sin_registros_heredados_es_parcial(tmp_path):
    """Un archivo fuera de alcance no es un registro examinado."""
    carpeta = tmp_path / "docs"
    carpeta.mkdir()
    (carpeta / "README.md").write_text("# Notas\n", encoding="utf-8")
    code, out = kb("migrar", str(carpeta), "--revision", "r1")
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["resumen"]["total"] == 1 and out["resultado"]["resumen"]["propuestos"] == 0


def test_impacto_sin_cambios_sigue_completado(tmp_path):
    repo_, _, final = repo_con_consumidor(tmp_path)
    code, out = kb_impacto("impacto", str(repo_), "--carpeta", "kb", "--base", final, "--revision", final)
    assert code == 0 and out["resultado"]["estado"] == "completado", out
    assert out["resultado"]["cambiados"] == [] and out["cobertura"]["registros_leidos"] > 0


def test_verificar_que_falla_es_fallido(repo):
    instalacion = repo / "instalacion.json"
    instalacion.write_text(json.dumps(INSTALACION), encoding="utf-8")
    commit(repo)
    code, out = kb_verificar(repo, instalacion, "--verificacion", "mal")
    assert code == 1 and out["resultado"]["estado"] == "fallido", out
    assert out["resultado"]["resultado"] == "fallido" and isinstance(out["resultado"]["codigo"], int)
    assert out["resultado"]["codigo"] != 0 and "falló" in out["resultado"]["motivo"]


@pytest.mark.parametrize("ident", ["ausente", "lenta"])
def test_verificar_desconocido_o_no_ejecutado_es_parcial(repo, ident):
    instalacion = repo / "instalacion.json"
    instalacion.write_text(json.dumps(INSTALACION), encoding="utf-8")
    commit(repo)
    code, out = kb_verificar(repo, instalacion, "--verificacion", ident)
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["resultado"] in ("no_ejecutado", "requiere_revision")
    assert any("la verificación" in a for a in out["advertencias"])


def test_verificar_que_pasa_sigue_completado(repo):
    instalacion = repo / "instalacion.json"
    instalacion.write_text(json.dumps(INSTALACION), encoding="utf-8")
    commit(repo)
    code, out = kb_verificar(repo, instalacion, "--verificacion", "ok")
    assert code == 0 and out["resultado"]["estado"] == "completado", out


@pytest.mark.parametrize("op", ["validar", "digest"])
def test_validar_y_digest_sobre_una_carpeta_son_fallidos_con_sobre(tmp_path, op):
    code, out = kb(op, str(tmp_path))
    assert code == 1 and out["operacion"] == op and out["resultado"]["estado"] == "fallido", out
    assert out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"


def test_preparar_contexto_con_un_ambito_sin_registros_es_parcial(vacio, tmp_path):
    instalacion = tmp_path / "instalacion.json"
    instalacion.write_text(json.dumps({"proyecto": "p", "instrucciones": [], "procedimientos": []}), encoding="utf-8")
    code, out = kb(
        "preparar_contexto",
        str(vacio),
        "--carpeta",
        "kb",
        "--tarea",
        "t",
        "--ambito",
        "nada",
        "--instalacion",
        str(instalacion),
        "--valido-en",
        T,
    )
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert "ningún registro en el ámbito" in out["resultado"]["motivo"]


def test_migrar_una_carpeta_sin_registros_es_parcial(tmp_path):
    (tmp_path / "vieja").mkdir()
    code, out = kb("migrar", str(tmp_path / "vieja"), "--revision", "r")
    assert code == 3 and out["resultado"]["estado"] == "parcial", out
    assert out["resultado"]["resumen"]["total"] == 0 and out["advertencias"]
