"""Comprobación local única de KBOL, solo con la biblioteca estándar.

Uso: `uv run python tools/comprobar.py [--rapido] [--sin-di] [--instalar-hook]`. Ejecuta en orden y se detiene en el primer fallo:

1. análisis estático (`ruff` 0.17.4) sobre `kbol`, `tests` y este script;
2. la suite de pruebas en Python 3.10 y 3.14, cada una en un entorno aislado (`uv run --isolated`) para no tocar
   el `.venv` del proyecto; con `--rapido`, una sola vez con el intérprete del proyecto;
3. los tests de `tools/di`, en su propio proyecto de uv (`tools/di/pyproject.toml`, con Docling), en una pasada aparte;
   no corren con `--rapido` ni con `--sin-di`, y la salida lo dice.

`--instalar-hook` escribe `.git/hooks/pre-push`, que ejecuta este script con `--rapido`. No sobrescribe un hook que
no haya escrito este script. Fuera de la comprobación queda el análisis estático de `tools/di`.

Límites. Solo prueba la máquina local: un resultado verde aquí no acredita
nada en otra máquina, otro sistema operativo u otras versiones de dependencias. Nada obliga a ejecutarla: si el hook
no está instalado, o quien empuja se salta los hooks, el código llega sin comprobar. Los procesos hijo reciben
`core.fsmonitor=false` por el entorno (`GIT_CONFIG_*`), sin tocar la configuración global; `kbol` filtra las
variables `GIT_*` en sus propios procesos git, así que esa protección solo alcanza a los comandos que lanzan las
pruebas directamente.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUFF = "ruff@0.17.4"
VERSIONES = ("3.10", "3.14")
MARCA_HOOK = "# Escrito por tools/comprobar.py --instalar-hook"


# Variables que atan un proceso a su intérprete (`uv run`) o a un repositorio (git, al lanzar un hook). Heredadas, el
# Python 3.10 del hijo cargaría la biblioteca del 3.14 del padre, y el git de los tests actuaría sobre este repositorio.
_SOLO_DEL_PADRE = ("PYTHONHOME", "UV_INTERNAL__PYTHONHOME", "VIRTUAL_ENV", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")


def entorno():
    """Entorno de los hijos: el actual, sin lo que es solo del padre, más `core.fsmonitor=false`.

    Con fsmonitor activo, `git add` puede colgarse en la suite.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SOLO_DEL_PADRE}
    n = int(env.get("GIT_CONFIG_COUNT") or 0)
    env[f"GIT_CONFIG_KEY_{n}"] = "core.fsmonitor"
    env[f"GIT_CONFIG_VALUE_{n}"] = "false"
    env["GIT_CONFIG_COUNT"] = str(n + 1)
    return env


def ejecutar(comando, cwd=RAIZ, **kw):
    return subprocess.run(comando, cwd=cwd, env=entorno(), **kw)


class Fallo(Exception):
    pass


def paso_ruff(uv):
    p = ejecutar([uv, "tool", "run", RUFF, "check", "kbol", "tests", "tools/comprobar.py", "tools/calibracion"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise Fallo("ruff ha encontrado problemas:\n" + (p.stdout + p.stderr).strip())


def paso_suite(uv, version):
    if version is None:
        comando = [uv, "run", "python", "-m", "pytest", "-c", "pyproject.toml", "-q", "tests"]
    else:
        comando = [uv, "run", "--isolated", "--python", version, "python", "-m", "pytest"]
        comando += ["-c", "pyproject.toml", "-q", "tests"]
    p = ejecutar(comando, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        cola = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
        raise Fallo(f"la suite falla (código {p.returncode}):\n{cola}")


def paso_di(uv):
    comando = [uv, "run", "--project", ".", "python", "-m", "pytest", "-q"]
    p = ejecutar(comando, cwd=RAIZ / "tools" / "di", capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        cola = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
        raise Fallo(f"los tests de tools/di fallan (código {p.returncode}):\n{cola}")


def pasos(uv, rapido, di=True):
    lista = [("análisis estático (ruff)", lambda: paso_ruff(uv))]
    if rapido:
        lista.append(("suite de pruebas (intérprete del proyecto)", lambda: paso_suite(uv, None)))
    else:
        lista += [(f"suite de pruebas (Python {v})", lambda v=v: paso_suite(uv, v)) for v in VERSIONES]
    if di and not rapido:
        lista.append(("tests de tools/di", lambda: paso_di(uv)))
    return lista


def instalar_hook():
    p = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks/pre-push"], cwd=RAIZ, capture_output=True, text=True, env=entorno()
    )
    if p.returncode != 0:
        print("FALLO: no es un repositorio git")
        return 1
    destino = (RAIZ / p.stdout.strip()).resolve()
    if destino.exists() and MARCA_HOOK not in destino.read_text(encoding="utf-8", errors="replace"):
        print(f"FALLO: {destino} ya existe y no lo escribió este script; no se sobrescribe")
        return 1
    destino.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = f'#!/bin/sh\n{MARCA_HOOK}\ncd "$(git rev-parse --show-toplevel)" || exit 1\nexec uv run python tools/comprobar.py --rapido\n'
    destino.write_text(cuerpo, encoding="utf-8", newline="\n")
    destino.chmod(0o755)
    print(f"OK: hook instalado en {destino}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Comprobación local de KBOL")
    ap.add_argument("--rapido", action="store_true", help="la suite una sola vez, con el intérprete del proyecto")
    ap.add_argument("--sin-di", action="store_true", help="sin los tests de tools/di (siempre fuera con --rapido)")
    ap.add_argument("--instalar-hook", action="store_true", help="escribe .git/hooks/pre-push con --rapido")
    args = ap.parse_args(argv)
    if args.instalar_hook:
        return instalar_hook()
    uv = shutil.which("uv")
    if uv is None:
        print("FALLO: no se encuentra `uv` en el PATH")
        return 1
    if args.rapido or args.sin_di:
        print("AVISO: los tests de tools/di no se ejecutan en esta pasada", flush=True)
    for nombre, paso in pasos(uv, args.rapido, di=not args.sin_di):
        print(f"... {nombre}", flush=True)
        try:
            paso()
        except Fallo as e:
            print(f"FALLO: {nombre}: {e}")
            return 1
        print(f"OK: {nombre}", flush=True)
    print("Comprobación local completa. Solo prueba esta máquina.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
