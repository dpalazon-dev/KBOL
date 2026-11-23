"""Lexical search (core §8, "Exploration"), undeclared supersessions and plain-language output.

They repeat in small the bench questions KBOL could not answer or answered badly: P01 (what is in force today on a
subject, without an ID), P09 (a figure in a proposed fact, without an ID) and P04 (a decision that another one partly
replaces only in prose).
"""

import json

from conftest import decision, event, record

from kbol.cli import main
from kbol.consolidate import consolidate
from kbol.core import serialize
from kbol.plain import present
from kbol.projection import Snapshot
from kbol.query import query
from kbol.search import search, terms
from kbol.supersessions import undeclared

T = "2026-11-20T12:00:00Z"


def _proposed_fact(ident, claim):
    creation = event(
        "creation",
        event_id="E0",
        previous_state=None,
        new_state="proposed",
        recorded_at="2026-10-26T00:00:00Z",
        valid_from="2026-10-26T00:00:00Z",
    )
    return record("fact", id=ident, title="First pass of the CRA", claim=claim, events=[creation])


def snap():
    """The tool chain of P01, a proposed fact of P09 and the replacement in prose of P04."""
    regs, bodies = {}, {}

    def put(ident, pair, title):
        r, c = pair
        r["title"] = title
        regs[ident], bodies[ident] = r, c

    put(
        "ADR-0065",
        decision("ADR-0065", {"C1": "codebase-memory-mcp is retired; graphify stays as an optional support."}),
        "Retire codebase-memory-mcp",
    )
    put(
        "ADR-0077",
        decision(
            "ADR-0077",
            {"C1": "Graphify over the working tree as an optional support; git grep closes the impact."},
            recorded="2026-11-10T00:00:00Z",
            amends=[{"target": "ADR-0065#C1", "operation": "replaces", "by": "ADR-0077#C1"}],
        ),
        "Graphify over the working tree",
    )
    put(
        "ADR-0005",
        decision("ADR-0005", {"C1": "MailConfig with BaseSettings, in config/mail.py."}),
        "MailConfig with BaseSettings",
    )
    adr16 = decision(
        "ADR-0016",
        {"C1": "MailConfig lives in libs/common/mail.py; the pattern of ADR-0005 does not change."},
        affects=["ADR-0005"],
    )
    adr16 = (adr16[0], adr16[1] + "\n\n* Supersedes (partial): ADR-0005 §Implementation path\n")
    put("ADR-0016", adr16, "MailConfig path supersedes ADR-0005")
    regs["FACT-CRA"] = _proposed_fact(
        "FACT-CRA", "166 assessable CRA requirements in CISO Assistant; it is not a certification."
    )
    bodies["FACT-CRA"] = ""
    regs["PER-A"] = record("person", id="PER-A", title="David Palazón")
    paths = {i: f"kb/{i}.md" for i in regs}
    return Snapshot(regs, "r1", bodies, paths)


def test_terms_are_normalized_without_accents_or_stop_words():
    assert terms("What is in force today in the code, graphify?") == ["force", "today", "code", "graphi"]


def test_spanish_terms_are_still_normalized():
    # Deliberate Spanish input: records written before 0.13 may be in Spanish; accents and stop words go away.
    assert terms("¿Qué rige hoy en el código, graphify?") == ["rige", "codigo", "graphi"]


def test_p01_without_id_returns_what_is_current_and_counts_what_was_replaced():
    res = search(
        snap(), "What is in force today as a support, graphify or codebase-memory-mcp?", valid_at=T, known_until=T
    )
    refs = [c["reference"] for c in res["candidates"]]
    assert refs[0] == "ADR-0077#C1" and "ADR-0065#C1" not in refs
    first = res["candidates"][0]
    assert first["class"] == "current" and first["state"] == "accepted" and "Graphify" in first["fragment"]
    assert res["excluded"]["not_in_force"] == 1
    assert any("--include not_in_force" in a for a in res["warnings"])
    assert any("does not decide what is in force" in a for a in res["warnings"])


def test_what_was_replaced_only_appears_if_asked_and_says_what_is_in_force_now():
    res = search(snap(), "codebase-memory-mcp", valid_at=T, known_until=T, include=["not_in_force"])
    superseded = next(c for c in res["candidates"] if c["reference"] == "ADR-0065#C1")
    assert superseded["class"] == "not_in_force" and superseded["in_force_now"] == "ADR-0077#C1"


def test_p09_a_proposal_is_counted_and_only_shown_if_asked():
    question = "How many assessable requirements did the first pass of the CRA in CISO Assistant end with?"
    default = search(snap(), question, valid_at=T, known_until=T)
    assert default["candidates"] == [] and default["excluded"]["proposal"] == 1
    assert any("--include proposals" in a for a in default["warnings"])
    with_ = search(snap(), question, valid_at=T, known_until=T, include=["proposal"])
    fact = with_["candidates"][0]
    assert fact["id"] == "FACT-CRA" and fact["class"] == "proposal" and "166" in fact["fragment"]


def test_no_terms_or_no_matches_is_reported():
    assert any("no searchable terms" in a for a in search(snap(), "what?", valid_at=T, known_until=T)["warnings"])
    empty = search(snap(), "nonexistent", valid_at=T, known_until=T)
    assert empty["candidates"] == [] and any("no lexical matches" in a for a in empty["warnings"])


def test_the_limit_truncates_and_declares_it():
    res = search(snap(), "MailConfig graphify", valid_at=T, known_until=T, limit=1)
    assert len(res["candidates"]) == 1 and res["truncated"] is True
    assert any("showing 1 of" in a for a in res["warnings"])


def test_p04_the_replacement_in_prose_is_flagged_without_changing_the_validity():
    s = snap()
    assert [(i["record"], i["target"]) for i in undeclared(s)] == [("ADR-0016", "ADR-0005")]
    output = query(s, ["ADR-0005"], valid_at=T, known_until=T)
    assert output["results"][0]["validity"] == "full"
    assert any("UNDECLARED_SUPERSESSION" in a and "ADR-0016" in a for a in output["warnings"])
    warnings = consolidate(s, ["ADR-0005"], valid_at=T, known_until=T)["warnings"]
    assert any("UNDECLARED_SUPERSESSION" in a for a in warnings)


def test_a_later_regularization_turns_the_alert_off():
    s = snap()
    r, c = decision(
        "ADR-0090",
        {"C1": "MailConfig lives in libs/common/mail.py, as ADR-0016 says."},
        amends=[{"target": "ADR-0005#C1", "operation": "replaces", "by": "ADR-0090#C1"}],
    )
    s.records["ADR-0090"], s.bodies["ADR-0090"] = r, c
    assert undeclared(s) == []


def test_neither_the_passive_nor_the_negation_nor_a_question_are_hints():
    s = snap()
    for ident, text in (
        ("ADR-0100", "* Status: superseded by ADR-0005"),
        ("ADR-0101", "This decision does not replace ADR-0005."),
    ):
        r, c = decision(ident, {"C1": "Something else."})
        s.records[ident], s.bodies[ident] = r, c + "\n" + text
    s.records["Q-1"] = record("question", id="Q-1", title="What replaces ADR-0005?")
    assert [(i["record"], i["target"]) for i in undeclared(s)] == [("ADR-0016", "ADR-0005")]


def test_spanish_prose_replacement_is_still_a_hint():
    # Deliberate Spanish input: a legacy record written in Spanish that says it replaces another one.
    s = snap()
    r, c = decision("ADR-0101", {"C1": "Otra cosa."})
    s.records["ADR-0101"], s.bodies["ADR-0101"] = r, c + "\nEsta decisión sustituye a ADR-0065.\n"
    assert ("ADR-0101", "ADR-0065") in [(i["record"], i["target"]) for i in undeclared(s)]


def _with_approval(s):
    appr = s.records["ADR-0077"]["events"][1]["approval"]
    appr["actor"] = "human:PER-A"
    appr["proof"] = {"mechanism": "declared", "quote": "I accept ADR-0077", "authenticated": False}
    return s


def _envelope(op, result, warnings=()):
    return {
        "result": {"state": "completed", **result},
        "warnings": list(warnings),
        "valid_at": T,
        "known_until": T,
        "coverage": {"truncated": False},
    }


def test_plain_says_the_rule_who_approved_it_and_whether_it_is_in_force_without_ids():
    s = _with_approval(snap())
    res = query(s, ["ADR-0077"], valid_at=T, known_until=T)
    text = present("query", _envelope("query", res), s)
    assert "[APPROVED] «Graphify over the working tree»" in text
    assert "In force in full on 20 Nov 2026" in text and "git grep closes the impact" in text
    assert "Approved by David Palazón on 20 Nov 2026" not in text  # the date is the approval's, not the query's
    assert "Approved by David Palazón on 10 Nov 2026, in these words: «I accept ADR-0077»" in text
    assert "declared approval, not authenticated" in text
    assert "PER-A" not in text and "(ADR-0077)" not in text


def test_plain_with_ids_shows_them_and_the_proposed_is_distinguished():
    s = _with_approval(snap())
    res = query(s, ["ADR-0077", "FACT-CRA"], valid_at=T, known_until=T)
    text = present("query", _envelope("query", res), s, with_ids=True)
    assert "«Graphify over the working tree» (ADR-0077)" in text and "(PER-A)" in text
    assert "[PROPOSED FACT: not accepted] «First pass of the CRA» (FACT-CRA)" in text


def test_plain_of_a_search_marks_the_candidates_and_warns_about_p04():
    s = snap()
    res = search(s, "MailConfig mail", valid_at=T, known_until=T)
    text = present("search", _envelope("search", res), s)
    assert text.count("[CANDIDATE from search, unconfirmed]") == len(res["candidates"]) >= 2
    assert "says it replaces or repeals it, at least in part, without declaring it" in text


def test_cli_search_requires_text_and_returns_the_envelope(tmp_path, capsys):
    folder = tmp_path / "kb"
    folder.mkdir()
    for ident in ("ADR-0065", "ADR-0077"):
        r, c = snap().records[ident], snap().bodies[ident]
        (folder / f"{ident}.md").write_text(serialize(r, c), encoding="utf-8")
    base = ["search", str(tmp_path), "--folder", "kb", "--valid-at", T, "--known-until", T]
    assert main(base) == 2
    assert "needs --query" in capsys.readouterr().out
    assert main([*base, "--query", "graphify"]) == 3  # read from disk, without a revision: partial
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["result"]["candidates"][0]["reference"] == "ADR-0077#C1"
    assert "semantic similarity: the search is lexical" in envelope["coverage"]["not_evaluated"]
    assert main([*base, "--query", "graphify", "--plain"]) == 3
    assert capsys.readouterr().out.startswith("As of 20 Nov 2026")
