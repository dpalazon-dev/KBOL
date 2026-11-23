import pytest

from kbol.localizador import Cita, Lineas, LocalizadorInvalido, Norma, Pagina, formatear, parsear

COMBINADA = "norma-v1:art=14;ap=2;let=a @ pdf-v1:p=37;r=0.1120,0.4300,0.8870,0.5120"


def test_ida_y_vuelta_norma_pdf():
    cita = parsear(COMBINADA)
    assert cita.logico == Norma((("art", "14"), ("ap", "2"), ("let", "a")))
    assert cita.fisico == Pagina(37, ("0.1120", "0.4300", "0.8870", "0.5120"))
    assert cita.heredada is False
    assert cita.logico.clave() == "art=14;ap=2;let=a"
    assert formatear(cita) == COMBINADA


def test_solo_logico_y_solo_pagina():
    assert parsear("norma-v1:anx=I;parte=I;pto=2;let=c") == Cita(
        Norma((("anx", "I"), ("parte", "I"), ("pto", "2"), ("let", "c"))), None
    )
    assert parsear("pdf-v1:p=3") == Cita(None, Pagina(3, None))
    assert formatear(parsear("pdf-v1:p=3")) == "pdf-v1:p=3"


def test_lineas():
    cita = parsear("lines-v1:10-18")
    assert cita == Cita(None, Lineas(10, 18))
    assert formatear(cita) == "lines-v1:10-18"


@pytest.mark.parametrize(
    "ancla, inicio, fin",
    [("l. 66-84 (§3, mapa de consumo)", 66, 84), ("L10-L20", 10, 20), ("l. 161-167", 161, 167), ("l. 106", 106, 106)],
)
def test_heredadas(ancla, inicio, fin):
    cita = parsear(ancla)
    assert cita.fisico == Lineas(inicio, fin)
    assert cita.heredada is True


@pytest.mark.parametrize(
    "ancla",
    [
        "pdf-v1:p=1;r=0.1,0.2,1.2,0.3",  # fuera de 0-1
        "pdf-v1:p=1;r=0.5,0.2,0.4,0.3",  # x0 >= x1
        "pdf-v1:p=1;r=0.1,0.3,0.4,0.3",  # y0 >= y1
        "pdf-v1:p=1;r=0.12345,0.2,0.4,0.3",  # más de cuatro decimales
        "pdf-v1:p=1;r=0.1,0.2,0.4",  # tres coordenadas
    ],
)
def test_region_invalida(ancla):
    with pytest.raises(LocalizadorInvalido):
        parsear(ancla)


@pytest.mark.parametrize(
    "ancla",
    [
        "pdf-v1:p=0",
        "norma-v1:ap=2;art=14",  # orden de claves
        "norma-v1:art=14;foo=2",  # clave desconocida
        "norma-v1:art=14;art=15",  # clave repetida
        "norma-v1:art=",  # valor vacío
        "lines-v1:20-10",
        "lines-v1:0-3",
        "norma-v1:art=14 @ lines-v1:1-2",  # lógico con líneas
        "pdf-v1:p=3 @ pdf-v1:p=4",
        "",
        "l. 30-40 y l. 135-147",  # dos tramos: no es un localizador
    ],
)
def test_invalidos(ancla):
    with pytest.raises(LocalizadorInvalido):
        parsear(ancla)
