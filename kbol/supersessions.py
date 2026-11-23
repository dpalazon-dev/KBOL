"""Undeclared supersessions: records that say they replace or repeal another without declaring it (bench P04).

KBOL only follows `amends` and `supersedes` to decide what is in force. A legacy record may say in prose that it
replaces another ("Supersedes (partial): ADR-0005") or point to it in `affects`, and then the replaced one comes out
in force in full. This module detects it deterministically and flags it; it neither blocks nor changes the validity,
which still comes from what is declared.

There is a hint when, for a target that exists in the base, that the record could have declared (`amends` between
decisions, `supersedes` between records of the same type) and does not declare:

- a line of the title, the description or the body names the target shortly after an affirmed, active replacement
  verb ("supersedes", "replaces", "repeals", "makes obsolete"), outside a question; "superseded by X" does not
  count, because X is the one that replaces; or
- the target is in `affects` and some line starts with a replacement label ("Supersedes", "Replaces", "Repeals"),
  even if it does not name it.

A target that another record already regularizes (it declares it in `amends` or `supersedes` and names the one that
flags it) is not flagged. A negation right before the verb ("does not replace") does not count. It is a lexical
heuristic: there may be false positives and omissions, and the alert says so.

The patterns also recognize the Spanish forms (sustituye, deroga, reemplaza, deja obsoleta, por, en parte, no, sin),
deliberately: records written before 0.13 may be in Spanish.
"""

import re

_VERB = re.compile(
    r"(?<![\w-])(not\s+|without\s+|no\s+|sin\s+)?"
    r"(supersed\w*|replac\w*|repeal\w*|makes?\s+obsolete|sustitu\w*|derog\w*|reemplaz\w*|deja\s+obsolet\w*|dejan\s+obsolet\w*)",
    re.IGNORECASE,
)
_LABEL = re.compile(
    r"^\s*(?:[*>-]\s*)*(?:\*\*)?(supersedes|superseded|replaces|repeals|makes\s+obsolete|sustituye(?:\s+a)?|deroga|reemplaza|deja\s+obsoleta)\b",
    re.IGNORECASE,
)
_ID = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9A-Za-z][0-9A-Za-z-]*")
_FILE = re.compile(r"\b(\d{4})-[\w.-]+\.md\b")


_PASSIVE = re.compile(r"^\s*(?:\(?(?:partially|partial|en parte)\)?\s+)?(?:by|por)\b", re.IGNORECASE)
_WINDOW = 80


def _after_verb(line):
    """What follows, up to `_WINDOW` characters, each affirmed, active replacement verb of the line: that is where the
    replaced record is named. "Superseded by X" says who replaces the record, not whom it replaces."""
    pieces = []
    for m in _VERB.finditer(line):
        rest = line[m.end() :]
        if m.group(1) or _PASSIVE.match(rest):
            continue
        pieces.append(rest[:_WINDOW])
    return " ".join(pieces)


def _affirmed_verb(text):
    return next((m.group(2) for m in _VERB.finditer(text) if not m.group(1)), None)


class _Resolutor:
    """From a mention in prose to an ID of the base: full ID, unique prefix or `NNNN-…md` file of an ADR."""

    def __init__(self, snapshot):
        self.ids = set(snapshot.records)
        self.by_number = {}
        for i in self.ids:
            m = re.fullmatch(r"[A-Z]+-(\d{4})", i)
            if m:
                self.by_number.setdefault(m.group(1), []).append(i)

    def __call__(self, token):
        token = token.rstrip("-.")
        if token in self.ids:
            return token
        if len(token) >= 6:
            found = [i for i in self.ids if i.startswith(token)]
            if len(found) == 1:
                return found[0]
        return None

    def in_(self, line):
        found = [x for x in (self(t) for t in _ID.findall(line)) if x]
        for number in _FILE.findall(line):
            if len(self.by_number.get(number, [])) == 1:
                found.append(self.by_number[number][0])
        return list(dict.fromkeys(found))


def _declared(r):
    targets = {str(m.get("target", "")).split("#", 1)[0] for m in r.get("amends") or [] if isinstance(m, dict)}
    return targets | set(r.get("supersedes") or [])


def _admissible(snapshot, ident, target):
    """The record could have declared it: `amends` between decisions or `supersedes` between records of the same type
    (decision, fact or source). A question that talks about replacing replaces nothing."""
    origin = snapshot.records[ident].get("type")
    type_ = (snapshot.records.get(target) or {}).get("type")
    return origin in ("decision", "fact", "source") and type_ == origin


def undeclared(snapshot):
    """Hints [{record, target, hint, reason}] sorted by record and target."""
    resolve = _Resolutor(snapshot)
    findings = {}
    for ident, r in sorted(snapshot.records.items()):
        body = snapshot.bodies.get(ident) or ""
        declared = _declared(r) | {ident}
        lines = [r.get("title") or "", r.get("description") or ""] + body.splitlines()
        labels = [x for x in lines if _LABEL.match(x)]
        # Lines that affirm a replacement: a label, or an affirmed replacement verb outside a question.
        affirming = [x for x in lines if _LABEL.match(x) or ("¿" not in x and "?" not in x and _after_verb(x))]
        candidates = {}
        for line in affirming:
            for target in resolve.in_(line if _LABEL.match(line) else _after_verb(line)):
                candidates.setdefault(target, f"«{' '.join(line.split())[:160]}»")
        if labels:
            for target in r.get("affects") or []:
                label = " ".join(labels[0].split())[:160]
                candidates.setdefault(target, f"affects and «{label}»")
        for target, hint in candidates.items():
            if target not in declared and target in snapshot.records and _admissible(snapshot, ident, target):
                findings[(ident, target)] = hint
    regularized = set()
    for other, r in snapshot.records.items():
        text = f"{snapshot.bodies.get(other) or ''} {r.get('title') or ''} {r.get('based_on') or ''}"
        text += f" {r.get('affects') or ''} {r.get('depends_on') or ''}"
        for target in _declared(r):
            for ident, d in findings:
                if d == target and ident != other and ident in text:
                    regularized.add((ident, d))
    return [
        {
            "record": ident,
            "target": target,
            "hint": hint,
            "reason": (
                f"UNDECLARED_SUPERSESSION: {ident} says it replaces or repeals {target} ({hint}) without declaring it "
                f"in amends or supersedes; the validity of {target} is computed as if it did not "
                "(lexical hint: check it in the text)"
            ),
        }
        for (ident, target), hint in sorted(findings.items())
        if (ident, target) not in regularized
    ]


def alerts_for(hints, ids):
    """The reasons of the hints that affect `ids`, as the flagging record or as the target."""
    ids = set(ids)
    return [i["reason"] for i in hints if i["record"] in ids or i["target"] in ids]
