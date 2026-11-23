"""Lectura segura y escritura canónica del contenedor Markdown con cabecera YAML."""

import pytest
from conftest import CUERPO_DECISION, registro

from kbol.core import ErrorDeFormato, parse, serializar


@pytest.mark.parametrize(
    "cabecera",
    [
        "a: 1\na: 2",  # clave repetida
        "a:\n  b: 1\n  b: 2",  # clave repetida anidada
        "a: !!python/object:builtins.object {}",  # construcción de objetos
        "a: !!str texto",  # cualquier etiqueta explícita
        "a: &x [1]\nb: *x",  # alias
        "a:\n  <<: {b: 1}",  # clave de fusión
        "- lista",  # la cabecera debe ser un mapa
        "1: entero",  # clave no textual
    ],
)
def test_cabeceras_rechazadas(cabecera):
    with pytest.raises(ErrorDeFormato):
        parse(f"---\n{cabecera}\n---\n")


def test_sin_cabecera_falla():
    with pytest.raises(ErrorDeFormato):
        parse("# solo cuerpo\n")


def test_fechas_se_leen_como_texto_y_unicode_se_conserva():
    meta, cuerpo = parse('---\nfecha: 2026-11-03\ntitle: "Cañería ñ"\n---\ncuerpo\r\n')
    assert meta == {"fecha": "2026-11-03", "title": "Cañería ñ"}
    assert cuerpo == "cuerpo\r\n"


def test_campos_desconocidos_se_conservan_al_leer():
    meta, _ = parse("---\nid: DEC-A\nextra:\n  anidado: [1, 2]\n---\n")
    assert meta["extra"] == {"anidado": [1, 2]}


def test_ida_y_vuelta_conserva_semantica():
    r = registro("decision", title="Plazo: «5 días» # no es comentario", criterios=["yes", "no", "2026-11-03", "1.0"])
    texto = serializar(r, CUERPO_DECISION)
    assert texto.startswith("---\n") and "\r" not in texto
    meta, cuerpo = parse(texto)
    assert meta == r
    assert cuerpo == CUERPO_DECISION


def test_serializar_rechaza_registro_invalido_o_con_campos_desconocidos():
    with pytest.raises(ErrorDeFormato, match="ESQUEMA_INVALIDO"):
        serializar(registro("decision", extra="x"), CUERPO_DECISION)
    with pytest.raises(ErrorDeFormato):
        serializar(registro("decision"), "sin cláusulas")


def test_serializar_normaliza_saltos_de_linea_del_cuerpo():
    texto = serializar(registro("decision"), CUERPO_DECISION.replace("\n", "\r\n"))
    assert "\r" not in texto
