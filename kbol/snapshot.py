"""Carga de un snapshot: los registros del perfil KB-DPP de una carpeta, en una revisión de git o en el disco.

Solo lee. Los índices generados y los archivos legibles cuyo `type` no es del perfil (formato heredado, fijos) se
omiten y se cuentan. Un archivo ilegible (cabecera ausente o YAML inválido, texto que no es UTF-8) o un registro
inválido no entra y deja la carga parcial: podría ser un registro, así que la consulta no se presenta como completa.
Un ID repetido excluye todas sus copias y bloquea la carga, porque elegir una dependería del orden de los archivos.
Sobre lo cargado se aplican VAL-02 y VAL-07 (`referencias.validar_snapshot`).

Con `heredados=True`, los registros del formato heredado se leen aparte, como fichas de la migración en
seco (`snapshot.heredados`): sirven para nombrarlos en las consultas durante la transición, nunca como normativos.
Un ID heredado que repite uno del perfil, u otro heredado, bloquea la carga como cualquier ID repetido; un registro
heredado (con `id` o con nombre de registro) sin un ID de forma heredada (`ADR-NNNN`, `QD-nnn`…) no se omite: deja
la carga parcial. Un documento con `type` de registro pero sin `id` ni nombre de registro se omite. El formato es el
heredado por defecto salvo que la instalación declare el suyo (`formato_heredado`): entonces lo sustituye, y un ID que no encaja en el patrón de su etiqueta deja la carga parcial.
"""

import os
import subprocess
from pathlib import Path

from .core import ErrorDeFormato, parse
from .migracion import POR_DEFECTO, inspeccionar
from .modelo import TIPOS
from .proyeccion import Snapshot
from .referencias import validar_snapshot
from .schema import validar

BLOQUEANTES = {"CONFLICTO_NORMATIVO", "ESQUEMA_INVALIDO"}
# Variables que git necesita para funcionar; nada más se hereda (ni tokens ni GIT_* del entorno).
_ENTORNO = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TZ",
)


def entorno_git():
    """Entorno mínimo para procesos git: sin `KB_GITHUB_TOKEN` ni variables `GIT_*` heredadas."""
    return {k: v for k, v in os.environ.items() if k.upper() in _ENTORNO}


def _git(raiz, *args):
    comando = ["git", "--literal-pathspecs", "-C", str(raiz), *args]
    return subprocess.run(comando, capture_output=True, check=True, env=entorno_git()).stdout


def carpetas_de(carpeta):
    """Las carpetas de una instalación como tupla: una, como texto, o varias, como lista (la primera, la política)."""
    if isinstance(carpeta, os.PathLike):
        carpeta = os.fspath(carpeta)
    return (carpeta,) if isinstance(carpeta, str) else tuple(os.fspath(c) for c in carpeta)


def _archivos_git(raiz, revision, carpeta):
    rutas = []
    for c in carpetas_de(carpeta):
        salida = _git(raiz, "ls-tree", "-r", "-z", "--name-only", "--full-name", "--end-of-options", revision, "--", c)
        propias = [r for r in salida.decode("utf-8").split("\0") if r]
        if not propias:
            raise FileNotFoundError(f"{c} no existe o está vacía en {revision}")
        rutas += propias
    for ruta in sorted({p for p in rutas if p.endswith(".md")}):
        yield ruta, _git(raiz, "show", f"{revision}:{ruta}")


def _archivos_disco(raiz, carpeta):
    rutas = set()
    for c in carpetas_de(carpeta):
        base = Path(raiz) / c
        if not base.is_dir():
            raise FileNotFoundError(f"{base} no existe")
        rutas |= set(base.rglob("*.md"))
    for p in sorted(rutas):
        yield p.relative_to(raiz).as_posix(), p.read_bytes()


def _ficha(informe, etiqueta, formato):
    """La ficha de un registro heredado, desde el informe de la migración en seco; None si no es un registro."""
    if informe.get("resultado") != "propuesto" or not formato.id_valido(etiqueta, informe.get("id")):
        return None
    campos = (
        "id",
        "tipo",
        "ruta",
        "estado_heredado",
        "estado_propuesto",
        "ambiguedades",
        "relaciones_propuestas",
        "autoridad_heredada",
    )
    return {**{c: informe.get(c) for c in campos}, "requiere_revision": bool(informe.get("requiere_revision"))}


def cargar(raiz, carpeta=".", revision=None, modo="canonico", heredados=False, formato=None):
    """(Snapshot, cobertura). Sin `revision` lee el disco y lo declara: no es una revisión canónica.

    `modo` es el de validación de cada registro: `canonico` para una revisión integrada, `propuesta` para el árbol
    de una propuesta, cuyos registros nuevos aún no tienen eventos.

    `formato` es el formato heredado que declara la instalación (`migracion.formato_de`); None, `migracion.POR_DEFECTO`.

    `cobertura["estado"]` es `completo`, `parcial` o `bloqueado`.
    """
    formato = formato or POR_DEFECTO
    archivos = _archivos_git(raiz, revision, carpeta) if revision else _archivos_disco(raiz, carpeta)
    leidos, rutas_por_id = {}, {}
    cobertura = {
        "estado": "completo",
        "leidos": 0,
        "omitidos": 0,
        "heredados": 0,
        "invalidos": [],
        "hallazgos": [],
        "advertencias": [],
    }
    fichas = {}
    for ruta, contenido in archivos:
        if Path(ruta).name == "index.md":
            cobertura["omitidos"] += 1  # vista generada, no registro
            continue
        try:
            meta, cuerpo = parse(contenido.decode("utf-8"))
        except UnicodeDecodeError:
            cobertura["invalidos"].append({"ruta": ruta, "motivo": "no es UTF-8"})
            continue
        except ErrorDeFormato as exc:
            # Un archivo ilegible podría ser un registro: su ausencia no es una ausencia legítima.
            cobertura["invalidos"].append({"ruta": ruta, "motivo": f"cabecera ilegible: {exc}"})
            continue
        if meta.get("type") not in TIPOS:
            etiqueta = meta.get("type")
            if heredados and etiqueta in formato.tipos and ("id" in meta or formato.es_registro(ruta)):
                informe = inspeccionar(contenido.decode("utf-8"), ruta, revision or "disco", formato)
                ficha = _ficha(informe, etiqueta, formato)
                if ficha is None:
                    # Un registro heredado sin ID válido no se omite: podría ser cualquiera de ellos.
                    motivo = f"registro heredado sin id válido: {meta.get('id')!r}"
                    cobertura["invalidos"].append({"ruta": ruta, "motivo": motivo})
                    continue
                rutas_por_id.setdefault(ficha["id"], []).append(ruta)
                fichas.setdefault(ficha["id"], ficha)
                continue
            cobertura["omitidos"] += 1
            continue
        errores = [h for h in validar(meta, cuerpo, modo=modo) if h["severidad"] == "error"]
        if errores:
            cobertura["invalidos"].append({"ruta": ruta, "motivo": "; ".join(e["mensaje"] for e in errores[:3])})
            continue
        rutas_por_id.setdefault(meta["id"], []).append(ruta)
        leidos.setdefault(meta["id"], (meta, cuerpo, ruta))
    registros, cuerpos, ruta_de, heredados_ok = {}, {}, {}, {}
    for ident, copias in rutas_por_id.items():
        if len(copias) > 1:
            cobertura["hallazgos"].append(
                {
                    "codigo": "ESQUEMA_INVALIDO",
                    "ruta": ident,
                    "mensaje": f"ID repetido en {copias}" + (" (formato heredado)" if ident in fichas else ""),
                    "severidad": "error",
                }
            )
            continue
        if ident in fichas:
            heredados_ok[ident] = fichas[ident]
        else:
            registros[ident], cuerpos[ident], ruta_de[ident] = leidos[ident]
    snapshot = Snapshot(registros, revision or "disco", cuerpos, ruta_de, heredados_ok)
    cobertura["leidos"] = len(registros)
    cobertura["heredados"] = len(heredados_ok)
    if heredados_ok:
        cobertura["advertencias"].append(
            f"{len(heredados_ok)} registros en formato heredado: se leen como importados sin historial admitido "
            "y no rigen"
        )
    cobertura["hallazgos"] += validar_snapshot(snapshot)
    errores = [h for h in cobertura["hallazgos"] if h["severidad"] == "error"]
    if any(h["codigo"] in BLOQUEANTES for h in errores):
        cobertura["estado"] = "bloqueado"
    elif errores or cobertura["invalidos"]:
        cobertura["estado"] = "parcial"
    if revision is None:
        cobertura["advertencias"].append("lectura del disco: puede incluir cambios sin integrar")
    return snapshot, cobertura
