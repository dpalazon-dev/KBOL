"""Relevo por tarea (KB-DPP implementación 0.8, «Relevo mínimo», y ESC-05 «Continuidad sin autorización inventada»).

El relevo es el estado de una tarea separado de la conversación: objetivo y referencia de autorización, alcance y
límites, verificaciones con su resultado y su revisión, bloqueos, preguntas y siguiente paso con su fundamento. Lo
guarda el agente (`guardar`) en `.kbol/relevos/<tarea>.json` de la raíz, un estado local que no es conocimiento ni se
versiona. Al guardarlo por primera vez se anota la base de la tarea en git, para distinguir después una rama sin
trabajo de una ya integrada.

Las verificaciones ejecutadas las anota `kbol verificar` (`anotar_verificacion`, módulo verificar), con la huella del
árbol de trabajo probado; `guardar` las conserva aunque la sesión no las repita, y no admite que la sesión las escriba.
Una ejecución nueva de la misma verificación sustituye a la anterior, que pasa al historial
sin su salida completa: un fallo seguido de un éxito queda escrito. El historial guarda las últimas `HISTORIAL`.

`relevo` lo combina con hechos de git (rama, base, commits propios y ajenos, cambios locales, integración) y declara
en `no_consta` lo que nunca se guardó: no lo deduce. La autorización va marcada como declarada por la sesión y no
verificada: no es una autorización portable. Construirlo solo lee git, sin tomar bloqueos del índice; no ejecuta las
verificaciones, que se registran como se hicieron. Los textos no admiten saltos de línea: un relevo no puede
presentarse como si fueran restricciones.
"""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .snapshot import entorno_git
from .tiempo import es_instante, instante

CARPETA = Path(".kbol") / "relevos"
_TAREA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
# Nombres que Windows reserva para dispositivos: un archivo con ellos no se puede crear.
_RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
ESPERA_BLOQUEO = 30
HISTORIAL = 200
BLOQUEO_CADUCADO = 120
RESULTADOS = ("pasa", "falla", "no_ejecutada", "desconocido")
CAMPOS = ("objetivo", "autorizacion", "verificaciones", "bloqueos", "preguntas", "siguiente_paso")
# Lo que el relevo mínimo necesita y, si falta, se declara.
MINIMOS = ("objetivo", "autorizacion", "verificaciones", "siguiente_paso")
LIMITE = 20


def _ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ruta(raiz, tarea):
    if not isinstance(tarea, str) or not _TAREA.fullmatch(tarea):
        raise ValueError(f"id de tarea inválido: {tarea!r} (letras, cifras, punto, guion y subrayado)")
    if tarea.endswith(".") or tarea.split(".")[0].upper() in _RESERVADOS:
        raise ValueError(f"id de tarea inválido en Windows: {tarea!r} (punto final o nombre reservado)")
    return Path(raiz) / CARPETA / f"{tarea}.json"


def ruta_del_relevo(raiz, tarea):
    """La ruta del relevo de la tarea; ValueError si el id no es seguro."""
    return _ruta(raiz, tarea)


def _texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip() or "\n" in valor or "\r" in valor:
        raise ValueError(f"{campo} es un texto de una sola línea")


def _textos(valor, campo):
    if not isinstance(valor, list):
        raise ValueError(f"{campo} es una lista de textos")
    for v in valor:
        _texto(v, campo)


def _validar(datos):
    if not isinstance(datos, dict):
        raise ValueError("el relevo es un objeto")
    sobrantes = sorted(set(datos) - set(CAMPOS))
    if sobrantes:
        raise ValueError(f"campos no admitidos en el relevo: {', '.join(sobrantes)}")
    if "objetivo" in datos:
        _texto(datos["objetivo"], "objetivo")
    aut = datos.get("autorizacion")
    if aut is not None:
        if not isinstance(aut, dict) or set(aut) - {"referencia", "alcance", "limites"}:
            raise ValueError("autorizacion admite referencia, alcance y limites")
        for campo in ("referencia", "alcance"):
            if campo in aut:
                _texto(aut[campo], f"autorizacion.{campo}")
        if "limites" in aut:
            _textos(aut["limites"], "autorizacion.limites")
    for v in datos.get("verificaciones") or []:
        if not isinstance(v, dict) or set(v) - {"comando", "resultado", "revision", "en", "motivo"}:
            raise ValueError(
                "una verificación declarada admite comando, resultado, revision, en y motivo; las ejecutadas las anota "
                "kbol verificar"
            )
        _texto(v.get("comando"), "verificaciones.comando")
        if v.get("resultado") not in RESULTADOS:
            raise ValueError(f"resultado de una verificación: uno de {', '.join(RESULTADOS)}")
        if v["resultado"] in ("pasa", "falla"):
            # Un resultado sin la revisión y el instante en que se obtuvo no se puede contrastar.
            _texto(v.get("revision"), "verificaciones.revision")
            if not es_instante(v.get("en")):
                raise ValueError("verificaciones.en es el instante del resultado, ISO 8601 con zona")
        if "motivo" in v:
            _texto(v["motivo"], "verificaciones.motivo")
    for campo in ("bloqueos", "preguntas"):
        if campo in datos:
            _textos(datos[campo], campo)
    paso = datos.get("siguiente_paso")
    if paso is not None:
        if not isinstance(paso, dict) or set(paso) - {"accion", "fundamento"}:
            raise ValueError("siguiente_paso admite accion y fundamento")
        _texto(paso.get("accion"), "siguiente_paso.accion")
        if "fundamento" in paso:
            _texto(paso["fundamento"], "siguiente_paso.fundamento")


def _leer(ruta, tarea):
    try:
        guardado = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(guardado, dict):
        raise ValueError(f"{ruta} no es un relevo")
    if guardado.get("tarea") != tarea:
        # En Windows dos ids que solo difieren en mayúsculas comparten archivo: no se entrega el de otra tarea.
        raise ValueError(f"{ruta} guarda el relevo de {guardado.get('tarea')!r}, no de {tarea!r}")
    return guardado


def _escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)
    return ruta


@contextmanager
def _bloqueo(ruta):
    """Exclusión entre quienes leen, modifican y escriben el relevo (guardar y anotar_verificacion)."""
    candado = ruta.with_name(f"{ruta.name}.lock")
    candado.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + ESPERA_BLOQUEO
    while True:
        try:
            fd = os.open(candado, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:  # el de un proceso que murió sin soltarlo
                if time.time() - candado.stat().st_mtime > BLOQUEO_CADUCADO:
                    candado.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > limite:
                raise ValueError(f"el relevo está bloqueado por otro proceso: {candado}") from None
            time.sleep(0.05)
    try:
        os.close(fd)
        yield
    finally:
        candado.unlink(missing_ok=True)


def _ejecutadas(guardado):
    return [v for v in guardado.get("verificaciones") or [] if isinstance(v, dict) and v.get("origen") == "kbol"]


def guardar(raiz, tarea, datos, rama_canonica="main"):
    """Guarda el relevo de la tarea, validado, de forma atómica; devuelve su ruta. Sustituye al anterior y conserva la
    base de la tarea en git que se anotó al guardarlo por primera vez y las verificaciones que ejecutó KBOL."""
    ruta = _ruta(raiz, tarea)
    _validar(datos)
    with _bloqueo(ruta):
        previo = _leer(ruta, tarea) or {}
        base = previo.get("base_git") or hechos_de_git(raiz, rama_canonica).get("base")
        contenido = {"tarea": tarea, **datos, "base_git": base, "actualizado_en": _ahora()}
        if previo.get("historial_verificaciones"):
            contenido["historial_verificaciones"] = previo["historial_verificaciones"]
        ejecutadas = _ejecutadas(previo)
        if ejecutadas:
            contenido["verificaciones"] = [*(datos.get("verificaciones") or []), *ejecutadas]
        return _escribir(ruta, contenido)


def anotar_verificacion(raiz, tarea, verificacion, rama_canonica="main"):
    """Anota en el relevo una verificación ejecutada por KBOL y sustituye la anterior del mismo id, cuya evidencia
    borra. Crea el relevo si no existía, con la base de la tarea en git."""
    ruta = _ruta(raiz, tarea)
    with _bloqueo(ruta):
        previo = _leer(ruta, tarea) or {"tarea": tarea, "base_git": hechos_de_git(raiz, rama_canonica).get("base")}
        otras, sustituidas = [], []
        for v in previo.get("verificaciones") or []:
            misma = v.get("origen") == "kbol" and v.get("verificacion_id") == verificacion["verificacion_id"]
            (sustituidas if misma else otras).append(v)
        historial = [*(previo.get("historial_verificaciones") or []), *(_al_historial(v) for v in sustituidas)]
        contenido = {**previo, "verificaciones": [*otras, verificacion], "actualizado_en": _ahora()}
        if historial:
            contenido["historial_verificaciones"] = historial[-HISTORIAL:]
        escrita = _escribir(ruta, contenido)
    for v in sustituidas:
        _borrar_evidencia(raiz, v, conservar=verificacion["evidencia"]["ruta"])
    return escrita


def _al_historial(verificacion):
    """La verificación sustituida, sin su salida completa, que se borra: queda dónde estaba y su huella."""
    evidencia = verificacion.get("evidencia")
    if isinstance(evidencia, dict):
        evidencia = {**evidencia, "borrada": True}
    return {**verificacion, "evidencia": evidencia}


def _borrar_evidencia(raiz, verificacion, conservar):
    """Borra la evidencia de una verificación sustituida, solo si está en .kbol/verificaciones/."""
    ruta = (verificacion.get("evidencia") or {}).get("ruta")
    if not isinstance(ruta, str) or ruta == conservar:
        return
    carpeta = (Path(raiz) / CARPETA.parent / "verificaciones").resolve()
    archivo = (Path(raiz) / ruta).resolve()
    if carpeta in archivo.parents:
        archivo.unlink(missing_ok=True)


def _git(raiz, *args):
    p = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(raiz), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno_git(),
    )
    # Solo el final: la primera línea de `status --porcelain` puede empezar por espacio y es parte del formato.
    return p.stdout.rstrip("\r\n") if p.returncode == 0 else None


def huella_del_arbol(raiz):
    """SHA-256 de los cambios sin commitear de la raíz (estado, diferencias con HEAD y contenido de lo no seguido), sin
    el estado local de KBOL; None si git no responde. Como la cabeza: si cambia, lo verificado ya no es esto."""

    def git(*args):
        p = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(raiz), *args], capture_output=True, env=entorno_git()
        )
        return p.stdout if p.returncode == 0 else None

    fuera = ":(exclude,glob)**/.kbol/**"
    estado = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".", fuera)
    diferencias = git("diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv", "--", ".", fuera)
    nuevos = git("ls-files", "--others", "--exclude-standard", "-z", "--", ".", fuera)
    if estado is None or diferencias is None or nuevos is None:
        return None
    h = hashlib.sha256()
    for parte in (estado, diferencias):
        h.update(len(parte).to_bytes(8, "big") + parte)
    for nombre in sorted(n for n in nuevos.split(b"\0") if n):
        h.update(
            len(nombre).to_bytes(8, "big") + nombre + _huella_de(Path(raiz) / nombre.decode("utf-8", "surrogateescape"))
        )
    return h.hexdigest()


def _huella_de(ruta):
    """SHA-256 del contenido de un archivo, leído por bloques; vacío si no se puede leer (repositorio anidado)."""
    h = hashlib.sha256()
    try:
        with open(ruta, "rb") as f:
            while bloque := f.read(1 << 20):
                h.update(bloque)
    except OSError:
        pass
    return h.digest()


def _lineas(texto):
    return [linea for linea in (texto or "").splitlines() if linea.strip()]


def _es_estado_de_kbol(ruta):
    return ".kbol" in Path(ruta).parts


def hechos_de_git(raiz, rama_canonica, base_registrada=None):
    """Rama, cabeza, base de la tarea, commits propios y ajenos, cambios locales e integración. `None` = no se pudo
    calcular, que no es lo mismo que «no hay»."""
    cabeza = _git(raiz, "rev-parse", "HEAD")
    if cabeza is None:
        return {"disponible": False, "avisos": ["git no da una cabeza: repositorio sin commits o sin git"]}
    canonica = _git(raiz, "rev-parse", "--verify", "--end-of-options", f"refs/heads/{rama_canonica}")
    avisos = [] if canonica else [f"la rama canónica {rama_canonica} no existe en este clon"]
    base = base_registrada or (_git(raiz, "merge-base", "HEAD", canonica) if canonica else None)
    # Rutas del estado relativas a la raíz pedida (-- .), sin el estado local de KBOL, que no es trabajo pendiente.
    estado = _lineas(
        _git(raiz, "-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "--", ".")
    )
    hechos = {
        "disponible": True,
        "rama": _git(raiz, "branch", "--show-current") or "(HEAD separado)",
        "cabeza": cabeza,
        "rama_canonica": rama_canonica,
        "base": base,
        "commits_propios": _lineas(_git(raiz, "log", "--format=%s", f"{base}..HEAD")) if base else None,
        "ajenos": _lineas(_git(raiz, "log", "--format=%s", f"{base}..{canonica}")) if base and canonica else None,
        "cambios_locales": [linea[3:] for linea in estado if not _es_estado_de_kbol(linea[3:])],
        "en_la_canonica": bool(canonica) and _git(raiz, "merge-base", "--is-ancestor", "HEAD", canonica) is not None,
        "avisos": avisos,
    }
    for campo in ("commits_propios", "ajenos", "cambios_locales"):
        if hechos[campo] is not None and len(hechos[campo]) > LIMITE:
            hechos[f"{campo}_omitidos"] = len(hechos[campo]) - LIMITE
            hechos[campo] = hechos[campo][:LIMITE]
    return hechos


def _entrega(git):
    """`local`, `integrado`, `sin_trabajo` o `desconocido`. Nunca «integrado» sin trabajo propio que integrar."""
    if not git.get("disponible"):
        return "desconocido"
    if git["cambios_locales"]:
        return "local"
    if git["commits_propios"] is None:
        return "desconocido"
    if not git["commits_propios"]:
        return "sin_trabajo"
    return "integrado" if git["en_la_canonica"] else "local"


def _verificacion(v, git, arbol):
    """La verificación con `desfasada`: True si cambió la revisión o, en las ejecutadas, el árbol de trabajo;
    "desconocido" si no se puede saber."""
    salida = dict(v)
    if not v.get("revision") or not git.get("disponible"):
        salida["desfasada"] = "desconocido"
    elif v["revision"] != git["cabeza"]:
        salida["desfasada"] = True
    elif v.get("origen") == "kbol":
        actual = arbol()
        salida["desfasada"] = "desconocido" if actual is None or not v.get("arbol") else v["arbol"] != actual
    else:
        salida["desfasada"] = False
    if es_instante(v.get("en")):
        segundos = (datetime.now(timezone.utc) - instante(v["en"])).total_seconds()
        salida["antiguedad_dias"] = round(segundos / 86400, 1)
    return salida


def relevo(raiz, tarea, rama_canonica="main"):
    """El relevo de la tarea: lo guardado, los hechos de git y lo que no consta. Solo lee."""
    guardado = _leer(_ruta(raiz, tarea), tarea)
    estado = "sin_relevo" if guardado is None else "guardado"
    guardado = guardado or {}
    git = hechos_de_git(raiz, rama_canonica, guardado.get("base_git"))
    calculada = []

    def arbol():  # solo si alguna verificación ejecutada lo necesita, y una sola vez
        if not calculada:
            calculada.append(huella_del_arbol(raiz))
        return calculada[0]

    aut = guardado.get("autorizacion")
    paso = guardado.get("siguiente_paso")
    no_consta = [c for c in MINIMOS if not guardado.get(c)]
    if aut and not aut.get("referencia"):
        no_consta.append("autorizacion.referencia")
    if paso and not paso.get("fundamento"):
        no_consta.append("siguiente_paso.fundamento")
    return {
        "tarea": tarea,
        "estado": estado,
        "actualizado_en": guardado.get("actualizado_en"),
        "objetivo": guardado.get("objetivo"),
        # Lo que la sesión dice que se le autorizó: no se ha verificado y no se puede invocar como autorización.
        "autorizacion": {**aut, "declarada": True, "verificada": False} if aut else None,
        "verificaciones": [_verificacion(v, git, arbol) for v in guardado.get("verificaciones") or []],
        "historial_verificaciones": guardado.get("historial_verificaciones") or [],
        "bloqueos": guardado.get("bloqueos") or [],
        "preguntas": guardado.get("preguntas") or [],
        "siguiente_paso": paso,
        "git": git,
        "estado_entrega": _entrega(git),
        "no_consta": no_consta,
    }
