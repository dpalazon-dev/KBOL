"""La cadena completa de un PDF, con Docling y pypdf sustituidos por dobles en su frontera."""

import json

from di import contraste
from di import incorporar as modulo
from di.almacen import guardar, leer
from di.localizar import localizar
from test_generica import _informe

from kbol.citas import resolver_pdf
from kbol.localizador import parsear

PAGINAS = {
    1: "Informe de rendimiento\nEste informe resume las mediciones de la campaña.\n1 Resultados\n"
    "El método reduce el tiempo de entrenamiento 547 veces de media.\nConjunto Muestras\nSWaT 496800\n"
    "Tabla 1: Conjuntos de datos\nPágina 1 de 2",
    2: "2 Conclusiones\nNo se observaron regresiones.",
}


def _docling_de_prueba(huella, almacen, extension=".pdf"):
    datos = json.dumps(_informe(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    sha, _ = guardar(datos, almacen)
    return {"sha256": sha, "derivada_de": huella, "procesador": "docling", "version": "prueba", "paginas": 2}


def _incorporar(tmp_path, monkeypatch, paginas=PAGINAS):
    monkeypatch.setattr(modulo, "procesar", _docling_de_prueba)
    monkeypatch.setattr(contraste, "texto_por_pagina", lambda datos: paginas)
    origen = tmp_path / "informe.pdf"
    origen.write_bytes(b"%PDF-1.7 informe")
    almacen = tmp_path / "almacen"
    return modulo.incorporar(origen, almacen), almacen, origen


def test_incorporar_deja_una_representacion_que_el_resolutor_acepta(tmp_path, monkeypatch):
    res, almacen, origen = _incorporar(tmp_path, monkeypatch)
    assert res["revisar"] == []
    assert res["estructura"]["derivada_de"] == res["docling"]["sha256"]
    assert res["estructura"]["original"] == res["original"]["sha256"]
    estructura = json.loads(leer(res["estructura"]["sha256"], almacen))
    doc = json.loads(leer(res["docling"]["sha256"], almacen))
    literal = "reduce el tiempo de entrenamiento 547 veces"
    region = localizar(doc, literal)[0][0]
    ancla = f"pdf-v1:p={region['p']};r={','.join(region['r'])}"
    r = resolver_pdf(
        parsear(ancla), sha256_original=res["original"]["sha256"], ruta_original=origen, estructura=estructura, literal=literal
    )
    assert r.estado == "resuelta"
    informe = json.loads(leer(res["contraste"]["sha256"], almacen))
    assert informe["entradas"]["estructura"] == res["estructura"]["sha256"]


def test_incorporar_dice_que_revisar_cuando_el_pdf_tiene_una_cifra_que_la_estructura_no(tmp_path, monkeypatch):
    paginas = {**PAGINAS, 1: PAGINAS[1] + "\nWADI 1048571"}
    res, _, _ = _incorporar(tmp_path, monkeypatch, paginas)
    assert any("cifras: 1 del PDF ausentes" in aviso for aviso in res["revisar"])


def test_incorporar_dos_veces_el_mismo_pdf_no_duplica_nada(tmp_path, monkeypatch):
    primera, almacen, _ = _incorporar(tmp_path, monkeypatch)
    objetos = sorted(p.name for p in (almacen / "sha256").iterdir())
    segunda, _, _ = _incorporar(tmp_path, monkeypatch)
    assert sorted(p.name for p in (almacen / "sha256").iterdir()) == objetos
    assert segunda["estructura"]["sha256"] == primera["estructura"]["sha256"]


def test_incorporar_con_nombre_genera_la_carpeta_del_documento(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "procesar", _docling_de_prueba)
    monkeypatch.setattr(contraste, "texto_por_pagina", lambda datos: PAGINAS)
    origen = tmp_path / "informe.pdf"
    origen.write_bytes(b"%PDF-1.7 informe")
    res = modulo.incorporar(origen, tmp_path / "estado" / "almacen", nombre="informe")
    carpeta = tmp_path / "estado" / "documentos" / "informe"
    assert res["carpeta"]["carpeta"] == str(carpeta)
    assert (carpeta / "informe.pdf").read_bytes() == b"%PDF-1.7 informe"
    assert (carpeta / "index.md").exists() and (carpeta / "recursos" / "tablas" / "tabla-1.md").exists()


def test_html_pasa_por_markitdown_y_se_cita_por_lineas(tmp_path):
    origen = tmp_path / "aviso.html"
    origen.write_text(
        "<html><body><h1>Aviso de seguridad</h1><p>El fabricante no corregirá la vulnerabilidad.</p></body></html>",
        encoding="utf-8",
    )
    almacen = tmp_path / "almacen"
    res = modulo.incorporar(origen, almacen)
    assert "docling" not in res and "estructura" not in res
    markdown = leer(res["markdown"]["sha256"], almacen).decode("utf-8")
    assert "# Aviso de seguridad" in markdown and "no corregirá la vulnerabilidad" in markdown
    assert res["markdown"]["derivada_de"] == res["original"]["sha256"]
    assert res["original"]["medio"] == "text/html"


def test_formato_no_admitido(tmp_path):
    import pytest

    origen = tmp_path / "nota.txt"
    origen.write_text("hola", encoding="utf-8")
    with pytest.raises(ValueError, match="formato no admitido"):
        modulo.incorporar(origen, tmp_path / "almacen")


def test_un_origen_sin_extension_entra_como_pdf(tmp_path, monkeypatch):
    """La URL de un PDF en EUR-Lex no trae extensión: se trata como PDF, igual que antes de admitir otros formatos."""
    vistos = []

    def procesar(huella, almacen, extension=".pdf"):
        vistos.append(extension)
        return _docling_de_prueba(huella, almacen, extension)

    monkeypatch.setattr(modulo, "procesar", procesar)
    monkeypatch.setattr(contraste, "texto_por_pagina", lambda datos: PAGINAS)
    origen = tmp_path / "CELEX-32024R2847"
    origen.write_bytes(b"%PDF-1.7 norma")
    res = modulo.incorporar(origen, tmp_path / "almacen")
    assert vistos == [".pdf"] and res["original"]["medio"] == "application/pdf" and "contraste" in res


def test_el_formato_declarado_manda_sobre_la_extension(tmp_path):
    origen = tmp_path / "aviso.php"
    origen.write_text("<html><body><h1>Aviso</h1><p>Sin parche.</p></body></html>", encoding="utf-8")
    almacen = tmp_path / "almacen"
    res = modulo.incorporar(origen, almacen, formato="html")
    assert res["original"]["medio"] == "text/html"
    assert "# Aviso" in leer(res["markdown"]["sha256"], almacen).decode("utf-8")
    import pytest

    with pytest.raises(ValueError, match="formato no admitido"):
        modulo.incorporar(origen, almacen, formato="txt")
