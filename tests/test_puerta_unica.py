"""Puerta única: solo los módulos de la lista escriben referencias de git.

Cuenta, como literales del código, las órdenes de git que mueven referencias o reescriben historia. Cambiar la lista
es una decisión visible en el diff: un módulo nuevo que escriba la rama canónica tiene que aparecer aquí.
"""

import ast
from collections import Counter
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent.parent / "kbol"
ESCRITURAS = frozenset({"update-ref", "commit-tree", "push", "merge", "rebase", "reset", "cherry-pick"})
PERMITIDAS = {
    "arranque.py": {"update-ref": 1, "commit-tree": 1},
    "integrar.py": {"update-ref": 1, "commit-tree": 1},
    # El clon del integrador: trae la rama, escribe la propuesta, ensaya en una rama temporal y sube.
    "proponer.py": {"update-ref": 5, "commit-tree": 1, "push": 1},
}


def _escrituras(fuente):
    return Counter(
        n.value for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.Constant) and n.value in ESCRITURAS
    )


def test_solo_los_modulos_de_la_puerta_escriben_referencias():
    reales = {}
    for p in sorted(PAQUETE.glob("*.py")):
        cuenta = _escrituras(p.read_text(encoding="utf-8"))
        if cuenta:
            reales[p.name] = dict(cuenta)
    assert reales == PERMITIDAS


def test_la_cuenta_detecta_una_escritura_nueva():
    assert _escrituras('git("update-ref", ref, nuevo)\nx = "reset"\n') == Counter({"update-ref": 1, "reset": 1})
    assert not _escrituras('git("rev-parse", "HEAD")  # update-ref en un comentario no cuenta\n')
