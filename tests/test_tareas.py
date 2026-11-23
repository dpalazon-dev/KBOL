"""Tareas de un hito como cláusulas `CT*`: se marcan, pero no se borran ni se reescriben.

Una memoria o una nota cita tareas por `PL-nnn-Hk#CTn`: una tarea citable tiene que conservar su texto y su ancla.
Marcar su casilla es avance, no un cambio de contenido; en un hito cerrado ni siquiera eso.
"""

import pytest
from conftest import registro

from kbol.mutabilidad import comparar
from kbol.proyeccion import Snapshot

TAREAS = (
    "## Tareas\n\n"
    '<clausula id="CT1">\n- [ ] Medir la paridad\n</clausula>\n\n'
    '<clausula id="CT2">\n- [x] Escribir el test rojo\n</clausula>\n'
)


def snap(cuerpo, estado="en_curso"):
    hito = registro("hito", estado=estado)
    return Snapshot({"HI-A": hito}, "r", {"HI-A": cuerpo}, {"HI-A": "kb/HI-A.md"})


def errores(antes, despues, estado="en_curso"):
    out = comparar(snap(antes, estado), snap(despues, estado))
    return [h["mensaje"] for h in out["hallazgos"] if h["severidad"] == "error"]


def test_marcar_una_casilla_es_avance_y_no_un_cambio_protegido():
    assert errores(TAREAS, TAREAS.replace("- [ ] Medir", "- [x] Medir")) == []
    assert errores(TAREAS, TAREAS.replace("- [x] Escribir", "- [ ] Escribir")) == []


def test_una_tarea_nueva_se_puede_anadir():
    nueva = TAREAS + '\n<clausula id="CT3">\n- [ ] Documentar\n</clausula>\n'
    assert errores(TAREAS, nueva) == []


@pytest.mark.parametrize(
    "despues",
    [
        TAREAS.replace("Medir la paridad", "Medir otra cosa"),
        TAREAS.replace('<clausula id="CT1">\n- [ ] Medir la paridad\n</clausula>\n\n', ""),
        TAREAS.replace('id="CT2"', 'id="CT9"'),
    ],
)
def test_una_tarea_no_se_reescribe_ni_se_borra_ni_se_renumera(despues):
    assert any("tarea" in m for m in errores(TAREAS, despues))


def test_en_un_hito_cerrado_ni_siquiera_se_marca():
    assert any("tarea" in m for m in errores(TAREAS, TAREAS.replace("- [ ] Medir", "- [x] Medir"), "completado"))


def test_un_cuerpo_con_marcas_rotas_no_pasa():
    assert any("tarea" in m for m in errores(TAREAS, TAREAS.replace("</clausula>\n\n", "\n", 1)))


def test_un_hito_con_las_marcas_rotas_en_la_base_no_admite_cambios_sin_comprobar():
    rota = '<clausula id="CT1">\n- [ ] Medir\n'
    assert errores(rota, rota + "</clausula>\n")
