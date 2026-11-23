"""Propose from the integrator's clone (`kbol propose`): from some files of the working tree to the canonical branch.

The integrator does not write to a checked-out branch, so each installation works on a `--bare` clone of its remote
(the integrator's clone), in its local state: `$KBOL_STATE/<repository>/integrator.git`, with the receipts next to it.
This command walks the whole way: it fetches the canonical branch, writes the proposal as a commit on top of it with
git plumbing (the given files and, if there are effects or imports, their request), passes it through the gate
(`integrate.integrate`, unchanged), runs the after steps the installation declares and, if asked, pushes.

How far it goes is decided by `until`. `dry_run` (the default) integrates on a temporary branch of the clone, with
separate receipts, and deletes it: the canonical branch does not change. `integrate` writes the canonical branch of the
clone and does not push. `push` also runs `git push` without forcing.

The approval is not assembled here: the command receives the declared approvals already given, with the digests that
were shown to the person, and the gate checks that they are those of what is integrated. If the gate asks for an
approval that was not given, the dry run returns the approval package (`kbol.package`), with the digests and the
skeleton, and ends `pending_approval`. There is no default quote, session nor identity.

What belongs to the installation goes in its configuration, block `integration`: `remote`, `repository` (the name of
its local state), `approval` (`all` or `decisive`), `after_integrate` (ids of `checks` that run on what was integrated
before pushing), `views` (globs of what those steps may regenerate, which goes in a commit of its own) and `author` (of
the proposal and view commits). The branch and the folders are `canonical_branch` and `records_folder`.

The after steps run in a temporary checkout of what was integrated, without a shell, with the runner of `verify` and
without isolation. They may only change declared views; inside a records folder, only `index.md`, which is what the
record loading skips. If a step fails or changes something else, nothing is pushed. Outside the dry run, what was
already integrated then stays in the clone without being pushed: dry-run first.
"""

import json
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .bootstrap import _BOOTSTRAP_IDENTITY
from .declared import MECHANISM, DeclaredVerifier
from .handoff import _RESERVED
from .integrate import _BRANCH, ACTOR, MODES, Lock, _check_operation, _Git, _safe_folder, integrate
from .integrate import _IDENTITY as _INTEGRATOR_IDENTITY
from .package import approval_package
from .snapshot import folders_of, git_environment
from .verify import _launch, _queue, checks_of, python_of

UNTIL = ("dry_run", "integrate", "push")
FIELDS = frozenset({"remote", "repository", "approval", "after_integrate", "views", "author"})
AUTHOR = {"name": "local-proposer", "email": "proposer@localhost"}
# The integrator and the bootstrap recognize their commits by the email: nobody else signs with it.
_RESERVED_EMAILS = {_INTEGRATOR_IDENTITY["GIT_COMMITTER_EMAIL"], _BOOTSTRAP_IDENTITY["GIT_COMMITTER_EMAIL"]}
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_NO_REF = "0" * 40
# Git trims symbols at the ends of the email: one that starts and ends with a letter or digit is required.
_EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*")
NETWORK = 300  # seconds of a git command that talks to the remote


@dataclass(frozen=True)
class Integration:
    """What the installation declares in order to propose (`integration_of`)."""

    remote: str
    repository: str
    branch: str
    folders: tuple
    mode: str
    after: tuple  # ((id, declared check), …)
    views: tuple
    author: dict


def _line(value):
    return isinstance(value, str) and value.strip() != "" and "\n" not in value and "\r" not in value


def integration_of(installation):
    """The `propose` configuration the installation declares, validated; ValueError if it is missing or invalid."""
    data = installation.get("integration") if isinstance(installation, dict) else None
    if not isinstance(data, dict):
        raise ValueError("the installation does not declare integration: {remote, repository, …}")
    extra = sorted(set(data) - FIELDS)
    if extra:
        raise ValueError(f"integration does not admit: {', '.join(extra)}")
    remote, repository = data.get("remote"), data.get("repository")
    if not _line(remote) or remote.startswith("-"):
        raise ValueError("integration.remote is the URL or the path of the canonical remote")
    if not isinstance(repository, str) or not _NAME.fullmatch(repository):
        raise ValueError(
            "integration.repository is the name of the local state: letters, digits, dot, hyphen and underscore"
        )
    branch = installation.get("canonical_branch")
    if (
        not isinstance(branch, str)
        or not _BRANCH.fullmatch(branch)
        or ".." in branch
        or branch.endswith((".lock", "/"))
    ):
        raise ValueError("canonical_branch is the name of the canonical branch")
    folders = installation.get("records_folder")
    if not isinstance(folders, str) or not all(c.strip() for c in folders.split(",")):
        raise ValueError("records_folder is the records folder; several, separated by commas")
    try:  # the same normalization as the gate: is_view and the request see the folders as it does
        folders = folders_of(_safe_folder([c.strip() for c in folders.split(",")]))
    except Lock as b:
        raise ValueError(f"records_folder: {b.result['reason']}") from None
    mode = data.get("approval", "all")
    if mode not in MODES:
        raise ValueError(f"integration.approval is one of {', '.join(MODES)}")
    declared = checks_of(installation)
    after = data.get("after_integrate", [])
    if (
        not isinstance(after, list)
        or any(not isinstance(i, str) or i not in declared for i in after)
        or len(set(after)) != len(after)
    ):
        raise ValueError("integration.after_integrate lists, without repeats, ids of declared checks")
    views = data.get("views", [])
    if not isinstance(views, list) or any(
        not _line(v) or v.startswith("/") or "\\" in v or ".." in v.split("/") for v in views
    ):
        raise ValueError("integration.views is a list of globs relative to the root, with /")
    author = data.get("author", AUTHOR)
    if (
        not isinstance(author, dict)
        or set(author) != {"name", "email"}
        or not _line(author["name"])
        or set("<>") & set(author["name"])
        or not isinstance(author["email"], str)
        or not _EMAIL.fullmatch(author["email"])
        or author["email"].casefold() in _RESERVED_EMAILS
    ):
        raise ValueError(
            "integration.author carries name and email, and the email is neither the integrator's nor the bootstrap's"
        )
    return Integration(
        remote=remote,
        repository=repository,
        branch=branch,
        folders=folders,
        mode=mode,
        after=tuple((i, declared[i]) for i in after),
        views=tuple(views),
        author=dict(author),
    )


def local_state(repository):
    """Folder of the local state of an installation: `$KBOL_STATE/<repository>`, by default `~/.kbol/<repository>`."""
    return Path(os.environ.get("KBOL_STATE") or Path.home() / ".kbol") / repository


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _network():
    """What a git command that talks to the remote adds to the minimal environment: it never prompts (neither git nor
    ssh) and sees the SSH agent."""
    agent = {k: os.environ[k] for k in ("SSH_AUTH_SOCK", "SSH_AGENT_PID") if k in os.environ}
    ssh = os.environ.get("GIT_SSH_COMMAND") or "ssh"
    return {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": f"{ssh} -o BatchMode=yes", **agent}


def _loose_git(*args, extra_env=None, timeout=None):
    """(code, error) of a git command without input whose failure the caller decides on: clone, fetch and push."""
    try:
        p = subprocess.run(
            ["git", *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env={**git_environment(), **(extra_env or {})},
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"git did not finish in {timeout} s"
    return p.returncode, p.stderr.decode("utf-8", "replace").strip()


def _same_remote(configured, saved):
    """Whether the `origin` of the clone is the installation's remote: the same URL or, locally, the same folder."""
    if configured == saved:
        return True
    try:
        return saved is not None and os.path.samefile(configured, saved)
    except OSError:
        return False


def open_clone(cfg):
    """The installation's integrator clone, created if it does not exist. It never uses the clone of another remote."""
    path = local_state(cfg.repository) / "integrator.git"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        clone_args = ("clone", "-q", "--bare", "--no-tags", "--", cfg.remote, str(path))
        code, error = _loose_git(*clone_args, extra_env=_network(), timeout=NETWORK)
        if code != 0:
            raise Lock("UNKNOWN_RESULT", f"could not clone {cfg.remote}: {error}")
    git = _Git(path)
    try:
        origin = git("config", "--get", "remote.origin.url")
    except Lock:
        origin = None
    if not _same_remote(cfg.remote, origin):
        raise Lock(None, f"{path} is not a clone of {cfg.remote}: it is not used")
    return git


def fetch(git, branch):
    """Fetches the canonical branch from the remote and brings the clone's up to date: {head, remote, pending_push}.

    It never discards what was integrated in the clone and not yet pushed: if the clone is ahead, the proposal goes on
    top of its head; if the clone and the remote have diverged, it blocks (`BASE_CHANGED`).
    """
    ref, remote_ref = f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"
    fetch_args = ("-C", git.repo, "fetch", "-q", "--no-tags", "origin", f"+{ref}:{remote_ref}")
    code, error = _loose_git(*fetch_args, extra_env=_network(), timeout=NETWORK)
    if code != 0:
        raise Lock("UNKNOWN_RESULT", f"could not fetch {branch} from the remote: {error}")
    remote = git("rev-parse", "--verify", "--end-of-options", f"{remote_ref}^{{commit}}")
    if git("show-ref", "--verify", "-q", ref, check=False) != 0:
        git("update-ref", ref, remote, _NO_REF)
    local = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    pending = 0
    if local != remote:
        if git("merge-base", "--is-ancestor", local, remote, check=False) == 0:
            git("update-ref", ref, remote, local)
            local = remote
        elif git("merge-base", "--is-ancestor", remote, local, check=False) == 0:
            pending = int(git("rev-list", "--count", f"{remote}..{local}"))
        else:
            not_pushed = git("rev-list", "--count", f"{remote}..{local}")
            # It is not discarded automatically: a person decides, with the exact command and knowing the receipts stay.
            raise Lock(
                "BASE_CHANGED",
                f"the integrator's clone and the remote have diverged on {branch}: {not_pushed} integrated and not "
                f"pushed commit(s) ({local[:12]}) do not descend from the remote ({remote[:12]}). To redo them on the "
                f"remote, discard them with `git -C {git.repo} update-ref {ref} {remote} {local}` (their receipts are "
                "kept) and propose again with a new operation_id",
                integrated_not_pushed=local,
                remote=remote,
            )
    return {"head": local, "remote": remote, "pending_push": pending}


def write_commit(git, base, files, author, message, delete=()):
    """Commit on `base` that writes `files` (path → bytes) and removes `delete`, without touching any working tree."""
    with tempfile.TemporaryDirectory(prefix="kb-proposal-") as tmp:
        env = {
            "GIT_INDEX_FILE": str(Path(tmp) / "index"),
            "GIT_AUTHOR_NAME": author["name"],
            "GIT_AUTHOR_EMAIL": author["email"],
            "GIT_COMMITTER_NAME": author["name"],
            "GIT_COMMITTER_EMAIL": author["email"],
        }
        git("read-tree", base, extra_env=env)
        if delete:  # a --bare clone has no working tree: they are removed from the index with mode 0
            removal = "".join(f"0 {_NO_REF}\t{path}\n" for path in sorted(delete))
            git("update-index", "--index-info", entry=removal.encode("utf-8"), extra_env=env)
        for path, content in sorted(files.items()):
            blob = git("hash-object", "-w", "--stdin", entry=content, extra_env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", extra_env=env)
        tree = git("write-tree", extra_env=env)
        return git("commit-tree", tree, "-p", base, entry=message.encode("utf-8"), extra_env=env)


def read_files(root, paths):
    """{path relative to the root: bytes} of the proposed working-tree files, with LF line breaks.

    ValueError if the root is not that of its repository, or a path repeats or lies outside it.
    """
    root = Path(root).resolve()
    p = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, env=git_environment()
    )
    toplevel = p.stdout.decode("utf-8", "replace").strip()
    if p.returncode != 0 or not toplevel or not os.path.samefile(toplevel, root):
        raise ValueError(f"the root has to be that of its git repository: {root}")
    output = {}
    for path in paths:
        archive = (root / path).resolve()
        try:
            relative = archive.relative_to(root).as_posix()
        except ValueError:
            raise ValueError(f"the file has to be inside the root: {path}") from None
        if relative in output or not _line(relative) or "\t" in relative:
            raise ValueError(f"repeated or not admitted path: {path}")
        output[relative] = archive.read_text(encoding="utf-8").encode("utf-8")
    if not output:
        raise ValueError("propose needs at least one file")
    return output


def _pattern(glob):
    """Regular expression of a path glob with `/`: `**/` crosses folders, `*` and `?` do not."""
    parts, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            parts.append("(?:[^/]+/)*")
            i += 3
        elif glob.startswith("**", i):
            parts.append(".*")
            i += 2
        elif glob[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(parts))


def is_view(path, cfg):
    """Whether an after step may change `path`: a declared view and, inside a records folder, only `index.md`, which is
    what the record loading skips. So a view is never a record, its fingerprints nor a request."""
    if not any(_pattern(g).fullmatch(path) for g in cfg.views):
        return False
    in_records = any(path.startswith(c.rstrip("/") + "/") for c in cfg.folders)
    return not in_records or path.rsplit("/", 1)[-1] == "index.md"


def _after(git, cfg, branch, op, root):
    """Runs the after steps on what was integrated in `branch` and writes the views that change in a commit of its own.

    Returns {steps, views, head, reason}; `reason` says why it cannot be pushed, or None.
    """
    ref = f"refs/heads/{branch}"
    head = git("rev-parse", "--verify", "--end-of-options", ref)
    output = {"steps": [], "views": [], "head": head, "reason": None}
    if not cfg.after:
        return output
    python, _ = python_of(root)
    with tempfile.TemporaryDirectory(prefix="kb-after-", ignore_cleanup_errors=True) as tmp:
        tree = Path(tmp) / "tree"
        # No line-break conversion: what is read from the checkout is what is on the branch.
        clone_args = ["clone", "-q", "--no-tags", "--single-branch", "--branch", branch, "-c", "core.autocrlf=false"]
        code, error = _loose_git(*clone_args, "--", git.repo, str(tree))
        if code != 0:
            raise Lock("UNKNOWN_RESULT", f"could not prepare the checkout of {branch}: {error}")
        in_tree = _Git(tree)
        for ident, spec in cfg.after:
            evidence = Path(tmp) / f"{ident}.log"
            order = [python if a == "{python}" else a for a in spec["command"]]
            code, observation = _launch(order, tree, spec["timeout"], evidence)
            expected = spec.get("expected_code", 0)
            step = {"check_id": ident, "code": code, "expected_code": expected}
            step["result"] = "passed" if code == expected else "failed"
            # What a step generates stays in the index: the next one sees it as tracked.
            in_tree("add", "-A")
            if code != expected:
                step["final_output"] = _queue(evidence)
                if observation:
                    step["observation"] = observation
                output["steps"].append(step)
                output["reason"] = f"the after step {ident} does not pass"
                return output
            output["steps"].append(step)
        fields = in_tree("diff", "--cached", "--no-renames", "--name-status", "-z", "HEAD", raw=True)
        fields = [c for c in fields.decode("utf-8").split("\0") if c]
        changes = list(zip(fields[0::2], fields[1::2]))
        foreign = sorted(path for _, path in changes if not is_view(path, cfg))
        if foreign:
            output["reason"] = f"an after step changed something that is not a declared view: {foreign[0]}"
            return output
        if changes:
            files = {path: in_tree("show", f":{path}", raw=True) for state, path in changes if state != "D"}
            delete = [path for state, path in changes if state == "D"]
            new = write_commit(git, head, files, cfg.author, f"kb: views after {op}\n", delete)
            if git("update-ref", ref, new, head, check=False) != 0:
                raise Lock("BASE_CHANGED", f"{branch} changed while the views were written: they were not written")
            output.update(views=sorted(path for _, path in changes), head=new)
    return output


def _gate(git, cfg, branch, receipts, op, base, prop, approvals, actor):
    return integrate(
        git.repo,
        branch=branch,
        folder=list(cfg.folders),
        operation_id=op,
        expected_base=base,
        proposal_rev=prop,
        revisions=approvals,
        verifier=DeclaredVerifier(git.repo),
        receipts=receipts,
        approval=cfg.mode,
        actor=actor,
    )


def _dry_run(git, cfg, op, base, prop, approvals, actor, root, valid_at):
    """The proposal through the gate and the after steps, on a temporary branch with separate receipts: nothing stays."""
    branch = f"dry-run-{op}-{uuid.uuid4().hex[:8]}"
    git("update-ref", f"refs/heads/{branch}", base, _NO_REF)
    try:
        with tempfile.TemporaryDirectory(prefix="kb-dry-run-") as tmp:
            receipt = _gate(git, cfg, branch, Path(tmp), op, base, prop, approvals, actor)
            if receipt.get("state") == "integrated":
                after = _after(git, cfg, branch, op, root)
                result = {k: receipt.get(k) for k in ("records", "decisive", "warnings", "impact")}
                result.update(after=after["steps"], views=after["views"])
                if after["reason"]:
                    return {"state": "blocked", "code": None, "reason": after["reason"], **result}
                return {"state": "dry_run_done", "code": None, **result}
    finally:
        git("update-ref", "-d", f"refs/heads/{branch}", check=False)
    if receipt.get("code") != "INSUFFICIENT_AUTHORITY" or approvals:
        return {k: v for k, v in receipt.items() if k != "operation_id"}
    # The gate asks for an approval that was not given: what must be shown to whoever approves, with the same digests.
    package = approval_package(
        git.repo,
        folder=list(cfg.folders),
        operation_id=op,
        base=base,
        proposal=prop,
        valid_at=valid_at or _now(),
    )
    if package["state"] == "blocked":
        return {k: v for k, v in package.items() if k != "operation_id"}
    return {
        "state": "pending_approval",
        "code": "INSUFFICIENT_AUTHORITY",
        "reason": receipt.get("reason"),
        "package": package,
    }


def propose(
    root,
    installation,
    *,
    operation_id,
    files,
    actor=None,
    effects=None,
    imports=None,
    approvals=None,
    until="dry_run",
    valid_at=None,
):
    """Proposes `files` of the working tree of `root` and takes them as far as `until` says; returns the result.

    `state` is `dry_run_done`, `integrated`, `pushed`, `pending_approval` (the dry run needs an approval that was not
    given: it carries the package) or `blocked`, with the gate's code and reason when the gate blocks. `approvals` is
    the list of declared approvals already given. `valid_at` is the cut for the package supports; without it, the
    current instant. ValueError or OSError if the installation or the files cannot be read.
    """
    cfg = integration_of(installation)
    content = read_files(root, files)
    try:
        return _propose(root, cfg, operation_id, content, actor, effects, imports, approvals, until, valid_at)
    except Lock as b:
        return {"operation_id": operation_id, **b.result}


def _propose(root, cfg, op, content, actor, effects, imports, approvals, until, valid_at):
    if until not in UNTIL:
        raise Lock(None, f"until is one of {', '.join(UNTIL)}")
    _check_operation(op)
    if ".." in op or op.split(".")[0].upper() in _RESERVED:
        raise Lock(None, "operation_id does not admit «..» nor a reserved Windows name")
    if actor is None:
        if cfg.mode == "decisive":
            raise Lock(None, "in decisive mode, propose needs the actor of whoever operates")
        actor = ACTOR
    approvals = [] if approvals is None else approvals
    if not isinstance(approvals, list) or any(
        not isinstance(a, dict) or a.get("mechanism") != MECHANISM for a in approvals
    ):
        raise Lock(None, "propose integrates with a list of declared approvals (kbol.declared)")
    if effects or imports:
        request = {"operation_id": op, "effects": effects or {}}
        if imports:
            request["imports"] = imports
        path = f"{cfg.folders[0]}/_requests/{op}.json"
        if path in content:
            raise Lock(None, f"the request is given as a file or with effects and imports, not both ways: {path}")
        try:
            content = {**content, path: json.dumps(request, ensure_ascii=False, indent=1).encode("utf-8")}
        except (TypeError, ValueError) as exc:
            raise Lock("INVALID_SCHEMA", f"request not serializable: {exc}") from exc
    git = open_clone(cfg)
    clone = fetch(git, cfg.branch)
    base = clone["head"]
    receipts = local_state(cfg.repository) / "receipts"
    if until != "dry_run":
        previous = _already_integrated(git, cfg.branch, receipts, op)
        if previous is not None:
            alert = "the operation was already integrated in the clone: its receipt is resumed and the disk is not proposed again"
            previous = {**previous, "until": until, "resumed": True}
            previous["warnings"] = [*(previous.get("warnings") or []), alert]
            return _finish(git, cfg, op, root, until, clone, previous)
    prop = write_commit(git, base, content, cfg.author, f"proposal {op}\n")
    common = {
        "operation_id": op,
        "until": until,
        "approval_mode": cfg.mode,
        "actor": actor,
        "base": base,
        "proposal": prop,
        "clone": git.repo,
        "pending_push": clone["pending_push"],
        "pushed": False,
    }
    if until == "dry_run":
        return {**common, **_dry_run(git, cfg, op, base, prop, approvals, actor, root, valid_at)}
    receipt = _gate(git, cfg, cfg.branch, receipts, op, base, prop, approvals, actor)
    if receipt.get("state") != "integrated":
        return {**common, **receipt}
    return _finish(git, cfg, op, root, until, clone, {**common, **receipt})


def _already_integrated(git, branch, receipts, op):
    """The receipt of `op` if its commit is already on the clone's branch: the operation was integrated and perhaps
    not pushed.

    This finishes an operation integrated with `integrate`, or whose after step or push failed, without proposing it
    again: the gate would reject it, because the file on disk does not carry the events the gate wrote.
    """
    path = Path(receipts) / f"{op}.json"
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise Lock("UNKNOWN_RESULT", f"unreadable receipt: {exc}") from exc
    commit = receipt.get("integrated_revision") if isinstance(receipt, dict) else None
    if receipt.get("state") != "integrated" or not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{40}", commit):
        return None
    if git("merge-base", "--is-ancestor", commit, f"refs/heads/{branch}", check=False) != 0:
        return None  # its commit is not on this branch: the gate decides (another request or a receipt that does not match)
    return receipt


def _finish(git, cfg, op, root, until, clone, output):
    """After steps and, with `until=push`, the push, on what was already integrated on the clone's branch."""
    ref = f"refs/heads/{cfg.branch}"
    try:
        after = _after(git, cfg, cfg.branch, op, root)
    except (Lock, OSError, ValueError) as exc:
        reason = exc.result["reason"] if isinstance(exc, Lock) else str(exc)
        after = {"steps": [], "views": [], "head": None, "reason": f"the after steps did not finish: {reason}"}
    output = {**output, "pushed": False}
    output.update(after=after["steps"], views=after["views"])
    output["head"] = git("rev-parse", "--verify", "--end-of-options", ref)
    output["pending_push"] = int(git("rev-list", "--count", f"{clone['remote']}..{ref}"))
    if after["reason"]:
        reason = f"{after['reason']}: what was integrated stays in the clone, not pushed"
        return {**output, "state": "blocked", "code": None, "reason": reason}
    if until == "integrate":
        return output
    push_args = ("-C", git.repo, "push", "-q", "origin", f"{ref}:{ref}")
    code, error = _loose_git(*push_args, extra_env=_network(), timeout=NETWORK)
    if code != 0:
        reason = (
            f"integrated in the clone, but it could not be pushed: {error}. If the remote moved on, the next command "
            "will say so and how to redo it; if not, push by repeating this command with the same operation_id"
        )
        return {**output, "state": "blocked", "code": "UNKNOWN_RESULT", "reason": reason}
    return {**output, "state": "pushed", "pushed": True, "pending_push": 0}
