"""CLI `kbol`: every operation returns the contract envelope; the ones not enabled fail closed.

Exit codes: 0 completed, 1 failed, 2 blocked, 3 partial (the query left out records that could change the
result, or examined none).
"""

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

from . import __version__, plain
from . import handoff as handoff_mod
from . import propose as propose_mod
from . import session as session_mod
from . import verify as verify_mod
from .bootstrap import bootstrap_run
from .citations import check as check_citations
from .consolidate import consolidate
from .context import context, present
from .core import FormatError, parse
from .declared import MECHANISM as DECLARED_MECHANISM
from .declared import DeclaredVerifier
from .dependencies import ready
from .digest import digest
from .export import export as export_skills
from .fingerprints import commits_outside_flow
from .fingerprints import drift as drift_mod
from .impact import impact
from .integrate import ACTOR as INTEGRATOR_ACTOR
from .integrate import MODES, integrate
from .integrity import check as check_integrity
from .links import check as check_links
from .links import configuration as links_configuration
from .migration import format_of, inspect_folder
from .package import approval_package
from .package import present as present_approval
from .query import query
from .schema import validate
from .search import search
from .snapshot import git_environment, load
from .support import delta, support
from .timeutil import is_instant
from .vocabulary import in_force_vocabulary, review

ENABLED = (
    "validate",
    "migrate",
    "digest",
    "consolidate",
    "ready",
    "impact",
    "handoff",
    "context",
    "verify",
    "query",
    "search",
    "integrate",
    "bootstrap",
    "drift",
    "citations",
    "links",
    "integrity",
    "support",
    "approval_package",
    "vocabulary",
    "session",
    "propose",
    "export_skills",
)
NOT_ENABLED = ("ingest",)
NOT_EVALUATED = ["authority", "validity", "references between records", "event admission"]


def envelope(operation, result, revision=None, warnings=None, scope_=None, not_evaluated=None):
    return {
        "operation": operation,
        "operation_id": str(uuid.uuid4()),
        "revision": revision,
        "valid_at": None,
        "known_until": None,
        "result": result,
        "warnings": warnings or [],
        "coverage": {
            "scope": scope_,
            "truncated": False,
            "not_evaluated": NOT_EVALUATED if not_evaluated is None else not_evaluated,
        },
    }


def _blocked(op, reason, code=None):
    return envelope(op, {"state": "blocked", "code": code, "reason": reason}), 2


def _failed(op, code, reason, scope_):
    return envelope(op, {"state": "failed", "code": code, "reason": reason}, scope_=scope_), 1


def _by_exam(examined, reason, alerts, partial=False):
    """(state, exit code, alerts) of an operation according to what it examined.

    Examining zero elements is not completing: it ends `partial` with the reason among the alerts. A comparison
    that finds no changes has still examined something; the caller decides that when counting.
    """
    if examined == 0:
        return "partial", 3, [*alerts, reason]
    return ("partial", 3, alerts) if partial else ("completed", 0, alerts)


def _load_coverage(coverage):
    """Coverage fields of a record load that the envelope exposes."""
    return {
        "records_read": coverage["read"],
        "omitted": coverage["omitted"],
        "invalid": coverage["invalid"],
        "legacy": coverage["legacy"],
        "truncated": coverage["state"] != "complete",
    }


def run(args):
    op = args.operation
    if op in NOT_ENABLED:
        return _blocked(op, "capability not enabled in this version")
    if not args.path:
        return _blocked(op, "the path is missing")
    if op == "export_skills":
        return _export_skills(args)
    path = Path(args.path)
    if not path.exists():
        return _failed(op, "MISSING_REFERENCE", f"does not exist: {args.path}", args.path)
    if op == "migrate":
        if not args.revision:
            return _blocked(op, "the dry-run migration needs --revision")
        format, failure = _format(op, args)
        if failure:
            return failure
        res = inspect_folder(path, args.revision, format)
        state, code, alerts = _by_exam(
            res["summary"]["proposed"], f"no legacy record in {args.path}: is it the right folder?", []
        )
        return envelope(op, {"state": state, **res}, args.revision, alerts, scope_=args.path), code
    if op in ("consolidate", "ready", "query", "support", "vocabulary", "search"):
        return _query(op, args)
    if op == "impact":
        return _impact(args)
    if op == "links":
        return _links(args)
    if op == "integrity":
        return _integrity(args)
    if op == "handoff":
        return _handoff(args)
    if op == "context":
        return _context(args)
    if op == "verify":
        return _verify(args)
    if op == "integrate":
        return _integrate(args)
    if op == "bootstrap":
        return _bootstrap(args)
    if op == "drift":
        return _drift(args)
    if op == "citations":
        return _citations(args)
    if op == "approval_package":
        return _approval_package(args)
    if op == "session":
        return _session(args)
    if op == "propose":
        return _propose(args)
    try:
        record, body = parse(path.read_text(encoding="utf-8"))
    except OSError as exc:  # a folder or an unreadable file is not a record
        return _failed(op, "MISSING_REFERENCE", f"could not read {args.path}: {exc}", args.path)
    except (FormatError, UnicodeDecodeError) as exc:
        return _failed(op, "INVALID_SCHEMA", str(exc), args.path)
    if op == "validate":
        findings = validate(record, body, mode=args.mode)
        errors = [h for h in findings if h["severity"] == "error"]
        alerts = [f"{h['path']}: {h['message']}" for h in findings if h["severity"] != "error"]
        state = "failed" if errors else "completed"
        return envelope(op, {"state": state, "errors": errors}, args.revision, alerts, args.path), int(bool(errors))
    errors = [h for h in validate(record, body) if h["severity"] == "error"]
    if errors:
        return envelope(op, {"state": "failed", "code": "INVALID_SCHEMA", "errors": errors}, scope_=args.path), 1
    try:
        effects = _read_json(args.effects) if args.effects else []
        value = digest(record, body, effects)
    except (OSError, ValueError) as exc:
        return _failed(op, "INVALID_SCHEMA", str(exc), args.path)
    result = {"state": "completed", "digest": value}
    return envelope(op, result, args.revision, scope_=args.path, not_evaluated=["authority", "validity"]), 0


def _handoff(args):
    """Handoff of a task; with --save, it first saves the handoff given in that JSON (local state, not knowledge)."""
    if not args.task:
        return _blocked("handoff", "handoff needs --task")
    try:
        if args.save:
            handoff_mod.save(
                args.path, args.task, _read_json(args.save), canonical_branch=args.canonical_branch or "main"
            )
        res = handoff_mod.handoff(args.path, args.task, canonical_branch=args.canonical_branch or "main")
    except (OSError, ValueError) as exc:
        return _failed("handoff", "INVALID_SCHEMA", str(exc), args.path)
    not_evaluated = ["checks not run by the handoff", "what was never saved"]
    return envelope(
        "handoff", {"state": "completed", **res}, res["git"].get("head"), scope_=args.path, not_evaluated=not_evaluated
    ), 0


def _verify(args):
    """Runs a check declared in the installation and records it in the task handoff."""
    missing = [
        n
        for n, v in (
            ("--task", args.task),
            ("--installation", args.installation),
            ("--check", args.check),
        )
        if not v
    ]
    if missing:
        return _blocked("verify", f"verify needs {', '.join(missing)}")
    try:
        installation, provenance = verify_mod.controlled_installation(args.path, args.installation)
        res = verify_mod.run(
            args.path,
            args.task,
            installation,
            args.check,
            canonical_branch=args.canonical_branch or "main",
            provenance=provenance,
        )
    except (OSError, ValueError) as exc:
        return _failed("verify", "INVALID_SCHEMA", str(exc), args.path)
    not_evaluated = [
        "isolation of the run",
        "effects outside the working tree",
        "files ignored by git",
        "receipt of the run",
    ]
    alerts = []
    if res["environment_ref"]["external"]:
        alerts.append(
            "the interpreter is not the one in the root .venv: what is installed there as editable may come from another copy"
        )
    # The check result becomes the envelope result: failed stays failed; unknown is partial.
    state, code = {"passed": ("completed", 0), "failed": ("failed", 1)}.get(res["result"], ("partial", 3))
    result = {"state": state, **res}
    if state == "failed":
        # `code` stays the exit code of the checked command: the envelope does not overwrite it.
        result["reason"] = f"check {args.check} failed (code {res['code']})"
    elif state == "partial":
        alerts.append(f"check {res['result']}: " + "; ".join(res["observations"] or ["no observations"]))
    output = envelope("verify", result, res["tested_revision"], alerts, scope_=args.path, not_evaluated=not_evaluated)
    return output, code


def _context(args):
    """Context package of a task (read only); --text presents it for injection into a session."""
    missing = [
        n
        for n, v in (
            ("--task", args.task),
            ("--scope", args.scope),
            ("--installation", args.installation),
            ("--valid-at", args.valid_at),
        )
        if not v
    ]
    if missing:
        return _blocked("context", f"context needs {', '.join(missing)}")
    for name, value in (("--valid-at", args.valid_at), ("--known-until", args.known_until)):
        if value is not None and not is_instant(value):
            return _blocked("context", f"{name} is not an ISO 8601 instant with a time zone", "AMBIGUOUS_TIME")
    try:
        installation = _read_json(args.installation)
        package = context(
            args.path,
            task=args.task,
            goal=args.goal,
            scope=args.scope,
            folder=_folders(args),
            installation=installation,
            valid_at=args.valid_at,
            known_until=args.known_until,
            revision=args.revision,
            budget=args.budget,
            legacy=args.legacy_folder,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return _failed("context", "MISSING_REFERENCE", str(exc), args.path)
    if args.text:
        return present(package), 0 if package["state"] == "completed" else 3
    warnings = package.pop("warnings")
    coverage = package.pop("coverage")
    output = envelope(
        "context",
        package,
        package["revision"],
        warnings,
        f"{args.path}:{args.folder}",
        coverage["not_evaluated"],
    )
    output["coverage"].update({k: coverage[k] for k in ("state", "read", "invalid")})
    output["valid_at"], output["known_until"] = args.valid_at, args.known_until
    return output, 0 if package["state"] == "completed" else 3


def _impact(args):
    """Consumers affected by moving from --base to --revision (or to the disk). Structural: it reads no clock.

    The base is loaded as a canonical revision; the final one, as the tree of a proposal, whose new records have
    no events yet. Without a declared edge there is no computed impact: what is not declared is not seen.
    """
    if not args.base:
        return _blocked("impact", "impact needs --base: the starting revision")
    try:
        base, cob_b = load(args.path, _folders(args), args.base, legacy=True)
        final, cob_f = load(args.path, _folders(args), args.revision, mode="proposal", legacy=True)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _failed("impact", "MISSING_REFERENCE", f"could not read a revision: {exc}", args.path)
    coverages = (cob_b, cob_f)
    scope_ = f"{args.path}:{args.folder}"
    not_evaluated = ["undeclared dependencies", "authenticity of the approvals"]
    if any(c["state"] == "blocked" for c in coverages):
        errors = [h for c in coverages for h in c["findings"] if h["severity"] == "error"]
        result = {
            "state": "blocked",
            "code": errors[0]["code"] if errors else None,
            "reason": "inconsistent snapshot",
            "findings": errors,
        }
        return envelope("impact", result, final.revision, cob_f["warnings"], scope_, not_evaluated), 2
    res = impact(base, final)
    warnings = cob_b["warnings"] + cob_f["warnings"] + res.pop("warnings")
    partial = any(c["state"] == "partial" for c in coverages)
    # No changes is still completed; partial only if the final revision loaded no record.
    state, code, warnings = _by_exam(
        cob_f["read"],
        "the final revision loaded no record: are the folder and the revision right?",
        warnings,
        partial,
    )
    result = {"state": state, **res}
    if partial:
        result["findings"] = cob_b["findings"] + cob_f["findings"]
    output = envelope("impact", result, final.revision, warnings, scope_, not_evaluated)
    output["coverage"].update(
        {
            "records_read": cob_f["read"],
            "invalid": cob_b["invalid"] + cob_f["invalid"],
            "truncated": state == "partial",
        }
    )
    return output, code


def _query(op, args):
    """Read-only queries over a snapshot: the clock and the cuts are explicit inputs.

    `support` with `--before-valid-at` or `--before-known-until` compares two pairs of cuts; the one not given is
    the same as the after one.
    """
    if not args.valid_at:
        return _blocked(op, "--valid-at is required: the query clock is an explicit input")
    instants = (
        ("--valid-at", args.valid_at),
        ("--known-until", args.known_until),
        ("--before-valid-at", args.before_valid_at),
        ("--before-known-until", args.before_known_until),
    )
    for name, value in instants:
        if value is not None and not is_instant(value):
            return _blocked(op, f"{name} is not an ISO 8601 instant with a time zone", "AMBIGUOUS_TIME")
    compare = args.before_valid_at is not None or args.before_known_until is not None
    if compare and op != "support":
        return _blocked(op, "--before-valid-at and --before-known-until only apply to support")
    if op in ("consolidate", "query") and not args.ids:
        return _blocked(op, f"{op} needs --ids")
    if op == "search" and not (args.query or "").strip():
        return _blocked(op, "search needs --query with the text to look for")
    if op == "search" and args.ids:
        return _blocked(op, "search does not take --ids: for a known ID, use query")
    if op == "vocabulary" and args.ids:
        return _blocked(op, "vocabulary reviews the whole base: it does not take --ids")
    folder = args.folder.split(",") if "," in args.folder else args.folder
    format, failure = _format(op, args)
    if failure:
        return failure
    try:
        legacy = args.legacy or op in ("query", "support", "vocabulary", "search")
        snapshot, coverage = load(args.path, folder, args.revision, legacy=legacy, format=format)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _failed(op, "MISSING_REFERENCE", f"could not read the snapshot: {exc}", args.path)
    cuts = {"valid_at": args.valid_at, "known_until": args.known_until}
    unevaluated = []
    if coverage["state"] == "blocked":
        errors = [h for h in coverage["findings"] if h["severity"] == "error"]
        result, code, warnings = (
            {
                "state": "blocked",
                "code": errors[0]["code"],
                "reason": "inconsistent snapshot",
                "findings": errors,
            },
            2,
            coverage["warnings"],
        )
    else:
        if op == "query":
            res = query(snapshot, args.ids, **cuts)
        elif op == "search":
            include = [_INCLUDE[x] for x in args.include]
            res = search(snapshot, args.query, **cuts, include=include, limit=args.limit)
        elif op == "support" and compare:
            before = {
                "valid_at": args.before_valid_at or args.valid_at,
                "known_until": args.before_known_until or args.known_until,
            }
            res = delta(snapshot, before, cuts, args.ids or None)
        elif op == "support":
            res = support(snapshot, **cuts, ids=args.ids or None)
        elif op == "consolidate":
            res = consolidate(snapshot, args.ids, **cuts)
        elif op == "vocabulary":
            res = _vocabulary(snapshot, cuts)
            unevaluated = res.pop("not_evaluated")
        else:
            res = ready(snapshot, **cuts)
        warnings = coverage["warnings"] + res.pop("warnings")
        # A requested legacy decision is not resolved: it is named, but it is not in force (compatible reading). A
        # query by ID that does not find the canonical record is not complete either.
        non_canonical = [x for x in res.get("results", []) if x["found"] != "canonical"]
        missing = res.get("missing", [])
        partial = coverage["state"] == "partial" or bool(res.get("legacy")) or bool(non_canonical) or bool(missing)
        warnings += [f"{i}: not in the base" for i in missing]
        if op == "ready":
            examined, reason = res["milestones_examined"], "no milestone examined in the folder"
        elif op == "support":
            examined, reason = (
                res["records_examined"],
                "no record examined: are the folder and the IDs right?",
            )
        elif op == "vocabulary":
            examined, reason = res["records_examined"], "no record examined in the folder"
        elif op == "search":
            examined, reason = res["examined"], "no record examined: are the folder and the revision right?"
        else:
            examined, reason = coverage["read"], "no record read: are the folder and the revision right?"
        state, code, warnings = _by_exam(examined, reason, warnings, partial)
        result = {"state": state, **res}
        if state == "partial":
            result["findings"] = coverage["findings"]
    not_evaluated = ["authenticity of the approvals", "integrity of the sources"]
    if op == "support":
        # Reports and does not block: a broken support does not change the exit code.
        not_evaluated += ["semantic backing of the supports", "undeclared supports"]
    if op == "search":
        not_evaluated += ["semantic similarity: the search is lexical", "records in legacy format"]
    if op in ("query", "consolidate", "search"):
        not_evaluated += ["undeclared supersessions: lexical hints only"]
    if op == "vocabulary":
        # Reports and does not block: an undeclared term does not change the exit code.
        not_evaluated += unevaluated
    output = envelope(op, result, snapshot.revision, warnings, f"{args.path}:{args.folder}", not_evaluated)
    output["valid_at"], output["known_until"] = args.valid_at, args.known_until
    output["coverage"].update(_load_coverage(coverage))
    if op == "search" and result.get("truncated"):
        output["coverage"]["truncated"] = True
    if args.plain and result.get("state") in ("completed", "partial"):
        return plain.present(op, output, snapshot, with_ids=args.with_ids), code
    return output, code


_INCLUDE = {"proposals": "proposal", "not_in_force": "not_in_force"}


def _vocabulary(snapshot, cuts):
    """The domain vocabulary in force at the cuts and its uses in the base.

    Legacy records are not reviewed: they are named, and the query ends `partial`.
    """
    voc = in_force_vocabulary(snapshot, **cuts)
    rev = review(snapshot, voc, known_until=cuts["known_until"])
    legacy = [snapshot.legacy[i] for i in sorted(snapshot.legacy)]
    alerts = [f"{f['id']}: legacy format; its class and scope are not reviewed" for f in legacy]
    return {
        "cuts": voc["cuts"],
        "declared": voc["declared"],
        "classes": voc["classes"],
        "aliases": voc["aliases"],
        "scopes": voc["scopes"],
        "undeclared": rev["undeclared"],
        "undetermined": rev["undetermined"],
        "retired_in_use": rev["retired_in_use"],
        "scopes_without_role": rev["scopes_without_role"],
        "records_examined": rev["records_examined"],
        "legacy": legacy,
        "not_evaluated": rev["coverage"],
        "warnings": voc["warnings"] + rev["warnings"] + alerts,
    }


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_BRANCH_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")


def _format(op, args):
    """(legacy format declared by `--installation`, None); without it, the default legacy format. If invalid, (None, output)."""
    try:
        return format_of(_read_json(args.installation) if args.installation else {}), None
    except OSError as exc:
        return None, _failed(op, "MISSING_REFERENCE", f"could not read the installation: {exc}", args.installation)
    except ValueError as exc:
        return None, _failed(op, "INVALID_SCHEMA", f"malformed installation: {exc}", args.installation)


def _folders(args):
    return args.folder.split(",") if "," in args.folder else args.folder


def _missing(op, pairs):
    missing = [name for name, value in pairs if not value]
    return _blocked(op, f"{op} needs {', '.join(missing)}") if missing else None


def _git_cli(path, *args):
    p = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, env=git_environment())
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _up_to_date_with_remote(op, path, remote, branch, base):
    """Fetches the remote and requires the base and the local branch to be its head; None if they are. Never pushes."""
    if not _NAME.fullmatch(remote) or not _BRANCH_NAME.fullmatch(branch) or ".." in branch:
        return _blocked(op, "--remote and --canonical-branch are git names, without options or paths")
    code, _, error = _git_cli(
        path, "fetch", "--quiet", "--end-of-options", remote, f"refs/heads/{branch}:refs/remotes/{remote}/{branch}"
    )
    if code != 0:
        return _failed(op, "UNKNOWN_RESULT", f"could not fetch {remote}/{branch}: {error}", path)
    _, head, _ = _git_cli(path, "rev-parse", "--verify", f"refs/remotes/{remote}/{branch}^{{commit}}")
    _, local, _ = _git_cli(path, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    if head != base:
        reason = f"{remote}/{branch} is at {head[:12]}, not at the base {base[:12]}: redo the proposal on top of it"
        return _blocked(op, reason, "BASE_CHANGED")
    if local != head:
        return _blocked(
            op, f"the local branch {branch} is not up to date with {remote}: update it first", "BASE_CHANGED"
        )
    return None


def _integrate(args):
    """Integrates with declared approvals; with --remote, first checks that the remote has not moved on.

    With `--approval decisive`, approvals are optional: only what is decisive needs them.
    """
    decisive = args.approval == "decisive"
    error = _missing(
        "integrate",
        (
            ("--canonical-branch", args.canonical_branch),
            ("--operation-id", args.operation_id),
            ("--base", args.base),
            ("--proposal", args.proposal),
            ("--approvals", args.approvals or decisive),
            ("--actor", args.actor or not decisive),
            ("--receipts", args.receipts),
        ),
    )
    if error:
        return error
    try:
        approvals = _read_json(args.approvals) if args.approvals else []
    except (OSError, ValueError) as exc:
        return _failed("integrate", "INVALID_SCHEMA", f"unreadable approvals: {exc}", args.approvals)
    if (
        not isinstance(approvals, list)
        or (not approvals and not decisive)
        or any(not isinstance(a, dict) or a.get("mechanism") != DECLARED_MECHANISM for a in approvals)
    ):
        return _blocked("integrate", "the CLI integrates with a list of declared approvals (kbol.declared)")
    if args.remote:
        error = _up_to_date_with_remote("integrate", args.path, args.remote, args.canonical_branch, args.base)
        if error:
            return error
    receipt = integrate(
        args.path,
        branch=args.canonical_branch,
        folder=_folders(args),
        operation_id=args.operation_id,
        expected_base=args.base,
        proposal_rev=args.proposal,
        revisions=approvals,
        verifier=DeclaredVerifier(args.path),
        receipts=args.receipts,
        approval=args.approval or "all",
        actor=args.actor or INTEGRATOR_ACTOR,
    )
    code = {"integrated": 0, "blocked": 2}.get(receipt.get("state"), 1)
    return envelope("integrate", receipt, receipt.get("integrated_revision"), scope_=args.path), code


def _approval_package(args):
    """Approval package of a proposal (read only); --text presents it to the person.

    Blocked with the gate code if integration would block; partial if it touches no record.
    """
    op = "approval_package"
    error = _missing(
        op,
        (
            ("--operation-id", args.operation_id),
            ("--base", args.base),
            ("--proposal", args.proposal),
            ("--valid-at", args.valid_at),
        ),
    )
    if error:
        return error
    try:
        package = approval_package(
            args.path,
            folder=_folders(args),
            operation_id=args.operation_id,
            base=args.base,
            proposal=args.proposal,
            valid_at=args.valid_at,
            known_until=args.known_until,
        )
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _failed(op, "MISSING_REFERENCE", f"could not read a revision: {exc}", args.path)
    scope_ = f"{args.path}:{args.folder}"
    if package["state"] == "blocked":
        output, code = envelope(op, package, args.proposal, scope_=scope_), 2
    else:
        state, code, alerts = _by_exam(
            len(package["records"]),
            "the proposal changes no record: there is nothing to approve",
            package["warnings"],
        )
        package["warnings"] = alerts
        result = {k: v for k, v in package.items() if k not in ("warnings", "not_evaluated")}
        output = envelope(op, {**result, "state": state}, args.proposal, alerts, scope_, package["not_evaluated"])
        output["valid_at"], output["known_until"] = args.valid_at, args.known_until
    if args.text:
        return present_approval(package), code
    return output, code


def _propose(args):
    """Proposes files of the working tree from the integrator clone; by default a dry run that changes nothing.

    The branch, the folders, the approval mode, the remote and the receipts are set by the installation, read from
    HEAD. Exits with 3 if the dry run needs an approval that was not given: the result carries the package (--text
    presents it).
    """
    op = "propose"
    error = _missing(
        op,
        (("--installation", args.installation), ("--operation-id", args.operation_id), ("--files", args.files)),
    )
    if error:
        return error
    if args.canonical_branch or args.folder != "." or args.approval or args.receipts or args.remote:
        return _blocked(
            op, "the branch, folders, approval mode, remote and receipts of propose are set by the installation"
        )
    try:
        installation, _ = verify_mod.controlled_installation(args.path, args.installation)
        res = propose_mod.propose(
            args.path,
            installation,
            operation_id=args.operation_id,
            files=args.files,
            actor=args.actor,
            effects=_read_json(args.effects) if args.effects else None,
            imports=_read_json(args.imports) if args.imports else None,
            approvals=_read_json(args.approvals) if args.approvals else None,
            until=args.until,
            valid_at=args.valid_at,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return _failed(op, "INVALID_SCHEMA", str(exc), args.path)
    states = {"dry_run_done": 0, "integrated": 0, "pushed": 0, "blocked": 2, "pending_approval": 3}
    code = states.get(res.get("state"), 1)
    if args.text and "package" in res:
        return present_approval(res["package"]), code
    not_evaluated = [
        "authenticity of the declared approvals",
        "that the working tree starts from the head of the canonical branch",
        "isolation of the later steps",
    ]
    return envelope(op, res, res.get("integrated_revision"), scope_=args.path, not_evaluated=not_evaluated), code


def _bootstrap(args):
    """Declared bootstrap of the root. The GitHub one is still available as a library."""
    error = _missing(
        "bootstrap",
        (
            ("--canonical-branch", args.canonical_branch),
            ("--operation-id", args.operation_id),
            ("--base", args.base),
            ("--person", args.person),
            ("--roles", args.roles),
            ("--declaration", args.declaration),
            ("--receipts", args.receipts),
        ),
    )
    if error:
        return error
    try:
        declaration = _read_json(args.declaration)
    except (OSError, ValueError) as exc:
        return _failed("bootstrap", "INVALID_SCHEMA", f"unreadable declaration: {exc}", args.declaration)
    receipt = bootstrap_run(
        args.path,
        branch=args.canonical_branch,
        folder=_folders(args),
        expected_base=args.base,
        person=args.person,
        roles=args.roles.split(","),
        declaration=declaration,
        receipts=args.receipts,
        operation_id=args.operation_id,
    )
    code = {"bootstrapped": 0, "blocked": 2}.get(receipt.get("state"), 1)
    return envelope("bootstrap", receipt, receipt.get("integrated_revision"), scope_=args.path), code


def _export_skills(args):
    """Writes the packaged skills under the path, with the KBOL version."""
    if args.skills is not None and not args.skills:
        return _blocked("export_skills", "--skills without names: nothing to export")
    try:
        res = export_skills(args.path, __version__, args.skills)
    except (OSError, ValueError) as exc:
        return _failed("export_skills", "MISSING_REFERENCE", f"could not export: {exc}", args.path)
    if res["state"] == "blocked":
        return envelope("export_skills", res, scope_=args.path, not_evaluated=[]), 2
    alerts = [f"{r} was already up to date" for r in res["equal"]]
    return envelope("export_skills", res, warnings=alerts, scope_=args.path, not_evaluated=[]), 0


def _drift(args):
    """Records with history edited outside the flow. Warns and ends with 0: it does not block."""
    try:
        res = drift_mod(args.path, _folders(args), staged=args.staged, branch=args.canonical_branch)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _failed("drift", "MISSING_REFERENCE", f"could not read the folder: {exc}", args.path)
    alerts = [
        f"{a['id']} ({a['path']}): {'differs from what was integrated' if a['reason'] == 'different' else 'no fingerprint'}"
        for a in res["alerts"]
    ]
    coverage = res["coverage"]
    if coverage["state"] == "blocked":
        errors = [h for h in coverage["findings"] if h["severity"] == "error"]
        block = {"state": "blocked", "code": errors[0]["code"], "reason": "inconsistent snapshot"}
        return envelope("drift", {**block, "findings": errors}, scope_=args.path), 2
    # Finding drift warns and does not block. Having checked no record, or having left out one that could not
    # be read, is partial: the state does not contradict the coverage.
    state, code, alerts = _by_exam(
        res["checked"],
        "no record with history checked: are the folder and the revision right?",
        coverage["warnings"] + alerts,
        coverage["state"] != "complete",
    )
    result = {"state": state, "checked": res["checked"], "alerts": res["alerts"]}
    not_evaluated = ["records without history", "who made the edit"]
    # With the canonical branch, also the commits that change records without going through the gate.
    # They warn and do not block, like drift.
    if args.canonical_branch and not args.staged:
        outside = commits_outside_flow(args.path, _folders(args), args.canonical_branch)
        result["commits_outside_flow"] = outside["commits"]
        if outside["evaluated"]:
            not_evaluated.append("commits of the canonical branch before the first one of the gate")
            alerts = alerts + [
                f"{c['commit'][:12]} ({c['email']}): changes records without going through the gate"
                for c in outside["commits"]
            ]
        else:
            not_evaluated.append("commits of the canonical branch: unreadable or without gate commits")
    else:
        not_evaluated.append("commits of the canonical branch")
    output = envelope("drift", result, warnings=alerts, scope_=args.path, not_evaluated=not_evaluated)
    output["coverage"].update(_load_coverage(coverage))
    return output, code


def _links(args):
    """Internal links of the Markdown documents of the root. A broken link is `failed`; declared debt is not."""
    try:
        exclude, debt = links_configuration(_read_json(args.installation) if args.installation else {})
    except OSError as exc:
        return _failed("links", "MISSING_REFERENCE", f"could not read the installation: {exc}", args.installation)
    except ValueError as exc:
        return _failed("links", "INVALID_SCHEMA", f"malformed installation: {exc}", args.installation)
    folders = _folders(args)
    try:
        res = check_links(args.path, folders if isinstance(folders, list) else [folders], exclude, debt)
    except (OSError, ValueError) as exc:
        return _failed("links", "MISSING_REFERENCE", str(exc), args.path)
    alerts = [f"{r}: could not be read as UTF-8; its links were not reviewed" for r in res["unreadable"]]
    alerts += [f"{d['document']}: «{d['target']}» no longer fails: remove it from the debt" for d in res["debt_left"]]
    not_evaluated = [
        "external links",
        "targets outside the root",
        "fragments of files that are not Markdown",
        "documents excluded by the installation",
    ]
    scope_ = f"{args.path}:{args.folder}"
    if res["errors"]:
        reason = f"{len(res['errors'])} link(s) or anchor(s) that do not resolve"
        result = {"state": "failed", "code": "MISSING_REFERENCE", "reason": reason, **res}
        return envelope("links", result, warnings=alerts, scope_=scope_, not_evaluated=not_evaluated), 1
    state, code, alerts = _by_exam(
        res["documents"],
        "no Markdown document reviewed: are the root and the folder right?",
        alerts,
        bool(res["unreadable"]),
    )
    return envelope("links", {"state": state, **res}, warnings=alerts, scope_=scope_, not_evaluated=not_evaluated), code


def _integrity(args):
    """Integrity of the sources. An altered or missing source is `failed`; an unchecked one, `partial`."""
    store = Path(args.store) if args.store else None
    try:
        res = check_integrity(args.path, _folders(args), store)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _failed("integrity", "MISSING_REFERENCE", f"could not read the folder: {exc}", args.path)
    coverage = res["coverage"]
    if coverage["state"] == "blocked":
        errors = [h for h in coverage["findings"] if h["severity"] == "error"]
        block = {"state": "blocked", "code": errors[0]["code"], "reason": "inconsistent snapshot"}
        return envelope("integrity", {**block, "findings": errors}, scope_=args.path), 2
    rows, count = res["sources"], res["count"]
    alerts = coverage["warnings"] + [
        f"{f['id']} ({f['location']}): {f['state']}: {f['cause']}" for f in rows if f["state"] != "matches"
    ]
    broken = count["altered"] + count["missing"]
    if broken:
        # The code gives the cause and the state the operational result: broken is not the same as unchecked.
        reason = f"{broken} source(s) with altered or missing content"
        result, code = {"state": "failed", "code": "INTEGRITY_BROKEN", "reason": reason}, 1
    else:
        unchecked = bool(count["unchecked"])
        state, code, alerts = _by_exam(
            len(rows),
            "no source in the folders: are they spelled right?",
            alerts,
            unchecked or coverage["state"] != "complete",
        )
        result = {"state": state}
        if unchecked:
            result["code"] = "INTEGRITY_UNCHECKED"
    not_evaluated = ["last valid check of each source", "validity of the source", "quality of the derivations"]
    output = envelope(
        "integrity",
        {**result, "sources": rows, "count": count},
        warnings=alerts,
        scope_=f"{args.path}:{args.folder}",
        not_evaluated=not_evaluated,
    )
    output["coverage"].update(_load_coverage(coverage))
    return output, code


def _citations(args):
    """Resolves the citations (`sources`) of the records. Exit 3 if any is broken or inconsistent."""
    store = Path(args.store) if args.store else None
    folders = _folders(args)
    try:
        res = check_citations(Path(args.path), folders if isinstance(folders, list) else [folders], store)
    except OSError as exc:
        return _failed("citations", "MISSING_REFERENCE", f"could not read the folder: {exc}", args.path)
    bad = res["count"]["broken"] + res["count"]["inconsistent"]
    alerts = [
        f"{f['record']}#{f['source']}: {f['state']}: {f['reason']}" for f in res["rows"] if f["state"] != "resolved"
    ]
    state, code, alerts = _by_exam(
        len(res["rows"]), "no citation found in the folders: are they spelled right?", alerts, bool(bad)
    )
    not_evaluated = ["semantic backing of the citation", "validity of the source", "originals missing from the store"]
    return envelope(
        "citations", {"state": state, **res}, warnings=alerts, scope_=args.path, not_evaluated=not_evaluated
    ), code


def _session(args):
    """Commands for the hooks of an installation: `--event` start, stop or commit. With --text, only what the
    adapter injects into the session; a failure of the command always comes out as an envelope."""
    error = _missing("session", (("--event", args.event), ("--installation", args.installation)))
    if error:
        return error
    try:
        res = session_mod.run(
            args.event,
            args.path,
            args.installation,
            task=args.task,
            valid_at=args.valid_at,
            origin=args.origin,
            paths=args.paths,
        )
    except ValueError as exc:
        return _failed("session", "INVALID_SCHEMA", str(exc), args.path)
    except (OSError, subprocess.CalledProcessError) as exc:
        return _failed("session", "MISSING_REFERENCE", str(exc), args.path)
    if args.text:
        return res["text"], res["code"]
    output = envelope("session", res["result"], res["revision"], res["warnings"], res["scope"], res["not_evaluated"])
    output["valid_at"] = res["valid_at"]
    output["coverage"].update(res["coverage"])
    return output, res["code"]


def _without_repeats(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"repeated JSON key in {keys}")
    return dict(pairs)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_without_repeats)


def main(argv=None):
    p = argparse.ArgumentParser(prog="kbol", description="KBOL: KB-DPP core")
    p.add_argument("--version", action="version", version=f"kbol {__version__}")
    p.add_argument("operation", choices=ENABLED + NOT_ENABLED)
    p.add_argument("path", nargs="?")
    p.add_argument("--revision")
    p.add_argument("--skills", nargs="*", default=None, help="skills to export; all if none given (export_skills)")
    p.add_argument("--mode", choices=["proposal", "canonical", "exchange"], default="proposal")
    p.add_argument("--effects", help="JSON with the requested effects (digest and propose)")
    p.add_argument("--valid-at", dest="valid_at", help="domain instant queried, with a time zone")
    p.add_argument("--known-until", dest="known_until", help="cut of the admitted history, with a time zone")
    p.add_argument("--folder", default=".", help="records folder; several, separated by commas")
    p.add_argument("--ids", nargs="*", default=[], help="IDs to consolidate, query or, in support, examine")
    p.add_argument("--query", help="text to look for (search)")
    p.add_argument("--include", nargs="*", default=[], choices=sorted(_INCLUDE), help="search: also show these classes")
    p.add_argument("--limit", type=int, default=10, help="candidates that search shows")
    p.add_argument("--plain", action="store_true", help="query, consolidate and search: answer in plain prose")
    p.add_argument("--with-ids", dest="with_ids", action="store_true", help="with --plain, show the IDs and anchors")
    p.add_argument("--before-valid-at", dest="before_valid_at", help="support: domain instant of the first cut")
    p.add_argument("--before-known-until", dest="before_known_until", help="support: knowledge of the first cut")
    p.add_argument("--base", help="starting revision (impact, integrate, approval_package)")
    p.add_argument("--task", help="task id (handoff and context)")
    p.add_argument("--save", help="JSON with the handoff to save before reading it")
    p.add_argument(
        "--canonical-branch",
        dest="canonical_branch",
        help="canonical branch: required in integrate and bootstrap; in handoff, main if not given",
    )
    p.add_argument("--approval", choices=MODES, help="what requires approval (integrate); all if not given")
    p.add_argument("--actor", help="actor of the operation, who signs its events (integrate)")
    p.add_argument("--goal", help="goal of the task; if missing, the one in the handoff")
    p.add_argument("--scope", help="scope of the context package")
    p.add_argument(
        "--installation",
        help="JSON with the installation configuration; in queries and migrate, only its legacy_format",
    )
    p.add_argument("--budget", type=int, default=30, help="elements of the context package")
    p.add_argument("--legacy-folder", dest="legacy_folder", help="folder of the legacy format (pending items)")
    p.add_argument("--text", action="store_true", help="present the package as short text")
    p.add_argument("--check", help="id of a check declared in the installation")
    p.add_argument(
        "--operation-id",
        dest="operation_id",
        help="operation_id of an integration, its approval package or a bootstrap",
    )
    p.add_argument("--proposal", help="SHA of the proposed commit (integrate, approval_package)")
    p.add_argument("--approvals", help="JSON with the list of declared approvals (integrate)")
    p.add_argument("--receipts", help="receipts directory, outside the canonical tree")
    p.add_argument("--remote", help="remote the base and the branch must be up to date with (integrate)")
    p.add_argument("--person", help="person of the root (bootstrap)")
    p.add_argument("--roles", help="roles of the root, separated by commas (bootstrap)")
    p.add_argument("--declaration", help="JSON with the root declaration (bootstrap)")
    p.add_argument("--store", help="content-addressed store of originals and representations (citations)")
    p.add_argument("--staged", action="store_true", help="compare the git index, not the disk (drift)")
    p.add_argument("--event", choices=session_mod.EVENTS, help="event of the calling hook (session)")
    p.add_argument("--origin", help="origin of the session start; with compact it adds the task's work in git")
    p.add_argument("--paths", nargs="*", help="paths the validation is limited to (session --event stop)")
    p.add_argument(
        "--legacy",
        action="store_true",
        help="also read the legacy format (the default format or the one --installation declares), apart and not in force",
    )
    p.add_argument("--files", nargs="+", default=[], help="records to propose, relative to the root (propose)")
    p.add_argument("--imports", help="JSON with the imports of the request (propose)")
    p.add_argument(
        "--until",
        choices=propose_mod.UNTIL,
        default="dry_run",
        help="how far propose goes: dry run, integrate in the integrator clone or push to the remote",
    )
    output, code = run(p.parse_intermixed_args(argv))
    sys.stdout.reconfigure(encoding="utf-8")
    print(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
