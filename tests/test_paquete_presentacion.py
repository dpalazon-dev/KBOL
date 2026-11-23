"""Lo que el paquete de aprobación enseña cubre lo que el digest cubre.

El digest incluye todo el cuerpo y todos los campos: nada de eso puede quedar oculto, recortado sin aviso o
disfrazado en la terminal.
"""

from kbol.paquete import _RECORTE, _fuera_de_clausulas, _linea, _valor

CLAUSULA = '<clausula id="C1">\nLunes.\n</clausula>\n'


def test_el_texto_fuera_de_las_clausulas_se_muestra_en_un_registro_nuevo():
    fuera = _fuera_de_clausulas(None, CLAUSULA + "\nY además, los martes también.\n")
    assert fuera == {"antes": None, "despues": "Y además, los martes también."}


def test_el_texto_fuera_de_las_clausulas_se_muestra_aunque_cambie_tambien_una_clausula():
    antes = CLAUSULA + "\nNota vieja.\n"
    despues = CLAUSULA.replace("Lunes", "Martes") + "\nNota nueva.\n"
    assert _fuera_de_clausulas(antes, despues) == {"antes": "Nota vieja.", "despues": "Nota nueva."}


def test_sin_cambios_fuera_de_las_clausulas_no_se_informa_nada():
    assert _fuera_de_clausulas(CLAUSULA, CLAUSULA.replace("Lunes", "Martes")) is None
    assert _fuera_de_clausulas(None, CLAUSULA) is None


def test_quitar_el_texto_de_fuera_tambien_se_informa():
    assert _fuera_de_clausulas(CLAUSULA + "\nNota.\n", CLAUSULA) == {"antes": "Nota.", "despues": None}


def test_los_caracteres_de_control_y_de_formato_no_ocultan_texto():
    # Un escape ANSI y una marca de anulación bidireccional: en la terminal podrían borrar o reordenar lo que se ve.
    texto = "aceptar\x1b[2K‮odot"
    visible = _linea(texto)
    assert "\x1b" not in visible and "‮" not in visible
    assert visible.count("�") == 2 and "aceptar" in visible and "odot" in visible


def test_los_saltos_de_linea_se_pliegan_sin_perder_palabras():
    assert _linea("uno\ndos\r\n\ttres") == "uno dos tres"


def test_un_valor_largo_dice_cuanto_se_recorta():
    largo = "x" * (_RECORTE + 40)
    mostrado = _valor(largo)
    assert mostrado.startswith("x" * _RECORTE) and "+40 caracteres" in mostrado and "JSON" in mostrado
    assert _valor("corto") == "corto"
