"""Política como prueba: la documentación coincide con el código, en los dos README (inglés y español)."""

import json
import re
from pathlib import Path

import pytest

import kbol
from kbol import cli

RAIZ = Path(__file__).resolve().parent.parent
ELECCIONES = (RAIZ / "docs" / "elecciones.md").read_text(encoding="utf-8")

# Cada README con los títulos de sus secciones de referencia, la frase de las operaciones que devuelven `bloqueado`
# y la forma en que nombra los elementos de la política de una instalación.
README = {
    "README.md": {
        "uso": "Usage",
        "modulos": "Modules",
        "limites": "Limitations",
        "bloqueado": r"^(.*?) returns? `bloqueado` in the CLI",
        "politica": r"policy \(([^)]*)\)",
        "y": " and ",
        "elementos": {"roles": "regla_aprobacion", "people": "ocupa"},
    },
    "README.es.md": {
        "uso": "Uso",
        "modulos": "Módulos",
        "limites": "Qué no hace todavía",
        "bloqueado": r"^(.*?) devuelven? `bloqueado` en la CLI",
        "politica": r"política \(([^)]*)\)",
        "y": " y ",
        "elementos": {"roles": "regla_aprobacion", "personas": "ocupa"},
    },
}


def _texto(nombre):
    return (RAIZ / nombre).read_text(encoding="utf-8")


def _seccion(texto, titulo):
    m = re.search(rf"^## {re.escape(titulo)}\n(.*?)(?=^## |\Z)", texto, re.S | re.M)
    assert m, f"falta la sección «{titulo}»"
    return m.group(1)


@pytest.mark.parametrize("nombre", README)
def test_la_tabla_de_modulos_lista_los_modulos_del_paquete(nombre):
    seccion = _seccion(_texto(nombre), README[nombre]["modulos"])
    documentados = set(re.findall(r"^\| `(\w+)` \|", seccion, re.M))
    reales = {p.stem for p in (RAIZ / "kbol").glob("*.py") if p.stem != "__init__"}
    assert documentados == reales, (
        f"sin documentar: {sorted(reales - documentados)}; documentados que no existen: {sorted(documentados - reales)}"
    )


@pytest.mark.parametrize("nombre", README)
def test_las_ordenes_del_uso_son_las_habilitadas(nombre):
    uso = _seccion(_texto(nombre), README[nombre]["uso"])
    documentadas = set(re.findall(r"^uv run kbol (\w+)", uso, re.M))
    assert documentadas == set(cli.HABILITADAS)


@pytest.mark.parametrize("nombre", README)
def test_las_ordenes_no_habilitadas_son_las_que_dice_el_readme(nombre):
    cfg = README[nombre]
    frase = re.search(cfg["bloqueado"], _seccion(_texto(nombre), cfg["limites"]), re.M)
    assert frase, "falta la frase sobre las operaciones que devuelven `bloqueado`"
    assert set(re.findall(r"`(\w+)`", frase.group(1))) == set(cli.NO_HABILITADAS)


def test_los_dos_readme_listan_las_mismas_ordenes():
    en, es = (_seccion(_texto(n), README[n]["uso"]) for n in README)
    bloque = lambda s: re.search(r"```bash\n(.*?)```", s, re.S).group(1)  # noqa: E731
    assert bloque(en) == bloque(es)


# Una ruta citada es un texto entre comillas invertidas que empieza por una carpeta de este repositorio, sin
# marcadores de plantilla (`<`, `*`, `…`). Una ruta con otro origen (`~/`, `.kbol/`, `<carpeta>/…`) no se comprueba.
RUTA = re.compile(r"`((?:kbol|docs|tools|tests)/[^`\s<>*…]*)`")


def _rutas_citadas(texto):
    return set(RUTA.findall(texto))


def test_las_rutas_citadas_existen():
    inexistentes = []
    for nombre, texto in [*((n, _texto(n)) for n in README), ("docs/elecciones.md", ELECCIONES)]:
        inexistentes += [f"{nombre}: {r}" for r in sorted(_rutas_citadas(texto)) if not (RAIZ / r).exists()]
    assert not inexistentes, f"rutas citadas que no existen: {inexistentes}"


def test_la_regla_de_rutas_ignora_lo_que_no_es_de_este_repositorio():
    texto = "`~/.kbol/x`, `<carpeta>/_solicitudes/<op>.json`, `.kbol/relevos/`, `docs/*.md` y `kbol/vectores/digest.json`"
    assert _rutas_citadas(texto) == {"kbol/vectores/digest.json"}


def test_la_version_del_proyecto_es_la_del_paquete():
    m = re.search(r'^version = "([^"]+)"', (RAIZ / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert m and m.group(1) == kbol.__version__


def test_el_catalogo_de_referencias_es_coherente():
    catalogo = json.loads((RAIZ / "docs" / "referencias" / "catalogo.json").read_text(encoding="utf-8"))
    nombres = [e["nombre"] for e in catalogo]
    assert len(nombres) == len(set(nombres)), "nombres repetidos en el catálogo"
    for e in catalogo:
        assert set(e) == {"nombre", "version", "que_es", "origen", "consumido_por"}, e["nombre"]
        assert e["consumido_por"], f"{e['nombre']}: nadie lo consume"
        faltan = [r for r in e["consumido_por"] if not (RAIZ / r).exists()]
        assert not faltan, f"{e['nombre']}: rutas que no existen: {faltan}"


@pytest.mark.parametrize("nombre", README)
def test_la_politica_del_readme_solo_nombra_lo_que_existe_en_el_codigo(nombre):
    cfg = README[nombre]
    m = re.search(cfg["politica"], _texto(nombre))
    assert m, "falta la descripción de la política de una instalación"
    elementos = [e.strip() for e in re.split(rf",|{cfg['y']}", m.group(1)) if e.strip()]
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "kbol").glob("*.py"))
    sin_respaldo = [e for e in elementos if e not in cfg["elementos"] or cfg["elementos"][e] not in codigo]
    assert not sin_respaldo, f"el README nombra en la política lo que el código no tiene: {sin_respaldo}"
