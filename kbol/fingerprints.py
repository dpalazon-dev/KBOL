"""Fingerprints of integrated records and drift: detect edits made outside the flow.

Local choice (docs/design-choices.md, "Fingerprints and drift"). Integration and bootstrap store in
`<first folder>/_fingerprints.json` the SHA-256 fingerprint of the text of each record they write, with normalized
line endings. `drift` recomputes it for the records with history (those that already went through the integration)
and lists those that do not match or have no fingerprint. It does not block: it warns, so that whoever sees it
compares the record with its last integrated version and proposes the difference through the integration.

With the canonical branch, `commits_outside_flow` also looks at its history: from the first commit of the gate
(integrator or bootstrap), every first-parent commit that changes the records folder must come from the gate. One that
does not is a direct write, which skips the integration. It does not block either.

It is not a signature: whoever edits a record on purpose can recompute its fingerprint. It detects slips, such as a
hand edit that leaves relations unconnected, not attacks. The name avoids `integrity`, which the contract reserves for
sources.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from .snapshot import folders_of, git_environment, load

ARCHIVE = "_fingerprints.json"
# Emails of whoever commits the gate's commits (integrate.EMAIL and bootstrap._BOOTSTRAP_IDENTITY); a test checks
# them, because importing them here would close a cycle with integrate.
GATE_EMAILS = frozenset({"integrator@localhost", "bootstrap@localhost"})


def fingerprint(text):
    """SHA-256 of the text of a record, with line endings normalized to LF."""
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def path_of(folder):
    return f"{folders_of(folder)[0]}/{ARCHIVE}"


def serialize_fingerprints(fingerprints):
    return (json.dumps(dict(sorted(fingerprints.items())), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def read_from_revision(git, revision, folder):
    """The fingerprints stored in a revision; {} if there is no file. `git` is the one of the integration."""
    path = path_of(folder)
    if git("cat-file", "-e", f"{revision}:{path}", check=False) != 0:
        return {}
    return json.loads(git("show", f"{revision}:{path}"))


def updated(previous_, written):
    """The previous fingerprints plus those of the written records ({ID: (path, text)})."""
    result = dict(previous_)
    for ident, (path, text) in written.items():
        result[ident] = {"path": path, "sha256": fingerprint(text)}
    return result


def _git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=git_environment())
    return p.returncode, p.stdout


def drift(root, folder, *, staged=False, branch=None, loaded=None, format=None):
    """{checked, alerts, coverage}: records with history whose fingerprint is missing or does not match.

    It reads the disk or, with `staged`, the git index (what will go into the commit, for pre-commit). With `branch`,
    each alert says where the last integrated version of the record is. `loaded` is the `(snapshot, coverage)` of the
    disk in proposal mode and with legacy records, if the caller already has it; `format`, the legacy format of the
    installation (`migration.format_of`), or the default legacy format if none is given.
    """
    snap, coverage = loaded or load(root, folder, None, mode="proposal", legacy=True, format=format)

    def read(path):
        if staged:
            code, output = _git(root, "show", f":{path}")
            return output if code == 0 else None
        archive = Path(root) / path
        return archive.read_bytes() if archive.is_file() else None

    raw = read(path_of(folder))
    try:
        stored = json.loads(raw) if raw else {}
    except ValueError:
        stored = None
    if not isinstance(stored, dict):
        stored = {}
        if raw:
            coverage = {**coverage, "warnings": [*coverage.get("warnings", []), f"{ARCHIVE} unreadable"]}
    alerts, checked = [], 0
    for ident, r in sorted(snap.records.items()):
        if not r.get("events"):
            continue  # no history: it has not gone through the integration yet
        path = snap.paths[ident]
        text = read(path)
        if text is None:
            continue  # not in the index yet: nothing to compare
        checked += 1
        expected = stored.get(ident)
        reason = None
        if not isinstance(expected, dict) or "sha256" not in expected:
            reason = "no_fingerprint"
        elif expected["sha256"] != fingerprint(text):
            reason = "different"
        if reason:
            alert = {"id": ident, "path": path, "reason": reason}
            if branch:
                alert["last_integrated"] = f"{branch}:{path}"
            alerts.append(alert)
    return {"checked": checked, "alerts": alerts, "coverage": coverage}


def commits_outside_flow(root, folder, branch):
    """{evaluated, from, commits}: first-parent commits of `branch` that change the folder without the gate.

    It only counts from the first commit of the gate: before it there was no integration to skip. An integrator commit
    must carry the `Operation-Id` trailer. If the branch cannot be read or the gate never wrote to it, `evaluated` is
    False and `commits` stays empty: nothing is asserted.
    """
    format = "--format=%H%x00%ce%x00%(trailers:key=Operation-Id,valueonly,separator=%x01)%x00%s"
    code, output = _git(root, "log", "--first-parent", format, "--end-of-options", branch, "--", *folders_of(folder))
    if code != 0:
        return {"evaluated": False, "from": None, "commits": []}
    lines = output.decode("utf-8", "replace").splitlines()
    rows = [line.split("\x00", 3) for line in lines if line.count("\x00") >= 3]
    rows.reverse()  # from oldest to newest
    start = next((i for i, f in enumerate(rows) if f[1] in GATE_EMAILS), None)
    if start is None:
        return {"evaluated": False, "from": None, "commits": []}
    outside = []
    for sha, email, operation, subject in rows[start + 1 :]:
        if email == "bootstrap@localhost" or (email == "integrator@localhost" and operation.strip()):
            continue
        outside.append({"commit": sha, "email": email, "subject": subject})
    return {"evaluated": True, "from": rows[start][0], "commits": outside}
