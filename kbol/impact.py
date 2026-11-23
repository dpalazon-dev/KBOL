"""VAL-09 and RES-05: consumers affected by a change, with cause, path and owner.

Compares a final revision with its base. It starts from the changed or new records and from the normative targets of
those changes (`amends`, `supersedes`, `affects`) and walks the declared references towards whoever consumes them.
It does not promise to find dependencies hidden in prose: without a declared edge there is no computed impact, which
does not prove independence. Each affected record stays `pending` until its owner resolves it.
"""

from collections import deque

from .markdown import MarkupError, facts
from .model import REFERENCES

MAX_HOPS = 10
# Header fields through which a record consumes another (`consumption` in `model.REFERENCES`). A role that
# changes affects what it authorizes and who holds it; the plan consumes the decision it relies on and the milestone,
# what it closes, advances, tests or produces. The `<fact ref>` citations of the body also consume; read separately.
CONSUMPTION = tuple(c for c, r in REFERENCES.items() if r.consumption and r.shape != "body")


def _references(r, body):
    for field in CONSUMPTION:
        for v in r.get(field) or []:
            target = (v.get("target") or v.get("resource") or v.get("role")) if isinstance(v, dict) else v
            if isinstance(target, str):
                yield target
    try:
        yield from (h["ref"] for h in facts(body or "") if "ref" in h)
    except MarkupError:
        return


def _matches(point, ref):
    p, _, pa = point.partition("#")
    r, _, ra = ref.partition("#")
    return p == r and (not pa or not ra or pa == ra)


def _owner(r):
    if r.get("type") in ("question", "milestone") and r.get("owner"):
        return [r["owner"]]
    return list(r.get("authorized_by") or []) or None


def impact(base, final):
    """{base, revision, changed, affected, warnings} of the step from `base` to `final`."""
    changed = sorted(
        i
        for i, r in final.records.items()
        if base.records.get(i) != r or base.bodies.get(i) != final.bodies.get(i)
    )
    res = {
        "base": base.revision,
        "revision": final.revision,
        "changed": changed,
        "affected": [],
        "warnings": [],
    }
    queue, seen = deque(), set(changed)

    def affect(ident, way):
        r = final.records.get(ident)
        if r is None or ident in seen:
            return
        seen.add(ident)
        res["affected"].append(
            {
                "affected": ident,
                "type": r.get("type"),
                "cause": f"change in {way[-2]}",
                "path": way,
                "owner": _owner(r),
                "resolution": "pending",
                "outdated": r.get("type") == "synthesis",
            }
        )
        queue.append((ident, way))

    for c in changed:
        r = final.records[c]
        queue.append((c, [c]))
        for mod in r.get("amends") or []:
            if isinstance(mod, dict) and isinstance(mod.get("target"), str):
                queue.append((mod["target"], [c, mod["target"]]))
        for d in r.get("supersedes") or []:
            queue.append((d, [c, d]))
        for d in r.get("affects") or []:
            affect(d.split("#", 1)[0], [c, d])
    while queue:
        point, way = queue.popleft()
        if len(way) > MAX_HOPS:
            res["warnings"].append(f"impact truncated at {MAX_HOPS} hops in {' → '.join(way)}")
            continue
        for ident in sorted(final.records):
            refs = _references(final.records[ident], final.bodies.get(ident))
            if any(_matches(point, ref) for ref in refs):
                affect(ident, way + [ident])
    return res
