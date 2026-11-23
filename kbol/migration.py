"""Dry-run migration of the legacy format (KB-DPP implementation 1.0, §14).

Read only. For each record it proposes a type, a state, candidate relations and an import event without an
incorporation instant, which the integration assigns. It invents neither approvals nor time precision: authority
written in prose is classified, and everything that does not translate one to one is left as an ambiguity for human
review.

The default legacy format (`DEFAULT`) is that of numbered ADRs, QD, HD, plans and milestones, with English labels
(`type: Decision`, `state: Accepted`, `Superseded by …`). A project with the same shape and other IDs or state words
(for example Spanish ones) declares it in its installation (`legacy_format`): its words are translated to the headers
of the legacy table, which decides with its review rules. Without that declaration, `DEFAULT` applies.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .core import FormatError, parse
from .model import TYPE_OF_PREFIX, TYPES
from .schema import fields_of

PRODUCER = "kbol-migration/0.2"
LEGACY_TYPE = {
    "Decision": "decision",
    "Question": "question",
    "Hypothesis": "hypothesis",
    "Plan": "plan",
    "Milestone": "milestone",
}
_IDS = re.compile(r"\b(?:ADR-\d{4}|QD-\d{3,}|HD-\d{3,}|PL-\d{3}(?:-H\d+)?)\b")
# Full shape of an ID of the default legacy format: with fullmatch, neither prefixes nor suffixes.
LEGACY_ID = re.compile(r"(?:ADR-\d{4}|QD-\d{3,}|HD-\d{3,}|PL-\d{3}(?:-H\d+)?)")
# File name of a record of the default legacy format: ADR ("0063-slug.md", not "2026-05-19-x.md"), QD, HD, plan or milestone.
RECORD_NAME = re.compile(r"(?:\d{4}-[a-z].*|(?:QD|HD)-\d{3,}|PL-\d{3}(?:-H\d+)?)\.md")
# State headers the legacy table understands, per type: the possible targets of an equivalence.
HEADERS = {
    "decision": ("Proposed", "Accepted", "Rejected", "Superseded by"),
    "question": ("Open", "Resolved", "Discarded", "Under review"),
    "hypothesis": ("Open", "Under validation", "Validated", "Discarded", "Obsolete"),
    "plan": ("Proposed", "Approved", "Closed", "In progress", "Rejected", "Abandoned", "Superseded by"),
    "milestone": ("Pending", "In progress", "Done", "Discarded"),
}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# States whose normative use requires a checkable authority.
WITH_AUTHORITY = {"accepted", "authorized", "in_progress", "completed", "closed"}


@dataclass(frozen=True)
class LegacyFormat:
    """How a project writes its legacy format.

    - `types`: `type` label → contract type.
    - `ids`: label → pattern that the whole ID of a record with that label matches.
    - `in_text`: IDs of the format cited in prose.
    - `decision`: decision IDs, the only ones valid as `resolved_by`.
    - `names`: file name of a record without `id`.
    - `equivalences`: label → {project state word: header of the legacy table}.
    - `separators`: characters that close the state header.
    """

    types: dict
    ids: dict
    in_text: re.Pattern
    decision: re.Pattern
    names: re.Pattern
    equivalences: dict
    separators: str = "(;"

    def is_record(self, path):
        """True if the file name is that of a record: "0063-….md", "QD-045.md", "DEC-108.md"…

        A document with a record `type` (a work plan, a roadmap) but with neither `id` nor a record name is not a
        record: it is omitted like any other document.
        """
        return bool(self.names.fullmatch(Path(path).name))

    def valid_id(self, label, ident):
        return isinstance(ident, str) and label in self.ids and bool(self.ids[label].fullmatch(ident))

    def normalize(self, label, text):
        """The state with its initial word translated to the equivalent header of the legacy table."""
        for word, header in sorted(self.equivalences.get(label, {}).items(), key=lambda p: -len(p[0])):
            rest = text[len(word) :]
            if text.startswith(word) and not (rest[:1].isalnum() or rest[:1] == "_"):
                return header + rest
        return text


DEFAULT = LegacyFormat(
    types=LEGACY_TYPE,
    ids=dict.fromkeys(LEGACY_TYPE, LEGACY_ID),
    in_text=_IDS,
    decision=re.compile(r"ADR-\d{4}"),
    names=RECORD_NAME,
    equivalences={},
)


def format_of(installation):
    """The legacy format the installation declares (`legacy_format`), or `DEFAULT` if it declares none.

    ValueError if the declaration is malformed: better to read nothing than to read with half a format.
    """
    f = installation.get("legacy_format") if isinstance(installation, dict) else None
    if f is None:
        return DEFAULT
    if not isinstance(f, dict):
        raise ValueError("legacy_format is an object")
    for key in f:
        if key not in ("records", "separators"):
            raise ValueError(f"legacy_format: unknown key {key!r}")
    records = f.get("records")
    if not isinstance(records, dict) or not records:
        raise ValueError("legacy_format.records maps at least one type label to its type and its id")
    separators = f.get("separators", "(;")
    if not isinstance(separators, str) or not separators:
        raise ValueError("legacy_format.separators is a non-empty string")
    types, ids, equivalences, patterns, of_decision = {}, {}, {}, [], []
    for label, d in records.items():
        where = f"legacy_format.records[{label!r}]"
        if label in TYPES:
            raise ValueError(f"{where}: {label!r} is a type of the profile, not a legacy label")
        if not isinstance(d, dict):
            raise ValueError(f"{where} is an object with type, id and, if needed, equivalences")
        for key in d:
            if key not in ("type", "id", "equivalences"):
                raise ValueError(f"{where}: unknown key {key!r}")
        type_, pattern, equiv = d.get("type"), d.get("id"), d.get("equivalences", {})
        if type_ not in HEADERS:
            raise ValueError(f"{where}: type {type_!r} does not admit a legacy format ({', '.join(HEADERS)})")
        if not isinstance(pattern, str):
            raise ValueError(f"{where}: id is the pattern of its IDs")
        try:
            ids[label] = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"{where}: invalid id pattern: {exc}") from None
        prefix = re.match(r"([A-Z]{1,4})-", pattern)
        if not prefix:
            raise ValueError(f"{where}: the id pattern starts with a literal uppercase prefix and a hyphen")
        if TYPE_OF_PREFIX.get(prefix.group(1), type_) != type_:
            raise ValueError(f"{where}: prefix {prefix.group(1)}- belongs to another contract type")
        if not isinstance(equiv, dict):
            raise ValueError(f"{where}: equivalences is an object")
        for word, header in equiv.items():
            if not word or header not in HEADERS[type_]:
                raise ValueError(
                    f"{where}: equivalence {word!r} → {header!r}: the legacy table has no such header "
                    f"for {type_} ({', '.join(HEADERS[type_])})"
                )
        types[label], equivalences[label] = type_, dict(equiv)
        patterns.append(f"(?:{pattern})")
        if type_ == "decision":
            of_decision.append(f"(?:{pattern})")
    every = "|".join(patterns)
    return LegacyFormat(
        types=types,
        ids=ids,
        in_text=re.compile(rf"\b(?:{every})\b"),
        decision=re.compile("|".join(of_decision) or r"(?!)"),
        names=re.compile(rf"(?:{every})\.md"),
        equivalences=equivalences,
        separators=separators,
    )


def _resolved_by(format, field, state_ids):
    """Candidate decisions: those of the `resolved_by` field (text or list) and then those the state cites."""
    texts = field if isinstance(field, list) else [field]
    from_field = []
    for text in (t for t in texts if isinstance(t, str)):
        from_field += [x.group(0) for x in format.in_text.finditer(text) if format.decision.fullmatch(x.group(0))]
    from_field = list(dict.fromkeys(from_field))
    return from_field + [i for i in state_ids if format.decision.fullmatch(i) and i not in from_field]


def _scp(field, reason, candidates=()):
    return {"field": field, "candidates": list(candidates), "reason": reason}


def _map_to(type_, text, format=DEFAULT, resolved_by=None):
    """(proposed state or None, ambiguities, proposed relations).

    `resolved_by` is the field of the same name in the legacy record, if it has one: a text or a list of texts.
    """
    t = text.strip()
    head = re.split(f"[{re.escape(format.separators)}]", t, maxsplit=1)[0].strip()
    ids = [x.group(0) for x in format.in_text.finditer(t)]
    amb, rel = [], {}
    if type_ == "decision":
        if t.startswith("Accepted; partially superseded by"):
            amb.append(_scp("amends", "partial supersession in prose: anchors and scope undetermined", ids))
            return "accepted", amb, rel
        if t.startswith("Superseded by"):
            amb.append(
                _scp(
                    "supersedes",
                    "succession declared in the superseded record; the relation goes in the successor",
                    ids,
                )
            )
            return "accepted", amb, rel
        state = {"Proposed": "proposed", "Accepted": "accepted", "Rejected": "rejected"}.get(head)
    elif type_ == "question":
        if head == "Resolved" and "fact:" in t:
            amb.append(_scp("based_on", "factual closure without a recorded source: a source or a fact is needed"))
            return "resolved", amb, rel
        if head == "Resolved":
            rel["resolved_by"] = _resolved_by(format, resolved_by, ids)
            if not rel["resolved_by"]:
                amb.append(_scp("resolved_by", "resolved without an identifiable decision"))
            return "resolved", amb, rel
        if head == "Under review":
            amb.append(_scp("state", '"Under review" does not exist in the contract; it stays open'))
            return "open", amb, rel
        state = {"Open": "open", "Discarded": "discarded"}.get(head)
    elif type_ == "hypothesis":
        if head == "Under validation":
            amb.append(_scp("state", '"Under validation" does not exist in the contract; it stays open'))
            return "open", amb, rel
        if head == "Validated":
            amb.append(_scp("state", "validated only under the tested conditions: review protocol and evidence"))
            return "validated", amb, rel
        if head in ("Discarded", "Obsolete"):
            amb.append(_scp("state", f'"{head}" may be refuted or retired: decide with the evidence', ids))
            return "retired", amb, rel
        state = {"Open": "open"}.get(head)
    elif type_ == "plan":
        if head == "In progress":
            amb.append(_scp("state", '"In progress" does not exist for plans; progress lives in the milestones'))
            return "authorized", amb, rel
        if head in ("Rejected", "Abandoned") or t.startswith("Superseded by"):
            amb.append(_scp("state", f'"{head}" is represented as cancelled; keep the reason', ids))
            return "cancelled", amb, rel
        state = {"Proposed": "proposed", "Approved": "authorized", "Closed": "closed"}.get(head)
    elif type_ == "milestone":
        if head == "Pending":
            amb.append(_scp("state", "the milestone's own authorization is not recorded; the plan's is not enough"))
            return "proposed", amb, rel
        if head == "In progress":
            amb.append(_scp("state", "in progress without an accredited authorization of the milestone"))
            return "in_progress", amb, rel
        if head == "Done":
            amb.append(
                _scp(
                    "state",
                    "completed requires acceptance per criterion and evidence on the tested revision; "
                    "review evidence and verifies",
                )
            )
            return "completed", amb, rel
        state = {"Discarded": "cancelled"}.get(head)
    else:
        state = None
    if state is None:
        amb.append(_scp("state", f"legacy state without a match: {t!r}"))
    return state, amb, rel


def _authority(meta):
    text = meta.get("adopted_by") or meta.get("approved_by")
    if not isinstance(text, str) or text.strip() in ("", "—"):
        return None
    class_ = "pending" if text.strip().lower().startswith("pending") else "insufficient"
    return {"text": text, "classification": class_}


def inspect(text, path, revision, format=DEFAULT):
    base = {"path": path, "revision": revision, "original": text}
    if Path(path).name == "index.md":
        return {**base, "result": "out_of_scope", "type": None, "reason": "generated index: a view, not a record"}
    try:
        meta, _ = parse(text)
    except FormatError as exc:
        return {**base, "result": "failed", "code": "INVALID_SCHEMA", "message": str(exc), "type": None}
    type_ = format.types.get(meta.get("type"))
    if type_ is None:
        return {
            **base,
            "result": "out_of_scope",
            "type": None,
            "reason": f"type {meta.get('type')!r} is not a record",
        }
    legacy = str(meta.get("state", ""))
    normalized = format.normalize(meta.get("type"), legacy.strip())
    state, amb, rel = _map_to(type_, normalized, format, meta.get("resolved_by"))
    date = meta.get("date")
    with_day = isinstance(date, str) and bool(_DATE.match(date))
    authority = _authority(meta)
    props, _ = fields_of(type_)
    event = {
        "event_id": None,
        "event_type": "import",
        "actor": PRODUCER,
        "recorded_at": None,
        "valid_from": date if with_day else None,
        "precision": "day" if with_day else "unknown",
        "reason": "import from the legacy format",
        "previous_state": None,
        "new_state": state,
        "legacy_state": legacy,
        "provenance": {"path": path, "revision": revision},
        "event_evidence": None,
    }
    requires = (
        bool(amb)
        or state is None
        or (
            state in WITH_AUTHORITY
            and (authority is None or authority["classification"] != "checked")
            and type_ != "question"
        )
    )
    return {
        **base,
        "result": "proposed",
        "id": meta.get("id"),
        "type": type_,
        "legacy_state": legacy,
        "proposed_state": state,
        "ambiguities": amb,
        "proposed_relations": rel,
        "inherited_authority": authority,
        "import_event": event,
        "fields_without_target": sorted(k for k in meta if k not in props),
        "requires_review": requires,
    }


def inspect_folder(folder, revision, format=DEFAULT):
    folder = Path(folder)
    files = [folder] if folder.is_file() else sorted(folder.rglob("*.md"))
    reports = [
        inspect(
            p.read_text(encoding="utf-8"),
            p.relative_to(folder.parent if folder.is_file() else folder).as_posix(),
            revision,
            format,
        )
        for p in files
    ]
    summary = {
        "total": len(reports),
        "proposed": sum(i["result"] == "proposed" for i in reports),
        "out_of_scope": sum(i["result"] == "out_of_scope" for i in reports),
        "failed": sum(i["result"] == "failed" for i in reports),
        "require_review": sum(bool(i.get("requires_review")) for i in reports),
    }
    return {"summary": summary, "reports": reports}
