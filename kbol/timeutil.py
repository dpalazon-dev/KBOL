"""ISO 8601 instants with a zone and day dates, without depending on the environment clock."""

import re
from datetime import date, datetime, timezone

_INSTANT = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?(Z|[+-]\d{2}:\d{2})")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def instant(text):
    """Converts an instant with a zone into an aware datetime; ValueError if the zone is missing or it is invalid."""
    m = _INSTANT.fullmatch(text) if isinstance(text, str) else None
    if not m:
        raise ValueError(f"not an ISO 8601 instant with a zone: {text!r}")
    day, hh, mm, ss, frac, zone = m.groups()
    micro = (frac or "0")[:6].ljust(6, "0")
    zone = "+00:00" if zone == "Z" else zone
    return datetime.fromisoformat(f"{day}T{hh}:{mm}:{ss or '00'}.{micro}{zone}").astimezone(timezone.utc)


def is_instant(text):
    try:
        instant(text)
        return True
    except ValueError:
        return False


def is_date(text):
    if not (isinstance(text, str) and _DATE.fullmatch(text)):
        return False
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def is_instant_or_date(text):
    return is_instant(text) or is_date(text)


def comparable(text):
    """Instant for sorting: a date counts from its UTC midnight; whoever compares it declares the ambiguity."""
    if is_date(text):
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    return instant(text)
