"""Verifier of declared approvals: the person approves in a conversation and the agent quotes their words.

Mechanism not conforming to KB-DPP (implementation, admitted approval): the proof is not checked against any identity
or trusted service, so the verifier never treats it as authenticated and says so in the proof. An installation only
enables it by its own decision and declares in its matrix that the authenticity of the approval is not available
(design choices, "Non-conforming mechanisms").

What is checked: the shape of the approval, that the base shown precedes the base of the integration and, in
`authority.evaluate`, that the approved digests are those of what is integrated. The person, their human nature,
their activity and their role are checked by `evaluate` against the base policy, as with any channel.
"""

import hashlib
import re
import subprocess
from datetime import datetime, timedelta, timezone

from .digest import canonical_bytes
from .snapshot import git_environment
from .timeutil import instant, is_instant
from .verification import VerificationError

MECHANISM = "declared"
_IDENTITY = re.compile(r"declared:\S+")
_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
FIELDS = ("mechanism", "identity", "session", "instant", "quote", "base_shown", "digests")
MARGIN = timedelta(minutes=5)  # clock tolerance between who records and who integrates


def _text(value):
    return isinstance(value, str) and value.strip() != ""


class DeclaredVerifier:
    mechanism = MECHANISM

    def __init__(self, repo, now=None):
        """`repo` is the repository of the integration: without it the base shown cannot be checked.

        `now` fixes the clock, for tests; by default, the system clock.
        """
        if repo is None:
            raise VerificationError("the declared verifier needs the repository of the integration")
        self.repo = str(repo)
        self._now = now

    def verify(self, revision, proposal_rev, base_rev):
        """{identity, instant, proof, digests, approval_id}; VerificationError if it is not valid."""
        if not isinstance(revision, dict) or revision.get("mechanism") != MECHANISM:
            raise VerificationError("the reference is not a declared approval")
        if set(revision) != set(FIELDS):
            raise VerificationError(f"a declared approval carries exactly {', '.join(FIELDS)}")
        identity, session, when, quote = (revision[k] for k in ("identity", "session", "instant", "quote"))
        shown_base, digests = revision["base_shown"], revision["digests"]
        if not isinstance(identity, str) or not _IDENTITY.fullmatch(identity):
            raise VerificationError("the declared identity has the form declared:<alias>")
        if not _text(session) or not _text(quote):
            raise VerificationError("a declared approval needs the session and the literal quote of the person")
        if not is_instant(when):
            raise VerificationError("the approval instant is an ISO 8601 instant with a time zone")
        clock = instant(self._now) if self._now else datetime.now(timezone.utc)
        if instant(when) > clock + MARGIN:
            raise VerificationError("the approval instant is in the future")
        if not isinstance(shown_base, str) or not _SHA.fullmatch(shown_base):
            raise VerificationError("base_shown is the full SHA of the base that was shown")
        if not isinstance(digests, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and _DIGEST.fullmatch(v) for k, v in digests.items()
        ):
            raise VerificationError("digests is a map ID → SHA-256 digest of what was shown")
        if not self._precedes(shown_base, base_rev):
            raise VerificationError("the base shown does not precede the base of the integration")
        signed = {k: revision[k] for k in FIELDS}
        approval_id = f"{MECHANISM}:{hashlib.sha256(canonical_bytes(signed)).hexdigest()[:16]}"
        proof = {
            "mechanism": MECHANISM,
            "session": session,
            "instant": when,
            "quote": quote,
            "base_shown": shown_base,
            "digests": dict(digests),
            "authenticated": False,
            "summary": f"{session}, {when}: «{quote}» (declared, not authenticated)",
        }
        return {
            "identity": identity,
            "instant": when,
            "proof": proof,
            "digests": dict(digests),
            "approval_id": approval_id,
        }

    def _precedes(self, previous, later):
        p = subprocess.run(
            ["git", "-C", self.repo, "merge-base", "--is-ancestor", previous, later],
            capture_output=True,
            env=git_environment(),
        )
        return p.returncode == 0
