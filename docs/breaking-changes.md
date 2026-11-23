---
type: Specification
title: KBOL breaking changes
description: "Notes on the schema or CLI behaviour changes of KBOL that can break whoever consumes them: why they are made, who is affected, what happens and how to migrate."
class: fixed
state: Draft
status: draft
---

# KBOL breaking changes

Every change to the schema or to the CLI behaviour falls into one of three classes:

- **Safe.** Whoever consumes KBOL notices nothing: no output that depends on it changes. No note.
- **Potentially breaking.** It changes something a consumer may be reading (a new field, a new warning, a result that did not appear before) but does not break whoever ignores it with care. Has a note.
- **Breaking.** A consumer that was correct with the previous version may stop being so (an exit code, a field removed or with another meaning). Has a note.

Every note follows the same template:

- **Why.** The reason for the change.
- **Who is affected.** Which consumers notice it.
- **What happens.** The previous behaviour and the new one.
- **How to migrate.** What the consumer must change.

Notes go from the most recent to the oldest. Notes for versions before 0.13 are written with the 0.13 names of commands, options, fields and codes; [the glossary](glossary-es-en.md) maps each one to the Spanish name those versions used.

## 0.13.0: Everything in English

Class: breaking.

**Why.** Until 0.12, the KB-DPP contract, the record format, the CLI, the messages and the code of KBOL were written in Spanish, while the project is public and meant for anyone. A tool whose commands, fields and errors are words most of its possible users do not read is harder to adopt, to review and to integrate with agents. KB-DPP 1.0 moves the contract to English, and KBOL 0.13 follows it entirely, in one release, so that there is never a mixed format to support.

**Who is affected.** Any 0.12 installation: its records, its installation file, the scripts and hooks that call `kbol`, and whoever reads the JSON envelope or the exit messages. Also whoever imports KBOL modules as a library, and whoever exported the `incorporar-documento` skill.

**What happens.**

| Where | 0.12 | 0.13 |
|---|---|---|
| Contract | KB-DPP core 0.7 and implementation 0.8, in Spanish (`docs/referencias/`) | KB-DPP 1.0, in English, in `docs/reference/` |
| Record format | Spanish types, states, fields, relations, events and body marks (`type: rol`, `estado: propuesta`, `<clausula id="C1">`) | English (`type: role`, `state: proposed`, `<clause id="C1">`); some ID prefixes change (`ROL` → `ROLE`, `F` → `SRC`, `HE` → `FACT`…) |
| Installation file | Spanish keys (`carpeta_registros`, `rama_canonica`, `integracion`…) | English keys (`records_folder`, `canonical_branch`, `integration`…), `kbol.json` by default |
| CLI | Spanish commands and options (`kbol consultar --carpeta kb --valido-en …`) | English (`kbol query --folder kb --valid-at …`) |
| Envelope and codes | `operacion`, `resultado`, `advertencias`…; `ESQUEMA_INVALIDO`, `APROBACION_CADUCADA`… | `operation`, `result`, `warnings`…; `INVALID_SCHEMA`, `STALE_APPROVAL`… Exit codes do not change |
| Messages and `--plain` output | Spanish (`[APROBADA]`, `Rige entera…`) | English (`[APPROVED]`, `In force in full…`) |
| Code | Spanish module names (`kbol.consultar`, `kbol.integrar`…) | English (`kbol.query`, `kbol.integrate`…) |
| Local state and environment | `KBOL_ESTADO`, `.kbol/relevos/`, `integrador.git`, `recibos/`, `_huellas.json` | `KBOL_STATE`, `.kbol/handoffs/`, `integrator.git`, `receipts/`, `_fingerprints.json` |
| Skills | `kbol` and `incorporar-documento`, in Spanish | `kbol` and `add-document`, in English |
| Documentation | `README.md` in English plus `README.es.md`; the rest in Spanish | Everything in English; `README.es.md` is removed |

Records in the 0.12 format are not read as canonical records by 0.13: they fail validation and leave a load partial or blocked.

**How to migrate.** [`docs/glossary-es-en.md`](glossary-es-en.md) is the single table of the renaming: every type, prefix, state, field, relation, event, code, command, option, installation key, path and module, old name next to new. Rename your installation file keys, your scripts and hooks, and the paths of your local state with it. Automatic conversion of existing records with `kbol migrate` is planned but **not available yet** in 0.13: until it ships, an installation with records in the 0.12 format either stays on 0.12 or converts its records by hand following the glossary, which rewrites history fields and therefore changes their digests and fingerprints. Re-export the skills with `kbol export_skills` and remove the old `incorporar-documento` copy.

## 0.12.0: `search`, undeclared supersession warning and `--plain`

Class: potentially breaking.

- **Why.** Without the ID of a record there was no way to reach it, and a decision partially replaced only in prose came out fully in force without a warning.
- **Who is affected.** Whoever reads the warnings of `query` and `consolidate`, or the fields of `query`; whoever validates the list of CLI operations.
- **What happens.** New command `search` (`--query`, `--include proposals not_in_force`, `--limit`): candidates by text, in memory and without an index, with their ID, anchor, state, validity and snippet; by default only what is in force. `query` and `consolidate` add the warning `UNDECLARED_SUPERSESSION` when a record says it replaces or repeals the queried one (or the queried one another) without declaring it in `amends` or `supersedes`; it changes neither validity nor the exit code. `query` adds `inverse_relations` (`superseded_by`, `amended_by`) and `supersession_warnings`. `--plain` presents `query`, `consolidate` and `search` in prose, without IDs except with `--with-ids`; the output is no longer JSON.
- **How to migrate.** Nothing, except for whoever treats every warning as a failure: the new one is a lexical hint that does not block.

## 0.12.0: approvals with their detail in `query` and `consolidate` with an anchor

Class: potentially breaking.

**Why.** Two bugs in what KBOL already did. "Who approved X?" did not come out of `query`, which only gave the ID of the approval even though the record keeps the person, the instant and the quote. And `consolidate --ids ID#anchor` reported the clause as missing.

**Who is affected.** Whoever reads `result.results[].authority` of `query` as a closed list of fields, and whoever calls `consolidate` with anchors.

**What happens.**

| Where | Before | Now |
|---|---|---|
| `query`, `authority` | `ratifications` and `declared` as a list of IDs | Also `approvals`: for each ratification in force, `approval_id`, `actor`, `roles`, `approved_at`, `mechanism`, `quote` and `authenticated`; what the proof does not carry is `null`. `checked: false` remains |
| `consolidate --ids ID#anchor` | The reference in `missing` and the result `partial` | Only that clause, with its chain; the `validity` is that of the decision. An anchor the decision does not have stays in `missing` |

**How to migrate.** Whoever validates `authority` as a closed list must admit `approvals`. Whoever counted on `consolidate` rejecting anchors has nothing else to do: the result with an anchor is a subset of that of the whole decision.

## 0.11.0: commits outside the flow in `drift`, `kbol export_skills` and `tools/di` in the local check

Class: potentially breaking in `drift`; safe for the rest.

**Why.** Hygiene of guarantees. The single gate depended on discipline: now a test counts in `kbol/` the git commands that move references, and `drift` flags the commits of the canonical branch that change records without going through the gate. Skills become package data, so that every installation receives the one for its version. The local check includes the tests of `tools/di`. The detail is in the design choices, "Fingerprints and drift", "Packaged skills" and "Zero examined and local check".

**Who is affected.** Whoever reads the result of `kbol drift` with `--canonical-branch`: the field `commits_outside_flow` appears and, if there is any, new warnings; the exit code does not change. Whoever edits the KBOL skills: the source is now in `kbol/skills/` and `.claude/skills/` is an export. Whoever runs the local check without `--quick`: it takes longer, because it syncs and runs the `tools/di` project.

**What happens.**

| Where | Before | Now |
|---|---|---|
| `drift --canonical-branch` | Only records edited by hand | Also `commits_outside_flow`, with a warning per commit; `coverage.not_evaluated` says which part of the history was not looked at |
| `drift` without `--canonical-branch` | — | `not_evaluated` includes "commits of the canonical branch" |
| Skills `kbol` and `add-document` | Only in `.claude/skills/` of this repository | In `kbol/skills/`, inside the wheel; `kbol export_skills DEST` writes them with the version |
| Local check (`tools/check.py`) | Without `tools/di`; `drift` without a branch | With the tests of `tools/di` (not with `--quick` or `--no-di`); `drift --canonical-branch main`, which fails with commits outside the flow |

**How to migrate.** Whoever reads `drift` as a closed list of fields must admit `commits_outside_flow`. An installation that copied the skill by hand can replace it with `kbol export_skills .claude/skills`; if its copy does not carry the export mark, the command refuses to overwrite it and it has to be deleted first.

## 0.10.0: citations by lines against the representation, `kbol integrity`, `kbol links` and the `kbol` skill

Class: breaking in `integrity`, which stops returning `blocked`; potentially breaking in citations; safe for the rest.

**Why.** Three pieces of work left outside `main` are recovered in a single version. A Word document, a spreadsheet or an HTML page have no physical pages and cannot be cited with `pdf-v1`: their common representation is a derived Markdown (from Docling or MarkItDown) and the natural thing is to cite it by lines, but `lines-v1` was only resolved against the original, which in these formats is not text. The contract's `integrity` operation was reserved and not enabled; it is enabled in part: it checks, it does not remember. `kbol links` is a new command for the links of any Markdown in the repository, and the `kbol` skill (`.claude/skills/kbol`) brings task continuity and care of the knowledge base to any repository that has KBOL installed. The detail is in the design choices, "Source integrity" and "Documentation links".

**Who is affected.** Whoever writes or reads `lines-v1` citations that carry `representation_id`. Whoever called `kbol integrity` and counted on `blocked` (2). `links` and the skill are new and change no previous output.

**What happens.**

| Where | Before | Now |
|---|---|---|
| `lines-v1` citation without `representation_id` | Lines of the original | Same |
| `lines-v1` citation with `representation_id` | Lines of the original; `representation_id` was ignored | Lines of the representation, which must be text (`format: text/…`) and derive from the original through `derived_from`, directly or in a chain; `broken` otherwise |
| Citation by lines with the original missing from the store | — | `not_checkable` with "representation conforming; original not available", as for a PDF |
| `kbol integrity` | `blocked` (2): operation not enabled | Compares the `sha256` of each source with the bytes at its `location` (`store:sha256/…` with `--store`, `git:<sha>:<path>` or a path from the root). `failed` (1, `INTEGRITY_BROKEN`) if any is altered or missing; `partial` (3, `INTEGRITY_UNCHECKED`) if any was left unchecked, and also with no source at all or with records that did not load; `blocked` (2) only with an inconsistent base |
| `kbol links` | Did not exist | Checks internal paths, fragments and anchors of the `.md` files; `failed` (1, `MISSING_REFERENCE`) with any broken link, `partial` (3) if it checked no document or one is not UTF-8. The installation declares in `links` what is not checked (`exclude`) and the debt that does not block (`debt`) |
| Disabled operations | `ingest` and `integrity` | Only `ingest` |

**How to migrate.** Nothing for existing citations. To cite a document without pages: register the original, the Markdown derivation with `derived_from` pointing to it (or to the intermediate derivation) and `format: text/markdown`, and cite `lines-v1:<start>-<end>` with `representation_id` and the literal quote in `context`. Whoever treats code 2 of `integrity` as "not available" must now read the state: 1 is a broken source and 3, an unchecked one. `integrity` does not store the last check and queries do not use it: `available_with_integrity` still fails closed.

## 0.8.0: legacy format configurable per installation

Class: potentially breaking.

**Why.** Compatible reading had a single legacy format hard-wired and reported as invalid the records of projects that differ only in their IDs and in some state words. An installation can now declare its legacy format (design choices, "Legacy format of another project").

**Who is affected.** Whoever passes `--installation` to a query or to `migrate`, whoever reads `proposed_relations` of a legacy question that carries the `resolved_by` field, and whoever calls `snapshot.load` or `migration.inspect` as a library. Without `legacy_format`, the result is the same as with 0.7.0.

**What happens.**

| Where | Before | Now |
|---|---|---|
| `--installation` in `consolidate`, `ready`, `query`, `support`, `vocabulary` and `migrate` | Ignored | Its `legacy_format` is read; if missing, the default format. Malformed or unreadable, `failed` (1, `INVALID_SCHEMA` or `MISSING_REFERENCE`) |
| `context` | Read legacy records with the default format | With the one the installation declares; a malformed one makes it fail like any malformed installation |
| Legacy question "Resolved" with a `resolved_by` field | The candidate came only from the state text | It comes first from the field and then from the text |
| `snapshot.load`, `migration.inspect` and `inspect_folder` | No format parameter | Optional `format` parameter (`migration.format_of`); without it, the default format |
| `snapshot.RECORD_NAME` | In `snapshot` | In `migration`, as part of the default format |

**How to migrate.** Nothing, unless `--installation` was passed to a query with an installation that is not valid JSON, or `RECORD_NAME` was imported from `snapshot`.

## 0.7.0: domain vocabulary

Class: potentially breaking.

**Why.** The class of an entity was free text and no module checked it: an invented term, or one written in two ways, was only discovered late. Decisions can now declare the domain terms with `defines`, and the gate does not let an entity whose class is not in force become `active` (design choices, "Domain vocabulary").

**Who is affected.** An installation that declares vocabulary, whoever reads receipts and approval packages, whoever reads the relations of `query`, and whoever calls `integrate.final_tree` as a library. An installation with no `defines` in force behaves as before: open world.

**What happens.**

| Where | Before | Now |
|---|---|---|
| Schema of a decision | `defines` is an undeclared field | Relation `defines`: list of `{clause, term, class, description, aliases?}` |
| `integrate`, effect that takes an entity to `active` | Integrates | With declared vocabulary, `blocked` (2, `INVALID_SCHEMA`) if its class is not in force at the start of validity of the effect or at integration |
| `integrate`, receipt | No vocabulary warnings | `warnings` reports the class and scope of the touched records and the entities whose term stops being in force |
| `approval_package` | No vocabulary | Blocks like the gate; key `vocabulary` with the findings and, if any, the section "Domain vocabulary" in `--text` |
| `query`, `relations` | No `defines` | Includes `defines` of a decision that declares it |
| `integrate.final_tree` | Returns `(final, warnings)` | Returns `(final, warnings, vocabulary)` |
| Command `vocabulary` | Does not exist | New read-only query |

No consumer that was correct with 0.6.0 sees another exit code: the block only appears when a `defines` is in force, which 0.6.0 rejected in the schema.

**How to migrate.** Nothing as long as no vocabulary is declared. The first decision with `defines` closes the class for the whole installation: declare in it also the classes the entities already use, and then `kbol vocabulary` lists the missing ones as undeclared, with their uses. Whoever calls `final_tree` unpacks three values.

## 0.4.1: exit codes when nothing was examined

Class: breaking.

**Why.** An operation that examined nothing ended `completed` (0) and read as "all in order". A failure of `verify` could not be told from a success by its code either. A 0 must mean that what was asked was examined and came out well (design choices, "Zero examined and local check").

**Who is affected.** Any hook or script that reads the exit codes of `kbol`.

**What happens.**

| Operation | Case | Before | Now |
|---|---|---|---|
| `ready` | No milestones | `completed` (0) | `partial` (3) |
| `consolidate` | Requested IDs missing | `completed` (0) | `partial` (3) |
| `citations` | Zero rows | `completed` (0) | `partial` (3) |
| `citations` | The folder does not exist | `completed` (0) | `failed` (1) |
| `drift` | Zero records checked, or a record that could not be read | `completed` (0) | `partial` (3) |
| `drift` | Inconsistent base (repeated ID or forbidden cycle) | `completed` (0) | `blocked` (2) |
| `migrate` | No legacy record proposed | `completed` (0) | `partial` (3) |
| `context` | No records in the scope | `completed` (0) | `partial` (3) |
| `verify` | The check fails | `completed` (0) | `failed` (1) |
| `verify` | The result is unknown | `completed` (0) | `partial` (3) |

**How to migrate.** Treat 3 as "answer with limits": it is neither an error nor a full success. Read `warnings` and `coverage` to know what was not examined and decide case by case. If your script only accepts 0, accept 3 too where an empty result is legitimate, and check the warnings where it is not. A 1 from `verify` or `citations` is now a real failure.

## 0.5.0: evidence in `query` and dependencies with an undecidable successor

Class: breaking.

**Why.** `query` considered a citation sufficient when its target existed, even if it was no longer in force. The `support` query defines which supports a record has and whether they are in force at the cut-off, and `query` uses that same rule. Also, a dependency on a fact with a successor whose start cannot be decided was considered satisfied with a warning.

**Who is affected.** Whoever reads the `evidence` block of `query`, and whoever depends on `ready` or on an `accepted_and_in_force` dependency on a fact with a successor.

**What happens.**

| Where | Before | Now |
|---|---|---|
| `query`, `evidence` block | `{citations: {ref: exists}, sufficient}` with `based_on` and the body citations | `{supports: [{ref, field, situation, reason, exists}], sufficient, reason?}`, also with `dependencies` and `sources` |
| `query`, `sufficient` | True if every target exists | True only if every support is in force at the cut-off |
| `accepted_and_in_force` dependency on a fact with a successor of ambiguous start | Satisfied, with a warning | Not satisfied: `AMBIGUOUS_TIME` |

**How to migrate.** Read `evidence.supports` instead of `evidence.citations`; the `citations` key no longer exists. A false `sufficient` may now be due to a support that exists and is not in force: its `reason` says so. To see all the supports of the base at once, use `kbol support`.
