"""Contractual digest of the approvable content ("Digest and approval", core 1.0).

Object: id, type, class, title, description, scope, author, body, fields and requested_effects. `fields` contains
all content fields and relations except those excluded by an explicit rule: events, projections (materialized
`state`, `status`, `stale_after`), `verified` and evaluations. Serialization: keys sorted by Unicode code point,
arrays in their order, no spaces, UTF-8 without BOM, no Unicode normalization, body line breaks as LF and only exact
integers. Digest = SHA-256 of those bytes.
"""

import hashlib
import json

from .core import normalize_body
from .timeutil import is_instant

SUPERIORS = ("id", "type", "class", "title", "description", "scope", "author")
EXCLUDED = frozenset(SUPERIORS) | {"events", "state", "status", "stale_after", "verified", "evaluations"}


def _check(value, path="$"):
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return
    if isinstance(value, float):
        raise ValueError(f"{path}: decimals are serialized as text")
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{path}: non-text key {k!r}")
            _check(v, f"{path}.{k}")
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            _check(v, f"{path}[{i}]")
        return
    raise ValueError(f"{path}: non-serializable type {type(value).__name__}")


def canonical_bytes(object_):
    _check(object_)
    text = json.dumps(object_, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8")


EFFECT_FIELDS = {"previous_state", "new_state", "valid_from", "valid_until"}


def check_effects(effects):
    """Requested transitions with their validity dates; without the incorporation instants, still unknown."""
    if not isinstance(effects, list):
        raise ValueError("requested_effects is a list of transitions")
    for i, ef in enumerate(effects):
        if not isinstance(ef, dict) or not {"new_state", "valid_from"} <= ef.keys() or set(ef) - EFFECT_FIELDS:
            raise ValueError(f"effect {i}: carries new_state and valid_from, and only {sorted(EFFECT_FIELDS)}")
        for field in ("valid_from", "valid_until"):
            if field in ef and not is_instant(ef[field]):
                raise ValueError(f"effect {i}: {field} is not an instant with a zone")


def approvable_object(record, body, requested_effects, import_=None):
    check_effects(requested_effects)
    obj = {k: record.get(k) for k in SUPERIORS}
    obj["body"] = normalize_body(body)
    obj["fields"] = {k: v for k, v in record.items() if k not in EXCLUDED}
    obj["requested_effects"] = requested_effects
    if import_ is not None:  # only in an import: the published vectors do not carry it
        obj["import"] = import_
    return obj


def digest(record, body, requested_effects, import_=None):
    object_ = approvable_object(record, body, requested_effects, import_)
    return hashlib.sha256(canonical_bytes(object_)).hexdigest()
