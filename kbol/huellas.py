"""Huellas de los registros integrados y desvíos: detectar ediciones fuera del flujo.

Elección local (docs/elecciones.md, «Huellas y desvíos»). La integración y el arranque guardan en
`<primera carpeta>/_huellas.json` la huella SHA-256 del texto de cada registro que escriben, con los saltos de línea
normalizados. `desvios` la recalcula para los registros con historial (los que ya pasaron por la integración) y
lista los que no coinciden o no tienen huella. No bloquea: avisa, para que quien lo vea compare el registro con su
última versión integrada y proponga la diferencia por la integración.

Con la rama canónica, `commits_fuera_del_flujo` mira además su historia: desde el primer commit de la puerta
(integrador o arranque), todo commit de primer padre que cambie la carpeta de registros debe ser de la puerta. Uno que
no lo sea es una escritura directa, que salta la integración. Tampoco bloquea.

No es una firma: quien edite un registro a propósito puede recalcular su huella. Detecta descuidos, como una
edición a mano que deja relaciones sin conectar, no ataques. El nombre evita `integridad`, que el contrato reserva
para las fuentes.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from .snapshot import cargar, carpetas_de, entorno_git

ARCHIVO = "_huellas.json"
# Correos de quien confirma los commits de la puerta (integrar.CORREO y arranque._IDENTIDAD_ARRANQUE); un test los
# contrasta, porque importarlos aquí cerraría un ciclo con integrar.
CORREOS_DE_LA_PUERTA = frozenset({"integrador@localhost", "arranque@localhost"})


def huella(texto):
    """SHA-256 del texto de un registro, con los saltos de línea normalizados a LF."""
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    return hashlib.sha256(texto.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def ruta_de(carpeta):
    return f"{carpetas_de(carpeta)[0]}/{ARCHIVO}"


def serializar_huellas(huellas):
    return (json.dumps(dict(sorted(huellas.items())), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def leer_de_revision(git, revision, carpeta):
    """Las huellas guardadas en una revisión; {} si no hay archivo. `git` es el de la integración."""
    ruta = ruta_de(carpeta)
    if git("cat-file", "-e", f"{revision}:{ruta}", comprobar=False) != 0:
        return {}
    return json.loads(git("show", f"{revision}:{ruta}"))


def actualizadas(previas, escritos):
    """Las huellas previas con las de los registros escritos ({ID: (ruta, texto)})."""
    nuevas = dict(previas)
    for ident, (ruta, texto) in escritos.items():
        nuevas[ident] = {"ruta": ruta, "sha256": huella(texto)}
    return nuevas


def _git(raiz, *args):
    p = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, env=entorno_git())
    return p.returncode, p.stdout


def desvios(raiz, carpeta, *, preparado=False, rama=None, cargado=None, formato=None):
    """{comprobados, avisos, cobertura}: registros con historial cuya huella falta o no coincide.

    Lee el disco o, con `preparado`, el índice de git (lo que va a entrar en el commit, para pre-commit). Con `rama`,
    cada aviso dice dónde está la última versión integrada del registro. `cargado` es el `(snapshot, cobertura)` del
    disco en modo propuesta y con heredados, si quien llama ya lo tiene; `formato`, el formato heredado de la
    instalación (`migracion.formato_de`), o el formato heredado por defecto si no se da.
    """
    snap, cobertura = cargado or cargar(raiz, carpeta, None, modo="propuesta", heredados=True, formato=formato)

    def leer(ruta):
        if preparado:
            codigo, salida = _git(raiz, "show", f":{ruta}")
            return salida if codigo == 0 else None
        archivo = Path(raiz) / ruta
        return archivo.read_bytes() if archivo.is_file() else None

    crudo = leer(ruta_de(carpeta))
    try:
        guardadas = json.loads(crudo) if crudo else {}
    except ValueError:
        guardadas = None
    if not isinstance(guardadas, dict):
        guardadas = {}
        if crudo:
            cobertura = {**cobertura, "advertencias": [*cobertura.get("advertencias", []), f"{ARCHIVO} ilegible"]}
    avisos, comprobados = [], 0
    for ident, r in sorted(snap.registros.items()):
        if not r.get("eventos"):
            continue  # sin historial: aún no ha pasado por la integración
        ruta = snap.rutas[ident]
        texto = leer(ruta)
        if texto is None:
            continue  # en el índice todavía no está: no hay nada que comparar
        comprobados += 1
        esperada = guardadas.get(ident)
        motivo = None
        if not isinstance(esperada, dict) or "sha256" not in esperada:
            motivo = "sin_huella"
        elif esperada["sha256"] != huella(texto):
            motivo = "distinta"
        if motivo:
            aviso = {"id": ident, "ruta": ruta, "motivo": motivo}
            if rama:
                aviso["ultima_integrada"] = f"{rama}:{ruta}"
            avisos.append(aviso)
    return {"comprobados": comprobados, "avisos": avisos, "cobertura": cobertura}


def commits_fuera_del_flujo(raiz, carpeta, rama):
    """{evaluado, desde, commits}: commits de primer padre de `rama` que cambian la carpeta sin pasar por la puerta.

    Solo cuenta desde el primer commit de la puerta: antes no había integración que saltarse. Un commit del integrador
    debe llevar el trailer `Operacion-Id`. Si la rama no se puede leer o la puerta nunca escribió en ella, `evaluado`
    es False y `commits` queda vacío: no se afirma nada.
    """
    formato = "--format=%H%x00%ce%x00%(trailers:key=Operacion-Id,valueonly,separator=%x01)%x00%s"
    codigo, salida = _git(raiz, "log", "--first-parent", formato, "--end-of-options", rama, "--", *carpetas_de(carpeta))
    if codigo != 0:
        return {"evaluado": False, "desde": None, "commits": []}
    lineas = salida.decode("utf-8", "replace").splitlines()
    filas = [linea.split("\x00", 3) for linea in lineas if linea.count("\x00") >= 3]
    filas.reverse()  # del más antiguo al más reciente
    inicio = next((i for i, f in enumerate(filas) if f[1] in CORREOS_DE_LA_PUERTA), None)
    if inicio is None:
        return {"evaluado": False, "desde": None, "commits": []}
    fuera = []
    for sha, correo, operacion, asunto in filas[inicio + 1 :]:
        if correo == "arranque@localhost" or (correo == "integrador@localhost" and operacion.strip()):
            continue
        fuera.append({"commit": sha, "correo": correo, "asunto": asunto})
    return {"evaluado": True, "desde": filas[inicio][0], "commits": fuera}
