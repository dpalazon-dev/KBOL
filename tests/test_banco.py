"""Banco mínimo previo del contrato, como prueba mantenida.

El contrato (docs/referencias/KB-DPP-implementacion.md, «Banco mínimo previo») lista los casos que el
sistema debe resolver bien. Este archivo no ejecuta esos casos: los ejecuta la suite. Aquí solo se
comprueba que cada caso del contrato tiene dueño en tests/banco/cobertura.yaml: pruebas existentes que
lo ejercitan, una capacidad declarada como no habilitada, o una prueba pendiente que aún no existe.
Si el contrato añade, quita o renombra un caso, la prueba falla y obliga a decidirlo.
"""

import ast
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONTRATO = RAIZ / "docs" / "referencias" / "KB-DPP-implementacion.md"
COBERTURA = RAIZ / "tests" / "banco" / "cobertura.yaml"
CLAVES = ("tests", "no_habilitada", "pendiente")


def casos_del_contrato() -> list[str]:
    lineas = CONTRATO.read_text(encoding="utf-8").splitlines()
    inicio = next(i for i, linea in enumerate(lineas) if linea.strip() == "### Banco mínimo previo")
    casos, en_tabla = [], False
    for linea in lineas[inicio + 1 :]:
        if linea.startswith("#"):
            break
        if not linea.startswith("|"):
            if en_tabla:
                break
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if celdas[0] == "Caso" or re.fullmatch(r"[-: ]+", celdas[0]):
            en_tabla = True
            continue
        casos.append(celdas[0])
    return casos


def cobertura() -> dict:
    return yaml.safe_load(COBERTURA.read_text(encoding="utf-8"))


def funciones_de_prueba(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    return {
        n.name
        for n in ast.walk(arbol)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test_")
    }


def test_el_contrato_tiene_la_tabla():
    assert len(casos_del_contrato()) >= 1


def test_la_cobertura_tiene_exactamente_los_casos_del_contrato():
    esperados, tiene = casos_del_contrato(), cobertura()
    assert len(set(esperados)) == len(esperados), "caso repetido en el contrato"
    assert not set(esperados) - set(tiene), f"casos del contrato sin decidir en cobertura.yaml: {set(esperados) - set(tiene)}"
    assert not set(tiene) - set(esperados), f"casos de cobertura.yaml que ya no están en el contrato: {set(tiene) - set(esperados)}"


@pytest.mark.parametrize("caso", sorted(cobertura()))
def test_cada_caso_tiene_exactamente_una_forma_de_cobertura(caso):
    entrada = cobertura()[caso]
    assert isinstance(entrada, dict), f"{caso}: la entrada debe ser un mapa"
    puestas = [k for k in entrada if k in CLAVES]
    assert len(puestas) == 1 and len(entrada) == 1, f"{caso}: debe tener solo una de {CLAVES}, tiene {list(entrada)}"
    clave = puestas[0]
    if clave == "tests":
        assert isinstance(entrada[clave], list) and entrada[clave], f"{caso}: `tests` no puede estar vacío"
    else:
        assert isinstance(entrada[clave], str) and entrada[clave].strip(), f"{caso}: `{clave}` no puede estar vacío"


@pytest.mark.parametrize("caso", sorted(cobertura()))
def test_cada_prueba_listada_existe(caso):
    ids = cobertura()[caso].get("tests", [])
    for ident in ids:
        ruta, sep, nombre = ident.partition("::")
        assert sep and nombre, f"{caso}: id mal formado: {ident}"
        nombre = nombre.split("[", 1)[0]
        archivo = RAIZ / ruta
        assert archivo.is_file(), f"{caso}: no existe el archivo {ruta}"
        assert nombre in funciones_de_prueba(archivo), f"{caso}: {ruta} no define {nombre}"


@pytest.mark.parametrize("caso", sorted(cobertura()))
def test_lo_pendiente_no_se_queda_pendiente_cuando_su_archivo_existe(caso):
    destino = cobertura()[caso].get("pendiente")
    if destino is None:
        return
    assert not (RAIZ / destino).is_file(), (
        f"{caso}: {destino} ya existe. Sustituye `pendiente` por `tests` con los ids reales en tests/banco/cobertura.yaml"
    )
