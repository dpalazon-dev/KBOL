"""Safe reading and canonical writing of the Markdown container with a YAML header."""

import pytest
from conftest import DECISION_BODY, record

from kbol.core import FormatError, parse, serialize


@pytest.mark.parametrize(
    "header",
    [
        "a: 1\na: 2",  # repeated key
        "a:\n  b: 1\n  b: 2",  # nested repeated key
        "a: !!python/object:builtins.object {}",  # object construction
        "a: !!str text",  # any explicit tag
        "a: &x [1]\nb: *x",  # alias
        "a:\n  <<: {b: 1}",  # merge key
        "- list",  # the header must be a mapping
        "1: integer",  # non-text key
    ],
)
def test_rejected_headers(header):
    with pytest.raises(FormatError):
        parse(f"---\n{header}\n---\n")


def test_missing_header_fails():
    with pytest.raises(FormatError):
        parse("# body only\n")


def test_dates_are_read_as_text_and_unicode_is_kept():
    meta, body = parse('---\ndate: 2026-11-03\ntitle: "Straße ü"\n---\nbody\r\n')
    assert meta == {"date": "2026-11-03", "title": "Straße ü"}
    assert body == "body\r\n"


def test_unknown_fields_are_kept_when_reading():
    meta, _ = parse("---\nid: DEC-A\nextra:\n  nested: [1, 2]\n---\n")
    assert meta["extra"] == {"nested": [1, 2]}


def test_round_trip_keeps_semantics():
    r = record("decision", title="Deadline: «5 days» # not a comment", criteria=["yes", "no", "2026-11-03", "1.0"])
    text = serialize(r, DECISION_BODY)
    assert text.startswith("---\n") and "\r" not in text
    meta, body = parse(text)
    assert meta == r
    assert body == DECISION_BODY


def test_serialize_rejects_invalid_record_or_unknown_fields():
    with pytest.raises(FormatError, match="INVALID_SCHEMA"):
        serialize(record("decision", extra="x"), DECISION_BODY)
    with pytest.raises(FormatError):
        serialize(record("decision"), "no clauses")


def test_serialize_normalizes_body_line_breaks():
    text = serialize(record("decision"), DECISION_BODY.replace("\n", "\r\n"))
    assert "\r" not in text
