"""`kbol sesion`: la lógica de conocimiento de los hooks de una instalación, detrás de una orden.

`inicio` da el paquete de contexto y los desvíos y los reutiliza mientras no cambie lo que los decide; `parar` valida
como propuestas los registros con cambios sin commitear; `commit` avisa de los desvíos del índice sin bloquear.
"""

import json
import subprocess
import sys

import pytest
from conftest import decision, evento, registro

from kbol import relevo as rv
from kbol import sesion
from kbol.core import serializar
from kbol.huellas import ARCHIVO, huella

V = "2026-11-20T00:00:00Z"
INSTALACION = {
    "proyecto": "Prueba",
    "rama_canonica": "main",
    "carpeta_registros": "kb",
    "ambito": "operaciones",
    "presupuesto": 50,
    "instrucciones": [{"ref": "AGENTS.md#limites", "resumen": "merge solo con visto bueno", "decisiva": True}],
}


def git(raiz, *args):
    orden = ["git", "-C", str(raiz), "-c", "user.name=t", "-c", "user.email=t@localhost", "-c", "core.autocrlf=false"]
    return subprocess.run([*orden, *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def escribir(raiz, nombre, r, c="", modo="canonico"):
    ruta = raiz / "kb" / f"{nombre}.md"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(serializar(r, c, modo=modo), encoding="utf-8", newline="\n")
    return ruta


def configurar(raiz, **cambios):
    ruta = raiz / "instalacion.json"
    ruta.write_text(json.dumps({**INSTALACION, **cambios}), encoding="utf-8")
    return ruta


@pytest.fixture
def raiz(tmp_path):
    """Un repositorio con el rol, una decisión vigente y una pregunta abierta, con sus huellas, en la rama feat/x."""
    creacion = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")
    abierta = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="abierta")
    rutas = {
        "ROL-EJEMPLO": escribir(tmp_path, "ROL", registro("rol", eventos=[creacion])),
        "DEC-A": escribir(tmp_path, "DEC-A", *decision("DEC-A", {"C1": "Solo datos verificados."})),
        "Q-A": escribir(tmp_path, "Q-A", registro("pregunta", eventos=[abierta])),
    }
    huellas = {i: {"ruta": f"kb/{r.name}", "sha256": huella(r.read_bytes())} for i, r in rutas.items()}
    (tmp_path / "kb" / ARCHIVO).write_text(json.dumps(huellas), encoding="utf-8")
    configurar(tmp_path)
    (tmp_path / ".gitignore").write_text(".kbol/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "feat/x")
    return tmp_path


def iniciar(raiz, **kw):
    return sesion.inicio(raiz, "instalacion.json", **kw)


def cli(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


# --- inicio ---


def test_inicio_da_el_paquete_y_los_desvios_con_la_tarea_de_la_rama(raiz):
    res = iniciar(raiz)
    r = res["resultado"]
    assert res["codigo"] == 0 and r["estado"] == "completado", r
    assert r["tarea"] == "feat-x" and r["paquete"]["tarea"] == "feat-x"
    assert "Solo datos verificados." in [x["texto"] for x in r["paquete"]["restricciones"]]
    assert r["desvios"] == {"comprobados": 3, "avisos": []}
    assert "Solo datos verificados." in res["texto"] and "Desvíos" not in res["texto"]


def test_inicio_lee_el_reloj_solo_si_no_se_le_da_el_corte_y_lo_declara(raiz):
    assert iniciar(raiz, valido_en=V)["valido_en"] == V
    dado = iniciar(raiz)["valido_en"]
    assert dado != V and rv.es_instante(dado)
    with pytest.raises(ValueError, match="instante"):
        iniciar(raiz, valido_en="2026-11-20")


def test_inicio_resuelve_la_raiz_desde_cualquier_carpeta_del_arbol(raiz):
    assert iniciar(raiz / "kb")["resultado"]["estado"] == "completado"
    assert (raiz / ".kbol" / "sesion" / "inicio-feat-x.json").is_file()


def test_inicio_reutiliza_lo_guardado_mientras_no_cambie_lo_que_lo_decide(raiz):
    primero = iniciar(raiz, valido_en=V)["resultado"]
    segundo = iniciar(raiz, valido_en=V)["resultado"]
    assert not primero["reutilizado"] and segundo["reutilizado"]
    assert segundo["paquete"]["paquete_id"] == primero["paquete"]["paquete_id"]
    assert segundo["huella"] == primero["huella"]


@pytest.mark.parametrize("cambio", ["registro", "relevo", "instalacion", "corte", "commit", "tarea"])
def test_inicio_recalcula_cuando_cambia_lo_que_lo_decide(raiz, cambio):
    antes = iniciar(raiz, valido_en=V)["resultado"]
    argumentos = {"valido_en": V}
    if cambio == "registro":
        escribir(raiz, "DEC-B", *decision("DEC-B", {"C1": "Informe los lunes."}))
    elif cambio == "relevo":
        rv.guardar(raiz, "feat-x", {"objetivo": "Preparar el informe"})
    elif cambio == "instalacion":
        configurar(raiz, presupuesto=40)
    elif cambio == "corte":
        argumentos["valido_en"] = "2026-11-21T00:00:00Z"
    elif cambio == "commit":
        git(raiz, "commit", "-q", "--allow-empty", "-m", "otro")
    else:
        argumentos["tarea"] = "otra"
    despues = iniciar(raiz, **argumentos)["resultado"]
    assert not despues["reutilizado"] and despues["huella"] != antes["huella"]


def test_inicio_no_reutiliza_un_guardado_estropeado(raiz):
    huella = iniciar(raiz, valido_en=V)["resultado"]["huella"]
    guardado = raiz / ".kbol" / "sesion" / "inicio-feat-x.json"
    for contenido in ("{", json.dumps({"huella": huella, "calculado": {"paquete": {}, "desvios": {}}})):
        guardado.write_text(contenido, encoding="utf-8")
        res = iniciar(raiz, valido_en=V)["resultado"]
        assert not res["reutilizado"] and res["estado"] == "completado"


def test_inicio_con_la_tarea_dada_recalcula_al_cambiar_de_rama(raiz):
    antes = iniciar(raiz, valido_en=V, tarea="informe")["resultado"]
    git(raiz, "checkout", "-q", "-b", "feat/y")
    despues = iniciar(raiz, valido_en=V, tarea="informe")["resultado"]
    assert not despues["reutilizado"] and despues["paquete"]["relevo"]["git"]["rama"] == "feat/y"
    assert antes["paquete"]["relevo"]["git"]["rama"] == "feat/x"


def test_inicio_da_el_resultado_aunque_no_pueda_guardarlo(raiz):
    (raiz / ".kbol").mkdir()
    (raiz / ".kbol" / "sesion").write_text("un archivo donde iría la carpeta", encoding="utf-8")
    res = iniciar(raiz, valido_en=V)
    assert res["codigo"] == 0 and not res["resultado"]["reutilizado"]


def test_inicio_avisa_de_un_desvio_sin_cambiar_el_codigo(raiz):
    ruta = raiz / "kb" / "Q-A.md"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("Una línea.", "Otra línea."), encoding="utf-8")
    res = iniciar(raiz)
    assert res["codigo"] == 0
    assert [a["id"] for a in res["resultado"]["desvios"]["avisos"]] == ["Q-A"]
    assert "1 difieren de lo integrado (Q-A)" in res["texto"] and "main" in res["texto"]
    assert any(a.startswith("Q-A (kb/Q-A.md)") for a in res["advertencias"])


def test_inicio_es_parcial_si_la_carga_lo_es_y_el_texto_lo_dice(raiz):
    (raiz / "kb" / "roto.md").write_text("sin cabecera\n", encoding="utf-8")
    res = iniciar(raiz)
    assert res["codigo"] == 3 and res["resultado"]["estado"] == "parcial"
    assert "Paquete parcial" in res["texto"] and res["cobertura"]["invalidos"]


def test_inicio_bloqueado_sale_con_2_y_sigue_dando_el_texto(raiz):
    copia, cuerpo = decision("DEC-A", {"C1": "Otra cosa."})
    escribir(raiz, "DEC-A-copia", copia, cuerpo)
    res = iniciar(raiz)
    assert res["codigo"] == 2 and res["resultado"]["estado"] == "bloqueado"
    assert "Paquete bloqueado" in res["texto"]


def test_inicio_sin_registros_con_historial_no_da_los_desvios_por_comprobados(tmp_path):
    escribir(tmp_path, "Q-A", registro("pregunta"), modo="propuesta")
    configurar(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    res = iniciar(tmp_path)
    assert res["codigo"] == 3 and "desvíos" in res["resultado"]["motivo"]
    assert "no se comprobó ningún registro" in res["texto"]


def test_tras_compactar_el_texto_lleva_el_trabajo_de_la_tarea_en_git(raiz):
    git(raiz, "commit", "-q", "--allow-empty", "-m", "primer paso")
    (raiz / "notas.txt").write_text("x", encoding="utf-8")
    (raiz / "otra.txt").write_text("x", encoding="utf-8")
    normal = iniciar(raiz)["texto"]
    compactado = iniciar(raiz, origen="compact")["texto"]
    assert "Trabajo de la tarea en git" not in normal
    assert "Trabajo de la tarea en git (rama feat/x)" in compactado
    assert "Commits propios (1): primer paso" in compactado
    assert "Cambios sin commitear (2)" in compactado and "  otra.txt" in compactado


@pytest.mark.parametrize(
    "cambios, motivo",
    [
        ({"carpeta_registros": None}, "carpeta_registros"),
        ({"carpeta_registros": "kb,"}, "carpeta_registros"),
        ({"ambito": 3}, "ambito"),
        ({"presupuesto": True}, "presupuesto"),
        ({"rama_canonica": 1}, "rama_canonica"),
    ],
)
def test_inicio_rechaza_una_instalacion_sin_lo_que_necesita(raiz, cambios, motivo):
    configurar(raiz, **cambios)
    with pytest.raises(ValueError, match=motivo):
        iniciar(raiz)


def test_inicio_y_commit_leen_con_el_formato_heredado_de_la_instalacion(raiz):
    formato = {"registros": {"Decisión": {"tipo": "decision", "id": r"DEC-\d{3,}"}}}
    configurar(raiz, formato_heredado=formato)
    heredado = "---\ntype: Decisión\nid: {}\ntitle: Ejemplo\nestado: Aceptada\n---\n\n# Ejemplo\n"
    ruta = raiz / "kb" / "DEC-108.md"
    ruta.write_text(heredado.format("DEC-108"), encoding="utf-8", newline="\n")
    assert iniciar(raiz)["codigo"] == 0  # el heredado se lee aparte, con su formato, y no rige
    ruta.write_text(heredado.format("DEC-1"), encoding="utf-8", newline="\n")
    res = iniciar(raiz)
    assert res["codigo"] == 3 and res["cobertura"]["invalidos"]  # un ID fuera del patrón de su etiqueta
    git(raiz, "add", "kb/DEC-108.md")
    assert sesion.commit(raiz, "instalacion.json")["codigo"] == 3
    configurar(raiz, formato_heredado={"registros": {}})
    with pytest.raises(ValueError, match="formato_heredado"):
        iniciar(raiz)


def test_fuera_de_un_arbol_de_git_no_hay_sesion(tmp_path):
    configurar(tmp_path)
    with pytest.raises(ValueError, match="árbol de trabajo"):
        iniciar(tmp_path)


def test_la_tarea_de_la_rama_sigue_el_patron_del_relevo(raiz):
    assert sesion.tarea_de_la_rama(raiz) == "feat-x"
    git(raiz, "checkout", "-q", "-b", "_fix/a+b/c.d")
    tarea = sesion.tarea_de_la_rama(raiz)
    assert tarea == "fix-a-b-c.d" and rv.ruta_del_relevo(raiz, tarea)
    git(raiz, "checkout", "-q", "--detach")
    assert sesion.tarea_de_la_rama(raiz) == "sin-rama"


# --- parar ---


def parar(raiz, **kw):
    return sesion.parar(raiz, "instalacion.json", **kw)


def sin_condicion(raiz, ident):
    """Una pregunta a la que le falta un campo obligatorio: no valida como propuesta."""
    ruta = escribir(raiz, ident, registro("pregunta", id=ident), modo="propuesta")
    lineas = [x for x in ruta.read_text(encoding="utf-8").splitlines() if not x.startswith("condicion_cierre:")]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def test_parar_sin_registros_con_cambios_no_ha_examinado_nada(raiz):
    (raiz / "notas.md").write_text("fuera de las carpetas\n", encoding="utf-8")
    res = parar(raiz)
    assert res["codigo"] == 3 and res["resultado"]["estado"] == "parcial"
    assert res["resultado"]["examinados"] == 0 and res["texto"] == "" and res["advertencias"]


def test_parar_valida_como_propuesta_lo_que_sigue_sin_commitear(raiz):
    escribir(raiz, "Q-N", registro("pregunta", id="Q-N"), modo="propuesta")
    res = parar(raiz)
    assert res["codigo"] == 0 and res["resultado"]["examinados"] == 1 and res["texto"] == ""
    git(raiz, "add", "-A")
    git(raiz, "commit", "-q", "-m", "pregunta")
    assert parar(raiz)["resultado"]["examinados"] == 0  # lo ya commiteado no es de este turno


def test_parar_rechaza_un_registro_que_no_valida_y_dice_por_que(raiz):
    sin_condicion(raiz, "Q-N")
    (raiz / "kb" / "roto.md").write_text("sin cabecera\n", encoding="utf-8")
    res = parar(raiz)
    r = res["resultado"]
    assert res["codigo"] == 1 and r["estado"] == "fallido" and r["codigo"] == "ESQUEMA_INVALIDO"
    assert [x["ruta"] for x in r["rechazados"]] == ["kb/Q-N.md", "kb/roto.md"] and r["examinados"] == 2
    assert "condicion_cierre" in json.dumps(r["rechazados"][0]["errores"], ensure_ascii=False)
    assert res["texto"].startswith("KBOL rechaza") and "kb/Q-N.md:" in res["texto"] and "kb/roto.md:" in res["texto"]


def test_parar_con_rutas_solo_mira_lo_que_edito_la_sesion(raiz):
    sin_condicion(raiz, "Q-N")
    escribir(raiz, "Q-M", registro("pregunta", id="Q-M"), modo="propuesta")
    assert parar(raiz, rutas=["kb/Q-M.md"])["codigo"] == 0
    assert parar(raiz, rutas=[])["codigo"] == 3
    assert parar(raiz, rutas=[str(raiz / "kb" / "Q-N.md"), "kb\\Q-M.md"])["resultado"]["examinados"] == 2
    assert parar(raiz, rutas=["kb/DEC-A.md"])["codigo"] == 3  # editado y ya commiteado: no hay nada que validar
    configurar(raiz, carpeta_registros="./kb/")
    assert parar(raiz, rutas=["./kb/Q-M.md"])["resultado"]["examinados"] == 1


def test_parar_no_cuenta_lo_que_no_es_un_registro_del_perfil(raiz):
    (raiz / "kb" / "guia.md").write_text("---\ntype: Guía\ntitle: x\n---\nTexto.\n", encoding="utf-8")
    (raiz / "kb" / "index.md").write_text("índice\n", encoding="utf-8")
    res = parar(raiz)
    assert res["codigo"] == 3 and res["resultado"]["no_registros"] == ["kb/guia.md"]


# --- commit ---


def test_commit_avisa_de_lo_que_entra_en_el_commit_y_no_bloquea(raiz):
    ruta = raiz / "kb" / "Q-A.md"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("Una línea.", "Otra línea."), encoding="utf-8")
    sin_preparar = sesion.commit(raiz, "instalacion.json")
    assert sin_preparar["codigo"] == 0 and sin_preparar["texto"] == ""
    git(raiz, "add", "kb/Q-A.md")
    res = sesion.commit(raiz, "instalacion.json")
    assert res["codigo"] == 0 and res["resultado"]["estado"] == "completado" and res["resultado"]["comprobados"] == 3
    assert res["texto"] == "aviso: Q-A (kb/Q-A.md) difiere de lo integrado en main: proponlo por la integración"


def test_commit_sin_registros_con_historial_es_parcial(tmp_path):
    escribir(tmp_path, "Q-A", registro("pregunta"), modo="propuesta")
    configurar(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git(tmp_path, "add", "-A")
    res = sesion.commit(tmp_path, "instalacion.json")
    assert res["codigo"] == 3 and res["resultado"]["estado"] == "parcial"


# --- CLI ---


def test_la_cli_devuelve_el_sobre_con_el_corte_que_uso(raiz):
    codigo, salida = cli("sesion", str(raiz / "kb"), "--evento", "inicio", "--instalacion", "instalacion.json")
    sobre = json.loads(salida)
    assert codigo == 0 and sobre["operacion"] == "sesion" and sobre["revision"] == "disco"
    assert sobre["valido_en"] and sobre["resultado"]["evento"] == "inicio"
    assert sobre["cobertura"]["leidos"] == 3 and "quien hizo la edición" in sobre["cobertura"]["no_evaluado"]
    assert "advertencias" not in sobre["resultado"]["paquete"]


def test_la_cli_con_texto_da_solo_lo_que_se_inyecta(raiz):
    args = ("--instalacion", str(raiz / "instalacion.json"), "--texto")
    codigo, salida = cli("sesion", str(raiz), "--evento", "inicio", "--tarea", "informe", *args)
    assert codigo == 0 and salida.startswith("Contexto de KBOL para la tarea informe")
    codigo, salida = cli("sesion", str(raiz), "--evento", "parar", *args)
    assert codigo == 3 and salida.strip() == ""
    (raiz / "kb" / "roto.md").write_text("sin cabecera\n", encoding="utf-8")
    codigo, salida = cli("sesion", str(raiz), "--evento", "parar", "--rutas", "kb/roto.md", *args)
    assert codigo == 1 and "kb/roto.md" in salida


def test_la_cli_falla_cerrada_sin_evento_sin_instalacion_o_con_una_ilegible(raiz):
    codigo, salida = cli("sesion", str(raiz), "--instalacion", "instalacion.json")
    assert codigo == 2 and "--evento" in json.loads(salida)["resultado"]["motivo"]
    codigo, salida = cli("sesion", str(raiz), "--evento", "inicio")
    assert codigo == 2 and "--instalacion" in json.loads(salida)["resultado"]["motivo"]
    codigo, salida = cli("sesion", str(raiz), "--evento", "inicio", "--instalacion", "no-existe.json", "--texto")
    assert codigo == 1 and json.loads(salida)["resultado"]["codigo"] == "REFERENCIA_AUSENTE"
    (raiz / "instalacion.json").write_text("{", encoding="utf-8")
    codigo, salida = cli("sesion", str(raiz), "--evento", "commit", "--instalacion", "instalacion.json")
    assert codigo == 1 and json.loads(salida)["resultado"]["codigo"] == "ESQUEMA_INVALIDO"
