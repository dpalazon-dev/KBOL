"""La carpeta navegable de un documento, generada desde su DoclingDocument y su estructura."""

import base64

import pytest
import yaml
from di.generica import estructura_generica
from di.proyectar import CarpetaAjena, proyectar
from test_contexto import _paper
from test_generica import SHA, _caja

# PNG de 1x1 píxel
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _con_figura(doc):
    doc["texts"].append(
        {"self_ref": "#/texts/10", "label": "caption", "text": "Figure 1: Arquitectura", "children": [],
         "prov": [{"page_no": 1, "bbox": _caja(0.1, 0.62, 0.9, 0.64)}]}
    )
    doc["pictures"].append(
        {"self_ref": "#/pictures/0", "label": "picture", "children": [{"$ref": "#/texts/10"}],
         "prov": [{"page_no": 1, "bbox": _caja(0.1, 0.65, 0.9, 0.9)}],
         "image": {"uri": "data:image/png;base64," + base64.b64encode(PNG).decode(), "mimetype": "image/png"}}
    )
    doc["body"]["children"].insert(6, {"$ref": "#/pictures/0"})
    doc["texts"][5]["text"] += " La Figure 1 muestra la arquitectura."
    return doc


def _cabecera(ruta):
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith("---\n")
    cabecera, cuerpo = texto[4:].split("\n---\n", 1)
    return yaml.safe_load(cabecera), cuerpo


@pytest.fixture
def carpeta(tmp_path):
    doc = _con_figura(_paper())
    est = estructura_generica(doc, SHA)
    res = proyectar(doc, est, b"%PDF original", "paper.pdf", "paper", tmp_path, estructura_sha256="e" * 64)
    return tmp_path / "paper", res


def test_carpeta_con_original_indice_contenidos_y_recursos(carpeta):
    raiz, res = carpeta
    assert (raiz / "paper.pdf").read_bytes() == b"%PDF original"
    assert (raiz / "index.md").exists()
    nombres = sorted(p.name for p in (raiz / "contenidos").iterdir())
    assert nombres == [
        "01-deteccion-de-anomalias.md",
        "02-abstract.md",
        "03-5-experiments-and-results.md",
        "04-5-3-training-time.md",
        "05-references.md",
    ]
    assert (raiz / "recursos" / "tablas" / "tabla-1.md").exists()
    assert (raiz / "recursos" / "figuras" / "figura-1.png").read_bytes() == PNG
    assert (raiz / "recursos" / "bibliografia.md").exists()
    assert res["contenidos"] == 5 and res["tablas"] == 1 and res["figuras"] == 1


def test_cada_contenido_lleva_su_contexto_en_la_cabecera(carpeta):
    raiz, _ = carpeta
    meta, cuerpo = _cabecera(raiz / "contenidos" / "04-5-3-training-time.md")
    assert meta["id"] == "paper#seccion=4"
    assert meta["type"] == "seccion" and meta["documento"] == "paper"
    assert meta["title"] == "5.3 Training time" and meta["numero"] == "5.3"
    assert meta["ruta"] == ["5 EXPERIMENTS AND RESULTS", "5.3 Training time"]
    assert meta["tipo"] == "experimentos" and meta["padre"] == "paper#seccion=3"
    assert meta["paginas"] == [1]
    assert meta["referencias"] == ["2", "1"]
    assert meta["recursos"] == ["tabla-1", "figura-1"]
    assert meta["origen"]["estructura_sha256"] == "e" * 64
    assert meta["origen"]["unidades"] == ["seccion=4;pagina=1", "seccion=4;tabla=1", "seccion=4;figura=1"]
    assert meta["generated"]["by"].startswith("kbol-di/proyectar")
    assert meta["description"].startswith("Seguimos el protocolo")


def test_el_cuerpo_conserva_el_texto_y_marca_paginas_referencias_y_recursos(carpeta):
    raiz, _ = carpeta
    _, cuerpo = _cabecera(raiz / "contenidos" / "04-5-3-training-time.md")
    assert cuerpo.lstrip().startswith("# 5.3 Training time")
    assert '<pagina n="1"/>' in cuerpo
    assert 'Seguimos el protocolo de <ref clave="2">[2]</ref> y <ref clave="1">[1]</ref>' in cuerpo
    assert '<recurso tipo="tabla" id="tabla-1" ref="../recursos/tablas/tabla-1.md">Tabla 1: Resultados</recurso>' in cuerpo
    assert '<recurso tipo="figura" id="figura-1" ref="../recursos/figuras/figura-1.md">Figure 1: Arquitectura</recurso>' in cuerpo


def test_el_padre_lista_a_sus_hijos(carpeta):
    raiz, _ = carpeta
    meta, _ = _cabecera(raiz / "contenidos" / "03-5-experiments-and-results.md")
    assert meta["hijos"] == ["paper#seccion=4"]


def test_la_tabla_trae_su_markdown_y_cada_dato_con_su_contexto(carpeta):
    raiz, _ = carpeta
    meta, cuerpo = _cabecera(raiz / "recursos" / "tablas" / "tabla-1.md")
    assert meta["id"] == "paper#tabla-1" and meta["type"] == "tabla"
    assert meta["seccion"] == "paper#seccion=4" and meta["unidad"] == "seccion=4;tabla=1"
    assert meta["title"] == "Tabla 1: Resultados"
    assert "| USAD" in cuerpo
    assert "- USAD · SWaT › Sin ajuste = 0.7917 (pág. 1)" in cuerpo


def test_la_figura_trae_su_imagen_y_su_leyenda(carpeta):
    raiz, _ = carpeta
    meta, cuerpo = _cabecera(raiz / "recursos" / "figuras" / "figura-1.md")
    assert meta["type"] == "figura" and meta["imagen"] == "figura-1.png"
    assert "![Figure 1: Arquitectura](figura-1.png)" in cuerpo


def test_bibliografia_con_sus_claves(carpeta):
    raiz, _ = carpeta
    _, cuerpo = _cabecera(raiz / "recursos" / "bibliografia.md")
    assert '<entrada clave="2">Goh et al. 2017. SWaT.</entrada>' in cuerpo


def test_el_indice_describe_el_documento_y_enlaza_todo(carpeta):
    raiz, _ = carpeta
    meta, cuerpo = _cabecera(raiz / "index.md")
    assert meta["id"] == "paper" and meta["type"] == "documento"
    assert meta["title"] == "Detección de anomalías"
    assert meta["original"] == {"fichero": "paper.pdf", "sha256": SHA, "paginas": 2}
    assert meta["representacion"]["estructura_sha256"] == "e" * 64
    assert "- [5.3 Training time](contenidos/04-5-3-training-time.md)" in cuerpo
    assert "[Tabla 1: Resultados](recursos/tablas/tabla-1.md)" in cuerpo
    assert "[Figure 1: Arquitectura](recursos/figuras/figura-1.md)" in cuerpo


def test_volver_a_proyectar_sustituye_la_carpeta_generada(tmp_path):
    doc = _paper()
    est = estructura_generica(doc, SHA)
    proyectar(doc, est, b"%PDF", "paper.pdf", "paper", tmp_path)
    (tmp_path / "paper" / "contenidos" / "sobrante.md").write_text("x", encoding="utf-8")
    proyectar(doc, est, b"%PDF", "paper.pdf", "paper", tmp_path)
    assert not (tmp_path / "paper" / "contenidos" / "sobrante.md").exists()


def test_no_borra_una_carpeta_que_no_generó(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "notas.md").write_text("mías", encoding="utf-8")
    doc = _paper()
    with pytest.raises(CarpetaAjena):
        proyectar(doc, estructura_generica(doc, SHA), b"%PDF", "paper.pdf", "paper", tmp_path)
    assert (tmp_path / "paper" / "notas.md").read_text(encoding="utf-8") == "mías"


def test_documento_sin_paginas_lleva_las_lineas_de_cada_seccion_en_su_markdown(tmp_path):
    """Un Word: sin páginas ni posiciones; cada sección dice qué líneas ocupa en su Markdown, que es lo que se cita."""
    from test_generica import _doc

    textos = [
        {"self_ref": "#/texts/0", "label": "title", "text": "Plan de ingeniería", "prov": [], "children": []},
        {"self_ref": "#/texts/1", "label": "section_header", "text": "1 Objetivo", "prov": [], "children": []},
        {"self_ref": "#/texts/2", "label": "text", "text": "Detectar fugas.", "prov": [], "children": []},
        {"self_ref": "#/texts/3", "label": "section_header", "text": "2 Riesgos", "prov": [], "children": []},
        {"self_ref": "#/texts/4", "label": "text", "text": "El piloto no cubre Murcia.", "prov": [], "children": []},
    ]
    doc = _doc([f"#/texts/{i}" for i in range(5)], textos, paginas=0)
    markdown = "\n".join(
        ["# Plan de ingeniería", "", "## 1 Objetivo", "", "Detectar fugas.", "", "## 2 Riesgos", "",
         "El piloto no cubre Murcia.", ""]
    )
    est = estructura_generica(doc, SHA)
    assert [u["clave"] for u in est["unidades"]] == ["seccion=1", "seccion=2", "seccion=3"]
    proyectar(doc, est, b"PK", "plan.docx", "plan", tmp_path, markdown=markdown, markdown_sha256="m" * 64)
    meta, cuerpo = _cabecera(tmp_path / "plan" / "contenidos" / "03-2-riesgos.md")
    assert meta["lineas"] == [7, 9] and meta["paginas"] == []
    assert markdown.split("\n")[8] == "El piloto no cubre Murcia."
    assert meta["origen"]["markdown_sha256"] == "m" * 64
    assert "<pagina" not in cuerpo
    assert (tmp_path / "plan" / "plan.docx").read_bytes() == b"PK"


def test_el_nombre_no_puede_salir_de_la_carpeta_de_destino(tmp_path):
    doc = _paper()
    est = estructura_generica(doc, SHA)
    for nombre in ("../fuera", "a/b", "", ".."):
        with pytest.raises(ValueError, match="nombre de carpeta"):
            proyectar(doc, est, b"%PDF", "paper.pdf", nombre, tmp_path / "documentos")
    assert not (tmp_path / "fuera").exists()
