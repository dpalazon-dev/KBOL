"""VAL-03: a proposal compared with the base revision (mutability matrix of core 1.0).

- No record is deleted or changes type; the state is not edited: it is requested as an effect.
- Events are append-only and only the integration adds them: the proposal keeps them as they are in the base.
- A closed record (`CLOSED`) does not change its content, its clauses or its marked claims; title,
  description and unmarked prose may change.
- An authorized plan or milestone does not change what its authorization covers without being authorized again.
- The fingerprint and format of a source do not change; its location may, with an integrity check.
- The tasks of a milestone (`CT*` clauses) are not deleted, rewritten or renumbered: only their checkbox is ticked,
  and in a closed milestone not even that. Citations to `ID#CTn` must keep pointing to the same text.
- Changing roles, holdings, identities or the access to a source requires the authority of the previous policy: it
  is flagged for that check, which this module does not do.
"""

import re

from .markdown import MarkupError, clauses, facts
from .model import REFERENCES, WORK_FIELDS

FREE = {"title", "description", "generated", "verified", "stale_after", "status", "evaluations", "events"}
# Links and work fields: changing them does not reopen a closure or an authorization, since they do not change what is in force.
FREE |= {c for c, r in REFERENCES.items() if r.free} | set(WORK_FIELDS)
# Closing states per type: the content is no longer edited; it is revised with a successor or a reasoned transition.
CLOSED = {
    "decision": {"accepted", "rejected"},
    "fact": {"accepted", "rejected"},
    "question": {"resolved", "discarded"},
    "hypothesis": {"validated", "refuted", "retired"},
    "assumption": {"retired"},
    "plan": {"closed", "cancelled"},
    "milestone": {"completed", "cancelled"},
    "source": {"retired"},
    "person": {"retired"},
    "role": {"retired"},
    "entity": {"retired"},
    "synthesis": {"retired"},
}
# What an authorization in force covers: changing it requires authorizing again.
AUTHORIZED = {
    "plan": ({"authorized"}, {"goal", "constraints", "authorized_by", "milestones"}),
    "milestone": (
        {"authorized", "in_progress"},
        {"goal", "work_scope", "authorized_by", "acceptance", "tolerances", "checks", "depends_on"},
    ),
}
SOURCE_IMMUTABLES = {
    "format",
    "sha256",
    "subtype",
    "derived_from",
    "processor",
    "processor_version",
    "configuration_ref",
    "processed_at",
}
POLICY = {
    "role": {"scopes", "capabilities", "approval_rule", "state"},
    "person": {"holds", "nature", "identity_ref"},
    "source": {"access"},
}


_CHECKBOX = re.compile(r"^(\s*[-*+]\s+)\[[ xX]\]", re.MULTILINE)


def _without_checkbox(text):
    return _CHECKBOX.sub(r"\1[ ]", text)


def _tasks(ident, body_before, body_after, closed, h):
    """Each `CT*` task of the base stays in the proposal with the same text; only its checkbox changes, unless closed."""
    all_ = _anchors(body_before)
    if all_ is None:  # the base cannot be read: no change to its tasks is accepted
        h.append(_h(ident, "body", "the milestone markup in the base is broken: its tasks are not checked"))
        return
    before = {k: v for k, v in all_.items() if k.startswith("CT")}
    if not before:
        return
    after = _anchors(body_after)
    if after is None:
        h.append(_h(ident, "body", "the task markup is broken: a task is not lost"))
        return
    for anchor, text in before.items():
        if anchor not in after:
            h.append(_h(ident, "body", f"task {anchor} is not deleted or renumbered: it may be cited"))
        elif closed and after[anchor] != text:
            h.append(_h(ident, "body", f"task {anchor} belongs to a closed milestone: it is not ticked or changed"))
        elif _without_checkbox(after[anchor]) != _without_checkbox(text):
            h.append(_h(ident, "body", f"task {anchor} is not rewritten: only its checkbox is ticked"))


def _h(ident, field, message, severity="error", code="INVALID_SCHEMA", control="VAL-03"):
    path = f"{ident}/{field}" if field else ident
    return {"code": code, "path": path, "message": message, "severity": severity, "control": control}


def _anchors(body):
    try:
        return clauses(body or "")
    except MarkupError:
        return None


def _facts(body):
    try:
        return facts(body or "")
    except MarkupError:
        return None


def compare(base, proposal):
    """{findings, new, modified, policy_changes} of `proposal` against `base`."""
    out = {"findings": [], "new": [], "modified": [], "policy_changes": [], "base": base.revision}
    h = out["findings"]
    for ident, before in sorted(base.records.items()):
        after = proposal.records.get(ident)
        if after is None:
            h.append(_h(ident, None, "a record is not deleted: its state changes"))
            continue
        if after == before and proposal.bodies.get(ident) == base.bodies.get(ident):
            continue
        out["modified"].append(ident)
        _compare_one(ident, before, after, base.bodies.get(ident), proposal.bodies.get(ident), out)
    for ident in sorted(set(proposal.records) - set(base.records)):
        out["new"].append(ident)
        new = proposal.records[ident]
        if new.get("events"):
            h.append(_h(ident, "events", "a new record carries no events: the integration adds them"))
        if new.get("type") in POLICY:
            out["policy_changes"].append(ident)
            h.append(
                _h(
                    ident,
                    None,
                    "new identity or role: requires prior authority",
                    "requires_authority",
                    "INSUFFICIENT_AUTHORITY",
                    "VAL-04",
                )
            )
    return out


def _compare_one(ident, before, after, body_before, body_after, out):
    h = out["findings"]
    type_ = before.get("type")
    if after.get("type") != type_:
        h.append(_h(ident, "type", "a record does not change type"))
        return
    if after.get("state") != before.get("state"):
        h.append(_h(ident, "state", "the state is not edited: the transition is requested and the integration produces it"))
    ev_a, ev_d = before.get("events") or [], after.get("events") or []
    if ev_d[: len(ev_a)] != ev_a:
        h.append(_h(ident, "events", "admitted events are not modified or removed"))
    elif len(ev_d) > len(ev_a):
        h.append(_h(ident, "events", "new events are added by the integration, not by the proposal"))
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if type_ in CLOSED and before.get("state") in CLOSED[type_]:
        for field in changed:
            if field not in FREE and field != "state":
                h.append(
                    _h(ident, field, f"protected content of a {before['state']} {type_}: it is changed with a successor")
                )
        if type_ == "decision":
            a, d = _anchors(body_before), _anchors(body_after)
            if d is None or a != d:
                h.append(
                    _h(ident, "body", "the clauses of a closed decision are not rewritten, removed or added")
                )
        if _facts(body_before) != _facts(body_after):
            h.append(
                _h(ident, "body", "a marked claim of a closed record is corrected with another one and succession")
            )
    if type_ == "milestone":
        _tasks(ident, body_before, body_after, before.get("state") in CLOSED["milestone"], h)
    if type_ in AUTHORIZED and before.get("state") in AUTHORIZED[type_][0]:
        for field in changed:
            if field in AUTHORIZED[type_][1]:
                h.append(
                    _h(
                        ident,
                        field,
                        f"covered by the authorization of an {before['state']} {type_}: it must be authorized again",
                    )
                )
    if type_ == "source":
        for field in changed:
            if field in SOURCE_IMMUTABLES:
                h.append(_h(ident, field, "the content of a source is immutable: another version is another source"))
        if "location" in changed:
            h.append(
                _h(
                    ident,
                    "location",
                    "pointer moved: check that the new location keeps the fingerprint (VAL-10)",
                    "alert",
                    None,
                    "VAL-10",
                )
            )
    if type_ in POLICY and any(c in POLICY[type_] for c in changed):
        out["policy_changes"].append(ident)
        h.append(
            _h(
                ident,
                None,
                "policy change: the previous policy authorizes it",
                "requires_authority",
                "INSUFFICIENT_AUTHORITY",
                "VAL-04",
            )
        )
