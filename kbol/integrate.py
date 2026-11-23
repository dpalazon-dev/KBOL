"""Controlled local integration into a canonical git branch (core 1.0, §7 "Integration gate" and "Receipts").

What the person approves: the PR diff, which compares the expected base with the proposed commit and includes the
records and, if any, the effects requested in `<folder>/_requests/<operation_id>.json`. The caller only identifies
the reviews; the integrator computes the digests, verifies each review in the trusted channel and builds the
approvals from verified data. Every integration requires authority over each touched record, even a proposal without
effects: the integration keeps its authorization.

Sequence: previous receipt checked against the branch, or reconciliation through an integrator commit → current base
equal to the expected one (otherwise `BASE_CHANGED`, without retrying) → the proposal descends from the base and only
touches records of the folder and its request file → mutability → authority under the base policy, revalidated when
integrating → events admitted with the integrator clock → references, cycles and conflicts on the final tree → domain
vocabulary on the same tree → flattened commit on the base with git plumbing and compare-and-swap → re-read → receipt
with the impact debt.

The read-only part between the base and the proposal (`prepare_request`) and the check of the final tree
(`final_tree`) are the same ones the approval package uses (`kbol.package`): what is shown before approving carries
the digests this gate recomputes.

Approval modes. `all` (the default) is the contract's. `decisive` is a non-conforming local choice
(docs/design-choices.md, "Non-conforming mechanisms"): it only requires approval for what is decisive (`DECISIVE`,
policy changes and the import that supersedes or closes); the rest enters with the operation actor, who signs each
event.

It runs nothing from the proposed content, touches no working tree and does not write to a checked-out branch.
Remote integration into `main` of an installation stays disabled until its bootstrap (`kbol.bootstrap`) and the
protection of the branch on the remote.
"""

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import fingerprints as fingerprints_mod
from . import vocabulary as vocabulary_mod
from .authority import evaluate
from .consolidate import consolidate
from .core import FormatError, serialize
from .core import parse as parse_legacy
from .digest import canonical_bytes, check_effects, digest
from .events import HistoryError
from .impact import impact
from .importing import check as check_import
from .importing import redistributes
from .model import INITIAL, PRECISIONS, TRANSITIONS
from .mutability import compare
from .projection import Snapshot
from .references import validate_snapshot
from .schema import validate
from .snapshot import folders_of, git_environment, load
from .timeutil import instant, is_date, is_instant
from .verification import VerificationError, revision_key

ACTOR = "process:local-integrator"
MODES = ("all", "decisive")
# Decisive transitions in `decisive` mode: accept or reject a decision; authorize, close or cancel a plan or a
# milestone. Starting a milestone, resolving a question or validating a hypothesis enter with their actor.
DECISIVE = {
    "decision": {"accepted", "rejected"},
    "plan": {"authorized", "closed", "cancelled"},
    "milestone": {"authorized", "completed", "cancelled"},
    "fact": {"accepted", "rejected"},
}
# People, roles and entities: any transition changes who decides or what exists for the policy.
DECISIVE_POLICY = ("person", "role")
# An import with these relations sets what supersedes or closes what: it is decisive.
DECISIVE_RELATIONS = ("amends", "supersedes", "resolved_by", "defines")
_LEGACY_IDS = re.compile(r"\b(?:ADR-\d{4}|QD-\d{3,}|HD-\d{3,}|PL-\d{3}(?:-H\d+)?)\b")
_ACTOR = re.compile(r"^(human:\S+|process:\S+|[^\s/:]+/[^\s/]+)(?!\n)$")
TRAILER = "Operation-Id"
EMAIL = "integrator@localhost"
_OPERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
_SHA = re.compile(r"[0-9a-f]{40}")
_IDENTITY = {
    "GIT_AUTHOR_NAME": "local-integrator",
    "GIT_AUTHOR_EMAIL": EMAIL,
    "GIT_COMMITTER_NAME": "local-integrator",
    "GIT_COMMITTER_EMAIL": EMAIL,
}


class Lock(Exception):
    """The gate stops: `result` is the `blocked` result with its code and reason, the same one `integrate` returns."""

    def __init__(self, code, reason, **extra):
        super().__init__(reason)
        self.result = {"state": "blocked", "code": code, "reason": reason, **extra}


_Lock = Lock  # internal name, shared with bootstrap


@dataclass(frozen=True)
class PreparedRequest:
    """What the gate knows about a proposal before looking at authority (`prepare_request`).

    `effects` are the transitions of the request with their `previous_state` filled in; `imports`, the imports checked
    against their legacy record, with `legacy_state` and the reasons that make them decisive.
    """

    operation_id: str
    base: str
    proposal: str
    base_snap: Snapshot
    prop_snap: Snapshot
    mut: dict
    effects: dict
    imports: dict
    touched: list

    def digests(self):
        """{ID: digest} of each touched record: the one authority recomputes when integrating."""
        regs, bodies = self.prop_snap.records, self.prop_snap.bodies
        return {
            i: digest(regs[i], bodies[i], *the_approvable(i, self.effects, self.imports)) for i in self.touched
        }

    def decisive_reasons(self, ident):
        return decisive_reasons(
            ident, self.prop_snap.records[ident], self.effects, self.mut["policy_changes"], self.imports
        )


class _Git:
    def __init__(self, repo):
        self.repo = str(repo)

    def __call__(self, *args, entry=None, extra_env=None, check=True, raw=False):
        env = {**git_environment(), **(extra_env or {})}
        p = subprocess.run(
            ["git", "--literal-pathspecs", "-C", self.repo, *args], input=entry, capture_output=True, env=env
        )
        if not check:
            return p.returncode
        if p.returncode != 0:
            raise _Lock(
                "UNKNOWN_RESULT", f"git {args[0]} failed: {p.stderr.decode('utf-8', 'replace').strip()}"
            )
        return p.stdout if raw else p.stdout.decode("utf-8").strip()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_receipt(path, receipt):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def integrate(
    repo,
    *,
    branch,
    folder,
    operation_id,
    expected_base,
    proposal_rev,
    revisions,
    verifier,
    receipts,
    approval="all",
    actor=ACTOR,
):
    """Integrates the proposal and returns the receipt, or a `blocked` result with its code. It never retries alone.

    `approval` is `all` or `decisive`; `actor`, who runs the operation (`human:…`, `process:…` or `client/model`),
    who signs the events the integration writes.
    """
    try:
        if approval not in MODES:
            raise _Lock(None, f"unknown approval mode: {approval!r}")
        if not isinstance(actor, str) or not _ACTOR.match(actor):
            raise _Lock(None, "invalid actor: human:<id>, process:<name> or <client>/<model>")
        return _integrate(
            _Git(repo),
            branch,
            folder,
            operation_id,
            expected_base,
            proposal_rev,
            revisions,
            verifier,
            Path(receipts),
            approval,
            actor,
        )
    except _Lock as b:
        return {"operation_id": operation_id, **b.result}


def _safe_folder(folder):
    """The folder, or the tuple of folders without repeats or nesting; the first holds the policy and the requests."""
    if isinstance(folder, (list, tuple)):
        if not folder:
            raise _Lock(None, "an installation has at least one knowledge folder")
        folders = tuple(_one_folder(c) for c in folder)
        for i, a in enumerate(folders):
            for b in folders[i + 1 :]:
                if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                    raise _Lock(None, f"repeated or nested folders: {a} and {b}")
        return folders[0] if len(folders) == 1 else folders
    return _one_folder(folder)


def _one_folder(folder):
    if not isinstance(folder, str) or not folder or "\\" in folder or folder.startswith((":", "/")):
        raise _Lock(None, "the knowledge folder must be an explicit relative subfolder")
    parts = PurePosixPath(folder).parts
    if not parts or any(p in ("..", ".") for p in parts):
        raise _Lock(None, "the knowledge folder does not admit . or .. components")
    return "/".join(parts)


def _check_operation(op):
    if not isinstance(op, str) or not _OPERATION.fullmatch(op):
        raise _Lock(None, "invalid operation_id: letters, digits, dot, hyphen and underscore, up to 100")


def _check_shas(expected_base, proposal_rev):
    for name, value in (("expected_base", expected_base), ("proposal_rev", proposal_rev)):
        if not isinstance(value, str) or not _SHA.fullmatch(value):
            raise _Lock(None, f"{name} must be a full 40-character SHA")


def prepare_request(repo, *, folder, operation_id, base, proposal):
    """The read-only part of the gate, up to knowing what is approved of each record: `PreparedRequest`.

    It does the same as the integration between the base and the proposal (paths, request, mutability, effects and
    imports), with the same code, and raises `Lock` with the same code where the integration would block. It does not
    look at the canonical branch, the receipts or authority. Zero touched records does not block here: the caller
    decides.
    """
    git = _Git(repo)
    _check_operation(operation_id)
    folder = _safe_folder(folder)
    _check_shas(base, proposal)
    if git("cat-file", "-e", f"{base}^{{commit}}", check=False) != 0:
        raise _Lock("MISSING_REFERENCE", "the base commit does not exist in the repository")
    return _prepare(git, folder, operation_id, base, proposal)


def final_tree(prepared):
    """(final tree, warnings, vocabulary) the integration would write, without the pending ratifications.

    The same checks the gate makes after authority: canonical final records, references, cycles, normative conflicts
    and domain vocabulary. None depends on the ratifications except the one requiring a ratification before accepting,
    which is not required here. It raises `Lock` where the gate would block. The events carry the current clock.
    `vocabulary` are the term and scope findings the gate would warn about in the receipt.
    """
    p = prepared
    now = _now()
    unapproved = {i: [] for i in p.touched}
    finals = _materialize(
        p.operation_id,
        now,
        p.touched,
        p.effects,
        unapproved,
        p.mut,
        p.prop_snap,
        p.imports,
        p.base,
        pending_approval=True,
    )
    final, warnings = _check_final(p.base_snap, p.prop_snap, finals)
    return final, warnings, _check_vocabulary(p.base_snap, final, p.effects, p.touched, now)


def _prepare(git, folder, op, base, prop):
    if git("cat-file", "-e", f"{prop}^{{commit}}", check=False) != 0:
        raise _Lock("MISSING_REFERENCE", "the proposed commit does not exist in the repository")
    if git("merge-base", "--is-ancestor", base, prop, check=False) != 0:
        raise _Lock("BASE_CHANGED", "the proposal does not descend from the base")
    base_snap, cob_b = load(git.repo, folder, base, legacy=True)
    if cob_b["state"] != "complete":
        raise _Lock("INVALID_SCHEMA", "the base is not coherent", coverage=cob_b)
    prop_snap, cob_p = load(git.repo, folder, prop, mode="proposal", legacy=True)
    if cob_p["state"] != "complete":
        raise _Lock("INVALID_SCHEMA", "the proposal is not coherent", coverage=cob_p)
    effects, imports = _paths_and_request(git, base, prop, folder, op, base_snap, prop_snap)
    mut = compare(base_snap, prop_snap)
    errors = [h for h in mut["findings"] if h["severity"] == "error"]
    if errors:
        raise _Lock("INVALID_SCHEMA", "the proposal changes protected content", findings=errors)
    effects = _check_effects(effects, prop_snap)
    imports = _check_imports(git, base, base_snap, prop_snap, imports, effects, mut)
    touched = sorted(set(mut["new"]) | set(mut["modified"]) | set(effects))
    return PreparedRequest(op, base, prop, base_snap, prop_snap, mut, effects, imports, touched)


def _integrate(git, branch, folder, op, expected_base, proposal_rev, revisions, verifier, receipts, mode, actor):
    _check_operation(op)
    if not isinstance(branch, str) or not _BRANCH.fullmatch(branch) or ".." in branch or branch.endswith((".lock", "/")):
        raise _Lock(None, "invalid branch name")
    folder = _safe_folder(folder)
    _check_shas(expected_base, proposal_rev)
    request = {
        "branch": branch,
        "folder": list(folders_of(folder)) if not isinstance(folder, str) else folder,
        "base": expected_base,
        "proposal": proposal_rev,
        "revisions": revisions,
    }
    if mode != "all" or actor != ACTOR:  # the usual request keeps its fingerprint
        request.update(approval=mode, actor=actor)
    try:
        fingerprint = hashlib.sha256(canonical_bytes(request)).hexdigest()
    except ValueError as exc:
        raise _Lock("INVALID_SCHEMA", f"request not serializable: {exc}") from exc
    ref = f"refs/heads/{branch}"
    receipt_path = receipts / f"{op}.json"
    _canonical_branch(git, ref)
    previous = _previous_receipt(git, ref, receipt_path, op, fingerprint, folder)
    if previous:
        return previous
    reconciled = _reconcile(git, ref, op, fingerprint, folder, receipt_path)
    if reconciled:
        return reconciled
    current = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    if current != expected_base:
        raise _Lock(
            "BASE_CHANGED", f"{branch} is at {current[:12]}, not at the expected base {expected_base[:12]}: revalidate"
        )
    base, prop = expected_base, proposal_rev
    p = _prepare(git, folder, op, base, prop)
    base_snap, prop_snap, mut = p.base_snap, p.prop_snap, p.mut
    effects, imports, touched = p.effects, p.imports, p.touched
    if not touched:
        raise _Lock(None, "the proposal changes no record")
    now = _now()
    approvals = _authority(
        touched,
        effects,
        mut["policy_changes"],
        revisions,
        base_snap,
        prop_snap,
        verifier,
        prop,
        base,
        now,
        imports,
        mode,
    )
    finals = _materialize(op, now, touched, effects, approvals, mut, prop_snap, imports, base, mode, actor)
    final_snap, warnings = _check_final(base_snap, prop_snap, finals)
    terms = _check_vocabulary(base_snap, final_snap, effects, touched, now)
    warnings = warnings + [vocabulary_warning(h) for h in terms]
    debt = impact(base_snap, final_snap)

    new = _write_commit(git, ref, current, prop, op, fingerprint, finals, prop_snap, approvals, mode, actor, folder)
    if new is None:
        reconciled = _reconcile(git, ref, op, fingerprint, folder, receipt_path)
        if reconciled:
            return reconciled
        raise _Lock("BASE_CHANGED", "the branch changed during the integration: nothing was written to it")
    if git("rev-parse", "--verify", "--end-of-options", ref) != new:
        raise _Lock("UNKNOWN_RESULT", "the branch does not point to the written commit: inspect before retrying")
    receipt = {
        "operation_id": op,
        "state": "integrated",
        "code": None,
        "request_sha256": fingerprint,
        "branch": branch,
        "base": base,
        "proposal": prop,
        "integrated_revision": new,
        "records": touched,
        "events": sorted(
            e["event_id"] for r, _ in finals.values() for e in r["events"] if e["event_id"].startswith(f"{op}-")
        ),
        "approvals": sorted({a["approval_id"] for list_ in approvals.values() for a in list_}),
        "approval_details": _detail(approvals),
        "approval_mode": mode,
        "actor": actor,
        "decisive": sorted(i for i, list_ in approvals.items() if list_),
        "impact": debt,
        "warnings": warnings,
        "recorded_at": now,
        "reconciled": False,
        "repeated": False,
    }
    try:
        _write_receipt(receipt_path, receipt)
    except OSError as exc:
        return {**receipt, "persisted_receipt": False, "warning": f"integrated, but the receipt was not saved: {exc}"}
    return receipt


def _canonical_branch(git, ref):
    """The branch exists, is not a symbolic ref and is not checked out in any worktree (case-insensitively)."""
    if git("check-ref-format", ref, check=False) != 0:
        raise _Lock(None, f"{ref} is not a valid branch name")
    if git("symbolic-ref", "-q", ref, check=False) == 0:
        raise _Lock(None, f"{ref} is a symbolic ref: the integrator only writes to a real branch")
    names = git("for-each-ref", "--format=%(refname)", "refs/heads/").splitlines()
    real = [n for n in names if n.casefold() == ref.casefold()]
    if real != [ref]:
        raise _Lock("MISSING_REFERENCE", f"there is no branch {ref} with that exact name")
    in_use = [
        line.split(" ", 1)[1].casefold()
        for line in git("worktree", "list", "--porcelain").splitlines()
        if line.startswith("branch ")
    ]
    if ref.casefold() in in_use:
        raise _Lock(None, f"{ref} is in use in a worktree: the integrator does not write to a checked-out branch")


def _is_integrator_commit(git, commit, op, fingerprint):
    """Mainline commit written by the integrator for this operation: (Base, Proposal) or None."""
    data = git(
        "show",
        "-s",
        "--format=%P%x00%ce%x00%(trailers:key=Operation-Id,valueonly,separator=%x01)%x00"
        "%(trailers:key=Request-Sha256,valueonly)%x00%(trailers:key=Base,valueonly)%x00"
        "%(trailers:key=Proposal,valueonly)",
        "--end-of-options",
        commit,
    ).split("\x00")
    parents, email, ops, req, base, prop = (d.strip() for d in data[:6])
    if email != EMAIL or ops.split("\x01") != [op] or parents.split() != [base]:
        return None
    if req != fingerprint:
        raise _Lock(None, "this operation_id was already integrated with another request", integrated_revision=commit)
    return base, prop


def _previous_receipt(git, ref, path, op, fingerprint, folder):
    """A previous receipt only counts if its commit is on the mainline of the branch and comes from the integrator.

    What describes the change (base, proposal, records and impact) is rebuilt from that commit, not read from the file.
    """
    if not path.exists():
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _Lock("UNKNOWN_RESULT", f"unreadable receipt: {exc}") from exc
    if receipt.get("request_sha256") != fingerprint:
        raise _Lock(None, "this operation_id was already used with another request: use a new identifier")
    commit = receipt.get("integrated_revision")
    mainline = git("rev-list", "--first-parent", "--end-of-options", ref).splitlines()
    pair = (
        _is_integrator_commit(git, commit, op, fingerprint) if isinstance(commit, str) and commit in mainline else None
    )
    if pair is None:
        raise _Lock("UNKNOWN_RESULT", "the receipt does not match the branch: inspect before retrying")
    base, prop = pair
    debt = impact(load(git.repo, folder, base)[0], load(git.repo, folder, commit)[0])
    return {
        **receipt,
        "base": base,
        "proposal": prop,
        "records": debt["changed"],
        "impact": debt,
        "repeated": True,
    }


def _reconcile(git, ref, op, fingerprint, folder, path):
    """If the mainline already has the integrator commit for the operation, the response was lost."""
    for commit in git("rev-list", "--first-parent", "--end-of-options", ref).splitlines():
        pair = _is_integrator_commit(git, commit, op, fingerprint)
        if pair is None:
            continue
        base, prop = pair
        debt = impact(load(git.repo, folder, base)[0], load(git.repo, folder, commit)[0])
        receipt = {
            "operation_id": op,
            "state": "integrated",
            "code": None,
            "request_sha256": fingerprint,
            "base": base,
            "proposal": prop,
            "integrated_revision": commit,
            "records": debt["changed"],
            "impact": debt,
            "recorded_at": _now(),
            "reconciled": True,
            "repeated": False,
            "note": "receipt rebuilt from the integrator commit: the original response was lost",
        }
        try:
            _write_receipt(path, receipt)
        except OSError as exc:
            receipt.update(persisted_receipt=False, warning=f"the receipt was not saved: {exc}")
        return receipt
    return None


def _paths_and_request(git, base, prop, folder, op, base_snap, prop_snap):
    """Checks that the proposal only touches records of the folder and returns the effects of its request."""
    output = git("diff-tree", "-r", "--no-renames", "--name-status", "-z", base, prop, raw=True).decode("utf-8")
    fields = [c for c in output.split("\0") if c]
    changes = list(zip(fields[0::2], fields[1::2]))
    request = f"{folders_of(folder)[0]}/_requests/{op}.json"
    records = set(prop_snap.paths.values()) | set(base_snap.paths.values())
    effects, imports = {}, {}
    for state, path in changes:
        if path == request:
            if state != "A":
                raise _Lock(None, "the request of this operation already existed: use a new operation_id")
            effects, imports = _read_request(git, prop, path, op)
        elif path not in records:
            raise _Lock(None, f"the proposal touches something that is not a record of the knowledge folder: {path}")
    return effects, imports


def _read_request(git, prop, path, op):
    def without_repeats(pairs):
        if len({k for k, _ in pairs}) != len(pairs):
            raise ValueError("repeated key")
        return dict(pairs)

    try:
        data = json.loads(git("show", f"{prop}:{path}"), object_pairs_hook=without_repeats)
    except ValueError as exc:
        raise _Lock("INVALID_SCHEMA", f"unreadable request: {exc}") from exc
    if (
        not isinstance(data, dict)
        or not {"operation_id", "effects"} <= set(data) <= {"operation_id", "effects", "imports"}
        or data["operation_id"] != op
    ):
        raise _Lock(
            "INVALID_SCHEMA",
            "the request carries operation_id (the one of this operation), effects and, if it imports, imports",
        )
    return data["effects"], data.get("imports", {})


def _check_effects(effects, prop_snap):
    if not isinstance(effects, dict):
        raise _Lock("INVALID_SCHEMA", "effects is a map ID → list of transitions")
    output = {}
    for ident, list_ in effects.items():
        r = prop_snap.records.get(ident)
        if r is None:
            raise _Lock("MISSING_REFERENCE", f"effect on {ident}, which is not in the proposal")
        try:
            check_effects(list_)
        except ValueError as exc:
            raise _Lock("INVALID_SCHEMA", f"{ident}: {exc}") from exc
        state, complete = r["state"], []
        for ef in list_:
            prev = ef.get("previous_state", state)
            if prev != state or (prev, ef["new_state"]) not in TRANSITIONS[r["type"]]:
                raise _Lock(
                    "INVALID_SCHEMA", f"{ident}: transition {prev}→{ef['new_state']} not admitted from {state}"
                )
            complete.append({**ef, "previous_state": prev})
            state = ef["new_state"]
        output[ident] = complete
    return output


IMPORT_FIELDS = frozenset({"state", "valid_from", "precision", "inherited_authority"})


def _approvable(import_):
    """What the person approves of an import: what the request declares, without what the integrator adds."""
    return None if import_ is None else {k: import_[k] for k in sorted(IMPORT_FIELDS)}


def the_approvable(ident, effects, imports):
    """(effects, import) covered by the digest of a record: the same when showing it as when recomputing it."""
    return effects.get(ident, []), _approvable(imports.get(ident))


def _check_imports(git, base, base_snap, prop_snap, imports, effects, mut):
    """Each import matches the legacy record of the base: same identity, same body and its mapped state."""
    if not isinstance(imports, dict):
        raise _Lock("INVALID_SCHEMA", "imports is a map ID → import")
    output = {}
    for ident, imp in imports.items():
        if not isinstance(imp, dict) or set(imp) != IMPORT_FIELDS:
            raise _Lock("INVALID_SCHEMA", f"{ident}: the import carries {sorted(IMPORT_FIELDS)}")
        if ident in effects:
            raise _Lock("INVALID_SCHEMA", f"{ident}: an import carries no effects in the same operation")
        card = base_snap.legacy.get(ident)
        if card is None or ident not in mut["new"] or ident not in prop_snap.records:
            raise _Lock("MISSING_REFERENCE", f"{ident} is not a legacy record of the base imported here")
        path, r = prop_snap.paths[ident], prop_snap.records[ident]
        if card["path"] != path or card["type"] != r.get("type"):
            raise _Lock("INVALID_SCHEMA", f"{ident}: it is imported at the path and with the type of its legacy record")
        if imp["state"] != card["proposed_state"]:
            raise _Lock(
                "INVALID_SCHEMA",
                f"{ident}: the imported state ({imp['state']}) is not the one of its legacy record ({card['proposed_state']})",
            )
        if imp["inherited_authority"] != card["inherited_authority"]:
            raise _Lock("INVALID_SCHEMA", f"{ident}: the inherited authority is not the one of the legacy record")
        if imp["precision"] not in (*PRECISIONS, "unknown"):
            raise _Lock("INVALID_SCHEMA", f"{ident}: unknown precision {imp['precision']!r}")
        valid = imp["valid_from"]
        if valid is not None and not (is_date(valid) or is_instant(valid)):
            raise _Lock("INVALID_SCHEMA", f"{ident}: valid_from is a date, an instant with a time zone or null")
        legacy_text = git("show", f"{base}:{path}") + "\n"
        reasons = check_import(r, prop_snap.bodies[ident], legacy_text, path)
        if reasons:
            raise _Lock("INVALID_SCHEMA", f"{ident}: {reasons[0]}", reasons=reasons)
        decisive_why = _decisive_by_legacy(ident, card, legacy_text, base_snap.legacy)
        if redistributes(prop_snap.bodies[ident], legacy_text):
            decisive_why.append("the split redistributes the lines of the legacy record")
        output[ident] = {
            **imp,
            "legacy_state": card["legacy_state"],
            "decisive": decisive_why,
        }
    return output


def _decisive_by_legacy(ident, card, legacy_text, legacy):
    """Why the import decides something even if the proposal does not declare it: the legacy record sets a succession
    or a closure.

    Whether an import is decisive cannot depend on relations the proposer can omit.
    """
    reasons = []
    if any((card.get("proposed_relations") or {}).get(k) for k in DECISIVE_RELATIONS):
        reasons.append("the legacy record closes or supersedes another record")
    if any(a.get("field") in DECISIVE_RELATIONS for a in card.get("ambiguities") or []):
        reasons.append("the legacy record declares a supersession or a closure")
    try:
        meta, _ = parse_legacy(legacy_text)
    except FormatError:
        meta = {}
    if _LEGACY_IDS.search(str(meta.get("supersedes_to") or "")):
        reasons.append("the legacy record declares what it supersedes")
    for other, f in legacy.items():
        if other == ident:
            continue
        for a in f.get("ambiguities") or []:
            if a.get("field") in DECISIVE_RELATIONS and ident in (a.get("candidates") or []):
                reasons.append(f"{other} declares that {ident} supersedes it")
    return reasons


class _SingleCheck:
    """Each review is verified only once per integration: the same result for every record."""

    def __init__(self, verifier):
        self._verifier = verifier
        self._done = {}

    def verify(self, revision, proposal_rev, base_rev):
        key = revision_key(revision)
        if key not in self._done:
            try:
                self._done[key] = (self._verifier.verify(revision, proposal_rev, base_rev), None)
            except VerificationError as exc:
                self._done[key] = (None, exc)
        result, error = self._done[key]
        if error is not None:
            raise error
        return result


def _authority(
    touched,
    effects,
    policy_changes,
    revisions,
    base_snap,
    prop_snap,
    verifier,
    prop,
    base,
    now,
    imports,
    mode,
):
    """{ID: [approvals built from verified data]}; blocks if any touched record is not authorized.

    In `decisive` mode, what is not decisive is not evaluated and gets an empty list.
    """
    if not isinstance(revisions, list):
        raise _Lock("INVALID_SCHEMA", "revisions is a list")
    approvals = {}
    single = _SingleCheck(verifier)
    # An approval already admitted in the base does not count again: a declared approval does not carry its own
    # operation, so this prevents reusing it if a record returns to content that was already approved.
    used = {
        e["approval"]["approval_id"]
        for r in base_snap.records.values()
        for e in r.get("events") or []
        if e.get("event_type") == "ratification" and isinstance(e.get("approval"), dict)
    }
    for ident in touched:
        r, c = prop_snap.records[ident], prop_snap.bodies[ident]
        if mode == "decisive" and not is_decisive(ident, r, effects, policy_changes, imports):
            approvals[ident] = []
            continue
        approvable_effects, approvable_import = the_approvable(ident, effects, imports)
        res = evaluate(
            r,
            c,
            approvable_effects,
            revisions,
            base_snap,
            single,
            prop,
            base,
            revalidate_at=now,
            policy_change=ident in policy_changes,
            import_=approvable_import,
        )
        if not res["authorized"]:
            raise _Lock(res["code"], f"{ident}: integration not authorized", authority=res)
        repeated = sorted({a["approval_id"] for a in res["approvals"]} & used)
        if repeated:
            raise _Lock(
                "STALE_APPROVAL", f"{ident}: the approval {repeated[0]} was already used in another integration"
            )
        approvals[ident] = res["approvals"]
    return approvals


def is_decisive(ident, record, effects, policy_changes, imports):
    """Whether touching this record in this operation decides something (`decisive` mode)."""
    return bool(decisive_reasons(ident, record, effects, policy_changes, imports))


def decisive_reasons(ident, record, effects, policy_changes, imports):
    """Why touching this record in this operation decides something; empty if it decides nothing."""
    type_, reasons = record.get("type"), []
    if ident in policy_changes:
        reasons.append("it changes the policy: roles, people or access")
    if type_ in DECISIVE_POLICY:
        reasons.append(f"a record of type {type_} changes who decides")
    decisive = DECISIVE.get(type_, set())
    reasons += [
        f"transition to {ef['new_state']}" for ef in effects.get(ident, []) if ef["new_state"] in decisive
    ]
    if ident in imports:
        imp = imports[ident] or {}
        relations = [k for k in DECISIVE_RELATIONS if record.get(k)]
        if relations:
            reasons.append(f"the import declares {', '.join(relations)}")
        reasons += list(imp.get("decisive") or [])
    return reasons


def _detail(approvals):
    """Each approval once, with its proof: with the declared channel, the quote is only recorded here and in the event."""
    views = {}
    for list_ in approvals.values():
        for a in list_:
            views.setdefault(a["approval_id"], {k: v for k, v in a.items() if k != "digest"})
    return [views[k] for k in sorted(views)]


def _event(op, n, now, type_, actor=ACTOR, **fields):
    return {
        "event_id": f"{op}-{n}",
        "event_type": type_,
        "actor": actor,
        "recorded_at": now,
        "valid_from": fields.pop("valid_from", now),
        "reason": f"integration {op}",
        "event_evidence": fields.pop("event_evidence", {"mechanism": "local-integrator", "proof": op}),
        **fields,
    }


def _materialize(
    op,
    now,
    touched,
    effects,
    approvals,
    mut,
    prop_snap,
    imports,
    base,
    mode="all",
    actor=ACTOR,
    pending_approval=False,
):
    """Final records with the events the integration admits.

    The ratification is recorded where there are effects or a policy change; in the others, the authorization of the
    integration stays in the `Reviews` trailer of the commit. In `decisive` mode, also where the import is decisive.
    Each event carries the operation actor; the ratification also carries the approver.

    With `pending_approval` (the approval package), the approvals do not exist yet: the ratification before an
    acceptance, the only thing of the final record that depends on them, is not required.
    """
    finals, n = {}, 0
    ratify = set(effects) | set(mut["policy_changes"])
    if mode == "decisive":
        ratify = {i for i in touched if approvals.get(i)}
    for ident in touched:
        r = copy.deepcopy(prop_snap.records[ident])
        latest = max(
            (instant(e["recorded_at"]) for e in r.get("events") or [] if e.get("recorded_at")), default=None
        )
        if latest is not None and instant(now) < latest:
            raise _Lock("UNKNOWN_RESULT", "the integrator clock is behind the last admitted event")
        events = list(r.get("events") or [])
        if ident in imports:
            n += 1
            imp = imports[ident]
            events.append(
                _event(
                    op,
                    n,
                    now,
                    "import",
                    actor,
                    valid_from=imp["valid_from"],
                    previous_state=None,
                    new_state=imp["state"],
                    legacy_state=imp["legacy_state"],
                    provenance={"path": prop_snap.paths[ident], "revision": base},
                    precision=imp["precision"],
                    inherited_authority=imp["inherited_authority"],
                )
            )
            r["state"] = imp["state"]
        elif ident in mut["new"]:
            n += 1
            events.append(
                _event(op, n, now, "creation", actor, previous_state=None, new_state=INITIAL[r["type"]])
            )
        if ident in ratify:
            for ap in approvals[ident]:
                n += 1
                c = ap["proof"]
                text = c.get("summary") or f"{c['repository']}#{c['pull']}/reviews/{c['review_id']}"
                evidence = {"mechanism": c["mechanism"], "proof": text}
                events.append(_event(op, n, now, "ratification", actor, approval=ap, event_evidence=evidence))
        for ef in effects.get(ident, []):
            n += 1
            extra = {"valid_until": ef["valid_until"]} if "valid_until" in ef else {}
            events.append(
                _event(
                    op,
                    n,
                    now,
                    "transition",
                    actor,
                    previous_state=ef["previous_state"],
                    new_state=ef["new_state"],
                    valid_from=ef["valid_from"],
                    **extra,
                )
            )
            r["state"] = ef["new_state"]
        r["events"] = events
        r.pop("status", None)  # projection: views compute it, it is not written
        errors = [
            h
            for h in validate(r, prop_snap.bodies[ident], mode="canonical")
            if h["severity"] == "error" and not (pending_approval and h["code"] == "INSUFFICIENT_AUTHORITY")
        ]
        if errors:
            raise _Lock("INVALID_SCHEMA", f"{ident}: the final record is not canonical", findings=errors)
        finals[ident] = (r, prop_snap.bodies[ident])
    return finals


def _check_final(base_snap, prop_snap, finals):
    regs = {**base_snap.records, **{i: r for i, (r, _) in finals.items()}}
    bodies = {**base_snap.bodies, **{i: c for i, (_, c) in finals.items()}}
    legacy = {i: f for i, f in base_snap.legacy.items() if i not in finals}
    final = Snapshot(regs, "final", bodies, {**base_snap.paths, **prop_snap.paths}, legacy)
    errors = [h for h in validate_snapshot(final) if h["severity"] == "error"]
    if errors:
        raise _Lock(errors[0]["code"], "the final tree is not coherent", findings=errors)
    warnings = []
    for t in sorted(set(_starts(regs)), key=instant):
        try:
            in_final = _conflicts(final, t)
            in_base = _conflicts(base_snap, t)
        except HistoryError as exc:
            raise _Lock(exc.code, str(exc)) from exc
        new = [c for c in in_final if c not in in_base]
        if new:
            raise _Lock("NORMATIVE_CONFLICT", f"normative conflict at {t}", conflicts=new)
        for c in in_final:
            alert = f"previous conflict, not introduced by this operation: {c['clause']} between {', '.join(c['candidates'])}"
            if alert not in warnings:
                warnings.append(alert)
    return final, warnings


_TERM = {
    vocabulary_mod.UNDECLARED: "undeclared term",
    vocabulary_mod.UNDETERMINED: "undetermined term",
    vocabulary_mod.RETIRED: "retired term, no longer in force",
}


def _check_vocabulary(base_snap, final, effects, touched, now):
    """Domain vocabulary in the final tree: its findings, or `Lock`.

    The vocabulary of the final tree is in force, so the decision that defines a term can enter with its first use. An
    effect that takes an entity to `active` blocks (`INVALID_SCHEMA`) if, with the world closed when integrating or at
    the start of validity of that effect, its class is not in force at both cuts: undeclared, undetermined or retired.
    It also blocks an already active entity from changing its class to one not in force when integrating. The rest
    enters with its findings, at the instant of the integration: [{id, field, value, situation, touched}] of the class
    and the scope of each touched record and, if the operation makes a term in use stop being in force, of each entity
    that uses it (`touched` false).
    """
    by_cut = {}

    def at(cut):
        if cut not in by_cut:
            by_cut[cut] = vocabulary_mod.in_force_vocabulary(final, valid_at=cut, known_until=now)
        return by_cut[cut]

    blocks = []
    for ident in touched:
        r = final.records[ident]
        if r.get("type") != "entity":
            continue
        value = r.get("entity_class")
        for ef in effects.get(ident, []):
            if ef["new_state"] != "active":
                continue
            # The proposer chooses the start of validity: dating the effect before the first definition does not open
            # the world. If it is closed when integrating or at that start, the class must be in force at both cuts.
            cuts = (ef["valid_from"], now)
            if not any(at(c)["declared"] for c in cuts):
                continue
            for cut in cuts:
                situation, _ = vocabulary_mod.situation(at(cut), value)
                if situation == vocabulary_mod.OPEN:
                    situation = vocabulary_mod.UNDECLARED
                if situation in _TERM:
                    blocks.append({"id": ident, "value": value, "situation": situation, "valid_at": cut})
                    break
        # An entity that is already active and changes its class goes through no effect: without this check,
        # activating with a declared class and changing it later would activate in two steps with one not in force.
        previous = base_snap.records.get(ident)
        if previous is None or previous.get("state") != "active" or r.get("state") != "active":
            continue
        if previous.get("entity_class") == value or not at(now)["declared"]:
            continue
        situation, _ = vocabulary_mod.situation(at(now), value)
        if situation in _TERM:
            blocks.append({"id": ident, "value": value, "situation": situation, "valid_at": now})
    if blocks:
        b = blocks[0]
        reason = f"{b['id']}: {_TERM[b['situation']]} in entity_class: {b['value']!r} is not in force at {b['valid_at']}"
        doubtful = sorted({t["term"] for v in by_cut.values() for t in v["undetermined"]})
        if doubtful:
            reason += f"; the vocabulary has undetermined definitions: {', '.join(doubtful)}"
        raise _Lock("INVALID_SCHEMA", reason, terms=blocks)
    before = vocabulary_mod.in_force_vocabulary(base_snap, valid_at=now, known_until=now)
    after = at(now)
    records, _ = vocabulary_mod.recorded(final, known_until=now)
    valid_scopes, findings = set(after["scopes"]), []
    for ident, r in records:
        touched_here = ident in touched
        scope = r.get("scope")
        if touched_here and isinstance(scope, str) and scope not in valid_scopes:
            findings.append({"id": ident, "field": "scope", "value": scope, "situation": "no_role", "touched": True})
        if r.get("type") != "entity":
            continue
        value = r.get("entity_class")
        situation, _ = vocabulary_mod.situation(after, value)
        affected = vocabulary_mod.situation(before, value)[0] == vocabulary_mod.CURRENT
        if situation in _TERM and (touched_here or affected):
            findings.append(
                {"id": ident, "field": "entity_class", "value": value, "situation": situation, "touched": touched_here}
            )
    return findings


def vocabulary_warning(finding):
    """One line for the receipt or the package with a finding of `_check_vocabulary`."""
    h = finding
    if h["field"] == "scope":
        return f"{h['id']}: scope {h['value']!r} without any active role covering it"
    use = "" if h["touched"] else "; use affected by this operation"
    return f"{h['id']}: {_TERM[h['situation']]} in entity_class: {h['value']!r}{use}"


def _starts(regs):
    """Instants at which the acceptance of each decision of the tree, new or existing, comes into force.

    The set of decisions in force only grows at those instants, so an overlap shows up at one of them. A date without
    time is checked outside its ambiguity window.
    """
    for r in regs.values():
        if r.get("type") != "decision":
            continue
        for e in r.get("events") or []:
            if (
                e.get("recorded_at")
                and e.get("event_type") in ("transition", "import")
                and e.get("new_state") == "accepted"
            ):
                since = e.get("valid_from")
                if is_instant(since):
                    yield since
                elif is_date(since):
                    yield f"{since}T14:00:00Z"


def _conflicts(snapshot, t):
    decisions = sorted(i for i, r in snapshot.records.items() if r.get("type") == "decision")
    return consolidate(snapshot, decisions, valid_at=t, known_until=None)["conflicts"]


def _write_fingerprints(git, base, folder, written, env):
    """Fingerprints warn, they do not block: if those of the base cannot be read, they are rebuilt from this operation."""
    try:
        previous_ = fingerprints_mod.read_from_revision(git, base, folder)
    except ValueError:
        previous_ = {}
    if not isinstance(previous_, dict):
        previous_ = {}
    content = fingerprints_mod.serialize_fingerprints(fingerprints_mod.updated(previous_, written))
    blob = git("hash-object", "-w", "--stdin", entry=content, extra_env=env)
    git("update-index", "--add", "--cacheinfo", f"100644,{blob},{fingerprints_mod.path_of(folder)}", extra_env=env)


def _write_commit(git, ref, current, prop, op, fingerprint, finals, prop_snap, approvals, mode, actor, folder):
    """Flattened commit on the base (without importing the history of the proposal); None if the CAS fails.

    It updates in the same commit the fingerprints of the written records (`kbol.fingerprints`).
    """
    with tempfile.TemporaryDirectory(prefix="kb-index-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), **_IDENTITY}
        git("read-tree", prop, extra_env=env)
        written = {}
        for ident, (r, c) in sorted(finals.items()):
            text = serialize(r, c, mode="canonical")
            blob = git("hash-object", "-w", "--stdin", entry=text.encode("utf-8"), extra_env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{prop_snap.paths[ident]}", extra_env=env)
            written[ident] = (prop_snap.paths[ident], text)
        _write_fingerprints(git, current, folder, written, env)
        tree = git("write-tree", extra_env=env)
        reviewed = ",".join(sorted({a["approval_id"] for list_ in approvals.values() for a in list_}))
        message = (
            f"kb: integrate {op}\n\n{TRAILER}: {op}\nRequest-Sha256: {fingerprint}\nBase: {current}\nProposal: {prop}\n"
            f"Reviews: {reviewed}\n"
        )
        if mode != "all" or actor != ACTOR:
            message += f"Approval: {mode}\nActor: {actor}\n"
        new = git("commit-tree", tree, "-p", current, entry=message.encode("utf-8"), extra_env=env)
    if git("update-ref", ref, new, current, check=False) != 0:
        return None
    return new
