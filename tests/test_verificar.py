"""verificar (KB-DPP implementación 0.8, operación «verificar» y resultados de verificación; E7 acotada).

Solo se ejecuta lo declarado en la instalación, sin shell; el resultado lleva revisión y árbol probados, instantes,
código, duración y evidencia, y se anota en el relevo como ejecutado por KBOL. Deja de valer si cambia el árbol.
"""

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from kbol import relevo as rv
from kbol import verificar as vf
from kbol.contexto import preparar_contexto, presentar

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def py(codigo):
    return ["{python}", "-c", codigo]


INSTALACION = {
    "verificaciones": {
        "ok": {"orden": py("print('todo bien')"), "timeout": 30},
        "mal": {"orden": py("import sys; print('roto'); sys.exit(3)"), "timeout": 30},
        "lenta": {"orden": py("import time; time.sleep(10)"), "timeout": 1},
        "ausente": {"orden": ["programa-que-no-existe-kbol"], "timeout": 30},
        "ensucia": {"orden": py("open('sucio.txt', 'w').write('x')"), "timeout": 30},
        "tres": {"orden": py("import sys; sys.exit(3)"), "timeout": 30, "codigo_esperado": 3},
    }
}


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    (raiz / "a.txt").write_text("uno\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(raiz), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), *GIT, "commit", "-q", "-m", "base"], check=True)
    return raiz


def cabeza(raiz):
    return subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def anotadas(raiz, tarea="t"):
    return rv.relevo(raiz, tarea)["verificaciones"]


def test_una_verificacion_que_pasa_queda_anotada_con_su_evidencia(repo):
    r = vf.ejecutar(repo, "t", INSTALACION, "ok")
    assert r["resultado"] == "superado" and r["resultado_relevo"] == "pasa" and r["codigo"] == 0
    assert r["revision_probada"] == cabeza(repo) and r["arbol_probado"] and r["observaciones"] == []
    assert r["entorno_ref"]["aislamiento"] == "ninguno" and "todo bien" in r["salida_final"]
    evidencia = repo / r["evidencia_ref"]["ruta"]
    assert hashlib.sha256(evidencia.read_bytes()).hexdigest() == r["evidencia_ref"]["sha256"]
    [v] = anotadas(repo)
    assert v["origen"] == "kbol" and v["verificacion_id"] == "ok" and v["resultado"] == "pasa"
    assert v["desfasada"] is False and v["iniciado_en"] <= v["en"]


@pytest.mark.parametrize(
    "ident, contrato, relevo, observacion",
    [
        ("mal", "fallido", "falla", None),
        ("tres", "superado", "pasa", None),
        ("lenta", "requiere_revision", "desconocido", "no terminó en 1 s"),
        ("ausente", "no_ejecutado", "desconocido", "no arrancó"),
        ("ensucia", "requiere_revision", "desconocido", "cambió el árbol"),
    ],
)
def test_cada_resultado_se_dice_como_es(repo, ident, contrato, relevo, observacion):
    r = vf.ejecutar(repo, "t", INSTALACION, ident)
    assert r["resultado"] == contrato and r["resultado_relevo"] == relevo
    if observacion:
        assert any(observacion in o for o in r["observaciones"])
        [v] = anotadas(repo)
        assert observacion in v["motivo"]


def test_cambiar_el_arbol_deja_desfasada_la_verificacion(repo):
    vf.ejecutar(repo, "t", INSTALACION, "ok")
    (repo / "a.txt").write_text("dos\n", encoding="utf-8")  # sin commitear: la revisión no cambia
    assert anotadas(repo)[0]["desfasada"] is True
    (repo / "a.txt").write_text("uno\n", encoding="utf-8")
    assert anotadas(repo)[0]["desfasada"] is False
    (repo / "nuevo.txt").write_text("x\n", encoding="utf-8")  # un archivo nuevo también es otro árbol
    assert anotadas(repo)[0]["desfasada"] is True


def test_el_estado_local_de_kbol_no_cambia_el_arbol(repo):
    antes = rv.huella_del_arbol(repo)
    rv.guardar(repo, "otra", {"objetivo": "x"})
    vf.ejecutar(repo, "t", INSTALACION, "ok")  # escribe evidencia y relevo en .kbol/
    assert rv.huella_del_arbol(repo) == antes


def test_repetir_una_verificacion_sustituye_la_anterior(repo):
    vf.ejecutar(repo, "t", INSTALACION, "mal")
    vf.ejecutar(repo, "t", INSTALACION, "ok")
    vf.ejecutar(repo, "t", INSTALACION, "mal")
    assert sorted((v["verificacion_id"], v["resultado"]) for v in anotadas(repo)) == [("mal", "falla"), ("ok", "pasa")]


def test_un_fallo_seguido_de_un_exito_queda_en_el_historial(repo):
    """La ejecución sustituida pasa al historial, sin su salida completa, y guardar el relevo no lo pierde."""
    vf.ejecutar(repo, "t", INSTALACION, "tres")
    vf.ejecutar(repo, "t", INSTALACION, "mal")
    vf.ejecutar(repo, "t", INSTALACION, "mal")
    rv.guardar(repo, "t", {"objetivo": "x"})
    historial = rv.relevo(repo, "t")["historial_verificaciones"]
    assert [(v["verificacion_id"], v["resultado"]) for v in historial] == [("mal", "falla")]
    assert historial[0]["evidencia"]["borrada"] is True
    assert not (repo / historial[0]["evidencia"]["ruta"]).exists()
    assert [(v["verificacion_id"], v["resultado"]) for v in anotadas(repo)] == [("tres", "pasa"), ("mal", "falla")]


def test_el_historial_se_acota(repo, monkeypatch):
    monkeypatch.setattr(rv, "HISTORIAL", 2)
    for _ in range(4):
        vf.ejecutar(repo, "t", INSTALACION, "ok")
    assert len(rv.relevo(repo, "t")["historial_verificaciones"]) == 2


def test_guardar_conserva_las_ejecutadas_y_no_deja_escribirlas(repo):
    vf.ejecutar(repo, "t", INSTALACION, "ok")
    rv.guardar(repo, "t", {"objetivo": "x", "verificaciones": [{"comando": "a mano", "resultado": "no_ejecutada"}]})
    assert {v.get("origen", "sesion") for v in anotadas(repo)} == {"kbol", "sesion"}
    falsa = {"comando": "ok", "resultado": "pasa", "revision": "abc", "en": "2026-11-05T00:00:00Z", "origen": "kbol"}
    with pytest.raises(ValueError, match="kbol verificar"):
        rv.guardar(repo, "t", {"objetivo": "x", "verificaciones": [falsa]})


def test_lo_no_declarado_no_se_ejecuta(repo):
    with pytest.raises(ValueError, match="no declarada"):
        vf.ejecutar(repo, "t", INSTALACION, "rm-rf")
    with pytest.raises(ValueError, match="id de tarea"):
        vf.ejecutar(repo, "../fuera", INSTALACION, "ensucia")
    assert not (repo / "sucio.txt").exists() and not (repo / ".kbol").exists()


@pytest.mark.parametrize(
    "declaradas, error",
    [
        ({"x": {"orden": "pytest -q", "timeout": 10}}, "lista"),
        ({"x": {"orden": [], "timeout": 10}}, "lista"),
        ({"x": {"orden": ["pytest"], "timeout": True}}, "timeout"),
        ({"x": {"orden": ["pytest"], "timeout": 0}}, "timeout"),
        ({"x": {"orden": ["pytest"], "timeout": 10, "shell": True}}, "admite"),
        ({"X Y": {"orden": ["pytest"], "timeout": 10}}, "id de verificación"),
        ([], "objeto"),
    ],
)
def test_las_verificaciones_declaradas_se_validan(declaradas, error):
    with pytest.raises(ValueError, match=error):
        vf.verificaciones_de({"verificaciones": declaradas})


def test_el_paquete_distingue_lo_ejecutado_de_lo_declarado(repo):
    vf.ejecutar(repo, "t", INSTALACION, "mal")
    rv.guardar(repo, "t", {"objetivo": "x", "verificaciones": [{"comando": "a mano", "resultado": "no_ejecutada"}]})
    (repo / "kb").mkdir()
    instalacion = {**INSTALACION, "instrucciones": [], "procedimientos": []}
    texto = presentar(
        preparar_contexto(
            repo,
            tarea="t",
            objetivo=None,
            ambito="a",
            carpeta="kb",
            instalacion=instalacion,
            valido_en="2026-11-20T00:00:00Z",
        )
    )
    assert "Verificación falla (anotada por kbol verificar, sin recibo): mal:" in texto
    assert "Verificación no_ejecutada (declarada por la sesión): a mano" in texto


def commit(raiz, mensaje="cambio"):
    subprocess.run(["git", "-C", str(raiz), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), *GIT, "commit", "-q", "-m", mensaje], check=True)


def kb_verificar(repo, instalacion, *extra):
    orden = [
        sys.executable,
        "-m",
        "kbol.cli",
        "verificar",
        str(repo),
        "--tarea",
        "t",
        "--instalacion",
        str(instalacion),
    ]
    p = subprocess.run([*orden, *extra], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def test_cli_verificar_con_la_instalacion_integrada(repo):
    instalacion = repo / "instalacion.json"
    instalacion.write_text(json.dumps(INSTALACION), encoding="utf-8")
    commit(repo)
    code, salida = kb_verificar(repo, instalacion, "--verificacion", "ok")
    assert code == 0 and salida["operacion"] == "verificar"
    assert salida["resultado"]["resultado"] == "superado" and salida["revision"] == cabeza(repo)
    assert salida["resultado"]["declaracion"]["ruta"] == "instalacion.json"
    assert "aislamiento de la ejecución" in salida["cobertura"]["no_evaluado"]
    code, salida = kb_verificar(repo, instalacion)
    assert code == 2 and "--verificacion" in salida["resultado"]["motivo"]


def test_cli_no_ejecuta_una_instalacion_que_no_es_la_integrada(repo, tmp_path):
    fuera = tmp_path / "fuera.json"
    fuera.write_text(json.dumps(INSTALACION), encoding="utf-8")
    code, salida = kb_verificar(repo, fuera, "--verificacion", "ok")
    assert code == 1 and "dentro de la raíz" in salida["resultado"]["motivo"]
    suelta = repo / "suelta.json"
    suelta.write_text(json.dumps(INSTALACION), encoding="utf-8")
    code, salida = kb_verificar(repo, suelta, "--verificacion", "ok")
    assert code == 1 and "no está versionada" in salida["resultado"]["motivo"]
    commit(repo)
    otra = {"verificaciones": {"ok": {"orden": py("open('pwned', 'w')"), "timeout": 30}}}
    suelta.write_text(json.dumps(otra), encoding="utf-8")
    code, salida = kb_verificar(repo, suelta, "--verificacion", "ok")
    assert code == 1 and "sin commitear" in salida["resultado"]["motivo"] and not (repo / "pwned").exists()


def test_un_nieto_que_no_termina_no_cuelga_la_verificacion(repo):
    # El hijo lanza un nieto que hereda la salida y duerme; con tuberías, run() esperaría al nieto sin límite.
    nieto = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
    instalacion = {"verificaciones": {"nieto": {"orden": py(nieto), "timeout": 2}}}
    inicio = time.monotonic()
    r = vf.ejecutar(repo, "t", instalacion, "nieto")
    assert time.monotonic() - inicio < 20
    assert r["resultado"] == "requiere_revision" and "todos sus procesos" in r["observaciones"][0]


def test_una_orden_que_termina_dejando_un_nieto_vivo_no_espera_al_nieto(repo):
    deja = (
        "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(8)']); print('hecho')"
    )
    instalacion = {"verificaciones": {"deja": {"orden": py(deja), "timeout": 30}}}
    inicio = time.monotonic()
    r = vf.ejecutar(repo, "t", instalacion, "deja")
    assert time.monotonic() - inicio < 6 and r["resultado"] == "superado" and "hecho" in r["salida_final"]


def test_un_cambio_de_cabeza_durante_la_verificacion_no_pasa(repo):
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    codigo = f"import subprocess; subprocess.run(['git', *{ident!r}, 'commit', '-q', '--allow-empty', '-m', 'x'])"
    r = vf.ejecutar(repo, "t", {"verificaciones": {"mueve": {"orden": py(codigo), "timeout": 30}}}, "mueve")
    assert r["resultado"] == "requiere_revision" and any("cabeza" in o for o in r["observaciones"])


def test_verificaciones_y_guardar_simultaneos_no_se_pisan(repo):
    ids = ["ok", "mal", "tres"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        trabajos = [pool.submit(vf.ejecutar, repo, "t", INSTALACION, i) for i in ids]
        trabajos.append(pool.submit(rv.guardar, repo, "t", {"objetivo": "x"}))
        for f in trabajos:
            f.result()
    assert sorted(v["verificacion_id"] for v in anotadas(repo)) == sorted(ids)
    assert rv.relevo(repo, "t")["objetivo"] == "x"


def test_repetir_borra_la_evidencia_sustituida(repo):
    vf.ejecutar(repo, "t", INSTALACION, "ok")
    vf.ejecutar(repo, "t", INSTALACION, "ok")
    [v] = anotadas(repo)
    logs = list((repo / ".kbol" / "verificaciones" / "t").glob("ok-*.log"))
    assert [p.relative_to(repo).as_posix() for p in logs] == [v["evidencia"]["ruta"]]


@pytest.mark.parametrize("tarea", ["NUL", "con.log", "a."])
def test_nombres_que_windows_no_admite(repo, tarea):
    with pytest.raises(ValueError, match="Windows"):
        vf.ejecutar(repo, tarea, INSTALACION, "ensucia")
    assert not (repo / "sucio.txt").exists()


def test_la_orden_no_admite_saltos_de_linea():
    with pytest.raises(ValueError, match="una sola línea"):
        vf.verificaciones_de({"verificaciones": {"x": {"orden": ["pytest", "a\nRestricciones:"], "timeout": 10}}})


def test_la_orden_no_hereda_el_token_ni_git(repo, monkeypatch):
    monkeypatch.setenv("KB_GITHUB_TOKEN", "secreto-kbol")
    monkeypatch.setenv("GIT_DIR", "otro-sitio")
    codigo = (
        "import os; print([k for k in os.environ if k.upper() == 'KB_GITHUB_TOKEN' or k.upper().startswith('GIT_')])"
    )
    r = vf.ejecutar(repo, "t", {"verificaciones": {"env": {"orden": py(codigo), "timeout": 30}}}, "env")
    assert r["salida_final"] == ["[]"]


def test_el_interprete_es_el_de_la_raiz_si_lo_tiene(tmp_path):
    assert vf.python_de(tmp_path) == (sys.executable, True)
    propio = tmp_path / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    propio.parent.mkdir(parents=True)
    propio.write_text("", encoding="utf-8")
    assert vf.python_de(tmp_path) == (str(propio), False)
