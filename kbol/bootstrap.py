"""Bootstrap of the root of trust of an installation (KB-DPP implementation 1.0, "initial root of trust").

The integration requires the authority of the base policy: without an active role that governs the policy, nothing can
activate the first one. The bootstrap breaks that circle once. It activates the roles and the person of the root,
which are already on the canonical branch as proposals without history, with admitted events whose evidence is the
founder's account verified on GitHub (`GET /user` with their own token). From the caller it only takes the IDs: GitHub
gives the account, and the person must be human, declare that account in `identity_ref` and already hold all the roles
of the root.

It refuses if the policy already has an active role with `govern_policy` (the root exists: changes go through the
integration), if any record of the root has events or is not proposed, or if no role of the root governs the policy.
It writes a flattened commit over the base on the canonical branch by compare-and-swap, like the integration, and a
receipt. Limit: without branch protection on the remote, the commit proves no more than its content; it records the
verified account, but does not stop another account with write permission from writing to the branch.
"""

import copy
import re
import tempfile
from pathlib import Path

from .authority import GOVERN, _holds
from .core import serialize
from .events import admitted
from .github import authenticated_account
from .integrate import (
    _BRANCH,
    _OPERATION,
    _SHA,
    TRAILER,
    _canonical_branch,
    _Git,
    _Lock,
    _now,
    _safe_folder,
    _write_fingerprints,
    _write_receipt,
)
from .schema import validate
from .snapshot import load
from .timeutil import is_instant
from .verification import VerificationError

ACTOR = "process:bootstrap"
MECHANISM = "bootstrap-github-user"
# Declared bootstrap: the person declares in a conversation that they are the root; nobody verifies the identity.
DECLARED_MECHANISM = "bootstrap-declared"
_DECLARATION = ("identity", "session", "instant", "quote")
_DECLARED_IDENTITY = re.compile(r"declared:\S+")
# Own identity of the bootstrap commits: they are not mistaken for the integrator's.
_BOOTSTRAP_IDENTITY = {
    "GIT_AUTHOR_NAME": "bootstrap-local",
    "GIT_AUTHOR_EMAIL": "bootstrap@localhost",
    "GIT_COMMITTER_NAME": "bootstrap-local",
    "GIT_COMMITTER_EMAIL": "bootstrap@localhost",
}


def bootstrap_run(
    repo, *, branch, folder, expected_base, person, roles, receipts, operation_id, client=None, declaration=None
):
    """Activates the root and returns the receipt, or a `blocked` result with its code. It does not retry by itself.

    The identity comes through one channel and only one: `client`, verified with GitHub (`GET /user`), or
    `declaration`, declared by the person in a conversation and quoted, not authenticated (design choices,
    "Non-conforming mechanisms").
    """
    try:
        if not isinstance(person, str) or not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            raise _Lock(None, "person is an ID and roles a list of IDs")
        if (client is None) == (declaration is None):
            raise _Lock(None, "the identity of the root comes through one channel and only one: client or declaration")
        return _bootstrap_run(
            _Git(repo), branch, folder, expected_base, person, roles, client, declaration, Path(receipts), operation_id
        )
    except _Lock as b:
        return {"operation_id": operation_id, **b.result}


def _entries(branch, folder, base, op):
    if not isinstance(op, str) or not _OPERATION.fullmatch(op):
        raise _Lock(None, "invalid operation_id: letters, digits, dot, hyphen and underscore, up to 100")
    if (
        not isinstance(branch, str)
        or not _BRANCH.fullmatch(branch)
        or ".." in branch
        or branch.endswith((".lock", "/"))
    ):
        raise _Lock(None, "invalid branch name")
    if not isinstance(base, str) or not _SHA.fullmatch(base):
        raise _Lock(None, "expected_base must be a full 40-character SHA")
    return _safe_folder(folder)


def _existing_root(snap):
    """Why the root was already established at some point, or None.

    It is enough that a role governing the policy has admitted history, active or not, or that some record carries a
    bootstrap event: retiring that role later does not open the door to a second bootstrap with another account.
    """
    for ident, r in sorted(snap.records.items()):
        events = admitted(r.get("events") or [])
        if r.get("type") == "role" and GOVERN in (r.get("capabilities") or []) and events:
            return f"{ident} governs the policy and already has history"
        if any((e.get("event_evidence") or {}).get("mechanism") in (MECHANISM, DECLARED_MECHANISM) for e in events):
            return f"{ident} already has a bootstrap event"
    return None


def _proposed(snap, ident, type_):
    r = snap.records.get(ident)
    if r is None or r.get("type") != type_:
        raise _Lock("MISSING_REFERENCE", f"{ident} is not a {type_} of the base")
    if r.get("state") != "proposed" or r.get("events"):
        raise _Lock("INVALID_SCHEMA", f"{ident} must be proposed and without events to bootstrap the root")
    return r


def _identity(client, declaration, now):
    """(identity, event evidence, data for the receipt and the trailer) of the channel in use."""
    if declaration is not None:
        if not isinstance(declaration, dict) or set(declaration) != set(_DECLARATION):
            raise _Lock("INVALID_SCHEMA", f"the declaration carries exactly {', '.join(_DECLARATION)}")
        identity, session, when, quote = (declaration[k] for k in _DECLARATION)
        if not isinstance(identity, str) or not _DECLARED_IDENTITY.fullmatch(identity):
            raise _Lock("INVALID_SCHEMA", "the declared identity has the form declared:<alias>")
        if not all(isinstance(x, str) and x.strip() for x in (session, quote)) or not is_instant(when):
            raise _Lock(
                "INVALID_SCHEMA", "the declaration needs a session, an instant with a time zone and the literal quote"
            )
        summary = f"{identity}, {session}, {when}: «{quote}» (declared, not authenticated)"
        data = {"identity": identity, "session": session, "instant": when, "quote": quote, "authenticated": False}
        return identity, {"mechanism": DECLARED_MECHANISM, "proof": summary}, data
    try:
        account = authenticated_account(client)
    except VerificationError as exc:
        raise _Lock(exc.code, str(exc)) from exc
    identity = f"github:{account['id']}"
    evidence = {"mechanism": MECHANISM, "proof": f"{identity} ({account['login']}) at {now}"}
    return identity, evidence, account


def _bootstrap_run(git, branch, folder, base, person_id, role_ids, client, declaration, receipts, op):
    folder = _entries(branch, folder, base, op)
    if not role_ids or len(set(role_ids)) != len(role_ids) or person_id in role_ids:
        raise _Lock(None, "the root needs at least one role, without repeats, and a person")
    ref = f"refs/heads/{branch}"
    _canonical_branch(git, ref)
    current = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    if current != base:
        raise _Lock("BASE_CHANGED", f"{branch} is at {current[:12]}, not at the expected base {base[:12]}")
    snap, coverage = load(git.repo, folder, base, mode="proposal")
    if coverage["state"] != "complete":
        raise _Lock("INVALID_SCHEMA", "the base is not consistent", coverage=coverage)
    now = _now()
    existing = _existing_root(snap)
    if existing:
        raise _Lock("ROOT_ALREADY_ESTABLISHED", f"{existing}: policy changes go through the integration")
    if (receipts / f"{op}.json").exists():
        raise _Lock(None, f"there is already a receipt with the operation_id {op}: it is not overwritten")

    roles = {i: _proposed(snap, i, "role") for i in role_ids}
    person = _proposed(snap, person_id, "person")
    # After the bootstrap the base must be canonical: the integration loads it so and every record needs history.
    no_history = sorted(
        i for i, r in snap.records.items() if i not in roles and i != person_id and not admitted(r.get("events") or [])
    )
    if no_history:
        raise _Lock(
            "INVALID_SCHEMA",
            f"the folder has records without admitted history outside the root ({', '.join(no_history)}): "
            "they leave the canonical branch and come back in through the integration after the bootstrap",
        )
    if not any(GOVERN in (r.get("capabilities") or []) for r in roles.values()):
        raise _Lock("INSUFFICIENT_AUTHORITY", "no role of the root governs the policy (govern_policy)")
    if person.get("nature") != "human":
        raise _Lock("INSUFFICIENT_AUTHORITY", f"{person_id} is not a human person: an agent is not the root")
    for i in role_ids:
        if not _holds(person, i, now):
            raise _Lock("INSUFFICIENT_AUTHORITY", f"{person_id} does not hold {i} now")
    identity, evidence, account = _identity(client, declaration, now)
    if person.get("identity_ref") != identity:
        raise _Lock("INSUFFICIENT_AUTHORITY", f"the identity ({identity}) is not the one {person_id} declares")

    finals, n = {}, 0
    for ident in [*role_ids, person_id]:
        r = copy.deepcopy(snap.records[ident])
        events = []
        for previous, new, type_ in ((None, "proposed", "creation"), ("proposed", "active", "transition")):
            n += 1
            events.append(
                {
                    "event_id": f"{op}-{n}",
                    "event_type": type_,
                    "actor": ACTOR,
                    "recorded_at": now,
                    "valid_from": now,
                    "reason": f"bootstrap of the root of trust ({op})",
                    "event_evidence": dict(evidence),  # one copy per event: a shared object would be a YAML alias
                    "previous_state": previous,
                    "new_state": new,
                }
            )
        r["events"], r["state"] = events, "active"
        r.pop("status", None)
        errors = [h for h in validate(r, snap.bodies[ident], mode="canonical") if h["severity"] == "error"]
        if errors:
            raise _Lock("INVALID_SCHEMA", f"{ident}: the activated record is not canonical", findings=errors)
        finals[ident] = (r, snap.bodies[ident])

    new = _commit(git, base, op, identity, finals, snap, folder)
    # The integration will load this revision in canonical mode: if it does not load completely, the branch is not written.
    _, final = load(git.repo, folder, new)
    if final["state"] != "complete":
        raise _Lock(
            "INVALID_SCHEMA", "after the bootstrap the base would not be canonical: nothing was written", coverage=final
        )
    if git("update-ref", ref, new, base, check=False) != 0:
        raise _Lock("BASE_CHANGED", "the branch changed during the bootstrap: nothing was written to it")
    receipt = {
        "operation_id": op,
        "state": "bootstrapped",
        "code": None,
        "branch": branch,
        "base": base,
        "integrated_revision": new,
        "records": [*role_ids, person_id],
        "account": account,
        "recorded_at": now,
    }
    try:
        _write_receipt(receipts / f"{op}.json", receipt)
    except OSError as exc:
        return {**receipt, "persisted_receipt": False, "warning": f"bootstrapped, but the receipt was not saved: {exc}"}
    return receipt


def _commit(git, base, op, identity, finals, snap, folder):
    """Flattened commit over the base with the activated records, without moving the branch yet."""
    with tempfile.TemporaryDirectory(prefix="kb-index-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), **_BOOTSTRAP_IDENTITY}
        git("read-tree", base, extra_env=env)
        written = {}
        for ident, (r, c) in sorted(finals.items()):
            text = serialize(r, c, mode="canonical")
            blob = git("hash-object", "-w", "--stdin", entry=text.encode("utf-8"), extra_env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{snap.paths[ident]}", extra_env=env)
            written[ident] = (snap.paths[ident], text)
        _write_fingerprints(git, base, folder, written, env)
        tree = git("write-tree", extra_env=env)
        message = f"kb: bootstrap {op}\n\n{TRAILER}: {op}\nBootstrap: {identity}\nBase: {base}\n"
        return git("commit-tree", tree, "-p", base, entry=message.encode("utf-8"), extra_env=env)
