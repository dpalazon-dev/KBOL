"""Gramática de cláusulas y afirmaciones del contrato concreto."""

import pytest

from kbol.markdown import ErrorDeMarca, clausulas, hechos


def test_clausulas_por_id_no_por_posicion():
    c = clausulas('<clausula id="C2">\nB\n</clausula>\n\n<clausula id="C1">\nA *md*\n</clausula>\n')
    assert c == {"C2": "B", "C1": "A *md*"}


@pytest.mark.parametrize(
    "cuerpo",
    [
        '<clausula id="C1">\nx\n</clausula>\n<clausula id="C1">\ny\n</clausula>',  # repetida
        '<clausula id="C1">\n<clausula id="C2">\n</clausula>\n</clausula>',  # anidada
        '<clausula id="C1">\nsin cierre',
        "</clausula>",
        '<clausula id="X1">\nx\n</clausula>',  # identificador inválido
        '  <clausula id="C1">\nx\n</clausula>',  # no está en línea propia
    ],
)
def test_clausulas_mal_formadas(cuerpo):
    with pytest.raises(ErrorDeMarca):
        clausulas(cuerpo)


def test_codigo_y_escapes_no_abren_clausulas():
    cuerpo = (
        '```\n<clausula id="C9">\n```\n'
        "~~~~\n</clausula>\n~~~~\n"
        '\\<clausula id="C8">\n'
        '`<clausula id="C7">`\n'
        '<clausula id="C1">\nA\n</clausula>\n'
    )
    assert clausulas(cuerpo) == {"C1": "A"}


def test_hechos_en_linea():
    cuerpo = 'El caudal es <hecho id="H1" evidencia="observado" fuente="s1">5 m3/h a 20 °C</hecho>. Ver <hecho ref="HE-A">la medida</hecho>.'
    h = hechos(cuerpo)
    assert h == [
        {"id": "H1", "evidencia": "observado", "fuente": "s1", "texto": "5 m3/h a 20 °C"},
        {"ref": "HE-A", "texto": "la medida"},
    ]


@pytest.mark.parametrize(
    "cuerpo",
    [
        '<hecho id="H1" evidencia="observado" fuente="s1">a</hecho><hecho id="H1" evidencia="observado" fuente="s1">b</hecho>',
        '<hecho id="H1" evidencia="observado">a</hecho>',  # falta fuente
        '<hecho id="H1" evidencia="observado" fuente="s1">a',  # sin cierre
        '<hecho ref="HE-A" id="H1">a</hecho>',  # ref y forma en línea a la vez
        '<hecho id="H1" evidencia="observado" fuente="s1"><hecho ref="HE-A">x</hecho></hecho>',
    ],
)
def test_hechos_mal_formados(cuerpo):
    with pytest.raises(ErrorDeMarca):
        hechos(cuerpo)


def test_hechos_en_codigo_se_ignoran():
    assert hechos('```\n<hecho id="H1">x</hecho>\n```\n`<hecho id="H2">y</hecho>`') == []
