"""Approval package: what the person sees before approving a proposal.

Read only. For a base, a proposal and an `operation_id` it returns, per touched record, what changes in the header and
in each clause (and, if it `amends` another, the text in force now next to the new one), the requested effects,
whether it is decisive and why, its supports and whether they are in force at the requested cut, and its digest; also
the impact on other records, what the package does not evaluate and the skeleton of the declared approval.

The digests come from the same code as the gate (`integrate.prepare_request`): the same normalization of effects and
imports. If the gate were to block the proposal for something that does not depend on the approval, the package is
blocked first with the same code and reason (`integrate.final_tree` runs the checks of the final tree). The skeleton
carries the base shown and the digests; the identity, the session, the instant and the quote are empty: whoever
collects the approval provides them, and the generator never writes nor assumes them.
"""

import json
import re
import unicodedata

from .declared import FIELDS as DECLARED_FIELDS
from .declared import MECHANISM as DECLARED_MECHANISM
from .digest import EXCLUDED, SUPERIORS
from .impact import impact
from .integrate import Lock, final_tree, prepare_request, the_approvable, vocabulary_warning
from .markdown import MarkupError, clauses
from .support import support
from .timeutil import is_instant

# What is not approved content: the history, the projections and the evaluations. The state is shown as a requested
# effect, not as a field.
NOISE = (EXCLUDED - set(SUPERIORS)) | {"id"}
PERSONAL = ("identity", "session", "instant", "quote")
NOT_EVALUATED = [
    "authority: who may approve and whether the approval meets the rule of its role (the integration checks it)",
    "authenticity of whoever approves: a declared approval is never authenticated",
    "semantic backing of the supports and of the citations",
    "undeclared supports",
    "supports with the effects of this operation: they are evaluated on the proposal, before integrating",
    "that the canonical branch is still at the base when integrating",
]
_CLIP = 160


def approval_package(repo, *, folder, operation_id, base, proposal, valid_at, known_until=None):
    """Approval package of a proposal, or the gate's `blocked` with its code.

    Returns {state, operation_id, base, proposal, cuts, records, impact, vocabulary, warnings, not_evaluated,
    approvals}. `state` is `completed`; `records` may be empty if the proposal touches none. `vocabulary` holds the
    term and scope findings the gate would warn about in the receipt.
    """
    for name, value in (("valid_at", valid_at), ("known_until", known_until)):
        if (value is not None or name == "valid_at") and not is_instant(value):
            reason = f"{name} is not an ISO 8601 instant with a time zone"
            return {"operation_id": operation_id, "state": "blocked", "code": "AMBIGUOUS_TIME", "reason": reason}
    try:
        p = prepare_request(repo, folder=folder, operation_id=operation_id, base=base, proposal=proposal)
        final, warnings, vocabulary = final_tree(p) if p.touched else (None, [], [])
    except Lock as b:
        return {"operation_id": operation_id, **b.result}
    supports = support(p.prop_snap, valid_at=valid_at, known_until=known_until, ids=p.touched)
    by_id = {r["id"]: r for r in supports["records"]}
    digests = p.digests()
    records = [_record(p, i, digests[i], by_id[i]) for i in p.touched]
    debt = impact(p.base_snap, final) if final is not None else {"changed": [], "affected": [], "warnings": []}
    warnings = warnings + supports["warnings"] + debt.pop("warnings")
    skeleton = {k: None for k in DECLARED_FIELDS}
    skeleton.update(mechanism=DECLARED_MECHANISM, base_shown=base, digests=digests)
    return {
        "state": "completed",
        "operation_id": operation_id,
        "base": base,
        "proposal": proposal,
        "cuts": {"valid_at": valid_at, "known_until": known_until},
        "records": records,
        "impact": {"changed": debt["changed"], "affected": debt["affected"]},
        "vocabulary": vocabulary,
        "warnings": warnings,
        "not_evaluated": list(NOT_EVALUATED),
        "approvals": [skeleton],
    }


def _record(p, ident, digest, supports):
    r, c = p.prop_snap.records[ident], p.prop_snap.bodies[ident]
    before, body_before = p.base_snap.records.get(ident), p.base_snap.bodies.get(ident)
    effects, import_ = the_approvable(ident, p.effects, p.imports)
    if import_ is not None:
        import_ = {**import_, "legacy_state": p.imports[ident]["legacy_state"]}
    if ident in p.imports:
        change = "imported"
    elif ident in p.mut["new"]:
        change = "new"
    elif ident in p.mut["modified"]:
        change = "modified"
    else:
        change = "effects_only"
    reasons = p.decisive_reasons(ident)
    output = {
        "id": ident,
        "type": r.get("type"),
        "title": r.get("title"),
        "path": p.prop_snap.paths[ident],
        "change": change,
        "header": _header(before, r),
        "clauses": _clauses(body_before, c),
        "body_changed": (body_before or "") != (c or ""),
        "outside_clauses": _outside_clauses(body_before, c),
        "unreadable_body": _anchors(c) is None,
        "amends": _amends(p, r),
        "effects": effects,
        "import": import_,
        "decisive": bool(reasons),
        "decisive_reasons": reasons,
        "supports": supports["supports"],
        "support": supports["support"],
        "digest": digest,
    }
    if "body" in supports:
        output["body_alert"] = supports["body"]
    return output


def _empty(value):
    return value is None or value == [] or value == {} or value == ""


def _header(before, after):
    """[{field, before, after}] of the fields that change, in the order of the proposal and without noise."""
    before = before or {}
    fields = [k for k in after if k not in NOISE] + [k for k in before if k not in NOISE and k not in after]
    return [
        {"field": k, "before": before.get(k), "after": after.get(k)}
        for k in fields
        if before.get(k) != after.get(k) and not (_empty(before.get(k)) and _empty(after.get(k)))
    ]


def _anchors(body):
    try:
        return clauses(body or "")
    except MarkupError:
        return None


_BLOCK = re.compile(r"<clause\b[^>]*>.*?</clause>", re.DOTALL)


def _outside_clauses(body_before, body_after):
    """{before, after} of the body text that is in no clause, if it changes; None if it does not change.

    The digest covers the whole body: what lies outside the clauses is approved too and has to be seen. It is obtained
    by removing the clause blocks as written; when in doubt it leaves too much text, not too little.
    """
    before, after = (" ".join(_BLOCK.sub("", c or "").split()) for c in (body_before, body_after))
    return {"before": before or None, "after": after or None} if before != after else None


def _clauses(body_before, body_after):
    """[{anchor, change, before?, after?}]: new, changed and removed clauses."""
    a, d = _anchors(body_before) or {}, _anchors(body_after) or {}
    changes = []
    for anchor, text in d.items():
        if anchor not in a:
            changes.append({"anchor": anchor, "change": "new", "after": text})
        elif a[anchor] != text:
            changes.append({"anchor": anchor, "change": "changed", "before": a[anchor], "after": text})
    changes += [{"anchor": k, "change": "removed", "before": v} for k, v in a.items() if k not in d]
    return changes


def _text_of(snapshot, reference):
    """Text of the clause `ID#anchor` in a snapshot, or None if it is not there."""
    if not isinstance(reference, str):
        return None
    ident, _, anchor = reference.partition("#")
    anchors = _anchors(snapshot.bodies.get(ident)) if ident in snapshot.bodies else None
    return (anchors or {}).get(anchor)


def _amends(p, record):
    """Each `amends` item, with the text in force now in the base and the one it proposes in its place."""
    output = []
    for mod in record.get("amends") or []:
        if not isinstance(mod, dict):
            continue
        output.append(
            {
                "target": mod.get("target"),
                "operation": mod.get("operation"),
                "by": mod.get("by"),
                "current_text": _text_of(p.base_snap, mod.get("target")),
                "new_text": _text_of(p.prop_snap, mod.get("by")),
            }
        )
    return output


def _line(text):
    """One line for the terminal: without line breaks nor control or format characters, which could hide text."""
    # Line breaks and tabs fold into a space; the other control and format characters (bidirectional marks included)
    # are replaced, so that nothing of what is approved stays hidden in the terminal.
    visible = "".join(
        " " if c in "\n\r\t" else "\ufffd" if unicodedata.category(c) in ("Cc", "Cf") else c for c in str(text)
    )
    return " ".join(visible.split())


def _value(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = _line(text)
    if len(text) <= _CLIP:
        return text
    return f"{text[:_CLIP]}… (+{len(text) - _CLIP} characters, in full in the JSON output)"


def present(package):
    """Short text for the person who approves: what changes, effects, evidence, impact, what is decisive, what was not
    evaluated and the digests. No YAML nor full diff; the clause texts, in full."""
    if package["state"] == "blocked":
        return f"Approval package of {package['operation_id']}: blocked ({package['code']}): {package['reason']}"
    lines = [
        f"Approval package of {package['operation_id']}: base {package['base'][:12]}, "
        f"proposal {package['proposal'][:12]}, supports at {package['cuts']['valid_at']}."
    ]
    if not package["records"]:
        lines.append("The proposal changes no record: there is nothing to approve.")
    for r in package["records"]:
        lines.append(f"{r['id']} ({r['type']}, {r['change'].replace('_', ' ')}): {_line(r['title'] or '')}")
        if r["change"] in ("new", "imported"):
            # A new record has no "before": its header, field by field, without what the heading already says.
            lines += [
                f"  {c['field']}: {_value(c['after'])}" for c in r["header"] if c["field"] not in ("type", "title")
            ]
        else:
            lines += [f"  {c['field']}: {_value(c['before'])} → {_value(c['after'])}" for c in r["header"]]
        for c in r["clauses"]:
            if c["change"] == "new":
                lines.append(f"  Clause {c['anchor']} new: «{_line(c['after'])}»")
            elif c["change"] == "changed":
                lines.append(f"  Clause {c['anchor']} changed: «{_line(c['before'])}» → «{_line(c['after'])}»")
            else:
                lines.append(f"  Clause {c['anchor']} removed: «{_line(c['before'])}»")
        outside = r["outside_clauses"]
        if outside:
            before = f"«{_line(outside['before'])}» → " if outside["before"] else ""
            after = f"«{_line(outside['after'])}»" if outside["after"] else "(removed)"
            lines.append(f"  Text outside the clauses: {before}{after}")
        if r["unreadable_body"]:
            lines.append("  WARNING: the body markup could not be read; its clauses are not shown.")
        for m in r["amends"]:
            current = f"«{_line(m['current_text'])}»" if m["current_text"] is not None else "(no text in the base)"
            new = f" → «{_line(m['new_text'])}»" if m["new_text"] is not None else ""
            lines.append(f"  Amends {m['target']} ({m['operation']}): now {current}{new}")
        for ef in r["effects"]:
            until = f" until {ef['valid_until']}" if "valid_until" in ef else ""
            lines.append(f"  Effect: {ef['previous_state']} → {ef['new_state']} from {ef['valid_from']}{until}")
        if r["import"]:
            imp = r["import"]
            lines.append(
                f"  Import: {imp['legacy_state']} → {imp['state']} from {imp['valid_from']} "
                f"({imp['precision']}); inherited authority: {_value(imp['inherited_authority'])}"
            )
        if r["decisive"]:
            lines.append(f"  Decisive: {'; '.join(r['decisive_reasons'])}")
        else:
            lines.append("  Not decisive.")
        if r["supports"]:
            lines.append(f"  Supports ({r['support']}):")
            lines += [f"  - {a['ref']} ({a['field']}): {a['situation']}, {_line(a['reason'])}" for a in r["supports"]]
        else:
            lines.append("  No declared supports.")
        lines.append(f"  Digest: {r['digest']}")
    affected = package["impact"]["affected"]
    if affected:
        lines.append("Impact on other records:")
        lines += [f"- {a['affected']} ({a['type']}): {a['cause']}, through {' → '.join(a['path'])}" for a in affected]
    elif package["records"]:
        lines.append("Impact: no other record declares it depends on what changes.")
    if package["vocabulary"]:
        lines.append("Domain vocabulary:")
        lines += [f"- {_line(vocabulary_warning(h))}" for h in package["vocabulary"]]
    lines += [f"Warning: {a}" for a in package["warnings"]]
    lines.append("Not evaluated: " + "; ".join(package["not_evaluated"]) + ".")
    if package["records"]:
        lines.append(
            f"Declared approval: base shown {package['base']}; the identity, the session, the instant and the quote are "
            "provided by whoever collects the approval."
        )
    return "\n".join(lines)
