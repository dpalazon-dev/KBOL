"""Dry-run migration of the legacy format: traceable, inventing neither history nor authority."""

from pathlib import Path

import pytest

from kbol.migration import inspect, inspect_folder

LEGACY = Path(__file__).parent / "legacy"


def read(name):
    return (LEGACY / f"{name}.txt").read_text(encoding="utf-8")


def report(name):
    return inspect(read(name), path=f"docs/{name}", revision="23fef059")


def test_keeps_the_original_and_fabricates_no_admitted_events():
    r = report("0063-one-working-copy-per-session.md")
    assert r["original"] == read("0063-one-working-copy-per-session.md")
    assert r["id"] == "ADR-0063" and r["type"] == "decision" and r["proposed_state"] == "accepted"
    ev = r["import_event"]
    assert ev["event_type"] == "import" and ev["recorded_at"] is None
    assert ev["valid_from"] == "2026-10-30" and ev["precision"] == "day"
    assert ev["provenance"] == {
        "path": "docs/0063-one-working-copy-per-session.md",
        "revision": "23fef059",
    }
    # The legacy approval is a statement, not an authenticated ratification.
    assert r["inherited_authority"] == {"text": "Owner, 30 Oct 2026", "classification": "insufficient"}
    assert r["requires_review"]


def test_partial_supersession_requires_individual_review():
    r = report("0001-catalog-by-independent-modules.md")
    assert r["proposed_state"] == "accepted"
    assert {
        "field": "amends",
        "candidates": ["ADR-0010"],
        "reason": "partial supersession in prose: anchors and scope undetermined",
    } in r["ambiguities"]
    assert r["requires_review"]


@pytest.mark.parametrize(
    "name,state,ambiguous",
    [
        ("QD-184.md", "resolved", False),
        ("QD-045.md", "resolved", True),  # factual closure without a recorded source
        ("QD-054.md", "open", True),  # "Under review" does not exist in the contract
        ("QD-112.md", "discarded", False),
        ("PL-001.md", "authorized", True),  # "In progress" does not exist for plans
        ("PL-001-H3.md", "proposed", True),  # Pending: the milestone's authorization is not recorded
        ("PL-001-H6.md", "completed", True),  # Done without accredited human acceptance
    ],
)
def test_state_mapping(name, state, ambiguous):
    r = report(name)
    assert r["proposed_state"] == state
    assert bool(r["ambiguities"]) is ambiguous, r["ambiguities"]


def test_closing_relation_is_proposed_as_a_candidate():
    r = report("QD-184.md")
    assert r["proposed_relations"]["resolved_by"] == ["ADR-0063"]


def test_non_records_are_left_out():
    r = inspect("---\ntype: Schema\ntitle: X\n---\n", path="docs/x/schema.md", revision="r")
    assert r["type"] is None and r["result"] == "out_of_scope"


def test_generated_indexes_are_views_out_of_scope():
    r = inspect("* [ADR-0001](0001.md)\n", path="docs/decisions/index.md", revision="r")
    assert r["result"] == "out_of_scope"


def test_an_unreadable_header_is_reported_without_crashing():
    r = inspect("---\na: [\n---\n", path="docs/x.md", revision="r")
    assert r["result"] == "failed" and r["code"] == "INVALID_SCHEMA"


def test_a_folder_produces_a_summary_without_writing(tmp_path):
    for p in LEGACY.glob("*.md.txt"):
        (tmp_path / p.name[: -len(".txt")]).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    res = inspect_folder(tmp_path, revision="23fef059")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert res["summary"]["total"] == 10
    assert res["summary"]["require_review"] >= 6


def test_the_legacy_fixtures_match_their_published_fingerprints():
    import hashlib

    listed = {}
    for line in (LEGACY / "README.txt").read_text(encoding="utf-8").splitlines():
        digest, sep, name = line.partition(" *")
        if sep and len(digest) == 64:
            listed[name] = digest
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in LEGACY.glob("*.md.txt")}
    assert listed == actual
