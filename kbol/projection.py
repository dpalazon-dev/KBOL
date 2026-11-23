"""Total projection of `status` (VAL-08), computed for one revision and two explicit time cuts.

`status` describes stability for exchange; it is not truth, permission or quality. Nobody writes it by hand. Queries
rebuild the state from the admitted events: a record without admitted history has no projection, and the current
header never replaces the history.
"""

from dataclasses import dataclass, field

from .events import HistoryError, admitted, effective_validity, in_force_at, state_at
from .model import EFFECTIVE

DEPRECATED = {"rejected", "discarded", "retired", "cancelled"}
DRAFT = {
    "decision": {"proposed"},
    "fact": {"proposed"},
    "person": {"proposed"},
    "role": {"proposed"},
    "entity": {"proposed"},
    "plan": {"proposed"},
    "milestone": {"proposed"},
    "synthesis": {"draft"},
    "hypothesis": {"open"},
    "assumption": {"active"},
}


@dataclass(frozen=True)
class Snapshot:
    """Records of an identified canonical revision, by ID, with their bodies if they were loaded."""

    records: dict
    revision: str
    bodies: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    # Records in the legacy format read for compatibility (snapshot.load with legacy=True): cards from the dry-run
    # migration, without admitted history. They never enter `records` and are never in force.
    legacy: dict = field(default_factory=dict)


def state_at_cut(record, known_until):
    """State known at the cut from the admitted history; None if not recorded then or without history."""
    return state_at(record.get("events") or [], known_until, record["type"])


def in_force(record, valid_at, known_until):
    """True if the record is in its effective state and its validity covers `valid_at`. May raise AMBIGUOUS_TIME."""
    type_ = record["type"]
    if type_ not in EFFECTIVE:
        return False
    if type_ == "source":
        return state_at_cut(record, known_until) == "registered"
    validity = effective_validity(record.get("events") or [], type_, known_until)
    return validity is not None and in_force_at(*validity, valid_at)


def came_into_force(record, valid_at, known_until):
    """True if the record reached its effective state and its validity started at or before `valid_at`.

    Being superseded or expiring afterwards does not change the answer: a full succession that came into force does
    not undo itself. May raise AMBIGUOUS_TIME.
    """
    type_ = record["type"]
    if type_ == "source":
        return state_at_cut(record, known_until) in ("registered", "retired")
    validity = effective_validity(record.get("events") or [], type_, known_until)
    return validity is not None and in_force_at(validity[0], None, valid_at)


def _successors_f(record, snapshot, valid_at, known_until, warnings):
    effective = []
    for r in snapshot.records.values():
        if r.get("type") != record["type"] or record["id"] not in (r.get("supersedes") or []):
            continue
        try:
            if came_into_force(r, valid_at, known_until):
                effective.append(r["id"])
        except HistoryError as exc:
            warnings.append(f"{exc.code}: successor {r['id']} without determinable validity ({exc})")
    return effective


def project(record, snapshot, *, valid_at, known_until):
    """{status, state, successors, warnings}. `status` is None if the record was not recorded at the cut."""
    type_ = record["type"]
    warnings = []
    result = {"status": None, "state": None, "successors": [], "warnings": warnings}
    if not admitted(record.get("events") or []):
        warnings.append("no admitted history: the state written in the header is not projected")
        return result
    try:
        state = state_at_cut(record, known_until)
    except HistoryError as exc:
        warnings.append(f"{exc.code}: inconsistent history ({exc})")
        return result
    result["state"] = state
    if state is None:
        warnings.append("the record was not recorded at the knowledge cut")
        return result
    result["successors"] = _successors_f(record, snapshot, valid_at, known_until, warnings)
    if (
        record.get("class") == "archive"
        or state in DEPRECATED
        or (type_ == "hypothesis" and state == "refuted")
        or result["successors"]
    ):
        result["status"] = "deprecated"
    elif state in DRAFT.get(type_, ()) or (
        type_ in ("decision", "fact")
        and state == "accepted"
        and _future_entry(record, valid_at, known_until, warnings)
    ):
        result["status"] = "draft"
    else:
        result["status"] = "stable"
    return result


def project_status(record, snapshot, *, valid_at, known_until):
    """`draft`, `stable`, `deprecated` or None (no admitted history, or not recorded at the cut)."""
    return project(record, snapshot, valid_at=valid_at, known_until=known_until)["status"]


def _future_entry(record, valid_at, known_until, warnings):
    """Rule 3: accepted with a validity start later than `valid_at`. An already expired validity is not future.

    If the start has day precision and the query falls in the ambiguous window, it is treated as future (`draft`):
    what may not be in force yet is not presented as in force.
    """
    validity = effective_validity(record.get("events") or [], record["type"], known_until)
    if validity is None:
        return False
    try:
        return not in_force_at(validity[0], None, valid_at)
    except HistoryError as exc:
        warnings.append(f"{exc.code}: {exc}")
        return True
