"""`kbol proponer`: del árbol de trabajo a la rama canónica, por el clon del integrador y sin saltarse la puerta.

El remoto es un repositorio `--bare` local y el estado de la instalación (`KBOL_ESTADO`) una carpeta temporal: nada
sale de la máquina. Lo que importa: el ensayo no cambia nada; la aprobación la da quien la recoge, con los digests del
paquete, y caduca si el contenido cambia; lo integrado y sin subir no se pierde, y los pasos posteriores solo escriben
vistas.
"""

import copy
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from conftest import CUERPO_DECISION, decision, registro
from test_integrar import Repo, activo, canonico

from kbol.core import parse, serializar
from kbol.proponer import es_vista, integracion_de, proponer

INSTANTE = "2026-11-05T18:00:00Z"
# Sin estado_anterior: la puerta lo rellena antes del digest, y lo que se aprueba tiene que salir de su mismo código.
ACEPTAR = {"DEC-X": [{"estado_nuevo": "aceptada", "valido_desde": "2026-11-05T00:00:00Z"}]}
AGENTE = "claude-code/opus-5.5"
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def py(codigo):
    return {"orden": ["{python}", "-c", codigo], "timeout": 60}


ESCRIBE_INDICE = py("import pathlib; pathlib.Path('kb/index.md').write_bytes(b'indice\\n')")


def git_en(ruta, *args):
    p = subprocess.run(["git", "-C", str(ruta), *IDENT, *args], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """Una instalación con su remoto: persona con rol, una decisión aceptada y la configuración en la rama."""
    monkeypatch.setenv("KBOL_ESTADO", str(tmp_path / "estado"))
    remoto = tmp_path / "remoto.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remoto)], check=True)
    repo = Repo(tmp_path / "repo")
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    per = activo(
        "persona",
        "PER-H",
        naturaleza="humana",
        identidad_ref="declarada:h",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    a, ca = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-10-03T00:00:00Z", autorizado_por=["ROL-OP"])
    for ident, r, c in (("ROL-OP", rol, ""), ("PER-H", per, ""), ("DEC-A", a, ca)):
        repo.escribir(f"kb/{ident}.md", canonico(r, c))
    instalacion = {
        "rama_canonica": "main",
        "carpeta_registros": "kb",
        "integracion": {"remoto": remoto.as_posix(), "repositorio": "prueba"},
    }
    repo.escribir("instalacion.json", json.dumps(instalacion))
    base = repo.commit("base")
    repo.git("remote", "add", "origin", str(remoto))
    repo.git("push", "-q", "origin", "main")
    clon = tmp_path / "estado" / "prueba" / "integrador.git"
    return SimpleNamespace(repo=repo, remoto=remoto, base=base, instalacion=instalacion, clon=clon, tmp=tmp_path)


def con(inst, verificaciones=None, **integracion):
    instalacion = copy.deepcopy(inst.instalacion)
    instalacion["integracion"].update(integracion)
    if verificaciones:
        instalacion["verificaciones"] = verificaciones
    return instalacion


def decision_nueva(inst):
    r = registro("decision", id="DEC-X", autorizado_por=["ROL-OP"])
    inst.repo.escribir("kb/DEC-X.md", serializar(r, CUERPO_DECISION))
    return ["kb/DEC-X.md"]


def pregunta_nueva(inst, ident="Q-N"):
    r = registro("pregunta", id=ident, responsable="ROL-OP")
    inst.repo.escribir(f"kb/{ident}.md", serializar(r, "Texto.\n"))
    return [f"kb/{ident}.md"]


def firmar(paquete):
    """Lo que aporta quien recoge la aprobación; los digests y la base mostrada vienen del paquete."""
    return [
        {**e, "identidad": "declarada:h", "sesion": "sesión de prueba", "instante": INSTANTE, "cita": "Sí, acepto DEC-X"}
        for e in paquete["aprobaciones"]
    ]


def aceptar(inst, instalacion=None, **kw):
    return proponer(
        inst.repo.raiz,
        instalacion or inst.instalacion,
        operacion_id="op-1",
        archivos=decision_nueva(inst),
        efectos=ACEPTAR,
        **kw,
    )


def en_el_remoto(inst):
    return git_en(inst.remoto, "rev-parse", "main")


def otro_empuja(inst):
    """Alguien más sube un commit a la rama canónica del remoto."""
    otro = inst.tmp / "otro"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(inst.remoto), str(otro)], check=True)
    (otro / "README.md").write_text("otra\n", encoding="utf-8")
    git_en(otro, "add", "-A")
    git_en(otro, "commit", "-q", "-m", "otra")
    git_en(otro, "push", "-q", "origin", "main")
    return git_en(otro, "rev-parse", "HEAD")


def test_el_ensayo_sin_aprobacion_devuelve_el_paquete_y_no_cambia_nada(inst):
    res = aceptar(inst)
    assert res["estado"] == "pendiente_de_aprobacion" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res
    paquete = res["paquete"]
    assert [r["id"] for r in paquete["registros"]] == ["DEC-X"]
    esqueleto = paquete["aprobaciones"][0]
    assert esqueleto["base_mostrada"] == inst.base and set(esqueleto["digests"]) == {"DEC-X"}
    assert all(esqueleto[k] is None for k in ("identidad", "sesion", "instante", "cita"))
    assert en_el_remoto(inst) == inst.base and git_en(inst.clon, "rev-parse", "main") == inst.base
    assert git_en(inst.clon, "for-each-ref", "--format=%(refname)", "refs/heads/") == "refs/heads/main"
    assert not (inst.clon.parent / "recibos").exists()


def test_el_paquete_firmado_integra_sube_y_deja_la_cita_y_el_recibo(inst):
    paquete = aceptar(inst)["paquete"]
    ensayo = aceptar(inst, aprobaciones=firmar(paquete))
    assert ensayo["estado"] == "ensayado" and ensayo["decisivos"] == ["DEC-X"], ensayo
    assert en_el_remoto(inst) == inst.base
    res = aceptar(inst, aprobaciones=firmar(paquete), hasta="subir")
    assert res["estado"] == "subido" and res["subido"] and res["pendientes_de_subir"] == 0, res
    assert en_el_remoto(inst) == res["revision_integrada"] == git_en(inst.clon, "rev-parse", "main")
    meta, _ = parse(git_en(inst.remoto, "show", "main:kb/DEC-X.md") + "\n")
    assert meta["estado"] == "aceptada"
    ratificacion = next(e for e in meta["eventos"] if e["tipo_evento"] == "ratificacion")
    assert ratificacion["aprobacion"]["comprobante"]["cita"] == "Sí, acepto DEC-X"
    recibo = json.loads((inst.clon.parent / "recibos" / "op-1.json").read_text(encoding="utf-8"))
    assert recibo["revision_integrada"] == res["revision_integrada"]
    assert recibo["aprobaciones_detalle"][0]["comprobante"]["digests"] == paquete["aprobaciones"][0]["digests"]


def test_si_el_contenido_cambia_tras_mostrarlo_la_aprobacion_caduca(inst):
    aprobaciones = firmar(aceptar(inst)["paquete"])
    r = registro("decision", id="DEC-X", autorizado_por=["ROL-OP"], justificacion="Otra cosa.")
    inst.repo.escribir("kb/DEC-X.md", serializar(r, CUERPO_DECISION))
    res = proponer(
        inst.repo.raiz,
        inst.instalacion,
        operacion_id="op-1",
        archivos=["kb/DEC-X.md"],
        efectos=ACEPTAR,
        aprobaciones=aprobaciones,
        hasta="subir",
    )
    assert res["estado"] == "bloqueado" and res["codigo"] == "APROBACION_CADUCADA", res
    assert en_el_remoto(inst) == inst.base and git_en(inst.clon, "rev-parse", "main") == inst.base


@pytest.mark.parametrize("modo", ["toda", "decisiva"])
def test_sin_aprobacion_lo_decisivo_no_se_integra_ni_se_sube(inst, modo):
    res = aceptar(inst, con(inst, aprobacion=modo), actor=AGENTE, hasta="subir")
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE", res
    assert en_el_remoto(inst) == inst.base and git_en(inst.clon, "rev-parse", "main") == inst.base


@pytest.mark.parametrize("aprobaciones", [[{"mecanismo": "github-review", "pull": 1, "review_id": 1}], {"a": 1}])
def test_solo_admite_aprobaciones_declaradas(inst, aprobaciones):
    res = aceptar(inst, aprobaciones=aprobaciones, hasta="subir")
    assert res["estado"] == "bloqueado" and "declaradas" in res["motivo"]
    assert not inst.clon.exists()


def test_en_modo_decisiva_lo_no_decisivo_se_ensaya_entero_con_el_actor(inst):
    instalacion = con(inst, aprobacion="decisiva")
    archivos = pregunta_nueva(inst)
    res = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE)
    assert res["estado"] == "ensayado" and res["decisivos"] == [] and res["registros"] == ["Q-N"], res
    assert git_en(inst.clon, "rev-parse", "main") == inst.base
    sin_actor = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos)
    assert sin_actor["estado"] == "bloqueado" and "actor" in sin_actor["motivo"]


def test_lo_integrado_sin_subir_no_se_pierde_y_sube_con_la_siguiente(inst):
    instalacion = con(inst, aprobacion="decisiva")
    uno = proponer(
        inst.repo.raiz, instalacion, operacion_id="op-1", archivos=pregunta_nueva(inst), actor=AGENTE, hasta="integrar"
    )
    assert uno["estado"] == "integrado" and not uno["subido"] and uno["pendientes_de_subir"] == 1, uno
    assert en_el_remoto(inst) == inst.base
    dos = proponer(
        inst.repo.raiz,
        instalacion,
        operacion_id="op-2",
        archivos=pregunta_nueva(inst, "Q-M"),
        actor=AGENTE,
        hasta="subir",
    )
    assert dos["estado"] == "subido" and dos["base"] == uno["revision_integrada"], dos
    assert en_el_remoto(inst) == dos["revision_integrada"]
    assert git_en(inst.remoto, "show", "main:kb/Q-N.md") and git_en(inst.remoto, "show", "main:kb/Q-M.md")


def test_si_el_remoto_avanza_se_propone_sobre_su_cabeza(inst):
    aceptar(inst)
    nueva = otro_empuja(inst)
    res = aceptar(inst)
    assert res["base"] == nueva and res["paquete"]["aprobaciones"][0]["base_mostrada"] == nueva


def test_si_el_clon_y_el_remoto_divergen_bloquea_sin_descartar_nada(inst):
    instalacion = con(inst, aprobacion="decisiva")
    uno = proponer(
        inst.repo.raiz, instalacion, operacion_id="op-1", archivos=pregunta_nueva(inst), actor=AGENTE, hasta="integrar"
    )
    otro_empuja(inst)
    dos = proponer(
        inst.repo.raiz, instalacion, operacion_id="op-2", archivos=pregunta_nueva(inst, "Q-M"), actor=AGENTE
    )
    assert dos["estado"] == "bloqueado" and dos["codigo"] == "BASE_CAMBIADA", dos
    assert git_en(inst.clon, "rev-parse", "main") == uno["revision_integrada"]


def test_si_el_remoto_rechaza_la_subida_lo_dice_y_queda_pendiente(inst):
    instalacion = con(inst, aprobacion="decisiva")
    proponer(inst.repo.raiz, instalacion, operacion_id="op-0", archivos=pregunta_nueva(inst, "Q-0"), actor=AGENTE)
    rechazo = inst.remoto / "hooks" / "pre-receive"
    rechazo.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
    rechazo.chmod(0o755)
    res = proponer(
        inst.repo.raiz, instalacion, operacion_id="op-1", archivos=pregunta_nueva(inst), actor=AGENTE, hasta="subir"
    )
    assert res["estado"] == "bloqueado" and res["codigo"] == "RESULTADO_DESCONOCIDO" and not res["subido"], res
    assert res["pendientes_de_subir"] == 1 and en_el_remoto(inst) == inst.base
    assert git_en(inst.clon, "rev-parse", "main") == res["revision_integrada"]


def test_no_usa_el_clon_de_otro_remoto(inst):
    aceptar(inst)
    otro = inst.tmp / "otro.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(inst.remoto), str(otro)], check=True)
    res = aceptar(inst, con(inst, remoto=otro.as_posix()))
    assert res["estado"] == "bloqueado" and "no es un clon" in res["motivo"]


def test_los_pasos_posteriores_escriben_las_vistas_en_un_commit_propio_antes_de_subir(inst):
    verificaciones = {
        "indices": ESCRIBE_INDICE,
        # El segundo paso ve como rastreado lo que generó el primero.
        "comprobador": {"orden": ["git", "ls-files", "--error-unmatch", "kb/index.md"], "timeout": 60},
    }
    instalacion = con(
        inst,
        verificaciones,
        aprobacion="decisiva",
        despues_de_integrar=["indices", "comprobador"],
        vistas=["kb/**/index.md"],
        autor={"nombre": "operador", "correo": "operador@localhost"},
    )
    archivos = pregunta_nueva(inst)
    ensayo = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE)
    assert ensayo["estado"] == "ensayado" and ensayo["vistas"] == ["kb/index.md"], ensayo
    assert [p["resultado"] for p in ensayo["despues"]] == ["superado", "superado"]
    assert en_el_remoto(inst) == inst.base and git_en(inst.clon, "rev-parse", "main") == inst.base
    res = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="subir")
    assert res["estado"] == "subido" and res["vistas"] == ["kb/index.md"], res
    assert en_el_remoto(inst) == res["cabeza"] != res["revision_integrada"]
    assert git_en(inst.remoto, "rev-parse", "main^") == res["revision_integrada"]
    assert git_en(inst.remoto, "show", "main:kb/index.md") == "indice"
    assert git_en(inst.remoto, "log", "-1", "--format=%an <%ce> %s", "main") == (
        "operador <operador@localhost> kb: vistas tras op-1"
    )
    assert git_en(inst.remoto, "diff", "--name-only", "main^", "main") == "kb/index.md"


@pytest.mark.parametrize("hasta", ["ensayo", "subir"])
def test_un_paso_posterior_que_falla_impide_subir(inst, hasta):
    verificaciones = {"comprobador": py("import sys; print('roto'); sys.exit(3)")}
    instalacion = con(inst, verificaciones, aprobacion="decisiva", despues_de_integrar=["comprobador"])
    res = proponer(
        inst.repo.raiz, instalacion, operacion_id="op-1", archivos=pregunta_nueva(inst), actor=AGENTE, hasta=hasta
    )
    assert res["estado"] == "bloqueado" and "comprobador no pasa" in res["motivo"], res
    assert res["despues"][0]["codigo"] == 3 and res["despues"][0]["salida_final"] == ["roto"]
    assert en_el_remoto(inst) == inst.base and not res["subido"]
    # El ensayo no deja nada; fuera de él, lo integrado queda en el clon y se dice.
    integrado = git_en(inst.clon, "rev-parse", "main") != inst.base
    assert integrado == (hasta == "subir") and res["pendientes_de_subir"] == int(integrado)


@pytest.mark.parametrize(
    "codigo",
    [
        "import pathlib; pathlib.Path('README.md').write_bytes(b'otra cosa')",
        "import pathlib; pathlib.Path('kb/DEC-A.md').write_bytes(b'otra cosa')",
        "import pathlib; pathlib.Path('kb/_huellas.json').write_bytes(b'{}')",
    ],
)
def test_un_paso_posterior_solo_puede_cambiar_vistas(inst, codigo):
    instalacion = con(
        inst, {"paso": py(codigo)}, aprobacion="decisiva", despues_de_integrar=["paso"], vistas=["kb/**", "docs/**"]
    )
    res = proponer(
        inst.repo.raiz, instalacion, operacion_id="op-1", archivos=pregunta_nueva(inst), actor=AGENTE, hasta="subir"
    )
    assert res["estado"] == "bloqueado" and "no es una vista declarada" in res["motivo"], res
    assert en_el_remoto(inst) == inst.base


def test_que_es_una_vista():
    cfg = SimpleNamespace(vistas=("docs/**/index.md", "kb/**", "*.txt"), carpetas=("kb", "conocimiento/decisions"))
    assert es_vista("docs/index.md", cfg) and es_vista("docs/a/b/index.md", cfg) and es_vista("kb/x/index.md", cfg)
    assert es_vista("notas.txt", cfg)
    for ruta in ("docs/a/otro.md", "kb/DEC-A.md", "kb/_huellas.json", "kb/_solicitudes/op.json", "a/notas.txt"):
        assert not es_vista(ruta, cfg), ruta


def test_la_solicitud_no_se_da_de_dos_formas(inst):
    inst.repo.escribir("kb/_solicitudes/op-1.json", json.dumps({"operacion_id": "op-1", "efectos": ACEPTAR}))
    res = proponer(
        inst.repo.raiz,
        inst.instalacion,
        operacion_id="op-1",
        archivos=[*decision_nueva(inst), "kb/_solicitudes/op-1.json"],
        efectos=ACEPTAR,
    )
    assert res["estado"] == "bloqueado" and "dos formas" in res["motivo"]


def test_lo_que_no_es_un_registro_lo_rechaza_la_puerta(inst):
    inst.repo.escribir("README.md", "otra\n")
    res = proponer(inst.repo.raiz, inst.instalacion, operacion_id="op-1", archivos=["README.md"], hasta="subir")
    assert res["estado"] == "bloqueado" and "no es un registro" in res["motivo"], res


@pytest.mark.parametrize("archivos", [[], ["../fuera.md"], ["kb/no-existe.md"], ["kb/DEC-A.md", "kb/../kb/DEC-A.md"]])
def test_archivos_que_no_se_pueden_proponer(inst, archivos):
    with pytest.raises((ValueError, OSError)):
        proponer(inst.repo.raiz, inst.instalacion, operacion_id="op-1", archivos=archivos)
    assert not inst.clon.exists()


def test_la_raiz_es_la_del_repositorio(inst):
    with pytest.raises(ValueError, match="raíz"):
        proponer(inst.repo.raiz / "kb", inst.instalacion, operacion_id="op-1", archivos=["DEC-A.md"])


@pytest.mark.parametrize(
    "cambio",
    [
        {"integracion": None},
        {"rama_canonica": None},
        {"rama_canonica": "a..b"},
        {"carpeta_registros": "kb,,otra"},
        {"integracion": {"remoto": "x"}},
        {"integracion": {"remoto": "--upload-pack=x", "repositorio": "p"}},
        {"integracion": {"remoto": "x", "repositorio": "../p"}},
        {"integracion": {"remoto": "x", "repositorio": "p", "aprobacion": "ninguna"}},
        {"integracion": {"remoto": "x", "repositorio": "p", "despues_de_integrar": ["no-declarada"]}},
        {"integracion": {"remoto": "x", "repositorio": "p", "vistas": ["../fuera/**"]}},
        {"integracion": {"remoto": "x", "repositorio": "p", "autor": {"nombre": "n"}}},
        {"integracion": {"remoto": "x", "repositorio": "p", "autor": {"nombre": "n", "correo": "integrador@localhost"}}},
        {"integracion": {"remoto": "x", "repositorio": "p", "cita": "Sí"}},
    ],
)
def test_configuracion_invalida(inst, cambio):
    with pytest.raises(ValueError):
        integracion_de({**inst.instalacion, **cambio})


def test_configuracion_de_varias_carpetas(inst):
    cfg = integracion_de({**inst.instalacion, "carpeta_registros": "kb,conocimiento/decisions"})
    assert cfg.carpetas == ("kb", "conocimiento/decisions") and cfg.modo == "toda" and cfg.despues == ()


def kbol(*args):
    return subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")


def cli(inst, *extra):
    efectos = inst.tmp / "efectos.json"
    efectos.write_text(json.dumps(ACEPTAR), encoding="utf-8")
    args = ["proponer", str(inst.repo.raiz), "--instalacion", str(inst.repo.raiz / "instalacion.json")]
    args += ["--operacion-id", "op-1", "--archivos", *decision_nueva(inst), "--efectos", str(efectos)]
    return kbol(*args, *extra)


def test_cli_del_paquete_a_la_subida(inst):
    p = cli(inst)
    sobre = json.loads(p.stdout)
    assert p.returncode == 3 and sobre["operacion"] == "proponer", p.stdout
    assert sobre["resultado"]["estado"] == "pendiente_de_aprobacion"
    texto = cli(inst, "--texto")
    assert texto.returncode == 3 and texto.stdout.startswith("Paquete de aprobación de op-1")
    aprobaciones = inst.tmp / "aprobaciones.json"
    aprobaciones.write_text(json.dumps(firmar(sobre["resultado"]["paquete"])), encoding="utf-8")
    p = cli(inst, "--aprobaciones", str(aprobaciones), "--hasta", "subir")
    sobre = json.loads(p.stdout)
    assert p.returncode == 0 and sobre["resultado"]["estado"] == "subido", p.stdout
    assert sobre["revision"] == en_el_remoto(inst)


@pytest.mark.parametrize(
    "extra", [["--aprobacion", "decisiva"], ["--rama-canonica", "otra"], ["--carpeta", "kb"], ["--recibos", "r"]]
)
def test_cli_lo_que_fija_la_instalacion_no_se_pasa_por_argumento(inst, extra):
    p = cli(inst, *extra)
    assert p.returncode == 2 and "los fija la instalación" in json.loads(p.stdout)["resultado"]["motivo"]
    assert not inst.clon.exists()


def test_cli_la_instalacion_se_lee_de_head(inst):
    inst.repo.escribir("instalacion.json", json.dumps(con(inst, aprobacion="decisiva")))
    p = cli(inst)
    assert p.returncode == 1 and "cambios sin commitear" in json.loads(p.stdout)["resultado"]["motivo"]


def test_cli_faltan_entradas(inst):
    p = kbol("proponer", str(inst.repo.raiz))
    assert p.returncode == 2 and "necesita" in json.loads(p.stdout)["resultado"]["motivo"]


def test_una_operacion_integrada_sin_subir_se_termina_con_el_mismo_id(inst):
    instalacion = con(inst, aprobacion="decisiva")
    archivos = pregunta_nueva(inst)
    uno = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="integrar")
    assert uno["estado"] == "integrado" and en_el_remoto(inst) == inst.base
    res = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="subir")
    assert res["estado"] == "subido" and res["retomada"] and res["revision_integrada"] == uno["revision_integrada"], res
    assert any("ya estaba integrada" in a for a in res["advertencias"])
    assert en_el_remoto(inst) == uno["revision_integrada"]


def test_tras_un_paso_posterior_fallido_se_termina_con_el_mismo_id(inst):
    marca = inst.tmp / "pasa"
    paso = py(f"import pathlib, sys; sys.exit(0 if pathlib.Path({str(marca)!r}).exists() else 3)")
    instalacion = con(inst, {"comprobador": paso}, aprobacion="decisiva", despues_de_integrar=["comprobador"])
    archivos = pregunta_nueva(inst)
    uno = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="subir")
    assert uno["estado"] == "bloqueado" and uno["pendientes_de_subir"] == 1
    marca.write_text("", encoding="utf-8")
    res = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="subir")
    assert res["estado"] == "subido" and res["retomada"], res
    assert [p["resultado"] for p in res["despues"]] == ["superado"]


def test_si_otro_sube_antes_se_dice_como_rehacerlo_y_se_rehace_con_otro_id(inst):
    instalacion = con(inst, aprobacion="decisiva")
    archivos = pregunta_nueva(inst)
    uno = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="integrar")
    remoto = otro_empuja(inst)
    res = proponer(inst.repo.raiz, instalacion, operacion_id="op-1", archivos=archivos, actor=AGENTE, hasta="subir")
    assert res["estado"] == "bloqueado" and res["codigo"] == "BASE_CAMBIADA", res
    assert res["integrado_sin_subir"] == uno["revision_integrada"] and res["remoto"] == remoto
    orden = res["motivo"].split("`")[1].split()
    assert orden[:3] == ["git", "-C", str(inst.clon)] and orden[3] == "update-ref"
    subprocess.run(orden, check=True)  # lo descarta una persona, con la orden que se le da
    res = proponer(inst.repo.raiz, instalacion, operacion_id="op-2", archivos=archivos, actor=AGENTE, hasta="subir")
    assert res["estado"] == "subido" and res["base"] == remoto, res


def test_un_remoto_local_con_ruta_relativa_sirve_en_la_segunda_orden(inst, monkeypatch):
    monkeypatch.chdir(inst.tmp)
    instalacion = con(inst, remoto="remoto.git", aprobacion="decisiva")
    for op in ("op-1", "op-2"):
        archivos = pregunta_nueva(inst, f"Q-{op[-1]}")
        res = proponer(inst.repo.raiz, instalacion, operacion_id=op, archivos=archivos, actor=AGENTE)
        assert res["estado"] == "ensayado", res


@pytest.mark.parametrize("op", ["a..b", "con", "NUL.x"])
def test_operacion_id_que_no_se_puede_usar(inst, op):
    res = proponer(inst.repo.raiz, inst.instalacion, operacion_id=op, archivos=decision_nueva(inst))
    assert res["estado"] == "bloqueado" and res["codigo"] is None


@pytest.mark.parametrize("escrita, normal", [("kb/", ("kb",)), ("kb//x, otra/", ("kb/x", "otra"))])
def test_las_carpetas_se_normalizan_como_en_la_puerta(inst, escrita, normal):
    assert integracion_de({**inst.instalacion, "carpeta_registros": escrita}).carpetas == normal


@pytest.mark.parametrize("correo", ["integrador@localhost.", ".Integrador@localhost", "Arranque@LOCALHOST", "x@"])
def test_el_correo_del_autor_no_suplanta_al_integrador(inst, correo):
    with pytest.raises(ValueError):
        integracion_de(con(inst, autor={"nombre": "n", "correo": correo}))
