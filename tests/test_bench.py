"""Minimum prior test bench of the contract, as a maintained test.

The contract (docs/reference/KB-DPP-implementation.md, "Minimum prior test bench") lists the cases the
system must resolve correctly. This file does not run those cases: the suite runs them. Here it is only
checked that each case of the contract has an owner in tests/bench/coverage.yaml: existing tests that
exercise it, a capability declared as not enabled, or a pending test that does not exist yet.
If the contract adds, removes or renames a case, the test fails and forces a decision.
"""

import ast
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "reference" / "KB-DPP-implementation.md"
COVERAGE = ROOT / "tests" / "bench" / "coverage.yaml"
KEYS = ("tests", "not_enabled", "pending")


def contract_cases() -> list[str]:
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "### Minimum prior test bench")
    cases, in_table = [], False
    for line in lines[start + 1 :]:
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "Case" or re.fullmatch(r"[-: ]+", cells[0]):
            in_table = True
            continue
        cases.append(cells[0])
    return cases


def coverage() -> dict:
    return yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))


def defined_tests(file: Path) -> set[str]:
    tree = ast.parse(file.read_text(encoding="utf-8"))
    return {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test_")
    }


def test_the_contract_has_the_table():
    assert len(contract_cases()) >= 1


def test_the_coverage_has_exactly_the_contract_cases():
    expected, has = contract_cases(), coverage()
    assert len(set(expected)) == len(expected), "repeated case in the contract"
    assert not set(expected) - set(has), f"contract cases not decided in coverage.yaml: {set(expected) - set(has)}"
    assert not set(has) - set(expected), f"coverage.yaml cases no longer in the contract: {set(has) - set(expected)}"


@pytest.mark.parametrize("case", sorted(coverage()))
def test_each_case_has_exactly_one_form_of_coverage(case):
    entry = coverage()[case]
    assert isinstance(entry, dict), f"{case}: the entry must be a mapping"
    present = [k for k in entry if k in KEYS]
    assert len(present) == 1 and len(entry) == 1, f"{case}: it must have only one of {KEYS}, it has {list(entry)}"
    key = present[0]
    if key == "tests":
        assert isinstance(entry[key], list) and entry[key], f"{case}: `tests` cannot be empty"
    else:
        assert isinstance(entry[key], str) and entry[key].strip(), f"{case}: `{key}` cannot be empty"


@pytest.mark.parametrize("case", sorted(coverage()))
def test_each_listed_test_exists(case):
    ids = coverage()[case].get("tests", [])
    for ident in ids:
        path, sep, name = ident.partition("::")
        assert sep and name, f"{case}: malformed id: {ident}"
        name = name.split("[", 1)[0]
        file = ROOT / path
        assert file.is_file(), f"{case}: the file {path} does not exist"
        assert name in defined_tests(file), f"{case}: {path} does not define {name}"


@pytest.mark.parametrize("case", sorted(coverage()))
def test_what_is_pending_does_not_stay_pending_once_its_file_exists(case):
    target = coverage()[case].get("pending")
    if target is None:
        return
    assert not (ROOT / target).is_file(), (
        f"{case}: {target} already exists. Replace `pending` with `tests` and the real ids in tests/bench/coverage.yaml"
    )
