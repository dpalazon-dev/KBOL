"""Plain-language answer for `query`, `consolidate` and `search` (`--plain`).

It says, in short prose, the rule, who approved it and when, and whether it is in force on the query date. IDs and
anchors only appear with `--with-ids`; without them, each record is named by its title. What is approved and what is
proposed, legacy or found by search are told apart by the bracketed label each block starts with, and what is not
recorded is said («no approval is recorded»), not inferred.

It is built from the command envelope and the snapshot that answered it; it queries nothing else. The warnings that
are not translated are counted at the end, with a hint to ask for the JSON output to see them.
"""

from .consolidate import _Query, consolidate
from .supersessions import undeclared

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MAX_TEXT = 600
_MAX_RULES = 4
_NOT_FOUND = (
    "[NOT FOUND] Nothing integrated in the base has {ref}. A draft that has not gone through integration does not "
    "count: `kbol validate --mode canonical` says why."
)


def _date(value):
    if not value:
        return "unknown date"
    text = str(value)
    try:
        y, m, d = int(text[:4]), int(text[5:7]), int(text[8:10])
    except ValueError:
        return text
    return f"{d} {_MONTHS[m - 1]} {y}"


def _short(text):
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= _MAX_TEXT else flat[:_MAX_TEXT].rsplit(" ", 1)[0] + "…"


class _Presenter:
    def __init__(self, snapshot, with_ids):
        self.snap, self.with_ids = snapshot, with_ids

    def name(self, ref):
        """«Title» of the record of `ref` and, if asked for, its ID and anchor."""
        ident = str(ref).partition("#")[0]
        r = self.snap.records.get(ident) or {}
        title = r.get("title") or (self.snap.legacy.get(ident) or {}).get("title")
        if not title:
            return ref if self.with_ids else "a record without a title"
        return f"«{title}» ({ref})" if self.with_ids else f"«{title}»"

    def person(self, actor):
        if not actor:
            return "someone not recorded"
        ident = str(actor).split(":", 1)[-1]
        r = self.snap.records.get(ident)
        if r and r.get("title"):
            return f"{r['title']} ({ident})" if self.with_ids else r["title"]
        return str(actor) if self.with_ids else "a person without a record in the base"

    def approval(self, authority):
        approvals = (authority or {}).get("approvals") or []
        if not approvals:
            inherited = (authority or {}).get("inherited")
            if inherited and inherited.get("text"):
                return f"Approval inherited from the old format: «{inherited['text']}», unchecked."
            return "No approval is recorded."
        sentences = []
        for a in approvals:
            sentence = f"Approved by {self.person(a.get('actor'))} on {_date(a.get('approved_at'))}"
            if a.get("quote"):
                sentence += f", in these words: «{_short(a['quote'])}»"
            if a.get("authenticated") is False:
                sentence += " (declared approval, not authenticated)"
            sentences.append(sentence + ".")
        return " ".join(sentences)

    def label(self, type_, state):
        if type_ == "decision":
            return {
                "accepted": "[APPROVED]",
                "proposed": "[PROPOSAL: not approved, not in force]",
                "rejected": "[REJECTED: not in force]",
            }.get(state, f"[{str(state or 'no state').upper()}]")
        if state in ("proposed", "draft"):
            return f"[PROPOSED {type_.upper()}: not accepted]"
        return f"[{str(type_ or 'record').upper()}, {state or 'no state'}]"

    def supersessions(self, ident):
        sentences = []
        for i in undeclared(self.snap):
            if i["target"] == ident:
                sentences.append(
                    f"Note: {self.name(i['record'])} says it replaces or repeals it, at least in part, without "
                    "declaring it; it may not be in force as shown here."
                )
            elif i["record"] == ident:
                sentences.append(
                    f"Note: it says it replaces or repeals {self.name(i['target'])} without declaring it; what "
                    "that one says may still come out as in force."
                )
        return sentences

    def rules(self, ident, cuts):
        """Lines with what is in force of a decision and what replaces it."""
        res = consolidate(self.snap, [ident], **cuts)
        lines = []
        for c in res["clauses"][:_MAX_RULES]:
            if c["state"] != "current":
                lines.append(f"One part is no longer in force ({c['state'].replace('_', ' ')}).")
                continue
            anchor = f" [{c['origin']}]" if self.with_ids else ""
            if c.get("origin") != c["reference"]:
                lines.append(f"Replaced by {self.name(c['origin'])}: {_short(c.get('text'))}{anchor}")
            else:
                lines.append(f"Says: {_short(c.get('text'))}{anchor}")
        if len(res["clauses"]) > _MAX_RULES:
            lines.append(f"And {len(res['clauses']) - _MAX_RULES} more clauses (ask for the JSON output).")
        return lines

    def validity(self, validity, date, inverse):
        if validity == "full":
            return f"In force in full on {date}."
        if validity == "partial":
            return f"In force in part on {date}."
        reason = ""
        if inverse and inverse.get("superseded_by"):
            reason = ": superseded by " + ", ".join(self.name(i) for i in inverse["superseded_by"])
        elif inverse and inverse.get("amended_by"):
            reason = ": amended by " + ", ".join(self.name(i) for i in inverse["amended_by"])
        return f"Not in force on {date}{reason}."


def _query(p, output, cuts, date):
    blocks = []
    for res in output["result"].get("results", []):
        ref = res["reference"]
        if res["found"] == "missing":
            blocks.append([_NOT_FOUND.format(ref=ref)])
            continue
        if res["found"] == "legacy":
            blocks.append([f"[LEGACY: not in force] {p.name(ref)} is in the old format and does not apply."])
            continue
        if res["found"] == "missing_anchor":
            blocks.append([f"[NOT FOUND] {p.name(res['id'])} does not have the requested clause."])
            continue
        type_, state = res.get("type"), res.get("state")
        lines = [f"{p.label(type_, state)} {p.name(ref)}"]
        if type_ == "decision":
            if res.get("clause"):
                c = res["clause"]
                if c.get("state") == "current" and c.get("origin") == ref:
                    lines.append(f"In force on {date}. Says: {_short(c.get('text'))}")
                elif c.get("state") == "current":
                    lines.append(f"This clause is no longer in force on {date}; {p.name(c['origin'])} replaced it.")
                    lines.append(f"Now says: {_short(c.get('text'))}")
                else:
                    lines.append(f"This clause is not in force on {date} ({str(c.get('state')).replace('_', ' ')}).")
            else:
                lines.append(p.validity(res.get("validity"), date, res.get("inverse_relations")))
                if res.get("validity") in ("full", "partial"):
                    lines += p.rules(res["id"], cuts)
        else:
            r = p.snap.records.get(res["id"]) or {}
            if r.get("claim"):
                lines.append(f"Claims: {_short(r['claim'])}")
            elif res.get("text"):
                lines.append(f"Says: {_short(res['text'])}")
            elif r.get("description") and r["description"] != r.get("title"):
                lines.append(_short(r["description"]))
        lines.append(p.approval(res.get("authority")))
        evidence = res.get("evidence")
        if evidence and not evidence.get("sufficient"):
            lines.append("Its evidence is not enough: one of its sources is missing or not in force.")
        lines += p.supersessions(res["id"])
        blocks.append(lines)
    return blocks


def _consolidate(p, output, cuts, date):
    result = output["result"]
    blocks = []
    for ident, validity in result.get("validity", {}).items():
        r = p.snap.records.get(ident) or {}
        lines = [f"{p.label('decision', r.get('state'))} {p.name(ident)}", p.validity(validity, date, None)]
        lines += p.rules(ident, cuts)
        lines += p.supersessions(ident)
        blocks.append(lines)
    for prop in result.get("proposals", []):
        blocks.append([f"[PROPOSAL: not approved, not in force] {p.name(prop['decision'])} proposes changing it."])
    for ref in result.get("missing", []):
        blocks.append([_NOT_FOUND.format(ref=ref)])
    return blocks


def _search(p, output, cuts, date):
    result = output["result"]
    blocks = []
    for c in result.get("candidates", []):
        label = p.label(c["type"], c["state"])
        lines = [f"[CANDIDATE from search, unconfirmed] {label} {p.name(c['reference'])}"]
        if c["class"] == "current":
            lines.append(f"In force on {date}.")
        elif c.get("in_force_now"):
            lines.append(f"No longer in force; {p.name(c['in_force_now'])} is in force now.")
        else:
            lines.append(f"Not in force on {date}.")
        lines.append(f"Fragment: {c['fragment']}")
        r = p.snap.records.get(c["id"]) or {}
        if r.get("type") == "decision":
            lines.append(p.approval({"approvals": _Query(p.snap, **cuts)._approvals(r)}))
        lines += p.supersessions(c["id"])
        blocks.append(lines)
    if not blocks:
        blocks.append(["No matches among what is in force."])
    excluded = result.get("excluded", {})
    if any(excluded.values()):
        parts = []
        if excluded.get("proposal"):
            parts.append(f"{excluded['proposal']} in proposals (--include proposals)")
        if excluded.get("not_in_force"):
            parts.append(f"{excluded['not_in_force']} in what is no longer in force (--include not_in_force)")
        blocks.append(["There are more matches that are not shown: " + "; ".join(parts) + "."])
    return blocks


def present(op, output, snapshot, *, with_ids=False):
    """Plain text of the `output` envelope of `op`."""
    p = _Presenter(snapshot, with_ids)
    cuts = {"valid_at": output["valid_at"], "known_until": output["known_until"]}
    date = _date(cuts["valid_at"])
    header = f"As of {date}"
    if cuts["known_until"]:
        header += f", with what was known until {_date(cuts['known_until'])}"
    if op == "search":
        header += f". Text search: «{output['result']['query']}»"
    blocks = {"query": _query, "consolidate": _consolidate, "search": _search}[op](p, output, cuts, date)
    text = [header + "."]
    for b in blocks:
        text.append("\n".join([b[0], *(f"  {x}" for x in b[1:])]))
    rest = [a for a in output.get("warnings", []) if "UNDECLARED_SUPERSESSION" not in a]
    if output["result"].get("state") == "partial":
        text.append("The answer is partial: something requested is missing or the whole base could not be read.")
    if output["coverage"].get("truncated") and op == "search" and output["result"].get("candidates"):
        text.append("Only the first candidates are shown (--limit to see more).")
    if rest:
        if len(rest) == 1:
            text.append("There is 1 more technical warning: run without --plain to see it.")
        else:
            text.append(f"There are {len(rest)} more technical warnings: run without --plain to see them.")
    return "\n\n".join(text)
