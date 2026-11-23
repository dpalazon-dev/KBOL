"""Digest contractual: serialización exacta, campos cubiertos y vectores publicados."""

import hashlib
import json
from pathlib import Path

import pytest
from conftest import CUERPO_DECISION, evento, registro

from kbol.digest import bytes_canonicos, digest, objeto_aprobable

VECTORES = Path(__file__).resolve().parents[1] / "kbol" / "vectores" / "digest.json"
EFECTO = [{"estado_anterior": "propuesta", "estado_nuevo": "aceptada", "valido_desde": "2026-11-15T00:00:00Z"}]


def test_objeto_aprobable_separa_contenido_de_eventos_y_proyecciones():
    r = registro(
        "decision", status="draft", verified=[{"by": "human:x", "at": "2026-11-01T00:00:00Z", "digest": "c" * 64}]
    )
    r["eventos"] = [evento("creacion", estado_anterior=None, estado_nuevo="propuesta")]
    obj = objeto_aprobable(r, CUERPO_DECISION, EFECTO)
    assert set(obj) == {
        "id",
        "type",
        "clase",
        "title",
        "description",
        "ambito",
        "autor",
        "cuerpo",
        "campos",
        "efectos_solicitados",
    }
    for excluido in ("eventos", "status", "verified", "evaluaciones", "estado", "id", "title"):
        assert excluido not in obj["campos"]
    assert obj["campos"]["sources"] == [] and "alternativas" in obj["campos"]


def test_cambios_que_alteran_el_digest():
    r = registro("decision")
    d = digest(r, CUERPO_DECISION, EFECTO)
    assert d != digest(r, CUERPO_DECISION.replace("martes", "miércoles"), EFECTO)
    assert d != digest(r, CUERPO_DECISION, [{**EFECTO[0], "valido_desde": "2026-11-16T00:00:00Z"}])
    assert d != digest({**r, "modifica": [{"destino": "DEC-A#C1", "tipo": "derogacion"}]}, CUERPO_DECISION, EFECTO)
    assert d != digest({**r, "alternativas": list(reversed(r["alternativas"]))}, CUERPO_DECISION, EFECTO)


def test_cambios_que_no_alteran_el_digest():
    r = registro("decision")
    d = digest(r, CUERPO_DECISION, EFECTO)
    assert d == digest(r, CUERPO_DECISION.replace("\n", "\r\n"), EFECTO)
    assert d == digest(dict(reversed(list(r.items()))), CUERPO_DECISION, EFECTO)
    con_eventos = {
        **r,
        "eventos": [evento("creacion", estado_anterior=None, estado_nuevo="propuesta")],
        "status": "draft",
    }
    assert d == digest(con_eventos, CUERPO_DECISION, EFECTO)


def test_unicode_sin_normalizar_y_escapes():
    r = registro("decision")
    compuesto = digest({**r, "title": "ñ"}, CUERPO_DECISION, [])
    descompuesto = digest({**r, "title": "ñ"}, CUERPO_DECISION, [])
    assert compuesto != descompuesto
    b = bytes_canonicos({"a": 'comilla " barra \\ tab \t nul \x00', "b": "ñ"})
    assert b == '{"a":"comilla \\" barra \\\\ tab \\t nul \\u0000","b":"ñ"}'.encode()
    assert not b.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("valor", [1.5, float("nan"), {"x": 2.0}, [object()]])
def test_tipos_no_admitidos(valor):
    with pytest.raises(ValueError):
        bytes_canonicos({"v": valor})


def test_claves_ordenadas_por_codigo_unicode():
    assert bytes_canonicos({"é": 1, "z": 2, "Z": 3, "a": 4}) == '{"Z":3,"a":4,"z":2,"é":1}'.encode()


def test_vectores_publicados():
    vectores = json.loads(VECTORES.read_text(encoding="utf-8"))
    assert len(vectores) >= 4
    for v in vectores:
        obj = objeto_aprobable(v["registro"], v["cuerpo"], v["efectos_solicitados"])
        b = bytes_canonicos(obj)
        assert b.decode("utf-8") == v["bytes"], v["nombre"]
        assert (
            hashlib.sha256(b).hexdigest() == v["sha256"] == digest(v["registro"], v["cuerpo"], v["efectos_solicitados"])
        )
