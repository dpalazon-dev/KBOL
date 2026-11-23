"""Approval verifier based on GitHub pull request reviews.

Whoever asks for the integration only identifies reviews (`{mechanism, pull, review_id}`); it supplies no identities,
roles, digests or effects. The verifier, with the repository fixed by configuration, checks in the GitHub API that the
PR compares exactly the expected base with the proposed commit and that the review approves that commit, and returns
the account that made it and its instant. What the person approved is that diff, including the requested effects file
that travels in it. It stores no tokens: the client takes it from `KB_GITHUB_TOKEN`; without it, it is not enabled.
"""

import json
import os
import re

from .timeutil import instant, is_instant
from .verification import VerificationError  # noqa: F401 (re-exported)

API = "https://api.github.com"
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _opener_without_redirects():
    """urllib forwards Authorization when it follows a redirect: none is followed. urllib.request is imported here
    and not when the module loads, since the CLI imports it on every command even when it does not talk to GitHub."""
    import urllib.request

    class _NoRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(_NoRedirects)


class GitHubClient:
    """Minimal read-only HTTP client for the GitHub REST API that follows no redirects."""

    def __init__(self, token):
        self._token = token
        self._opener = _opener_without_redirects()

    def __repr__(self):
        return "GitHubClient(token=***)"

    @classmethod
    def from_environment(cls):
        token = os.environ.get("KB_GITHUB_TOKEN")
        if not token:
            raise VerificationError("GitHub verifier not enabled: KB_GITHUB_TOKEN is missing")
        return cls(token)

    def get(self, path):
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            API + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "kbol",
            },
        )
        try:
            with self._opener.open(req, timeout=20) as response:  # noqa: S310 - fixed API URL
                return json.load(response)
        except urllib.error.HTTPError as exc:
            code = "ACCESS_DENIED" if exc.code in (401, 403) else "INSUFFICIENT_AUTHORITY"
            raise VerificationError(f"GitHub answered {exc.code} for {path}", code) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise VerificationError(
                f"GitHub did not answer validly: {type(exc).__name__}", "UNKNOWN_RESULT"
            ) from None


def authenticated_account(client):
    """{id, login} of the account that owns the client token, according to GitHub (`GET /user`); person accounts only."""
    data = client.get("/user")
    if not isinstance(data, dict):
        raise VerificationError("unexpected GitHub response for /user")
    ident, login, type_ = data.get("id"), data.get("login"), data.get("type")
    if not isinstance(ident, int) or isinstance(ident, bool) or not isinstance(login, str) or not login:
        raise VerificationError("GitHub did not identify the token account")
    if type_ != "User":
        raise VerificationError(f"the token account is of type {type_!r}, not a person")
    return {"id": ident, "login": login}


class GitHubVerifier:
    """Checks an approved review of a PR of the configured repository, on the exact base and commit."""

    mechanism = "github-review"

    # States that set an account's stance; comments do not change it.
    EFFECTIVE = ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")
    # Events that change what the PR compares after it was approved.
    BASE_CHANGES = ("base_ref_changed", "base_ref_force_pushed")

    def __init__(self, client, repository, branch):
        if not isinstance(repository, str) or not _REPO.fullmatch(repository):
            raise VerificationError(f"invalid GitHub repository: {repository!r}")
        if not isinstance(branch, str) or not branch:
            raise VerificationError("the configuration lacks the canonical branch")
        self.client = client
        self.repository = repository
        self.branch = branch

    def _pages(self, path):
        elements, page = [], 1
        while True:
            batch = self.client.get(f"{path}?per_page=100&page={page}")
            if not isinstance(batch, list):
                raise VerificationError(f"unexpected GitHub response for {path}")
            elements += batch
            if len(batch) < 100:
                return elements
            page += 1

    def verify(self, revision, proposal_rev, base_rev):
        """{identity, instant, proof}; VerificationError if it does not prove the approval of that diff.

        The account's current stance counts: its last effective review in the PR must approve the proposed commit.
        An approval the same person withdrew later does not count.
        """
        if not isinstance(revision, dict) or revision.get("mechanism") != self.mechanism:
            raise VerificationError("the reference is not a GitHub review")
        pull, review_id = revision.get("pull"), revision.get("review_id")
        if (
            not (isinstance(pull, int) and isinstance(review_id, int))
            or isinstance(pull, bool)
            or isinstance(review_id, bool)
        ):
            raise VerificationError("pull and review_id are integers")
        pr = self.client.get(f"/repos/{self.repository}/pulls/{pull}")
        if (pr.get("head") or {}).get("sha") != proposal_rev:
            raise VerificationError(
                "the PR no longer points to the proposed commit: other content was approved", "STALE_APPROVAL"
            )
        if (pr.get("base") or {}).get("ref") != self.branch:
            raise VerificationError("the PR does not target the canonical branch")
        if (pr.get("base") or {}).get("sha") != base_rev:
            raise VerificationError("the PR does not compare with the expected base: the reviewed diff is another one")
        revisions = self._pages(f"/repos/{self.repository}/pulls/{pull}/reviews")
        rev = next((r for r in revisions if r.get("id") == review_id), None)
        if rev is None:
            raise VerificationError("the review does not exist in the PR")
        if rev.get("state") != "APPROVED":
            raise VerificationError(f"the review is {rev.get('state')!r}, not approved")
        if rev.get("commit_id") != proposal_rev:
            raise VerificationError(
                "the review approves another commit: the content changed afterwards", "STALE_APPROVAL"
            )
        user_id = (rev.get("user") or {}).get("id")
        when = rev.get("submitted_at")
        if not isinstance(user_id, int) or isinstance(user_id, bool) or not is_instant(when):
            raise VerificationError("the review does not identify the account or the instant")
        stances = [
            r for r in revisions if (r.get("user") or {}).get("id") == user_id and r.get("state") in self.EFFECTIVE
        ]
        last = stances[-1] if stances else None
        if last is None or last.get("state") != "APPROVED" or last.get("commit_id") != proposal_rev:
            raise VerificationError(
                "the same person changed or withdrew the review afterwards: their current stance does not approve"
            )
        timeline = self._pages(f"/repos/{self.repository}/issues/{pull}/timeline")
        for ev in timeline:
            if ev.get("event") in self.BASE_CHANGES and (
                not is_instant(ev.get("created_at")) or instant(ev["created_at"]) >= instant(when)
            ):
                raise VerificationError("the PR base changed after the approval: what was approved was another diff")
        proof = {
            "mechanism": self.mechanism,
            "repository": self.repository,
            "pull": pull,
            "review_id": review_id,
        }
        return {"identity": f"github:{user_id}", "instant": when, "proof": proof}
