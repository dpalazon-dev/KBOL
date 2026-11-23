"""Common error of the approval verifiers, whatever their channel (GitHub, declared)."""

import json


def revision_key(revision):
    """Canonical form of a review to recognize it when repeated, even if its nested maps change order."""
    return json.dumps(revision, sort_keys=True, ensure_ascii=False, default=repr)


class VerificationError(Exception):
    def __init__(self, reason, code="INSUFFICIENT_AUTHORITY"):
        super().__init__(reason)
        self.code = code
