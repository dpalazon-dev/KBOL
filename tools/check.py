"""Single local check of KBOL, with the standard library only.

Usage: `uv run python tools/check.py [--quick] [--no-di] [--install-hook]`. Runs in order and stops at the first failure:

1. static analysis (`ruff` 0.17.4) over `kbol`, `tests` and this script;
2. the test suite on Python 3.10 and 3.14, each in an isolated environment (`uv run --isolated`) so as not to touch
   the project's `.venv`; with `--quick`, once only with the project's interpreter;
3. the tests of `tools/di`, in their own uv project (`tools/di/pyproject.toml`, with Docling), in a separate pass;
   they do not run with `--quick` or `--no-di`, and the output says so.

`--install-hook` writes `.git/hooks/pre-push`, which runs this script with `--quick`. It does not overwrite a hook
this script did not write. The static analysis of `tools/di` is outside the check.

Limits. It only tests the local machine: a green result here proves
nothing on another machine, another operating system or other dependency versions. Nothing forces anyone to run it:
if the hook is not installed, or whoever pushes skips the hooks, the code arrives unchecked. Child processes receive
`core.fsmonitor=false` through the environment (`GIT_CONFIG_*`), without touching the global configuration; `kbol`
filters the `GIT_*` variables in its own git processes, so that protection only reaches the commands the tests launch
directly.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUFF = "ruff@0.17.4"
VERSIONS = ("3.10", "3.14")
HOOK_MARK = "# Written by tools/check.py --install-hook"


# Variables that tie a process to its interpreter (`uv run`) or to a repository (git, when running a hook). Inherited,
# the child's Python 3.10 would load the parent's 3.14 library, and the tests' git would act on this repository.
_PARENT_ONLY = ("PYTHONHOME", "UV_INTERNAL__PYTHONHOME", "VIRTUAL_ENV", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")


def environment():
    """Environment of the children: the current one, without what belongs only to the parent, plus
    `core.fsmonitor=false`.

    With fsmonitor active, `git add` can hang in the suite.
    """
    env = {k: v for k, v in os.environ.items() if k not in _PARENT_ONLY}
    n = int(env.get("GIT_CONFIG_COUNT") or 0)
    env[f"GIT_CONFIG_KEY_{n}"] = "core.fsmonitor"
    env[f"GIT_CONFIG_VALUE_{n}"] = "false"
    env["GIT_CONFIG_COUNT"] = str(n + 1)
    return env


def run(command, cwd=ROOT, **kw):
    return subprocess.run(command, cwd=cwd, env=environment(), **kw)


class Failure(Exception):
    pass


def ruff_step(uv):
    command = [uv, "tool", "run", RUFF, "check", "kbol", "tests", "tools/check.py", "tools/calibration"]
    p = run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise Failure("ruff found problems:\n" + (p.stdout + p.stderr).strip())


def suite_step(uv, version):
    if version is None:
        command = [uv, "run", "python", "-m", "pytest", "-c", "pyproject.toml", "-q", "tests"]
    else:
        command = [uv, "run", "--isolated", "--python", version, "python", "-m", "pytest"]
        command += ["-c", "pyproject.toml", "-q", "tests"]
    p = run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
        raise Failure(f"the suite fails (code {p.returncode}):\n{tail}")


def di_step(uv):
    command = [uv, "run", "--project", ".", "python", "-m", "pytest", "-q"]
    p = run(command, cwd=ROOT / "tools" / "di", capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
        raise Failure(f"the tools/di tests fail (code {p.returncode}):\n{tail}")


def steps(uv, quick, di=True):
    list_ = [("static analysis (ruff)", lambda: ruff_step(uv))]
    if quick:
        list_.append(("test suite (project interpreter)", lambda: suite_step(uv, None)))
    else:
        list_ += [(f"test suite (Python {v})", lambda v=v: suite_step(uv, v)) for v in VERSIONS]
    if di and not quick:
        list_.append(("tools/di tests", lambda: di_step(uv)))
    return list_


def install_hook():
    p = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks/pre-push"], cwd=ROOT, capture_output=True, text=True, env=environment()
    )
    if p.returncode != 0:
        print("FAILED: not a git repository")
        return 1
    target = (ROOT / p.stdout.strip()).resolve()
    if target.exists() and HOOK_MARK not in target.read_text(encoding="utf-8", errors="replace"):
        print(f"FAILED: {target} already exists and this script did not write it; it is not overwritten")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    body = f'#!/bin/sh\n{HOOK_MARK}\ncd "$(git rev-parse --show-toplevel)" || exit 1\nexec uv run python tools/check.py --quick\n'
    target.write_text(body, encoding="utf-8", newline="\n")
    target.chmod(0o755)
    print(f"OK: hook installed at {target}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Local check of KBOL")
    ap.add_argument("--quick", action="store_true", help="the suite once only, with the project's interpreter")
    ap.add_argument("--no-di", action="store_true", help="without the tools/di tests (always left out with --quick)")
    ap.add_argument("--install-hook", action="store_true", help="writes .git/hooks/pre-push with --quick")
    args = ap.parse_args(argv)
    if args.install_hook:
        return install_hook()
    uv = shutil.which("uv")
    if uv is None:
        print("FAILED: `uv` not found in PATH")
        return 1
    if args.quick or args.no_di:
        print("WARNING: the tools/di tests are not run in this pass", flush=True)
    for name, step in steps(uv, args.quick, di=not args.no_di):
        print(f"... {name}", flush=True)
        try:
            step()
        except Failure as e:
            print(f"FAILED: {name}: {e}")
            return 1
        print(f"OK: {name}", flush=True)
    print("Local check complete. It only tests this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
