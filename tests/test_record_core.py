"""The references table of `model` is the only source of the names of relations and fields with a target.

The views derived from it keep the values and the order they had when written by hand (revision 6278bfc): they are
frozen here. The order is compared where it is observed: in the tuples walked to report and in the keys of the maps
that are walked.
"""

from kbol import impact, model, mutability, query, references, support
from kbol.model import CYCLES, FORMS, REFERENCES, TYPES

RELATIONS = {
    "resolved_by": {"origin": ("question",), "target": ("decision",), "anchor": "forbidden"},
    "challenges": {"origin": ("question",), "target": ("decision",), "anchor": "required"},
    "supersedes": {"origin": ("decision", "fact", "source"), "target": "same", "anchor": "forbidden"},
    "tests": {"origin": ("hypothesis",), "target": ("decision",), "anchor": "required"},
    "based_on": {
        "origin": ("decision", "fact", "hypothesis", "question"),
        "target": ("source", "fact"),
        "anchor": "optional",
    },
    "derived_from": {"origin": ("source",), "target": ("source",), "anchor": "forbidden"},
    "affects": {"origin": ("decision", "fact", "question"), "target": None, "anchor": "optional"},
    "authorized_by": {"origin": ("decision", "plan", "milestone"), "target": ("role",), "anchor": "forbidden"},
    "closes": {"origin": ("milestone",), "target": ("question",), "anchor": "forbidden"},
    "advances": {"origin": ("milestone",), "target": ("question",), "anchor": "forbidden"},
    "tests_hypothesis": {"origin": ("milestone",), "target": ("hypothesis",), "anchor": "forbidden"},
    "produces": {"origin": ("milestone",), "target": None, "anchor": "optional"},
    "relies_on": {"origin": ("plan",), "target": ("decision",), "anchor": "optional"},
}
LINKS = ("closes", "advances", "tests_hypothesis", "produces", "relies_on")
OBJECT_RELATIONS = {
    "amends": ("decision",),
    "depends_on": ("question", "decision", "plan", "milestone"),
    "holds": ("person",),
    "vetoes": ("decision",),
    "defines": ("decision",),
}
NO_CYCLES = ("supersedes", "amends", "derived_from", "depends_on")
CONSUMPTION = (
    "depends_on",
    "based_on",
    "dependencies",
    "sources",
    "challenges",
    "tests",
    "derived_from",
    "resolved_by",
    "authorized_by",
    "holds",
    "relies_on",
    "closes",
    "advances",
    "tests_hypothesis",
    "produces",
)
EXPECTED_TARGET = {
    "holds": ("role",),
    "milestones": ("milestone",),
    "owner": ("role", "person"),
    "amends": ("decision",),
    "body": ("fact",),
}
QUERY_RELATIONS = (*RELATIONS, "amends", "depends_on", "holds", "milestones", "defines")
FREE = {"title", "description", "generated", "verified", "stale_after", "status", "evaluations", "events"}
FREE |= set(LINKS) | {"owner", "evidence", "implementation"}
SUPPORTS = ("based_on", "dependencies", "sources")


def test_model_views_keep_values_and_order():
    assert model.RELATIONS == RELATIONS and list(model.RELATIONS) == list(RELATIONS)
    assert model.OBJECT_RELATIONS == OBJECT_RELATIONS and list(model.OBJECT_RELATIONS) == list(OBJECT_RELATIONS)
    assert model.LINKS == LINKS
    # The order of NO_CYCLES is that of the cycle findings in `validate_snapshot`.
    assert model.NO_CYCLES == NO_CYCLES


def test_consumer_views_keep_values_and_order():
    # `impact` only asks whether some reference matches: the order of CONSUMPTION is not observed.
    assert isinstance(impact.CONSUMPTION, tuple) and set(impact.CONSUMPTION) == set(CONSUMPTION)
    assert len(impact.CONSUMPTION) == len(CONSUMPTION)
    assert references.EXPECTED_TARGET == EXPECTED_TARGET
    # The order of the relations is that of the output of `query`.
    assert query._RELATIONS == QUERY_RELATIONS
    assert mutability.FREE == FREE
    assert support.FIELDS == SUPPORTS


def test_edges_walks_in_the_usual_order():
    synthesis = {
        "type": "synthesis",
        "dependencies": ["FACT-1", 7],
        "sources": [{"id": "s1", "resource": "SRC-1"}, {"id": "s2"}, "SRC-x"],
        "resolved_by": ["DEC-1"],
        "based_on": ["SRC-2"],
        "relies_on": ["DEC-2"],
        "amends": [{"target": "DEC-3#C1"}, {"target": None}],
        "depends_on": [{"target": "Q-1"}],
        "holds": [{"role": "ROLE-1"}],
        "vetoes": [{"pattern": "x"}],
        "owner": "ROLE-2",
        "milestones": ["MS-1"],
    }
    body = '<fact ref="FACT-2">text</fact>'
    assert list(references.edges(synthesis, body)) == [
        ("dependencies", "FACT-1"),
        ("sources", "SRC-1"),
        ("body", "FACT-2"),
        ("resolved_by", "DEC-1"),
        ("based_on", "SRC-2"),
        ("relies_on", "DEC-2"),
        ("amends", "DEC-3#C1"),
        ("depends_on", "Q-1"),
        ("holds", "ROLE-1"),
    ]
    # Own fields only count in the types that declare them; relations, in any.
    plan = {"type": "plan", "milestones": ["MS-1"], "owner": "ROLE-2", "dependencies": ["FACT-1"], "challenges": ["X"]}
    assert list(references.edges(plan)) == [("challenges", "X"), ("milestones", "MS-1")]
    question = {"type": "question", "owner": "ROLE-2", "milestones": ["MS-1"]}
    assert list(references.edges(question)) == [("owner", "ROLE-2")]
    # Without a body there are no citations; with broken markup neither, and it is not an error.
    assert ("body", "FACT-2") not in list(references.edges(synthesis))
    assert ("body", "FACT-2") not in list(references.edges(synthesis, '<fact ref="FACT-2">no closing'))


def test_each_table_entry_has_a_coherent_shape():
    for field, r in REFERENCES.items():
        assert r.shape in FORMS, field
        assert r.origin is None or (r.origin and set(r.origin) <= set(TYPES)), field
        assert r.target in (None, "same") or (r.target and set(r.target) <= set(TYPES)), field
        assert r.without_cycles in (None, *CYCLES), field
        if r.shape != "objects":
            assert r.key is None, field
        has_target = r.shape != "objects" or r.key is not None
        if has_target:
            assert r.anchor in ("forbidden", "required", "optional"), field
        else:
            # An object without a target key (`vetoes`) points to nothing: no anchor, no type, no effects in the graph.
            assert r.anchor is None and r.target is None, field
            assert not (r.consumption or r.without_cycles or r.evidence), field
        if r.relation:
            # The table gives the shape of a relation: list of IDs or of objects, with their origin types.
            assert r.shape in ("ids", "objects") and r.origin, field
        else:
            # An own field has no cycle rule nor the shape of a list of objects without a target.
            assert r.without_cycles is None, field


def test_ordered_literals_do_not_depart_from_the_table():
    """The report order is written by hand; the table fixes the content."""
    evidence = {c for c, r in REFERENCES.items() if r.evidence and r.shape != "body"}
    assert set(support.FIELDS) == evidence
    assert set(query._RELATIONS) <= set(REFERENCES)
