"""Proponer desde el clon del integrador (`kbol proponer`): de unos archivos del árbol de trabajo a la rama canónica.

El integrador no escribe en una rama con checkout, así que cada instalación opera sobre un clon `--bare` de su remoto
(el clon del integrador), en su estado local: `$KBOL_ESTADO/<repositorio>/integrador.git`, con los recibos al lado. Esta
orden hace el camino entero: trae la rama canónica, escribe la propuesta como un commit sobre ella con plumbing de git
(los archivos indicados y, si hay efectos o importaciones, su solicitud), la pasa por la puerta (`integrar.integrar`,
sin cambiarla), ejecuta los pasos posteriores que declara la instalación y, si se le pide, sube.

Hasta dónde llega lo decide `hasta`. `ensayo` (por defecto) integra en una rama temporal del clon, con recibos
aparte, y la borra: la rama canónica no cambia. `integrar` escribe la rama canónica del clon y no sube. `subir`,
además, hace `git push` sin forzar.

La aprobación no se arma aquí: la orden recibe las aprobaciones declaradas ya
dadas, con los digests que se mostraron a la persona, y la puerta comprueba que son los de lo que se integra. Si la
puerta pide una aprobación que no se le dio, el ensayo devuelve el paquete de aprobación (`kbol.paquete`), con los
digests y el esqueleto, y termina `pendiente_de_aprobacion`. No hay cita, sesión ni identidad por defecto.

Lo propio de la instalación va en su configuración, bloque `integracion`: `remoto`, `repositorio` (el nombre de su
estado local), `aprobacion` (`toda` o `decisiva`), `despues_de_integrar` (ids de `verificaciones` que corren sobre lo
integrado antes de subir), `vistas` (globs de lo que esos pasos pueden regenerar, que va en un commit propio) y
`autor` (de los commits de propuesta y de vistas). La rama y las carpetas son `rama_canonica` y `carpeta_registros`.

Los pasos posteriores corren en un checkout temporal de lo integrado, sin shell, con el ejecutor de `verificar` y sin
aislamiento. Solo pueden cambiar vistas declaradas; dentro de una carpeta de registros, solo `index.md`, que es lo que
la carga de registros omite. Si un paso falla o cambia otra cosa, no se sube. Fuera del ensayo, lo ya integrado queda
entonces en el clon sin subir: se ensaya antes.
"""

import json
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .arranque import _IDENTIDAD_ARRANQUE
from .declarada import MECANISMO, VerificadorDeclarado
from .integrar import _IDENTIDAD as _IDENTIDAD_INTEGRADOR
from .integrar import _RAMA, ACTOR, MODOS, Bloqueo, _carpeta_segura, _comprobar_operacion, _Git, integrar
from .paquete import preparar_aprobacion
from .relevo import _RESERVADOS
from .snapshot import carpetas_de, entorno_git
from .verificar import _cola, _lanzar, python_de, verificaciones_de

HASTA = ("ensayo", "integrar", "subir")
CAMPOS = frozenset({"remoto", "repositorio", "aprobacion", "despues_de_integrar", "vistas", "autor"})
AUTOR = {"nombre": "proponente-local", "correo": "proponente@localhost"}
# El integrador y el arranque reconocen sus commits por el correo: nadie más los firma con él.
_CORREOS_RESERVADOS = {_IDENTIDAD_INTEGRADOR["GIT_COMMITTER_EMAIL"], _IDENTIDAD_ARRANQUE["GIT_COMMITTER_EMAIL"]}
_NOMBRE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_SIN_REF = "0" * 40
# Git recorta signos en los extremos del correo: se exige uno que empiece y acabe en letra o cifra.
_CORREO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*")
RED = 300  # segundos de una orden de git que habla con el remoto


@dataclass(frozen=True)
class Integracion:
    """Lo que la instalación declara para proponer (`integracion_de`)."""

    remoto: str
    repositorio: str
    rama: str
    carpetas: tuple
    modo: str
    despues: tuple  # ((id, verificación declarada), …)
    vistas: tuple
    autor: dict


def _linea(valor):
    return isinstance(valor, str) and valor.strip() != "" and "\n" not in valor and "\r" not in valor


def integracion_de(instalacion):
    """La configuración de `proponer` que declara la instalación, validada; ValueError si falta o no es válida."""
    datos = instalacion.get("integracion") if isinstance(instalacion, dict) else None
    if not isinstance(datos, dict):
        raise ValueError("la instalación no declara integracion: {remoto, repositorio, …}")
    sobrantes = sorted(set(datos) - CAMPOS)
    if sobrantes:
        raise ValueError(f"integracion no admite: {', '.join(sobrantes)}")
    remoto, repositorio = datos.get("remoto"), datos.get("repositorio")
    if not _linea(remoto) or remoto.startswith("-"):
        raise ValueError("integracion.remoto es la URL o la ruta del remoto canónico")
    if not isinstance(repositorio, str) or not _NOMBRE.fullmatch(repositorio):
        raise ValueError("integracion.repositorio es el nombre del estado local: letras, cifras, punto, guion y subrayado")
    rama = instalacion.get("rama_canonica")
    if not isinstance(rama, str) or not _RAMA.fullmatch(rama) or ".." in rama or rama.endswith((".lock", "/")):
        raise ValueError("rama_canonica es el nombre de la rama canónica")
    carpetas = instalacion.get("carpeta_registros")
    if not isinstance(carpetas, str) or not all(c.strip() for c in carpetas.split(",")):
        raise ValueError("carpeta_registros es la carpeta de registros; varias, separadas por comas")
    try:  # la misma normalización que la puerta: es_vista y la solicitud ven las carpetas como ella
        carpetas = carpetas_de(_carpeta_segura([c.strip() for c in carpetas.split(",")]))
    except Bloqueo as b:
        raise ValueError(f"carpeta_registros: {b.resultado['motivo']}") from None
    modo = datos.get("aprobacion", "toda")
    if modo not in MODOS:
        raise ValueError(f"integracion.aprobacion es uno de {', '.join(MODOS)}")
    declaradas = verificaciones_de(instalacion)
    despues = datos.get("despues_de_integrar", [])
    if (
        not isinstance(despues, list)
        or any(not isinstance(i, str) or i not in declaradas for i in despues)
        or len(set(despues)) != len(despues)
    ):
        raise ValueError("integracion.despues_de_integrar lista, sin repetir, ids de verificaciones declaradas")
    vistas = datos.get("vistas", [])
    if not isinstance(vistas, list) or any(
        not _linea(v) or v.startswith("/") or "\\" in v or ".." in v.split("/") for v in vistas
    ):
        raise ValueError("integracion.vistas es una lista de globs relativos a la raíz, con /")
    autor = datos.get("autor", AUTOR)
    if (
        not isinstance(autor, dict)
        or set(autor) != {"nombre", "correo"}
        or not _linea(autor["nombre"])
        or set("<>") & set(autor["nombre"])
        or not isinstance(autor["correo"], str)
        or not _CORREO.fullmatch(autor["correo"])
        or autor["correo"].casefold() in _CORREOS_RESERVADOS
    ):
        raise ValueError("integracion.autor lleva nombre y correo, y el correo no es el del integrador ni el del arranque")
    return Integracion(
        remoto=remoto,
        repositorio=repositorio,
        rama=rama,
        carpetas=carpetas,
        modo=modo,
        despues=tuple((i, declaradas[i]) for i in despues),
        vistas=tuple(vistas),
        autor=dict(autor),
    )


def estado_local(repositorio):
    """Carpeta del estado local de una instalación: `$KBOL_ESTADO/<repositorio>`, por defecto `~/.kbol/<repositorio>`."""
    return Path(os.environ.get("KBOL_ESTADO") or Path.home() / ".kbol") / repositorio


def _ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _red():
    """Lo que añade al entorno mínimo una orden de git que habla con el remoto: nunca pregunta (ni git ni ssh) y ve
    el agente SSH."""
    agente = {k: os.environ[k] for k in ("SSH_AUTH_SOCK", "SSH_AGENT_PID") if k in os.environ}
    ssh = os.environ.get("GIT_SSH_COMMAND") or "ssh"
    return {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": f"{ssh} -o BatchMode=yes", **agente}


def _git_suelto(*args, extra_env=None, timeout=None):
    """(código, error) de una orden de git sin entrada cuyo fallo decide quien llama: clonar, traer y subir."""
    try:
        p = subprocess.run(
            ["git", *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env={**entorno_git(), **(extra_env or {})},
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"git no terminó en {timeout} s"
    return p.returncode, p.stderr.decode("utf-8", "replace").strip()


def _mismo_remoto(configurado, guardado):
    """Si el `origin` del clon es el remoto de la instalación: la misma URL o, en local, la misma carpeta."""
    if configurado == guardado:
        return True
    try:
        return guardado is not None and os.path.samefile(configurado, guardado)
    except OSError:
        return False


def abrir_clon(cfg):
    """El clon del integrador de la instalación, que se crea si no existe. Nunca usa el clon de otro remoto."""
    ruta = estado_local(cfg.repositorio) / "integrador.git"
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        clonar = ("clone", "-q", "--bare", "--no-tags", "--", cfg.remoto, str(ruta))
        codigo, error = _git_suelto(*clonar, extra_env=_red(), timeout=RED)
        if codigo != 0:
            raise Bloqueo("RESULTADO_DESCONOCIDO", f"no se pudo clonar {cfg.remoto}: {error}")
    git = _Git(ruta)
    try:
        origen = git("config", "--get", "remote.origin.url")
    except Bloqueo:
        origen = None
    if not _mismo_remoto(cfg.remoto, origen):
        raise Bloqueo(None, f"{ruta} no es un clon de {cfg.remoto}: no se usa")
    return git


def traer(git, rama):
    """Trae la rama canónica del remoto y deja la del clon al día: {cabeza, remoto, pendientes_de_subir}.

    Nunca descarta lo integrado en el clon y aún sin subir: si el clon va por delante, se propone sobre su cabeza; si
    el clon y el remoto han divergido, bloquea (`BASE_CAMBIADA`).
    """
    ref, remota = f"refs/heads/{rama}", f"refs/remotes/origin/{rama}"
    traida = ("-C", git.repo, "fetch", "-q", "--no-tags", "origin", f"+{ref}:{remota}")
    codigo, error = _git_suelto(*traida, extra_env=_red(), timeout=RED)
    if codigo != 0:
        raise Bloqueo("RESULTADO_DESCONOCIDO", f"no se pudo traer {rama} del remoto: {error}")
    remoto = git("rev-parse", "--verify", "--end-of-options", f"{remota}^{{commit}}")
    if git("show-ref", "--verify", "-q", ref, comprobar=False) != 0:
        git("update-ref", ref, remoto, _SIN_REF)
    local = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    pendientes = 0
    if local != remoto:
        if git("merge-base", "--is-ancestor", local, remoto, comprobar=False) == 0:
            git("update-ref", ref, remoto, local)
            local = remoto
        elif git("merge-base", "--is-ancestor", remoto, local, comprobar=False) == 0:
            pendientes = int(git("rev-list", "--count", f"{remoto}..{local}"))
        else:
            sin_subir = git("rev-list", "--count", f"{remoto}..{local}")
            # No se descarta solo: lo decide una persona, con la orden exacta y sabiendo que los recibos quedan.
            raise Bloqueo(
                "BASE_CAMBIADA",
                f"el clon del integrador y el remoto han divergido en {rama}: {sin_subir} commit(s) integrados y sin "
                f"subir ({local[:12]}) no descienden del remoto ({remoto[:12]}). Para rehacerlos sobre el remoto, "
                f"descártalos con `git -C {git.repo} update-ref {ref} {remoto} {local}` (sus recibos se conservan) y "
                "vuelve a proponer con un operacion_id nuevo",
                integrado_sin_subir=local,
                remoto=remoto,
            )
    return {"cabeza": local, "remoto": remoto, "pendientes_de_subir": pendientes}


def escribir_commit(git, base, archivos, autor, mensaje, borrar=()):
    """Commit sobre `base` que escribe `archivos` (ruta → bytes) y quita `borrar`, sin tocar ningún árbol de trabajo."""
    with tempfile.TemporaryDirectory(prefix="kb-propuesta-") as tmp:
        env = {
            "GIT_INDEX_FILE": str(Path(tmp) / "index"),
            "GIT_AUTHOR_NAME": autor["nombre"],
            "GIT_AUTHOR_EMAIL": autor["correo"],
            "GIT_COMMITTER_NAME": autor["nombre"],
            "GIT_COMMITTER_EMAIL": autor["correo"],
        }
        git("read-tree", base, extra_env=env)
        if borrar:  # en un clon --bare no hay árbol de trabajo: se quitan del índice con modo 0
            quitar = "".join(f"0 {_SIN_REF}\t{ruta}\n" for ruta in sorted(borrar))
            git("update-index", "--index-info", entrada=quitar.encode("utf-8"), extra_env=env)
        for ruta, contenido in sorted(archivos.items()):
            blob = git("hash-object", "-w", "--stdin", entrada=contenido, extra_env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{ruta}", extra_env=env)
        arbol = git("write-tree", extra_env=env)
        return git("commit-tree", arbol, "-p", base, entrada=mensaje.encode("utf-8"), extra_env=env)


def leer_archivos(raiz, rutas):
    """{ruta relativa a la raíz: bytes} de los archivos del árbol de trabajo que se proponen, con saltos en LF.

    ValueError si la raíz no es la de su repositorio, o una ruta se repite o queda fuera de ella.
    """
    raiz = Path(raiz).resolve()
    p = subprocess.run(["git", "-C", str(raiz), "rev-parse", "--show-toplevel"], capture_output=True, env=entorno_git())
    cima = p.stdout.decode("utf-8", "replace").strip()
    if p.returncode != 0 or not cima or not os.path.samefile(cima, raiz):
        raise ValueError(f"la raíz tiene que ser la de su repositorio de git: {raiz}")
    salida = {}
    for ruta in rutas:
        archivo = (raiz / ruta).resolve()
        try:
            relativa = archivo.relative_to(raiz).as_posix()
        except ValueError:
            raise ValueError(f"el archivo tiene que estar dentro de la raíz: {ruta}") from None
        if relativa in salida or not _linea(relativa) or "\t" in relativa:
            raise ValueError(f"ruta repetida o no admitida: {ruta}")
        salida[relativa] = archivo.read_text(encoding="utf-8").encode("utf-8")
    if not salida:
        raise ValueError("proponer necesita al menos un archivo")
    return salida


def _patron(glob):
    """Expresión regular de un glob de rutas con `/`: `**/` cruza carpetas, `*` y `?` no."""
    partes, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            partes.append("(?:[^/]+/)*")
            i += 3
        elif glob.startswith("**", i):
            partes.append(".*")
            i += 2
        elif glob[i] == "*":
            partes.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            partes.append("[^/]")
            i += 1
        else:
            partes.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(partes))


def es_vista(ruta, cfg):
    """Si un paso posterior puede cambiar `ruta`: una vista declarada y, dentro de una carpeta de registros, solo
    `index.md`, que es lo que la carga de registros omite. Así una vista nunca es un registro, sus huellas ni una
    solicitud."""
    if not any(_patron(g).fullmatch(ruta) for g in cfg.vistas):
        return False
    en_registros = any(ruta.startswith(c.rstrip("/") + "/") for c in cfg.carpetas)
    return not en_registros or ruta.rsplit("/", 1)[-1] == "index.md"


def _despues(git, cfg, rama, op, raiz):
    """Ejecuta los pasos posteriores sobre lo integrado en `rama` y escribe las vistas que cambian en un commit propio.

    Devuelve {pasos, vistas, cabeza, motivo}; `motivo` dice por qué no se puede subir, o None.
    """
    ref = f"refs/heads/{rama}"
    cabeza = git("rev-parse", "--verify", "--end-of-options", ref)
    salida = {"pasos": [], "vistas": [], "cabeza": cabeza, "motivo": None}
    if not cfg.despues:
        return salida
    python, _ = python_de(raiz)
    with tempfile.TemporaryDirectory(prefix="kb-despues-", ignore_cleanup_errors=True) as tmp:
        arbol = Path(tmp) / "arbol"
        # Sin conversión de saltos de línea: lo que se lee del checkout es lo que hay en la rama.
        clonar = ["clone", "-q", "--no-tags", "--single-branch", "--branch", rama, "-c", "core.autocrlf=false"]
        codigo, error = _git_suelto(*clonar, "--", git.repo, str(arbol))
        if codigo != 0:
            raise Bloqueo("RESULTADO_DESCONOCIDO", f"no se pudo preparar el checkout de {rama}: {error}")
        en_arbol = _Git(arbol)
        for ident, spec in cfg.despues:
            evidencia = Path(tmp) / f"{ident}.log"
            orden = [python if a == "{python}" else a for a in spec["orden"]]
            codigo, observacion = _lanzar(orden, arbol, spec["timeout"], evidencia)
            esperado = spec.get("codigo_esperado", 0)
            paso = {"verificacion_id": ident, "codigo": codigo, "codigo_esperado": esperado}
            paso["resultado"] = "superado" if codigo == esperado else "fallido"
            # Lo que un paso genera queda en el índice: el siguiente lo ve como rastreado.
            en_arbol("add", "-A")
            if codigo != esperado:
                paso["salida_final"] = _cola(evidencia)
                if observacion:
                    paso["observacion"] = observacion
                salida["pasos"].append(paso)
                salida["motivo"] = f"el paso posterior {ident} no pasa"
                return salida
            salida["pasos"].append(paso)
        campos = en_arbol("diff", "--cached", "--no-renames", "--name-status", "-z", "HEAD", crudo=True)
        campos = [c for c in campos.decode("utf-8").split("\0") if c]
        cambios = list(zip(campos[0::2], campos[1::2]))
        ajenos = sorted(ruta for _, ruta in cambios if not es_vista(ruta, cfg))
        if ajenos:
            salida["motivo"] = f"un paso posterior cambió algo que no es una vista declarada: {ajenos[0]}"
            return salida
        if cambios:
            archivos = {ruta: en_arbol("show", f":{ruta}", crudo=True) for estado, ruta in cambios if estado != "D"}
            borrar = [ruta for estado, ruta in cambios if estado == "D"]
            nuevo = escribir_commit(git, cabeza, archivos, cfg.autor, f"kb: vistas tras {op}\n", borrar)
            if git("update-ref", ref, nuevo, cabeza, comprobar=False) != 0:
                raise Bloqueo("BASE_CAMBIADA", f"{rama} cambió mientras se escribían las vistas: no se escribieron")
            salida.update(vistas=sorted(ruta for _, ruta in cambios), cabeza=nuevo)
    return salida


def _puerta(git, cfg, rama, recibos, op, base, prop, aprobaciones, actor):
    return integrar(
        git.repo,
        rama=rama,
        carpeta=list(cfg.carpetas),
        operacion_id=op,
        base_esperada=base,
        propuesta_rev=prop,
        revisiones=aprobaciones,
        verificador=VerificadorDeclarado(git.repo),
        recibos=recibos,
        aprobacion=cfg.modo,
        actor=actor,
    )


def _ensayar(git, cfg, op, base, prop, aprobaciones, actor, raiz, valido_en):
    """La propuesta por la puerta y los pasos posteriores, en una rama temporal con recibos aparte: nada queda."""
    rama = f"ensayo-{op}-{uuid.uuid4().hex[:8]}"
    git("update-ref", f"refs/heads/{rama}", base, _SIN_REF)
    try:
        with tempfile.TemporaryDirectory(prefix="kb-ensayo-") as tmp:
            recibo = _puerta(git, cfg, rama, Path(tmp), op, base, prop, aprobaciones, actor)
            if recibo.get("estado") == "integrado":
                despues = _despues(git, cfg, rama, op, raiz)
                resultado = {k: recibo.get(k) for k in ("registros", "decisivos", "advertencias", "impacto")}
                resultado.update(despues=despues["pasos"], vistas=despues["vistas"])
                if despues["motivo"]:
                    return {"estado": "bloqueado", "codigo": None, "motivo": despues["motivo"], **resultado}
                return {"estado": "ensayado", "codigo": None, **resultado}
    finally:
        git("update-ref", "-d", f"refs/heads/{rama}", comprobar=False)
    if recibo.get("codigo") != "AUTORIDAD_INSUFICIENTE" or aprobaciones:
        return {k: v for k, v in recibo.items() if k != "operacion_id"}
    # La puerta pide una aprobación que no se le dio: lo que hay que enseñar a quien aprueba, con los mismos digests.
    paquete = preparar_aprobacion(
        git.repo,
        carpeta=list(cfg.carpetas),
        operacion_id=op,
        base=base,
        propuesta=prop,
        valido_en=valido_en or _ahora(),
    )
    if paquete["estado"] == "bloqueado":
        return {k: v for k, v in paquete.items() if k != "operacion_id"}
    return {
        "estado": "pendiente_de_aprobacion",
        "codigo": "AUTORIDAD_INSUFICIENTE",
        "motivo": recibo.get("motivo"),
        "paquete": paquete,
    }


def proponer(
    raiz,
    instalacion,
    *,
    operacion_id,
    archivos,
    actor=None,
    efectos=None,
    importaciones=None,
    aprobaciones=None,
    hasta="ensayo",
    valido_en=None,
):
    """Propone `archivos` del árbol de trabajo de `raiz` y los lleva hasta donde diga `hasta`; devuelve el resultado.

    `estado` es `ensayado`, `integrado`, `subido`, `pendiente_de_aprobacion` (el ensayo necesita una aprobación que no
    se dio: trae el paquete) o `bloqueado`, con el código y el motivo de la puerta cuando es ella quien bloquea.
    `aprobaciones` es la lista de aprobaciones declaradas ya dadas. `valido_en` es el corte de los apoyos del paquete;
    sin él, el instante actual. ValueError u OSError si la instalación o los archivos no se pueden leer.
    """
    cfg = integracion_de(instalacion)
    contenido = leer_archivos(raiz, archivos)
    try:
        return _proponer(
            raiz, cfg, operacion_id, contenido, actor, efectos, importaciones, aprobaciones, hasta, valido_en
        )
    except Bloqueo as b:
        return {"operacion_id": operacion_id, **b.resultado}


def _proponer(raiz, cfg, op, contenido, actor, efectos, importaciones, aprobaciones, hasta, valido_en):
    if hasta not in HASTA:
        raise Bloqueo(None, f"hasta es uno de {', '.join(HASTA)}")
    _comprobar_operacion(op)
    if ".." in op or op.split(".")[0].upper() in _RESERVADOS:
        raise Bloqueo(None, "operacion_id no admite «..» ni un nombre reservado de Windows")
    if actor is None:
        if cfg.modo == "decisiva":
            raise Bloqueo(None, "en el modo decisiva, proponer necesita el actor de quien opera")
        actor = ACTOR
    aprobaciones = [] if aprobaciones is None else aprobaciones
    if not isinstance(aprobaciones, list) or any(
        not isinstance(a, dict) or a.get("mecanismo") != MECANISMO for a in aprobaciones
    ):
        raise Bloqueo(None, "proponer integra con una lista de aprobaciones declaradas (kbol.declarada)")
    if efectos or importaciones:
        solicitud = {"operacion_id": op, "efectos": efectos or {}}
        if importaciones:
            solicitud["importaciones"] = importaciones
        ruta = f"{cfg.carpetas[0]}/_solicitudes/{op}.json"
        if ruta in contenido:
            raise Bloqueo(None, f"la solicitud se da como archivo o con efectos e importaciones, no de las dos formas: {ruta}")
        try:
            contenido = {**contenido, ruta: json.dumps(solicitud, ensure_ascii=False, indent=1).encode("utf-8")}
        except (TypeError, ValueError) as exc:
            raise Bloqueo("ESQUEMA_INVALIDO", f"solicitud no serializable: {exc}") from exc
    git = abrir_clon(cfg)
    clon = traer(git, cfg.rama)
    base = clon["cabeza"]
    recibos = estado_local(cfg.repositorio) / "recibos"
    if hasta != "ensayo":
        previo = _ya_integrada(git, cfg.rama, recibos, op)
        if previo is not None:
            aviso = "la operación ya estaba integrada en el clon: se retoma su recibo y no se vuelve a proponer el disco"
            previo = {**previo, "hasta": hasta, "retomada": True}
            previo["advertencias"] = [*(previo.get("advertencias") or []), aviso]
            return _terminar(git, cfg, op, raiz, hasta, clon, previo)
    prop = escribir_commit(git, base, contenido, cfg.autor, f"propuesta {op}\n")
    comun = {
        "operacion_id": op,
        "hasta": hasta,
        "modo_aprobacion": cfg.modo,
        "actor": actor,
        "base": base,
        "propuesta": prop,
        "clon": git.repo,
        "pendientes_de_subir": clon["pendientes_de_subir"],
        "subido": False,
    }
    if hasta == "ensayo":
        return {**comun, **_ensayar(git, cfg, op, base, prop, aprobaciones, actor, raiz, valido_en)}
    recibo = _puerta(git, cfg, cfg.rama, recibos, op, base, prop, aprobaciones, actor)
    if recibo.get("estado") != "integrado":
        return {**comun, **recibo}
    return _terminar(git, cfg, op, raiz, hasta, clon, {**comun, **recibo})


def _ya_integrada(git, rama, recibos, op):
    """El recibo de `op` si su commit ya está en la rama del clon: la operación se integró y quizá no se subió.

    Así se termina una operación integrada con `integrar`, o cuyo paso posterior o subida fallaron, sin proponerla
    otra vez: la puerta la rechazaría, porque el archivo del disco no lleva los eventos que ella escribió.
    """
    ruta = Path(recibos) / f"{op}.json"
    try:
        recibo = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise Bloqueo("RESULTADO_DESCONOCIDO", f"recibo ilegible: {exc}") from exc
    commit = recibo.get("revision_integrada") if isinstance(recibo, dict) else None
    if recibo.get("estado") != "integrado" or not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{40}", commit):
        return None
    if git("merge-base", "--is-ancestor", commit, f"refs/heads/{rama}", comprobar=False) != 0:
        return None  # su commit no está en esta rama: decide la puerta (otra solicitud o recibo que no corresponde)
    return recibo


def _terminar(git, cfg, op, raiz, hasta, clon, salida):
    """Pasos posteriores y, con `hasta=subir`, la subida, sobre lo ya integrado en la rama del clon."""
    ref = f"refs/heads/{cfg.rama}"
    try:
        despues = _despues(git, cfg, cfg.rama, op, raiz)
    except (Bloqueo, OSError, ValueError) as exc:
        motivo = exc.resultado["motivo"] if isinstance(exc, Bloqueo) else str(exc)
        despues = {"pasos": [], "vistas": [], "cabeza": None, "motivo": f"los pasos posteriores no terminaron: {motivo}"}
    salida = {**salida, "subido": False}
    salida.update(despues=despues["pasos"], vistas=despues["vistas"])
    salida["cabeza"] = git("rev-parse", "--verify", "--end-of-options", ref)
    salida["pendientes_de_subir"] = int(git("rev-list", "--count", f"{clon['remoto']}..{ref}"))
    if despues["motivo"]:
        motivo = f"{despues['motivo']}: lo integrado queda en el clon, sin subir"
        return {**salida, "estado": "bloqueado", "codigo": None, "motivo": motivo}
    if hasta == "integrar":
        return salida
    subida = ("-C", git.repo, "push", "-q", "origin", f"{ref}:{ref}")
    codigo, error = _git_suelto(*subida, extra_env=_red(), timeout=RED)
    if codigo != 0:
        motivo = (
            f"integrado en el clon, pero no se pudo subir: {error}. Si el remoto avanzó, la próxima orden lo dirá y "
            "dará cómo rehacerlo; si no, se sube repitiendo esta orden con el mismo operacion_id"
        )
        return {**salida, "estado": "bloqueado", "codigo": "RESULTADO_DESCONOCIDO", "motivo": motivo}
    return {**salida, "estado": "subido", "subido": True, "pendientes_de_subir": 0}
