"""Regresiones de la revisión del 4 nov 2026: sucesión completa encadenada y YAML ilegible en la carga."""

import json
import subprocess
import sys

from conftest import decision, evento, registro

from kbol.consolidar import consolidar
from kbol.core import serializar
from kbol.proyeccion import Snapshot

C = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")


def snap(*pares):
    return Snapshot({r["id"]: r for r, _ in pares}, "r1", {r["id"]: c for r, c in pares})


def cadena_completa():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b = decision("DEC-B", {"C1": "Martes."}, registrado="2026-11-02T00:00:00Z", deja_obsoleta=["DEC-A"])
    c = decision("DEC-C", {"C1": "Jueves."}, registrado="2026-11-03T00:00:00Z", deja_obsoleta=["DEC-B"])
    return a, b, c


def test_sustituida_no_vuelve_cuando_su_sucesora_es_sustituida():
    a, b, c = cadena_completa()
    res = consolidar(snap(a, b, c), ["DEC-A", "DEC-B", "DEC-C"], **C)
    assert res["vigencia"] == {"DEC-A": "no_vigente", "DEC-B": "no_vigente", "DEC-C": "total"}
    assert [x["texto"] for x in res["clausulas"] if x["estado"] == "vigente"] == ["Jueves."]


def test_status_de_la_sustituida_no_vuelve_a_stable():
    from kbol.proyeccion import proyectar_status

    a, b, c = cadena_completa()
    s = snap(a, b, c)
    assert proyectar_status(a[0], s, **C) == "deprecated"
    assert proyectar_status(b[0], s, **C) == "deprecated"
    assert proyectar_status(c[0], s, **C) == "stable"


def test_sustituida_no_vuelve_cuando_su_sucesora_vence():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        hasta="2026-11-10T00:00:00Z",
        deja_obsoleta=["DEC-A"],
    )
    res = consolidar(snap(a, b), ["DEC-A"], **C)
    assert res["vigencia"] == {"DEC-A": "no_vigente"} and res["clausulas"] == []


def test_sucesora_futura_no_retira_todavia():
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        valido="2026-12-01T00:00:00Z",
        deja_obsoleta=["DEC-A"],
    )
    assert consolidar(snap(a, b), ["DEC-A"], **C)["vigencia"] == {"DEC-A": "total"}


def test_cadena_antes_de_que_entre_la_ultima_sucesora():
    a, b, c = cadena_completa()
    corte = dict(valido_en="2026-11-02T12:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")
    res = consolidar(snap(a, b, c), ["DEC-A", "DEC-B"], **corte)
    assert res["vigencia"] == {"DEC-A": "no_vigente", "DEC-B": "total"}


def kb(*args):
    p = subprocess.run([sys.executable, "-m", "kbol.cli", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, json.loads(p.stdout)


def test_yaml_ilegible_deja_la_consulta_parcial(tmp_path):
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    rol = registro("rol", eventos=[evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")])
    (tmp_path / "DEC-A.md").write_text(serializar(*a, modo="canonico"), encoding="utf-8", newline="\n")
    (tmp_path / "ROL.md").write_text(serializar(rol, ""), encoding="utf-8", newline="\n")
    (tmp_path / "DEC-B.md").write_text("---\nid: DEC-B\nid: DEC-B\ntype: decision\n---\n", encoding="utf-8")
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 3 and out["resultado"]["estado"] == "parcial"
    assert [i["ruta"] for i in out["cobertura"]["invalidos"]] == ["DEC-B.md"]


def test_sin_cabecera_tambien_es_invalido_pero_el_indice_no(tmp_path):
    a = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    rol = registro("rol", eventos=[evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")])
    (tmp_path / "DEC-A.md").write_text(serializar(*a, modo="canonico"), encoding="utf-8", newline="\n")
    (tmp_path / "ROL.md").write_text(serializar(rol, ""), encoding="utf-8", newline="\n")
    (tmp_path / "index.md").write_text("* [DEC-A](DEC-A.md)\n", encoding="utf-8")
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 0, out
    (tmp_path / "suelto.md").write_text("Texto sin cabecera.\n", encoding="utf-8")
    code, out = kb("consolidar", str(tmp_path), "--ids", "DEC-A", "--valido-en", C["valido_en"])
    assert code == 3 and [i["ruta"] for i in out["cobertura"]["invalidos"]] == ["suelto.md"]
