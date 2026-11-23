# Changelog

Versions follow the form `MAJOR.MINOR.PATCH`. While KBOL is at 0.x, a minor version may break the CLI: every breaking or potentially breaking change has its note, with why, who is affected and how to migrate, in [docs/breaking-changes.md](docs/breaking-changes.md). This changelog summarises; that note is authoritative.

0.12.0 is the first version published in this repository. Earlier ones were developed in a private repository: their notes are kept as project history, but they have no tag here. Entries before 0.13.0 use the 0.13 names of commands, options and fields; [docs/glossary-es-en.md](docs/glossary-es-en.md) maps them to the Spanish names those versions used.

## 0.13.0 · unreleased

Everything in English. Breaking for any 0.12 installation: see the note in [docs/breaking-changes.md](docs/breaking-changes.md).

- The KB-DPP contract becomes version 1.0, in English, in `docs/reference/` (it was core 0.7 and implementation 0.8, in Spanish, in `docs/referencias/`).
- Record format in English: types, ID prefixes, states, fields, relations, events, body marks (`<clause>`, `<fact>`) and error codes.
- CLI in English: commands (`query`, `search`, `propose`, `bootstrap`…), options (`--folder`, `--valid-at`, `--plain`…), the output envelope and the messages, including the `--plain` output (`[APPROVED]`, `In force…`). Exit codes do not change.
- Installation file with English keys, `kbol.json` by default; local state and environment in English (`KBOL_STATE`, `.kbol/handoffs/`, `integrator.git`, `receipts/`).
- Code in English: module names (`kbol.query`, `kbol.integrate`…), identifiers and docstrings.
- Documentation in English: `docs/design-choices.md`, `docs/breaking-changes.md`, `docs/getting-started.md`, `CONTRIBUTING.md` and the GitHub templates. `README.es.md` is removed.
- `docs/glossary-es-en.md`: the single table that maps every 0.12 name to its 0.13 name.
- Skills in English; `incorporar-documento` is renamed `add-document`.
- `tools/di` in English; the local check is `tools/check.py`.
- Converting 0.12 records with `kbol migrate` is planned and not available yet.

Also in this version:

- Demo GIF in the README (`docs/demo.gif`), recorded from real output by `tools/demo_gif.py`.
- A quick start in a script, `examples/quickstart.sh`, which continuous integration runs end to end.
- Badges for continuous integration, version, license and Python in the README.

## 0.12.0 · 23 Nov 2026

First public version.

- `kbol search`: lexical search by text or alias, in memory, for when the ID is not known. Gives candidates with state, validity and snippet; by default only what is in force. It does not decide what is in force.
- `--plain` in `query`, `consolidate` and `search`: an answer in prose without IDs, with the label of each block (`[APPROVED]`, `[PROPOSED: …]`…); IDs with `--with-ids`.
- Warning `UNDECLARED_SUPERSESSION` in `query` and `consolidate`: a record says in prose that it replaces another without declaring it. Flags, does not block.
- `query` gives `inverse_relations`: which records supersede or amend the queried one.
- The `kbol` skill explains how to query what is in force with these commands.
- `kbol handoff`: the first path of `local_changes` no longer loses its first letter.
- The CLI imports `jsonschema`, `markdown_it` and `urllib.request` only when using them, which shortens start-up.
- README in English (`README.md`) and in Spanish (`README.es.md`), getting-started guide, `CONTRIBUTING.md`, issue and pull request templates, continuous integration with the local check without `tools/di`, and this changelog.
- `kbol --version`.
- No longer tied to the format of a particular project: the legacy format read when no other is declared is the default legacy format (`migration.DEFAULT`). The `tools/di` store, without `KBOL_REPOSITORY`, becomes `default`. Breaking for whoever imported the previous format constant or used the store without that variable.
- Apache-2.0 license (`LICENSE`, `NOTICE` and `license` in `pyproject.toml`).
- The records in the legacy test folder are invented.

## 0.11.0 · 16 Nov 2026 (no tag)

Hygiene of guarantees.

- `kbol drift --canonical-branch` flags in `commits_outside_flow` the commits of the canonical branch that change records without going through the gate. Potentially breaking.
- A test counts in `kbol/` the git commands that move references, so that the gate stays single.
- Skills move to `kbol/skills/`, inside the package, and `kbol export_skills DEST` writes them with the installed version.
- The local check runs the tests of `tools/di` (except with the quick or no-di options) and `drift` against `main`.
- The README is checked against the code and the records by a test.

## 0.10.0 · 12 Nov 2026

- A `lines-v1` citation with `representation_id` resolves against the text representation of a document without pages (Word, spreadsheet, PowerPoint, HTML). Potentially breaking.
- `kbol integrity` compares the `sha256` of each source with its bytes. Breaking: it stops returning `blocked`.
- `kbol links` checks internal links and anchors of the repository's Markdown.
- `kbol` skill for task continuity in any repository with KBOL.
- `tools/di` reads Word, spreadsheets, PowerPoint and HTML.

## 0.9.0 · 12 Nov 2026

- `kbol session` (`start`, `stop`, `commit`), commands for an installation's hooks.
- `kbol propose`, integration operator: dry run by default, integrates with `--until integrate` and pushes without forcing with `--until push`.

## 0.8.0 · 11 Nov 2026

- Legacy format configurable per installation (`legacy_format`). Potentially breaking: `--installation` is no longer ignored in queries and in `migrate`.

## 0.7.0 · 10 Nov 2026

- `kbol vocabulary`: entity classes declared by decisions in force; the gate blocks activating an entity of a class that is not in force. Potentially breaking.

## 0.6.0 · 10 Nov 2026

- `kbol approval_package`: read-only approval package with the digests the gate uses.

## 0.5.0 · 10 Nov 2026

- `kbol support`: whether the supports of each record are in force at a cut-off.
- `query` reports the evidence, and dependencies handle the undecidable successor. Breaking.

## 0.4.1 · 10 Nov 2026

- An operation that examines nothing ends `partial` (code 3), not `completed`. Breaking.
- Single local check and policy tests.

## 0.4.0 · 10 Nov 2026

- Locators with a profile (`lines-v1`, `pdf-v1`, `norma-v1`) and citation resolver, `kbol citations`.
- `tools/di`, from the Document Intelligence pilot.

## 0.3.2 · 6 Nov 2026

- Context, impact and drift also read legacy records.

## 0.3.1 · 6 Nov 2026

- The import guard accepts the interpreted values of the legacy record, with YAML escapes.

## 0.3.0 · 6 Nov 2026

- Task handoff (`kbol handoff`) and context package (`kbol context`).
- `kbol verify`: runs the checks the installation declares and records them in the handoff.
- Root of trust (`kbol bootstrap`) and `impact` as a read-only query.
- Declared governance for the first installation: verifier of declared approvals (unauthenticated quote), declared bootstrap and integration from the CLI, approval of decisive changes only, guarded import of legacy records, fingerprints and `kbol query` by ID or anchor.

## 0.2.0 · 4 Nov 2026

- KBOL moves to its own repository with the KB-DPP core: schema, events, rebuilt state, digest, consolidation at two cut-offs, dependencies, mutability, authority, local integration with receipts, impact and dry-run migration.
