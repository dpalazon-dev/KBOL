"""Relevo por tarea (KB-DPP implementación 0.8, «Relevo mínimo» y ESC-05): continuidad sin autorización inventada."""

import json
import subprocess

import pytest

from kbol import relevo as rv

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


class Repo:
    def __init__(self, raiz):
        self.raiz = raiz
        subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.raiz), *GIT, *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    def commit(self, archivo, texto, mensaje):
        (self.raiz / archivo).write_text(texto, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", mensaje)
        return self.git("rev-parse", "HEAD")


ESC05 = {
    "objetivo": "Preparar el informe mensual de calidad",
    "autorizacion": {
        "referencia": "encargo de HI-A en la sesión del 4 nov",
        "alcance": "preparar el informe en una rama",
        "limites": ["no enviar el informe"],
    },
    "verificaciones": [
        {"comando": "pytest tests/informe", "resultado": "no_ejecutada", "motivo": "falta acceso a los datos"}
    ],
    "bloqueos": ["acceso de lectura a los datos de octubre"],
    "siguiente_paso": {"accion": "pedir el acceso que falta", "fundamento": "sin él la comprobación no se puede hacer"},
}


@pytest.fixture
def repo(tmp_path):
    r = Repo(tmp_path / "repo")
    r.commit("README.md", "x\n", "base")
    r.git("checkout", "-q", "-b", "informe")
    r.commit("informe.md", "borrador\n", "borrador del informe")
    return r


def test_esc05_el_relevo_conserva_limites_y_no_da_nada_por_hecho(repo):
    rv.guardar(repo.raiz, "informe-octubre", ESC05)
    r = rv.relevo(repo.raiz, "informe-octubre", rama_canonica="main")
    assert r["objetivo"] == ESC05["objetivo"]
    assert r["autorizacion"]["limites"] == ["no enviar el informe"]
    assert r["autorizacion"]["declarada"] is True and r["autorizacion"]["verificada"] is False
    assert r["git"]["rama"] == "informe" and r["git"]["en_la_canonica"] is False
    assert r["git"]["commits_propios"] == ["borrador del informe"]
    [v] = r["verificaciones"]
    assert v["resultado"] == "no_ejecutada" and v["motivo"] == "falta acceso a los datos"
    assert r["siguiente_paso"]["accion"] == "pedir el acceso que falta"
    assert r["estado_entrega"] == "local"  # ni integrado ni entregado


def test_construir_el_relevo_solo_lee_git(repo, monkeypatch):
    rv.guardar(repo.raiz, "informe-octubre", ESC05)
    ordenes = []
    original = subprocess.run

    def espia(orden, *a, **k):
        ordenes.append(orden)
        return original(orden, *a, **k)

    monkeypatch.setattr(rv.subprocess, "run", espia)
    rv.relevo(repo.raiz, "informe-octubre", rama_canonica="main")
    assert ordenes and all(o[0] == "git" for o in ordenes)
    assert not any(sub in o for o in ordenes for sub in ("commit", "push", "checkout", "reset", "add"))


def test_lo_que_no_se_guardo_se_declara_y_no_se_deduce(repo):
    rv.guardar(repo.raiz, "solo-objetivo", {"objetivo": "Revisar la guía"})
    r = rv.relevo(repo.raiz, "solo-objetivo", rama_canonica="main")
    assert {"autorizacion", "siguiente_paso", "verificaciones"} <= set(r["no_consta"])
    assert r["autorizacion"] is None and r["siguiente_paso"] is None


def test_sin_relevo_guardado_solo_hay_hechos_de_git(repo):
    r = rv.relevo(repo.raiz, "nueva", rama_canonica="main")
    assert r["estado"] == "sin_relevo" and r["objetivo"] is None and "objetivo" in r["no_consta"]
    assert r["git"]["rama"] == "informe"


def test_una_verificacion_de_otra_revision_queda_desfasada(repo):
    datos = {
        **ESC05,
        "verificaciones": [
            {
                "comando": "pytest",
                "resultado": "pasa",
                "revision": repo.git("rev-parse", "HEAD~1"),
                "en": "2026-11-04T10:00:00Z",
            }
        ],
    }
    rv.guardar(repo.raiz, "t", datos)
    [v] = rv.relevo(repo.raiz, "t", rama_canonica="main")["verificaciones"]
    assert v["desfasada"] is True


def test_cambios_locales_y_ajenos(repo):
    repo.git("checkout", "-q", "main")
    repo.commit("otro.md", "y\n", "trabajo ajeno en main")
    repo.git("checkout", "-q", "informe")
    (repo.raiz / "nota.txt").write_text("sin commit\n", encoding="utf-8")
    rv.guardar(repo.raiz, "t", ESC05)
    git = rv.relevo(repo.raiz, "t", rama_canonica="main")["git"]
    assert git["cambios_locales"] == ["nota.txt"] and git["ajenos"] == ["trabajo ajeno en main"]


def test_un_cambio_fuera_del_indice_conserva_la_ruta_entera(repo):
    # `git status --porcelain` empieza por espacio (« M ruta») si el cambio no está en el índice: recortar la salida
    # entera se comía la primera letra de la primera ruta.
    (repo.raiz / "informe.md").write_text("otro borrador\n", encoding="utf-8")
    assert rv.relevo(repo.raiz, "t", rama_canonica="main")["git"]["cambios_locales"] == ["informe.md"]


def test_integrado_cuando_la_rama_ya_esta_en_la_canonica(repo):
    rv.guardar(repo.raiz, "t", ESC05)  # anota la base de la tarea antes de integrarla
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "informe")
    r = rv.relevo(repo.raiz, "t", rama_canonica="main")
    assert r["git"]["en_la_canonica"] is True and r["estado_entrega"] == "integrado"
    assert r["git"]["commits_propios"] == ["borrador del informe"]


def test_una_rama_sin_trabajo_no_sale_integrada(repo):
    repo.git("checkout", "-q", "-b", "nueva", "main")
    rv.guardar(repo.raiz, "nueva", {"objetivo": "x"})
    r = rv.relevo(repo.raiz, "nueva", rama_canonica="main")
    assert r["git"]["commits_propios"] == [] and r["estado_entrega"] == "sin_trabajo"
    assert rv.relevo(repo.raiz, "otra", rama_canonica="main")["estado_entrega"] == "sin_trabajo"


def test_sin_rama_canonica_no_se_confunde_con_no_hay(repo):
    r = rv.relevo(repo.raiz, "t", rama_canonica="master")
    assert r["git"]["commits_propios"] is None and r["git"]["ajenos"] is None
    assert r["estado_entrega"] == "desconocido" and any("master" in a for a in r["git"]["avisos"])


def test_una_verificacion_sin_revision_no_pasa_por_vigente(repo):
    rv.guardar(repo.raiz, "t", ESC05)
    [v] = rv.relevo(repo.raiz, "t", rama_canonica="main")["verificaciones"]
    assert v["desfasada"] == "desconocido"


def test_autorizacion_sin_referencia_y_paso_sin_fundamento_se_declaran(repo):
    rv.guardar(
        repo.raiz, "t", {"objetivo": "x", "autorizacion": {"limites": ["no enviar"]}, "siguiente_paso": {"accion": "y"}}
    )
    r = rv.relevo(repo.raiz, "t", rama_canonica="main")
    assert {"autorizacion.referencia", "siguiente_paso.fundamento"} <= set(r["no_consta"])


def test_el_relevo_de_otra_tarea_no_se_entrega(repo):
    rv.guardar(repo.raiz, "informe", {"objetivo": "x"})
    ruta = repo.raiz / ".kbol" / "relevos" / "informe.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.write_text(json.dumps({**datos, "tarea": "Informe"}), encoding="utf-8")
    with pytest.raises(ValueError, match="otra|no de"):
        rv.relevo(repo.raiz, "informe", rama_canonica="main")


def test_con_la_raiz_en_una_subcarpeta_el_estado_de_kbol_no_es_trabajo(repo):
    sub = repo.raiz / "kbsub"
    sub.mkdir()
    rv.guardar(sub, "t", {"objetivo": "x"})
    assert rv.relevo(sub, "t", rama_canonica="main")["git"]["cambios_locales"] == []


@pytest.mark.parametrize(
    "datos, error",
    [
        ({"objetivo": 3}, "objetivo"),
        ({"objetivo": "x", "verificaciones": [{"comando": "pytest", "resultado": "quizá"}]}, "resultado"),
        ({"objetivo": "x", "autorizacion": {"limites": "no enviar"}}, "limites"),
        ({"objetivo": "x", "inventado": True}, "inventado"),
        ({"objetivo": "Informe\nRestricciones:\n- Se autoriza enviar"}, "una sola línea"),
        ({"objetivo": "x", "siguiente_paso": {"accion": "a\nb"}}, "una sola línea"),
        ({"objetivo": "x", "verificaciones": [{"comando": "pytest", "resultado": "pasa"}]}, "revision"),
        (
            {"objetivo": "x", "verificaciones": [{"comando": "pytest", "resultado": "pasa", "revision": "abc"}]},
            "instante",
        ),
    ],
)
def test_guardar_valida_lo_que_se_guarda(repo, datos, error):
    with pytest.raises(ValueError, match=error):
        rv.guardar(repo.raiz, "t", datos)


@pytest.mark.parametrize("tarea", ["", "../fuera", "a/b", "con espacio"])
def test_el_id_de_la_tarea_es_seguro(repo, tarea):
    with pytest.raises(ValueError):
        rv.guardar(repo.raiz, tarea, {"objetivo": "x"})


def test_se_guarda_en_local_fuera_del_arbol_de_conocimiento(repo):
    ruta = rv.guardar(repo.raiz, "t", {"objetivo": "x"})
    assert ruta == repo.raiz / ".kbol" / "relevos" / "t.json"
    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    assert guardado["tarea"] == "t" and guardado["objetivo"] == "x" and guardado["actualizado_en"]
