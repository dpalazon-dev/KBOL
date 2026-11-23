"""Lexical search: the "Exploration" of the core (§8), candidates by free text or alias.

It finds records and clauses that share terms with the query and returns them with their identity, their state, their
validity at the cuts and a fragment. It does not decide what is in force: a candidate is a starting point for `query`
or `consolidate`, which are the ones that answer. By default it only returns what is current; proposals and what is
not in force are counted and only shown if asked for, marked.

Everything happens in memory over the snapshot of the query, without vectors or a persistent index. The score is BM25
over normalized terms (lowercase, without accents, six-letter prefix, without stop words), with the title and the
aliases counted twice. It is deterministic: same snapshot and query, same order.

Units: each clause of a decision is one (with the title and description of its decision); every other record is one,
with title, description, aliases (`defines`, `aliases`), claim and body. Legacy records are not examined: the coverage
says so. Each record appears once, through its best unit; the other matching clauses go in `other_anchors`.
"""

import math
import re
import unicodedata

from .consolidate import IN_FORCE, _Query
from .markdown import MarkupError, clauses
from .projection import state_at_cut
from .supersessions import alerts_for, undeclared

CLASSES = ("current", "proposal", "not_in_force")
_PROPOSALS = {"proposed", "draft"}
_NOT_IN_FORCE = {"rejected", "retired", "discarded", "refuted", "cancelled", "closed"}
# English stop words.
_EMPTY_EN = (
    "a an and are as at be by for from has have how in is it its of on or that the this to was what when which who with"
)
# Spanish stop words, deliberately kept: records written before 0.13 and the queries about them may be in Spanish.
_EMPTY_ES = (
    "a al algo como con cual cuales cuando cuanto cuantos cuantas de del donde el ella ellos en entre es esa ese eso "
    "esta este esto estos fue ha hay la las le lo los mas me mi mucho muy no nos o para pero por que quien se sea ser "
    "si sin sobre su sus tambien te tiene un una uno unos y ya hoy dice"
)
_EMPTY = set(_EMPTY_EN.split()) | set(_EMPTY_ES.split())
_K1, _B = 1.2, 0.75
_FRAGMENT = 240


def _flat(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def terms(text):
    """Normalized terms of a text, in order and with repetitions."""
    output = []
    for t in re.findall(r"[a-z0-9]+", _flat(text or "")):
        if len(t) < 2 or t in _EMPTY:
            continue
        output.append(t[:6] if not t.isdigit() else t)
    return output


def _alias(r):
    texts = list(r.get("aliases") or []) + [r.get("name") or ""]
    for d in r.get("defines") or []:
        if isinstance(d, dict):
            texts += [d.get("term") or "", *(d.get("aliases") or [])]
    return " ".join(t for t in texts if isinstance(t, str))


def _units(snapshot, warn):
    """[(id, anchor, weighted_text, visible_text)] of the canonical records."""
    units = []
    for ident, r in sorted(snapshot.records.items()):
        header = f"{r.get('title') or ''} {_alias(r)}"
        rest = f"{r.get('description') or ''}"
        body = snapshot.bodies.get(ident) or ""
        if r.get("type") == "decision":
            try:
                anchors = clauses(body)
            except MarkupError as exc:
                warn(f"{ident}: malformed body ({exc}); its header is searched")
                anchors = {}
            for anchor, text in anchors.items():
                units.append((ident, anchor, f"{header} {header} {rest} {text}", text))
            if anchors:
                continue
        visible = " ".join(str(x) for x in (r.get("claim"), r.get("description"), body) if x)
        units.append((ident, None, f"{header} {header} {rest} {r.get('claim') or ''} {body}", visible))
    return units


def _fragment(visible, query_):
    text = " ".join(visible.split())
    flat = _flat(text)
    pos = [flat.find(t) for t in query_ if flat.find(t) >= 0]
    start = max(0, min(pos) - 60) if pos else 0
    piece = text[start : start + _FRAGMENT]
    return ("…" if start else "") + piece + ("…" if start + _FRAGMENT < len(text) else "")


def _class(query_, snapshot, ident, anchor):
    """(class, state, validity, in_force_now) of a candidate at the cuts."""
    r = snapshot.records[ident]
    state = state_at_cut(r, query_.known_until)
    if r.get("type") == "decision" and anchor:
        sit = query_.situation(ident)
        if sit != IN_FORCE:
            class_ = "proposal" if query_.is_proposal(ident) else "not_in_force"
            return class_, state, sit, None
        res = query_.resolve(f"{ident}#{anchor}")
        if res["state"] == "current" and res.get("origin") == res["reference"]:
            return "current", state, "current", None
        in_force_now = res.get("origin") if res["state"] == "current" else None
        return "not_in_force", state, res["state"] if res["state"] != "current" else "superseded", in_force_now
    if state is None:
        return "not_in_force", state, "not_recorded_then", None
    if state in _PROPOSALS:
        return "proposal", state, "not_in_force", None
    if state in _NOT_IN_FORCE:
        return "not_in_force", state, "not_in_force", None
    return "current", state, "current", None


def search(snapshot, text, *, valid_at, known_until, include=(), limit=10):
    """{query, terms, candidates, excluded, examined, truncated, warnings}."""
    query_ = _Query(snapshot, valid_at, known_until)
    q = list(dict.fromkeys(terms(text)))
    units = _units(snapshot, query_.warn)
    docs = [terms(u[2]) for u in units]
    n = len(docs)
    mean = (sum(len(d) for d in docs) / n) if n else 0
    df = {t: sum(1 for d in docs if t in d) for t in q}
    scored = []
    for unit, d in zip(units, docs):
        if not d:
            continue
        frequencies = {t: d.count(t) for t in q if t in df and df[t]}
        points = 0.0
        for t, f in frequencies.items():
            if not f:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            points += idf * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * len(d) / mean))
        if points > 0:
            scored.append((round(points, 4), unit, sum(1 for f in frequencies.values() if f)))
    scored.sort(key=lambda x: (-x[0], x[1][0], x[1][1] or ""))
    include = set(include) | {"current"}
    hints = undeclared(snapshot)
    candidates, excluded = [], {c: 0 for c in CLASSES if c != "current"}
    total, by_record = 0, {}
    for points, (ident, anchor, _, visible), matching in scored:
        class_, state, validity, in_force_now = _class(query_, snapshot, ident, anchor)
        if class_ not in include:
            excluded[class_] += 1
            continue
        if ident in by_record:  # one candidate per record: the other matching clauses, in `other_anchors`
            by_record[ident].setdefault("other_anchors", []).append(anchor)
            continue
        total += 1
        if len(candidates) >= limit:
            by_record[ident] = {}
            continue
        r = snapshot.records[ident]
        c = {
            "id": ident,
            "anchor": anchor,
            "reference": f"{ident}#{anchor}" if anchor else ident,
            "type": r.get("type"),
            "title": r.get("title"),
            "class": class_,
            "state": state,
            "validity": validity,
            "score": points,
            "matching_terms": matching,
            "fragment": _fragment(visible, q),
            "path": snapshot.paths.get(ident),
        }
        if in_force_now:
            c["in_force_now"] = in_force_now
        alerts = alerts_for(hints, [ident])
        if alerts:
            c["alerts"] = alerts
        candidates.append(c)
        by_record[ident] = c
    warnings = list(query_.warnings)
    if not q:
        warnings.append("the query has no searchable terms (only stop words or symbols)")
    elif not scored:
        warnings.append("no lexical matches: it does not mean the base does not deal with the subject")
    for class_, count in excluded.items():
        if count:
            name = "proposals" if class_ == "proposal" else "records not in force"
            option = "proposals" if class_ == "proposal" else "not_in_force"
            warnings.append(f"{count} matches in {name} not shown: add --include {option}")
    if total > len(candidates):
        warnings.append(f"showing {len(candidates)} of {total} candidates: raise --limit to see more")
    if candidates:
        warnings.append("search finds candidates, it does not decide what is in force: confirm with query or consolidate")
    return {
        "query": text,
        "terms": q,
        "candidates": candidates,
        "excluded": excluded,
        "examined": n,
        "truncated": total > len(candidates),
        "warnings": warnings,
    }
