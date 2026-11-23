"""State materialized from the history of admitted events (append-only).

Only events with `recorded_at` count: an event without an incorporation instant is local, not admitted, and is
ignored when materializing. This function does not check the authenticity of `event_evidence`; that belongs to the
integration gate.
"""

from datetime import timedelta

from .model import EFFECTIVE, INITIAL, STATE_EVENTS, TRANSITIONS
from .timeutil import comparable, instant, is_date

# A date without a zone may start between UTC−12 and UTC+14: a query inside that window is ambiguous.
_MAX_ZONE = timedelta(hours=14)


class HistoryError(ValueError):
    def __init__(self, message, code="INVALID_SCHEMA"):
        super().__init__(message)
        self.code = code


def admitted(events):
    return [ev for ev in events if isinstance(ev, dict) and ev.get("recorded_at") is not None]


def _sorted_all(events):
    previous = None
    for ev in admitted(events):
        t = instant(ev["recorded_at"])
        if previous is not None and t < previous:
            raise HistoryError(f"event {ev.get('event_id')} recorded before the previous one")
        previous = t
        yield t, ev


def state_history(events, known_until=None, type_=None):
    """Admitted state events up to the cut, checking the whole chain; list of (recorded_at, event)."""
    cut = instant(known_until) if known_until is not None else None
    chain, state = [], None
    for t, ev in _sorted_all(events):
        if ev.get("event_type") not in STATE_EVENTS:
            continue
        prior, new = ev.get("previous_state"), ev.get("new_state")
        if prior != state:
            raise HistoryError(f"event {ev.get('event_id')}: starts from {prior!r} and the state was {state!r}")
        if type_ is not None:
            if ev["event_type"] == "creation" and new != INITIAL[type_]:
                raise HistoryError(f"event {ev.get('event_id')}: a {type_} is created in {INITIAL[type_]!r}")
            if prior is not None and (prior, new) not in TRANSITIONS[type_]:
                raise HistoryError(
                    f"event {ev.get('event_id')}: transition {prior}→{new} not admitted; "
                    "a reopening requires an explicit policy"
                )
        state = new
        if cut is None or t <= cut:
            chain.append((t, ev))
    return chain


def state_at(events, known_until=None, type_=None):
    """State known at the cut, or None if the record was not recorded yet or has no admitted history."""
    chain = state_history(events, known_until, type_)
    return chain[-1][1]["new_state"] if chain else None


def effective_validity(events, type_, known_until=None):
    """(valid_from, valid_until) of the last step into the effective state known at the cut, or None."""
    chain = state_history(events, known_until, type_)
    if not chain or chain[-1][1]["new_state"] != EFFECTIVE.get(type_):
        return None
    ev = chain[-1][1]
    return ev.get("valid_from"), ev.get("valid_until")


def in_force_at(since, until, valid_at):
    """Half-open interval [from, until). A date without a time is ambiguous in the window of possible zones.

    Without a validity start (import of unknown precision) it cannot be decided: AMBIGUOUS_TIME.
    """
    query_ = instant(valid_at)
    if since is None:
        raise HistoryError("validity without a known start: whether it is in force is not decided", "AMBIGUOUS_TIME")
    if is_date(since):
        midnight = comparable(since)
        if midnight - _MAX_ZONE <= query_ < midnight + _MAX_ZONE:
            raise HistoryError(
                f"validity from {since} with day precision: ambiguous at {valid_at}", "AMBIGUOUS_TIME"
            )
        if query_ < midnight:
            return False
    elif instant(since) > query_:
        return False
    return until is None or query_ < instant(until)
