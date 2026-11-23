"""Muestra de calibración: lo que entró sin aprobación se revisa por muestra, y solo se lee."""

import importlib.util
import json
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "tools" / "calibracion" / "muestra.py"
_spec = importlib.util.spec_from_file_location("muestra_de_calibracion", RUTA)
calibracion = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calibracion)


def recibo(carpeta, op, registros, decisivos, modo="decisiva", estado="integrado", registrado="2026-11-10T10:00:00Z"):
    datos = {
        "operacion_id": op,
        "estado": estado,
        "modo_aprobacion": modo,
        "registros": registros,
        "decisivos": decisivos,
        "revision_integrada": "a" * 40,
        "registrado_en": registrado,
        "actor": "claude-code/fable-5.2",
    }
    (carpeta / f"{op}.json").write_text(json.dumps(datos), encoding="utf-8")


def test_solo_entra_en_la_muestra_lo_que_no_pidio_aprobacion(tmp_path):
    recibo(tmp_path, "op-1", ["DEC-A", "Q-1", "Q-2"], ["DEC-A"])
    recibo(tmp_path, "op-2", ["DEC-B"], [], modo="toda")
    recibo(tmp_path, "op-3", ["Q-3"], [], estado="bloqueado")
    sin_aprobacion, leidos, ilegibles = calibracion.candidatos(tmp_path)
    assert [(c["operacion_id"], c["id"]) for c in sin_aprobacion] == [("op-1", "Q-1"), ("op-1", "Q-2")]
    assert leidos == 2 and ilegibles == []


def test_la_muestra_es_determinista_y_no_depende_del_orden(tmp_path):
    recibo(tmp_path, "op-1", [f"Q-{i}" for i in range(30)], [])
    sin_aprobacion, _, _ = calibracion.candidatos(tmp_path)
    una = calibracion.muestra(sin_aprobacion, 5)
    otra = calibracion.muestra(list(reversed(sin_aprobacion)), 5)
    assert una == otra and len(una) == 5
    assert una != sin_aprobacion[:5]


def test_sin_nada_que_muestrear_lo_dice_y_no_sale_con_cero(tmp_path, capsys):
    recibo(tmp_path, "op-1", ["DEC-A"], ["DEC-A"], modo="toda")
    assert calibracion.main([str(tmp_path)]) == 3
    assert "ningún registro entró sin aprobación" in capsys.readouterr().err


def test_escribe_la_hoja_y_no_toca_los_recibos(tmp_path):
    recibos = tmp_path / "recibos"
    recibos.mkdir()
    recibo(recibos, "op-1", ["Q-1"], [])
    (recibos / "roto.json").write_text("{", encoding="utf-8")
    antes = {p.name: p.read_bytes() for p in recibos.iterdir()}
    salida = tmp_path / "hoja.md"
    assert calibracion.main([str(recibos), "--salida", str(salida)]) == 0
    texto = salida.read_text(encoding="utf-8")
    assert "| op-1 | Q-1 |" in texto and "roto.json" in texto
    assert {p.name: p.read_bytes() for p in recibos.iterdir()} == antes


def test_desde_deja_fuera_los_recibos_anteriores(tmp_path):
    recibo(tmp_path, "op-1", ["Q-1"], [], registrado="2026-10-01T00:00:00Z")
    recibo(tmp_path, "op-2", ["Q-2"], [], registrado="2026-11-10T00:00:00Z")
    sin_aprobacion, _, _ = calibracion.candidatos(tmp_path, desde="2026-11-01T00:00:00Z")
    assert [c["id"] for c in sin_aprobacion] == ["Q-2"]


def test_una_carpeta_que_no_existe_es_un_error(tmp_path):
    assert calibracion.main([str(tmp_path / "no-existe")]) == 1
