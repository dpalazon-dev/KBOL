"""VAL-04: authority checked for the requested effects on a record (core 1.0, §7 and ESC-03).

The policy is the one of the base revision, before the change: a change cannot grant itself the authority it uses.
Whoever asks for the integration only identifies reviews; this module computes the digest from the content and the
effects of the reviewed commit, and each approval is built from what the trust channel verifies. A review counts if
the verified account matches a single active human person who holds a required role at the instant of the review
and, if given, also at the instant of the integration (revocation is revalidated when integrating). Then the rule of
each role applies: `one`, `all` or `quorum`.

Local capabilities: `ratify` in the role's scopes, and `govern_policy` to change roles and identities.
"""

from .digest import digest
from .events import HistoryError
from .projection import state_at_cut
from .timeutil import instant
from .verification import VerificationError, revision_key

RATIFY, GOVERN = "ratify", "govern_policy"


def _active(record, when):
    try:
        return record is not None and when is not None and state_at_cut(record, when) == "active"
    except HistoryError:
        return False


def _holds(person, role, when):
    t = instant(when)
    for o in person.get("holds") or []:
        if o.get("role") == role and instant(o["from"]) <= t and (o.get("until") is None or t < instant(o["until"])):
            return True
    return False


def required_roles(record, policy, when, policy_change=False):
    """(roles, mode, problems) at the instant `when`. `mode`: `each` (authorized_by) or `some` (implicit)."""
    roles = {i: r for i, r in policy.records.items() if r.get("type") == "role"}
    if record.get("type") in ("role", "person") or policy_change:
        gob = [i for i, r in roles.items() if GOVERN in (r.get("capabilities") or []) and _active(r, when)]
        return gob, "some", [] if gob else ["the base policy has no active role that governs the policy"]
    declared = record.get("authorized_by")
    scope = record.get("scope")
    if declared:
        problems = []
        for i in declared:
            r = roles.get(i)
            if not _active(r, when):
                problems.append(f"{i} is not an active role in the base policy")
            elif RATIFY not in (r.get("capabilities") or []):
                problems.append(f"{i} does not have the capability to ratify")
            elif scope not in (r.get("scopes") or []):
                problems.append(f"{i} does not cover the scope {scope}")
        return list(declared), "each", problems
    implicit = [
        i
        for i, r in roles.items()
        if RATIFY in (r.get("capabilities") or []) and scope in (r.get("scopes") or []) and _active(r, when)
    ]
    return implicit, "some", [] if implicit else [f"no active role ratifies in the scope {scope}"]


def _humans_of_role(policy, role, instants):
    return {
        i
        for i, p in policy.records.items()
        if p.get("type") == "person"
        and p.get("nature") == "human"
        and all(_active(p, t) and _holds(p, role, t) for t in instants)
    }


def _rule_met(rule, approved, holders):
    if rule == "all":
        return bool(holders) and holders <= approved
    if isinstance(rule, dict):
        return len(approved) >= rule.get("quorum", 0)
    return len(approved) >= 1


def evaluate(
    record,
    body,
    effects,
    revisions,
    policy,
    verifier,
    proposal_rev,
    base_rev,
    revalidate_at=None,
    policy_change=False,
    import_=None,
):
    """{authorized, code, digest, required, roles, revisions, approvals, problems}.

    `approvals` are the approval objects built from verified data, ready for their event.
    """
    d = digest(record, body, effects, import_=import_)
    persons = {i: p for i, p in policy.records.items() if p.get("type") == "person"}
    verified, results, views = [], [], set()
    for rv in revisions:
        key = revision_key(rv)
        if key in views:
            continue  # a review cited twice is a single approval
        views.add(key)
        res = {"revision": rv, "valid": False, "reason": None, "code": None, "person": None}
        results.append(res)
        try:
            v = verifier.verify(rv, proposal_rev, base_rev)
        except VerificationError as exc:
            res["reason"], res["code"] = str(exc), exc.code
            continue
        if "digests" in v and v["digests"].get(record.get("id")) != d:
            res["reason"] = "what was approved is not what is integrated: the digest shown does not match"
            res["code"] = "STALE_APPROVAL"
            continue
        res["verified_at"] = v["instant"]
        account = [i for i, p in persons.items() if p.get("identity_ref") == v["identity"] and _active(p, v["instant"])]
        if len(account) != 1:
            res["reason"] = f"{v['identity']} does not match a single active person in the base policy"
            continue
        person = persons[account[0]]
        res["person"] = account[0]
        if person.get("nature") != "human":
            res["reason"] = "an agent does not ratify"
            continue
        if revalidate_at is not None and not _active(person, revalidate_at):
            res["reason"] = "the person is no longer active when integrating"
            continue
        verified.append((res, person, v))
    when = revalidate_at or (max((v["instant"] for _, _, v in verified), key=instant) if verified else None)
    required, mode, problems = (
        required_roles(record, policy, when, policy_change) if when else ([], "some", ["no verified review"])
    )
    approved, approvals = {}, []
    for res, person, v in verified:
        instants = [v["instant"]] + ([revalidate_at] if revalidate_at else [])
        exercised = [r for r in required if all(_holds(person, r, t) for t in instants)]
        if not exercised:
            res["reason"] = "does not hold a required role at the instant of the review or when integrating"
            continue
        res["valid"], res["roles"] = True, exercised
        for r in exercised:
            approved.setdefault(r, set()).add(res["person"])
        c = v["proof"]
        approval_id = v.get("approval_id") or f"{c['mechanism']}:{c['repository']}#{c['pull']}/{c['review_id']}"
        if any(a["approval_id"] == approval_id for a in approvals):
            continue  # the same approval, cited another way: it counts once
        approvals.append(
            {
                "approval_id": approval_id,
                "actor": f"human:{res['person']}",
                "identity_ref": v["identity"],
                "roles": exercised,
                "digest": d,
                "base_revision": base_rev,
                "approved_at": v["instant"],
                "policy_revision": policy.revision,
                "proof": c,
            }
        )
    role_states = {}
    for r in required:
        rule = (policy.records.get(r) or {}).get("approval_rule", "one")
        instants = [when] if when else []
        facts = approved.get(r, set())
        holders = _humans_of_role(policy, r, instants) if instants else set()
        role_states[r] = {
            "rule": rule,
            "approved_by": sorted(facts),
            "met": _rule_met(rule, facts, holders),
        }
    met_roles = [r for r, e in role_states.items() if e["met"]]
    authorized = (
        bool(required) and not problems and (len(met_roles) == len(required) if mode == "each" else bool(met_roles))
    )
    if authorized:
        code = None
    elif not any(x["valid"] for x in results) and any(x["code"] == "STALE_APPROVAL" for x in results):
        code = "STALE_APPROVAL"
    else:
        code = "INSUFFICIENT_AUTHORITY"
    return {
        "authorized": authorized,
        "code": code,
        "digest": d,
        "required": required,
        "mode": mode,
        "roles": role_states,
        "revisions": results,
        "approvals": approvals if authorized else [],
        "problems": problems,
        "policy": policy.revision,
    }
