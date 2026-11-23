"""Arranque de la raíz de confianza de una instalación (KB-DPP implementación 0.8, «raíz inicial de confianza»).

La integración exige la autoridad de la política base: sin un rol activo que gobierne la política, nada puede activar
el primero. El arranque rompe ese círculo una sola vez. Activa los roles y la persona de la raíz, que ya están en la
rama canónica como propuestas sin historial, con eventos admitidos cuya evidencia es la cuenta del fundador verificada
en GitHub (`GET /user` con su propio token). Del llamante solo toma los IDs: la cuenta la da GitHub, y la persona debe
ser humana, declarar esa cuenta en `identidad_ref` y ocupar ya todos los roles de la raíz.

Se niega si la política ya tiene un rol activo con `gobernar_politica` (la raíz existe: los cambios van por la
integración), si algún registro de la raíz tiene eventos o no está propuesto, o si ningún rol de la raíz gobierna la
política. Escribe un commit aplanado sobre la base en la rama canónica por compare-and-swap, como la integración, y un
recibo. Límite: sin la protección de la rama en el remoto, el commit no prueba más que su contenido; deja constancia de
la cuenta verificada, pero no impide que otra cuenta con permiso de escritura escriba en la rama.
"""

import copy
import re
import tempfile
from pathlib import Path

from .autoridad import GOBERNAR, _ocupa
from .core import serializar
from .eventos import admitidos
from .github import cuenta_autenticada
from .integrar import (
    _OPERACION,
    _RAMA,
    _SHA,
    TRAILER,
    _ahora,
    _Bloqueo,
    _carpeta_segura,
    _escribir_huellas,
    _escribir_recibo,
    _Git,
    _rama_canonica,
)
from .schema import validar
from .snapshot import cargar
from .tiempo import es_instante
from .verificacion import ErrorDeVerificacion

ACTOR = "process:arranque"
MECANISMO = "arranque-github-user"
# Arranque declarado: la persona declara que es la raíz en una conversación; nadie verifica la identidad.
MECANISMO_DECLARADO = "arranque-declarado"
_DECLARACION = ("identidad", "sesion", "instante", "cita")
_IDENTIDAD_DECLARADA = re.compile(r"declarada:\S+")
# Identidad propia de los commits del arranque: no se confunden con los del integrador.
_IDENTIDAD_ARRANQUE = {
    "GIT_AUTHOR_NAME": "arranque-local",
    "GIT_AUTHOR_EMAIL": "arranque@localhost",
    "GIT_COMMITTER_NAME": "arranque-local",
    "GIT_COMMITTER_EMAIL": "arranque@localhost",
}


def arrancar(
    repo, *, rama, carpeta, base_esperada, persona, roles, recibos, operacion_id, cliente=None, declaracion=None
):
    """Activa la raíz y devuelve el recibo, o un resultado `bloqueado` con su código. No reintenta solo.

    La identidad llega por un canal y solo uno: `cliente`, verificada con GitHub (`GET /user`), o `declaracion`,
    declarada por la persona en una conversación y citada, sin autenticar (elecciones, «Mecanismos no conformes»).
    """
    try:
        if not isinstance(persona, str) or not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            raise _Bloqueo(None, "persona es un ID y roles una lista de IDs")
        if (cliente is None) == (declaracion is None):
            raise _Bloqueo(None, "la identidad de la raíz llega por un canal y solo uno: cliente o declaracion")
        return _arrancar(
            _Git(repo), rama, carpeta, base_esperada, persona, roles, cliente, declaracion, Path(recibos), operacion_id
        )
    except _Bloqueo as b:
        return {"operacion_id": operacion_id, **b.resultado}


def _entradas(rama, carpeta, base, op):
    if not isinstance(op, str) or not _OPERACION.fullmatch(op):
        raise _Bloqueo(None, "operacion_id inválido: letras, cifras, punto, guion y subrayado, hasta 100")
    if not isinstance(rama, str) or not _RAMA.fullmatch(rama) or ".." in rama or rama.endswith((".lock", "/")):
        raise _Bloqueo(None, "nombre de rama inválido")
    if not isinstance(base, str) or not _SHA.fullmatch(base):
        raise _Bloqueo(None, "base_esperada debe ser un SHA completo de 40 caracteres")
    return _carpeta_segura(carpeta)


def _raiz_existente(snap):
    """Por qué la raíz ya se estableció alguna vez, o None.

    Basta con que un rol que gobierna la política tenga historial admitido, esté activo o no, o con que algún registro
    lleve un evento del arranque: retirar después ese rol no abre la puerta a un segundo arranque con otra cuenta.
    """
    for ident, r in sorted(snap.registros.items()):
        eventos = admitidos(r.get("eventos") or [])
        if r.get("type") == "rol" and GOBERNAR in (r.get("capacidades") or []) and eventos:
            return f"{ident} gobierna la política y ya tiene historial"
        if any((e.get("evidencia_evento") or {}).get("mecanismo") in (MECANISMO, MECANISMO_DECLARADO) for e in eventos):
            return f"{ident} ya tiene un evento del arranque"
    return None


def _propuesto(snap, ident, tipo):
    r = snap.registros.get(ident)
    if r is None or r.get("type") != tipo:
        raise _Bloqueo("REFERENCIA_AUSENTE", f"{ident} no es un {tipo} de la base")
    if r.get("estado") != "propuesta" or r.get("eventos"):
        raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident} ha de estar en propuesta y sin eventos para arrancar la raíz")
    return r


def _identidad(cliente, declaracion, ahora):
    """(identidad, evidencia del evento, datos para el recibo y el trailer) del canal que se usa."""
    if declaracion is not None:
        if not isinstance(declaracion, dict) or set(declaracion) != set(_DECLARACION):
            raise _Bloqueo("ESQUEMA_INVALIDO", f"la declaración lleva exactamente {', '.join(_DECLARACION)}")
        identidad, sesion, cuando, cita = (declaracion[k] for k in _DECLARACION)
        if not isinstance(identidad, str) or not _IDENTIDAD_DECLARADA.fullmatch(identidad):
            raise _Bloqueo("ESQUEMA_INVALIDO", "la identidad declarada tiene la forma declarada:<alias>")
        if not all(isinstance(x, str) and x.strip() for x in (sesion, cita)) or not es_instante(cuando):
            raise _Bloqueo("ESQUEMA_INVALIDO", "la declaración necesita sesión, instante con zona y la cita literal")
        resumen = f"{identidad}, {sesion}, {cuando}: «{cita}» (declarada, sin autenticar)"
        datos = {"identidad": identidad, "sesion": sesion, "instante": cuando, "cita": cita, "autenticada": False}
        return identidad, {"mecanismo": MECANISMO_DECLARADO, "comprobante": resumen}, datos
    try:
        cuenta = cuenta_autenticada(cliente)
    except ErrorDeVerificacion as exc:
        raise _Bloqueo(exc.codigo, str(exc)) from exc
    identidad = f"github:{cuenta['id']}"
    evidencia = {"mecanismo": MECANISMO, "comprobante": f"{identidad} ({cuenta['login']}) en {ahora}"}
    return identidad, evidencia, cuenta


def _arrancar(git, rama, carpeta, base, persona_id, roles_ids, cliente, declaracion, recibos, op):
    carpeta = _entradas(rama, carpeta, base, op)
    if not roles_ids or len(set(roles_ids)) != len(roles_ids) or persona_id in roles_ids:
        raise _Bloqueo(None, "la raíz necesita al menos un rol, sin repetidos, y una persona")
    ref = f"refs/heads/{rama}"
    _rama_canonica(git, ref)
    actual = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    if actual != base:
        raise _Bloqueo("BASE_CAMBIADA", f"{rama} está en {actual[:12]}, no en la base esperada {base[:12]}")
    snap, cobertura = cargar(git.repo, carpeta, base, modo="propuesta")
    if cobertura["estado"] != "completo":
        raise _Bloqueo("ESQUEMA_INVALIDO", "la base no es coherente", cobertura=cobertura)
    ahora = _ahora()
    existente = _raiz_existente(snap)
    if existente:
        raise _Bloqueo("RAIZ_YA_ESTABLECIDA", f"{existente}: los cambios de la política pasan por la integración")
    if (recibos / f"{op}.json").exists():
        raise _Bloqueo(None, f"ya hay un recibo con el operacion_id {op}: no se sobrescribe")

    roles = {i: _propuesto(snap, i, "rol") for i in roles_ids}
    persona = _propuesto(snap, persona_id, "persona")
    # Tras el arranque la base debe ser canónica: la integración la carga así y todo registro necesita historial.
    sin_historial = sorted(
        i
        for i, r in snap.registros.items()
        if i not in roles and i != persona_id and not admitidos(r.get("eventos") or [])
    )
    if sin_historial:
        raise _Bloqueo(
            "ESQUEMA_INVALIDO",
            f"la carpeta tiene registros sin historial admitido fuera de la raíz ({', '.join(sin_historial)}): "
            "salen de la rama canónica y vuelven a entrar por la integración después del arranque",
        )
    if not any(GOBERNAR in (r.get("capacidades") or []) for r in roles.values()):
        raise _Bloqueo("AUTORIDAD_INSUFICIENTE", "ningún rol de la raíz gobierna la política (gobernar_politica)")
    if persona.get("naturaleza") != "humana":
        raise _Bloqueo("AUTORIDAD_INSUFICIENTE", f"{persona_id} no es una persona humana: un agente no es la raíz")
    for i in roles_ids:
        if not _ocupa(persona, i, ahora):
            raise _Bloqueo("AUTORIDAD_INSUFICIENTE", f"{persona_id} no ocupa {i} ahora")
    identidad, evidencia, cuenta = _identidad(cliente, declaracion, ahora)
    if persona.get("identidad_ref") != identidad:
        raise _Bloqueo("AUTORIDAD_INSUFICIENTE", f"la identidad ({identidad}) no es la que declara {persona_id}")

    finales, n = {}, 0
    for ident in [*roles_ids, persona_id]:
        r = copy.deepcopy(snap.registros[ident])
        eventos = []
        for anterior, nuevo, tipo in ((None, "propuesta", "creacion"), ("propuesta", "activa", "transicion")):
            n += 1
            eventos.append(
                {
                    "evento_id": f"{op}-{n}",
                    "tipo_evento": tipo,
                    "actor": ACTOR,
                    "registrado_en": ahora,
                    "valido_desde": ahora,
                    "motivo": f"arranque de la raíz de confianza ({op})",
                    "evidencia_evento": dict(
                        evidencia
                    ),  # una copia por evento: un objeto compartido sería un alias YAML
                    "estado_anterior": anterior,
                    "estado_nuevo": nuevo,
                }
            )
        r["eventos"], r["estado"] = eventos, "activa"
        r.pop("status", None)
        errores = [h for h in validar(r, snap.cuerpos[ident], modo="canonico") if h["severidad"] == "error"]
        if errores:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: el registro activado no es canónico", hallazgos=errores)
        finales[ident] = (r, snap.cuerpos[ident])

    nuevo = _commit(git, base, op, identidad, finales, snap, carpeta)
    # La integración cargará esta revisión en modo canónico: si no carga completa, no se escribe la rama.
    _, final = cargar(git.repo, carpeta, nuevo)
    if final["estado"] != "completo":
        raise _Bloqueo(
            "ESQUEMA_INVALIDO", "tras el arranque la base no sería canónica: nada se escribió", cobertura=final
        )
    if git("update-ref", ref, nuevo, base, comprobar=False) != 0:
        raise _Bloqueo("BASE_CAMBIADA", "la rama cambió mientras se arrancaba: nada se escribió en ella")
    recibo = {
        "operacion_id": op,
        "estado": "arrancado",
        "codigo": None,
        "rama": rama,
        "base": base,
        "revision_integrada": nuevo,
        "registros": [*roles_ids, persona_id],
        "cuenta": cuenta,
        "registrado_en": ahora,
    }
    try:
        _escribir_recibo(recibos / f"{op}.json", recibo)
    except OSError as exc:
        return {**recibo, "recibo_persistido": False, "advertencia": f"arrancado, pero el recibo no se guardó: {exc}"}
    return recibo


def _commit(git, base, op, identidad, finales, snap, carpeta):
    """Commit aplanado sobre la base con los registros activados, sin mover todavía la rama."""
    with tempfile.TemporaryDirectory(prefix="kb-indice-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), **_IDENTIDAD_ARRANQUE}
        git("read-tree", base, extra_env=env)
        escritos = {}
        for ident, (r, c) in sorted(finales.items()):
            texto = serializar(r, c, modo="canonico")
            blob = git("hash-object", "-w", "--stdin", entrada=texto.encode("utf-8"), extra_env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{snap.rutas[ident]}", extra_env=env)
            escritos[ident] = (snap.rutas[ident], texto)
        _escribir_huellas(git, base, carpeta, escritos, env)
        arbol = git("write-tree", extra_env=env)
        mensaje = f"kb: arranque {op}\n\n{TRAILER}: {op}\nArranque: {identidad}\nBase: {base}\n"
        return git("commit-tree", arbol, "-p", base, entrada=mensaje.encode("utf-8"), extra_env=env)
