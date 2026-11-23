"""Regresiones de la revisión independiente de consolidar, dependencias, mutabilidad y snapshot (3 nov 2026)."""

import copy
import json
import subprocess
import sys

from conftest import decision, evento, registro

from kbol.consolidar import consolidar
from kbol.core import serializar
from kbol.dependencias import evaluar, listos
from kbol.mutabilidad import comparar
from kbol.proyeccion import Snapshot

C = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")


def snap(*pares):
    return Snapshot({r["id"]: r for r, _ in pares}, "r1", {r["id"]: c for r, c in pares})


def sust(destino, por):
    return {"destino": destino, "tipo": "sustitucion", "por": por}


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def rol_canonico():
    return registro(
        "rol",
        eventos=[
            evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta"),
        ],
    )


def a_disco(carpeta, *pares, nombres=None):
    carpeta.mkdir(parents=True, exist_ok=True)
    for i, (r, c) in enumerate(pares):
        nombre = nombres[i] if nombres else f"{r['id']}.md"
        modo = "canonico" if r.get("eventos") else "propuesta"
        (carpeta / nombre).write_text(serializar(r, c, modo=modo), encoding="utf-8", newline="\n")


def base_esc():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b = decision("DEC-B", {"C1": "Martes."}, registrado="2026-11-02T00:00:00Z", modifica=[sust("DEC-A#C1", "DEC-B#C1")])
    return a, b


# --- HIGH ---------------------------------------------------------------------------------------------------


def test_registro_excluido_deja_la_consulta_parcial(tmp_path):
    a, b = base_esc()
    a_disco(tmp_path, a, b, (rol_canonico(), ""))
    texto = (tmp_path / "DEC-B.md").read_text(encoding="utf-8").replace("---\n", "---\nextra: 1\n", 1)
    (tmp_path / "DEC-B.md").write_text(texto, encoding="utf-8")
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 3 and out["resultado"]["estado"] == "parcial"


def test_id_repetido_bloquea(tmp_path):
    a, b = base_esc()
    b2 = copy.deepcopy(b)
    a_disco(tmp_path, a, b, b2, (rol_canonico(), ""), nombres=["DEC-A.md", "a-DEC-B.md", "z-DEC-B.md", "ROL.md"])
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 2 and out["resultado"]["estado"] == "bloqueado"


def test_snapshot_coherente_es_completado(tmp_path):
    a, b = base_esc()
    a_disco(tmp_path, a, b, (rol_canonico(), ""))
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 0 and out["resultado"]["estado"] == "completado", out


def test_sucesion_mutua_es_conflicto_no_texto_base():
    a, b = base_esc()
    b[0]["depende_de"] = [{"destino": "DEC-D", "condicion": "aceptada_y_vigente"}]
    d = decision(
        "DEC-D",
        {"C1": "Miércoles."},
        registrado="2026-11-02T12:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-D#C1")],
        depende_de=[{"destino": "DEC-B", "condicion": "aceptada_y_vigente"}],
    )
    (c1,) = consolidar(snap(a, b, d), ["DEC-A"], **C)["clausulas"]
    assert c1["estado"] == "conflicto"


def test_decision_toda_derogada_no_rige_ni_satisface():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    f = decision(
        "DEC-F",
        {"C1": "M."},
        registrado="2026-11-02T00:00:00Z",
        modifica=[{"destino": "DEC-A#C1", "tipo": "derogacion"}],
    )
    s = snap(a, f)
    assert consolidar(s, ["DEC-A"], **C)["vigencia"] == {"DEC-A": "no_vigente"}
    h = registro("hito", depende_de=[{"destino": "DEC-A", "condicion": "aceptada_y_vigente"}])
    assert evaluar(h, s, **C)[0]["satisfecha"] is False


# --- MEDIUM -------------------------------------------------------------------------------------------------


def test_modificar_otra_clausula_no_es_sucesion():
    a, b = base_esc()
    d = decision(
        "DEC-D",
        {"C1": "Miércoles."},
        registrado="2026-11-02T12:00:00Z",
        modifica=[sust("DEC-A#C1", "DEC-D#C1"), {"destino": "DEC-B#C7", "tipo": "derogacion"}],
    )
    (c1,) = consolidar(snap(a, b, d), ["DEC-A"], **C)["clausulas"]
    assert c1["estado"] == "conflicto"


def test_ciclo_de_sucesion_completa_es_ambiguo_en_cualquier_orden():
    x = decision("DEC-X", {"C1": "x"}, deja_obsoleta=["DEC-Y"])
    y = decision("DEC-Y", {"C1": "y"}, deja_obsoleta=["DEC-X"])
    for orden in (["DEC-X", "DEC-Y"], ["DEC-Y", "DEC-X"]):
        res = consolidar(snap(x, y), orden, **C)
        assert res["vigencia"] == {"DEC-X": "no_vigente", "DEC-Y": "no_vigente"}, orden
        assert any("ciclo" in a for a in res["advertencias"])


def test_propuesta_al_corte_aunque_la_cabecera_diga_aceptada():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    c = decision(
        "DEC-C", {"C1": "Estimados."}, registrado="2026-11-05T00:00:00Z", modifica=[sust("DEC-A#C1", "DEC-C#C1")]
    )
    c[0]["eventos"][0]["registrado_en"] = c[0]["eventos"][0]["valido_desde"] = "2026-11-01T00:00:00Z"
    res = consolidar(snap(a, c), ["DEC-A"], valido_en="2026-11-03T00:00:00Z", conocido_hasta="2026-11-03T00:00:00Z")
    assert [p["decision"] for p in res["propuestas"]] == ["DEC-C"]


def test_adicion_propuesta_se_informa():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    g = decision(
        "DEC-G",
        {"C1": "Panel."},
        estado="propuesta",
        modifica=[{"destino": "DEC-A", "tipo": "adicion", "por": "DEC-G#C1", "posicion": "al final"}],
    )
    res = consolidar(snap(a, g), ["DEC-A"], **C)
    assert [p["decision"] for p in res["propuestas"]] == ["DEC-G"]


def con_historial(tipo, pasos, **campos):
    """pasos: [(estado, valido_desde, valido_hasta)]; el primero es la creación."""
    ev = []
    previo = None
    for i, (estado, desde, hasta) in enumerate(pasos):
        t = f"2026-11-0{i + 1}T00:00:00Z"
        e = evento(
            "creacion" if i == 0 else "transicion",
            evento_id=f"E{i}",
            estado_anterior=previo,
            estado_nuevo=estado,
            registrado_en=t,
            valido_desde=desde or t,
        )
        if hasta:
            e["valido_hasta"] = hasta
        ev.append(e)
        previo = estado
    return registro(tipo, estado=previo, eventos=ev, **campos)


def test_listos_exige_autorizacion_vigente():
    futura = con_historial("hito", [("propuesto", None, None), ("autorizado", "2026-12-01T00:00:00Z", None)], id="HI-F")
    vencida = con_historial(
        "hito", [("propuesto", None, None), ("autorizado", None, "2026-11-05T00:00:00Z")], id="HI-V"
    )
    res = listos(Snapshot({"HI-F": futura, "HI-V": vencida}, "r"), **C)
    assert res["listos"] == []


def test_completado_sin_verificaciones_no_satisface():
    y = con_historial(
        "hito",
        [("propuesto", None, None), ("autorizado", None, None), ("en_curso", None, None), ("completado", None, None)],
        id="HI-Y",
    )
    x = registro("hito", id="HI-X", depende_de=[{"destino": "HI-Y", "condicion": "completado_con_evidencia"}])
    (r,) = evaluar(x, Snapshot({"HI-Y": y, "HI-X": x}, "r"), **C)
    assert r["satisfecha"] is False and r["codigo"] == "EVIDENCIA_INSUFICIENTE"


def _comparar(antes, cambiar, cuerpo=""):
    base = Snapshot({antes["id"]: antes}, "b", {antes["id"]: cuerpo})
    prop = copy.deepcopy(base)
    cambiar(prop)
    return [h for h in comparar(base, prop)["hallazgos"] if h["severidad"] == "error"]


def test_registros_cerrados_de_otros_tipos_protegidos():
    hip = con_historial("hipotesis", [("abierta", None, None), ("validada", None, None)])
    assert _comparar(hip, lambda p: p.registros["HIP-A"].update(afirmacion="otra"))
    q = con_historial("pregunta", [("abierta", None, None), ("resuelta", None, None)])
    assert _comparar(q, lambda p: p.registros["Q-A"].update(condicion_cierre="otra"))
    hito = con_historial("hito", [("propuesto", None, None), ("autorizado", None, None)])
    assert _comparar(hito, lambda p: p.registros["HI-A"].update(alcance="todo el repositorio"))


def test_hecho_en_prosa_de_decision_cerrada_protegido():
    r, cuerpo = decision("DEC-A", {"C1": "Lunes."}, sources=[{"id": "s1", "resource": "F-A"}])
    cuerpo += 'Caudal <hecho id="H1" evidencia="observado" fuente="s1">5 m3/h</hecho>.\n'

    def cambiar(p):
        p.cuerpos["DEC-A"] = cuerpo.replace("5 m3/h", "50 m3/h").replace("observado", "declarado")

    assert _comparar(r, cambiar, cuerpo)


def test_importacion_sin_inicio_de_validez_es_ambigua():
    imp = evento(
        "importacion",
        evento_id="E0",
        estado_anterior=None,
        estado_nuevo="aceptada",
        estado_heredado="Aceptada",
        procedencia={"ruta": "docs/x.md", "revision": "r"},
        valido_desde=None,
        precision="desconocida",
    )
    r = registro("decision", id="DEC-I", estado="aceptada", eventos=[imp])
    res = consolidar(
        Snapshot({"DEC-I": r}, "r", {"DEC-I": '<clausula id="C1">\nRegla.\n</clausula>\n'}),
        ["DEC-I"],
        valido_en="1990-01-01T00:00:00Z",
        conocido_hasta=None,
    )
    assert res["vigencia"] == {"DEC-I": "no_vigente"} and any("TIEMPO_AMBIGUO" in a for a in res["advertencias"])


# --- LOW ----------------------------------------------------------------------------------------------------


def test_autoridad_es_la_de_la_decision_de_origen_y_sin_revocadas():
    a, b = base_esc()
    b[0]["autorizado_por"] = ["ROL-B"]
    b[0]["eventos"].append(
        evento(
            "revocacion_aprobacion",
            evento_id="E3",
            registrado_en="2026-11-03T00:00:00Z",
            valido_desde="2026-11-03T00:00:00Z",
            aprobacion_id="AP-DEC-B",
        )
    )
    (c1,) = consolidar(snap(a, b), ["DEC-A"], **C)["clausulas"]
    assert c1["autoridad"]["decision"] == "DEC-B" and c1["autoridad"]["autorizado_por"] == ["ROL-B"]
    assert c1["autoridad"]["ratificaciones"] == []


def test_acceso_de_fuente_es_politica_y_formato_inmutable():
    f = con_historial("fuente", [("registrada", None, None)])
    base = Snapshot({"F-A": f}, "b", {"F-A": ""})
    prop = copy.deepcopy(base)
    prop.registros["F-A"]["acceso"] = "publico"
    assert comparar(base, prop)["cambios_de_politica"] == ["F-A"]
    assert _comparar(f, lambda p: p.registros["F-A"].update(formato="text/plain"))


def test_revision_desde_subcarpeta_y_carpeta_inexistente(tmp_path):
    repo = tmp_path / "repo"
    a, b = base_esc()
    a_disco(repo / "docs" / "kb", a, b, (rol_canonico(), ""))
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    code, out = kb(
        "consolidar",
        str(repo / "docs"),
        "--carpeta",
        "kb",
        "--revision",
        "HEAD",
        "--ids",
        "DEC-A",
        "--valido-en",
        C["valido_en"],
    )
    assert code == 0, out
    code, out = kb("listos", str(repo), "--carpeta", "no-existe", "--valido-en", C["valido_en"])
    assert code == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"
    code, out = kb("listos", str(repo), "--carpeta", "no-existe", "--revision", "HEAD", "--valido-en", C["valido_en"])
    assert code == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"


def test_archivo_no_utf8_no_tumba_la_carga(tmp_path):
    a, b = base_esc()
    a_disco(tmp_path, a, b, (rol_canonico(), ""))
    (tmp_path / "roto.md").write_bytes(b"---\ntitle: \xff\n---\n")
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 3 and [i["ruta"] for i in out["cobertura"]["invalidos"]] == ["roto.md"]


def test_un_solo_aviso_sin_corte(tmp_path):
    a, b = base_esc()
    a_disco(tmp_path, a, b, (rol_canonico(), ""))
    _, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert sum("historial admitido" in a for a in out["advertencias"]) == 1
