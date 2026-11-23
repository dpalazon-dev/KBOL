"""Links, fragments and anchors of the Markdown documents (`kbol links`)."""

import json
import subprocess

import pytest

from kbol import links as en
from kbol.cli import main

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]

GUIDE = "\n".join(
    [
        "---",
        "title: Guide",
        "description: x",
        "---",
        "",
        "# Test guide",
        "",
        '<a id="integration-gate"></a>',
        "## How it integrates (step 1)",
        "",
        "## Notes",
        "## Notes",
        "",
    ]
)


def review(docs, extra=(), debt=frozenset()):
    """Result of an in-memory tree: its documents and the paths in `extra` exist."""
    return en.review(docs, set(docs) | set(extra), docs.get, set(debt))


def messages(docs, **kw):
    return [(e["path"], e["line"], e["message"]) for e in review(docs, **kw)["errors"]]


# ── Anchors ─────────────────────────────────────────────────────────────────


def test_github_style_heading_anchors_and_explicit_ones():
    anchors, repeated = en.anchors(GUIDE)
    assert {"test-guide", "how-it-integrates-step-1", "notes", "notes-1", "integration-gate"} <= anchors
    assert repeated == []


def test_the_yaml_header_creates_no_headings():
    anchors, _ = en.anchors(GUIDE)
    assert not any("title" in a or "description" in a for a in anchors)


def test_heading_with_code_and_link():
    anchors, _ = en.anchors("## Use of `kbol validate` and [KBOL](x.md)\n")
    assert "use-of-kbol-validate-and-kbol" in anchors


def test_a_repeated_explicit_anchor_is_reported():
    _, repeated = en.anchors('<a id="x"></a>\n\ntext\n\n<a id="x"></a>\n')
    assert repeated == [(5, "x")]


def test_id_and_name_in_the_same_tag_are_one_anchor():
    anchors, repeated = en.anchors('<a name="x" id="x"></a>\n')
    assert "x" in anchors and repeated == []


def test_only_id_and_the_name_of_a_are_anchors():
    anchors, _ = en.anchors('<div data-id="foo"></div>\n\n<input name="bar">\n\n<span id="baz"></span>\n')
    assert "foo" not in anchors and "bar" not in anchors and "baz" in anchors


def test_the_mark_of_a_clause_is_an_anchor():
    anchors, repeated = en.anchors('<clause id="C1">\nOn Tuesdays.\n</clause>\n\n<clause id="C2">\nNo.\n</clause>\n')
    assert {"C1", "C2"} <= anchors and repeated == []


def test_slug_keeps_marks_and_removes_symbols():
    assert en.slug("⚠️ Warning") == "️-warning"  # the emoji goes; its variation selector (a mark) stays
    # Non-English headings keep their letters, as GitHub does: deliberate non-ASCII test data.
    assert en.slug("Qué es (y qué no)") == "qué-es-y-qué-no"
    assert en.slug("snake_case and kebab-case") == "snake_case-and-kebab-case"


# ── Links ───────────────────────────────────────────────────────────────────


def test_links_ignore_blocks_and_inline_code():
    text = "\n".join(
        [
            "[a](a.md) and `[b](b.md)`",
            "```markdown",
            "[c](c.md)",
            "```",
            "    [d](d.md)",
            "",
            "![image](img.png) and [e][ref]",
            "",
            "[ref]: e.md",
        ]
    )
    assert en.links(text) == [(1, "a.md"), (7, "img.png"), (7, "e.md")]


def test_a_link_in_a_multiline_paragraph_gives_its_line():
    assert en.links("First line\nsecond with [x](x.md)\n") == [(2, "x.md")]


def test_the_line_is_not_confused_with_similar_text_or_a_repeated_link():
    assert en.links("see data.md and\n[a](a.md)\n") == [(2, "a.md")]
    assert en.links("[x](a.md) and\n[y](a.md)\n") == [(1, "a.md"), (2, "a.md")]


def test_a_valid_link_with_fragment_gives_no_error():
    docs = {
        "docs/guide.md": GUIDE,
        "docs/a.md": "[g](guide.md#integration-gate), [t](guide.md#how-it-integrates-step-1), [n](guide.md#notes-1)\n",
    }
    res = review(docs)
    assert res["errors"] == [] and res["links"] == 3


def test_missing_fragment():
    docs = {"docs/guide.md": GUIDE, "docs/a.md": "See [g](guide.md#does-not-exist).\n"}
    assert messages(docs) == [
        ("docs/a.md", 1, "«guide.md#does-not-exist»: docs/guide.md has no anchor «does-not-exist»")
    ]


def test_fragment_in_the_same_document():
    docs = {"docs/a.md": "# A\n\n## One\n\n[good](#one) and [bad](#two)\n"}
    assert messages(docs) == [("docs/a.md", 5, "«#two»: docs/a.md has no anchor «two»")]


def test_fragment_with_other_capitalization():
    docs = {"docs/guide.md": GUIDE, "docs/a.md": "[g](guide.md#Notes)\n"}
    assert [m[2] for m in messages(docs)] == ["«guide.md#Notes»: docs/guide.md has no anchor «Notes»"]


def test_the_fragment_of_a_file_that_is_not_markdown_is_not_checked():
    docs = {"docs/a.md": "[code](../src/x.py#L10)\n"}
    assert messages(docs, extra=("src/x.py",)) == []


def test_missing_path_and_path_with_other_capitalization():
    docs = {"docs/a.md": "[x](no.md) [y](Guide.md)\n", "docs/guide.md": "# G\n"}
    assert messages(docs) == [
        ("docs/a.md", 1, "«no.md»: docs/no.md does not exist"),
        ("docs/a.md", 1, "«Guide.md»: docs/Guide.md does not exist; it is spelled docs/guide.md"),
    ]


def test_links_with_title_by_reference_and_with_spaces():
    docs = {"docs/m/a.md": '[t](no.md "Title") [r][ref] [s](<no with space.md>) [d](docs/b.md)\n\n[ref]: no-ref.md\n'}
    assert [m[2] for m in messages(docs, extra=("docs/b.md",))] == [
        "«no.md»: docs/m/no.md does not exist",
        "«no-ref.md»: docs/m/no-ref.md does not exist",
        "«no with space.md»: docs/m/no with space.md does not exist",
        "«docs/b.md»: docs/m/docs/b.md does not exist",
    ]


def test_link_to_a_folder_to_the_root_external_and_outside_the_root():
    docs = {
        "docs/a.md": "[c](manual/) [r](../) [w](https://x.org/a#b) [m](mailto:a@b.c) [f](../../outside.md)\n",
        "README.md": "[repo](.)\n",
    }
    assert messages(docs, extra=("docs/manual/r.md",)) == []


def test_path_from_the_root_and_with_query():
    docs = {"docs/a.md": "[x](/docs/b.md) [y](b.md?plain=1) [z](/no.md)\n", "docs/b.md": "# B\n"}
    assert [m[2] for m in messages(docs)] == ["«/no.md»: no.md does not exist"]


def test_local_absolute_path():
    docs = {"docs/a.md": "[x](C:/Users/someone/x.md)\n"}
    assert messages(docs) == [
        ("docs/a.md", 1, "«C:/Users/someone/x.md»: local absolute path; use a relative path")
    ]


def test_an_encoded_path_resolves():
    docs = {"docs/a.md": "[x](my%20guide.md)\n", "docs/my guide.md": "# M\n"}
    assert messages(docs) == []


def test_a_repeated_explicit_anchor_is_an_error():
    docs = {"docs/a.md": '<a id="x"></a>\n\n<a id="x"></a>\n'}
    assert messages(docs) == [("docs/a.md", 3, "the explicit anchor «x» is repeated")]


def test_declared_debt_is_not_an_error_and_the_used_one_is_known():
    docs = {"docs/a.md": "[x](no.md)\n"}
    res = review(docs, debt={("docs/a.md", "no.md"), ("docs/b.md", "z.md")})
    assert res["errors"] == [] and res["debt_used"] == {("docs/a.md", "no.md")}


# ── Installation configuration ──────────────────────────────────────────────


def test_empty_and_declared_configuration():
    assert en.configuration({}) == ([], set())
    installation = {
        "project": "p",
        "links": {"exclude": ["docs/originals/", ".\\copies"], "debt": [{"document": "a.md", "target": "../x.md"}]},
    }
    assert en.configuration(installation) == (["docs/originals", "copies"], {("a.md", "../x.md")})


@pytest.mark.parametrize(
    "declared",
    [
        [],
        {"other": 1},
        {"exclude": "docs"},
        {"exclude": [""]},
        {"exclude": ["."]},
        {"debt": [{"document": "a.md"}]},
        {"debt": [{"document": "a.md", "target": "x.md", "reason": "m"}]},
        {"debt": [{"document": "a.md", "target": 3}]},
    ],
)
def test_malformed_configuration(declared):
    with pytest.raises(ValueError):
        en.configuration({"links": declared})


# ── On a repository ─────────────────────────────────────────────────────────


def write(root, path, text):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    write(root, ".gitignore", "ignored/\n")
    write(root, "README.md", "# Project\n\n[guide](docs/guide.md#notes) and [code](src/x.py)\n")
    write(root, "docs/guide.md", "# Guide\n\n## Notes\n\n[up](../README.md#project)\n")
    write(root, "src/x.py", "x = 1\n")
    subprocess.run(["git", "-C", str(root), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), *GIT, "commit", "-q", "-m", "base"], check=True)
    return root


def kb(capsys, *args):
    code = main(list(args))
    return code, json.loads(capsys.readouterr().out)


def test_a_repository_without_broken_links(repo):
    res = en.check(repo)
    assert res["documents"] == 2 and res["links"] == 3 and res["errors"] == [] and res["unreadable"] == []


def test_new_unignored_files_exist_and_ignored_ones_do_not(repo):
    write(repo, "docs/new.md", "[a](guide.md) [b](../ignored/x.md)\n")
    write(repo, "ignored/x.md", "[broken](no.md)\n")
    res = en.check(repo)
    assert res["documents"] == 3
    assert [(e["path"], e["target"]) for e in res["errors"]] == [("docs/new.md", "../ignored/x.md")]


def test_a_file_deleted_from_disk_no_longer_exists(repo):
    (repo / "src" / "x.py").unlink()
    assert [e["target"] for e in en.check(repo)["errors"]] == ["src/x.py"]


def test_only_the_requested_folders_are_reviewed_but_targets_come_from_the_whole_root(repo):
    write(repo, "README.md", "# Project\n\n[broken](no.md)\n")
    res = en.check(repo, ["docs"])
    assert res["documents"] == 1 and res["errors"] == []  # docs/guide.md links README.md, outside the folder
    with pytest.raises(FileNotFoundError):
        en.check(repo, ["does-not-exist"])


def test_what_is_excluded_is_not_reviewed_but_can_be_linked(repo):
    write(repo, "copies/foreign.md", "# Foreign\n\n[broken](where-it-was.md)\n")
    write(repo, "docs/quote.md", "[copy](../copies/foreign.md#foreign)\n")
    assert [e["path"] for e in en.check(repo)["errors"]] == ["copies/foreign.md"]
    res = en.check(repo, exclude=["copies"])
    assert res["errors"] == [] and res["documents"] == 3


def test_debt_that_no_longer_fails_is_left_over(repo):
    write(repo, "docs/old.md", "[x](no.md)\n")
    debt = {("docs/old.md", "no.md"), ("docs/guide.md", "../README.md#project")}
    res = en.check(repo, debt=debt)
    assert res["errors"] == []
    assert res["debt_used"] == [{"document": "docs/old.md", "target": "no.md"}]
    assert res["debt_left"] == [{"document": "docs/guide.md", "target": "../README.md#project"}]


def test_a_document_that_is_not_utf8_is_not_taken_as_reviewed(repo):
    write(repo, "docs/latin.md", "[x](no.md) caf\xe9\n".encode("latin-1"))
    res = en.check(repo)
    assert res["unreadable"] == ["docs/latin.md"] and res["errors"] == []


def test_outside_git_it_is_unknown_what_exists(tmp_path):
    (tmp_path / "a.md").write_text("[x](b.md)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="is not a git working tree"):
        en.check(tmp_path)


def test_cli_completed_with_the_envelope(repo, capsys):
    code, out = kb(capsys, "links", str(repo))
    assert code == 0 and out["operation"] == "links" and out["result"]["state"] == "completed", out
    assert out["result"]["documents"] == 2 and out["result"]["links"] == 3
    assert "external links" in out["coverage"]["not_evaluated"]


def test_cli_a_broken_link_is_failed(repo, capsys):
    write(repo, "docs/guide.md", "# Guide\n\n[x](no.md)\n")
    code, out = kb(capsys, "links", str(repo), "--folder", "docs")
    assert code == 1 and out["result"]["state"] == "failed", out
    assert out["result"]["code"] == "MISSING_REFERENCE"
    assert out["result"]["errors"] == [
        {"path": "docs/guide.md", "line": 3, "target": "no.md", "message": "«no.md»: docs/no.md does not exist"}
    ]


def test_cli_debt_and_exclusions_come_from_the_installation(repo, tmp_path, capsys):
    write(repo, "docs/old.md", "[x](no.md)\n")
    write(repo, "copies/foreign.md", "[broken](where-it-was.md)\n")
    installation = tmp_path / "kbol.json"
    declared = {
        "exclude": ["copies"],
        "debt": [{"document": "docs/old.md", "target": "no.md"}, {"document": "README.md", "target": "src/x.py"}],
    }
    installation.write_text(json.dumps({"project": "p", "links": declared}), encoding="utf-8")
    code, out = kb(capsys, "links", str(repo), "--installation", str(installation))
    assert code == 0 and out["result"]["state"] == "completed", out
    assert out["result"]["debt_used"] == [{"document": "docs/old.md", "target": "no.md"}]
    assert any("README.md" in a and "no longer fails" in a for a in out["warnings"])


def test_cli_a_malformed_installation_reviews_nothing(repo, tmp_path, capsys):
    installation = tmp_path / "kbol.json"
    installation.write_text(json.dumps({"links": {"debt": "all"}}), encoding="utf-8")
    code, out = kb(capsys, "links", str(repo), "--installation", str(installation))
    assert code == 1 and out["result"]["code"] == "INVALID_SCHEMA", out


def test_cli_an_unreadable_document_is_partial(repo, capsys):
    write(repo, "docs/latin.md", "caf\xe9\n".encode("latin-1"))
    code, out = kb(capsys, "links", str(repo))
    assert code == 3 and out["result"]["state"] == "partial", out
    assert any("docs/latin.md" in a for a in out["warnings"])


def test_cli_outside_git_or_without_the_folder_is_failed(tmp_path, repo, capsys):
    code, out = kb(capsys, "links", str(tmp_path))
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE", out
    code, out = kb(capsys, "links", str(repo), "--folder", "does-not-exist")
    assert code == 1 and out["result"]["code"] == "MISSING_REFERENCE", out
