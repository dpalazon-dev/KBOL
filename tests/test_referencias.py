"""VAL-02 y VAL-07 sobre un snapshot: identidad, referencias, tipos de destino y ciclos."""

from conftest import CUERPO_DECISION, registro

from kbol.proyeccion import Snapshot
from kbol.referencias import validar_snapshot


def snap(*registros, cuerpos=None):
    return Snapshot({r["id"]: r for r in registros}, revision="r1", cuerpos=cuerpos or {})


def codigos(h):
    return sorted(x["codigo"] for x in h)


def test_snapshot_coherente_sin_hallazgos():
    rol = registro("rol")
    dec = registro("decision")
    assert validar_snapshot(snap(rol, dec, cuerpos={"DEC-EJEMPLO": CUERPO_DECISION})) == []


def test_referencia_ausente_y_tipo_de_destino():
    dec = registro("decision", autorizado_por=["ROL-NADIE"])
    assert codigos(validar_snapshot(snap(dec, cuerpos={"DEC-EJEMPLO": CUERPO_DECISION}))) == ["REFERENCIA_AUSENTE"]
    q = registro("pregunta", resuelta_por=["DEC-EJEMPLO"])
    hip = registro("hipotesis", id="HIP-B", estado="abierta")
    rol = registro("rol")
    dec = registro("decision")
    assert validar_snapshot(snap(q, rol, dec, hip, cuerpos={"DEC-EJEMPLO": CUERPO_DECISION})) == []
    mal = registro("pregunta", resuelta_por=["HIP-B"])
    assert "ESQUEMA_INVALIDO" in codigos(validar_snapshot(snap(mal, hip)))


def test_ancla_de_clausula_inexistente():
    rol = registro("rol")
    dec = registro("decision")
    q = registro("pregunta", cuestiona=["DEC-EJEMPLO#C9"])
    assert codigos(validar_snapshot(snap(rol, dec, q, cuerpos={"DEC-EJEMPLO": CUERPO_DECISION}))) == [
        "REFERENCIA_AUSENTE"
    ]


def test_ciclos_prohibidos_y_contextuales_permitidos():
    rol = registro("rol")
    a = registro("hito", id="HI-A", depende_de=[{"destino": "HI-B", "condicion": "completado_con_evidencia"}])
    b = registro("hito", id="HI-B", depende_de=[{"destino": "HI-A", "condicion": "completado_con_evidencia"}])
    assert "CONFLICTO_NORMATIVO" in codigos(validar_snapshot(snap(rol, a, b)))
    # Una pregunta resuelta por una decisión que la afecta es un ciclo de contexto legítimo.
    q = registro("pregunta", resuelta_por=["DEC-EJEMPLO"])
    dec = registro("decision", afecta_a=["Q-A"])
    assert validar_snapshot(snap(rol, q, dec, cuerpos={"DEC-EJEMPLO": CUERPO_DECISION})) == []


def test_sucesion_ciclica_rechazada():
    rol = registro("rol")
    a = registro("decision", id="DEC-A", deja_obsoleta=["DEC-B"])
    b = registro("decision", id="DEC-B", deja_obsoleta=["DEC-A"])
    cuerpos = {"DEC-A": CUERPO_DECISION, "DEC-B": CUERPO_DECISION}
    assert "CONFLICTO_NORMATIVO" in codigos(validar_snapshot(snap(rol, a, b, cuerpos=cuerpos)))


def test_deja_obsoleta_exige_mismo_tipo():
    rol = registro("rol")
    dec = registro("decision", deja_obsoleta=["Q-A"])
    q = registro("pregunta")
    assert "ESQUEMA_INVALIDO" in codigos(validar_snapshot(snap(rol, dec, q, cuerpos={"DEC-EJEMPLO": CUERPO_DECISION})))
