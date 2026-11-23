"""Loading a snapshot: the KB-DPP profile records of a folder, at a git revision or on disk.

Read only. Generated indexes and readable files whose `type` is not in the profile (legacy format, fixed) are
omitted and counted. An unreadable file (missing header or invalid YAML, text that is not UTF-8) or an invalid
record does not enter and leaves the load partial: it could be a record, so the query is not presented as complete.
A repeated ID excludes all its copies and blocks the load, because choosing one would depend on the order of files.
VAL-02 and VAL-07 (`references.validate_snapshot`) are applied to what was loaded.

With `legacy=True`, records in the legacy format are read separately, as cards from the dry-run migration
(`snapshot.legacy`): they serve to name them in queries during the transition, never as normative.
A legacy ID that repeats one from the profile, or another legacy one, blocks the load like any repeated ID; a legacy
record (with `id` or with a record name) without an ID of legacy shape (`ADR-NNNN`, `QD-nnn`…) is not omitted: it
leaves the load partial. A document with a record `type` but without `id` or record name is omitted. The format is
the default legacy one unless the installation declares its own (`legacy_format`): then it replaces it, and an ID
that does not fit the pattern of its label leaves the load partial.
"""

import os
import subprocess
from pathlib import Path

from .core import FormatError, parse
from .migration import DEFAULT, inspect
from .model import TYPES
from .projection import Snapshot
from .references import validate_snapshot
from .schema import validate

BLOCKING = {"NORMATIVE_CONFLICT", "INVALID_SCHEMA"}
# Variables git needs to work; nothing else is inherited (neither tokens nor GIT_* from the environment).
_ENVIRONMENT = (
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


def git_environment():
    """Minimal environment for git processes: without `KB_GITHUB_TOKEN` or inherited `GIT_*` variables."""
    return {k: v for k, v in os.environ.items() if k.upper() in _ENVIRONMENT}


def _git(root, *args):
    command = ["git", "--literal-pathspecs", "-C", str(root), *args]
    return subprocess.run(command, capture_output=True, check=True, env=git_environment()).stdout


def folders_of(folder):
    """The folders of an installation as a tuple: one, as text, or several, as a list (the first one, the policy)."""
    if isinstance(folder, os.PathLike):
        folder = os.fspath(folder)
    return (folder,) if isinstance(folder, str) else tuple(os.fspath(c) for c in folder)


def _git_files(root, revision, folder):
    paths = []
    for c in folders_of(folder):
        output = _git(root, "ls-tree", "-r", "-z", "--name-only", "--full-name", "--end-of-options", revision, "--", c)
        own = [r for r in output.decode("utf-8").split("\0") if r]
        if not own:
            raise FileNotFoundError(f"{c} does not exist or is empty at {revision}")
        paths += own
    for path in sorted({p for p in paths if p.endswith(".md")}):
        yield path, _git(root, "show", f"{revision}:{path}")


def _disk_files(root, folder):
    paths = set()
    for c in folders_of(folder):
        base = Path(root) / c
        if not base.is_dir():
            raise FileNotFoundError(f"{base} does not exist")
        paths |= set(base.rglob("*.md"))
    for p in sorted(paths):
        yield p.relative_to(root).as_posix(), p.read_bytes()


def _card(report, label, format):
    """The card of a legacy record, from the dry-run migration report; None if it is not a record."""
    if report.get("result") != "proposed" or not format.valid_id(label, report.get("id")):
        return None
    fields = (
        "id",
        "type",
        "path",
        "legacy_state",
        "proposed_state",
        "ambiguities",
        "proposed_relations",
        "inherited_authority",
    )
    return {**{c: report.get(c) for c in fields}, "requires_review": bool(report.get("requires_review"))}


def load(root, folder=".", revision=None, mode="canonical", legacy=False, format=None):
    """(Snapshot, coverage). Without `revision` it reads the disk and says so: it is not a canonical revision.

    `mode` is the validation mode of each record: `canonical` for an integrated revision, `proposal` for the tree
    of a proposal, whose new records do not have events yet.

    `format` is the legacy format the installation declares (`migration.format_of`); None, `migration.DEFAULT`.

    `coverage["state"]` is `complete`, `partial` or `blocked`.
    """
    format = format or DEFAULT
    files = _git_files(root, revision, folder) if revision else _disk_files(root, folder)
    read, paths_by_id = {}, {}
    coverage = {
        "state": "complete",
        "read": 0,
        "omitted": 0,
        "legacy": 0,
        "invalid": [],
        "findings": [],
        "warnings": [],
    }
    cards = {}
    for path, content in files:
        if Path(path).name == "index.md":
            coverage["omitted"] += 1  # generated view, not a record
            continue
        try:
            meta, body = parse(content.decode("utf-8"))
        except UnicodeDecodeError:
            coverage["invalid"].append({"path": path, "reason": "not UTF-8"})
            continue
        except FormatError as exc:
            # An unreadable file could be a record: its absence is not a legitimate absence.
            coverage["invalid"].append({"path": path, "reason": f"unreadable header: {exc}"})
            continue
        if meta.get("type") not in TYPES:
            label = meta.get("type")
            if legacy and label in format.types and ("id" in meta or format.is_record(path)):
                report = inspect(content.decode("utf-8"), path, revision or "disk", format)
                card = _card(report, label, format)
                if card is None:
                    # A legacy record without a valid ID is not omitted: it could be any of them.
                    reason = f"legacy record without a valid id: {meta.get('id')!r}"
                    coverage["invalid"].append({"path": path, "reason": reason})
                    continue
                paths_by_id.setdefault(card["id"], []).append(path)
                cards.setdefault(card["id"], card)
                continue
            coverage["omitted"] += 1
            continue
        errors = [h for h in validate(meta, body, mode=mode) if h["severity"] == "error"]
        if errors:
            coverage["invalid"].append({"path": path, "reason": "; ".join(e["message"] for e in errors[:3])})
            continue
        paths_by_id.setdefault(meta["id"], []).append(path)
        read.setdefault(meta["id"], (meta, body, path))
    records, bodies, path_of, legacy_ok = {}, {}, {}, {}
    for ident, copies in paths_by_id.items():
        if len(copies) > 1:
            coverage["findings"].append(
                {
                    "code": "INVALID_SCHEMA",
                    "path": ident,
                    "message": f"ID repeated in {copies}" + (" (legacy format)" if ident in cards else ""),
                    "severity": "error",
                }
            )
            continue
        if ident in cards:
            legacy_ok[ident] = cards[ident]
        else:
            records[ident], bodies[ident], path_of[ident] = read[ident]
    snapshot = Snapshot(records, revision or "disk", bodies, path_of, legacy_ok)
    coverage["read"] = len(records)
    coverage["legacy"] = len(legacy_ok)
    if legacy_ok:
        coverage["warnings"].append(
            f"{len(legacy_ok)} records in legacy format: they are read as imported without an admitted history "
            "and are not in force"
        )
    coverage["findings"] += validate_snapshot(snapshot)
    errors = [h for h in coverage["findings"] if h["severity"] == "error"]
    if any(h["code"] in BLOCKING for h in errors):
        coverage["state"] = "blocked"
    elif errors or coverage["invalid"]:
        coverage["state"] = "partial"
    if revision is None:
        coverage["warnings"].append("read from disk: may include changes not integrated")
    return snapshot, coverage
