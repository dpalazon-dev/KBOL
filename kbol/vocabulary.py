"""Domain vocabulary: the terms declared by the decisions in force, and who uses them.

A decision declares terms with the `defines` relation: each entry names a clause of that decision, the term, its
class, its description and, if it has them, its aliases. A term is in force at some cuts when that clause is in force
at them with the text of that decision (C1): not replaced, repealed or left without a rule. In this increment the only
class is the entity class (C3).

- Closed world (C2). Once a term is in force, or may be in force because its validity cannot be decided, the class is
  a closed world for the whole installation, whatever the scope of the decision that defines it, and it stays so even
  if all of them are later retired. With none, open world: nothing is flagged about classes and the coverage says so.
- Undetermined (C5). A term with a definition of ambiguous validity or with its clause in conflict, with two
  different definitions, or that shares a name or alias with another term, is not in force: it is flagged apart.
- Retired. A term whose definition was in force and no longer is (its decision was retired, or its clause was
  replaced, repealed or left without a rule) and that no other definition in force takes up.
- Scopes (C3). They are not vocabulary: the valid ones are the `scopes` of the roles active at the cuts.

Read only. An undeclared term is flagged with its uses: it does not invalidate any record or remove it from a query,
does not grant authority, does not change what is in force and does not satisfy a dependency (C2, C7). The
integration gate is what blocks, and only the step of an entity to `active` (C4).
"""

from .consolidate import AMBIGUOUS, IN_FORCE, RETIRED_F, _Query
from .events import HistoryError, in_force_at, state_history
from .projection import DEPRECATED, state_at_cut

OPEN_WORLD = "undeclared vocabulary: open world"
# Situation of a name used as an entity class.
CURRENT, OPEN, UNDECLARED, UNDETERMINED, RETIRED = (
    "current",
    "open",
    "undeclared",
    "undetermined",
    "retired",
)


def _definition(ident, entry, in_force):
    aliases = entry.get("aliases") if isinstance(entry.get("aliases"), list) else []
    return {
        "term": entry.get("term"),
        "class": entry.get("class"),
        "description": entry.get("description"),
        "aliases": sorted(set(aliases)),
        "decision": ident,
        "clause": entry.get("clause"),
        "reference": f"{ident}#{entry.get('clause')}",
        "in_force": in_force,
    }


def _content(d):
    return d["class"], d["description"], tuple(d["aliases"])


def _definitions(query_):
    """(in_force, doubtful, past): the `defines` entries according to whether their clause is in force with the text of their decision."""
    in_force_defs, doubtful, past = [], [], []
    for ident in sorted(query_.regs):
        entries = [e for e in query_.regs[ident].get("defines") or [] if isinstance(e, dict)]
        if not entries:
            continue
        situation = query_.situation(ident)
        for e in entries:
            reference = f"{ident}#{e.get('clause')}"
            if situation == AMBIGUOUS:
                doubtful.append(_definition(ident, e, False))
            elif situation == RETIRED_F:
                past.append(_definition(ident, e, False))
            elif situation == IN_FORCE:
                res = query_.resolve(reference)
                if res["state"] in ("ambiguous", "conflict"):
                    doubtful.append(_definition(ident, e, False))
                elif res["state"] == "current" and res.get("origin") == reference:
                    in_force_defs.append(_definition(ident, e, True))
                elif res["state"] in ("current", "repealed", "no_rule"):
                    past.append(_definition(ident, e, False))
    return in_force_defs, doubtful, past


def _active_role(role, valid_at, known_until):
    """True if the last step of the role at the knowledge cut is `active` and its validity covers `valid_at`."""
    chain = state_history(role.get("events") or [], known_until, "role")
    if not chain or chain[-1][1]["new_state"] != "active":
        return False
    step = chain[-1][1]
    return in_force_at(step.get("valid_from"), step.get("valid_until"), valid_at)


def _scopes(query_):
    scopes = set()
    for ident, r in sorted(query_.snap.records.items()):
        if r.get("type") != "role":
            continue
        try:
            active = _active_role(r, query_.valid_at, query_.known_until)
        except HistoryError as exc:
            query_.warn(f"{exc.code}: {ident}: cannot decide whether the role is active ({exc})")
            continue
        if active:
            scopes.update(a for a in r.get("scopes") or [] if isinstance(a, str))
    return sorted(scopes)


def in_force_vocabulary(snapshot, *, valid_at, known_until):
    """Domain vocabulary at the two cuts.

    Returns {cuts, classes, aliases, undetermined, retired, scopes, declared, warnings}: `classes` is
    {term: {decision, clause, description, aliases}} with the entity class terms in force; `aliases`,
    {alias: term}; `undetermined`, [{term, reason, definitions, aliases}] (C5); `retired`, [{term, definitions,
    aliases}]; `scopes`, those of the roles active at the cuts (C3); `declared`, whether the class is a closed world
    (C2): some term is, may be or was in force. `definitions` are the `ID#anchor` clauses that define them.
    """
    query_ = _Query(snapshot, valid_at, known_until)
    if known_until is None:
        query_.warn("no knowledge cut: the whole admitted history of the revision is used")
    in_force_defs, doubtful, past = _definitions(query_)
    by_term, names = {}, {}
    for d in in_force_defs + doubtful:
        by_term.setdefault(d["term"], []).append(d)
        for name in (d["term"], *d["aliases"]):
            names.setdefault(name, set()).add(d["term"])
    classes, undetermined = {}, []
    for term in sorted(by_term):
        defs = by_term[term]
        certain = [d for d in defs if d["in_force"]]
        clashes = sorted({n for d in defs for n in (d["term"], *d["aliases"]) if len(names[n]) > 1})
        if not certain:
            reason = "its validity cannot be decided"
        elif len({_content(d) for d in defs}) > 1:
            reason = "it has two different definitions that are or may be in force"
        elif clashes:
            reason = f"it shares a name with another term: {', '.join(clashes)}"
        else:
            d = certain[0]
            classes[term] = {k: d[k] for k in ("decision", "clause", "description", "aliases")}
            continue
        undetermined.append(
            {
                "term": term,
                "reason": reason,
                "definitions": sorted({d["reference"] for d in defs}),
                "aliases": sorted({a for d in defs for a in d["aliases"]}),
            }
        )
    retired = {}
    for d in past:
        if d["term"] in names:
            continue  # another definition in force or doubtful takes it up, perhaps as an alias of a renamed term
        r = retired.setdefault(d["term"], {"term": d["term"], "definitions": [], "aliases": []})
        r["definitions"] = sorted({*r["definitions"], d["reference"]})
        r["aliases"] = sorted({*r["aliases"], *(a for a in d["aliases"] if a not in names)})
    return {
        "cuts": {"valid_at": valid_at, "known_until": known_until, "revision": snapshot.revision},
        "classes": classes,
        "aliases": {a: t for t, c in classes.items() for a in c["aliases"]},
        "undetermined": undetermined,
        "retired": [retired[t] for t in sorted(retired)],
        "scopes": _scopes(query_),
        "declared": bool(in_force_defs or doubtful or past),
        "warnings": query_.warnings,
    }


def situation(vocabulary, name):
    """(situation, term) of `name` as an entity class in `vocabulary` (the one from `in_force_vocabulary`).

    `current` if it is in force, directly or through an alias; `open` if no vocabulary is declared; otherwise,
    `undetermined`, `retired` or `undeclared`.
    """
    if not vocabulary["declared"]:
        return OPEN, name
    term = vocabulary["aliases"].get(name, name)
    if term in vocabulary["classes"]:
        return CURRENT, term
    for key, value in (("undetermined", UNDETERMINED), ("retired", RETIRED)):
        for t in vocabulary[key]:
            if name == t["term"] or name in t["aliases"]:
                return value, t["term"]
    return UNDECLARED, name


def recorded(snapshot, *, known_until):
    """(records recorded at the cut and not closed by retirement, rejection or cancellation, warnings)."""
    records, warnings = [], []
    for ident in sorted(snapshot.records):
        r = snapshot.records[ident]
        try:
            state = state_at_cut(r, known_until)
        except HistoryError as exc:
            warnings.append(f"{exc.code}: {ident}: incoherent history, not reviewed ({exc})")
            continue
        if state is not None and state not in DEPRECATED:
            records.append((ident, r))
    return records, warnings


def review(snapshot, vocabulary, *, known_until):
    """Uses of the vocabulary in the base: it flags, never invalidates (C2).

    Reviews the records recorded at the knowledge cut that are not retired, rejected or cancelled.
    Returns {undeclared, undetermined, retired_in_use, scopes_without_role, records_examined, coverage, warnings}:
    `undeclared` and `retired_in_use` are [{term, uses}] with the IDs of the entities that use them; `undetermined`,
    each undetermined term with its reason, its definitions and its uses, even if it has none; `scopes_without_role`,
    [{scope, uses}] of the records whose scope no active role covers (C3). In an open world it says nothing about
    classes and `coverage` declares it.
    """
    records, warnings = recorded(snapshot, known_until=known_until)
    valid = set(vocabulary["scopes"])
    by_situation = {UNDECLARED: {}, UNDETERMINED: {}, RETIRED: {}}
    scopes = {}
    for ident, r in records:
        scope = r.get("scope")
        if isinstance(scope, str) and scope not in valid:
            scopes.setdefault(scope, []).append(ident)
        if r.get("type") == "entity":
            value, term = situation(vocabulary, r.get("entity_class"))
            if value in by_situation:
                by_situation[value].setdefault(term, []).append(ident)
    used = by_situation[UNDETERMINED]
    return {
        "undeclared": [{"term": t, "uses": u} for t, u in sorted(by_situation[UNDECLARED].items())],
        "undetermined": [{**t, "uses": used.get(t["term"], [])} for t in vocabulary["undetermined"]],
        "retired_in_use": [{"term": t, "uses": u} for t, u in sorted(by_situation[RETIRED].items())],
        "scopes_without_role": [{"scope": a, "uses": u} for a, u in sorted(scopes.items())],
        "records_examined": len(records),
        "coverage": [] if vocabulary["declared"] else [OPEN_WORLD],
        "warnings": warnings,
    }
