"""Consulta por ID: lo que una memoria o una nota necesita para vincularse a lo canónico."""

import json
import subprocess
import sys

from conftest import decision, registro
from test_integrar import activo

from kbol.consultar import consultar
from kbol.core import serializar
from kbol.proyeccion import Snapshot

T = "2026-11-06T00:00:00Z"


def snap():
    a, ca = decision("DEC-A", {"C1": "Lunes.", "C2": "Martes."}, autorizado_por=["ROL-EJEMPLO"])
    b, cb = decision(
        "DEC-B",
        {"C1": "Miércoles."},
        registrado="2026-11-03T00:00:00Z",
        autorizado_por=["ROL-EJEMPLO"],
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
    )
    heredada = {"id": "ADR-0001", "tipo": "decision", "ruta": "docs/0001.md", "estado_heredado": "Aceptada"}
    heredada["estado_propuesto"] = "aceptada"
    return Snapshot(
        {"DEC-A": a, "DEC-B": b},
        "r1",
        {"DEC-A": ca, "DEC-B": cb},
        {"DEC-A": "kb/DEC-A.md", "DEC-B": "kb/DEC-B.md"},
        {"ADR-0001": heredada},
    )


def uno(ref):
    return consultar(snap(), [ref], valido_en=T, conocido_hasta=None)["resultados"][0]


def test_un_id_canonico_devuelve_tipo_estado_y_autoridad_sin_comprobar():
    r = uno("DEC-A")
    assert r["encontrado"] == "canonico" and r["tipo"] == "decision" and r["estado"] == "aceptada"
    assert r["ruta"] == "kb/DEC-A.md" and r["autoridad"]["comprobada"] is False
    assert r["autoridad"]["ratificaciones"] == ["AP-DEC-A"]


def test_un_ancla_devuelve_su_texto_y_si_rige():
    vigente, sustituida = uno("DEC-A#C2"), uno("DEC-A#C1")
    assert vigente["texto"] == "Martes." and vigente["clausula"]["estado"] == "vigente"
    assert sustituida["texto"] == "Lunes."
    assert sustituida["clausula"]["texto"] == "Miércoles." and sustituida["clausula"]["origen"] == "DEC-B#C1"


def test_un_ancla_que_no_existe_se_dice():
    assert uno("DEC-A#C9")["encontrado"] == "ancla_ausente"


def test_un_id_heredado_se_nombra_y_no_rige():
    r = uno("ADR-0001")
    assert r["encontrado"] == "heredado" and r["rige"] is False and r["estado_heredado"] == "Aceptada"


def test_un_id_ausente_se_dice_con_aviso():
    salida = consultar(snap(), ["DEC-Z"], valido_en=T, conocido_hasta=None)
    assert salida["resultados"][0]["encontrado"] == "ausente"
    assert any("DEC-Z" in a for a in salida["advertencias"])


def test_una_cita_a_una_fuente_que_falta_es_evidencia_insuficiente():
    s = snap()
    q = registro("pregunta", id="Q-A", basada_en=["F-NO"])
    s.registros["Q-A"], s.cuerpos["Q-A"] = q, "Texto."
    salida = consultar(s, ["Q-A"], valido_en=T, conocido_hasta=None)
    evidencia = salida["resultados"][0]["evidencia"]
    assert [(a["ref"], a["campo"], a["existe"], a["situacion"]) for a in evidencia["apoyos"]] == [
        ("F-NO", "basada_en", False, "ausente")
    ]
    assert evidencia["suficiente"] is False and "F-NO ausente" in evidencia["motivo"]
    assert any("EVIDENCIA_INSUFICIENTE" in a and "F-NO" in a for a in salida["advertencias"])


def test_la_cli_consulta_por_id(tmp_path):
    a, ca = decision("DEC-A", {"C1": "Lunes."}, autorizado_por=["ROL-EJEMPLO"])
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "DEC-A.md").write_text(serializar(a, ca, modo="canonico"), encoding="utf-8", newline="\n")
    rol = activo("rol", "ROL-EJEMPLO", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    (tmp_path / "kb" / "ROL-EJEMPLO.md").write_text(
        serializar(rol, "", modo="canonico"), encoding="utf-8", newline="\n"
    )
    salida = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "consultar", str(tmp_path), "--carpeta", "kb", "--ids", "DEC-A#C1"]
        + ["--valido-en", T],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    datos = json.loads(salida.stdout)
    assert salida.returncode == 0, salida.stdout + salida.stderr
    assert datos["resultado"]["resultados"][0]["texto"] == "Lunes."
    sin_reloj = subprocess.run(
        [sys.executable, "-m", "kbol.cli", "consultar", str(tmp_path), "--carpeta", "kb", "--ids", "DEC-A"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert sin_reloj.returncode == 2


def test_una_cita_a_un_hecho_que_existe_pero_no_rige_es_evidencia_insuficiente():
    """Existir no basta; el apoyo tiene que regir en el corte."""
    s = snap()
    s.registros["HE-A"], s.cuerpos["HE-A"] = registro("hecho", id="HE-A"), ""  # existe, sin historial admitido
    q = registro("pregunta", id="Q-A")
    s.registros["Q-A"], s.cuerpos["Q-A"] = q, 'Se mide <hecho ref="HE-A">el caudal</hecho>.'
    salida = consultar(s, ["Q-A"], valido_en=T, conocido_hasta=None)
    evidencia = salida["resultados"][0]["evidencia"]
    (apoyo,) = evidencia["apoyos"]
    assert (apoyo["campo"], apoyo["existe"], apoyo["situacion"]) == ("cuerpo", True, "no_rige")
    assert evidencia["suficiente"] is False and "HE-A no_rige" in evidencia["motivo"]
    assert any("EVIDENCIA_INSUFICIENTE" in a and "HE-A" in a for a in salida["advertencias"])


def test_una_cita_a_una_clausula_vigente_es_evidencia_suficiente():
    s = snap()
    s.registros["Q-A"], s.cuerpos["Q-A"] = registro("pregunta", id="Q-A", basada_en=["DEC-A#C2"]), ""
    evidencia = consultar(s, ["Q-A"], valido_en=T, conocido_hasta=None)["resultados"][0]["evidencia"]
    assert evidencia["suficiente"] is True and evidencia["apoyos"][0]["situacion"] == "rige"


def test_la_autoridad_dice_quien_aprobo_cuando_y_con_que_palabras():
    # Línea base del banco, P05 y P06: el registro conserva la aprobación, pero la consulta solo daba su ID.
    a, ca = decision("DEC-A", {"C1": "Lunes."}, autorizado_por=["ROL-EJEMPLO"])
    a["eventos"][1]["aprobacion"]["comprobante"] = {
        "mecanismo": "declarada",
        "sesion": "sesión de prueba",
        "instante": "2026-11-01T00:00:00Z",
        "cita": "Apruebo",
        "autenticada": False,
    }
    s = Snapshot({"DEC-A": a}, "r1", {"DEC-A": ca}, {"DEC-A": "kb/DEC-A.md"}, {})
    r = consultar(s, ["DEC-A"], valido_en=T, conocido_hasta=None)["resultados"][0]
    assert r["autoridad"]["aprobaciones"] == [
        {
            "aprobacion_id": "AP-DEC-A",
            "actor": "human:david",
            "roles": ["ROL-EJEMPLO"],
            "aprobada_en": a["eventos"][1]["aprobacion"]["aprobada_en"],
            "mecanismo": "declarada",
            "cita": "Apruebo",
            "autenticada": False,
        }
    ]
    assert r["autoridad"]["comprobada"] is False


def test_una_aprobacion_con_comprobante_sin_detalle_no_inventa_cita():
    r = uno("DEC-A")
    (aprobacion,) = r["autoridad"]["aprobaciones"]
    assert aprobacion["actor"] == "human:david" and aprobacion["cita"] is None and aprobacion["autenticada"] is None
