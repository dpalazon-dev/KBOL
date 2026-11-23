"""Closed vocabulary of the KB-DPP contract (core 1.0, "Concrete contracts" and "State contract").

The local choices that the contract leaves open are in docs/design-choices.md.
"""

import re
from dataclasses import dataclass

TYPES = (
    "source",
    "fact",
    "decision",
    "person",
    "role",
    "question",
    "hypothesis",
    "assumption",
    "entity",
    "plan",
    "milestone",
    "synthesis",
)
PREFIX = dict(zip(TYPES, ("SRC", "FACT", "DEC", "PER", "ROLE", "Q", "HYP", "ASM", "ENT", "PLAN", "MS", "SYN")))
TYPE_OF_PREFIX = {v: k for k, v in PREFIX.items()}
# IDs of the default legacy format (KB-DPP contract, "Identity"): they are kept as identity.
LEGACY_IDS = (
    (re.compile(r"^ADR-\d{4}(?!\n)$"), "decision"),
    (re.compile(r"^QD-\d{3,}(?!\n)$"), "question"),
    (re.compile(r"^HD-\d{3,}(?!\n)$"), "hypothesis"),
    (re.compile(r"^PL-\d{3}-H\d+(?!\n)$"), "milestone"),
    (re.compile(r"^PL-\d{3}(?!\n)$"), "plan"),
)
CLASSES = ("record", "source", "fixed", "view", "archive")

STATES = {
    "decision": ("proposed", "accepted", "rejected"),
    "fact": ("proposed", "accepted", "rejected"),
    "question": ("open", "resolved", "discarded"),
    "hypothesis": ("open", "validated", "refuted", "retired"),
    "assumption": ("active", "retired"),
    "plan": ("proposed", "authorized", "closed", "cancelled"),
    "milestone": ("proposed", "authorized", "in_progress", "completed", "cancelled"),
    "source": ("registered", "retired"),
    "person": ("proposed", "active", "retired"),
    "role": ("proposed", "active", "retired"),
    "entity": ("proposed", "active", "retired"),
    "synthesis": ("draft", "current", "retired"),
}
INITIAL = {t: e[0] for t, e in STATES.items()}
TRANSITIONS = {
    "decision": {("proposed", "accepted"), ("proposed", "rejected")},
    "fact": {("proposed", "accepted"), ("proposed", "rejected")},
    "question": {("open", "resolved"), ("open", "discarded")},
    "hypothesis": {("open", "validated"), ("open", "refuted"), ("open", "retired")},
    "assumption": {("active", "retired")},
    "plan": {
        ("proposed", "authorized"),
        ("proposed", "cancelled"),
        ("authorized", "closed"),
        ("authorized", "cancelled"),
    },
    "milestone": {
        ("proposed", "authorized"),
        ("proposed", "cancelled"),
        ("authorized", "in_progress"),
        ("authorized", "cancelled"),
        ("in_progress", "completed"),
        ("in_progress", "cancelled"),
    },
    "source": {("registered", "retired")},
    "synthesis": {("draft", "current"), ("draft", "retired"), ("current", "draft"), ("current", "retired")},
}
for _t in ("person", "role", "entity"):
    TRANSITIONS[_t] = {("proposed", "active"), ("proposed", "retired"), ("active", "retired")}

# State in which the record is in force or exists for the validity query.
EFFECTIVE = {"decision": "accepted", "fact": "accepted", "source": "registered"}

EVENTS = (
    "creation",
    "transition",
    "ratification",
    "approval_revocation",
    "evaluation",
    "holding_change",
    "impact_resolution",
    "import",
)
# Events that set the materialized state.
STATE_EVENTS = ("creation", "transition", "import")

EVIDENCE_CLASSES = ("observed", "computed", "declared", "modeled", "predicted", "assumed")
CONDITIONS = ("accepted_and_in_force", "resolved", "completed_with_evidence", "available_with_integrity")
PROCESSING = ("pending", "processed", "partial", "failed")
EVALUATION_RESULT = ("conforming", "non_conforming", "partial", "not_evaluated")
ACCEPTANCE_METHODS = ("command", "human_review", "ai_assisted_evaluation")
PRECISIONS = ("instant", "minute", "hour", "day", "month", "year")
# Term classes of the domain vocabulary: for now, only the entity class.
TERM_CLASSES = ("entity_class",)

CODES = (
    "INVALID_SCHEMA",
    "MISSING_REFERENCE",
    "INSUFFICIENT_AUTHORITY",
    "STALE_APPROVAL",
    "BASE_CHANGED",
    "NORMATIVE_CONFLICT",
    "AMBIGUOUS_TIME",
    "INTEGRITY_BROKEN",
    "INTEGRITY_UNCHECKED",
    "INSUFFICIENT_EVIDENCE",
    "ACCESS_DENIED",
    "UNKNOWN_RESULT",
)

FORMS = ("ids", "objects", "id", "body")
# Forbidden cycles, in the order they are checked: succession, derivation and executable dependency.
CYCLES = ("succession", "derivation", "dependency")


@dataclass(frozen=True)
class Reference:
    """A field that points to other records: where it is declared, where it points and how the engine treats it.

    - `origin`: types that declare it; None, any record.
    - `target`: admitted types, `"same"` (the type of the origin) or None (any, or no target).
    - `anchor`: `"forbidden"`, `"required"` or `"optional"`; None if it has no target.
    - `shape`: `"ids"` (list of IDs), `"objects"` (list of maps), `"id"` (one ID) or `"body"` (`<fact ref>` citations).
    - `key`: in `"objects"`, the key that carries the target; None if it carries none.
    - `relation`: this table gives its shape (core relations); False if its type declares it in the schema.
    - `consumption`: whoever declares it consumes the target; a change in the target reaches it as impact.
    - `without_cycles`: the class of forbidden cycle (`CYCLES`) it belongs to, or None if a cycle is legitimate.
    - `free`: changing it does not reopen a closure nor an authorization, because it does not change what is in force.
    - `evidence`: the target supports the record (support of the `support` query).
    """

    origin: tuple | None
    target: tuple | str | None
    anchor: str | None
    shape: str = "ids"
    key: str | None = None
    relation: bool = True
    consumption: bool = False
    without_cycles: str | None = None
    free: bool = False
    evidence: bool = False


_R = Reference
# References between records. The order is that of the walk and of the reports.
REFERENCES = {
    # Own fields with a target: their type declares their shape in the schema.
    "dependencies": _R(("synthesis",), None, "optional", relation=False, consumption=True, evidence=True),
    "sources": _R(None, None, "forbidden", "objects", "resource", relation=False, consumption=True, evidence=True),
    "body": _R(None, ("fact",), "forbidden", "body", relation=False, consumption=True, evidence=True),
    # Relations: admitted origin types (core table "Relations") and shape of the target.
    "resolved_by": _R(("question",), ("decision",), "forbidden", consumption=True),
    "challenges": _R(("question",), ("decision",), "required", consumption=True),
    "supersedes": _R(("decision", "fact", "source"), "same", "forbidden", without_cycles="succession"),
    "tests": _R(("hypothesis",), ("decision",), "required", consumption=True),
    "based_on": _R(
        ("decision", "fact", "hypothesis", "question"), ("source", "fact"), "optional", consumption=True, evidence=True
    ),
    "derived_from": _R(("source",), ("source",), "forbidden", consumption=True, without_cycles="derivation"),
    "affects": _R(("decision", "fact", "question"), None, "optional"),
    "authorized_by": _R(("decision", "plan", "milestone"), ("role",), "forbidden", consumption=True),
    # Work links (local choice, docs/design-choices.md, "Work links"): they do not change what is in force.
    "closes": _R(("milestone",), ("question",), "forbidden", consumption=True, free=True),
    "advances": _R(("milestone",), ("question",), "forbidden", consumption=True, free=True),
    "tests_hypothesis": _R(("milestone",), ("hypothesis",), "forbidden", consumption=True, free=True),
    "produces": _R(("milestone",), None, "optional", consumption=True, free=True),
    "relies_on": _R(("plan",), ("decision",), "optional", consumption=True, free=True),
    # Relations with typed objects.
    "amends": _R(("decision",), ("decision",), "optional", "objects", "target", without_cycles="succession"),
    "depends_on": _R(
        ("question", "decision", "plan", "milestone"),
        None,
        "optional",
        "objects",
        "target",
        consumption=True,
        without_cycles="dependency",
    ),
    "holds": _R(("person",), ("role",), "forbidden", "objects", "role", consumption=True),
    "vetoes": _R(("decision",), None, None, "objects"),
    # Domain terms that a decision declares (local choice): without a target, like `vetoes`.
    "defines": _R(("decision",), None, None, "objects"),
    # Own work fields with a target.
    "owner": _R(("question", "milestone"), ("role", "person"), "forbidden", "id", relation=False, free=True),
    "milestones": _R(("plan",), ("milestone",), "forbidden", relation=False),
}

# Views of the table.
RELATIONS = {
    c: {"origin": r.origin, "target": r.target, "anchor": r.anchor}
    for c, r in REFERENCES.items()
    if r.relation and r.shape == "ids"
}
LINKS = tuple(c for c in RELATIONS if REFERENCES[c].free)
# Work fields, free like the links: who answers, what proves it and how much is done.
WORK_FIELDS = ("owner", "evidence", "implementation")
IMPLEMENTATION = ("complete", "partial", "pending", "not_applicable")
# Relations with typed objects: admitted origin types.
OBJECT_RELATIONS = {c: r.origin for c, r in REFERENCES.items() if r.relation and r.shape == "objects"}
NO_CYCLES = tuple(c for class_ in CYCLES for c, r in REFERENCES.items() if r.without_cycles == class_)

ID_UUID = (
    r"(SRC|FACT|DEC|PER|ROLE|Q|HYP|ASM|ENT|PLAN|MS|SYN)-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
ANCHOR = r"C[A-Za-z0-9_-]+"
RE_ANCHOR = re.compile(rf"^{ANCHOR}(?!\n)$")
RE_ID = re.compile(r"^[A-Z]{1,4}-[A-Za-z0-9][A-Za-z0-9_-]*(?!\n)$")
RE_ANCHOR_ID = re.compile(rf"^[A-Z]{{1,4}}-[A-Za-z0-9][A-Za-z0-9_-]*(#{ANCHOR})?(?!\n)$")


def type_of_id(ident):
    """Type imposed by the ID, or None if no known convention imposes one."""
    if not isinstance(ident, str):
        return None
    base = ident.split("#", 1)[0]
    for pattern, type_ in LEGACY_IDS:
        if pattern.match(base):
            return type_
    prefix = base.split("-", 1)[0]
    return TYPE_OF_PREFIX.get(prefix)
