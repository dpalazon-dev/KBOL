"""Verificaciones ejecutadas (KB-DPP implementación 0.8, operación «verificar» y resultados de verificación; E7 acotada).

El ejecutor solo lanza las verificaciones declaradas en la configuración de la instalación, que se versiona: un id, la
orden como lista de argumentos, el tiempo límite y el código de salida esperado. Quien la pide elige el id; no añade
argumentos ni rutas, y nada pasa por una shell. Desde la CLI, la instalación se lee de HEAD y tiene que estar dentro de
la raíz y sin cambios locales (`instalacion_controlada`): lo que se ejecuta es lo integrado, no un archivo cualquiera.

«{python}» en la orden es el intérprete del `.venv` de la raíz si existe y, si no, el que ejecuta KBOL. En ese segundo
caso el entorno es externo a la raíz y el resultado lo dice: lo instalado allí como editable puede ser de otra copia.

La orden escribe su salida en la evidencia, .kbol/verificaciones/<tarea>/<id>-<instante>-<pid>.log, con su SHA-256, y
corre con un entorno sin KB_GITHUB_TOKEN ni variables GIT_*. Si no termina a tiempo, se detiene con todos sus procesos.
El resultado se anota en el relevo de la tarea (origen «kbol»): revisión y huella del árbol probadas, instantes, código,
duración, evidencia y huella de lo declarado. Deja de valer si cambia la revisión o el árbol. Si la verificación cambia
el árbol o la cabeza, no termina o git no responde, queda pendiente de revisión: no se da por superada.

Sin aislamiento ni recibos en esta versión. En Windows, un proceso que la orden deje vivo después de terminar no se
detiene.
"""

import contextlib
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import relevo as relevo_mod
from .snapshot import entorno_git

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,49}")
CAMPOS = {"orden", "timeout", "codigo_esperado", "descripcion"}
TIMEOUT_MAXIMO = 3600
COLA = 30  # líneas finales de la salida que se devuelven; la completa queda en la evidencia
_BLOQUE = 1 << 20


def _ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _una_linea(texto):
    return "\n" not in texto and "\r" not in texto


def verificaciones_de(instalacion):
    """Las verificaciones declaradas en la configuración de la instalación, validadas; ValueError si no lo están."""
    declaradas = instalacion.get("verificaciones", {}) if isinstance(instalacion, dict) else None
    if not isinstance(declaradas, dict):
        raise ValueError("verificaciones es un objeto: id → {orden, timeout, codigo_esperado, descripcion}")
    for ident, v in declaradas.items():
        if not _ID.fullmatch(ident):
            raise ValueError(f"id de verificación inválido: {ident!r} (minúsculas, cifras, guion y subrayado)")
        if not isinstance(v, dict) or set(v) - CAMPOS:
            raise ValueError(f"la verificación {ident} admite {', '.join(sorted(CAMPOS))}")
        orden = v.get("orden")
        if not isinstance(orden, list) or not orden or not all(isinstance(a, str) and a for a in orden):
            raise ValueError(f"la orden de {ident} es una lista no vacía de argumentos")
        if not all(_una_linea(a) for a in orden):
            raise ValueError(f"los argumentos de {ident} son de una sola línea")
        timeout = v.get("timeout")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= TIMEOUT_MAXIMO:
            raise ValueError(f"el timeout de {ident} es un entero de segundos entre 1 y {TIMEOUT_MAXIMO}")
        esperado = v.get("codigo_esperado", 0)
        if not isinstance(esperado, int) or isinstance(esperado, bool):
            raise ValueError(f"el código esperado de {ident} es un entero")
        if "descripcion" in v and not (isinstance(v["descripcion"], str) and _una_linea(v["descripcion"])):
            raise ValueError(f"la descripción de {ident} es un texto de una sola línea")
    return declaradas


def instalacion_controlada(raiz, ruta):
    """(instalación, procedencia) leída de HEAD. ValueError si la ruta está fuera de la raíz, no está versionada o
    tiene cambios locales: lo que se ejecuta tiene que ser lo integrado, no lo que diga un archivo cualquiera."""
    raiz = Path(raiz).resolve()
    try:
        rel = Path(ruta).resolve().relative_to(raiz).as_posix()
    except ValueError:
        raise ValueError(f"la instalación tiene que estar dentro de la raíz: {ruta}") from None

    def git(*args):
        return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, env=entorno_git())

    if git("ls-files", "--error-unmatch", "--", rel).returncode != 0:
        raise ValueError(f"la instalación no está versionada: {rel}")
    if git("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        raise ValueError(f"la instalación tiene cambios sin commitear: {rel}")
    leida = git("show", f"HEAD:./{rel}")
    if leida.returncode != 0:
        raise ValueError(f"no se pudo leer la instalación de HEAD: {rel}")
    cabeza = git("rev-parse", "HEAD").stdout.decode().strip()
    return json.loads(leida.stdout.decode("utf-8")), {"ruta": rel, "revision": cabeza}


def python_de(raiz):
    """(intérprete para «{python}», externo): el del .venv de la raíz si existe; si no, el que ejecuta KBOL."""
    for nombre in ("Scripts/python.exe", "bin/python"):
        propio = Path(raiz) / ".venv" / nombre
        if propio.exists():
            return str(propio), False
    return sys.executable, True


def _entorno():
    return {k: v for k, v in os.environ.items() if k.upper() != "KB_GITHUB_TOKEN" and not k.upper().startswith("GIT_")}


def _matar_arbol(proceso):
    """Detiene el proceso y todos sus descendientes."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proceso.pid)], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proceso.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proceso.wait(timeout=10)


def _lanzar(orden, raiz, timeout, salida):
    """(código o None, observación). Sin shell ni entrada, con la salida (y la de error) en el archivo `salida`."""
    grupo = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with open(salida, "wb") as f:
        try:
            proceso = subprocess.Popen(
                orden, cwd=raiz, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, env=_entorno(), **grupo
            )
        except OSError as exc:
            f.write(str(exc).encode("utf-8"))
            return None, f"no arrancó: {exc}"
        try:
            codigo = proceso.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _matar_arbol(proceso)
            return None, f"no terminó en {timeout} s; se detuvo con todos sus procesos"
    if os.name != "nt":  # lo que la orden dejó vivo al terminar
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proceso.pid, signal.SIGKILL)
    return codigo, None


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while bloque := f.read(_BLOQUE):
            h.update(bloque)
    return h.hexdigest()


def _cola(ruta, lineas=COLA):
    with open(ruta, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 64 * 1024))
        return f.read().decode("utf-8", errors="replace").splitlines()[-lineas:]


def ejecutar(raiz, tarea, instalacion, verificacion_id, rama_canonica="main", procedencia=None):
    """Ejecuta una verificación declarada, guarda su evidencia y la anota en el relevo de la tarea; devuelve el
    resultado con los campos del contrato y las últimas líneas de la salida. `procedencia` dice de dónde salió la
    instalación (la CLI la lee de HEAD con `instalacion_controlada`)."""
    declaradas = verificaciones_de(instalacion)
    if verificacion_id not in declaradas:
        disponibles = ", ".join(sorted(declaradas)) or "ninguna"
        raise ValueError(
            f"verificación no declarada en la instalación: {verificacion_id!r} (declaradas: {disponibles})"
        )
    relevo_mod.ruta_del_relevo(raiz, tarea)  # valida el id de la tarea antes de ejecutar nada
    spec = declaradas[verificacion_id]
    esperado = spec.get("codigo_esperado", 0)
    declaracion = {
        "sha256": hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        **(procedencia or {"ruta": None, "revision": None}),
    }
    python, externo = python_de(raiz)
    orden = [python if a == "{python}" else a for a in spec["orden"]]

    revision = relevo_mod.hechos_de_git(raiz, rama_canonica).get("cabeza")
    arbol_antes = relevo_mod.huella_del_arbol(raiz)
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidencia = (
        Path(raiz)
        / relevo_mod.CARPETA.parent
        / "verificaciones"
        / tarea
        / f"{verificacion_id}-{marca}-{os.getpid()}.log"
    )
    evidencia.parent.mkdir(parents=True, exist_ok=True)

    iniciado = _ahora()
    inicio = time.monotonic()
    codigo, observacion = _lanzar(orden, raiz, spec["timeout"], evidencia)
    duracion = round(time.monotonic() - inicio, 1)
    terminado = _ahora()
    arbol_despues = relevo_mod.huella_del_arbol(raiz)
    cabeza_despues = relevo_mod.hechos_de_git(raiz, rama_canonica).get("cabeza")

    observaciones = [observacion] if observacion else []
    if arbol_antes is None or revision is None:
        observaciones.append("git no dio la revisión o el árbol probados")
    elif cabeza_despues != revision:
        observaciones.append("la cabeza de git cambió mientras corría: no se sabe qué revisión probó")
    elif arbol_despues != arbol_antes:
        observaciones.append("la verificación cambió el árbol de trabajo: no se sabe qué contenido probó")
    if codigo is None:
        no_arranco = observacion.startswith("no arrancó")
        resultado, contrato = "desconocido", "no_ejecutado" if no_arranco else "requiere_revision"
    elif observaciones:
        resultado, contrato = "desconocido", "requiere_revision"
    elif codigo == esperado:
        resultado, contrato = "pasa", "superado"
    else:
        resultado, contrato = "falla", "fallido"

    ruta_evidencia = evidencia.relative_to(raiz).as_posix()
    huella = _sha256(evidencia)
    entorno_ref = {"python": python, "externo": externo, "aislamiento": "ninguno"}
    anotada = {
        "comando": f"{verificacion_id}: {' '.join(spec['orden'])}",
        "resultado": resultado,
        "origen": "kbol",
        "verificacion_id": verificacion_id,
        "revision": revision,
        "arbol": arbol_antes,
        "iniciado_en": iniciado,
        "en": terminado,
        "codigo": codigo,
        "codigo_esperado": esperado,
        "duracion_s": duracion,
        "evidencia": {"ruta": ruta_evidencia, "sha256": huella},
        "declaracion": declaracion,
        "entorno": entorno_ref,
    }
    if observaciones:
        anotada["motivo"] = "; ".join(observaciones)
    relevo_mod.anotar_verificacion(raiz, tarea, anotada, rama_canonica)

    return {
        "verificacion_id": verificacion_id,
        "revision_probada": revision,
        "arbol_probado": arbol_antes,
        "declaracion": declaracion,
        "entorno_ref": entorno_ref,
        "iniciado_en": iniciado,
        "terminado_en": terminado,
        "resultado": contrato,
        "resultado_relevo": resultado,
        "codigo": codigo,
        "codigo_esperado": esperado,
        "duracion_s": duracion,
        "evidencia_ref": {"ruta": ruta_evidencia, "sha256": huella},
        "observaciones": observaciones,
        "salida_final": _cola(evidencia),
    }
