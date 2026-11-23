"""VAL-07: condiciones de `depende_de` y hitos listos, sin que descartar equivalga a cumplir (AUD-04)."""

from conftest import decision, evento, registro

from kbol.consolidar import _Consulta
from kbol.dependencias import evaluar, listos, rige_al_corte
from kbol.proyeccion import Snapshot

C = dict(valido_en="2026-11-20T00:00:00Z", conocido_hasta="2026-11-20T00:00:00Z")


def con_historial(tipo, *estados, **campos):
    ev = [
        evento(
            "creacion",
            evento_id="E0",
            estado_anterior=None,
            estado_nuevo=estados[0],
            registrado_en="2026-11-01T00:00:00Z",
            valido_desde="2026-11-01T00:00:00Z",
        )
    ]
    for i, (a, b) in enumerate(zip(estados, estados[1:]), start=1):
        t = f"2026-11-0{i + 1}T00:00:00Z"
        ev.append(evento(evento_id=f"E{i}", estado_anterior=a, estado_nuevo=b, registrado_en=t, valido_desde=t))
    return registro(tipo, estado=estados[-1], eventos=ev, **campos)


def snap(*regs, cuerpos=None):
    return Snapshot({r["id"]: r for r in regs}, "r1", cuerpos or {})


def dep(destino, condicion):
    return [{"destino": destino, "condicion": condicion}]


def una(r, s):
    (resultado,) = evaluar(r, s, **C)
    return resultado


def test_hito_cancelado_no_satisface_la_dependencia():
    y = con_historial("hito", "propuesto", "cancelado", id="HI-Y")
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("HI-Y", "completado_con_evidencia"))
    r = una(x, snap(x, y))
    assert r["satisfecha"] is False and "cancelado" in r["motivo"]


def test_hito_completado_satisface_con_aviso_de_evidencia():
    y = con_historial("hito", "propuesto", "autorizado", "en_curso", "completado", id="HI-Y")
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("HI-Y", "completado_con_evidencia"))
    r = una(x, snap(x, y))
    # Falla cerrado hasta que exista el registro de verificaciones por criterio (VAL-12).
    assert r["satisfecha"] is False and r["codigo"] == "EVIDENCIA_INSUFICIENTE"


def test_decision_aceptada_y_vigente():
    a, ca = decision("DEC-A", {"C1": "x"}, registrado="2026-11-01T00:00:00Z")
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("DEC-A", "aceptada_y_vigente"))
    assert una(x, snap(x, a, cuerpos={"DEC-A": ca}))["satisfecha"] is True
    f, cf = decision("DEC-A", {"C1": "x"}, registrado="2026-11-01T00:00:00Z", valido="2026-12-01T00:00:00Z")
    assert una(x, snap(x, f, cuerpos={"DEC-A": cf}))["satisfecha"] is False
    p, cp = decision("DEC-A", {"C1": "x"}, estado="propuesta")
    assert una(x, snap(x, p, cuerpos={"DEC-A": cp}))["satisfecha"] is False


def test_dependencia_de_clausula_sustituida_no_se_satisface():
    a, ca = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b, cb = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-B#C1"}],
    )
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("DEC-A#C1", "aceptada_y_vigente"))
    r = una(x, snap(x, a, b, cuerpos={"DEC-A": ca, "DEC-B": cb}))
    assert r["satisfecha"] is False and "DEC-B#C1" in r["motivo"]


def test_pregunta_resuelta():
    q = con_historial("pregunta", "abierta", "resuelta", id="Q-B")
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("Q-B", "resuelta"))
    assert una(x, snap(x, q))["satisfecha"] is True
    q2 = con_historial("pregunta", "abierta", "descartada", id="Q-B")
    assert una(x, snap(x, q2))["satisfecha"] is False


def test_fuente_sin_integridad_comprobada_bloquea():
    f = con_historial("fuente", "registrada", id="F-A")
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("F-A", "disponible_con_integridad"))
    r = una(x, snap(x, f))
    assert r["satisfecha"] is False and r["codigo"] == "INTEGRIDAD_NO_COMPROBADA"


def test_destino_ausente_o_condicion_de_otro_tipo():
    x = con_historial(
        "hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("HI-NADA", "completado_con_evidencia")
    )
    assert una(x, snap(x))["codigo"] == "REFERENCIA_AUSENTE"
    q = con_historial("pregunta", "abierta", "resuelta", id="Q-B")
    y = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("Q-B", "completado_con_evidencia"))
    assert una(y, snap(y, q))["codigo"] == "ESQUEMA_INVALIDO"


def test_listos_exige_autorizacion_propia_y_dependencias():
    plan = con_historial("plan", "propuesto", id="PL-A", hitos=["HI-X", "HI-Z", "HI-W"])
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X")  # plan propuesto: no bloquea por asociación
    z = con_historial("hito", "propuesto", id="HI-Z")  # sin autorización propia
    y = con_historial("hito", "propuesto", "cancelado", id="HI-Y")
    w = con_historial("hito", "propuesto", "autorizado", id="HI-W", depende_de=dep("HI-Y", "completado_con_evidencia"))
    res = listos(snap(plan, x, z, y, w), **C)
    assert [h["id"] for h in res["listos"]] == ["HI-X"]
    assert [h["id"] for h in res["bloqueados"]] == ["HI-W"]


def test_sin_historial_no_esta_listo():
    x = registro("hito", estado="autorizado")
    res = listos(snap(x), **C)
    assert res["listos"] == [] and res["advertencias"]


def test_rige_al_corte_es_la_regla_de_las_dependencias():
    """Dependencias y soporte comparten la definición de qué rige."""
    a, ca = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-11-01T00:00:00Z")
    b, cb = decision(
        "DEC-B",
        {"C1": "Martes."},
        registrado="2026-11-02T00:00:00Z",
        modifica=[{"destino": "DEC-A#C1", "tipo": "derogacion", "por": "DEC-B"}],
    )
    s = snap(a, b, cuerpos={"DEC-A": ca, "DEC-B": cb})
    res = rige_al_corte(_Consulta(s, C["valido_en"], C["conocido_hasta"]), "DEC-A#C1")
    assert res["situacion"] == "no_rige" and res["origen"] == "DEC-B" and res["estado"] == "aceptada"
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("DEC-A#C1", "aceptada_y_vigente"))
    r = una(x, snap(x, a, b, cuerpos={"DEC-A": ca, "DEC-B": cb}))
    assert r["satisfecha"] is False and r["motivo"] == res["motivo"]


def test_hecho_con_sucesora_de_tiempo_ambiguo_no_satisface():
    """Sin decidir si la sucesora ya entró en vigor, el hecho no se da por vigente."""
    h = con_historial("hecho", "propuesta", "aceptada", id="HE-A")
    sucesora = con_historial("hecho", "propuesta", "aceptada", id="HE-B", deja_obsoleta=["HE-A"])
    sucesora["eventos"][-1]["valido_desde"] = C["valido_en"][:10]
    x = con_historial("hito", "propuesto", "autorizado", id="HI-X", depende_de=dep("HE-A", "aceptada_y_vigente"))
    r = una(x, snap(x, h, sucesora))
    assert r["satisfecha"] is False and r["codigo"] == "TIEMPO_AMBIGUO" and r["advertencias"]
