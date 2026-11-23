"""The `support` query: whether what holds up each record is in force at the two cuts, and what changed.

The supports of a record are its `based_on`, the `dependencies` of a synthesis, the sources cited in
`sources[].resource` and the `<fact ref>` citations of its body. Each support is evaluated with
`dependencies.in_force_at_cut`, the same rule used by dependencies and by the evidence of `query`, and carries the
field it comes from. The summary of a record is derived like this:

- `broken` if some support is `not_in_force` or `missing`;
- otherwise, `undetermined` if some is `undetermined` or the body has a malformed mark (its citations are not
  known);
- otherwise, `intact` if it has some support, and `no_supports` if it has none.

`legacy` and `no_validity` do not break by themselves, but they are listed. A cited synthesis reports its state at
the cut (`no_validity`); its own supports are not walked from whoever cites it, they are read in its own entry. So no
cycle guard is needed.

It only reads: it does not change states, does not satisfy or break a dependency and does not block work. What the
owner of a record with a broken support does is outside this query.
"""

from collections import Counter

from .consolidate import _Query
from .dependencies import IN_FORCE_IF, MISSING, NOT_IN_FORCE, UNDETERMINED, in_force_at_cut
from .events import HistoryError
from .markdown import MarkupError, facts
from .projection import state_at_cut
from .references import edges

# Header fields that hold up a record (those with the `evidence` trait in `model.REFERENCES`), in the order in which
# they are reported. The body citations go last.
FIELDS = ("based_on", "dependencies", "sources")
BROKEN = (NOT_IN_FORCE, MISSING)
# Situations of a support that do not hold it up: they break the support or leave it undetermined.
DO_NOT_SUPPORT = (*BROKEN, UNDETERMINED)


def supports(record, body):
    """([(field, reference)], alert): the declared supports, without repeats, and the body error if it could not be read.

    `field` is `based_on`, `dependencies`, `sources` or `body` (a `<fact ref>` citation). A malformed mark is not kept
    quiet: the alert says so and the body citations remain unknown.
    """
    seen = []
    for field, ref in edges(record):
        if field in FIELDS and (field, ref) not in seen:
            seen.append((field, ref))
    seen.sort(key=lambda pair: FIELDS.index(pair[0]))
    try:
        citations = [h["ref"] for h in facts(body or "") if "ref" in h]
    except MarkupError as exc:
        return seen, f"malformed body, its citations are not known ({exc})"
    for ref in citations:
        if ("body", ref) not in seen:
            seen.append(("body", ref))
    return seen, None


RETIRED_ONES = ("retired",)


def summary(evaluated, alert=None):
    """`broken`, `undetermined`, `intact` or `no_supports` according to the situations of the supports (see the module)."""
    situations = {a["situation"] for a in evaluated}
    # A support without an effective state (a synthesis, an entity) does not break by itself, unless it is retired.
    retired = any(a["situation"] == "no_validity" and a.get("state") in RETIRED_ONES for a in evaluated)
    if situations & set(BROKEN) or retired:
        return "broken"
    if UNDETERMINED in situations or alert:
        return "undetermined"
    return "intact" if evaluated else "no_supports"


def evaluate(query_, record, body):
    """{supports, support} of a record at the cuts of `query_` (a `consolidate._Query`), and `body` if it failed."""
    list_, alert = supports(record, body)
    evaluated = [{"ref": ref, "field": field, **in_force_at_cut(query_, ref)} for field, ref in list_]
    output = {"supports": evaluated, "support": summary(evaluated, alert)}
    if alert:
        output["body"] = alert
        query_.warn(f"{record.get('id')}: {alert}")
    return output


def support(snapshot, *, valid_at, known_until, ids=None):
    """{cuts, records, count, records_examined, missing, legacy, warnings}.

    Without `ids`, every record of the snapshot. Each record: {id, type, state, supports, support}, and each support:
    {ref, field, situation, reason, code} with, if known, `state`, `transition`, `chain`, `origin` and `successors`.
    `known_until=None` uses the whole admitted history and warns about it.
    """
    query_ = _Query(snapshot, valid_at, known_until)
    if known_until is None:
        query_.warn("no knowledge cut: the whole admitted history of the revision is used")
    # Without `ids`, the legacy ones too: they are not examined, and saying so avoids taking an incomplete base as complete.
    every = sorted([*snapshot.records, *snapshot.legacy])
    requested = every if ids is None else list(dict.fromkeys(i.partition("#")[0] for i in ids))
    records, missing, legacy = [], [], []
    for ident in requested:
        r = snapshot.records.get(ident)
        if r is None:
            if ident in snapshot.legacy:
                card = snapshot.legacy[ident]
                legacy.append(card)
                query_.warn(f"{ident}: legacy format ({card['legacy_state']}); no admitted history")
            else:
                missing.append(ident)
            continue
        try:
            state = state_at_cut(r, known_until)
        except HistoryError as exc:
            state = None
            query_.warn(f"{exc.code}: {ident}: inconsistent history ({exc})")
        evaluated_ = evaluate(query_, r, snapshot.bodies.get(ident))
        records.append({"id": ident, "type": r.get("type"), "state": state, **evaluated_})
    return {
        "cuts": {"valid_at": valid_at, "known_until": known_until, "revision": snapshot.revision},
        "records": records,
        "count": dict(sorted(Counter(r["support"] for r in records).items())),
        "records_examined": len(records),
        "missing": missing,
        "legacy": legacy,
        "warnings": query_.warnings,
    }


def _explanation(before, after):
    """What explains the change: the chain, the origin or the successors of the side not in force, and the transition."""
    side = after if after["situation"] != IN_FORCE_IF else before
    explanation = {k: side[k] for k in ("chain", "origin", "successors") if k in side}
    if before.get("transition") != after.get("transition"):
        explanation["transition"] = {"before": before.get("transition"), "after": after.get("transition")}
    elif side.get("transition"):
        explanation["transition"] = side["transition"]
    return explanation


def _without_key(support_):
    return {k: v for k, v in support_.items() if k not in ("ref", "field")}


def delta(snapshot, before, after, ids=None):
    """Supports whose situation changes between two pairs of cuts, with what explains it.

    `before` and `after` are {valid_at, known_until}. Returns {before, after, changes, records, records_examined,
    missing, legacy, warnings}: `changes` lists {id, ref, field, before, after, explanation} and `records`, the records
    whose summary changes. The supports are the same at both cuts, because they come from the same snapshot.
    """
    a = support(snapshot, ids=ids, **before)
    d = support(snapshot, ids=ids, **after)
    previous = {r["id"]: r for r in a["records"]}
    changes, records = [], []
    for rd in d["records"]:
        ra = previous[rd["id"]]
        if ra["support"] != rd["support"]:
            records.append({"id": rd["id"], "before": ra["support"], "after": rd["support"]})
        by_key = {(x["field"], x["ref"]): x for x in ra["supports"]}
        for y in rd["supports"]:
            x = by_key[(y["field"], y["ref"])]
            if x["situation"] != y["situation"]:
                changes.append(
                    {
                        "id": rd["id"],
                        "ref": y["ref"],
                        "field": y["field"],
                        "before": _without_key(x),
                        "after": _without_key(y),
                        "explanation": _explanation(x, y),
                    }
                )
    common = [t for t in a["warnings"] if t in d["warnings"]]
    warnings = common + [f"before: {t}" for t in a["warnings"] if t not in common]
    warnings += [f"after: {t}" for t in d["warnings"] if t not in common]
    return {
        "before": a["cuts"],
        "after": d["cuts"],
        "changes": changes,
        "records": records,
        "records_examined": d["records_examined"],
        "missing": d["missing"],
        "legacy": d["legacy"],
        "warnings": warnings,
    }
