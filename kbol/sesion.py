"""Órdenes para los hooks de una instalación (`kbol sesion`): la lógica de conocimiento que cada
instalación repetía en sus hooks, detrás de una sola orden con tres eventos.

El adaptador de la instalación lee el evento de su harness, localiza el binario y llama a `kbol sesion` con el `cwd`
del evento. Lo demás lo resuelve esta orden: sube a la raíz del árbol de trabajo (la del worktree, si lo es), lee de
la configuración de la instalación `carpeta_registros`, `ambito`, `presupuesto` y `rama_canonica`, y deriva la tarea
de la rama si no se le da.

- `inicio`: el paquete de contexto de la tarea y los desvíos, con una sola carga de los registros. El resultado se
  guarda en `.kbol/sesion/inicio-<tarea>.json` con la huella de lo que lo decide y se reutiliza mientras no cambie. Es
  la única orden que lee el reloj: sin `valido_en` usa el instante actual y lo declara.
- `parar`: valida como propuestas los registros de las carpetas que tienen cambios sin commitear; con `rutas`, solo
  esos (lo que editó la sesión). Un registro rechazado es un fallo.
- `commit`: los desvíos del índice de git, lo que va a entrar en el commit. Avisa, no bloquea.

La huella del inicio reúne la versión y los archivos de KBOL, la configuración, la tarea y su relevo, la cabeza, la
rama canónica, el árbol de trabajo (`relevo.huella_del_arbol`: estado, diferencias con la cabeza y contenido de lo no
seguido) y el corte: el instante dado o, si no se da, el día. Límites: no ve los archivos ignorados por git, y con el
corte por día una vigencia que empiece o acabe a otra hora del mismo día no se refleja hasta el siguiente. Un fallo no
se guarda: el inicio siguiente lo vuelve a intentar.
"""

import contextlib
import hashlib
import json
import posixpath
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from . import relevo as rv
from .contexto import preparar_contexto, presentar
from .core import ErrorDeFormato, parse
from .huellas import desvios
from .migracion import formato_de
from .modelo import TIPOS
from .schema import validar
from .snapshot import cargar, entorno_git
from .tiempo import es_instante

EVENTOS = ("inicio", "parar", "commit")
CARPETA = rv.CARPETA.parent / "sesion"
MAX_DESVIOS = 10
MAX_COMMITS = 10
MAX_LINEAS = 30


def _git(raiz, *args):
    p = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(raiz), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=entorno_git(),
    )
    return p.stdout if p.returncode == 0 else None


def raiz_de(ruta):
    """La raíz del árbol de trabajo que contiene `ruta`: la del worktree, si lo es. ValueError si no hay git."""
    salida = _git(ruta, "rev-parse", "--show-toplevel")
    if not salida or not salida.strip():
        raise ValueError(f"{ruta} no está en un árbol de trabajo de git")
    return Path(salida.strip())


def tarea_de_la_rama(raiz):
    """El id de la tarea que corresponde a la rama: lo que no sea letra, cifra, punto, guion o subrayado pasa a guion,
    empieza por letra o cifra y tiene 100 caracteres como mucho; `sin-rama` con la cabeza separada. Dos ramas que solo
    difieren en esos caracteres (`feat/x` y `feat-x`) comparten tarea y relevo."""
    rama = re.sub(r"[^A-Za-z0-9._-]", "-", (_git(raiz, "branch", "--show-current") or "").strip())
    return re.sub(r"^[^A-Za-z0-9]+", "", rama)[:100].rstrip("-.") or "sin-rama"


def configuracion(raiz, instalacion, evento):
    """(configuración, bytes leídos) de la instalación; una ruta relativa lo es a la raíz. ValueError si le falta lo
    que el evento necesita."""
    ruta = Path(instalacion)
    crudo = (ruta if ruta.is_absolute() else Path(raiz) / ruta).read_bytes()
    conf = json.loads(crudo.decode("utf-8"))
    if not isinstance(conf, dict):
        raise ValueError("la configuración de la instalación es un objeto")
    carpetas = conf.get("carpeta_registros")
    if not isinstance(carpetas, str) or not all(c.strip() for c in carpetas.split(",")):
        raise ValueError("carpeta_registros es un texto con las carpetas de registros, separadas por comas")
    if not isinstance(conf.get("rama_canonica", "main"), str) or not conf.get("rama_canonica", "main"):
        raise ValueError("rama_canonica es el nombre de una rama")
    if evento == "inicio":
        if not isinstance(conf.get("ambito"), str) or not conf["ambito"]:
            raise ValueError("ambito es el ámbito del paquete de contexto, como texto")
        presupuesto = conf.get("presupuesto", 30)
        if not isinstance(presupuesto, int) or isinstance(presupuesto, bool) or presupuesto < 0:
            raise ValueError("presupuesto es un número de elementos, 0 o más")
    formato_de(conf)  # un formato heredado mal declarado falla aquí, antes de leer nada
    return conf, crudo


def _carpetas(conf):
    carpetas = [c.strip() for c in conf["carpeta_registros"].split(",")]
    return carpetas if len(carpetas) > 1 else carpetas[0]


def _marca(ruta):
    try:
        estado = Path(ruta).stat()
    except OSError:
        return "ausente"
    return f"{estado.st_size}:{estado.st_mtime_ns}"


def huella_del_inicio(raiz, crudo, conf, tarea, corte):
    """Huella de lo que decide el resultado de `inicio`, o None si git no responde."""
    canonica = conf.get("rama_canonica", "main")
    cabeza = _git(raiz, "rev-parse", "HEAD")
    arbol = rv.huella_del_arbol(raiz)
    if cabeza is None or arbol is None:
        return None
    partes = [
        __version__,
        *sorted(f"{p.name}:{_marca(p)}" for p in Path(__file__).parent.glob("*.py")),
        hashlib.sha256(crudo).hexdigest(),
        tarea,
        (_git(raiz, "branch", "--show-current") or "").strip(),
        _marca(rv.ruta_del_relevo(raiz, tarea)),
        corte,
        cabeza.strip(),
        (_git(raiz, "rev-parse", "--verify", "--quiet", "--end-of-options", f"refs/heads/{canonica}") or "").strip(),
        arbol,
    ]
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()


def _guardado(ruta, huella):
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or datos.get("huella") != huella:
        return None
    calculado = datos.get("calculado")
    try:  # lo que `inicio` va a leer de él: uno con otra forma (otra versión, editado a mano) no se reutiliza
        completo = (
            isinstance(calculado["valido_en"], str)
            and isinstance(calculado["paquete"]["advertencias"], list)
            and isinstance(calculado["paquete"]["cobertura"]["no_evaluado"], list)
            and isinstance(calculado["paquete"]["relevo"]["git"], dict)
            and isinstance(calculado["desvios"]["avisos"], list)
            and all(isinstance(a, dict) and {"id", "ruta", "motivo"} <= set(a) for a in calculado["desvios"]["avisos"])
            and {"estado", "motivo", "revision"} <= set(calculado["paquete"])
            and {"estado", "leidos", "invalidos"} <= set(calculado["paquete"]["cobertura"])
            and "comprobados" in calculado["desvios"]
        )
    except (KeyError, TypeError):
        return None
    return calculado if completo else None


def _linea_de_desvios(avisos, rama):
    distintos = [a["id"] for a in avisos if a["motivo"] == "distinta"]
    sin_huella = sum(1 for a in avisos if a["motivo"] == "sin_huella")
    partes = []
    if distintos:
        resto = f" y {len(distintos) - MAX_DESVIOS} más" if len(distintos) > MAX_DESVIOS else ""
        partes.append(f"{len(distintos)} difieren de lo integrado ({', '.join(distintos[:MAX_DESVIOS])}{resto})")
    if sin_huella:
        partes.append(f"{sin_huella} sin huella")
    if not partes:
        return None
    return (
        f"Desvíos de KBOL (kbol desvios): {'; '.join(partes)}. Se comparan con su versión de {rama} y se proponen por "
        "la integración; no bloquea."
    )


def _trabajo_en_git(git):
    """Lo que la tarea tenía entre manos según git, para una sesión que acaba de compactar su contexto."""
    if not git.get("disponible"):
        return ["Trabajo de la tarea en git: desconocido (git no responde)."]
    lineas = [f"Trabajo de la tarea en git (rama {git['rama']}):"]
    propios = git.get("commits_propios")
    if propios:
        total = len(propios) + git.get("commits_propios_omitidos", 0)
        lineas.append(f"- Commits propios ({total}): " + "; ".join(propios[:MAX_COMMITS]))
    locales = git.get("cambios_locales") or []
    if locales:
        total = len(locales) + git.get("cambios_locales_omitidos", 0)
        lineas.append(f"- Cambios sin commitear ({total}):")
        lineas += [f"  {ruta}" for ruta in locales]
    if len(lineas) == 1:
        lineas.append("- Sin commits propios ni cambios sin commitear.")
    return lineas


def inicio(ruta, instalacion, tarea=None, valido_en=None, origen=None):
    """Paquete de contexto y desvíos de la tarea, reutilizando lo guardado si su huella sigue valiendo."""
    if valido_en is not None and not es_instante(valido_en):
        raise ValueError("valido_en no es un instante ISO 8601 con zona")
    raiz = raiz_de(ruta)
    conf, crudo = configuracion(raiz, instalacion, "inicio")
    tarea = tarea or tarea_de_la_rama(raiz)
    rv.ruta_del_relevo(raiz, tarea)  # valida el id de la tarea antes de usarlo en un nombre de archivo
    guardado_en = raiz / CARPETA / f"inicio-{tarea}.json"
    rama = conf.get("rama_canonica", "main")
    corte = valido_en or datetime.now(timezone.utc).date().isoformat()
    huella = huella_del_inicio(raiz, crudo, conf, tarea, corte)
    calculado = _guardado(guardado_en, huella) if huella else None
    reutilizado = calculado is not None
    if calculado is None:
        instante = valido_en or rv._ahora()
        carpeta = _carpetas(conf)
        cargado = cargar(raiz, carpeta, None, modo="propuesta", heredados=True, formato=formato_de(conf))
        paquete = preparar_contexto(
            raiz,
            tarea=tarea,
            objetivo=None,
            ambito=conf["ambito"],
            carpeta=carpeta,
            instalacion=conf,
            valido_en=instante,
            presupuesto=conf.get("presupuesto", 30),
            cargado=cargado,
        )
        res = desvios(raiz, carpeta, rama=rama, cargado=cargado)
        calculado = {
            "valido_en": instante,
            "paquete": paquete,
            "desvios": {"comprobados": res["comprobados"], "avisos": res["avisos"]},
        }
        # Solo se guarda si lo que decide el resultado no cambió mientras se calculaba; y no poder guardarlo (otro
        # inicio de la misma tarea a la vez, un archivo abierto en Windows) no estropea un resultado ya calculado.
        if huella and huella_del_inicio(raiz, crudo, conf, tarea, corte) == huella:
            with contextlib.suppress(OSError):
                rv._escribir(guardado_en, {"huella": huella, "calculado": calculado})
    paquete, desv = calculado["paquete"], calculado["desvios"]
    advertencias = list(paquete["advertencias"])
    estado, motivos = paquete["estado"], [paquete["motivo"]] if paquete["motivo"] else []
    if not desv["comprobados"] and estado != "bloqueado":
        estado = "parcial"
        motivos.append("ningún registro con historial comprobado en busca de desvíos")
    advertencias += [
        f"{a['id']} ({a['ruta']}): {'difiere de lo integrado' if a['motivo'] == 'distinta' else 'sin huella'}"
        for a in desv["avisos"]
    ]
    lineas = [presentar(paquete)]
    linea = _linea_de_desvios(desv["avisos"], rama)
    if linea:
        lineas.append(linea)
    if not desv["comprobados"]:
        lineas.append("Desvíos de KBOL: no se comprobó ningún registro con historial.")
    if origen == "compact":
        lineas += _trabajo_en_git(paquete["relevo"]["git"])
    resultado = {
        "estado": estado,
        "evento": "inicio",
        "tarea": tarea,
        "reutilizado": reutilizado,
        "huella": huella,
        "paquete": {k: v for k, v in paquete.items() if k not in ("advertencias", "cobertura")},
        "desvios": desv,
    }
    if motivos:
        resultado["motivo"] = "; ".join(motivos)
    return {
        "resultado": resultado,
        "codigo": {"completado": 0, "bloqueado": 2}.get(estado, 3),
        "advertencias": advertencias,
        "texto": "\n".join(lineas),
        "revision": paquete["revision"],
        "valido_en": calculado["valido_en"],
        "alcance": f"{raiz.as_posix()}:{conf['carpeta_registros']}",
        "no_evaluado": [*paquete["cobertura"]["no_evaluado"], "registros sin historial", "quien hizo la edición"],
        "cobertura": {k: paquete["cobertura"][k] for k in ("estado", "leidos", "invalidos")},
    }


def _sin_commitear(raiz):
    """Rutas, relativas a la raíz del repositorio, con cambios sin commitear y que siguen existiendo."""
    salida = _git(raiz, "status", "--porcelain", "-z", "--untracked-files=all")
    if salida is None:
        raise ValueError("git no dio el estado del árbol de trabajo")
    rutas, partes, i = set(), salida.split("\0"), 0
    while i < len(partes):
        entrada = partes[i]
        i += 1
        if len(entrada) < 4:
            continue
        estado, nombre = entrada[:2], entrada[3:]
        if estado[0] in "RC":  # renombrado o copiado: la ruta de origen viene en el campo siguiente
            i += 1
        if "D" not in estado:
            rutas.add(nombre)
    return rutas


def _relativa(raiz, ruta):
    """La ruta, relativa a la raíz y con barras «/»; una relativa lo es a la raíz, no al directorio del proceso. Tal
    cual si está fuera."""
    texto = str(ruta).replace("\\", "/")
    if re.match(r"^/[A-Za-z]/", texto) and re.match(r"^[A-Za-z]:", str(raiz)):  # Git Bash: /c/Users/… → c:/Users/…
        texto = f"{texto[1]}:{texto[2:]}"
    if Path(texto).is_absolute():
        try:
            return Path(texto).resolve().relative_to(Path(raiz).resolve()).as_posix()
        except ValueError:
            return texto
    return posixpath.normpath(texto)


def _en_carpetas(ruta, carpetas):
    return any(c == "." or ruta.startswith(c + "/") for c in carpetas)


def parar(ruta, instalacion, rutas=None):
    """Valida como propuestas los registros de las carpetas con cambios sin commitear; con `rutas`, solo esos."""
    raiz = raiz_de(ruta)
    conf, _ = configuracion(raiz, instalacion, "parar")
    carpetas = [posixpath.normpath(c.strip().replace("\\", "/")) for c in conf["carpeta_registros"].split(",")]
    candidatas = {
        r for r in _sin_commitear(raiz) if r.endswith(".md") and Path(r).name != "index.md" and _en_carpetas(r, carpetas)
    }
    if rutas is not None:
        candidatas &= {_relativa(raiz, r) for r in rutas}
    rechazados, no_registros, examinados = [], [], 0
    for nombre in sorted(candidatas):
        try:
            meta, cuerpo = parse((raiz / nombre).read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ErrorDeFormato) as exc:
            # Como en la carga: un archivo ilegible en una carpeta de registros podría ser un registro.
            examinados += 1
            rechazados.append({"ruta": nombre, "errores": [{"ruta": "", "mensaje": f"no se pudo leer: {exc}"}]})
            continue
        if meta.get("type") not in TIPOS:
            no_registros.append(nombre)
            continue
        examinados += 1
        errores = [h for h in validar(meta, cuerpo, modo="propuesta") if h["severidad"] == "error"]
        if errores:
            rechazados.append({"ruta": nombre, "errores": errores})
    advertencias = []
    if rechazados:
        estado, codigo = "fallido", 1
    elif not examinados:
        estado, codigo = "parcial", 3
        advertencias.append("ningún registro con cambios sin commitear que validar")
    else:
        estado, codigo = "completado", 0
    lineas = [f"{r['ruta']}: {e['ruta']}: {e['mensaje']}" for r in rechazados for e in r["errores"]]
    texto = ""
    if lineas:
        resto = [f"… ({len(lineas) - MAX_LINEAS} líneas más)"] if len(lineas) > MAX_LINEAS else []
        texto = "\n".join(
            ["KBOL rechaza, como propuestas, registros con cambios sin commitear:", *lineas[:MAX_LINEAS], *resto]
        )
    resultado = {
        "estado": estado,
        "evento": "parar",
        "examinados": examinados,
        "rechazados": rechazados,
        "no_registros": no_registros,
    }
    if rechazados:
        resultado["codigo"] = "ESQUEMA_INVALIDO"
        resultado["motivo"] = f"{len(rechazados)} registro(s) no validan como propuesta"
    return {
        "resultado": resultado,
        "codigo": codigo,
        "advertencias": advertencias,
        "texto": texto,
        "revision": None,
        "valido_en": None,
        "alcance": f"{raiz.as_posix()}:{conf['carpeta_registros']}",
        "no_evaluado": ["referencias entre registros", "autoridad", "vigencia", "registros ya commiteados"],
        "cobertura": {},
    }


def commit(ruta, instalacion):
    """Desvíos de lo que va a entrar en el commit (el índice de git). Avisa y no bloquea."""
    raiz = raiz_de(ruta)
    conf, _ = configuracion(raiz, instalacion, "commit")
    rama = conf.get("rama_canonica", "main")
    res = desvios(raiz, _carpetas(conf), preparado=True, rama=rama, formato=formato_de(conf))
    cobertura = res["cobertura"]
    avisos = [
        f"{a['id']} ({a['ruta']}): {'difiere de lo integrado' if a['motivo'] == 'distinta' else 'sin huella'}"
        for a in res["avisos"]
    ]
    resultado = {"evento": "commit", "comprobados": res["comprobados"], "avisos": res["avisos"]}
    if cobertura["estado"] == "bloqueado":
        errores = [h for h in cobertura["hallazgos"] if h["severidad"] == "error"]
        resultado = {
            "estado": "bloqueado",
            "codigo": errores[0]["codigo"],
            "motivo": "snapshot incoherente",
            **resultado,
            "hallazgos": errores,
        }
        codigo = 2
    elif not res["comprobados"] or cobertura["estado"] != "completo":
        resultado = {"estado": "parcial", **resultado}
        codigo = 3
        if not res["comprobados"]:
            avisos.append("ningún registro con historial comprobado: ¿están bien las carpetas?")
    else:
        resultado = {"estado": "completado", **resultado}
        codigo = 0
    lineas = [
        f"aviso: {a['id']} ({a['ruta']}) difiere de lo integrado en {rama}: proponlo por la integración"
        for a in res["avisos"]
        if a["motivo"] == "distinta"
    ]
    return {
        "resultado": resultado,
        "codigo": codigo,
        "advertencias": cobertura["advertencias"] + avisos,
        "texto": "\n".join(lineas),
        "revision": None,
        "valido_en": None,
        "alcance": f"{raiz.as_posix()}:{conf['carpeta_registros']}",
        "no_evaluado": ["registros sin historial", "quien hizo la edición"],
        "cobertura": {k: cobertura[k] for k in ("leidos", "invalidos")},
    }


def ejecutar(evento, ruta, instalacion, *, tarea=None, valido_en=None, origen=None, rutas=None):
    """El resultado del evento: `resultado`, `codigo` de salida, `advertencias`, `texto` para inyectar y lo que el
    sobre declara (`revision`, `valido_en`, `alcance`, `no_evaluado`, `cobertura`)."""
    if evento == "inicio":
        return inicio(ruta, instalacion, tarea=tarea, valido_en=valido_en, origen=origen)
    if evento == "parar":
        return parar(ruta, instalacion, rutas=rutas)
    if evento == "commit":
        return commit(ruta, instalacion)
    raise ValueError(f"evento desconocido: {evento!r} (uno de {', '.join(EVENTOS)})")
