"""Grammar of clauses and claims of the concrete contract."""

import pytest

from kbol.markdown import MarkupError, clauses, facts


def test_clauses_by_id_not_by_position():
    c = clauses('<clause id="C2">\nB\n</clause>\n\n<clause id="C1">\nA *md*\n</clause>\n')
    assert c == {"C2": "B", "C1": "A *md*"}


@pytest.mark.parametrize(
    "body",
    [
        '<clause id="C1">\nx\n</clause>\n<clause id="C1">\ny\n</clause>',  # repeated
        '<clause id="C1">\n<clause id="C2">\n</clause>\n</clause>',  # nested
        '<clause id="C1">\nno closing',
        "</clause>",
        '<clause id="X1">\nx\n</clause>',  # invalid identifier
        '  <clause id="C1">\nx\n</clause>',  # not on its own line
    ],
)
def test_malformed_clauses(body):
    with pytest.raises(MarkupError):
        clauses(body)


def test_code_and_escapes_do_not_open_clauses():
    body = (
        '```\n<clause id="C9">\n```\n'
        "~~~~\n</clause>\n~~~~\n"
        '\\<clause id="C8">\n'
        '`<clause id="C7">`\n'
        '<clause id="C1">\nA\n</clause>\n'
    )
    assert clauses(body) == {"C1": "A"}


def test_inline_facts():
    body = 'The flow is <fact id="H1" evidence="observed" source="s1">5 m3/h at 20 °C</fact>. See <fact ref="FACT-A">the measurement</fact>.'
    h = facts(body)
    assert h == [
        {"id": "H1", "evidence": "observed", "source": "s1", "text": "5 m3/h at 20 °C"},
        {"ref": "FACT-A", "text": "the measurement"},
    ]


@pytest.mark.parametrize(
    "body",
    [
        '<fact id="H1" evidence="observed" source="s1">a</fact><fact id="H1" evidence="observed" source="s1">b</fact>',
        '<fact id="H1" evidence="observed">a</fact>',  # missing source
        '<fact id="H1" evidence="observed" source="s1">a',  # no closing
        '<fact ref="FACT-A" id="H1">a</fact>',  # ref and inline shape at once
        '<fact id="H1" evidence="observed" source="s1"><fact ref="FACT-A">x</fact></fact>',
    ],
)
def test_malformed_facts(body):
    with pytest.raises(MarkupError):
        facts(body)


def test_facts_in_code_are_ignored():
    assert facts('```\n<fact id="H1">x</fact>\n```\n`<fact id="H2">y</fact>`') == []
