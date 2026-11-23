import hashlib
from pathlib import Path

import pytest
from di.almacen import ErrorDeIntegridad, almacen_por_defecto, capturar, leer


def test_captura_idempotente(tmp_path):
    origen = tmp_path / "norma.pdf"
    origen.write_bytes(b"%PDF original")
    almacen = tmp_path / "almacen"
    primera = capturar(origen, almacen, medio="application/pdf")
    segunda = capturar(origen, almacen, medio="application/pdf")
    assert primera == segunda
    assert primera["sha256"] == hashlib.sha256(b"%PDF original").hexdigest()
    assert leer(primera["sha256"], almacen) == b"%PDF original"


def test_otro_origen_mismos_bytes_se_anota(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    a.write_bytes(b"mismo")
    b.write_bytes(b"mismo")
    almacen = tmp_path / "almacen"
    capturar(a, almacen)
    meta = capturar(b, almacen)
    assert meta["origenes"] == [str(a), str(b)]


def test_objeto_alterado_se_detecta(tmp_path):
    origen = tmp_path / "n.pdf"
    origen.write_bytes(b"bytes buenos")
    almacen = tmp_path / "almacen"
    meta = capturar(origen, almacen)
    (almacen / meta["ruta"]).write_bytes(b"bytes malos")
    with pytest.raises(ErrorDeIntegridad):
        leer(meta["sha256"], almacen)
    with pytest.raises(ErrorDeIntegridad):
        capturar(origen, almacen)


def test_almacen_por_defecto_en_el_estado_local(tmp_path, monkeypatch):
    monkeypatch.delenv("KBOL_ALMACEN", raising=False)
    monkeypatch.delenv("KBOL_REPOSITORIO", raising=False)
    monkeypatch.setenv("KBOL_ESTADO", str(tmp_path))
    assert almacen_por_defecto() == tmp_path / "predeterminado" / "almacen"
    monkeypatch.delenv("KBOL_ESTADO")
    assert almacen_por_defecto() == Path.home() / ".kbol" / "predeterminado" / "almacen"
    monkeypatch.setenv("KBOL_ALMACEN", str(tmp_path / "otro"))
    assert almacen_por_defecto() == tmp_path / "otro"


def test_almacen_de_otra_instalacion_por_su_repositorio(tmp_path, monkeypatch):
    monkeypatch.delenv("KBOL_ALMACEN", raising=False)
    monkeypatch.setenv("KBOL_ESTADO", str(tmp_path))
    monkeypatch.setenv("KBOL_REPOSITORIO", "otro-proyecto")
    assert almacen_por_defecto() == tmp_path / "otro-proyecto" / "almacen"
    monkeypatch.setenv("KBOL_REPOSITORIO", "../fuera")
    with pytest.raises(ValueError, match="KBOL_REPOSITORIO"):
        almacen_por_defecto()
