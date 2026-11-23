"""Integración y arranque desde la CLI, con aprobación declarada.

La CLI no sube nada: con --remoto trae el remoto y exige que la base y la rama local estén al día con él, para que el
push posterior, que hace una persona, no se rechace. Sin las entradas obligatorias o con un mecanismo que la CLI no
integra, falla cerrada.
"""

import json
import subprocess
import sys

import pytest
from conftest import CUERPO_DECISION, registro
from test_arranque_declarado import declaracion
from test_arranque_declarado import raiz as raiz  # noqa: F401 (fixture)
from test_declarada import aceptacion, declarada
from test_declarada import entorno as entorno  # noqa: F401 (fixture)
from test_integrar import ACEPTAR, proponer, solicitud

from kbol.core import serializar
from kbol.declarada import MECANISMO
from kbol.digest import digest


def kbol(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def json_en(tmp_path, nombre, datos):
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return str(ruta)


def integrar_cli(repo, base, prop, recibos, aprobaciones, tmp_path, *extra):
    return kbol(
        "integrar",
        str(repo.raiz),
        "--rama-canonica",
        "canon",
        "--carpeta",
        "kb",
        "--operacion-id",
        "op-1",
        "--base",
        base,
        "--propuesta",
        prop,
        "--aprobaciones",
        json_en(tmp_path, "aprobaciones.json", aprobaciones),
        "--recibos",
        str(recibos),
        *extra,
    )


def test_integra_con_una_aprobacion_declarada(entorno, tmp_path):  # noqa: F811
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    codigo, salida = integrar_cli(repo, base, prop, recibos, [declarada(base)], tmp_path)
    assert codigo == 0, salida
    assert salida["operacion"] == "integrar" and salida["resultado"]["estado"] == "integrado"
    assert repo.git("rev-parse", "canon") == salida["resultado"]["revision_integrada"]


def test_un_rechazo_sale_bloqueado(entorno, tmp_path):  # noqa: F811
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    codigo, salida = integrar_cli(repo, base, prop, recibos, [declarada(base, digests={"DEC-X": "0" * 64})], tmp_path)
    assert codigo == 2 and salida["resultado"]["codigo"] == "APROBACION_CADUCADA"


@pytest.mark.parametrize("aprobaciones", [[], [{"mecanismo": "github-review", "pull": 1, "review_id": 1}], {"a": 1}])
def test_sin_aprobaciones_declaradas_no_integra(entorno, tmp_path, aprobaciones):  # noqa: F811
    repo, base, recibos = entorno
    prop = aceptacion(repo, base)
    codigo, salida = integrar_cli(repo, base, prop, recibos, aprobaciones, tmp_path)
    assert codigo == 2 and salida["resultado"]["estado"] == "bloqueado"
    assert repo.git("rev-parse", "canon") == base


def test_faltan_entradas(entorno):  # noqa: F811
    repo, _, _ = entorno
    codigo, salida = kbol("integrar", str(repo.raiz), "--rama-canonica", "canon")
    assert codigo == 2 and "necesita" in salida["resultado"]["motivo"]


def remoto_de(repo, tmp_path):
    remoto = tmp_path / "remoto.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remoto)], check=True)
    repo.git("remote", "add", "origin", str(remoto))
    repo.git("push", "-q", "origin", "canon")
    return remoto


def test_con_remoto_al_dia_integra(entorno, tmp_path):  # noqa: F811
    repo, base, recibos = entorno
    remoto_de(repo, tmp_path)
    prop = aceptacion(repo, base)
    codigo, salida = integrar_cli(repo, base, prop, recibos, [declarada(base)], tmp_path, "--remoto", "origin")
    assert codigo == 0, salida


def test_si_el_remoto_avanzo_no_integra(entorno, tmp_path):  # noqa: F811
    repo, base, recibos = entorno
    remoto = remoto_de(repo, tmp_path)
    otro = tmp_path / "otro"
    subprocess.run(["git", "clone", "-q", "-b", "canon", str(remoto), str(otro)], check=True)
    (otro / "README.md").write_text("otra\n", encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "-C", str(otro), *ident, "commit", "-q", "-am", "otra"], check=True)
    subprocess.run(["git", "-C", str(otro), "push", "-q", "origin", "canon"], check=True)
    prop = aceptacion(repo, base)
    codigo, salida = integrar_cli(repo, base, prop, recibos, [declarada(base)], tmp_path, "--remoto", "origin")
    assert codigo == 2 and salida["resultado"]["codigo"] == "BASE_CAMBIADA", salida
    assert repo.git("rev-parse", "canon") == base


def test_arranque_declarado_desde_la_cli(raiz, tmp_path):  # noqa: F811
    repo, base, recibos = raiz
    args = ["arranque", str(repo.raiz), "--rama-canonica", "canon", "--carpeta", "kb", "--operacion-id", "arranque-1"]
    args += ["--base", base, "--persona", "PER-D", "--roles", "ROL-RAIZ", "--recibos", str(recibos)]
    codigo, salida = kbol(*args, "--declaracion", json_en(tmp_path, "declaracion.json", declaracion()))
    assert codigo == 0, salida
    assert salida["resultado"]["estado"] == "arrancado"
    otra_vez = kbol(*args[:7], "arranque-2", *args[8:], "--declaracion", json_en(tmp_path, "d2.json", declaracion()))
    assert otra_vez[0] == 2


def test_tras_el_arranque_la_cli_integra_con_la_raiz(raiz, tmp_path):  # noqa: F811
    repo, base, recibos = raiz
    args = ["arranque", str(repo.raiz), "--rama-canonica", "canon", "--carpeta", "kb", "--operacion-id", "arranque-1"]
    args += ["--base", base, "--persona", "PER-D", "--roles", "ROL-RAIZ", "--recibos", str(recibos)]
    _, arranque = kbol(*args, "--declaracion", json_en(tmp_path, "declaracion.json", declaracion()))
    canon = arranque["resultado"]["revision_integrada"]
    r = registro("decision", id="DEC-X", autorizado_por=["ROL-RAIZ"])
    prop = proponer(
        repo, canon, {"kb/DEC-X.md": serializar(r, CUERPO_DECISION), **solicitud("op-1", {"DEC-X": ACEPTAR})}
    )
    aprobacion = {
        "mecanismo": MECANISMO,
        "identidad": "declarada:d",
        "sesion": "s",
        "instante": arranque["resultado"]["registrado_en"],
        "cita": "Acepto DEC-X",
        "base_mostrada": canon,
        "digests": {"DEC-X": digest(r, CUERPO_DECISION, ACEPTAR)},
    }
    codigo, salida = integrar_cli(repo, canon, prop, recibos, [aprobacion], tmp_path)
    assert codigo == 0, salida
