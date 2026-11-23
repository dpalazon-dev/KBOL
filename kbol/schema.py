"""VAL-01: shape of an isolated record (header, fields per type, relations, events and body markup).

Validating the shape does not establish authority, validity nor admission of events: those checks need the policy,
the base and the integration mechanism. References between records are checked in `references.py`.

Modes:
- `proposal` (default): unknown fields are errors; a decision needs clauses.
- `canonical`: also, the written state must match the admitted history.
- `exchange`: unknown fields are kept and only raise an alert.
"""

from functools import cache

from . import model as m
from .events import HistoryError, state_at
from .markdown import MarkupError, clauses, facts
from .timeutil import comparable, is_date, is_instant, is_instant_or_date


@cache
def _formats():
    """Format checker. jsonschema is imported when validating, not when loading the module: importing it costs more
    than many whole commands that validate nothing."""
    from jsonschema import FormatChecker

    checker = FormatChecker(formats=())
    checker.checks("instant")(is_instant)
    checker.checks("date")(is_date)
    checker.checks("instant-or-date")(is_instant_or_date)
    return checker


TEXT = {"type": "string", "minLength": 1}
LINE = {"type": "string", "minLength": 1, "pattern": r"^[^\r\n]*(?!\n)$"}
TEXTS = {"type": "array", "items": TEXT}
ID = {"type": "string", "pattern": m.RE_ID.pattern}
ANCHOR_ID = {"type": "string", "pattern": m.RE_ANCHOR_ID.pattern}
IDS = {"type": "array", "items": ID}
ANCHOR_IDS = {"type": "array", "items": ANCHOR_ID}
ACTOR = {"type": "string", "pattern": r"^(human:\S+|process:\S+|[^\s/:]+/[^\s/]+)(?!\n)$"}
SHA256 = {"type": "string", "pattern": r"^[0-9a-f]{64}(?!\n)$"}
INSTANT = {"type": "string", "format": "instant"}
INSTANT_OR_DATE = {"type": "string", "format": "instant-or-date"}
INTEGER = {"type": "integer"}


def object_(required, optional=None, **extra):
    props = {**required, **(optional or {})}
    return {"type": "object", "required": list(required), "properties": props, "additionalProperties": False, **extra}


EVENT_EVIDENCE = object_({"mechanism": TEXT, "proof": TEXT})
CITED_SOURCE = object_(
    {"id": TEXT, "resource": ID},
    {"anchor": TEXT, "representation_id": ID, "hash": SHA256, "context": TEXT},
)
EVALUATION = object_(
    {
        "evaluation_id": TEXT,
        "subject_id": ID,
        "digest_or_fingerprint": SHA256,
        "dimensions": {**TEXTS, "minItems": 1},
        "method": TEXT,
        "actor": ACTOR,
        "performed_at": INSTANT,
        "result": {"enum": list(m.EVALUATION_RESULT)},
        "evidence_ref": TEXT,
        "limitations": TEXT,
    }
)
APPROVAL = object_(
    {
        "approval_id": TEXT,
        "actor": ACTOR,
        "identity_ref": TEXT,
        "roles": {**IDS, "minItems": 1},
        "digest": SHA256,
        "base_revision": TEXT,
        "approved_at": INSTANT,
        "policy_revision": TEXT,
        "proof": {"anyOf": [TEXT, {"type": "object", "minProperties": 1}]},
    }
)
LIMIT = {"anyOf": [TEXT, {"type": "object", "minProperties": 1}]}

EVENT_COMMON = {
    "event_id": TEXT,
    "event_type": {"enum": list(m.EVENTS)},
    "actor": ACTOR,
    "recorded_at": {"anyOf": [INSTANT, {"type": "null"}]},
    "valid_from": INSTANT,
    "reason": TEXT,
    "event_evidence": EVENT_EVIDENCE,
}
EVENT_OPTIONAL = {"valid_until": INSTANT}
EVENT_BY_CLASS = {
    "creation": ({"previous_state": {"type": "null"}, "new_state": TEXT}, {}),
    "transition": ({"previous_state": TEXT, "new_state": TEXT}, {}),
    "import": (
        {
            "previous_state": {"type": "null"},
            "new_state": TEXT,
            "legacy_state": TEXT,
            "provenance": object_({"path": TEXT, "revision": TEXT}),
            "valid_from": {"anyOf": [INSTANT_OR_DATE, {"type": "null"}]},
        },
        {
            "precision": {"enum": list(m.PRECISIONS) + ["unknown"]},
            "inherited_authority": {
                "anyOf": [
                    {"type": "null"},
                    object_({"text": TEXT, "classification": {"enum": ["checked", "pending", "insufficient"]}}),
                ]
            },
        },
    ),
    "ratification": ({"approval": APPROVAL}, {}),
    "approval_revocation": ({"approval_id": TEXT}, {}),
    "evaluation": ({"evaluation": EVALUATION}, {}),
    "holding_change": ({"role": ID, "from": INSTANT}, {"until": INSTANT}),
    "impact_resolution": (
        {"affected": ANCHOR_ID, "cause": TEXT, "resolution": {"enum": ["updated", "does_not_affect", "pending"]}},
        {"owner": ID, "deadline": INSTANT_OR_DATE},
    ),
}


def event_schema(class_):
    required, optional = EVENT_BY_CLASS[class_]
    return object_({**EVENT_COMMON, **required}, {**EVENT_OPTIONAL, **optional})


OBJECT_RELATION = {
    "amends": {
        "type": "array",
        "items": object_(
            {"target": ANCHOR_ID, "operation": {"enum": ["replaces", "repeals", "adds"]}},
            {"by": ANCHOR_ID, "position": TEXT},
        ),
    },
    "depends_on": {"type": "array", "items": object_({"target": ANCHOR_ID, "condition": {"enum": list(m.CONDITIONS)}})},
    "holds": {"type": "array", "items": object_({"role": ID, "from": INSTANT}, {"until": INSTANT})},
    "vetoes": {"type": "array", "items": object_({"pattern": TEXT, "scope": TEXT, "use": TEXT, "exclusions": TEXTS})},
    "defines": {
        "type": "array",
        "items": object_(
            {
                "clause": {"type": "string", "pattern": m.RE_ANCHOR.pattern},
                "term": LINE,
                "class": {"enum": list(m.TERM_CLASSES)},
                "description": TEXT,
            },
            {"aliases": {"type": "array", "items": LINE}},
        ),
    },
}

COMMON = {
    "id": ID,
    "type": {"enum": list(m.TYPES)},
    "class": {"enum": list(m.CLASSES)},
    "title": LINE,
    "description": LINE,
    "scope": TEXT,
    "state": TEXT,
    "author": ACTOR,
    "events": {"type": "array", "items": {"type": "object", "required": ["event_type"]}},
    "sources": {"type": "array", "items": CITED_SOURCE},
}
COMMON_OPTIONAL = {
    "generated": object_({"by": TEXT, "at": INSTANT}),
    "verified": {"type": "array", "items": object_({"by": ACTOR, "at": INSTANT, "digest": SHA256})},
    "stale_after": INSTANT,
    "status": {"enum": ["draft", "stable", "deprecated"]},
}
QUALITY = {
    "type": "object",
    "minProperties": 1,
    "additionalProperties": {
        "anyOf": [
            {"const": "not_evaluated"},
            object_({"method": TEXT, "result": {"enum": list(m.EVALUATION_RESULT)}, "limits": TEXT}),
        ]
    },
}
_COMMON_SOURCE = {
    "subtype": {"enum": ["original", "derived"]},
    "location": TEXT,
    "format": TEXT,
    "sha256": SHA256,
    "access": TEXT,
}
ACCEPTANCE = object_(
    {
        "criterion_id": TEXT,
        "description": TEXT,
        "method": {"enum": list(m.ACCEPTANCE_METHODS)},
        "required": {"type": "boolean"},
    },
    {"rubric": TEXT, "disagreement_resolution": TEXT},
)
CHECK = object_(
    {
        "check_id": TEXT,
        "criterion_id": TEXT,
        "executor": TEXT,
        "input": {"type": ["object", "array"]},
        "environment_ref": TEXT,
        "timeout": {**INTEGER, "minimum": 1},
        "permitted_effects": TEXTS,
    }
)
ALTERNATIVE = object_({"id": TEXT, "description": TEXT, "selected": {"type": "boolean"}, "reason": TEXT})

# Own fields per type: (required, optional). The admitted relations are added from model.RELATIONS.
BY_TYPE = {
    "source": (_COMMON_SOURCE, {"evaluations": {"type": "array", "items": EVALUATION}}),
    "fact": (
        {
            "claim": TEXT,
            "evidence_class": {"enum": list(m.EVIDENCE_CLASSES)},
            "precision": {"enum": list(m.PRECISIONS)},
        },
        {"date": INSTANT_OR_DATE, "interval": object_({"from": INSTANT_OR_DATE}, {"until": INSTANT_OR_DATE})},
    ),
    "decision": (
        {"alternatives": {"type": "array", "items": ALTERNATIVE}, "criteria": TEXTS, "rationale": TEXT},
        {"no_alternatives_reason": TEXT, "implementation": {"enum": list(m.IMPLEMENTATION)}},
    ),
    "person": ({"nature": {"enum": ["human", "agent"]}, "identity_ref": TEXT}, {}),
    "role": (
        {
            "scopes": {**TEXTS, "minItems": 1},
            "capabilities": {**TEXTS, "minItems": 1},
            "approval_rule": {"anyOf": [{"enum": ["one", "all"]}, object_({"quorum": {**INTEGER, "minimum": 1}})]},
        },
        {},
    ),
    "question": (
        {
            "subtype": {"enum": ["unknown", "incident", "discrepancy"]},
            "owner": ID,
            "closing_condition": TEXT,
        },
        {"deadline": INSTANT_OR_DATE, "evidence": TEXTS},
    ),
    "hypothesis": (
        {"claim": TEXT, "test_plan": TEXT, "refutation_criterion": TEXT, "consequence_if_fails": TEXT},
        {},
    ),
    "assumption": ({"claim": TEXT, "review_at": INSTANT_OR_DATE, "consequence_if_fails": TEXT}, {}),
    "entity": ({"name": TEXT, "aliases": TEXTS, "entity_class": TEXT}, {}),
    "plan": ({"goal": TEXT, "milestones": IDS, "constraints": TEXTS}, {}),
    "milestone": (
        {
            "goal": TEXT,
            "work_scope": TEXT,
            "acceptance": {"type": "array", "items": ACCEPTANCE, "minItems": 1},
            "tolerances": object_({}, {"time": LIMIT, "cost": LIMIT, "resources": LIMIT, "work_scope": LIMIT}),
            "checks": {"type": "array", "items": CHECK},
        },
        {"owner": ID, "evidence": TEXTS},
    ),
    "synthesis": ({"dependencies": ANCHOR_IDS, "evaluations": {"type": "array", "items": EVALUATION}}, {}),
}
DERIVED = {
    "derived_from": {**IDS, "minItems": 1},
    "processor": TEXT,
    "processor_version": TEXT,
    "configuration_ref": TEXT,
    "processed_at": INSTANT,
    "processing": {"enum": list(m.PROCESSING)},
    "quality": QUALITY,
}
# Required relations per type (table "Concrete contracts").
REQUIRED_RELATIONS = {
    "fact": ("based_on",),
    "decision": ("authorized_by",),
    "person": ("holds",),
    "plan": ("authorized_by",),
    "milestone": ("authorized_by",),
}
# Contract names that no domain term may take: types, fields and relations.
# They are compared case-insensitively: `Entity` also names a type.
RESERVED = frozenset(
    n.casefold()
    for n in (
        *m.TYPES,
        *COMMON,
        *COMMON_OPTIONAL,
        *(c for required, optional in BY_TYPE.values() for c in (*required, *optional)),
        *DERIVED,
        "origin",
        *m.REFERENCES,
    )
)


def fields_of(type_, subtype=None):
    """(properties schema, required) for a type."""
    required, optional = BY_TYPE[type_]
    props = {**COMMON, **COMMON_OPTIONAL, **required, **optional}
    req = list(COMMON) + list(required)
    for rel, rule in m.RELATIONS.items():
        if type_ in rule["origin"]:
            props[rel] = {**ANCHOR_IDS, "minItems": 1} if rel == "authorized_by" else ANCHOR_IDS
    for rel, origins in m.OBJECT_RELATIONS.items():
        if type_ in origins:
            props[rel] = OBJECT_RELATION[rel]
    req += list(REQUIRED_RELATIONS.get(type_, ()))
    if type_ == "source":
        if subtype == "derived":
            props.update(DERIVED)
            req += list(DERIVED)
            props.pop("origin", None)
        else:
            props["origin"] = TEXT
            props.pop("derived_from", None)
            req.append("origin")
    return props, req


def _finding(code, path, message, severity="error"):
    return {"code": code, "path": path, "message": message, "severity": severity}


def _path(error):
    return "/" + "/".join(str(p) for p in error.absolute_path)


def _jsonschema(schema, instance, prefix=""):
    from jsonschema import Draft202012Validator

    return [
        _finding("INVALID_SCHEMA", prefix + _path(e), e.message)
        for e in Draft202012Validator(schema, format_checker=_formats()).iter_errors(instance)
    ]


def _repeated(items, key, path):
    seen, out = set(), []
    for i, it in enumerate(items):
        if isinstance(it, dict) and key in it:
            if it[key] in seen:
                out.append(_finding("INVALID_SCHEMA", f"{path}/{i}/{key}", f"repeated {key}: {it[key]}"))
            seen.add(it[key])
    return out


def validate(record, body="", mode="proposal"):
    """List of findings {code, path, message, severity}. Empty if the shape is valid in the requested mode."""
    if mode not in ("proposal", "canonical", "exchange"):
        raise ValueError(f"unknown mode: {mode}")
    if not isinstance(record, dict):
        return [_finding("INVALID_SCHEMA", "/", "the header must be a mapping")]
    type_ = record.get("type")
    if type_ not in m.TYPES:
        return _jsonschema({"type": "object", "required": list(COMMON), "properties": COMMON}, record)

    props, req = fields_of(type_, record.get("subtype"))
    schema = {"type": "object", "required": req, "properties": props}
    out = _jsonschema(schema, record)
    for field in record:
        if field not in props:
            sev = "alert" if mode == "exchange" else "error"
            out.append(_finding("INVALID_SCHEMA", f"/{field}", f"field not declared for {type_}", sev))

    out += _decimals(record, "")
    out += _identity(record, type_)
    if record.get("state") not in m.STATES[type_]:
        out.append(_finding("INVALID_SCHEMA", "/state", f"{record.get('state')!r} is not a state of {type_}"))
    elif mode == "proposal" and record.get("events") == [] and record["state"] != m.INITIAL[type_]:
        out.append(
            _finding(
                "INVALID_SCHEMA", "/state", f"a new proposal is in {m.INITIAL[type_]!r}; the change is requested"
            )
        )
    out += _relations(record, type_)
    out += _by_type(record, type_)
    out += _events(record, type_, mode)
    out += _body(record, type_, body, mode)
    return out


def _decimals(value, path):
    """Numeric values are exact integers; decimals are written as text (600.0 too)."""
    if isinstance(value, float):
        return [_finding("INVALID_SCHEMA", path or "/", "decimals are written as text")]
    if isinstance(value, dict):
        return [h for k, v in value.items() for h in _decimals(v, f"{path}/{k}")]
    if isinstance(value, list):
        return [h for i, v in enumerate(value) for h in _decimals(v, f"{path}/{i}")]
    return []


def _sorted(since, until, path):
    if not (
        isinstance(since, str) and isinstance(until, str) and is_instant_or_date(since) and is_instant_or_date(until)
    ):
        return []
    if comparable(until) <= comparable(since):
        return [_finding("INVALID_SCHEMA", path, f"the end {until} is not after the start {since}")]
    return []


def _identity(record, type_):
    ident = record.get("id")
    if not isinstance(ident, str):
        return []
    imposed = m.type_of_id(ident)
    if imposed is None:
        return [_finding("INVALID_SCHEMA", "/id", f"the prefix of {ident} matches no type")]
    if imposed != type_:
        return [_finding("INVALID_SCHEMA", "/id", f"{ident} is an ID of {imposed}, not of {type_}")]
    return []


def _relations(record, type_):
    out = []
    for rel, rule in m.RELATIONS.items():
        values = record.get(rel)
        if not isinstance(values, list):
            continue
        for i, dest in enumerate(values):
            if not isinstance(dest, str):
                continue
            with_anchor = "#" in dest
            if rule["anchor"] == "required" and not with_anchor:
                out.append(_finding("INVALID_SCHEMA", f"/{rel}/{i}", f"{rel} points to a clause: ID#anchor"))
            if rule["anchor"] == "forbidden" and with_anchor:
                out.append(
                    _finding("INVALID_SCHEMA", f"/{rel}/{i}", f"{rel} points to a record, not to a clause")
                )
            expected = (type_,) if rule["target"] == "same" else rule["target"]
            actual = m.type_of_id(dest)
            if expected and actual is not None and actual not in expected:
                out.append(_finding("INVALID_SCHEMA", f"/{rel}/{i}", f"{rel} does not admit a target of type {actual}"))
    for i, mod in enumerate(record.get("amends") or []):
        if not isinstance(mod, dict):
            continue
        operation, target, by = mod.get("operation"), str(mod.get("target", "")), mod.get("by")
        path = f"/amends/{i}"
        if operation in ("replaces", "adds") and not by:
            out.append(_finding("INVALID_SCHEMA", path, f"{operation} requires by"))
        if operation == "repeals" and by is not None:
            out.append(_finding("INVALID_SCHEMA", path, "repeals does not admit by"))
        if operation in ("replaces", "repeals") and "#" not in target:
            out.append(_finding("INVALID_SCHEMA", path, f"{operation} requires an ID#anchor target"))
        if operation == "adds":
            if "#" in target:
                out.append(_finding("INVALID_SCHEMA", path, "adds points to a decision, not to a clause"))
            if not mod.get("position"):
                out.append(_finding("INVALID_SCHEMA", path, "adds requires an explicit logical position"))
        elif "position" in mod:
            out.append(_finding("INVALID_SCHEMA", path, "position is only admitted in adds"))
        if by and not str(by).startswith(f"{record.get('id')}#"):
            out.append(_finding("INVALID_SCHEMA", path, "by identifies a clause of the record itself"))
        if m.type_of_id(target) not in (None, "decision"):
            out.append(_finding("INVALID_SCHEMA", path, "amends points to a decision"))
    for i, dep in enumerate(record.get("depends_on") or []):
        if isinstance(dep, dict) and dep.get("target") == record.get("id"):
            out.append(_finding("NORMATIVE_CONFLICT", f"/depends_on/{i}", "a record does not depend on itself"))
    return out


def _by_type(record, type_):
    out = []
    out += _repeated(record.get("sources") or [], "id", "/sources")
    if type_ == "decision":
        alts = record.get("alternatives")
        if isinstance(alts, list):
            out += _repeated(alts, "id", "/alternatives")
            reason = record.get("no_alternatives_reason")
            if not alts and not reason:
                out.append(
                    _finding("INVALID_SCHEMA", "/no_alternatives_reason", "without alternatives, say why")
                )
            if alts and reason:
                out.append(_finding("INVALID_SCHEMA", "/no_alternatives_reason", "only when there are no alternatives"))
            if alts and not any(isinstance(a, dict) and a.get("selected") is True for a in alts):
                out.append(_finding("INVALID_SCHEMA", "/alternatives", "no alternative is selected"))
        out += _defined_names(record.get("defines") or [])
    if type_ == "fact":
        present = [k for k in ("date", "interval") if k in record]
        if len(present) != 1:
            out.append(_finding("INVALID_SCHEMA", "/date", "a fact carries a date or an interval, one of the two"))
        interval = record.get("interval")
        if isinstance(interval, dict):
            out += _sorted(interval.get("from"), interval.get("until"), "/interval")
    for i, occ in enumerate(record.get("holds") or []):
        if isinstance(occ, dict):
            out += _sorted(occ.get("from"), occ.get("until"), f"/holds/{i}")
    if type_ == "milestone":
        accept = record.get("acceptance") or []
        checks = record.get("checks") or []
        out += _repeated(accept, "criterion_id", "/acceptance")
        out += _repeated(checks, "check_id", "/checks")
        criteria = {a.get("criterion_id") for a in accept if isinstance(a, dict)}
        for i, v in enumerate(checks):
            if isinstance(v, dict) and v.get("criterion_id") not in criteria:
                out.append(_finding("MISSING_REFERENCE", f"/checks/{i}/criterion_id", "nonexistent criterion"))
        for i, a in enumerate(accept):
            assisted = isinstance(a, dict) and a.get("method") == "ai_assisted_evaluation"
            if assisted and not (a.get("rubric") and a.get("disagreement_resolution")):
                out.append(
                    _finding(
                        "INVALID_SCHEMA",
                        f"/acceptance/{i}",
                        "an assisted evaluation requires a rubric and a human resolution of disagreement",
                    )
                )
    return out


def _defined_names(entries):
    """Terms and aliases of `defines`: none is a contract name and none repeats in the record."""
    out, seen = [], set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            continue
        aliases = e.get("aliases") if isinstance(e.get("aliases"), list) else []
        names = [("term", e.get("term"))] + [(f"aliases/{j}", a) for j, a in enumerate(aliases)]
        for field, name in names:
            if not isinstance(name, str):
                continue
            path = f"/defines/{i}/{field}"
            if name != name.strip():
                out.append(_finding("INVALID_SCHEMA", path, f"{name!r} has leading or trailing spaces"))
            if name.strip().casefold() in RESERVED:
                out.append(_finding("INVALID_SCHEMA", path, f"{name!r} is a type, a field or a relation"))
            if name in seen:
                out.append(_finding("INVALID_SCHEMA", path, f"{name!r} is already defined in this record"))
            seen.add(name)
    return out


def _events(record, type_, mode):
    events = record.get("events")
    if not isinstance(events, list):
        return []
    out = _repeated(events, "event_id", "/events")
    for i, ev in enumerate(events):
        class_ = ev.get("event_type") if isinstance(ev, dict) else None
        if class_ not in EVENT_BY_CLASS:
            out.append(_finding("INVALID_SCHEMA", f"/events/{i}", f"unknown event_type: {class_!r}"))
            continue
        out += _jsonschema(event_schema(class_), ev, f"/events/{i}")
        for field in ("previous_state", "new_state"):
            value = ev.get(field)
            if value is not None and value not in m.STATES[type_]:
                out.append(
                    _finding("INVALID_SCHEMA", f"/events/{i}/{field}", f"{value!r} is not a state of {type_}")
                )
        out += _sorted(ev.get("valid_from"), ev.get("valid_until"), f"/events/{i}")
    if mode == "canonical" and not out:
        out += _canonical_history(events, record, type_)
    return out


def _canonical_history(events, record, type_):
    """A canonical record materializes its state from admitted events, starting with a creation or an import."""
    local = [i for i, ev in enumerate(events) if ev.get("recorded_at") is None]
    if local:
        return [
            _finding("INVALID_SCHEMA", f"/events/{i}", "local event not admitted in a canonical record")
            for i in local
        ]
    if not any(ev.get("event_type") in m.STATE_EVENTS for ev in events):
        return [_finding("INVALID_SCHEMA", "/events", "no creation nor import: the state has no history")]
    try:
        materialized = state_at(events, None, type_)
    except (HistoryError, ValueError) as exc:
        return [_finding(getattr(exc, "code", "INVALID_SCHEMA"), "/events", str(exc))]
    out = []
    if materialized != record.get("state"):
        out.append(_finding("INVALID_SCHEMA", "/state", f"the admitted history gives {materialized!r}"))
    if type_ == "decision":
        out += _ratified_acceptance(events)
    return out


def _ratified_acceptance(events):
    """Accepting a decision requires a previous, unrevoked ratification. Integration checks its authenticity."""
    active, out = set(), []
    for i, ev in enumerate(events):
        class_ = ev.get("event_type")
        if class_ == "ratification":
            active.add(ev["approval"]["approval_id"])
        elif class_ == "approval_revocation":
            active.discard(ev.get("approval_id"))
        elif class_ == "transition" and ev.get("new_state") == "accepted" and not active:
            out.append(
                _finding("INSUFFICIENT_AUTHORITY", f"/events/{i}", "acceptance without a previous ratification in force")
            )
    return out


def _body(record, type_, body, mode):
    out = []
    try:
        anchors = clauses(body)
    except MarkupError as exc:
        return [_finding("INVALID_SCHEMA", "body", str(exc))]
    if type_ == "decision" and mode != "exchange" and not anchors:
        out.append(_finding("INVALID_SCHEMA", "body", "a decision states its rules in clauses"))
    own = f"{record.get('id')}#"
    for i, mod in enumerate(record.get("amends") or []):
        by = mod.get("by") if isinstance(mod, dict) else None
        if isinstance(by, str) and by.startswith(own) and by[len(own) :] not in anchors:
            out.append(_finding("MISSING_REFERENCE", f"/amends/{i}/by", f"the clause {by} is not in the body"))
    for i, e in enumerate(record.get("defines") or []):
        clause = e.get("clause") if isinstance(e, dict) else None
        if isinstance(clause, str) and clause not in anchors:
            out.append(
                _finding("MISSING_REFERENCE", f"/defines/{i}/clause", f"the clause {clause} is not in the body")
            )
    try:
        marks = facts(body)
    except MarkupError as exc:
        return out + [_finding("INVALID_SCHEMA", "body", str(exc))]
    citations = {s.get("id") for s in record.get("sources") or [] if isinstance(s, dict)}
    for h in marks:
        if "ref" in h:
            if m.type_of_id(h["ref"]) != "fact" or not m.RE_ID.match(h["ref"]):
                out.append(_finding("INVALID_SCHEMA", "body", f"invalid fact ref: {h['ref']}"))
            continue
        if h["evidence"] not in m.EVIDENCE_CLASSES:
            out.append(
                _finding(
                    "INVALID_SCHEMA", "body", f"unknown evidence class in {h['id']}: {h['evidence']}"
                )
            )
        if h["source"] not in citations:
            out.append(
                _finding(
                    "MISSING_REFERENCE",
                    "body",
                    f"the fact {h['id']} cites the source {h['source']}, which is not in sources",
                )
            )
    return out
