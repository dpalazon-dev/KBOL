"""Commands for the hooks of an installation (`kbol session`): the knowledge logic that each installation repeated in
its hooks, behind a single command with three events.

The installation adapter reads the event from its harness, finds the binary and calls `kbol session` with the `cwd`
of the event. This command resolves the rest: it goes up to the root of the working tree (the worktree's, if it is
one), reads `records_folder`, `scope`, `budget` and `canonical_branch` from the installation configuration, and derives
the task from the branch if it is not given.

- `start`: the context package of the task and the drift, with a single load of the records. The result is saved in
  `.kbol/session/start-<task>.json` with the fingerprint of what decides it and is reused while that does not change.
  It is the only command that reads the clock: without `valid_at` it uses the current instant and declares it.
- `stop`: validates as proposals the records of the folders that have uncommitted changes; with `paths`, only those
  (what the session edited). A rejected record is a failure.
- `commit`: the drift of the git index, what is about to go into the commit. It warns, it does not block.

The start fingerprint gathers the version and files of KBOL, the configuration, the task and its handoff, the head,
the canonical branch, the working tree (`handoff.tree_fingerprint`: status, diff against the head and content of
untracked files) and the cut: the given instant or, if none is given, the day. Limits: it does not see files ignored
by git, and with the cut per day a validity that starts or ends at another hour of the same day is not reflected
until the next one. A failure is not saved: the next start tries again.
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
from . import handoff as rv
from .context import context, present
from .core import FormatError, parse
from .fingerprints import drift
from .migration import format_of
from .model import TYPES
from .schema import validate
from .snapshot import git_environment, load
from .timeutil import is_instant

EVENTS = ("start", "stop", "commit")
FOLDER = rv.FOLDER.parent / "session"
MAX_DRIFT = 10
MAX_COMMITS = 10
MAX_LINES = 30


def _git(root, *args):
    p = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=git_environment(),
    )
    return p.stdout if p.returncode == 0 else None


def root_of(path):
    """The root of the working tree that contains `path`: the worktree's, if it is one. ValueError if there is no git."""
    output = _git(path, "rev-parse", "--show-toplevel")
    if not output or not output.strip():
        raise ValueError(f"{path} is not in a git working tree")
    return Path(output.strip())


def task_of_branch(root):
    """The task id that corresponds to the branch: anything other than a letter, digit, dot, hyphen or underscore
    becomes a hyphen, it starts with a letter or digit and has at most 100 characters; `no-branch` with a detached head.
    Two branches that differ only in those characters (`feat/x` and `feat-x`) share task and handoff."""
    branch = re.sub(r"[^A-Za-z0-9._-]", "-", (_git(root, "branch", "--show-current") or "").strip())
    return re.sub(r"^[^A-Za-z0-9]+", "", branch)[:100].rstrip("-.") or "no-branch"


def configuration(root, installation, event):
    """(configuration, bytes read) of the installation; a relative path is relative to the root. ValueError if it lacks
    what the event needs."""
    path = Path(installation)
    raw = (path if path.is_absolute() else Path(root) / path).read_bytes()
    conf = json.loads(raw.decode("utf-8"))
    if not isinstance(conf, dict):
        raise ValueError("the installation configuration is an object")
    folders = conf.get("records_folder")
    if not isinstance(folders, str) or not all(c.strip() for c in folders.split(",")):
        raise ValueError("records_folder is a text with the records folders, separated by commas")
    if not isinstance(conf.get("canonical_branch", "main"), str) or not conf.get("canonical_branch", "main"):
        raise ValueError("canonical_branch is the name of a branch")
    if event == "start":
        if not isinstance(conf.get("scope"), str) or not conf["scope"]:
            raise ValueError("scope is the scope of the context package, as text")
        budget = conf.get("budget", 30)
        if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
            raise ValueError("budget is a number of elements, 0 or more")
    format_of(conf)  # a badly declared legacy format fails here, before reading anything
    return conf, raw


def _folders(conf):
    folders = [c.strip() for c in conf["records_folder"].split(",")]
    return folders if len(folders) > 1 else folders[0]


def _mark(path):
    try:
        state = Path(path).stat()
    except OSError:
        return "missing"
    return f"{state.st_size}:{state.st_mtime_ns}"


def start_fingerprint(root, raw, conf, task, cut):
    """Fingerprint of what decides the result of `start`, or None if git does not answer."""
    canonical = conf.get("canonical_branch", "main")
    head = _git(root, "rev-parse", "HEAD")
    tree = rv.tree_fingerprint(root)
    if head is None or tree is None:
        return None
    parts = [
        __version__,
        *sorted(f"{p.name}:{_mark(p)}" for p in Path(__file__).parent.glob("*.py")),
        hashlib.sha256(raw).hexdigest(),
        task,
        (_git(root, "branch", "--show-current") or "").strip(),
        _mark(rv.handoff_path(root, task)),
        cut,
        head.strip(),
        (_git(root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"refs/heads/{canonical}") or "").strip(),
        tree,
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _saved(path, fingerprint):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("fingerprint") != fingerprint:
        return None
    computed = data.get("computed")
    try:  # what `start` is going to read from it: one with another shape (another version, hand-edited) is not reused
        complete = (
            isinstance(computed["valid_at"], str)
            and isinstance(computed["package"]["warnings"], list)
            and isinstance(computed["package"]["coverage"]["not_evaluated"], list)
            and isinstance(computed["package"]["handoff"]["git"], dict)
            and isinstance(computed["drift"]["alerts"], list)
            and all(isinstance(a, dict) and {"id", "path", "reason"} <= set(a) for a in computed["drift"]["alerts"])
            and {"state", "reason", "revision"} <= set(computed["package"])
            and {"state", "read", "invalid"} <= set(computed["package"]["coverage"])
            and "checked" in computed["drift"]
        )
    except (KeyError, TypeError):
        return None
    return computed if complete else None


def _drift_line(alerts, branch):
    differing = [a["id"] for a in alerts if a["reason"] == "different"]
    no_fingerprint = sum(1 for a in alerts if a["reason"] == "no_fingerprint")
    parts = []
    if differing:
        rest = f" and {len(differing) - MAX_DRIFT} more" if len(differing) > MAX_DRIFT else ""
        parts.append(f"{len(differing)} differ from what was integrated ({', '.join(differing[:MAX_DRIFT])}{rest})")
    if no_fingerprint:
        parts.append(f"{no_fingerprint} without fingerprint")
    if not parts:
        return None
    return (
        f"KBOL drift (kbol drift): {'; '.join(parts)}. They are compared with their version in {branch} and proposed "
        "through integration; it does not block."
    )


def _work_in_git(git):
    """What the task had in hand according to git, for a session that has just compacted its context."""
    if not git.get("available"):
        return ["Task work in git: unknown (git does not answer)."]
    lines = [f"Task work in git (branch {git['branch']}):"]
    own = git.get("own_commits")
    if own:
        total = len(own) + git.get("own_commits_omitted", 0)
        lines.append(f"- Own commits ({total}): " + "; ".join(own[:MAX_COMMITS]))
    local = git.get("local_changes") or []
    if local:
        total = len(local) + git.get("local_changes_omitted", 0)
        lines.append(f"- Uncommitted changes ({total}):")
        lines += [f"  {path}" for path in local]
    if len(lines) == 1:
        lines.append("- No own commits and no uncommitted changes.")
    return lines


def start(path, installation, task=None, valid_at=None, origin=None):
    """Context package and drift of the task, reusing what was saved if its fingerprint still holds."""
    if valid_at is not None and not is_instant(valid_at):
        raise ValueError("valid_at is not an ISO 8601 instant with zone")
    root = root_of(path)
    conf, raw = configuration(root, installation, "start")
    task = task or task_of_branch(root)
    rv.handoff_path(root, task)  # validates the task id before using it in a file name
    saved_at = root / FOLDER / f"start-{task}.json"
    branch = conf.get("canonical_branch", "main")
    cut = valid_at or datetime.now(timezone.utc).date().isoformat()
    fingerprint = start_fingerprint(root, raw, conf, task, cut)
    computed = _saved(saved_at, fingerprint) if fingerprint else None
    reused = computed is not None
    if computed is None:
        instant = valid_at or rv._now()
        folder = _folders(conf)
        loaded = load(root, folder, None, mode="proposal", legacy=True, format=format_of(conf))
        package = context(
            root,
            task=task,
            goal=None,
            scope=conf["scope"],
            folder=folder,
            installation=conf,
            valid_at=instant,
            budget=conf.get("budget", 30),
            loaded=loaded,
        )
        res = drift(root, folder, branch=branch, loaded=loaded)
        computed = {
            "valid_at": instant,
            "package": package,
            "drift": {"checked": res["checked"], "alerts": res["alerts"]},
        }
        # It is saved only if what decides the result did not change while it was computed; and not being able to save
        # it (another start of the same task at the same time, a file open on Windows) does not spoil a computed result.
        if fingerprint and start_fingerprint(root, raw, conf, task, cut) == fingerprint:
            with contextlib.suppress(OSError):
                rv._write(saved_at, {"fingerprint": fingerprint, "computed": computed})
    package, drift_res = computed["package"], computed["drift"]
    warnings = list(package["warnings"])
    state, reasons = package["state"], [package["reason"]] if package["reason"] else []
    if not drift_res["checked"] and state != "blocked":
        state = "partial"
        reasons.append("no record with history checked for drift")
    warnings += [
        f"{a['id']} ({a['path']}): {'differs from what was integrated' if a['reason'] == 'different' else 'without fingerprint'}"
        for a in drift_res["alerts"]
    ]
    lines = [present(package)]
    line = _drift_line(drift_res["alerts"], branch)
    if line:
        lines.append(line)
    if not drift_res["checked"]:
        lines.append("KBOL drift: no record with history was checked.")
    if origin == "compact":
        lines += _work_in_git(package["handoff"]["git"])
    result = {
        "state": state,
        "event": "start",
        "task": task,
        "reused": reused,
        "fingerprint": fingerprint,
        "package": {k: v for k, v in package.items() if k not in ("warnings", "coverage")},
        "drift": drift_res,
    }
    if reasons:
        result["reason"] = "; ".join(reasons)
    return {
        "result": result,
        "code": {"completed": 0, "blocked": 2}.get(state, 3),
        "warnings": warnings,
        "text": "\n".join(lines),
        "revision": package["revision"],
        "valid_at": computed["valid_at"],
        "scope": f"{root.as_posix()}:{conf['records_folder']}",
        "not_evaluated": [*package["coverage"]["not_evaluated"], "records without history", "who made the edit"],
        "coverage": {k: package["coverage"][k] for k in ("state", "read", "invalid")},
    }


def _uncommitted(root):
    """Paths, relative to the repository root, with uncommitted changes and that still exist."""
    output = _git(root, "status", "--porcelain", "-z", "--untracked-files=all")
    if output is None:
        raise ValueError("git did not give the status of the working tree")
    paths, parts, i = set(), output.split("\0"), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        state, name = entry[:2], entry[3:]
        if state[0] in "RC":  # renamed or copied: the source path comes in the next field
            i += 1
        if "D" not in state:
            paths.add(name)
    return paths


def _relative(root, path):
    """The path, relative to the root and with "/" slashes; a relative one is relative to the root, not to the process
    directory. As is if it is outside."""
    text = str(path).replace("\\", "/")
    if re.match(r"^/[A-Za-z]/", text) and re.match(r"^[A-Za-z]:", str(root)):  # Git Bash: /c/Users/… → c:/Users/…
        text = f"{text[1]}:{text[2:]}"
    if Path(text).is_absolute():
        try:
            return Path(text).resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            return text
    return posixpath.normpath(text)


def _in_folders(path, folders):
    return any(c == "." or path.startswith(c + "/") for c in folders)


def stop(path, installation, paths=None):
    """Validates as proposals the records of the folders with uncommitted changes; with `paths`, only those."""
    root = root_of(path)
    conf, _ = configuration(root, installation, "stop")
    folders = [posixpath.normpath(c.strip().replace("\\", "/")) for c in conf["records_folder"].split(",")]
    candidates = {
        r for r in _uncommitted(root) if r.endswith(".md") and Path(r).name != "index.md" and _in_folders(r, folders)
    }
    if paths is not None:
        candidates &= {_relative(root, r) for r in paths}
    rejected, no_records, examined = [], [], 0
    for name in sorted(candidates):
        try:
            meta, body = parse((root / name).read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, FormatError) as exc:
            # As in loading: an unreadable file in a records folder could be a record.
            examined += 1
            rejected.append({"path": name, "errors": [{"path": "", "message": f"could not be read: {exc}"}]})
            continue
        if meta.get("type") not in TYPES:
            no_records.append(name)
            continue
        examined += 1
        errors_ = [h for h in validate(meta, body, mode="proposal") if h["severity"] == "error"]
        if errors_:
            rejected.append({"path": name, "errors": errors_})
    warnings = []
    if rejected:
        state, code = "failed", 1
    elif not examined:
        state, code = "partial", 3
        warnings.append("no record with uncommitted changes to validate")
    else:
        state, code = "completed", 0
    lines = [f"{r['path']}: {e['path']}: {e['message']}" for r in rejected for e in r["errors"]]
    text = ""
    if lines:
        rest = [f"… ({len(lines) - MAX_LINES} more lines)"] if len(lines) > MAX_LINES else []
        text = "\n".join(["KBOL rejects, as proposals, records with uncommitted changes:", *lines[:MAX_LINES], *rest])
    result = {
        "state": state,
        "event": "stop",
        "examined": examined,
        "rejected": rejected,
        "no_records": no_records,
    }
    if rejected:
        result["code"] = "INVALID_SCHEMA"
        result["reason"] = f"{len(rejected)} record(s) do not validate as a proposal"
    return {
        "result": result,
        "code": code,
        "warnings": warnings,
        "text": text,
        "revision": None,
        "valid_at": None,
        "scope": f"{root.as_posix()}:{conf['records_folder']}",
        "not_evaluated": ["references between records", "authority", "validity", "records already committed"],
        "coverage": {},
    }


def commit(path, installation):
    """Drift of what is about to go into the commit (the git index). It warns and does not block."""
    root = root_of(path)
    conf, _ = configuration(root, installation, "commit")
    branch = conf.get("canonical_branch", "main")
    res = drift(root, _folders(conf), staged=True, branch=branch, format=format_of(conf))
    coverage = res["coverage"]
    alerts = [
        f"{a['id']} ({a['path']}): {'differs from what was integrated' if a['reason'] == 'different' else 'without fingerprint'}"
        for a in res["alerts"]
    ]
    result = {"event": "commit", "checked": res["checked"], "alerts": res["alerts"]}
    if coverage["state"] == "blocked":
        errors_ = [h for h in coverage["findings"] if h["severity"] == "error"]
        result = {
            "state": "blocked",
            "code": errors_[0]["code"],
            "reason": "inconsistent snapshot",
            **result,
            "findings": errors_,
        }
        code = 2
    elif not res["checked"] or coverage["state"] != "complete":
        result = {"state": "partial", **result}
        code = 3
        if not res["checked"]:
            alerts.append("no record with history checked: are the folders right?")
    else:
        result = {"state": "completed", **result}
        code = 0
    lines = [
        f"warning: {a['id']} ({a['path']}) differs from what was integrated in {branch}: propose it through integration"
        for a in res["alerts"]
        if a["reason"] == "different"
    ]
    return {
        "result": result,
        "code": code,
        "warnings": coverage["warnings"] + alerts,
        "text": "\n".join(lines),
        "revision": None,
        "valid_at": None,
        "scope": f"{root.as_posix()}:{conf['records_folder']}",
        "not_evaluated": ["records without history", "who made the edit"],
        "coverage": {k: coverage[k] for k in ("read", "invalid")},
    }


def run(event, path, installation, *, task=None, valid_at=None, origin=None, paths=None):
    """The result of the event: `result`, exit `code`, `warnings`, `text` to inject and what the envelope declares
    (`revision`, `valid_at`, `scope`, `not_evaluated`, `coverage`)."""
    if event == "start":
        return start(path, installation, task=task, valid_at=valid_at, origin=origin)
    if event == "stop":
        return stop(path, installation, paths=paths)
    if event == "commit":
        return commit(path, installation)
    raise ValueError(f"unknown event: {event!r} (one of {', '.join(EVENTS)})")
