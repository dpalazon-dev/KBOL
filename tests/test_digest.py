"""Contractual digest: exact serialization, covered fields and published vectors."""

import hashlib
import json
from pathlib import Path

import pytest
from conftest import DECISION_BODY, event, record

from kbol.digest import approvable_object, canonical_bytes, digest

VECTORS = Path(__file__).resolve().parents[1] / "kbol" / "vectors" / "digest.json"
EFFECT = [{"previous_state": "proposed", "new_state": "accepted", "valid_from": "2026-11-15T00:00:00Z"}]


def test_approvable_object_separates_content_from_events_and_projections():
    r = record(
        "decision", status="draft", verified=[{"by": "human:x", "at": "2026-11-01T00:00:00Z", "digest": "c" * 64}]
    )
    r["events"] = [event("creation", previous_state=None, new_state="proposed")]
    obj = approvable_object(r, DECISION_BODY, EFFECT)
    assert set(obj) == {
        "id",
        "type",
        "class",
        "title",
        "description",
        "scope",
        "author",
        "body",
        "fields",
        "requested_effects",
    }
    for excluded in ("events", "status", "verified", "evaluations", "state", "id", "title"):
        assert excluded not in obj["fields"]
    assert obj["fields"]["sources"] == [] and "alternatives" in obj["fields"]


def test_changes_that_alter_the_digest():
    r = record("decision")
    d = digest(r, DECISION_BODY, EFFECT)
    assert d != digest(r, DECISION_BODY.replace("Tuesdays", "Wednesdays"), EFFECT)
    assert d != digest(r, DECISION_BODY, [{**EFFECT[0], "valid_from": "2026-11-16T00:00:00Z"}])
    assert d != digest({**r, "amends": [{"target": "DEC-A#C1", "operation": "repeals"}]}, DECISION_BODY, EFFECT)
    assert d != digest({**r, "alternatives": list(reversed(r["alternatives"]))}, DECISION_BODY, EFFECT)


def test_changes_that_do_not_alter_the_digest():
    r = record("decision")
    d = digest(r, DECISION_BODY, EFFECT)
    assert d == digest(r, DECISION_BODY.replace("\n", "\r\n"), EFFECT)
    assert d == digest(dict(reversed(list(r.items()))), DECISION_BODY, EFFECT)
    with_events = {
        **r,
        "events": [event("creation", previous_state=None, new_state="proposed")],
        "status": "draft",
    }
    assert d == digest(with_events, DECISION_BODY, EFFECT)


def test_unnormalized_unicode_and_escapes():
    r = record("decision")
    composed = digest({**r, "title": "\u00f1"}, DECISION_BODY, [])
    decomposed = digest({**r, "title": "n\u0303"}, DECISION_BODY, [])
    assert composed != decomposed
    b = canonical_bytes({"a": 'quote " backslash \\ tab \t nul \x00', "b": "\u00f1"})
    assert b == '{"a":"quote \\" backslash \\\\ tab \\t nul \\u0000","b":"\u00f1"}'.encode()
    assert not b.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("value", [1.5, float("nan"), {"x": 2.0}, [object()]])
def test_types_not_admitted(value):
    with pytest.raises(ValueError):
        canonical_bytes({"v": value})


def test_keys_sorted_by_unicode_code_point():
    assert canonical_bytes({"\u00e9": 1, "z": 2, "Z": 3, "a": 4}) == '{"Z":3,"a":4,"z":2,"\u00e9":1}'.encode()


def test_published_vectors():
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert len(vectors) >= 4
    for v in vectors:
        obj = approvable_object(v["record"], v["body"], v["requested_effects"])
        b = canonical_bytes(obj)
        assert b.decode("utf-8") == v["bytes"], v["name"]
        assert (
            hashlib.sha256(b).hexdigest() == v["sha256"] == digest(v["record"], v["body"], v["requested_effects"])
        )
