"""Consolidated clauses for two time cuts (core 1.0, "Amendment by clauses" and "Two times").

It only reads the snapshot. An amendment is in force when its decision is accepted at the knowledge cut and its
validity covers `valid_at`. Each applicable clause travels with its origin and its chain of replacements; proposals
are returned apart as non-binding. Two amendments in force of the same clause without declared succession are a
conflict and are not ordered by date. Retiring an amending decision does not revive the previous text.

Succession between two amendments of the same clause is declared with `depends_on` towards the earlier one. A mutual
succession, or a `supersedes` cycle, decides nothing: the result is a conflict or an ambiguous validity.
"""

from .events import HistoryError, admitted, in_force_at, state_history
from .markdown import MarkupError, clauses
from .supersessions import alerts_for, undeclared
from .timeutil import comparable, instant

IN_FORCE, FUTURE, RETIRED_F, NOT_RECORDED_THEN, NOT_EFFECTIVE, AMBIGUOUS, NO_HISTORY = (
    "in_force",
    "future",
    "retired",
    "not_recorded_then",
    "not_effective",
    "ambiguous",
    "no_history",
)


class _Query:
    def __init__(self, snapshot, valid_at, known_until):
        self.snap = snapshot
        self.valid_at = valid_at
        self.known_until = known_until
        self.regs = {k: r for k, r in snapshot.records.items() if r.get("type") == "decision"}
        self.warnings = []
        self.proposals, self.future, self.conflicts = [], [], []
        self._situation, self._anchors, self._state = {}, {}, {}
        self.by_target = {}
        for ident, r in self.regs.items():
            for mod in r.get("amends") or []:
                if isinstance(mod, dict) and isinstance(mod.get("target"), str):
                    self.by_target.setdefault(mod["target"], []).append((ident, mod))
        self._in_cycle = self._succession_cycles()

    def _succession_cycles(self):
        """Decisions in a `supersedes` cycle (forbidden, VAL-07): their validity is not decided."""
        succeeds = {i: [d for d in r.get("supersedes") or [] if d in self.regs] for i, r in self.regs.items()}
        in_cycle, color = set(), {}

        def visit(node, way):
            color[node] = 1
            for nxt in succeeds[node]:
                if color.get(nxt) == 1:
                    in_cycle.update(way[way.index(nxt) :])
                elif color.get(nxt) is None:
                    visit(nxt, way + [nxt])
            color[node] = 2

        for node in sorted(succeeds):
            if node not in color:
                visit(node, [node])
        return in_cycle

    def warn(self, text):
        if text not in self.warnings:
            self.warnings.append(text)

    def anchors(self, ident):
        if ident not in self._anchors:
            body = self.snap.bodies.get(ident)
            try:
                self._anchors[ident] = clauses(body) if body is not None else None
            except MarkupError as exc:
                self.warn(f"{ident}: malformed body ({exc})")
                self._anchors[ident] = None
        return self._anchors[ident]

    def situation(self, ident):
        """Situation of a decision at the cuts, computed once per query and independently of the order."""
        if ident not in self._situation:
            if ident in self._in_cycle:
                self.warn(f"NORMATIVE_CONFLICT: {ident} is in a supersedes cycle; its validity is not decided")
                self._situation[ident] = AMBIGUOUS
            else:
                self._situation[ident] = self._compute(ident)
        return self._situation[ident]

    def _compute(self, ident):
        r = self.regs[ident]
        if not admitted(r.get("events") or []):
            self.warn(f"{ident}: no admitted history; not considered")
            return NO_HISTORY
        try:
            chain = state_history(r["events"], self.known_until, "decision")
        except HistoryError as exc:
            self.warn(f"{exc.code}: {ident}: inconsistent history ({exc})")
            return AMBIGUOUS
        if not chain:
            return NOT_RECORDED_THEN
        recorded, last = chain[-1]
        self._state[ident] = last["new_state"]
        if last["new_state"] != "accepted":
            return NOT_EFFECTIVE
        since, until = last.get("valid_from"), last.get("valid_until")
        succeeded = self._succeeded(ident)
        if succeeded is None:
            return AMBIGUOUS
        if succeeded:
            return RETIRED_F
        try:
            covers = in_force_at(since, until, self.valid_at)
        except HistoryError as exc:
            self.warn(f"{exc.code}: {ident}: {exc}")
            return AMBIGUOUS
        if covers:
            if comparable(since) < recorded:
                self.warn(f"{ident}: added on {last['recorded_at']} with retroactive effect from {since}")
            return IN_FORCE
        if until is not None and instant(until) <= instant(self.valid_at):
            return RETIRED_F
        self._annotate(self.future, {"decision": ident, "valid_from": since})
        return FUTURE

    def _succeeded(self, ident):
        """True if a full successor (`supersedes`) already came into force; None if it cannot be decided.

        Having come into force is enough: being replaced, repealed or expiring afterwards does not revive the decision
        it superseded. Restoring the earlier one requires a new decision that says so.
        """
        ambiguous = False
        for other, r in self.regs.items():
            if other == ident or ident not in (r.get("supersedes") or []):
                continue
            came = self._came_into_force(other)
            if came:
                return True
            ambiguous = ambiguous or came is None
        return None if ambiguous else False

    def _came_into_force(self, ident):
        """True if the decision is accepted at the cut and its validity started at or before `valid_at`; None if
        ambiguous."""
        r = self.regs[ident]
        try:
            chain = state_history(r.get("events") or [], self.known_until, "decision")
        except HistoryError:
            return None
        if not chain or chain[-1][1]["new_state"] != "accepted":
            return False
        try:
            return in_force_at(chain[-1][1].get("valid_from"), None, self.valid_at)
        except HistoryError as exc:
            self.warn(f"{exc.code}: successor {ident}: {exc}")
            return None

    def is_proposal(self, ident):
        """Proposal according to the history at the cut, not according to the current header."""
        self.situation(ident)
        return self._state.get(ident) == "proposed"

    @staticmethod
    def _annotate(list_, element):
        if element not in list_:
            list_.append(element)

    def annotate_proposal(self, ident, mod):
        self._annotate(self.proposals, {"decision": ident, "amendment": mod, "state": "proposed", "binding": False})

    def _succeeds(self, x, y):
        """x declares succession with respect to y through a dependency on y."""
        deps = [d.get("target", "") for d in self.regs[x].get("depends_on") or [] if isinstance(d, dict)]
        return any(d.split("#", 1)[0] == y for d in deps)

    def _ratifications(self, r):
        current = []
        for ev in admitted(r.get("events") or []):
            if self.known_until is not None and instant(ev["recorded_at"]) > instant(self.known_until):
                break
            if ev.get("event_type") == "ratification":
                current.append(ev["approval"]["approval_id"])
            elif ev.get("event_type") == "approval_revocation" and ev.get("approval_id") in current:
                current.remove(ev["approval_id"])
        return current

    def _inherited(self, r):
        """Authority inherited from the previous format, if the record came in by import; None otherwise."""
        for ev in admitted(r.get("events") or []):
            if ev.get("event_type") == "import":
                return ev.get("inherited_authority")
        return None

    def _declared_f(self, r):
        """Ratifications in force through the declared channel: quoted approvals, not authenticated."""
        current = set(self._ratifications(r))
        return sorted(
            ev["approval"]["approval_id"]
            for ev in admitted(r.get("events") or [])
            if ev.get("event_type") == "ratification"
            and ev["approval"]["approval_id"] in current
            and isinstance(ev["approval"].get("proof"), dict)
            and ev["approval"]["proof"].get("authenticated") is False
        )

    def _approvals(self, r):
        """The ratifications in force with who, when, through which channel and in which words, as the record keeps
        them; unchecked. What the proof does not carry stays None; it is not inferred."""
        current = set(self._ratifications(r))
        output = []
        for ev in admitted(r.get("events") or []):
            approval = ev.get("approval") if ev.get("event_type") == "ratification" else None
            if not approval or approval["approval_id"] not in current:
                continue
            proof = approval.get("proof")
            detail = proof if isinstance(proof, dict) else {}
            output.append(
                {
                    "approval_id": approval["approval_id"],
                    "actor": approval.get("actor"),
                    "roles": list(approval.get("roles") or []),
                    "approved_at": approval.get("approved_at"),
                    "mechanism": detail.get("mechanism") or (ev.get("event_evidence") or {}).get("mechanism"),
                    "quote": detail.get("quote"),
                    "authenticated": detail.get("authenticated"),
                }
            )
        return output

    def resolve(self, ref, chain=None):
        """Consolidated state of an `ID#anchor` clause, following replacements and repeals."""
        chain = (chain or []) + [ref]
        ident, _, anchor = ref.partition("#")
        base = {"reference": chain[0], "chain": chain}
        if len(chain) != len(set(chain)):
            self.warn(f"NORMATIVE_CONFLICT: replacement cycle in {' → '.join(chain)}")
            return {**base, "state": "conflict"}
        candidates, retired = [], []
        for m, mod in self.by_target.get(ref, []):
            if mod.get("operation") not in ("replaces", "repeals"):
                continue
            sit = self.situation(m)
            if sit == IN_FORCE:
                candidates.append((m, mod))
            elif sit == RETIRED_F:
                retired.append(m)
            elif sit == AMBIGUOUS:
                return {**base, "state": "ambiguous"}
            elif sit == NOT_EFFECTIVE and self.is_proposal(m):
                self.annotate_proposal(m, mod)
        finals = [(m, mod) for m, mod in candidates if not any(o != m and self._succeeds(o, m) for o, _ in candidates)]
        if len(finals) > 1 or (candidates and not finals):
            conflict = {
                "code": "NORMATIVE_CONFLICT",
                "clause": ref,
                "candidates": sorted(mod.get("by") or m for m, mod in candidates),
            }
            self._annotate(self.conflicts, conflict)
            return {**base, "state": "conflict"}
        if finals:
            m, mod = finals[0]
            if mod["operation"] == "repeals":
                return {**base, "state": "repealed", "origin": m}
            return self.resolve(mod["by"], chain)
        if retired:
            self.warn(
                f"{ref}: the amending decision {', '.join(sorted(retired))} is no longer in force and the previous "
                "text does not come back by itself; a decision that says what is in force is needed"
            )
            return {**base, "state": "no_rule"}
        anchors = self.anchors(ident)
        if anchors is None or anchor not in anchors:
            self.warn(f"{ref}: text not available in revision {self.snap.revision}")
            return {**base, "state": "no_text", "origin": ref}
        r = self.regs[ident]
        authority = {
            "decision": ident,
            "authorized_by": list(r.get("authorized_by") or []),
            "ratifications": self._ratifications(r),
            "declared": self._declared_f(r),
            "inherited": self._inherited(r),
            "checked": False,
        }
        return {**base, "state": "current", "text": anchors[anchor], "origin": ref, "authority": authority}

    def additions(self, ident):
        entries = []
        for m, mod in self.by_target.get(ident, []):
            if mod.get("operation") != "adds":
                continue
            sit = self.situation(m)
            extra = {"added_to": ident, "position": mod.get("position")}
            if sit == IN_FORCE:
                entries.append({**self.resolve(mod["by"]), **extra})
            elif sit == AMBIGUOUS:
                entries.append({"reference": mod.get("by"), "chain": [mod.get("by")], "state": "ambiguous", **extra})
            elif sit == NOT_EFFECTIVE and self.is_proposal(m):
                self.annotate_proposal(m, mod)
        return entries


def validity_of(query_, ident):
    """(validity, entries) of a decision: `full`, `partial`, `not_in_force` or `not_recorded_then`, with its clauses.

    The single definition of a decision's validity; consolidation, dependencies and support share it.
    """
    sit = query_.situation(ident)
    if sit != IN_FORCE:
        return ("not_recorded_then" if sit == NOT_RECORDED_THEN else "not_in_force"), []
    own = [query_.resolve(f"{ident}#{a}") for a in query_.anchors(ident) or {}]
    entries = own + query_.additions(ident)
    if not any(e["state"] == "current" for e in entries):
        return "not_in_force", entries
    if any(e["state"] != "current" or e.get("origin") != e["reference"] for e in own):
        return "partial", entries
    return "full", entries


def consolidate(snapshot, ids, *, valid_at, known_until):
    """Clauses in force of the decisions `ids` at `valid_at` with what was known up to `known_until`.

    `known_until=None` uses the whole admitted history of the snapshot; the result declares it in its cuts and in its
    warnings.
    """
    q = _Query(snapshot, valid_at, known_until)
    result = {
        "cuts": {"valid_at": valid_at, "known_until": known_until, "revision": snapshot.revision},
        "clauses": [],
        "validity": {},
        "proposals": q.proposals,
        "future": q.future,
        "conflicts": q.conflicts,
        "missing": [],
        "legacy": [],
        "warnings": q.warnings,
    }
    if known_until is None:
        q.warn("no knowledge cut: the whole admitted history of the revision is used")
    views = {}
    for ref in ids:
        ident, _, anchor = ref.partition("#")
        if ident not in q.regs and ident in snapshot.legacy:
            card = snapshot.legacy[ident]
            result["legacy"].append(card)
            q.warn(f"{ident}: legacy format ({card['legacy_state']}); no admitted history, not in force")
            continue
        if ident not in q.regs or (anchor and anchor not in (q.anchors(ident) or {})):
            result["missing"].append(ref)
            continue
        result["validity"][ident], entries = validity_of(q, ident)
        if anchor:  # with an anchor, only that clause; the validity is still the decision's
            entries = [e for e in entries if e["reference"] == ref]
        for e in entries:
            key = e.get("origin") if e["state"] == "current" else None
            if key and key in views:
                views[key].setdefault("also_by", []).append(e["reference"])
                continue
            if key:
                views[key] = e
            result["clauses"].append(e)
    for alert in alerts_for(undeclared(snapshot), [r.partition("#")[0] for r in ids]):
        q.warn(alert)
    return result
