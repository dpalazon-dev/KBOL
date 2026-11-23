"""Executed checks (KB-DPP implementation 1.0, "verify" operation and check results; E7 bounded).

The executor only launches the checks declared in the installation configuration, which is versioned: an id, the
command as a list of arguments, the time limit and the expected exit code. Whoever asks chooses the id; they add no
arguments or paths, and nothing goes through a shell. From the CLI, the installation is read from HEAD and has to be
inside the root and without local changes (`controlled_installation`): what runs is what was integrated, not any file.

"{python}" in the command is the interpreter of the root `.venv` if it exists and, if not, the one running KBOL. In
that second case the environment is external to the root and the result says so: what is installed there as editable
may come from another copy.

The command writes its output to the evidence, .kbol/checks/<task>/<id>-<instant>-<pid>.log, with its SHA-256, and
runs with an environment without KB_GITHUB_TOKEN or GIT_* variables. If it does not finish in time, it is stopped with
all its processes. The result is annotated in the task handoff (origin "kbol"): tested revision and tree fingerprint,
instants, code, duration, evidence and fingerprint of what was declared. It stops being valid if the revision or the
tree changes. If the check changes the tree or the head, does not finish or git does not answer, it is left pending
review: it is not taken as passed.

No isolation or receipts in this version. On Windows, a process that the command leaves alive after finishing is not
stopped.
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

from . import handoff as handoff_mod
from .snapshot import git_environment

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,49}")
FIELDS = {"command", "timeout", "expected_code", "description"}
MAX_TIMEOUT = 3600
QUEUE = 30  # last lines of the output that are returned; the full output stays in the evidence
_BLOCK = 1 << 20


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _one_line(text):
    return "\n" not in text and "\r" not in text


def checks_of(installation):
    """The checks declared in the installation configuration, validated; ValueError if they are not."""
    declared = installation.get("checks", {}) if isinstance(installation, dict) else None
    if not isinstance(declared, dict):
        raise ValueError("checks is an object: id → {command, timeout, expected_code, description}")
    for ident, v in declared.items():
        if not _ID.fullmatch(ident):
            raise ValueError(f"invalid check id: {ident!r} (lowercase letters, digits, hyphen and underscore)")
        if not isinstance(v, dict) or set(v) - FIELDS:
            raise ValueError(f"the check {ident} admits {', '.join(sorted(FIELDS))}")
        command = v.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command):
            raise ValueError(f"the command of {ident} is a non-empty list of arguments")
        if not all(_one_line(a) for a in command):
            raise ValueError(f"the arguments of {ident} are single-line")
        timeout = v.get("timeout")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= MAX_TIMEOUT:
            raise ValueError(f"the timeout of {ident} is an integer number of seconds between 1 and {MAX_TIMEOUT}")
        expected = v.get("expected_code", 0)
        if not isinstance(expected, int) or isinstance(expected, bool):
            raise ValueError(f"the expected code of {ident} is an integer")
        if "description" in v and not (isinstance(v["description"], str) and _one_line(v["description"])):
            raise ValueError(f"the description of {ident} is a single-line text")
    return declared


def controlled_installation(root, path):
    """(installation, provenance) read from HEAD. ValueError if the path is outside the root, is not versioned or has
    local changes: what runs has to be what was integrated, not whatever any file says."""
    root = Path(root).resolve()
    try:
        rel = Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        raise ValueError(f"the installation has to be inside the root: {path}") from None

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=git_environment())

    if git("ls-files", "--error-unmatch", "--", rel).returncode != 0:
        raise ValueError(f"the installation is not versioned: {rel}")
    if git("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        raise ValueError(f"the installation has uncommitted changes: {rel}")
    read_back = git("show", f"HEAD:./{rel}")
    if read_back.returncode != 0:
        raise ValueError(f"the installation could not be read from HEAD: {rel}")
    head = git("rev-parse", "HEAD").stdout.decode().strip()
    return json.loads(read_back.stdout.decode("utf-8")), {"path": rel, "revision": head}


def python_of(root):
    """(interpreter for "{python}", external): the root .venv one if it exists; if not, the one running KBOL."""
    for name in ("Scripts/python.exe", "bin/python"):
        own = Path(root) / ".venv" / name
        if own.exists():
            return str(own), False
    return sys.executable, True


def _environment():
    return {k: v for k, v in os.environ.items() if k.upper() != "KB_GITHUB_TOKEN" and not k.upper().startswith("GIT_")}


def _kill_tree(process):
    """Stops the process and all its descendants."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=10)


def _launch(command, root, timeout, output):
    """(code or None, observation). Without shell or input, with the output (and stderr) in the file `output`."""
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with open(output, "wb") as f:
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=_environment(),
                **group,
            )
        except OSError as exc:
            f.write(str(exc).encode("utf-8"))
            return None, f"did not start: {exc}"
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            return None, f"did not finish in {timeout} s; it was stopped with all its processes"
    if os.name != "nt":  # what the command left alive when it finished
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    return code, None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_BLOCK):
            h.update(chunk)
    return h.hexdigest()


def _queue(path, lines=QUEUE):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 64 * 1024))
        return f.read().decode("utf-8", errors="replace").splitlines()[-lines:]


def run(root, task, installation, check_id, canonical_branch="main", provenance=None):
    """Runs a declared check, saves its evidence and annotates it in the task handoff; returns the result with the
    contract fields and the last lines of the output. `provenance` says where the installation came from (the CLI
    reads it from HEAD with `controlled_installation`)."""
    declared = checks_of(installation)
    if check_id not in declared:
        available = ", ".join(sorted(declared)) or "none"
        raise ValueError(f"check not declared in the installation: {check_id!r} (declared: {available})")
    handoff_mod.handoff_path(root, task)  # validates the task id before running anything
    spec = declared[check_id]
    expected = spec.get("expected_code", 0)
    declaration = {
        "sha256": hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        **(provenance or {"path": None, "revision": None}),
    }
    python, external = python_of(root)
    command = [python if a == "{python}" else a for a in spec["command"]]

    revision = handoff_mod.git_facts(root, canonical_branch).get("head")
    tree_before = handoff_mod.tree_fingerprint(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence = Path(root) / handoff_mod.FOLDER.parent / "checks" / task / f"{check_id}-{stamp}-{os.getpid()}.log"
    evidence.parent.mkdir(parents=True, exist_ok=True)

    started = _now()
    start = time.monotonic()
    code, observation = _launch(command, root, spec["timeout"], evidence)
    duration = round(time.monotonic() - start, 1)
    finished = _now()
    tree_after = handoff_mod.tree_fingerprint(root)
    head_after = handoff_mod.git_facts(root, canonical_branch).get("head")

    observations = [observation] if observation else []
    if tree_before is None or revision is None:
        observations.append("git did not give the tested revision or tree")
    elif head_after != revision:
        observations.append("the git head changed while it ran: it is not known which revision it tested")
    elif tree_after != tree_before:
        observations.append("the check changed the working tree: it is not known which content it tested")
    if code is None:
        did_not_start = observation.startswith("did not start")
        result, contract = "unknown", "not_run" if did_not_start else "requires_review"
    elif observations:
        result, contract = "unknown", "requires_review"
    elif code == expected:
        result, contract = "passed", "passed"
    else:
        result, contract = "failed", "failed"

    evidence_path = evidence.relative_to(root).as_posix()
    fingerprint = _sha256(evidence)
    environment_ref = {"python": python, "external": external, "isolation": "none"}
    annotated = {
        "command": f"{check_id}: {' '.join(spec['command'])}",
        "result": result,
        "origin": "kbol",
        "check_id": check_id,
        "revision": revision,
        "tree": tree_before,
        "started_at": started,
        "at": finished,
        "code": code,
        "expected_code": expected,
        "duration_s": duration,
        "evidence": {"path": evidence_path, "sha256": fingerprint},
        "declaration": declaration,
        "environment": environment_ref,
    }
    if observations:
        annotated["reason"] = "; ".join(observations)
    handoff_mod.annotate_check(root, task, annotated, canonical_branch)

    return {
        "check_id": check_id,
        "tested_revision": revision,
        "tested_tree": tree_before,
        "declaration": declaration,
        "environment_ref": environment_ref,
        "started_at": started,
        "finished_at": finished,
        "result": contract,
        "handoff_result": result,
        "code": code,
        "expected_code": expected,
        "duration_s": duration,
        "evidence_ref": {"path": evidence_path, "sha256": fingerprint},
        "observations": observations,
        "final_output": _queue(evidence),
    }
