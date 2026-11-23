"""Minimal valid records per type, with IDs from the contract test corpus."""

import copy

import pytest

T0 = "2026-11-01T00:00:00Z"
T1 = "2026-11-02T00:00:00Z"

BASE = {
    "class": "record",
    "title": "Title",
    "description": "One line.",
    "scope": "operations",
    "author": "example-agent/1",
    "events": [],
    "sources": [],
}

BY_TYPE = {
    "decision": dict(
        id="DEC-EXAMPLE",
        state="proposed",
        authorized_by=["ROLE-EXAMPLE"],
        alternatives=[
            dict(id="A", description="Monday.", selected=False, reason="No day to check."),
            dict(id="B", description="Tuesday.", selected=True, reason="Keeps Monday free."),
        ],
        criteria=["Checked data", "Deadline"],
        rationale="Keep a day free.",
    ),
    "fact": dict(
        id="FACT-A",
        state="proposed",
        claim="Table 2 gives 5 m3/h.",
        evidence_class="observed",
        based_on=["SRC-A"],
        date="2026-10-30",
        precision="day",
    ),
    "source": dict(
        id="SRC-A",
        state="registered",
        subtype="original",
        origin="Email from the operator",
        location="sources/SRC-A.pdf",
        format="application/pdf",
        sha256="a" * 64,
        access="common-read",
    ),
    "person": dict(
        id="PER-A",
        state="proposed",
        nature="human",
        identity_ref="github:1",
        holds=[{"role": "ROLE-EXAMPLE", "from": T0}],
    ),
    "role": dict(
        id="ROLE-EXAMPLE", state="proposed", scopes=["operations"], capabilities=["ratify"], approval_rule="one"
    ),
    "question": dict(
        id="Q-A", state="open", subtype="unknown", owner="ROLE-EXAMPLE", closing_condition="Measured."
    ),
    "hypothesis": dict(
        id="HYP-A",
        state="open",
        claim="X",
        test_plan="Y",
        refutation_criterion="Z",
        consequence_if_fails="W",
    ),
    "assumption": dict(id="ASM-A", state="active", claim="X", review_at="2026-12-01", consequence_if_fails="W"),
    "entity": dict(id="ENT-A", state="proposed", name="Plant", aliases=["WWTP"], entity_class="installation"),
    "plan": dict(
        id="PLAN-A",
        state="proposed",
        goal="O",
        milestones=["MS-A"],
        authorized_by=["ROLE-EXAMPLE"],
        constraints=["Do not send"],
    ),
    "milestone": dict(
        id="MS-A",
        state="proposed",
        goal="Prepare the report",
        work_scope="Own branch",
        authorized_by=["ROLE-EXAMPLE"],
        acceptance=[dict(criterion_id="K1", description="Tests", method="command", required=True)],
        tolerances={"time": "2h"},
        checks=[
            dict(
                check_id="V1",
                criterion_id="K1",
                executor="pytest",
                input={"argv": ["-q"]},
                environment_ref="local",
                timeout=600,
                permitted_effects=[],
            )
        ],
    ),
    "synthesis": dict(id="SYN-A", state="draft", dependencies=["DEC-EXAMPLE#C1"], evaluations=[]),
}

DECISION_BODY = '<clause id="C1">\nThe report is delivered on Tuesdays.\n</clause>\n'


def record(type_, **changes):
    r = copy.deepcopy(BASE)
    r["type"] = type_
    r.update(copy.deepcopy(BY_TYPE[type_]))
    r.update(changes)
    return r


def event(event_type="transition", **changes):
    e = dict(
        event_id="E1",
        event_type=event_type,
        actor="process:integrator",
        recorded_at=T0,
        valid_from=T0,
        reason="m",
        event_evidence={"mechanism": "github-review", "proof": "review:1"},
    )
    e.update(changes)
    return e


def body_of(clauses):
    return "".join(f'<clause id="{a}">\n{t}\n</clause>\n\n' for a, t in clauses.items())


def decision(ident, clauses, recorded=T0, valid=None, until=None, state="accepted", **extra):
    """(record, body) of a decision with an admitted history: creation, ratification and acceptance."""
    events = [
        event(
            "creation",
            event_id="E0",
            previous_state=None,
            new_state="proposed",
            recorded_at=recorded,
            valid_from=recorded,
        )
    ]
    if state == "accepted":
        appr = dict(
            approval_id=f"AP-{ident}",
            actor="human:david",
            identity_ref="github:1",
            roles=["ROLE-EXAMPLE"],
            digest="b" * 64,
            base_revision="r0",
            approved_at=recorded,
            policy_revision="r0",
            proof="review:1",
        )
        events.append(
            event("ratification", event_id="E1", recorded_at=recorded, valid_from=recorded, approval=appr)
        )
        step = event(
            event_id="E2",
            previous_state="proposed",
            new_state="accepted",
            recorded_at=recorded,
            valid_from=valid or recorded,
        )
        if until:
            step["valid_until"] = until
        events.append(step)
    r = record("decision", id=ident, state=state, events=events, **extra)
    return r, body_of(clauses)


@pytest.fixture
def new():
    return record
