"""VAL-02 and VAL-07 over a snapshot: resolvable references, target type, anchors and forbidden cycles.

A cycle between context relations (`affects`, `resolved_by`, `based_on`) is legitimate; cycles are forbidden in
succession (`supersedes` and `amends`), derivation (`derived_from`) and executable dependency (`depends_on`).
An anchor whose body was not loaded in the snapshot is not taken as good: it stays as a coverage alert.
"""

from . import model as m
from .markdown import MarkupError, clauses, facts


def _finding(code, origin, field, message, severity="error"):
    return {"code": code, "path": f"{origin}/{field}", "message": message, "severity": severity}


def edges(record, body=None):
    """(field, target) of each reference of the record, in the order of `model.REFERENCES`; only text targets.

    A relation is walked in any record that declares it (the schema watches where it belongs); an own field, only in
    the types that declare it. `<fact ref>` citations are read if the body is given, with the field `body`;
    malformed markup leaves them unread, without error: the schema reports it.
    """
    type_ = record.get("type")
    for field, ref in m.REFERENCES.items():
        if not ref.relation and ref.origin is not None and type_ not in ref.origin:
            continue
        if ref.shape == "body":
            if body is not None:
                try:
                    for h in facts(body):
                        if "ref" in h:
                            yield field, h["ref"]
                except MarkupError:
                    pass
        elif ref.shape == "id":
            if isinstance(record.get(field), str):
                yield field, record[field]
        elif ref.shape == "ids":
            for d in record.get(field) or []:
                if isinstance(d, str):
                    yield field, d
        elif ref.key is not None:
            for v in record.get(field) or []:
                if isinstance(v, dict) and isinstance(v.get(ref.key), str):
                    yield field, v[ref.key]


# Target type of the references that are not list relations; list relations take it from `model.RELATIONS`.
EXPECTED_TARGET = {c: r.target for c, r in m.REFERENCES.items() if c not in m.RELATIONS and r.target}


def validate_snapshot(snapshot):
    regs = snapshot.records
    out = []
    anchors = {}
    for ident, body in snapshot.bodies.items():
        try:
            anchors[ident] = set(clauses(body))
        except MarkupError:
            anchors[ident] = set()
    for origin, r in regs.items():
        for field, target in edges(r, snapshot.bodies.get(origin)):
            ident, _, anchor = target.partition("#")
            if ident not in regs:
                if ident in snapshot.legacy:
                    # During the corpus migration: the target exists, in legacy format. It is not in force nor
                    # satisfies dependencies, but the reference resolves; it alerts, it does not block.
                    reason = f"{ident} is in legacy format: it resolves, but does not serve as a normative target"
                    out.append(_finding("MISSING_REFERENCE", origin, field, reason, "alert"))
                else:
                    reason = f"{ident} does not exist in revision {snapshot.revision}"
                    out.append(_finding("MISSING_REFERENCE", origin, field, reason))
                continue
            actual = regs[ident].get("type")
            rule = m.RELATIONS.get(field, {})
            expected = EXPECTED_TARGET.get(field) or (
                (r.get("type"),) if rule.get("target") == "same" else rule.get("target")
            )
            if expected and actual not in expected:
                out.append(
                    _finding("INVALID_SCHEMA", origin, field, f"{field} does not admit a target of type {actual}")
                )
            if anchor and ident not in snapshot.bodies:
                out.append(
                    _finding(None, origin, field, f"{target}: body not loaded, anchor not checked", "alert")
                )
            elif anchor and anchor not in anchors.get(ident, set()):
                out.append(_finding("MISSING_REFERENCE", origin, field, f"{target}: the clause does not exist"))
    for rel in m.NO_CYCLES:
        out += _cycles(regs, rel)
    return out


def _successors(record, rel):
    for value in record.get(rel) or []:
        target = value.get("target") if isinstance(value, dict) else value
        if isinstance(target, str):
            yield target.split("#", 1)[0]


def _cycles(regs, rel):
    out, color = [], {}

    def visit(node, path):
        color[node] = 1
        for nxt in _successors(regs.get(node, {}), rel):
            if nxt not in regs:
                continue
            if color.get(nxt) == 1:
                cycle = path[path.index(nxt) :] + [nxt]
                out.append(_finding("NORMATIVE_CONFLICT", node, rel, "forbidden cycle: " + " → ".join(cycle)))
            elif color.get(nxt) is None:
                visit(nxt, path + [nxt])
        color[node] = 2

    for node in sorted(regs):
        if color.get(node) is None:
            visit(node, [node])
    return out
