"""Integrity of the sources: the content at the `location` of each source has its `sha256`.

Contract operation `integrity` («Integrity and update»): for each source record it says whether its content
`matches`, is `altered` or `missing`, or whether the check could not be made (`unchecked`), with the cause. The bytes
are compared as they are, without normalizing line endings. Three forms of location are checked:

- `store:sha256/<fingerprint>`: the object of the content-addressed store that is given;
- `git:<40-character revision>:<path>`: the blob of that path in that revision of the root's repository;
- a path relative to the root: the file of the working tree.

A source is broken (`altered` or `missing`) only when it could be looked at and the content is different or absent.
What could not be looked at is `unchecked`, not an accusation: no store, an object that is not in this machine's
store (the store is local state and is not synchronized), a revision that is not in this clone, an unanchored
revision or a location of another form (a URL, an absolute path).

It saves nothing: each run checks again, and the last valid check of a source is not kept.
"""

import hashlib
import re
import subprocess
from pathlib import Path

from .snapshot import git_environment, load

STATES = ("matches", "altered", "missing", "unchecked")
BROKEN_F = ("altered", "missing")
_STORE = re.compile(r"store:sha256/([0-9a-f]{64})")
_GIT = re.compile(r"git:([^:]+):(.+)", re.S)
_REVISION = re.compile(r"[0-9a-f]{40}")
_SCHEMA = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")  # https:, s3:; a single letter would be a Windows drive
_UNIT = re.compile(r"[A-Za-z]:[\\/]")


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=git_environment())


def _compare(data, sha256, what):
    if hashlib.sha256(data).hexdigest() == sha256:
        return "matches", None
    return "altered", f"{what} does not have the source's fingerprint"


def _in_store(fingerprint, sha256, store):
    if fingerprint != sha256:
        return "altered", "the location names a fingerprint that is not the source's"
    if store is None:
        return "unchecked", "no store was given"
    object_ = Path(store) / "sha256" / fingerprint
    if not object_.is_file():
        return "unchecked", "the object is not in this machine's store"
    try:
        data = object_.read_bytes()
    except OSError as exc:
        return "unchecked", f"the store object could not be read: {exc}"
    return _compare(data, sha256, "the store object")


def _in_git(root, revision, path, sha256):
    if not _REVISION.fullmatch(revision):
        return "unchecked", "the revision is not anchored: the full SHA of a commit is needed"
    if _git(root, "cat-file", "-e", f"{revision}^{{commit}}").returncode != 0:
        shallow = _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true"
        where = "shallow clone" if shallow else "it may need fetching"
        return "unchecked", f"revision {revision[:12]} is not in this clone ({where})"
    # `cat-file blob` and not `show`: for a folder, `show` would give its listing and the source would come out altered.
    blob = _git(root, "cat-file", "blob", f"{revision}:{path}")
    if blob.returncode != 0:
        return "missing", f"{path} is not a file of revision {revision[:12]}"
    return _compare(blob.stdout, sha256, f"{path} in revision {revision[:12]}")


def _on_disk(root, location, sha256):
    root = Path(root).resolve()
    file = (root / location).resolve()
    if root != file and root not in file.parents:
        return "unchecked", "the location leaves the root"
    if not file.is_file():
        return "missing", f"{location} does not exist in the working tree"
    try:
        data = file.read_bytes()
    except OSError as exc:
        return "unchecked", f"{location} could not be read: {exc}"
    return _compare(data, sha256, f"{location} in the working tree")


def check_source(root, source, store=None):
    """(state, cause) of a source; the cause is None if it matches."""
    location, sha256 = source.get("location"), source.get("sha256")
    if not isinstance(location, str) or not location or not isinstance(sha256, str):
        return "unchecked", "the source does not declare location and sha256"
    m = _STORE.fullmatch(location)
    if m:
        return _in_store(m.group(1), sha256, store)
    m = _GIT.fullmatch(location)
    if m:
        return _in_git(root, m.group(1), m.group(2), sha256)
    if _UNIT.match(location) or location.startswith(("/", "\\")):
        return "unchecked", "local absolute path: not a location another machine can check"
    if _SCHEMA.match(location):
        return "unchecked", f"location «{location.split(':', 1)[0]}:» without a check"
    return _on_disk(root, location, sha256)


def check(root, folder, store=None):
    """{sources, count, coverage}: one row per source record in the folders, with its state and its cause.

    It reads the disk, like `drift`: records with history and proposals. A source that does not load (invalid or
    unreadable) stays in the coverage, which is then no longer complete.
    """
    snapshot, coverage = load(root, folder, None, mode="proposal", legacy=True)
    rows = []
    for ident, record in sorted(snapshot.records.items()):
        if record.get("type") != "source":
            continue
        state, cause = check_source(root, record, store)
        rows.append(
            {
                "id": ident,
                "path": snapshot.paths[ident],
                "location": record.get("location"),
                "state": state,
                "cause": cause,
            }
        )
    count = {e: sum(1 for f in rows if f["state"] == e) for e in STATES}
    return {"sources": rows, "count": count, "coverage": coverage}
