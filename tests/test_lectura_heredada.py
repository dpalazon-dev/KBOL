"""Lectura compatible del formato heredado, mientras dura la transición al contrato.

Los registros heredados se leen aparte, como importados sin historial admitido: las consultas los nombran con su estado
heredado, pero nunca los cuentan como normativos ni dan por cumplida una dependencia que apunte a ellos.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import decision, evento, registro

from kbol.consolidar import consolidar
from kbol.core import serializar
from kbol.dependencias import evaluar, listos
from kbol.snapshot import cargar

HEREDADOS = Path(__file__).parent / "heredados"
C = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")


def corpus(carpeta, *nombres):
    """Copia los registros heredados indicados (sin el .txt) y un registro KBOL con historial."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        shutil.copy(HEREDADOS / f"{nombre}.txt", carpeta / nombre)
    r, c = decision("DEC-A", {"C1": "Lunes."})
    (carpeta / "DEC-A.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")
    creacion = evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="propuesta")
    rol = registro("rol", eventos=[creacion])  # el rol que autoriza DEC-A: sin él la carga sería parcial
    (carpeta / f"{rol['id']}.md").write_text(serializar(rol, "", modo="canonico"), encoding="utf-8", newline="\n")
    return carpeta


ADR = "0063-una-copia-de-trabajo-por-sesion.md"


def test_sin_la_opcion_los_heredados_se_omiten_como_hasta_ahora(tmp_path):
    corpus(tmp_path / "docs", ADR, "PL-001-H3.md")
    snapshot, cobertura = cargar(tmp_path, "docs")
    assert set(snapshot.registros) == {"DEC-A", "ROL-EJEMPLO"} and snapshot.heredados == {}
    assert cobertura["omitidos"] == 2 and cobertura["heredados"] == 0


def test_con_la_opcion_se_leen_aparte_y_sin_historial(tmp_path):
    corpus(tmp_path / "docs", ADR, "PL-001-H3.md", "QD-054.md")
    snapshot, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert set(snapshot.registros) == {"DEC-A", "ROL-EJEMPLO"}
    assert set(snapshot.heredados) == {"ADR-0063", "PL-001-H3", "QD-054"}
    adr = snapshot.heredados["ADR-0063"]
    assert adr["tipo"] == "decision" and adr["estado_heredado"] == "Aceptada" and adr["estado_propuesto"] == "aceptada"
    assert adr["ruta"] == f"docs/{ADR}" and adr["requiere_revision"]
    assert snapshot.heredados["QD-054"]["ambiguedades"]  # «En revisión» no existe en el contrato
    assert cobertura["heredados"] == 3 and cobertura["omitidos"] == 0 and cobertura["estado"] == "completo"
    assert any("formato heredado" in a for a in cobertura["advertencias"])


def test_un_id_heredado_que_repite_uno_del_perfil_bloquea(tmp_path):
    # Durante la migración, un registro ya migrado conserva su ID heredado y convive con su archivo antiguo.
    carpeta = corpus(tmp_path / "docs", ADR)
    r, c = decision("ADR-0063", {"C1": "Una copia de trabajo por sesión."})
    (carpeta / "ADR-0063.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")
    _, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert cobertura["estado"] == "bloqueado"
    assert any("ADR-0063" in h["mensaje"] and "formato heredado" in h["mensaje"] for h in cobertura["hallazgos"])


def test_un_heredado_con_id_del_perfil_es_invalido(tmp_path):
    carpeta = corpus(tmp_path / "docs", ADR)
    reescribir(carpeta, ADR, "id: ADR-0063", "id: DEC-A")
    _, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert cobertura["estado"] == "parcial" and [i["ruta"] for i in cobertura["invalidos"]] == [f"docs/{ADR}"]


def test_un_hito_heredado_nunca_esta_listo_y_se_explica(tmp_path):
    corpus(tmp_path / "docs", "PL-001-H3.md", "PL-001-H6.md")
    snapshot, _ = cargar(tmp_path, "docs", heredados=True)
    res = listos(snapshot, **C)
    assert res["listos"] == [] and res["bloqueados"] == []
    avisos = " ".join(res["advertencias"])
    assert "PL-001-H3: formato heredado (Pendiente)" in avisos and "PL-001-H6: formato heredado (Cumplido)" in avisos


def test_una_dependencia_hacia_un_heredado_no_se_satisface(tmp_path):
    corpus(tmp_path / "docs", ADR)
    snapshot, _ = cargar(tmp_path, "docs", heredados=True)
    hito = registro(
        "hito",
        estado="autorizado",
        eventos=[evento("creacion", evento_id="E0", estado_anterior=None, estado_nuevo="autorizado")],
        depende_de=[{"destino": "ADR-0063", "condicion": "aceptada_y_vigente"}],
    )
    [dep] = evaluar(hito, snapshot, **C)
    assert not dep["satisfecha"] and "formato heredado" in dep["motivo"] and "Aceptada" in dep["motivo"]


def test_consolidar_nombra_la_decision_heredada_sin_darla_por_vigente(tmp_path):
    corpus(tmp_path / "docs", ADR)
    snapshot, _ = cargar(tmp_path, "docs", heredados=True)
    res = consolidar(snapshot, ["ADR-0063", "ADR-9999"], **C)
    assert res["ausentes"] == ["ADR-9999"] and "ADR-0063" not in res["vigencia"]
    [ficha] = res["heredados"]
    assert ficha["id"] == "ADR-0063" and ficha["estado_heredado"] == "Aceptada"
    assert any("ADR-0063" in a and "no rige" in a for a in res["advertencias"])


def test_cli_listos_con_heredados(tmp_path):
    corpus(tmp_path / "docs", "PL-001-H3.md")
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "kbol.cli",
            "listos",
            "--heredados",
            "--valido-en",
            C["valido_en"],
            "--carpeta",
            "docs",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    salida = json.loads(p.stdout)
    # El corpus solo trae un hito heredado, que no rige: no hay ningún hito examinado y la salida es parcial.
    assert p.returncode == 3, salida
    assert salida["resultado"]["estado"] == "parcial" and salida["resultado"]["hitos_examinados"] == 0
    assert salida["resultado"]["listos"] == []
    assert any("PL-001-H3: formato heredado" in a for a in salida["advertencias"])
    assert salida["cobertura"]["heredados"] == 1


def reescribir(carpeta, nombre, antes, despues):
    ruta = carpeta / nombre
    ruta.write_text(ruta.read_text(encoding="utf-8").replace(antes, despues, 1), encoding="utf-8", newline="\n")


def test_un_heredado_sin_id_valido_no_desaparece(tmp_path):
    carpeta = corpus(tmp_path / "docs", "PL-001-H3.md", "PL-001-H5.md")
    reescribir(carpeta, "PL-001-H3.md", "id: PL-001-H3\n", "")
    reescribir(carpeta, "PL-001-H5.md", "id: PL-001-H5", "id: 123")
    snapshot, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert snapshot.heredados == {} and cobertura["estado"] == "parcial"
    assert {i["ruta"] for i in cobertura["invalidos"]} == {"docs/PL-001-H3.md", "docs/PL-001-H5.md"}
    assert listos(snapshot, **C)["listos"] == []  # un id que no es texto no rompe la consulta


def test_dos_heredados_con_el_mismo_id_bloquean_y_lo_dicen(tmp_path):
    carpeta = corpus(tmp_path / "docs", "PL-001-H3.md", "PL-001-H5.md")
    reescribir(carpeta, "PL-001-H5.md", "id: PL-001-H5", "id: PL-001-H3")
    _, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert cobertura["estado"] == "bloqueado"
    assert any("PL-001-H3" in h["mensaje"] and "formato heredado" in h["mensaje"] for h in cobertura["hallazgos"])


def test_la_condicion_se_comprueba_antes_que_el_formato(tmp_path):
    corpus(tmp_path / "docs", ADR)
    snapshot, _ = cargar(tmp_path, "docs", heredados=True)
    hito = registro("hito", depende_de=[{"destino": "ADR-0063", "condicion": "resuelta"}])
    [dep] = evaluar(hito, snapshot, **C)
    assert not dep["satisfecha"] and dep["codigo"] == "ESQUEMA_INVALIDO"


def test_una_referencia_del_perfil_a_un_heredado_lo_dice(tmp_path):
    carpeta = corpus(tmp_path / "docs", ADR)
    r, c = decision("DEC-B", {"C1": "Martes."}, depende_de=[{"destino": "ADR-0063", "condicion": "aceptada_y_vigente"}])
    (carpeta / "DEC-B.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")
    _, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert any("ADR-0063 está en formato heredado" in h["mensaje"] for h in cobertura["hallazgos"])


def test_cli_consolidar_una_heredada_no_se_da_por_resuelto(tmp_path):
    corpus(tmp_path / "docs", ADR)
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "kbol.cli",
            "consolidar",
            "--heredados",
            "--ids",
            "ADR-0063",
            "--valido-en",
            C["valido_en"],
            "--carpeta",
            "docs",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    salida = json.loads(p.stdout)
    assert p.returncode == 3 and salida["resultado"]["estado"] == "parcial"
    assert [f["id"] for f in salida["resultado"]["heredados"]] == ["ADR-0063"]


def test_desde_una_revision_de_git(tmp_path):
    corpus(tmp_path / "docs", ADR)
    for orden in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *orden], check=True, capture_output=True)
    snapshot, cobertura = cargar(tmp_path, "docs", revision="HEAD", heredados=True)
    assert set(snapshot.heredados) == {"ADR-0063"} and snapshot.heredados["ADR-0063"]["ruta"] == f"docs/{ADR}"
    assert cobertura["estado"] == "completo"


def test_un_documento_con_type_de_registro_sin_id_ni_nombre_de_registro_se_omite(tmp_path):
    carpeta = corpus(tmp_path / "docs")
    for nombre in ("PLAN.md", "2026-02-18-quickstart.md"):
        (carpeta / nombre).write_text("---\ntype: Plan\ntitle: Plan de trabajo\n---\n\n# Plan\n", encoding="utf-8")
    snapshot, cobertura = cargar(tmp_path, "docs", heredados=True)
    assert snapshot.heredados == {} and cobertura["invalidos"] == [] and cobertura["omitidos"] == 2


def test_las_lecturas_de_contexto_y_desvios_cuentan_los_heredados_y_no_quedan_parciales(tmp_path):
    """Mientras quedan heredados, una referencia a uno no deja parcial el paquete de contexto ni los desvíos."""
    from kbol.contexto import preparar_contexto
    from kbol.huellas import desvios

    carpeta = corpus(tmp_path / "docs", ADR)
    r, c = decision("DEC-B", {"C1": "Martes."}, afecta_a=["ADR-0063"])
    (carpeta / "DEC-B.md").write_text(serializar(r, c, modo="canonico"), encoding="utf-8", newline="\n")
    paquete = preparar_contexto(
        tmp_path,
        tarea="t",
        objetivo="o",
        ambito="operaciones",
        carpeta="docs",
        instalacion={},
        valido_en=C["valido_en"],
    )
    assert paquete["cobertura"]["estado"] != "parcial", paquete["cobertura"]
    assert desvios(tmp_path, "docs")["cobertura"]["estado"] == "completo"
