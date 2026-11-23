"""context (KB-DPP implementation 1.0, "Context package for a task"; ESC-06 and ESC-09).

Read only. It gathers for a task what the session needs before acting: the goal; the decisive constraints (the
instructions that the installation declares decisive, the in-force clauses of the canonical decisions of the scope with
their origin and, as decisive uncertainties, the clauses in conflict, ambiguous or without text); apart and marked as
non-binding, the proposals of the scope and the pending items (open questions, also those of the legacy format if
asked); the procedures that the installation declares, and the task handoff, which is what the session declared, not
normative knowledge.

The budget is counted in elements. Decisive constraints are never trimmed: if they do not fit, the package comes out
`partial` with its reason. If loading the records is not complete, the package is not either: it comes out `partial`
or `blocked`, because a decisive constraint may be missing. What is not decisive is trimmed in order (legacy pending,
pending, proposals, procedures, non-decisive instructions) and each omission says why. The package references and does
not copy: instructions go as `path#anchor` with a summary. `refresh_if` says which changes invalidate it. It grants no
authorization: each effect revalidates its authority in the core.
"""

import hashlib
import json
import uuid

from . import handoff as rv
from .consolidate import consolidate
from .events import HistoryError, admitted
from .migration import format_of
from .projection import state_at_cut
from .snapshot import load
from .verify import checks_of

# States in which a record is a proposal (non-binding) and in which a question is still pending.
PROPOSED = {"proposed", "draft"}
OPEN_ONES = {"open"}
# Roles and persons are the installation policy, not task knowledge: they do not enter as proposals.
POLICY = {"role", "person"}
# Clause states that cannot be resolved: the session must know there is a decisive uncertainty there.
UNCERTAIN = {"conflict", "ambiguous", "no_rule", "no_text"}
# Order in which what is not decisive is trimmed: the last in the list is the first to go.
NON_DECISIVE_ORDER = ("instruction", "procedure", "proposal", "pending", "legacy_pending")
TEXT_WARNINGS = 5


def _now():
    return rv._now()


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _state(record, known_until):
    """State used to classify what is non-binding: that of the admitted history or, without history, the declared one
    (in proposal mode it can only be the initial one of the type)."""
    if not admitted(record.get("events") or []):
        return record.get("state")
    try:
        return state_at_cut(record, known_until)
    except HistoryError:
        return None


def validate_installation(installation):
    """The installation configuration that the package uses; ValueError if it does not have the expected shape."""
    if not isinstance(installation, dict):
        raise ValueError("the installation configuration is an object")
    for i in installation.get("instructions", []):
        if not isinstance(i, dict) or not isinstance(i.get("ref"), str) or not isinstance(i.get("summary"), str):
            raise ValueError("each instruction has ref and summary")
        if not isinstance(i.get("decisive", False), bool):
            raise ValueError("decisive is true or false")
    for p in installation.get("procedures", []):
        if not isinstance(p, dict) or not isinstance(p.get("ref"), str):
            raise ValueError("each procedure has ref")
    checks_of(installation)
    format_of(installation)


def context(
    root,
    *,
    task,
    goal,
    scope,
    folder,
    installation,
    valid_at,
    known_until=None,
    revision=None,
    budget=30,
    legacy=None,
    loaded=None,
):
    """Context package of the task (dict). `installation` is the project configuration already read. `loaded` is the
    `(snapshot, coverage)` of that same folder and revision in proposal mode and with legacy records, if the caller
    already has it: this way two operations on the same records read them once."""
    validate_installation(installation)
    if not isinstance(budget, int) or budget < 0:
        raise ValueError("the budget is a number of elements, 0 or more")
    # Proposal mode: a proposal not yet integrated is named as such, it does not disappear as invalid. What is in
    # force still requires an admitted history (consolidate), so a proposal never passes for an in-force decision.
    format = format_of(installation)
    snapshot, coverage = loaded or load(root, folder, revision, mode="proposal", legacy=True, format=format)
    warnings = list(coverage["warnings"])
    in_scope = {i: r for i, r in snapshot.records.items() if r.get("scope") == scope}

    decisive = [
        {"origin": i["ref"], "text": i["summary"], "decisive": True}
        for i in installation.get("instructions", [])
        if i.get("decisive")
    ]
    # Only decisions with an admitted history can be in force; proposals go apart.
    governing = sorted(i for i, r in in_scope.items() if r["type"] == "decision" and admitted(r.get("events") or []))
    if governing:
        res = consolidate(snapshot, governing, valid_at=valid_at, known_until=known_until)
        warnings += res["warnings"]
        for c in res["clauses"]:
            if c["state"] == "current":
                decisive.append({"origin": c["origin"], "text": c["text"], "decisive": True})
            elif c["state"] in UNCERTAIN:
                text = f"clause {c['state'].replace('_', ' ')}: it is not known what is in force"
                decisive.append({"origin": c["reference"], "text": text, "decisive": True, "uncertain": True})
        for c in res["conflicts"]:
            decisive.append(
                {
                    "origin": c["clause"],
                    "text": "unresolved normative conflict",
                    "decisive": True,
                    "uncertain": True,
                }
            )
        for a in res["warnings"]:
            if a.startswith("NORMATIVE_CONFLICT"):
                decisive.append({"origin": "consolidated", "text": a, "decisive": True, "uncertain": True})

    candidates = [
        {"type": "instruction", "origin": i["ref"], "text": i["summary"], "decisive": False}
        for i in installation.get("instructions", [])
        if not i.get("decisive")
    ]
    candidates += [{**p, "type": "procedure"} for p in installation.get("procedures", [])]
    candidates += [
        {"type": "proposal", "id": i, "title": r.get("title"), "binding": False}
        for i, r in sorted(in_scope.items())
        if r["type"] not in POLICY and _state(r, known_until) in PROPOSED
    ]
    candidates += [
        {"type": "pending", "id": i, "title": r.get("title"), "binding": False, "format": "profile"}
        for i, r in sorted(in_scope.items())
        if r["type"] == "question" and _state(r, known_until) in OPEN_ONES
    ]
    if legacy:
        legacy_snap, cob_h = load(root, legacy, revision, legacy=True, format=format)
        if cob_h["state"] != "complete":
            warnings.append(f"reading of the legacy format {cob_h['state']}")
        candidates += [
            {"type": "legacy_pending", "id": i, "binding": False, "format": "legacy"}
            for i, f in sorted(legacy_snap.legacy.items())
            if f["type"] == "question" and f["proposed_state"] == "open"
        ]

    state, reasons = "completed", []
    if coverage["state"] != "complete":
        # A record that could not be read could carry a decisive constraint: the package is not taken as complete.
        state = "blocked" if coverage["state"] == "blocked" else "partial"
        reasons.append(f"loading the records is {coverage['state']}: a decisive constraint may be missing")
    if not in_scope:
        state = "partial" if state == "completed" else state
        reasons.append(f"no record in the scope {scope!r}: is it spelled right?")
    if len(decisive) > budget:
        state = "partial" if state == "completed" else state
        reasons.append(
            f"the decisive constraints ({len(decisive)}) do not fit in the budget ({budget}): they are not trimmed"
        )
    free_slots = max(budget - len(decisive), 0)
    candidates.sort(key=lambda c: NON_DECISIVE_ORDER.index(c["type"]))
    included, omitted = candidates[:free_slots], candidates[free_slots:]

    rel = rv.handoff(root, task, canonical_branch=installation.get("canonical_branch", "main"))
    git = rel["git"]
    package = {
        "package_id": str(uuid.uuid4()),
        "task": task,
        "revision": snapshot.revision,
        "prepared_at": _now(),
        "scope": {"scope": scope, "folder": folder, "project": installation.get("project")},
        "cuts": {"valid_at": valid_at, "known_until": known_until},
        "state": state,
        "reason": "; ".join(reasons) or None,
        "goal": goal or rel["goal"],
        "constraints": decisive + [c for c in included if c["type"] == "instruction"],
        "proposals": [c for c in included if c["type"] == "proposal"],
        "pending": [c for c in included if c["type"] in ("pending", "legacy_pending")],
        "procedures": [c for c in included if c["type"] == "procedure"],
        "handoff": rel,
        "omitted": [
            {"type": c["type"], "id": c.get("id") or c.get("origin") or c.get("ref"), "reason": "budget exhausted"}
            for c in omitted
        ],
        "budget": {"amount": budget, "unit": "elements", "used": len(decisive) + len(included)},
        "coverage": {
            "state": coverage["state"],
            "read": coverage["read"],
            "invalid": coverage["invalid"],
            "not_evaluated": ["authenticity of the approvals", "integrity of the sources"],
        },
        "refresh_if": [
            {"datum": "revision", "value": snapshot.revision},
            {"datum": "head", "value": git.get("head"), "dirty": bool(git.get("local_changes"))},
            {"datum": "handoff", "value": rel.get("updated_at")},
            {
                "datum": "records",
                "value": {i: _fingerprint([r, snapshot.bodies.get(i)]) for i, r in sorted(in_scope.items())},
            },
            {"datum": "installation", "value": _fingerprint(installation)},
            {"datum": "cuts", "value": {"valid_at": valid_at, "known_until": known_until}},
        ],
        "warnings": warnings,
    }
    return package


def _open_checks(rel):
    return [v for v in rel["checks"] if v.get("result") != "passed" or v.get("outdated") is not False]


def _with_title(element, limit=140):
    """ "- ID: title", with the title on one line and clipped: without it, the session only sees an identifier."""
    title = " ".join(str(element.get("title") or "").split())
    if len(title) > limit:
        title = title[: limit - 1] + "…"
    return f"- {element['id']}: {title}" if title else f"- {element['id']}"


def present(package):
    """Short text to inject into a session: what is decisive first; what is non-binding and what the session declared,
    marked as such; the stop conditions always."""
    lines = [f"KBOL context for task {package['task']} (revision {str(package['revision'])[:12]})."]
    if package["state"] != "completed":
        lines.append(f"Package {package['state']}: {package['reason']}")
    if package.get("goal"):
        lines.append(f"Goal: {package['goal']}")
    if package["constraints"]:
        lines.append("Constraints:")
        lines += [
            f"- {r['text']} ({r['origin']}{'' if r['decisive'] else ', guidance'})" for r in package["constraints"]
        ]
    if package["proposals"]:
        lines.append("Proposals (non-binding, they authorize nothing):")
        lines += [_with_title(p) for p in package["proposals"]]
    if package["pending"]:
        lines.append("Pending:")
        lines += [_with_title(p) for p in package["pending"]]
    if package["procedures"]:
        lines += [f"Procedure: {p['ref']} ({p.get('when', '')})" for p in package["procedures"]]
    rel = package["handoff"]
    if rel["state"] == "saved":
        lines.append(
            f"Task handoff (declared by the session on {rel['updated_at']}; it is not normative and authorizes "
            f"nothing); delivery state: {rel['delivery_state']}."
        )
        aut = rel["authorization"] or {}
        if aut.get("reference"):
            lines.append(f"  Declared authorization: {aut['reference']} (not verified)")
        if aut.get("limits"):
            lines.append("  Declared limits: " + "; ".join(aut["limits"]))
        for b in rel["blocks"]:
            lines.append(f"  Block: {b}")
        for p in rel["questions"]:
            lines.append(f"  Question: {p}")
        for v in _open_checks(rel):
            state = "outdated" if v.get("outdated") is True else v["result"]
            who = (
                "annotated by kbol verify, without receipt" if v.get("origin") == "kbol" else "declared by the session"
            )
            lines.append(f"  Check {state} ({who}): {v['command']}")
        if rel["next_step"]:
            lines.append(f"  Next step: {rel['next_step']['action']}")
        if rel["not_recorded"]:
            lines.append("  Not recorded: " + ", ".join(rel["not_recorded"]))
    if rel["git"].get("local_changes"):
        lines.append(f"Uncommitted local changes: {len(rel['git']['local_changes'])} files.")
    if package["omitted"]:
        lines.append(f"Omitted for budget: {len(package['omitted'])} non-decisive elements.")
    alerts = package["warnings"]
    lines += [f"Warning: {a}" for a in alerts[:TEXT_WARNINGS]]
    if len(alerts) > TEXT_WARNINGS:
        lines.append(f"Warnings omitted from the text: {len(alerts) - TEXT_WARNINGS} (full JSON output).")
    return "\n".join(lines)
