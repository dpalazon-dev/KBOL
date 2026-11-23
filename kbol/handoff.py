"""Per-task handoff (KB-DPP implementation 1.0, "Minimum handoff", and ESC-05 "Continuity without invented authorization").

The handoff is the state of a task kept apart from the conversation: goal and authorization reference, scope and
limits, checks with their result and revision, blocks, questions and next step with its basis. The agent saves it
(`save`) in `.kbol/handoffs/<task>.json` under the root, a local state that is neither knowledge nor versioned. The
first save records the base of the task in git, so a branch with no work can later be told apart from one already
integrated.

Executed checks are annotated by `kbol verify` (`annotate_check`, verify module), with the fingerprint of the tested
working tree; `save` keeps them even if the session does not repeat them, and does not let the session write them.
A new run of the same check replaces the prevus one, which moves to the history without its full output: a failure
followed by a success stays written. The history keeps the last `HISTORY`.

`handoff` combines it with git facts (branch, base, own and foreign commits, local changes, integration) and declares
in `not_recorded` what was never saved: it does not infer it. The authorization is marked as declared by the session
and not verified: it is not a portable authorization. Building it only reads git, without taking index locks; it does
not run the checks, which are recorded as they were done. Texts do not admit line breaks: a handoff cannot be passed
off as constraints.
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

from .snapshot import git_environment
from .timeutil import instant, is_instant

FOLDER = Path(".kbol") / "handoffs"
_TASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
# Names Windows reserves for devices: a file with them cannot be created.
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
LOCK_WAIT = 30
HISTORY = 200
STALE_LOCK = 120
RESULTS = ("passed", "failed", "not_run", "unknown")
FIELDS = ("goal", "authorization", "checks", "blocks", "questions", "next_step")
# What the minimum handoff needs and, if missing, is declared.
MINIMUMS = ("goal", "authorization", "checks", "next_step")
LIMIT = 20


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _path(root, task):
    if not isinstance(task, str) or not _TASK.fullmatch(task):
        raise ValueError(f"invalid task id: {task!r} (letters, digits, dot, hyphen and underscore)")
    if task.endswith(".") or task.split(".")[0].upper() in _RESERVED:
        raise ValueError(f"invalid task id on Windows: {task!r} (trailing dot or reserved name)")
    return Path(root) / FOLDER / f"{task}.json"


def handoff_path(root, task):
    """The path of the task handoff; ValueError if the id is not safe."""
    return _path(root, task)


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{field} is a single-line text")


def _texts(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} is a list of texts")
    for v in value:
        _text(v, field)


def _validate(data):
    if not isinstance(data, dict):
        raise ValueError("the handoff is an object")
    extra = sorted(set(data) - set(FIELDS))
    if extra:
        raise ValueError(f"fields not admitted in the handoff: {', '.join(extra)}")
    if "goal" in data:
        _text(data["goal"], "goal")
    aut = data.get("authorization")
    if aut is not None:
        if not isinstance(aut, dict) or set(aut) - {"reference", "scope", "limits"}:
            raise ValueError("authorization admits reference, scope and limits")
        for field in ("reference", "scope"):
            if field in aut:
                _text(aut[field], f"authorization.{field}")
        if "limits" in aut:
            _texts(aut["limits"], "authorization.limits")
    for v in data.get("checks") or []:
        if not isinstance(v, dict) or set(v) - {"command", "result", "revision", "at", "reason"}:
            raise ValueError(
                "a declared check admits command, result, revision, at and reason; executed ones are annotated by "
                "kbol verify"
            )
        _text(v.get("command"), "checks.command")
        if v.get("result") not in RESULTS:
            raise ValueError(f"result of a check: one of {', '.join(RESULTS)}")
        if v["result"] in ("passed", "failed"):
            # A result without the revision and instant at which it was obtained cannot be checked.
            _text(v.get("revision"), "checks.revision")
            if not is_instant(v.get("at")):
                raise ValueError("checks.at is the instant of the result, ISO 8601 with zone")
        if "reason" in v:
            _text(v["reason"], "checks.reason")
    for field in ("blocks", "questions"):
        if field in data:
            _texts(data[field], field)
    step = data.get("next_step")
    if step is not None:
        if not isinstance(step, dict) or set(step) - {"action", "basis"}:
            raise ValueError("next_step admits action and basis")
        _text(step.get("action"), "next_step.action")
        if "basis" in step:
            _text(step["basis"], "next_step.basis")


def _read(path, task):
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(saved, dict):
        raise ValueError(f"{path} is not a handoff")
    if saved.get("task") != task:
        # On Windows two ids that differ only in case share a file: the one of another task is not handed over.
        raise ValueError(f"{path} holds the handoff of {saved.get('task')!r}, not of {task!r}")
    return saved


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


@contextmanager
def _lock(path):
    """Mutual exclusion among those who read, modify and write the handoff (save and annotate_check)."""
    lockfile = path.with_name(f"{path.name}.lock")
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    limit = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:  # that of a process that died without releasing it
                if time.time() - lockfile.stat().st_mtime > STALE_LOCK:
                    lockfile.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > limit:
                raise ValueError(f"the handoff is locked by another process: {lockfile}") from None
            time.sleep(0.05)
    try:
        os.close(fd)
        yield
    finally:
        lockfile.unlink(missing_ok=True)


def _executed(saved):
    return [v for v in saved.get("checks") or [] if isinstance(v, dict) and v.get("origin") == "kbol"]


def save(root, task, data, canonical_branch="main"):
    """Saves the task handoff, validated, atomically; returns its path. It replaces the prevus one and keeps the
    base of the task in git recorded on the first save and the checks that KBOL executed."""
    path = _path(root, task)
    _validate(data)
    with _lock(path):
        prev = _read(path, task) or {}
        base = prev.get("git_base") or git_facts(root, canonical_branch).get("base")
        content = {"task": task, **data, "git_base": base, "updated_at": _now()}
        if prev.get("check_history"):
            content["check_history"] = prev["check_history"]
        executed = _executed(prev)
        if executed:
            content["checks"] = [*(data.get("checks") or []), *executed]
        return _write(path, content)


def annotate_check(root, task, check_, canonical_branch="main"):
    """Annotates in the handoff a check executed by KBOL and replaces the previous one with the same id, whose evidence
    it deletes. Creates the handoff if it did not exist, with the base of the task in git."""
    path = _path(root, task)
    with _lock(path):
        prev = _read(path, task) or {"task": task, "git_base": git_facts(root, canonical_branch).get("base")}
        others, replaced = [], []
        for v in prev.get("checks") or []:
            same = v.get("origin") == "kbol" and v.get("check_id") == check_["check_id"]
            (replaced if same else others).append(v)
        history = [*(prev.get("check_history") or []), *(_to_history(v) for v in replaced)]
        content = {**prev, "checks": [*others, check_], "updated_at": _now()}
        if history:
            content["check_history"] = history[-HISTORY:]
        written = _write(path, content)
    for v in replaced:
        _delete_evidence(root, v, keep=check_["evidence"]["path"])
    return written


def _to_history(check_):
    """The replaced check, without its full output, which is deleted: where it was and its fingerprint remain."""
    evidence = check_.get("evidence")
    if isinstance(evidence, dict):
        evidence = {**evidence, "deleted": True}
    return {**check_, "evidence": evidence}


def _delete_evidence(root, check_, keep):
    """Deletes the evidence of a replaced check, only if it is in .kbol/checks/."""
    path = (check_.get("evidence") or {}).get("path")
    if not isinstance(path, str) or path == keep:
        return
    folder = (Path(root) / FOLDER.parent / "checks").resolve()
    archive = (Path(root) / path).resolve()
    if folder in archive.parents:
        archive.unlink(missing_ok=True)


def _git(root, *args):
    p = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=git_environment(),
    )
    # Only the end: the first line of `status --porcelain` may start with a space that is part of the format.
    return p.stdout.rstrip("\r\n") if p.returncode == 0 else None


def tree_fingerprint(root):
    """SHA-256 of the uncommitted changes of the root (status, diff against HEAD and content of untracked files),
    without KBOL local state; None if git does not answer. Like the head: if it changes, what was checked is no longer
    this."""

    def git(*args):
        p = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args], capture_output=True, env=git_environment()
        )
        return p.stdout if p.returncode == 0 else None

    outside = ":(exclude,glob)**/.kbol/**"
    state = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".", outside)
    diffs = git("diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv", "--", ".", outside)
    new = git("ls-files", "--others", "--exclude-standard", "-z", "--", ".", outside)
    if state is None or diffs is None or new is None:
        return None
    h = hashlib.sha256()
    for part in (state, diffs):
        h.update(len(part).to_bytes(8, "big") + part)
    for name in sorted(n for n in new.split(b"\0") if n):
        h.update(
            len(name).to_bytes(8, "big") + name + _fingerprint_of(Path(root) / name.decode("utf-8", "surrogateescape"))
        )
    return h.hexdigest()


def _fingerprint_of(path):
    """SHA-256 of the content of a file, read in blocks; empty if it cannot be read (nested repository)."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
    except OSError:
        pass
    return h.digest()


def _lines(text):
    return [line for line in (text or "").splitlines() if line.strip()]


def _is_kbol_state(path):
    return ".kbol" in Path(path).parts


def git_facts(root, canonical_branch, recorded_base=None):
    """Branch, head, task base, own and foreign commits, local changes and integration. `None` = could not be
    computed, which is not the same as "there are none"."""
    head = _git(root, "rev-parse", "HEAD")
    if head is None:
        return {"available": False, "alerts": ["git gives no head: repository without commits or without git"]}
    canonical = _git(root, "rev-parse", "--verify", "--end-of-options", f"refs/heads/{canonical_branch}")
    alerts = [] if canonical else [f"the canonical branch {canonical_branch} does not exist in this clone"]
    base = recorded_base or (_git(root, "merge-base", "HEAD", canonical) if canonical else None)
    # Status paths relative to the requested root (-- .), without KBOL local state, which is not pending work.
    state = _lines(_git(root, "-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "--", "."))
    facts = {
        "available": True,
        "branch": _git(root, "branch", "--show-current") or "(detached HEAD)",
        "head": head,
        "canonical_branch": canonical_branch,
        "base": base,
        "own_commits": _lines(_git(root, "log", "--format=%s", f"{base}..HEAD")) if base else None,
        "foreign": _lines(_git(root, "log", "--format=%s", f"{base}..{canonical}")) if base and canonical else None,
        "local_changes": [line[3:] for line in state if not _is_kbol_state(line[3:])],
        "on_canonical": bool(canonical) and _git(root, "merge-base", "--is-ancestor", "HEAD", canonical) is not None,
        "alerts": alerts,
    }
    for field in ("own_commits", "foreign", "local_changes"):
        if facts[field] is not None and len(facts[field]) > LIMIT:
            facts[f"{field}_omitted"] = len(facts[field]) - LIMIT
            facts[field] = facts[field][:LIMIT]
    return facts


def _delivery(git):
    """`local`, `integrated`, `no_work` or `unknown`. Never "integrated" without own work to integrate."""
    if not git.get("available"):
        return "unknown"
    if git["local_changes"]:
        return "local"
    if git["own_commits"] is None:
        return "unknown"
    if not git["own_commits"]:
        return "no_work"
    return "integrated" if git["on_canonical"] else "local"


def _check(v, git, tree):
    """The check with `outdated`: True if the revision or, for executed ones, the working tree changed; "unknown" if it
    cannot be known."""
    output = dict(v)
    if not v.get("revision") or not git.get("available"):
        output["outdated"] = "unknown"
    elif v["revision"] != git["head"]:
        output["outdated"] = True
    elif v.get("origin") == "kbol":
        current = tree()
        output["outdated"] = "unknown" if current is None or not v.get("tree") else v["tree"] != current
    else:
        output["outdated"] = False
    if is_instant(v.get("at")):
        seconds = (datetime.now(timezone.utc) - instant(v["at"])).total_seconds()
        output["age_days"] = round(seconds / 86400, 1)
    return output


def handoff(root, task, canonical_branch="main"):
    """The task handoff: what was saved, the git facts and what is not recorded. Read only."""
    saved = _read(_path(root, task), task)
    state = "no_handoff" if saved is None else "saved"
    saved = saved or {}
    git = git_facts(root, canonical_branch, saved.get("git_base"))
    computed = []

    def tree():  # only if some executed check needs it, and only once
        if not computed:
            computed.append(tree_fingerprint(root))
        return computed[0]

    aut = saved.get("authorization")
    step = saved.get("next_step")
    not_recorded = [c for c in MINIMUMS if not saved.get(c)]
    if aut and not aut.get("reference"):
        not_recorded.append("authorization.reference")
    if step and not step.get("basis"):
        not_recorded.append("next_step.basis")
    return {
        "task": task,
        "state": state,
        "updated_at": saved.get("updated_at"),
        "goal": saved.get("goal"),
        # What the session says it was authorized to do: not verified and cannot be invoked as authorization.
        "authorization": {**aut, "declared": True, "verified": False} if aut else None,
        "checks": [_check(v, git, tree) for v in saved.get("checks") or []],
        "check_history": saved.get("check_history") or [],
        "blocks": saved.get("blocks") or [],
        "questions": saved.get("questions") or [],
        "next_step": step,
        "git": git,
        "delivery_state": _delivery(git),
        "not_recorded": not_recorded,
    }
