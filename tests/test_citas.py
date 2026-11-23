import hashlib
import json
import subprocess

import pytest

from kbol.citas import comprobar, normalizar, resolver_lineas, resolver_pdf
from kbol.cli import main
from kbol.localizador import parsear

ORIGINAL = b"%PDF-1.7 original de prueba"
SHA_ORIGINAL = hashlib.sha256(ORIGINAL).hexdigest()


def _estructura(**cambios):
    est = {
        "perfil": "estructura-v1",
        "original_sha256": SHA_ORIGINAL,
        "paginas": [{"p": 1, "ancho": 595.0, "alto": 842.0}, {"p": 2, "ancho": 595.0, "alto": 842.0}],
        "unidades": [
            {
                "clave": "art=14",
                "paginas": [1, 2],
                "regiones": [{"p": 1, "r": ["0.1", "0.5", "0.9", "0.9"]}, {"p": 2, "r": ["0.1", "0.1", "0.9", "0.3"]}],
                "texto": "Artículo 14\n1. El fabricante notificará simultáneamente al CSIRT. 2. La obli-\ngación «no» cesa.",
            },
            {
                "clave": "art=14;ap=2",
                "paginas": [2],
                "regiones": [{"p": 2, "r": ["0.1", "0.1", "0.9", "0.3"]}],
                "texto": "2. La obli-\ngación «no» cesa.",
            },
            {"clave": "art=2", "paginas": [1], "regiones": [], "texto": "Artículo 2 Ámbito"},
            {"clave": "art=2", "paginas": [2], "regiones": [], "texto": "Artículo 2 citado en un anexo"},
        ],
    }
    est.update(cambios)
    return est


@pytest.fixture
def original(tmp_path):
    ruta = tmp_path / "orig.pdf"
    ruta.write_bytes(ORIGINAL)
    return ruta


def _pdf(ancla, original, literal=None, estructura=None, sha=SHA_ORIGINAL):
    return resolver_pdf(
        parsear(ancla),
        sha256_original=sha,
        ruta_original=original,
        estructura=estructura or _estructura(),
        literal=literal,
    )


def test_resuelta(original):
    r = _pdf("norma-v1:art=14;ap=2 @ pdf-v1:p=2;r=0.2,0.15,0.5,0.2", original, literal="La obligación «no» cesa")
    assert r.estado == "resuelta", r.motivo


def test_original_ausente_es_no_comprobable(tmp_path):
    r = _pdf("norma-v1:art=14 @ pdf-v1:p=1", tmp_path / "no-existe.pdf")
    assert r.estado == "no_comprobable"
    r = _pdf("norma-v1:art=14 @ pdf-v1:p=1", None)
    assert r.estado == "no_comprobable"


def test_huella_distinta_es_rota(tmp_path):
    otro = tmp_path / "otro.pdf"
    otro.write_bytes(b"otros bytes")
    assert _pdf("norma-v1:art=14 @ pdf-v1:p=1", otro).estado == "rota"


def test_representacion_de_otro_original(original):
    est = _estructura(original_sha256="0" * 64)
    assert _pdf("norma-v1:art=14 @ pdf-v1:p=1", original, estructura=est).estado == "rota"


def test_pagina_inexistente(original):
    assert _pdf("norma-v1:art=14 @ pdf-v1:p=9", original).estado == "rota"


def test_unidad_ausente(original):
    assert _pdf("norma-v1:art=15 @ pdf-v1:p=1", original).estado == "rota"


def test_unidad_en_otra_pagina_es_inconsistente(original):
    assert _pdf("norma-v1:art=14;ap=2 @ pdf-v1:p=1", original).estado == "inconsistente"


def test_region_fuera_de_la_unidad_es_inconsistente(original):
    r = _pdf("norma-v1:art=14;ap=2 @ pdf-v1:p=2;r=0.1,0.6,0.9,0.8", original)
    assert r.estado == "inconsistente"


def test_clave_repetida_es_ambigua(original):
    assert _pdf("norma-v1:art=2 @ pdf-v1:p=1", original).estado == "ambigua"


def test_literal_ausente_es_rota(original):
    assert _pdf("norma-v1:art=14 @ pdf-v1:p=1", original, literal="el importador").estado == "rota"


def test_falta_la_pagina_es_rota(original):
    assert _pdf("norma-v1:art=14", original).estado == "rota"


def test_palabras_partidas_en_la_representacion(original):
    est = _estructura()
    est["unidades"][0]["texto"] = "El fabri cante notifi cará simultá neamente"
    r = _pdf(
        "norma-v1:art=14 @ pdf-v1:p=1", original, literal="El fabricante notificará simultáneamente", estructura=est
    )
    assert r.estado == "resuelta"
    assert "sin espacios" in r.motivo


def test_normalizar():
    assert normalizar("La obli-\ngación  “no” cesa­") == normalizar('la obligación "no" cesa')


TEXTO = "uno\ndos\ntres\ncuatro\n"
SHA_TEXTO = hashlib.sha256(TEXTO.encode()).hexdigest()


def test_lineas():
    assert resolver_lineas(parsear("lines-v1:2-3"), texto=TEXTO, sha256_esperado=SHA_TEXTO).estado == "resuelta"
    assert resolver_lineas(parsear("lines-v1:2-9"), texto=TEXTO, sha256_esperado=SHA_TEXTO).estado == "rota"
    assert resolver_lineas(parsear("lines-v1:2-3"), texto=TEXTO, sha256_esperado="0" * 64).estado == "rota"
    r = resolver_lineas(parsear("L2-L3"), texto=TEXTO, sha256_esperado=SHA_TEXTO, literal="tres")
    assert r.estado == "resuelta"
    assert "heredada" in r.motivo
    r = resolver_lineas(parsear("lines-v1:1-2"), texto=TEXTO, sha256_esperado=SHA_TEXTO, literal="cuatro")
    assert r.estado == "rota"


def _registro(ruta, cabecera):
    lineas = ["---"]
    for clave, valor in cabecera.items():
        lineas.append(f"{clave}: {json.dumps(valor, ensure_ascii=False)}")
    lineas += ["---", "", "# Prueba", ""]
    ruta.write_text("\n".join(lineas), encoding="utf-8")


def _git(raiz, *args):
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


def test_comprobar_almacen_y_git(tmp_path):
    raiz = tmp_path / "repo"
    (raiz / "kb").mkdir(parents=True)
    _git(raiz, "init", "-q")
    (raiz / "doc.md").write_text(TEXTO, encoding="utf-8", newline="\n")
    _git(raiz, "add", "doc.md")
    _git(raiz, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "doc")
    rev = subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    almacen = tmp_path / "almacen"
    (almacen / "sha256").mkdir(parents=True)
    (almacen / "sha256" / SHA_ORIGINAL).write_bytes(ORIGINAL)
    est = json.dumps(_estructura()).encode()
    sha_est = hashlib.sha256(est).hexdigest()
    (almacen / "sha256" / sha_est).write_bytes(est)

    _registro(
        raiz / "kb" / "F-1.md",
        {"id": "F-1", "type": "fuente", "ubicacion": f"almacen:sha256/{SHA_ORIGINAL}", "sha256": SHA_ORIGINAL},
    )
    _registro(
        raiz / "kb" / "F-2.md",
        {"id": "F-2", "type": "fuente", "ubicacion": f"almacen:sha256/{sha_est}", "sha256": sha_est},
    )
    _registro(
        raiz / "kb" / "F-3.md", {"id": "F-3", "type": "fuente", "ubicacion": f"git:{rev}:doc.md", "sha256": SHA_TEXTO}
    )
    _registro(
        raiz / "kb" / "HE-1.md",
        {
            "id": "HE-1",
            "type": "hecho",
            "sources": [
                {
                    "id": "s1",
                    "resource": "F-1",
                    "representacion_id": "F-2",
                    "hash": SHA_ORIGINAL,
                    "ancla": "norma-v1:art=14;ap=2 @ pdf-v1:p=2",
                    "contexto": "La obligación «no» cesa",
                },
                {"id": "s2", "resource": "F-3", "ancla": "l. 2-3", "hash": SHA_TEXTO},
                {"id": "s3", "resource": "F-3", "ancla": "l. 1-2 y l. 3-4"},
                {"id": "s4", "resource": "F-9", "ancla": "lines-v1:1-1"},
            ],
        },
    )
    res = comprobar(raiz, ["kb"], almacen)
    estados = {f["source"]: f["estado"] for f in res["filas"]}
    assert estados == {"s1": "resuelta", "s2": "resuelta", "s3": "no_comprobable", "s4": "rota"}
    assert res["recuento"]["rota"] == 1

    sin_almacen = {f["source"]: f["estado"] for f in comprobar(raiz, ["kb"], None)["filas"]}
    assert sin_almacen["s1"] == "no_comprobable"

    assert main(["citas", str(raiz), "--carpeta", "kb", "--almacen", str(almacen)]) == 3


DOCX = b"PK\x03\x04 documento de Word de prueba"
SHA_DOCX = hashlib.sha256(DOCX).hexdigest()
DOCLING = b'{"schema_name": "DoclingDocument"}'
SHA_DOCLING = hashlib.sha256(DOCLING).hexdigest()
MARKDOWN = b"# Plan\n\n## Riesgos\n\nEl piloto no cubre la planta de Murcia.\n"
SHA_MARKDOWN = hashlib.sha256(MARKDOWN).hexdigest()


def _documento_sin_paginas(tmp_path, sources, con_original=True, fuentes_extra=()):
    """Un Word en el almacén, su DoclingDocument y el Markdown derivado de este; un hecho que cita por líneas."""
    raiz, almacen = tmp_path / "repo", tmp_path / "almacen"
    (raiz / "kb").mkdir(parents=True)
    (almacen / "sha256").mkdir(parents=True)
    objetos = [(SHA_DOCLING, DOCLING), (SHA_MARKDOWN, MARKDOWN)] + ([(SHA_DOCX, DOCX)] if con_original else [])
    for sha, datos in objetos:
        (almacen / "sha256" / sha).write_bytes(datos)
    fuentes = [
        {"id": "F-10", "type": "fuente", "subtipo": "original", "ubicacion": f"almacen:sha256/{SHA_DOCX}", "sha256": SHA_DOCX},
        {"id": "F-11", "type": "fuente", "subtipo": "derivada", "ubicacion": f"almacen:sha256/{SHA_DOCLING}",
         "sha256": SHA_DOCLING, "formato": "application/json", "derivada_de": ["F-10"]},
        {"id": "F-12", "type": "fuente", "subtipo": "derivada", "ubicacion": f"almacen:sha256/{SHA_MARKDOWN}",
         "sha256": SHA_MARKDOWN, "formato": "text/markdown", "derivada_de": ["F-11"]},
        *fuentes_extra,
    ]
    for f in fuentes:
        _registro(raiz / "kb" / f"{f['id']}.md", f)
    _registro(raiz / "kb" / "HE-2.md", {"id": "HE-2", "type": "hecho", "sources": sources})
    return {f["source"]: f for f in comprobar(raiz, ["kb"], almacen)["filas"]}


def _cita(ancla, **extra):
    return {"id": "s1", "resource": "F-10", "representacion_id": "F-12", "hash": SHA_DOCX, "ancla": ancla, **extra}


def test_cita_por_lineas_contra_la_representacion_en_markdown(tmp_path):
    filas = _documento_sin_paginas(tmp_path, [_cita("lines-v1:5-5", contexto="no cubre la planta de Murcia")])
    assert filas["s1"]["estado"] == "resuelta"


def test_cita_por_lineas_contra_la_representacion_rota_si_no_esta_el_literal(tmp_path):
    filas = _documento_sin_paginas(tmp_path, [_cita("lines-v1:3-3", contexto="no cubre la planta de Murcia")])
    assert filas["s1"]["estado"] == "rota" and "no aparece" in filas["s1"]["motivo"]


def test_representacion_de_otro_documento_es_rota(tmp_path):
    otro = {"id": "F-20", "type": "fuente", "subtipo": "original", "ubicacion": "almacen:sha256/" + "0" * 64,
            "sha256": "0" * 64}
    cita = {"id": "s1", "resource": "F-20", "representacion_id": "F-12", "ancla": "lines-v1:5-5"}
    filas = _documento_sin_paginas(tmp_path, [cita], fuentes_extra=[otro])
    assert filas["s1"]["estado"] == "rota" and "no deriva" in filas["s1"]["motivo"]


def test_representacion_que_no_es_texto_es_rota(tmp_path):
    cita = _cita("lines-v1:1-1")
    cita["representacion_id"] = "F-11"
    filas = _documento_sin_paginas(tmp_path, [cita])
    assert filas["s1"]["estado"] == "rota" and "texto" in filas["s1"]["motivo"]


def test_sin_el_original_la_cita_por_lineas_es_no_comprobable(tmp_path):
    filas = _documento_sin_paginas(tmp_path, [_cita("lines-v1:5-5", contexto="planta de Murcia")], con_original=False)
    assert filas["s1"]["estado"] == "no_comprobable" and "original no disponible" in filas["s1"]["motivo"]


def test_cita_por_lineas_sin_representacion_sigue_resolviendo_contra_el_original(tmp_path):
    cita = {"id": "s1", "resource": "F-12", "ancla": "lines-v1:5-5", "contexto": "planta de Murcia"}
    assert _documento_sin_paginas(tmp_path, [cita])["s1"]["estado"] == "resuelta"
