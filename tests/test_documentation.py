"""Policy as a test: the documentation matches the code."""

import json
import re
from pathlib import Path

import kbol
from kbol import cli

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
DESIGN_CHOICES = (ROOT / "docs" / "design-choices.md").read_text(encoding="utf-8")

# Policy elements the README may name, each with a field of the code that backs it.
POLICY_ELEMENTS = {"roles": "approval_rule", "people": "holds"}


def _section(text, title):
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"missing section «{title}»"
    return m.group(1)


def test_the_module_table_lists_the_package_modules():
    section = _section(README, "Modules")
    documented = set(re.findall(r"^\| `(\w+)` \|", section, re.M))
    actual = {p.stem for p in (ROOT / "kbol").glob("*.py") if p.stem != "__init__"}
    assert documented == actual, (
        f"undocumented: {sorted(actual - documented)}; documented but missing: {sorted(documented - actual)}"
    )


def test_the_usage_commands_are_the_enabled_ones():
    usage = _section(README, "Usage")
    documented = set(re.findall(r"^uv run kbol (\w+)", usage, re.M))
    assert documented == set(cli.ENABLED)


def test_the_disabled_commands_are_the_ones_the_readme_names():
    sentence = re.search(r"^(.*?) returns? `blocked` in the CLI", _section(README, "Limitations"), re.M)
    assert sentence, "missing the sentence about the operations that return `blocked`"
    assert set(re.findall(r"`(\w+)`", sentence.group(1))) == set(cli.NOT_ENABLED)


# A cited path is text between backticks that starts with a folder of this repository, without template markers
# (`<`, `*`, `…`). A path with another origin (`~/`, `.kbol/`, `<folder>/…`) is not checked.
PATH = re.compile(r"`((?:kbol|docs|tools|tests)/[^`\s<>*…]*)`")


def _cited_paths(text):
    return set(PATH.findall(text))


def test_cited_paths_exist():
    missing = []
    for name, text in [("README.md", README), ("docs/design-choices.md", DESIGN_CHOICES)]:
        missing += [f"{name}: {p}" for p in sorted(_cited_paths(text)) if not (ROOT / p).exists()]
    assert not missing, f"cited paths that do not exist: {missing}"


def test_the_path_rule_ignores_what_is_not_from_this_repository():
    text = "`~/.kbol/x`, `<folder>/_requests/<op>.json`, `.kbol/handoffs/`, `docs/*.md` and `kbol/vectors/digest.json`"
    assert _cited_paths(text) == {"kbol/vectors/digest.json"}


def test_the_project_version_is_the_package_version():
    m = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert m and m.group(1) == kbol.__version__


def test_the_reference_catalog_is_consistent():
    catalog = json.loads((ROOT / "docs" / "reference" / "catalog.json").read_text(encoding="utf-8"))
    names = [e["name"] for e in catalog]
    assert len(names) == len(set(names)), "repeated names in the catalog"
    for e in catalog:
        assert set(e) == {"name", "version", "what_it_is", "origin", "consumed_by"}, e["name"]
        assert e["consumed_by"], f"{e['name']}: nobody consumes it"
        missing = [p for p in e["consumed_by"] if not (ROOT / p).exists()]
        assert not missing, f"{e['name']}: paths that do not exist: {missing}"


def test_the_readme_policy_only_names_what_exists_in_the_code():
    m = re.search(r"policy \(([^)]*)\)", README)
    assert m, "missing the description of an installation's policy"
    elements = [e.strip() for e in re.split(r",| and ", m.group(1)) if e.strip()]
    code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "kbol").glob("*.py"))
    unbacked = [e for e in elements if e not in POLICY_ELEMENTS or POLICY_ELEMENTS[e] not in code]
    assert not unbacked, f"the README names in the policy what the code does not have: {unbacked}"
