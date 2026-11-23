"""VAL-07: evaluation of the `depends_on` conditions and the query of ready milestones.

A dependency is satisfied only by its typed condition, never because the target exists. A cancelled milestone does
not satisfy `completed_with_evidence`: to go on without it, the dependent changes its `depends_on` through a revised
proposal. While the check record does not exist, a completed milestone does not satisfy it either, and a source does
not satisfy `available_with_integrity`: both fail closed. A proposed plan does not block a milestone by association,
but the milestone needs its own authorization in force.

`in_force_at_cut` is the only definition of what is in force at two cuts: `accepted_and_in_force`, the `support`
query and the evidence of `query` use it.
"""

from .consolidate import AMBIGUOUS, IN_FORCE, RETIRED_F, _Query, validity_of
from .events import HistoryError, admitted, in_force_at, state_history
from .model import EFFECTIVE
from .projection import came_into_force, in_force, state_at_cut

# Situation of what supports a record at the two cuts.
IN_FORCE_IF, NOT_IN_FORCE, UNDETERMINED, MISSING, LEGACY, NO_VALIDITY = (
    "in_force",
    "not_in_force",
    "undetermined",
    "missing",
    "legacy",
    "no_validity",
)

CONDITION_TYPE = {
    "accepted_and_in_force": ("decision", "fact"),
    "resolved": ("question",),
    "completed_with_evidence": ("milestone",),
    "available_with_integrity": ("source",),
}


def _result(dep, satisfied, reason, code=None, warnings=None):
    return {
        "target": dep.get("target"),
        "condition": dep.get("condition"),
        "satisfied": satisfied,
        "code": code,
        "reason": reason,
        "warnings": warnings or [],
    }


def _one_f(dep, snapshot, valid_at, known_until):
    target, condition = dep.get("target", ""), dep.get("condition")
    ident = target.partition("#")[0]
    goal = snapshot.records.get(ident)
    if goal is None and ident in snapshot.legacy:
        card = snapshot.legacy[ident]
        if card["type"] not in CONDITION_TYPE.get(condition, ()):
            return _result(dep, False, f"{condition} does not apply to a {card['type']}", "INVALID_SCHEMA")
        legacy_state = card["legacy_state"]
        reason = f"{ident} is in legacy format ({legacy_state}): without an admitted history it meets no condition"
        return _result(dep, False, reason)
    if goal is None:
        return _result(dep, False, f"{ident} does not exist at revision {snapshot.revision}", "MISSING_REFERENCE")
    if goal.get("type") not in CONDITION_TYPE.get(condition, ()):
        return _result(dep, False, f"{condition} does not apply to a {goal.get('type')}", "INVALID_SCHEMA")
    if not admitted(goal.get("events") or []):
        return _result(dep, False, f"{ident} has no admitted history")
    try:
        state = state_at_cut(goal, known_until)
    except HistoryError as exc:
        return _result(dep, False, str(exc), exc.code)
    if state is None:
        return _result(dep, False, f"{ident} was not recorded at the knowledge cut")
    if condition == "resolved":
        return _result(dep, state == "resolved", f"{ident} is {state}")
    if condition == "completed_with_evidence":
        if state == "completed":
            # Fails closed: the results per criterion will live in the execution record (VAL-12), not built yet.
            reason = f"{ident} completed, but its evidence per criterion cannot be checked yet"
            return _result(dep, False, reason, "INSUFFICIENT_EVIDENCE")
        reason = f"{ident} is {state}" + ("; cancelling is not the same as meeting it" if state == "cancelled" else "")
        return _result(dep, False, reason)
    if condition == "available_with_integrity":
        if state != "registered":
            return _result(dep, False, f"{ident} is {state}")
        return _result(dep, False, "the integrity of the source has not been checked", "INTEGRITY_UNCHECKED")
    return _accepted_and_in_force(dep, goal, snapshot, valid_at, known_until)


def _accepted_and_in_force(dep, goal, snapshot, valid_at, known_until):
    query_ = _Query(snapshot, valid_at, known_until)
    if goal["type"] == "decision" and known_until is None:
        query_.warn("no knowledge cut: the whole admitted history of the revision is used")
    res = in_force_at_cut(query_, dep["target"])
    return _result(dep, res["situation"] == IN_FORCE_IF, res["reason"], res["code"], list(query_.warnings))


def _response(situation, reason, code=None, **detail):
    return {"situation": situation, "reason": reason, "code": code, **{k: v for k, v in detail.items() if v}}


def _transition(step):
    """Last state event at the cut: explains a change of situation between two cuts."""
    keys = ("event_id", "event_type", "new_state", "recorded_at", "valid_from", "valid_until")
    return {k: step[k] for k in keys if step.get(k) is not None}


def _succession(record, query_):
    """(successors already in force, successors whose validity cannot be decided), through `supersedes`."""
    effective, doubtful = [], []
    for other in sorted(query_.snap.records.values(), key=lambda r: r["id"]):
        if other.get("type") != record["type"] or record["id"] not in (other.get("supersedes") or []):
            continue
        try:
            if came_into_force(other, query_.valid_at, query_.known_until):
                effective.append(other["id"])
        except HistoryError as exc:
            doubtful.append(other["id"])
            query_.warn(f"{exc.code}: successor {other['id']} with undeterminable validity ({exc})")
    return effective, doubtful


def _fact_or_source(query_, goal, state):
    ident = goal["id"]
    try:
        in_force_now = in_force(goal, query_.valid_at, query_.known_until)
    except HistoryError as exc:
        return _response(UNDETERMINED, str(exc), exc.code)
    successors, doubtful = _succession(goal, query_)
    if not in_force_now:
        suffix = f" (it is {state})" if state != EFFECTIVE[goal["type"]] else f" on {query_.valid_at}"
        return _response(NOT_IN_FORCE, f"{ident} is not in force{suffix}", successors=successors)
    if successors:
        return _response(NOT_IN_FORCE, f"{ident} is not in force: superseded by {', '.join(successors)}", successors=successors)
    if doubtful:
        reason = f"{ident}: cannot decide whether {', '.join(doubtful)} supersedes it"
        return _response(UNDETERMINED, reason, "AMBIGUOUS_TIME", successors=doubtful)
    return _response(IN_FORCE_IF, f"{ident} is in force")


def _clause(entry):
    """Chain of replacements and origin of a resolved clause, if the chain goes beyond the clause itself."""
    chain = entry.get("chain") or []
    return {"chain": chain if len(chain) > 1 else None, "origin": entry.get("origin")}


def _decision(query_, goal, reference):
    ident, _, anchor = reference.partition("#")
    sit = query_.situation(ident)
    validity, entries = validity_of(query_, ident)
    entry = None
    if anchor and sit == IN_FORCE and anchor in (query_.anchors(ident) or {}):
        entry = query_.resolve(reference)
    if validity not in ("full", "partial"):
        reason = f"{ident} {validity}" + (f": {reference} is {entry['state']}" if entry else "")
        doubtful_ = sit == AMBIGUOUS or any(e["state"] in ("ambiguous", "conflict") for e in entries)
        successors = _succession(goal, query_)[0] if sit == RETIRED_F else None
        detail = _clause(entry) if entry else {}
        return _response(UNDETERMINED if doubtful_ else NOT_IN_FORCE, reason, successors=successors, **detail)
    if not anchor:
        return _response(IN_FORCE_IF, f"{ident} is in force ({validity})")
    if entry is None:
        return _response(MISSING, f"{reference} is not in the consolidated text", "MISSING_REFERENCE")
    detail = _clause(entry)
    if entry["state"] == "conflict":
        return _response(UNDETERMINED, f"{reference} is in conflict", "NORMATIVE_CONFLICT", **detail)
    if entry["state"] == "ambiguous":
        return _response(UNDETERMINED, f"{reference} is ambiguous", **detail)
    if entry["state"] != "current":
        return _response(NOT_IN_FORCE, f"{reference} is {entry['state']}", **detail)
    if entry["origin"] != reference:
        return _response(NOT_IN_FORCE, f"{reference} replaced by {entry['origin']}: review the impact", **detail)
    return _response(IN_FORCE_IF, f"{reference} is in force")


def in_force_at_cut(query_, reference):
    """Whether `ID` or `ID#anchor` is in force at the cuts of `query_` (a `consolidate._Query`): the single definition.

    Used by dependencies (`accepted_and_in_force`), the `support` query and the evidence of `query`. Returns
    {situation, reason, code} and, when known, `state` at the knowledge cut, `transition` (the last state event at the
    cut), `chain` and `origin` of a replaced or repealed clause and `successors`. `situation` is `in_force`,
    `not_in_force`, `undetermined` (ambiguous time, incoherent history or conflict: never an assumed situation),
    `missing`, `legacy` (named, but not in force) or `no_validity` (a type without an effective state, such as a
    synthesis, which only reports its state). A source is in force if it is registered and no successor has come into
    force; a fact, if it is accepted, its validity covers `valid_at` and no successor has come into force; a decision
    or a clause, according to the consolidated text. Read only.
    """
    snapshot = query_.snap
    ident = reference.partition("#")[0]
    goal = snapshot.records.get(ident)
    if goal is None:
        if ident in snapshot.legacy:
            legacy_state = snapshot.legacy[ident].get("legacy_state")
            reason = f"{ident} is in legacy format ({legacy_state}): it is named, but not in force"
            return _response(LEGACY, reason, state=legacy_state)
        return _response(MISSING, f"{ident} does not exist at revision {snapshot.revision}", "MISSING_REFERENCE")
    if not admitted(goal.get("events") or []):
        return _response(NOT_IN_FORCE, f"{ident} has no admitted history")
    type_ = goal.get("type")
    try:
        chain = state_history(goal["events"], query_.known_until, type_)
    except HistoryError as exc:
        return _response(UNDETERMINED, f"{ident}: incoherent history ({exc})", exc.code)
    if not chain:
        return _response(NOT_IN_FORCE, f"{ident} was not recorded at the knowledge cut")
    state = chain[-1][1]["new_state"]
    if type_ not in EFFECTIVE:
        res = _response(NO_VALIDITY, f"{ident} is a record of type {type_}, without validity of its own: it is {state}")
    elif type_ == "decision":
        res = _decision(query_, goal, reference)
    else:
        res = _fact_or_source(query_, goal, state)
    return {**res, "state": state, "transition": _transition(chain[-1][1])}


def evaluate(record, snapshot, *, valid_at, known_until):
    """Result per dependency declared in `record`, in written order."""
    return [
        _one_f(dep, snapshot, valid_at, known_until)
        for dep in record.get("depends_on") or []
        if isinstance(dep, dict)
    ]


def ready(snapshot, *, valid_at, known_until):
    """Milestones authorized at the cut with all their dependencies satisfied, and the authorized ones still blocked."""
    out = {"ready": [], "blocked": [], "milestones_examined": 0, "warnings": []}
    for ident in sorted(snapshot.records):
        r = snapshot.records[ident]
        if r.get("type") != "milestone":
            continue
        out["milestones_examined"] += 1
        if not admitted(r.get("events") or []):
            out["warnings"].append(f"{ident}: no admitted history; its authorization is not recorded")
            continue
        try:
            chain = state_history(r["events"], known_until, "milestone")
            if not chain or chain[-1][1]["new_state"] != "authorized":
                continue
            step = chain[-1][1]
            if not in_force_at(step.get("valid_from"), step.get("valid_until"), valid_at):
                out["warnings"].append(f"{ident}: authorized, but its authorization is not in force on {valid_at}")
                continue
        except HistoryError as exc:
            out["warnings"].append(f"{exc.code}: {ident}: {exc}")
            continue
        deps = evaluate(r, snapshot, valid_at=valid_at, known_until=known_until)
        pending = [d for d in deps if not d["satisfied"]]
        target = out["blocked"] if pending else out["ready"]
        target.append({"id": ident, "dependencies": deps, "pending": pending})
    for ident, card in sorted(snapshot.legacy.items()):
        if card["type"] == "milestone":
            out["warnings"].append(
                f"{ident}: legacy format ({card['legacy_state']}); its authorization is not recorded in an admitted "
                "history"
            )
    return out
