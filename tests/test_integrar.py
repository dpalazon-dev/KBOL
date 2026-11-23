"""RES-02 y RES-06: integración local controlada, con recibos idempotentes y rechazo por base cambiada (ESC-03.5)."""

import copy
import hashlib
import json
import subprocess

import pytest
from conftest import CUERPO_DECISION, cuerpo_de, decision, evento, registro

from kbol.core import parse, serializar
from kbol.digest import bytes_canonicos, digest
from kbol.github import ClienteGitHub, VerificadorGitHub
from kbol.integrar import integrar
from kbol.schema import validar

ACEPTAR = [{"estado_anterior": "propuesta", "estado_nuevo": "aceptada", "valido_desde": "2026-11-05T00:00:00Z"}]
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REVISION = {"mecanismo": "github-review", "pull": 1, "review_id": 11}


def activo(tipo, ident, **campos):
    ev = [
        evento(
            "creacion",
            evento_id="E0",
            estado_anterior=None,
            estado_nuevo="propuesta",
            registrado_en="2026-10-01T00:00:00Z",
            valido_desde="2026-10-01T00:00:00Z",
        ),
        evento(
            evento_id="E1",
            estado_anterior="propuesta",
            estado_nuevo="activa",
            registrado_en="2026-10-02T00:00:00Z",
            valido_desde="2026-10-02T00:00:00Z",
        ),
    ]
    return registro(tipo, id=ident, estado="activa", eventos=ev, **campos)


class Repo:
    def __init__(self, raiz):
        self.raiz = raiz
        self.n = 0
        subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.raiz), *IDENT, *args], capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def escribir(self, ruta, texto):
        f = self.raiz / ruta
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(texto, encoding="utf-8", newline="\n")

    def commit(self, mensaje):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", mensaje)
        return self.git("rev-parse", "HEAD")


def canonico(r, c=""):
    return serializar(r, c, modo="canonico")


@pytest.fixture
def entorno(tmp_path):
    repo = Repo(tmp_path / "repo")
    repo.escribir("README.md", "x\n")
    repo.escribir("notas/guia.md", "---\ntype: Guía\ntitle: g\n---\nGuía.\n")
    rol = activo("rol", "ROL-OP", ambitos=["operaciones"], capacidades=["ratificar"], regla_aprobacion="uno")
    per = activo(
        "persona",
        "PER-H",
        naturaleza="humana",
        identidad_ref="github:101",
        ocupa=[{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}],
    )
    ag = activo("persona", "PER-AG", naturaleza="agente", identidad_ref="github:900", ocupa=[])
    sin_rol = activo("persona", "PER-N", naturaleza="humana", identidad_ref="github:300", ocupa=[])
    repo.escribir("kb/PER-N.md", canonico(sin_rol))
    a, ca = decision("DEC-A", {"C1": "Lunes."}, registrado="2026-10-03T00:00:00Z", autorizado_por=["ROL-OP"])
    repo.escribir("kb/ROL-OP.md", canonico(rol))
    repo.escribir("kb/PER-H.md", canonico(per))
    repo.escribir("kb/PER-AG.md", canonico(ag))
    repo.escribir("kb/DEC-A.md", canonico(a, ca))
    base = repo.commit("base")
    repo.git("branch", "canon")
    return repo, base, tmp_path / "recibos"


def proponer(repo, base, archivos, mensaje="propuesta", mover=None):
    repo.n += 1
    repo.git("checkout", "-q", "-b", f"p{repo.n}", base)
    if mover:
        repo.git("mv", *mover)
    for ruta, texto in archivos.items():
        repo.escribir(ruta, texto)
    rev = repo.commit(mensaje)
    repo.git("checkout", "-q", "main")
    return rev


def solicitud(op, efectos):
    return {f"kb/_solicitudes/{op}.json": json.dumps({"operacion_id": op, "efectos": efectos})}


class Cliente(ClienteGitHub):
    def __init__(self, respuestas, al_llamar=None):
        super().__init__(token="t")
        self.respuestas = respuestas
        self.al_llamar = al_llamar

    def get(self, ruta):
        if self.al_llamar:
            self.al_llamar()
            self.al_llamar = None
        return copy.deepcopy(self.respuestas[ruta])


def verificador(head, base, user=101, commit=None, al_llamar=None):
    revision = {
        "id": 11,
        "user": {"id": user},
        "state": "APPROVED",
        "commit_id": commit or head,
        "submitted_at": "2026-11-04T10:00:00Z",
    }
    respuestas = {
        "/repos/o/r/pulls/1": {"head": {"sha": head}, "base": {"sha": base, "ref": "canon"}},
        "/repos/o/r/pulls/1/reviews?per_page=100&page=1": [revision],
        "/repos/o/r/issues/1/timeline?per_page=100&page=1": [],
    }
    return VerificadorGitHub(Cliente(respuestas, al_llamar), "o/r", "canon")


def dec_x():
    return registro("decision", id="DEC-X", autorizado_por=["ROL-OP"]), CUERPO_DECISION


def preparar_aceptacion(repo, base, op="op-1"):
    r, c = dec_x()
    return proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud(op, {"DEC-X": ACEPTAR})})


def llamar(repo, base, prop, recibos, op="op-1", revisiones=None, ver=None, **kw):
    argumentos = dict(
        rama="canon",
        carpeta="kb",
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=[REVISION] if revisiones is None else revisiones,
        verificador=ver or verificador(prop, base),
        recibos=recibos,
    )
    argumentos.update(kw)
    return integrar(repo.raiz, **argumentos)


def test_integracion_valida_con_recibo_y_sin_tocar_el_arbol(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    head_antes = repo.git("rev-parse", "HEAD")
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "integrado", res
    canon = repo.git("rev-parse", "canon")
    assert res["revision_integrada"] == canon and canon not in (base, prop)
    assert repo.git("rev-parse", "HEAD") == head_antes and repo.git("status", "--porcelain") == ""
    # Aplanado: un solo padre, la base; la historia de la propuesta no entra en la rama canónica.
    assert repo.git("log", "-1", "--format=%P", "canon").split() == [base]
    mensaje = repo.git("log", "-1", "--format=%B", "canon")
    assert (
        f"Operacion-Id: op-1\nSolicitud-Sha256: {res['solicitud_sha256']}\nBase: {base}\nPropuesta: {prop}" in mensaje
    )
    assert "Revisiones: github-review:o/r#1/11" in mensaje
    meta, cuerpo = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert meta["estado"] == "aceptada"
    assert [e["tipo_evento"] for e in meta["eventos"]] == ["creacion", "ratificacion", "transicion"]
    ap = meta["eventos"][1]["aprobacion"]
    assert ap["actor"] == "human:PER-H" and ap["roles"] == ["ROL-OP"] and ap["revision_base"] == base
    assert ap["digest"] == digest(*dec_x(), ACEPTAR)
    assert meta["eventos"][2]["valido_desde"] == "2026-11-05T00:00:00Z"
    assert validar(meta, cuerpo, modo="canonico") == []
    recibo = json.loads((recibos / "op-1.json").read_text(encoding="utf-8"))
    assert recibo["revision_integrada"] == canon and recibo["registros"] == ["DEC-X"]
    assert set(recibo["impacto"]) >= {"afectados", "advertencias"}


def test_esc03_5_repetir_la_operacion_devuelve_el_recibo_sin_segunda_aceptacion(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    primero = llamar(repo, base, prop, recibos)
    segundo = llamar(repo, base, prop, recibos)
    assert segundo["estado"] == "integrado" and segundo["repetido"] is True
    assert segundo["revision_integrada"] == primero["revision_integrada"] == repo.git("rev-parse", "canon")


def test_respuesta_perdida_se_reconcilia_desde_el_commit(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    primero = llamar(repo, base, prop, recibos)
    (recibos / "op-1.json").unlink()
    otra = llamar(repo, base, prop, recibos)
    assert otra["estado"] == "integrado" and otra["reconciliado"] is True
    assert otra["revision_integrada"] == primero["revision_integrada"] == repo.git("rev-parse", "canon")
    assert otra["registros"] == ["DEC-X"] and "afectados" in otra["impacto"]


def test_mismo_id_con_otra_solicitud_se_rechaza_sin_escribir(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    llamar(repo, base, prop, recibos)
    canon = repo.git("rev-parse", "canon")
    res = llamar(repo, base, prop, recibos, revisiones=[REVISION, {**REVISION, "review_id": 12}])
    assert res["estado"] == "bloqueado" and "ya se usó con otra solicitud" in res["motivo"]
    assert repo.git("rev-parse", "canon") == canon


def test_recibo_falsificado_no_vale(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    llamar(repo, base, prop, recibos)
    ruta = recibos / "op-1.json"
    recibo = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.write_text(json.dumps({**recibo, "revision_integrada": "0" * 40}), encoding="utf-8")
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "RESULTADO_DESCONOCIDO"


def test_trailer_falsificado_en_la_propuesta_no_reconcilia(entorno):
    # La propuesta trae en su mensaje un trailer con la huella real de una solicitud op-7 inventada.
    repo, base, recibos = entorno
    r, c = dec_x()
    inventada = "b" * 40
    peticion = {"rama": "canon", "carpeta": "kb", "base": base, "propuesta": inventada, "revisiones": [REVISION]}
    huella = hashlib.sha256(bytes_canonicos(peticion)).hexdigest()
    falso = f"propuesta\n\nOperacion-Id: op-7\nSolicitud-Sha256: {huella}\nBase: {base}\nPropuesta: {inventada}\n"
    prop = proponer(
        repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud("op-1", {"DEC-X": ACEPTAR})}, mensaje=falso
    )
    assert llamar(repo, base, prop, recibos)["estado"] == "integrado"
    otra = llamar(repo, base, inventada, recibos, op="op-7")
    # No se reconcilia: el commit falso no es del integrador ni está en la línea principal. Sigue la puerta normal.
    assert otra["estado"] == "bloqueado" and otra["codigo"] == "BASE_CAMBIADA" and not otra.get("reconciliado")
    assert not (recibos / "op-7.json").exists()


def test_base_cambiada_no_integra(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    otro = proponer(
        repo,
        base,
        {"kb/DEC-Z.md": serializar(registro("decision", id="DEC-Z", autorizado_por=["ROL-OP"]), CUERPO_DECISION)},
    )
    repo.git("update-ref", "refs/heads/canon", otro, base)
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "BASE_CAMBIADA"
    assert repo.git("rev-parse", "canon") == otro and not recibos.exists()


def test_base_esperada_simbolica_se_rechaza(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, base_esperada="canon")
    assert res["estado"] == "bloqueado" and "SHA" in res["motivo"]


def test_contenido_cambiado_despues_de_la_revision(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, ver=verificador(prop, base, commit=base))
    assert res["estado"] == "bloqueado" and res["codigo"] == "APROBACION_CADUCADA"
    assert repo.git("rev-parse", "canon") == base


def test_la_rama_cambia_durante_la_verificacion(entorno):
    # Otra escritura mueve canon mientras se verifican las revisiones: el compare-and-swap falla y nada se escribe.
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    otro = proponer(
        repo,
        base,
        {"kb/DEC-Z.md": serializar(registro("decision", id="DEC-Z", autorizado_por=["ROL-OP"]), CUERPO_DECISION)},
    )

    def mover():
        repo.git("update-ref", "refs/heads/canon", otro, base)

    res = llamar(repo, base, prop, recibos, ver=verificador(prop, base, al_llamar=mover))
    assert res["estado"] == "bloqueado" and res["codigo"] == "BASE_CAMBIADA"
    assert repo.git("rev-parse", "canon") == otro and not (recibos / "op-1.json").exists()


def test_esc03_4_una_persona_no_se_da_el_rol_que_usa_para_aprobar(entorno):
    # Humana activa sin rol en la base: la propuesta le da ROL-OP y acepta DEC-X con su revisión. Vale la política anterior.
    repo, base, recibos = entorno
    meta, cuerpo = parse(repo.git("show", f"{base}:kb/PER-N.md") + "\n")
    meta["ocupa"] = [{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}]
    r, c = dec_x()
    archivos = {"kb/PER-N.md": serializar(meta, cuerpo, modo="canonico"), "kb/DEC-X.md": serializar(r, c)}
    prop = proponer(repo, base, {**archivos, **solicitud("op-1", {"DEC-X": ACEPTAR})})
    res = llamar(repo, base, prop, recibos, ver=verificador(prop, base, user=300))
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE"
    assert repo.git("rev-parse", "canon") == base


def test_sin_revisiones_no_hay_integracion(entorno):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    res = llamar(repo, base, prop, recibos, revisiones=[])
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE"


def test_una_propuesta_sin_efectos_tambien_necesita_revision(entorno):
    repo, base, recibos = entorno
    r, c = dec_x()
    prop = proponer(repo, base, {"kb/DEC-X.md": serializar(r, c)})
    assert llamar(repo, base, prop, recibos, revisiones=[])["estado"] == "bloqueado"
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "integrado", res
    meta, _ = parse(repo.git("show", "canon:kb/DEC-X.md") + "\n")
    assert meta["estado"] == "propuesta" and [e["tipo_evento"] for e in meta["eventos"]] == ["creacion"]


def test_esc03_4_el_agente_no_se_da_el_rol_y_acepta_en_la_misma_operacion(entorno):
    repo, base, recibos = entorno
    texto = repo.git("show", f"{base}:kb/PER-AG.md") + "\n"
    meta, cuerpo = parse(texto)
    meta["ocupa"] = [{"rol": "ROL-OP", "desde": "2026-10-02T00:00:00Z"}]
    r, c = dec_x()
    archivos = {"kb/PER-AG.md": serializar(meta, cuerpo, modo="canonico"), "kb/DEC-X.md": serializar(r, c)}
    prop = proponer(repo, base, {**archivos, **solicitud("op-1", {"DEC-X": ACEPTAR})})
    res = llamar(repo, base, prop, recibos, ver=verificador(prop, base, user=900))
    assert res["estado"] == "bloqueado" and res["codigo"] == "AUTORIDAD_INSUFICIENTE"
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize(
    "archivos,mover",
    [
        ({"README.md": "cambiado\n"}, None),
        ({}, ("notas/guia.md", "kb/guia.md")),  # un renombrado borra el origen
        ({"kb/nota.md": "---\ntype: Guía\ntitle: x\n---\n"}, None),  # .md que no es registro del perfil
        ({"kb/index.md": "* [x](x.md)\n"}, None),
    ],
)
def test_solo_registros_de_la_carpeta(entorno, archivos, mover):
    repo, base, recibos = entorno
    r, c = dec_x()
    prop = proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), **archivos}, mover=mover)
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "bloqueado", res
    assert repo.git("rev-parse", "canon") == base


def test_clausula_aceptada_reescrita(entorno):
    repo, base, recibos = entorno
    texto = repo.git("show", f"{base}:kb/DEC-A.md") + "\n"
    clausula = '<clausula id="C1">\nLunes.\n</clausula>'
    assert texto.count(clausula) == 1
    prop = proponer(repo, base, {"kb/DEC-A.md": texto.replace(clausula, clausula.replace("Lunes.", "Martes."))})
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "ESQUEMA_INVALIDO"
    assert [h["ruta"] for h in res["hallazgos"]] == ["DEC-A/cuerpo"]


def test_dos_sustituciones_aceptadas_de_la_misma_clausula_son_conflicto(entorno):
    repo, base, recibos = entorno
    archivos = {}
    for ident, texto in (("DEC-B", "Martes."), ("DEC-D", "Jueves.")):
        r = registro(
            "decision",
            id=ident,
            autorizado_por=["ROL-OP"],
            modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": f"{ident}#C1"}],
        )
        archivos[f"kb/{ident}.md"] = serializar(r, cuerpo_de({"C1": texto}))
    prop = proponer(repo, base, {**archivos, **solicitud("op-1", {"DEC-B": ACEPTAR, "DEC-D": ACEPTAR})})
    res = llamar(repo, base, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "CONFLICTO_NORMATIVO"
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize("rama", ["main", "CANON", "alias"])
def test_rama_en_uso_simbolica_o_con_otro_nombre(entorno, rama):
    repo, base, recibos = entorno
    repo.git("symbolic-ref", "refs/heads/alias", "refs/heads/canon")
    prop = preparar_aceptacion(repo, base)
    try:
        cabeza = repo.git("rev-parse", rama)
    except subprocess.CalledProcessError:
        # `CANON` solo nombra `canon` donde las referencias no distinguen mayúsculas (Windows, macOS).
        pytest.skip("las referencias distinguen mayúsculas: no hay otro nombre que probar")
    res = llamar(repo, cabeza, prop, recibos, rama=rama)
    assert res["estado"] == "bloqueado"
    assert repo.git("rev-parse", "canon") == base


@pytest.mark.parametrize("op", ["../fuera", "a/b", "", "x" * 200])
def test_operacion_id_seguro(entorno, op):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    assert llamar(repo, base, prop, recibos, op=op)["estado"] == "bloqueado"


@pytest.mark.parametrize("carpeta", ["kb/..", ".", ":/", "kb\\x", "/kb"])
def test_carpeta_segura(entorno, carpeta):
    repo, base, recibos = entorno
    prop = preparar_aceptacion(repo, base)
    assert llamar(repo, base, prop, recibos, carpeta=carpeta)["estado"] == "bloqueado"


def test_solicitud_de_otra_operacion_no_vale(entorno):
    repo, base, recibos = entorno
    r, c = dec_x()
    prop = proponer(repo, base, {"kb/DEC-X.md": serializar(r, c), **solicitud("op-2", {"DEC-X": ACEPTAR})})
    res = llamar(repo, base, prop, recibos, op="op-1")
    assert res["estado"] == "bloqueado"  # el archivo de op-2 no es un registro ni la solicitud de op-1


def _base_con(repo, base, archivos):
    """Mueve canon a un commit con registros ya canónicos, como si se hubieran integrado antes."""
    nueva = proponer(repo, base, archivos)
    repo.git("update-ref", "refs/heads/canon", nueva, base)
    return nueva


def _sustituye_a1(ident, texto):
    return registro(
        "decision",
        id=ident,
        autorizado_por=["ROL-OP"],
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": f"{ident}#C1"}],
    ), cuerpo_de({"C1": texto})


def test_conflicto_con_una_decision_existente_que_entra_en_vigor_despues(entorno):
    # DEC-E, ya integrada, sustituye DEC-A#C1 desde el 10 dic. La nueva DEC-N la sustituye desde el 1 dic.
    # El 1 dic no hay conflicto; desde el 10 dic rigen las dos sin sucesión declarada.
    repo, base, recibos = entorno
    e, ce = decision(
        "DEC-E",
        {"C1": "Jueves."},
        registrado="2026-10-04T00:00:00Z",
        valido="2026-12-10T00:00:00Z",
        autorizado_por=["ROL-OP"],
        modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": "DEC-E#C1"}],
    )
    base2 = _base_con(repo, base, {"kb/DEC-E.md": canonico(e, ce)})
    n, cn = _sustituye_a1("DEC-N", "Martes.")
    desde_1 = [{**ACEPTAR[0], "valido_desde": "2026-12-01T00:00:00Z"}]
    prop = proponer(repo, base2, {"kb/DEC-N.md": serializar(n, cn), **solicitud("op-1", {"DEC-N": desde_1})})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "CONFLICTO_NORMATIVO", res
    assert res["conflictos"][0]["clausula"] == "DEC-A#C1"
    assert repo.git("rev-parse", "canon") == base2 and not (recibos / "op-1.json").exists()


def test_conflicto_previo_ajeno_no_bloquea_otra_integracion(entorno):
    # La base ya arrastra un conflicto entre DEC-E y DEC-F; una propuesta que no lo toca se integra y lo avisa.
    repo, base, recibos = entorno
    archivos = {}
    for ident, texto in (("DEC-E", "Jueves."), ("DEC-F", "Viernes.")):
        r, c = decision(
            ident,
            {"C1": texto},
            registrado="2026-10-04T00:00:00Z",
            autorizado_por=["ROL-OP"],
            modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": f"{ident}#C1"}],
        )
        archivos[f"kb/{ident}.md"] = canonico(r, c)
    base2 = _base_con(repo, base, archivos)
    r, c = dec_x()
    prop = proponer(repo, base2, {"kb/DEC-X.md": serializar(r, c)})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "integrado", res
    assert any("DEC-A#C1" in a for a in res["advertencias"])


def test_la_nueva_agrava_un_conflicto_previo_si_bloquea(entorno):
    # La base arrastra el conflicto DEC-E/DEC-F sobre DEC-A#C1; DEC-N entra como tercera candidata: empeora y bloquea.
    repo, base, recibos = entorno
    archivos = {}
    for ident, texto in (("DEC-E", "Jueves."), ("DEC-F", "Viernes.")):
        r, c = decision(
            ident,
            {"C1": texto},
            registrado="2026-10-04T00:00:00Z",
            autorizado_por=["ROL-OP"],
            modifica=[{"destino": "DEC-A#C1", "tipo": "sustitucion", "por": f"{ident}#C1"}],
        )
        archivos[f"kb/{ident}.md"] = canonico(r, c)
    base2 = _base_con(repo, base, archivos)
    n, cn = _sustituye_a1("DEC-N", "Martes.")
    prop = proponer(repo, base2, {"kb/DEC-N.md": serializar(n, cn), **solicitud("op-1", {"DEC-N": ACEPTAR})})
    res = llamar(repo, base2, prop, recibos)
    assert res["estado"] == "bloqueado" and res["codigo"] == "CONFLICTO_NORMATIVO"
    assert res["conflictos"][0]["candidatas"] == ["DEC-E#C1", "DEC-F#C1", "DEC-N#C1"]
    assert repo.git("rev-parse", "canon") == base2
