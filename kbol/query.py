"""Query by ID: given `ID` or `ID#anchor`, the record with its state at the cut, its authority and the anchor text.

It is the basis of linking a memory or a note to canonical knowledge: resolve what is cited without interpreting it.
A canonical ID returns its type, its state at the knowledge cut, its authority (declared, inherited or none checked),
its relations and, with an anchor, the text of the clause; for a decision, also whether that clause is in force at
`valid_at`. A legacy ID is named with its legacy state and is not in force. An ID that does not exist, or an anchor
its record does not have, is reported as such. Its evidence is its supports, the same ones `support` evaluates
(`based_on`, `dependencies`, `sources` and `<fact ref>`), with the same validity rule: a support that does not exist,
is not in force at the cut or cannot be decided, or a body whose citations cannot be read, leaves the evidence
insufficient with its reason. It only reads.
"""

from . import support
from .consolidate import _Query, consolidate
from .markdown import MarkupError, clauses
from .model import RELATIONS, WORK_FIELDS
from .mutability import CLOSED
from .projection import state_at_cut
from .supersessions import alerts_for, undeclared
from .timeutil import instant

# Relations that are reported: the header lists that point to other records, except the supports that are fields of
# the type itself (`dependencies`, `sources`), reported in the evidence. The owner goes in the work.
# `defines` does not point to another record, but says which terms a decision declares.
_RELATIONS = (*RELATIONS, "amends", "depends_on", "holds", "milestones", "defines")


def _anchors(body):
    try:
        return clauses(body or "")
    except MarkupError:
        return None


def _evidence(query_, r, body):
    """Supports of the record with whether they exist and are in force; None if it declares none."""
    evaluated = support.evaluate(query_, r, body)
    if not evaluated["supports"] and "body" not in evaluated:
        return None
    evidence = {
        "supports": [{**a, "exists": a["situation"] != "missing"} for a in evaluated["supports"]],
        "sufficient": evaluated["support"] == "intact",
    }
    if not evidence["sufficient"]:
        reasons = [
            f"{a['ref']} {a['situation']}: {a['reason']}"
            for a in evaluated["supports"]
            if a["situation"] in support.DO_NOT_SUPPORT
        ]
        evidence["reason"] = "; ".join(reasons + ([evaluated["body"]] if "body" in evaluated else []))
    return evidence


def _one(snapshot, query_, ref, valid_at, known_until):
    ident, _, anchor = ref.partition("#")
    if ident not in snapshot.records:
        if ident in snapshot.legacy:
            card = snapshot.legacy[ident]
            return {
                "reference": ref,
                "found": "legacy",
                "id": ident,
                "type": card.get("type"),
                "path": card.get("path"),
                "legacy_state": card.get("legacy_state"),
                "proposed_state": card.get("proposed_state"),
                "in_force": False,
            }
        return {"reference": ref, "found": "missing", "id": ident}
    r, body = snapshot.records[ident], snapshot.bodies.get(ident)
    output = {
        "reference": ref,
        "found": "canonical",
        "id": ident,
        "type": r.get("type"),
        "title": r.get("title"),
        "scope": r.get("scope"),
        "path": snapshot.paths.get(ident),
        "state": state_at_cut(r, known_until),
        "authority": {
            "authorized_by": list(r.get("authorized_by") or []),
            "ratifications": query_._ratifications(r),
            "declared": query_._declared_f(r),
            "approvals": query_._approvals(r),
            "inherited": query_._inherited(r),
            "checked": False,
        },
        "relations": {rel: r[rel] for rel in _RELATIONS if r.get(rel)},
    }
    # Who declares it superseded or amended: the relation lives in the other record and is read backwards here.
    inverse = {
        "superseded_by": sorted(i for i, o in snapshot.records.items() if ident in (o.get("supersedes") or [])),
        "amended_by": sorted(m for m, _ in query_.by_target.get(ident, []))
        + sorted({m for d, mods in query_.by_target.items() if d.startswith(f"{ident}#") for m, _ in mods}),
    }
    inverse = {k: list(dict.fromkeys(v)) for k, v in inverse.items() if v}
    if inverse:
        output["inverse_relations"] = inverse
    work = {k: r[k] for k in WORK_FIELDS if r.get(k)}
    if work:
        output["work"] = work
    if r.get("type") == "person":
        output["assigned"] = assigned(snapshot, ident, valid_at)
    if anchor:
        anchors = _anchors(body)
        if anchors is None or anchor not in anchors:
            output["found"] = "missing_anchor"
            return output
        output["text"] = anchors[anchor]
    if r.get("type") == "decision":
        validity = consolidate(snapshot, [ident], valid_at=valid_at, known_until=known_until)
        output["validity"] = validity["validity"].get(ident)
        if anchor:
            clause = next((c for c in validity["clauses"] if c.get("reference") == ref), None)
            if clause:
                output["clause"] = {k: clause.get(k) for k in ("state", "text", "origin", "chain")}
    evidence = _evidence(query_, r, body)
    if evidence:
        output["evidence"] = evidence
    return output


def _roles_of(person, when):
    """Roles the person holds at `when`; without a cut, those held without an end date."""
    t = instant(when) if when else None
    roles = set()
    for o in person.get("holds") or []:
        if not isinstance(o, dict) or not isinstance(o.get("role"), str):
            continue
        until = o.get("until")
        if t is None:
            if until is None:
                roles.add(o["role"])
        elif instant(o["from"]) <= t and (until is None or t < instant(until)):
            roles.add(o["role"])
    return roles


def assigned(snapshot, person_id, valid_at=None):
    """Milestones and questions the person is responsible for, directly or through a role they hold.

    Tasks are not copied into the person: they are read here, from a single source. It also lists whether each one is
    still open, to separate what is pending from what is closed.
    """
    person = snapshot.records.get(person_id) or {}
    who = {person_id} | _roles_of(person, valid_at)
    output = []
    for i, r in sorted(snapshot.records.items()):
        if r.get("type") in ("milestone", "question") and r.get("owner") in who:
            state = r.get("state")
            output.append(
                {
                    "id": i,
                    "type": r["type"],
                    "title": r.get("title"),
                    "state": state,
                    "via": r["owner"],
                    "open": state not in CLOSED.get(r["type"], ()),
                }
            )
    return output


def query(snapshot, references, *, valid_at, known_until):
    """{cuts, results, warnings} for each `ID` or `ID#anchor` of `references`, in their order."""
    query_ = _Query(snapshot, valid_at, known_until)
    results = [_one(snapshot, query_, ref, valid_at, known_until) for ref in references]
    warnings = list(query_.warnings)
    hints = undeclared(snapshot)
    for res in results:
        alerts = alerts_for(hints, [res["id"]])
        if alerts:
            res["supersession_alerts"] = alerts
            warnings += [a for a in alerts if a not in warnings]
    for res in results:
        if res["found"] == "legacy":
            warnings.append(f"{res['id']} is in legacy format: it is named, but it is not in force")
        elif res["found"] in ("missing", "missing_anchor"):
            warnings.append(f"{res['reference']}: {res['found'].replace('_', ' ')}")
        if res.get("evidence") and not res["evidence"]["sufficient"]:
            warnings.append(f"{res['reference']}: INSUFFICIENT_EVIDENCE, {res['evidence']['reason']}")
    return {
        "cuts": {"valid_at": valid_at, "known_until": known_until, "revision": snapshot.revision},
        "results": results,
        "warnings": warnings,
    }
