"""Integración local controlada en una rama canónica de git (núcleo 0.7, §7 «Puerta de integración» y «Recibos»).

Qué aprueba la persona: el diff de la PR, que compara la base esperada con el commit propuesto e incluye los
registros y, si los hay, los efectos solicitados en `<carpeta>/_solicitudes/<operacion_id>.json`. Quien llama solo
identifica las revisiones; el integrador calcula los digests, verifica cada revisión en el canal de confianza y
construye las aprobaciones con datos verificados. Toda integración exige autoridad sobre cada registro tocado, aunque
sea una propuesta sin efectos: la integración conserva su autorización.

Secuencia: recibo previo contrastado con la rama, o reconciliación por un commit del integrador → base actual igual
a la esperada (si no, `BASE_CAMBIADA`, sin reintentar) → la propuesta desciende de la base y solo toca registros de
la carpeta y su archivo de solicitud → mutabilidad → autoridad bajo la política de la base, revalidada al integrar →
eventos admitidos con el reloj del integrador → referencias, ciclos y conflictos sobre el árbol final → vocabulario
del dominio sobre el mismo árbol → commit aplanado sobre la base con plumbing de git y compare-and-swap → relectura → recibo con la deuda de impacto.

La parte de solo lectura entre la base y la propuesta (`preparar_solicitud`) y la comprobación del árbol final
(`arbol_final`) son las mismas que usa el paquete de aprobación (`kbol.paquete`): lo que se muestra antes de aprobar
lleva los digests que esta puerta recalcula.

Modos de aprobación. `toda` (por defecto) es el del contrato. `decisiva` es una elección local no conforme
(docs/elecciones.md, «Mecanismos no conformes»): solo exige aprobación para lo decisivo (`DECISIVAS`, los cambios
de política y la importación que sustituye o cierra); lo demás entra con el actor de la operación, que firma cada
evento.

No ejecuta nada del contenido propuesto, no toca ningún árbol de trabajo y no escribe en una rama con checkout. La
integración remota en `main` de una instalación queda deshabilitada hasta su arranque (`kbol.arranque`) y la
protección de la rama en el remoto.
"""

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import huellas as huellas_mod
from . import vocabulario as vocabulario_mod
from .autoridad import evaluar
from .consolidar import consolidar
from .core import ErrorDeFormato, serializar
from .core import parse as parse_heredado
from .digest import bytes_canonicos, comprobar_efectos, digest
from .eventos import ErrorDeHistorial
from .impacto import impacto
from .importacion import comprobar as comprobar_importacion
from .importacion import redistribuye
from .modelo import INICIAL, PRECISIONES, TRANSICIONES
from .mutabilidad import comparar
from .proyeccion import Snapshot
from .referencias import validar_snapshot
from .schema import validar
from .snapshot import cargar, carpetas_de, entorno_git
from .tiempo import es_fecha, es_instante, instante
from .verificacion import ErrorDeVerificacion, clave_de_revision

ACTOR = "process:integrador-local"
MODOS = ("toda", "decisiva")
# Transiciones decisivas en el modo `decisiva`: aceptar o rechazar una decisión; autorizar, cerrar o cancelar un
# plan o un hito. Empezar un hito, resolver una pregunta o validar una hipótesis entran con su actor.
DECISIVAS = {
    "decision": {"aceptada", "rechazada"},
    "plan": {"autorizado", "cerrado", "cancelado"},
    "hito": {"autorizado", "completado", "cancelado"},
    "hecho": {"aceptada", "rechazada"},
}
# Personas, roles y entidades: cualquier transición cambia quién decide o qué existe para la política.
POLITICA_DECISIVA = ("persona", "rol")
# Una importación con estas relaciones fija qué sustituye o cierra a qué: es decisiva.
RELACIONES_DECISIVAS = ("modifica", "deja_obsoleta", "resuelta_por", "define")
_IDS_HEREDADOS = re.compile(r"\b(?:ADR-\d{4}|QD-\d{3,}|HD-\d{3,}|PL-\d{3}(?:-H\d+)?)\b")
_ACTOR = re.compile(r"^(human:\S+|process:\S+|[^\s/:]+/[^\s/]+)(?!\n)$")
TRAILER = "Operacion-Id"
CORREO = "integrador@localhost"
_OPERACION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_RAMA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
_SHA = re.compile(r"[0-9a-f]{40}")
_IDENTIDAD = {
    "GIT_AUTHOR_NAME": "integrador-local",
    "GIT_AUTHOR_EMAIL": CORREO,
    "GIT_COMMITTER_NAME": "integrador-local",
    "GIT_COMMITTER_EMAIL": CORREO,
}


class Bloqueo(Exception):
    """La puerta no sigue: `resultado` es el `bloqueado` con su código y su motivo, el mismo que da `integrar`."""

    def __init__(self, codigo, motivo, **extra):
        super().__init__(motivo)
        self.resultado = {"estado": "bloqueado", "codigo": codigo, "motivo": motivo, **extra}


_Bloqueo = Bloqueo  # nombre interno, que comparte el arranque


@dataclass(frozen=True)
class SolicitudPreparada:
    """Lo que la puerta sabe de una propuesta antes de mirar la autoridad (`preparar_solicitud`).

    `efectos` son las transiciones de la solicitud con su `estado_anterior` ya rellenado; `importaciones`, las
    importaciones comprobadas contra su heredado, con `estado_heredado` y los motivos que las hacen decisivas.
    """

    operacion_id: str
    base: str
    propuesta: str
    base_snap: Snapshot
    prop_snap: Snapshot
    mut: dict
    efectos: dict
    importaciones: dict
    tocados: list

    def digests(self):
        """{ID: digest} de cada registro tocado: el que recalcula la autoridad al integrar."""
        regs, cuerpos = self.prop_snap.registros, self.prop_snap.cuerpos
        return {
            i: digest(regs[i], cuerpos[i], *lo_aprobable(i, self.efectos, self.importaciones)) for i in self.tocados
        }

    def motivos_decisivos(self, ident):
        return motivos_decisivos(
            ident, self.prop_snap.registros[ident], self.efectos, self.mut["cambios_de_politica"], self.importaciones
        )


class _Git:
    def __init__(self, repo):
        self.repo = str(repo)

    def __call__(self, *args, entrada=None, extra_env=None, comprobar=True, crudo=False):
        env = {**entorno_git(), **(extra_env or {})}
        p = subprocess.run(
            ["git", "--literal-pathspecs", "-C", self.repo, *args], input=entrada, capture_output=True, env=env
        )
        if not comprobar:
            return p.returncode
        if p.returncode != 0:
            raise _Bloqueo(
                "RESULTADO_DESCONOCIDO", f"git {args[0]} falló: {p.stderr.decode('utf-8', 'replace').strip()}"
            )
        return p.stdout if crudo else p.stdout.decode("utf-8").strip()


def _ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _escribir_recibo(ruta, recibo):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(recibo, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def integrar(
    repo,
    *,
    rama,
    carpeta,
    operacion_id,
    base_esperada,
    propuesta_rev,
    revisiones,
    verificador,
    recibos,
    aprobacion="toda",
    actor=ACTOR,
):
    """Integra la propuesta y devuelve el recibo, o un resultado `bloqueado` con su código. Nunca reintenta solo.

    `aprobacion` es `toda` o `decisiva`; `actor`, quien ejecuta la operación (`human:…`, `process:…` o
    `cliente/modelo`), que firma los eventos que escribe la integración.
    """
    try:
        if aprobacion not in MODOS:
            raise _Bloqueo(None, f"modo de aprobación desconocido: {aprobacion!r}")
        if not isinstance(actor, str) or not _ACTOR.match(actor):
            raise _Bloqueo(None, "actor inválido: human:<id>, process:<nombre> o <cliente>/<modelo>")
        return _integrar(
            _Git(repo),
            rama,
            carpeta,
            operacion_id,
            base_esperada,
            propuesta_rev,
            revisiones,
            verificador,
            Path(recibos),
            aprobacion,
            actor,
        )
    except _Bloqueo as b:
        return {"operacion_id": operacion_id, **b.resultado}


def _carpeta_segura(carpeta):
    """La carpeta, o la tupla de carpetas sin repetidas ni anidadas; la primera guarda la política y las solicitudes."""
    if isinstance(carpeta, (list, tuple)):
        if not carpeta:
            raise _Bloqueo(None, "una instalación tiene al menos una carpeta de conocimiento")
        carpetas = tuple(_una_carpeta(c) for c in carpeta)
        for i, a in enumerate(carpetas):
            for b in carpetas[i + 1 :]:
                if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                    raise _Bloqueo(None, f"carpetas repetidas o anidadas: {a} y {b}")
        return carpetas[0] if len(carpetas) == 1 else carpetas
    return _una_carpeta(carpeta)


def _una_carpeta(carpeta):
    if not isinstance(carpeta, str) or not carpeta or "\\" in carpeta or carpeta.startswith((":", "/")):
        raise _Bloqueo(None, "la carpeta de conocimiento debe ser una subcarpeta relativa y explícita")
    partes = PurePosixPath(carpeta).parts
    if not partes or any(p in ("..", ".") for p in partes):
        raise _Bloqueo(None, "la carpeta de conocimiento no admite componentes . ni ..")
    return "/".join(partes)


def _comprobar_operacion(op):
    if not isinstance(op, str) or not _OPERACION.fullmatch(op):
        raise _Bloqueo(None, "operacion_id inválido: letras, cifras, punto, guion y subrayado, hasta 100")


def _comprobar_shas(base_esperada, propuesta_rev):
    for nombre, valor in (("base_esperada", base_esperada), ("propuesta_rev", propuesta_rev)):
        if not isinstance(valor, str) or not _SHA.fullmatch(valor):
            raise _Bloqueo(None, f"{nombre} debe ser un SHA completo de 40 caracteres")


def preparar_solicitud(repo, *, carpeta, operacion_id, base, propuesta):
    """La parte de solo lectura de la puerta, hasta saber qué se aprueba de cada registro: `SolicitudPreparada`.

    Hace lo mismo que la integración entre la base y la propuesta (rutas, solicitud, mutabilidad, efectos e
    importaciones), con el mismo código, y lanza `Bloqueo` con el mismo código donde ella bloquearía. No mira la rama
    canónica, los recibos ni la autoridad. Cero registros tocados no bloquea aquí: lo decide quien llama.
    """
    git = _Git(repo)
    _comprobar_operacion(operacion_id)
    carpeta = _carpeta_segura(carpeta)
    _comprobar_shas(base, propuesta)
    if git("cat-file", "-e", f"{base}^{{commit}}", comprobar=False) != 0:
        raise _Bloqueo("REFERENCIA_AUSENTE", "el commit base no existe en el repositorio")
    return _preparar(git, carpeta, operacion_id, base, propuesta)


def arbol_final(preparada):
    """(árbol final, advertencias, vocabulario) que escribiría la integración, sin las ratificaciones pendientes.

    Las mismas comprobaciones que hace la puerta después de la autoridad: registros finales canónicos, referencias,
    ciclos, conflictos normativos y vocabulario del dominio. Ninguna depende de las ratificaciones salvo la que exige
    una antes de aceptar, que aquí no se exige. Lanza `Bloqueo` donde la puerta bloquearía. Los eventos llevan el
    reloj de ahora. `vocabulario` son los hallazgos de términos y ámbitos que la puerta avisaría en el recibo.
    """
    p = preparada
    ahora = _ahora()
    sin_aprobar = {i: [] for i in p.tocados}
    finales = _materializar(
        p.operacion_id,
        ahora,
        p.tocados,
        p.efectos,
        sin_aprobar,
        p.mut,
        p.prop_snap,
        p.importaciones,
        p.base,
        aprobacion_pendiente=True,
    )
    final, advertencias = _comprobar_final(p.base_snap, p.prop_snap, finales)
    return final, advertencias, _comprobar_vocabulario(p.base_snap, final, p.efectos, p.tocados, ahora)


def _preparar(git, carpeta, op, base, prop):
    if git("cat-file", "-e", f"{prop}^{{commit}}", comprobar=False) != 0:
        raise _Bloqueo("REFERENCIA_AUSENTE", "el commit propuesto no existe en el repositorio")
    if git("merge-base", "--is-ancestor", base, prop, comprobar=False) != 0:
        raise _Bloqueo("BASE_CAMBIADA", "la propuesta no desciende de la base")
    base_snap, cob_b = cargar(git.repo, carpeta, base, heredados=True)
    if cob_b["estado"] != "completo":
        raise _Bloqueo("ESQUEMA_INVALIDO", "la base no es coherente", cobertura=cob_b)
    prop_snap, cob_p = cargar(git.repo, carpeta, prop, modo="propuesta", heredados=True)
    if cob_p["estado"] != "completo":
        raise _Bloqueo("ESQUEMA_INVALIDO", "la propuesta no es coherente", cobertura=cob_p)
    efectos, importaciones = _rutas_y_solicitud(git, base, prop, carpeta, op, base_snap, prop_snap)
    mut = comparar(base_snap, prop_snap)
    errores = [h for h in mut["hallazgos"] if h["severidad"] == "error"]
    if errores:
        raise _Bloqueo("ESQUEMA_INVALIDO", "la propuesta cambia contenido protegido", hallazgos=errores)
    efectos = _comprobar_efectos(efectos, prop_snap)
    importaciones = _comprobar_importaciones(git, base, base_snap, prop_snap, importaciones, efectos, mut)
    tocados = sorted(set(mut["nuevos"]) | set(mut["modificados"]) | set(efectos))
    return SolicitudPreparada(op, base, prop, base_snap, prop_snap, mut, efectos, importaciones, tocados)


def _integrar(git, rama, carpeta, op, base_esperada, propuesta_rev, revisiones, verificador, recibos, modo, actor):
    _comprobar_operacion(op)
    if not isinstance(rama, str) or not _RAMA.fullmatch(rama) or ".." in rama or rama.endswith((".lock", "/")):
        raise _Bloqueo(None, "nombre de rama inválido")
    carpeta = _carpeta_segura(carpeta)
    _comprobar_shas(base_esperada, propuesta_rev)
    solicitud = {
        "rama": rama,
        "carpeta": list(carpetas_de(carpeta)) if not isinstance(carpeta, str) else carpeta,
        "base": base_esperada,
        "propuesta": propuesta_rev,
        "revisiones": revisiones,
    }
    if modo != "toda" or actor != ACTOR:  # la solicitud de siempre conserva su huella
        solicitud.update(aprobacion=modo, actor=actor)
    try:
        huella = hashlib.sha256(bytes_canonicos(solicitud)).hexdigest()
    except ValueError as exc:
        raise _Bloqueo("ESQUEMA_INVALIDO", f"solicitud no serializable: {exc}") from exc
    ref = f"refs/heads/{rama}"
    ruta_recibo = recibos / f"{op}.json"
    _rama_canonica(git, ref)
    previo = _recibo_previo(git, ref, ruta_recibo, op, huella, carpeta)
    if previo:
        return previo
    reconciliado = _reconciliar(git, ref, op, huella, carpeta, ruta_recibo)
    if reconciliado:
        return reconciliado
    actual = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    if actual != base_esperada:
        raise _Bloqueo(
            "BASE_CAMBIADA", f"{rama} está en {actual[:12]}, no en la base esperada {base_esperada[:12]}: revalidar"
        )
    base, prop = base_esperada, propuesta_rev
    p = _preparar(git, carpeta, op, base, prop)
    base_snap, prop_snap, mut = p.base_snap, p.prop_snap, p.mut
    efectos, importaciones, tocados = p.efectos, p.importaciones, p.tocados
    if not tocados:
        raise _Bloqueo(None, "la propuesta no cambia ningún registro")
    ahora = _ahora()
    aprobaciones = _autoridad(
        tocados,
        efectos,
        mut["cambios_de_politica"],
        revisiones,
        base_snap,
        prop_snap,
        verificador,
        prop,
        base,
        ahora,
        importaciones,
        modo,
    )
    finales = _materializar(op, ahora, tocados, efectos, aprobaciones, mut, prop_snap, importaciones, base, modo, actor)
    final_snap, advertencias = _comprobar_final(base_snap, prop_snap, finales)
    terminos = _comprobar_vocabulario(base_snap, final_snap, efectos, tocados, ahora)
    advertencias = advertencias + [aviso_de_vocabulario(h) for h in terminos]
    deuda = impacto(base_snap, final_snap)

    nuevo = _escribir_commit(git, ref, actual, prop, op, huella, finales, prop_snap, aprobaciones, modo, actor, carpeta)
    if nuevo is None:
        reconciliado = _reconciliar(git, ref, op, huella, carpeta, ruta_recibo)
        if reconciliado:
            return reconciliado
        raise _Bloqueo("BASE_CAMBIADA", "la rama cambió mientras se integraba: nada se escribió en ella")
    if git("rev-parse", "--verify", "--end-of-options", ref) != nuevo:
        raise _Bloqueo("RESULTADO_DESCONOCIDO", "la rama no apunta al commit escrito: inspeccionar antes de reintentar")
    recibo = {
        "operacion_id": op,
        "estado": "integrado",
        "codigo": None,
        "solicitud_sha256": huella,
        "rama": rama,
        "base": base,
        "propuesta": prop,
        "revision_integrada": nuevo,
        "registros": tocados,
        "eventos": sorted(
            e["evento_id"] for r, _ in finales.values() for e in r["eventos"] if e["evento_id"].startswith(f"{op}-")
        ),
        "aprobaciones": sorted({a["aprobacion_id"] for lista in aprobaciones.values() for a in lista}),
        "aprobaciones_detalle": _detalle(aprobaciones),
        "modo_aprobacion": modo,
        "actor": actor,
        "decisivos": sorted(i for i, lista in aprobaciones.items() if lista),
        "impacto": deuda,
        "advertencias": advertencias,
        "registrado_en": ahora,
        "reconciliado": False,
        "repetido": False,
    }
    try:
        _escribir_recibo(ruta_recibo, recibo)
    except OSError as exc:
        return {**recibo, "recibo_persistido": False, "advertencia": f"integrado, pero el recibo no se guardó: {exc}"}
    return recibo


def _rama_canonica(git, ref):
    """La rama existe, no es un enlace simbólico y no tiene checkout en ningún worktree (sin distinguir mayúsculas)."""
    if git("check-ref-format", ref, comprobar=False) != 0:
        raise _Bloqueo(None, f"{ref} no es un nombre de rama válido")
    if git("symbolic-ref", "-q", ref, comprobar=False) == 0:
        raise _Bloqueo(None, f"{ref} es un enlace simbólico: el integrador solo escribe en una rama real")
    nombres = git("for-each-ref", "--format=%(refname)", "refs/heads/").splitlines()
    reales = [n for n in nombres if n.casefold() == ref.casefold()]
    if reales != [ref]:
        raise _Bloqueo("REFERENCIA_AUSENTE", f"no existe la rama {ref} con ese nombre exacto")
    en_uso = [
        linea.split(" ", 1)[1].casefold()
        for linea in git("worktree", "list", "--porcelain").splitlines()
        if linea.startswith("branch ")
    ]
    if ref.casefold() in en_uso:
        raise _Bloqueo(None, f"{ref} está en uso en un worktree: el integrador no escribe en una rama con checkout")


def _es_commit_del_integrador(git, commit, op, huella):
    """Commit de la línea principal escrito por el integrador para esta operación: (Base, Propuesta) o None."""
    datos = git(
        "show",
        "-s",
        "--format=%P%x00%ce%x00%(trailers:key=Operacion-Id,valueonly,separator=%x01)%x00"
        "%(trailers:key=Solicitud-Sha256,valueonly)%x00%(trailers:key=Base,valueonly)%x00"
        "%(trailers:key=Propuesta,valueonly)",
        "--end-of-options",
        commit,
    ).split("\x00")
    padres, correo, ops, sol, base, prop = (d.strip() for d in datos[:6])
    if correo != CORREO or ops.split("\x01") != [op] or padres.split() != [base]:
        return None
    if sol != huella:
        raise _Bloqueo(None, "este operacion_id ya se integró con otra solicitud", revision_integrada=commit)
    return base, prop


def _recibo_previo(git, ref, ruta, op, huella, carpeta):
    """Un recibo previo solo vale si su commit está en la línea principal de la rama y es del integrador.

    Lo que describe el cambio (base, propuesta, registros e impacto) se rehace desde ese commit, no se lee del archivo.
    """
    if not ruta.exists():
        return None
    try:
        recibo = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _Bloqueo("RESULTADO_DESCONOCIDO", f"recibo ilegible: {exc}") from exc
    if recibo.get("solicitud_sha256") != huella:
        raise _Bloqueo(None, "este operacion_id ya se usó con otra solicitud: usar un identificador nuevo")
    commit = recibo.get("revision_integrada")
    principal = git("rev-list", "--first-parent", "--end-of-options", ref).splitlines()
    par = (
        _es_commit_del_integrador(git, commit, op, huella) if isinstance(commit, str) and commit in principal else None
    )
    if par is None:
        raise _Bloqueo("RESULTADO_DESCONOCIDO", "el recibo no corresponde a la rama: inspeccionar antes de reintentar")
    base, prop = par
    deuda = impacto(cargar(git.repo, carpeta, base)[0], cargar(git.repo, carpeta, commit)[0])
    return {
        **recibo,
        "base": base,
        "propuesta": prop,
        "registros": deuda["cambiados"],
        "impacto": deuda,
        "repetido": True,
    }


def _reconciliar(git, ref, op, huella, carpeta, ruta):
    """Si la línea principal ya tiene el commit del integrador para la operación, la respuesta se perdió."""
    for commit in git("rev-list", "--first-parent", "--end-of-options", ref).splitlines():
        par = _es_commit_del_integrador(git, commit, op, huella)
        if par is None:
            continue
        base, prop = par
        deuda = impacto(cargar(git.repo, carpeta, base)[0], cargar(git.repo, carpeta, commit)[0])
        recibo = {
            "operacion_id": op,
            "estado": "integrado",
            "codigo": None,
            "solicitud_sha256": huella,
            "base": base,
            "propuesta": prop,
            "revision_integrada": commit,
            "registros": deuda["cambiados"],
            "impacto": deuda,
            "registrado_en": _ahora(),
            "reconciliado": True,
            "repetido": False,
            "nota": "recibo reconstruido desde el commit del integrador: la respuesta original se perdió",
        }
        try:
            _escribir_recibo(ruta, recibo)
        except OSError as exc:
            recibo.update(recibo_persistido=False, advertencia=f"el recibo no se guardó: {exc}")
        return recibo
    return None


def _rutas_y_solicitud(git, base, prop, carpeta, op, base_snap, prop_snap):
    """Comprueba que la propuesta solo toca registros de la carpeta y devuelve los efectos de su solicitud."""
    salida = git("diff-tree", "-r", "--no-renames", "--name-status", "-z", base, prop, crudo=True).decode("utf-8")
    campos = [c for c in salida.split("\0") if c]
    cambios = list(zip(campos[0::2], campos[1::2]))
    solicitud = f"{carpetas_de(carpeta)[0]}/_solicitudes/{op}.json"
    registros = set(prop_snap.rutas.values()) | set(base_snap.rutas.values())
    efectos, importaciones = {}, {}
    for estado, ruta in cambios:
        if ruta == solicitud:
            if estado != "A":
                raise _Bloqueo(None, "la solicitud de esta operación ya existía: usar un operacion_id nuevo")
            efectos, importaciones = _leer_solicitud(git, prop, ruta, op)
        elif ruta not in registros:
            raise _Bloqueo(None, f"la propuesta toca algo que no es un registro de la carpeta de conocimiento: {ruta}")
    return efectos, importaciones


def _leer_solicitud(git, prop, ruta, op):
    def sin_repetidas(pares):
        if len({k for k, _ in pares}) != len(pares):
            raise ValueError("clave repetida")
        return dict(pares)

    try:
        datos = json.loads(git("show", f"{prop}:{ruta}"), object_pairs_hook=sin_repetidas)
    except ValueError as exc:
        raise _Bloqueo("ESQUEMA_INVALIDO", f"solicitud ilegible: {exc}") from exc
    if (
        not isinstance(datos, dict)
        or not {"operacion_id", "efectos"} <= set(datos) <= {"operacion_id", "efectos", "importaciones"}
        or datos["operacion_id"] != op
    ):
        raise _Bloqueo(
            "ESQUEMA_INVALIDO",
            "la solicitud lleva operacion_id (el de esta operación), efectos y, si importa, importaciones",
        )
    return datos["efectos"], datos.get("importaciones", {})


def _comprobar_efectos(efectos, prop_snap):
    if not isinstance(efectos, dict):
        raise _Bloqueo("ESQUEMA_INVALIDO", "efectos es un mapa ID → lista de transiciones")
    salida = {}
    for ident, lista in efectos.items():
        r = prop_snap.registros.get(ident)
        if r is None:
            raise _Bloqueo("REFERENCIA_AUSENTE", f"efecto sobre {ident}, que no está en la propuesta")
        try:
            comprobar_efectos(lista)
        except ValueError as exc:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: {exc}") from exc
        estado, completos = r["estado"], []
        for ef in lista:
            previo = ef.get("estado_anterior", estado)
            if previo != estado or (previo, ef["estado_nuevo"]) not in TRANSICIONES[r["type"]]:
                raise _Bloqueo(
                    "ESQUEMA_INVALIDO", f"{ident}: transición {previo}→{ef['estado_nuevo']} no admitida desde {estado}"
                )
            completos.append({**ef, "estado_anterior": previo})
            estado = ef["estado_nuevo"]
        salida[ident] = completos
    return salida


CAMPOS_IMPORTACION = frozenset({"estado", "valido_desde", "precision", "autoridad_heredada"})


def _aprobable(importacion):
    """Lo que aprueba la persona de una importación: lo que declara la solicitud, sin lo que añade el integrador."""
    return None if importacion is None else {k: importacion[k] for k in sorted(CAMPOS_IMPORTACION)}


def lo_aprobable(ident, efectos, importaciones):
    """(efectos, importación) que cubre el digest de un registro: lo mismo al mostrarlo que al recalcularlo."""
    return efectos.get(ident, []), _aprobable(importaciones.get(ident))


def _comprobar_importaciones(git, base, base_snap, prop_snap, importaciones, efectos, mut):
    """Cada importación corresponde al heredado de la base: misma identidad, mismo cuerpo y su estado mapeado."""
    if not isinstance(importaciones, dict):
        raise _Bloqueo("ESQUEMA_INVALIDO", "importaciones es un mapa ID → importación")
    salida = {}
    for ident, imp in importaciones.items():
        if not isinstance(imp, dict) or set(imp) != CAMPOS_IMPORTACION:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: la importación lleva {sorted(CAMPOS_IMPORTACION)}")
        if ident in efectos:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: una importación no lleva efectos en la misma operación")
        ficha = base_snap.heredados.get(ident)
        if ficha is None or ident not in mut["nuevos"] or ident not in prop_snap.registros:
            raise _Bloqueo("REFERENCIA_AUSENTE", f"{ident} no es un registro heredado de la base que se importe aquí")
        ruta, r = prop_snap.rutas[ident], prop_snap.registros[ident]
        if ficha["ruta"] != ruta or ficha["tipo"] != r.get("type"):
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: se importa en la ruta y con el tipo de su heredado")
        if imp["estado"] != ficha["estado_propuesto"]:
            raise _Bloqueo(
                "ESQUEMA_INVALIDO",
                f"{ident}: el estado importado ({imp['estado']}) no es el de su heredado ({ficha['estado_propuesto']})",
            )
        if imp["autoridad_heredada"] != ficha["autoridad_heredada"]:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: la autoridad heredada no es la del registro heredado")
        if imp["precision"] not in (*PRECISIONES, "desconocida"):
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: precisión desconocida {imp['precision']!r}")
        valido = imp["valido_desde"]
        if valido is not None and not (es_fecha(valido) or es_instante(valido)):
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: valido_desde es una fecha, un instante con zona o null")
        heredado = git("show", f"{base}:{ruta}") + "\n"
        motivos = comprobar_importacion(r, prop_snap.cuerpos[ident], heredado, ruta)
        if motivos:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: {motivos[0]}", motivos=motivos)
        motivos_decisiva = _decisiva_por_heredado(ident, ficha, heredado, base_snap.heredados)
        if redistribuye(prop_snap.cuerpos[ident], heredado):
            motivos_decisiva.append("la partición redistribuye las líneas del heredado")
        salida[ident] = {
            **imp,
            "estado_heredado": ficha["estado_heredado"],
            "decisiva": motivos_decisiva,
        }
    return salida


def _decisiva_por_heredado(ident, ficha, texto_heredado, heredados):
    """Por qué la importación decide algo aunque la propuesta no lo declare: el heredado fija una sucesión o un cierre.

    Que una importación sea decisiva no puede depender de relaciones que quien propone puede omitir.
    """
    motivos = []
    if any((ficha.get("relaciones_propuestas") or {}).get(k) for k in RELACIONES_DECISIVAS):
        motivos.append("el heredado cierra o sustituye otro registro")
    if any(a.get("campo") in RELACIONES_DECISIVAS for a in ficha.get("ambiguedades") or []):
        motivos.append("el heredado declara una sustitución o un cierre")
    try:
        meta, _ = parse_heredado(texto_heredado)
    except ErrorDeFormato:
        meta = {}
    if _IDS_HEREDADOS.search(str(meta.get("sustituye_a") or "")):
        motivos.append("el heredado declara a quién sustituye")
    for otro, f in heredados.items():
        if otro == ident:
            continue
        for a in f.get("ambiguedades") or []:
            if a.get("campo") in RELACIONES_DECISIVAS and ident in (a.get("candidatos") or []):
                motivos.append(f"{otro} declara que {ident} lo sustituye")
    return motivos


class _VerificacionUnica:
    """Cada revisión se verifica una sola vez por integración: el mismo resultado para todos los registros."""

    def __init__(self, verificador):
        self._verificador = verificador
        self._hechas = {}

    def verificar(self, revision, propuesta_rev, base_rev):
        clave = clave_de_revision(revision)
        if clave not in self._hechas:
            try:
                self._hechas[clave] = (self._verificador.verificar(revision, propuesta_rev, base_rev), None)
            except ErrorDeVerificacion as exc:
                self._hechas[clave] = (None, exc)
        resultado, error = self._hechas[clave]
        if error is not None:
            raise error
        return resultado


def _autoridad(
    tocados,
    efectos,
    cambios_de_politica,
    revisiones,
    base_snap,
    prop_snap,
    verificador,
    prop,
    base,
    ahora,
    importaciones,
    modo,
):
    """{ID: [aprobaciones construidas con datos verificados]}; bloquea si algún registro tocado no está autorizado.

    En el modo `decisiva`, lo que no es decisivo no se evalúa y queda con una lista vacía.
    """
    if not isinstance(revisiones, list):
        raise _Bloqueo("ESQUEMA_INVALIDO", "revisiones es una lista")
    aprobaciones = {}
    unico = _VerificacionUnica(verificador)
    # Una aprobación ya admitida en la base no vuelve a valer: una aprobación declarada no lleva su propia
    # operación, así que esto impide reutilizarla si un registro vuelve a un contenido ya aprobado.
    usadas = {
        e["aprobacion"]["aprobacion_id"]
        for r in base_snap.registros.values()
        for e in r.get("eventos") or []
        if e.get("tipo_evento") == "ratificacion" and isinstance(e.get("aprobacion"), dict)
    }
    for ident in tocados:
        r, c = prop_snap.registros[ident], prop_snap.cuerpos[ident]
        if modo == "decisiva" and not es_decisivo(ident, r, efectos, cambios_de_politica, importaciones):
            aprobaciones[ident] = []
            continue
        efectos_aprobables, importacion_aprobable = lo_aprobable(ident, efectos, importaciones)
        res = evaluar(
            r,
            c,
            efectos_aprobables,
            revisiones,
            base_snap,
            unico,
            prop,
            base,
            revalidar_en=ahora,
            cambio_de_politica=ident in cambios_de_politica,
            importacion=importacion_aprobable,
        )
        if not res["autorizado"]:
            raise _Bloqueo(res["codigo"], f"{ident}: integración no autorizada", autoridad=res)
        repetidas = sorted({a["aprobacion_id"] for a in res["aprobaciones"]} & usadas)
        if repetidas:
            raise _Bloqueo(
                "APROBACION_CADUCADA", f"{ident}: la aprobación {repetidas[0]} ya se usó en otra integración"
            )
        aprobaciones[ident] = res["aprobaciones"]
    return aprobaciones


def es_decisivo(ident, registro, efectos, cambios_de_politica, importaciones):
    """Si tocar este registro en esta operación decide algo (modo `decisiva`)."""
    return bool(motivos_decisivos(ident, registro, efectos, cambios_de_politica, importaciones))


def motivos_decisivos(ident, registro, efectos, cambios_de_politica, importaciones):
    """Por qué tocar este registro en esta operación decide algo; vacía si no decide nada."""
    tipo, motivos = registro.get("type"), []
    if ident in cambios_de_politica:
        motivos.append("cambia la política: roles, personas o acceso")
    if tipo in POLITICA_DECISIVA:
        motivos.append(f"un registro de tipo {tipo} cambia quién decide")
    decisivas = DECISIVAS.get(tipo, set())
    motivos += [
        f"transición a {ef['estado_nuevo']}" for ef in efectos.get(ident, []) if ef["estado_nuevo"] in decisivas
    ]
    if ident in importaciones:
        imp = importaciones[ident] or {}
        relaciones = [k for k in RELACIONES_DECISIVAS if registro.get(k)]
        if relaciones:
            motivos.append(f"la importación declara {', '.join(relaciones)}")
        motivos += list(imp.get("decisiva") or [])
    return motivos


def _detalle(aprobaciones):
    """Cada aprobación una vez, con su comprobante: con el canal declarado, la cita solo consta aquí y en el evento."""
    vistas = {}
    for lista in aprobaciones.values():
        for a in lista:
            vistas.setdefault(a["aprobacion_id"], {k: v for k, v in a.items() if k != "digest"})
    return [vistas[k] for k in sorted(vistas)]


def _evento(op, n, ahora, tipo, actor=ACTOR, **campos):
    return {
        "evento_id": f"{op}-{n}",
        "tipo_evento": tipo,
        "actor": actor,
        "registrado_en": ahora,
        "valido_desde": campos.pop("valido_desde", ahora),
        "motivo": f"integración {op}",
        "evidencia_evento": campos.pop("evidencia_evento", {"mecanismo": "integrador-local", "comprobante": op}),
        **campos,
    }


def _materializar(
    op,
    ahora,
    tocados,
    efectos,
    aprobaciones,
    mut,
    prop_snap,
    importaciones,
    base,
    modo="toda",
    actor=ACTOR,
    aprobacion_pendiente=False,
):
    """Registros finales con los eventos que admite la integración.

    La ratificación se registra donde hay efectos o cambio de política; en las demás, la autorización de la
    integración queda en el trailer `Revisiones` del commit. En el modo `decisiva`, también donde la importación es
    decisiva. Cada evento lleva el actor de la operación; la ratificación, además, el de quien aprueba.

    Con `aprobacion_pendiente` (el paquete de aprobación), las aprobaciones aún no existen: no se exige la ratificación
    previa a una aceptación, que es lo único del registro final que depende de ellas.
    """
    finales, n = {}, 0
    ratificar = set(efectos) | set(mut["cambios_de_politica"])
    if modo == "decisiva":
        ratificar = {i for i in tocados if aprobaciones.get(i)}
    for ident in tocados:
        r = copy.deepcopy(prop_snap.registros[ident])
        ultimo = max(
            (instante(e["registrado_en"]) for e in r.get("eventos") or [] if e.get("registrado_en")), default=None
        )
        if ultimo is not None and instante(ahora) < ultimo:
            raise _Bloqueo("RESULTADO_DESCONOCIDO", "el reloj del integrador va por detrás del último evento admitido")
        eventos = list(r.get("eventos") or [])
        if ident in importaciones:
            n += 1
            imp = importaciones[ident]
            eventos.append(
                _evento(
                    op,
                    n,
                    ahora,
                    "importacion",
                    actor,
                    valido_desde=imp["valido_desde"],
                    estado_anterior=None,
                    estado_nuevo=imp["estado"],
                    estado_heredado=imp["estado_heredado"],
                    procedencia={"ruta": prop_snap.rutas[ident], "revision": base},
                    precision=imp["precision"],
                    autoridad_heredada=imp["autoridad_heredada"],
                )
            )
            r["estado"] = imp["estado"]
        elif ident in mut["nuevos"]:
            n += 1
            eventos.append(
                _evento(op, n, ahora, "creacion", actor, estado_anterior=None, estado_nuevo=INICIAL[r["type"]])
            )
        if ident in ratificar:
            for ap in aprobaciones[ident]:
                n += 1
                c = ap["comprobante"]
                texto = c.get("resumen") or f"{c['repositorio']}#{c['pull']}/reviews/{c['review_id']}"
                evidencia = {"mecanismo": c["mecanismo"], "comprobante": texto}
                eventos.append(_evento(op, n, ahora, "ratificacion", actor, aprobacion=ap, evidencia_evento=evidencia))
        for ef in efectos.get(ident, []):
            n += 1
            extra = {"valido_hasta": ef["valido_hasta"]} if "valido_hasta" in ef else {}
            eventos.append(
                _evento(
                    op,
                    n,
                    ahora,
                    "transicion",
                    actor,
                    estado_anterior=ef["estado_anterior"],
                    estado_nuevo=ef["estado_nuevo"],
                    valido_desde=ef["valido_desde"],
                    **extra,
                )
            )
            r["estado"] = ef["estado_nuevo"]
        r["eventos"] = eventos
        r.pop("status", None)  # proyección: la calculan las vistas, no se escribe
        errores = [
            h
            for h in validar(r, prop_snap.cuerpos[ident], modo="canonico")
            if h["severidad"] == "error" and not (aprobacion_pendiente and h["codigo"] == "AUTORIDAD_INSUFICIENTE")
        ]
        if errores:
            raise _Bloqueo("ESQUEMA_INVALIDO", f"{ident}: el registro final no es canónico", hallazgos=errores)
        finales[ident] = (r, prop_snap.cuerpos[ident])
    return finales


def _comprobar_final(base_snap, prop_snap, finales):
    regs = {**base_snap.registros, **{i: r for i, (r, _) in finales.items()}}
    cuerpos = {**base_snap.cuerpos, **{i: c for i, (_, c) in finales.items()}}
    heredados = {i: f for i, f in base_snap.heredados.items() if i not in finales}
    final = Snapshot(regs, "final", cuerpos, {**base_snap.rutas, **prop_snap.rutas}, heredados)
    errores = [h for h in validar_snapshot(final) if h["severidad"] == "error"]
    if errores:
        raise _Bloqueo(errores[0]["codigo"], "el árbol final no es coherente", hallazgos=errores)
    advertencias = []
    for t in sorted(set(_inicios(regs)), key=instante):
        try:
            en_final = _conflictos(final, t)
            en_base = _conflictos(base_snap, t)
        except ErrorDeHistorial as exc:
            raise _Bloqueo(exc.codigo, str(exc)) from exc
        nuevos = [c for c in en_final if c not in en_base]
        if nuevos:
            raise _Bloqueo("CONFLICTO_NORMATIVO", f"conflicto normativo en {t}", conflictos=nuevos)
        for c in en_final:
            aviso = f"conflicto previo, no introducido por esta operación: {c['clausula']} entre {', '.join(c['candidatas'])}"
            if aviso not in advertencias:
                advertencias.append(aviso)
    return final, advertencias


_TERMINO = {
    vocabulario_mod.NO_DECLARADO: "término no declarado",
    vocabulario_mod.INDETERMINADO: "término indeterminado",
    vocabulario_mod.RETIRADO: "término retirado, que ya no rige",
}


def _comprobar_vocabulario(base_snap, final, efectos, tocados, ahora):
    """Vocabulario del dominio en el árbol final: sus hallazgos, o `Bloqueo`.

    Rige el vocabulario del árbol final, así que la decisión que define un término puede entrar con su primer uso. Un
    efecto que lleva una entidad a `activa` bloquea (`ESQUEMA_INVALIDO`) si, con el mundo cerrado al integrar o en el
    inicio de validez de ese efecto, su clase no rige en los dos cortes: no declarada, indeterminada o retirada. También
    bloquea que una entidad ya activa cambie su clase a una que no rige al integrar. Lo demás
    entra con sus hallazgos, al instante de la integración: [{id, campo, valor, situacion, tocado}] de la clase y el
    ámbito de cada registro tocado y, si la operación hace que deje de regir un término en uso, de cada entidad que lo
    usa (`tocado` falso).
    """
    por_corte = {}

    def en(corte):
        if corte not in por_corte:
            por_corte[corte] = vocabulario_mod.vigente(final, valido_en=corte, conocido_hasta=ahora)
        return por_corte[corte]

    bloqueos = []
    for ident in tocados:
        r = final.registros[ident]
        if r.get("type") != "entidad":
            continue
        valor = r.get("clase_entidad")
        for ef in efectos.get(ident, []):
            if ef["estado_nuevo"] != "activa":
                continue
            # El inicio de validez lo elige quien propone: fechar el efecto antes de la primera definición no abre el
            # mundo. Si está cerrado al integrar o en ese inicio, la clase tiene que regir en los dos cortes.
            cortes = (ef["valido_desde"], ahora)
            if not any(en(c)["declarado"] for c in cortes):
                continue
            for corte in cortes:
                situacion, _ = vocabulario_mod.situacion(en(corte), valor)
                if situacion == vocabulario_mod.ABIERTO:
                    situacion = vocabulario_mod.NO_DECLARADO
                if situacion in _TERMINO:
                    bloqueos.append({"id": ident, "valor": valor, "situacion": situacion, "valido_en": corte})
                    break
        # Una entidad que ya está activa y cambia de clase no pasa por ningún efecto: sin esta comprobación, activar
        # con una clase declarada y cambiarla después sería activar en dos pasos con una que no rige.
        anterior = base_snap.registros.get(ident)
        if anterior is None or anterior.get("estado") != "activa" or r.get("estado") != "activa":
            continue
        if anterior.get("clase_entidad") == valor or not en(ahora)["declarado"]:
            continue
        situacion, _ = vocabulario_mod.situacion(en(ahora), valor)
        if situacion in _TERMINO:
            bloqueos.append({"id": ident, "valor": valor, "situacion": situacion, "valido_en": ahora})
    if bloqueos:
        b = bloqueos[0]
        motivo = f"{b['id']}: {_TERMINO[b['situacion']]} en clase_entidad: {b['valor']!r} no rige en {b['valido_en']}"
        dudosos = sorted({t["termino"] for v in por_corte.values() for t in v["indeterminados"]})
        if dudosos:
            motivo += f"; el vocabulario tiene definiciones indeterminadas: {', '.join(dudosos)}"
        raise _Bloqueo("ESQUEMA_INVALIDO", motivo, terminos=bloqueos)
    antes = vocabulario_mod.vigente(base_snap, valido_en=ahora, conocido_hasta=ahora)
    despues = en(ahora)
    registros, _ = vocabulario_mod.constan(final, conocido_hasta=ahora)
    validos, hallazgos = set(despues["ambitos"]), []
    for ident, r in registros:
        tocado = ident in tocados
        ambito = r.get("ambito")
        if tocado and isinstance(ambito, str) and ambito not in validos:
            hallazgos.append({"id": ident, "campo": "ambito", "valor": ambito, "situacion": "sin_rol", "tocado": True})
        if r.get("type") != "entidad":
            continue
        valor = r.get("clase_entidad")
        situacion, _ = vocabulario_mod.situacion(despues, valor)
        afectado = vocabulario_mod.situacion(antes, valor)[0] == vocabulario_mod.VIGENTE
        if situacion in _TERMINO and (tocado or afectado):
            hallazgos.append(
                {"id": ident, "campo": "clase_entidad", "valor": valor, "situacion": situacion, "tocado": tocado}
            )
    return hallazgos


def aviso_de_vocabulario(hallazgo):
    """Una línea para el recibo o el paquete con un hallazgo de `_comprobar_vocabulario`."""
    h = hallazgo
    if h["campo"] == "ambito":
        return f"{h['id']}: ámbito {h['valor']!r} sin ningún rol activo que lo cubra"
    uso = "" if h["tocado"] else "; uso afectado por esta operación"
    return f"{h['id']}: {_TERMINO[h['situacion']]} en clase_entidad: {h['valor']!r}{uso}"


def _inicios(regs):
    """Instantes en que entra en vigor la aceptación de cada decisión del árbol, nueva o existente.

    El conjunto de decisiones vigentes solo crece en esos instantes, así que un solapamiento aparece en alguno de
    ellos. Una fecha sin hora se comprueba fuera de su ventana de ambigüedad.
    """
    for r in regs.values():
        if r.get("type") != "decision":
            continue
        for e in r.get("eventos") or []:
            if (
                e.get("registrado_en")
                and e.get("tipo_evento") in ("transicion", "importacion")
                and e.get("estado_nuevo") == "aceptada"
            ):
                desde = e.get("valido_desde")
                if es_instante(desde):
                    yield desde
                elif es_fecha(desde):
                    yield f"{desde}T14:00:00Z"


def _conflictos(snapshot, t):
    decisiones = sorted(i for i, r in snapshot.registros.items() if r.get("type") == "decision")
    return consolidar(snapshot, decisiones, valido_en=t, conocido_hasta=None)["conflictos"]


def _escribir_huellas(git, base, carpeta, escritos, env):
    """Las huellas avisan, no bloquean: si las de la base no se leen, se rehacen con las de esta operación."""
    try:
        previas = huellas_mod.leer_de_revision(git, base, carpeta)
    except ValueError:
        previas = {}
    if not isinstance(previas, dict):
        previas = {}
    contenido = huellas_mod.serializar_huellas(huellas_mod.actualizadas(previas, escritos))
    blob = git("hash-object", "-w", "--stdin", entrada=contenido, extra_env=env)
    git("update-index", "--add", "--cacheinfo", f"100644,{blob},{huellas_mod.ruta_de(carpeta)}", extra_env=env)


def _escribir_commit(git, ref, actual, prop, op, huella, finales, prop_snap, aprobaciones, modo, actor, carpeta):
    """Commit aplanado sobre la base (sin importar la historia de la propuesta); None si el CAS falla.

    Actualiza en el mismo commit las huellas de los registros escritos (`kbol.huellas`).
    """
    with tempfile.TemporaryDirectory(prefix="kb-indice-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), **_IDENTIDAD}
        git("read-tree", prop, extra_env=env)
        escritos = {}
        for ident, (r, c) in sorted(finales.items()):
            texto = serializar(r, c, modo="canonico")
            blob = git("hash-object", "-w", "--stdin", entrada=texto.encode("utf-8"), extra_env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{prop_snap.rutas[ident]}", extra_env=env)
            escritos[ident] = (prop_snap.rutas[ident], texto)
        _escribir_huellas(git, actual, carpeta, escritos, env)
        arbol = git("write-tree", extra_env=env)
        revisadas = ",".join(sorted({a["aprobacion_id"] for lista in aprobaciones.values() for a in lista}))
        mensaje = (
            f"kb: integra {op}\n\n{TRAILER}: {op}\nSolicitud-Sha256: {huella}\nBase: {actual}\nPropuesta: {prop}\n"
            f"Revisiones: {revisadas}\n"
        )
        if modo != "toda" or actor != ACTOR:
            mensaje += f"Aprobacion: {modo}\nActor: {actor}\n"
        nuevo = git("commit-tree", arbol, "-p", actual, entrada=mensaje.encode("utf-8"), extra_env=env)
    if git("update-ref", ref, nuevo, actual, comprobar=False) != 0:
        return None
    return nuevo
