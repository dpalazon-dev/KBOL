# KBOL · Knowledge Base Operating Layer

[![CI](https://github.com/dpalazon-dev/KBOL/actions/workflows/comprobar.yml/badge.svg)](https://github.com/dpalazon-dev/KBOL/actions/workflows/comprobar.yml)
[![Release](https://img.shields.io/github/v/release/dpalazon-dev/KBOL)](https://github.com/dpalazon-dev/KBOL/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Project decisions you can check: which rule is in force on any date, who approved it, and which page or lines each citation comes from.**

[Leer en español](README.es.md)

KBOL is a command-line tool that works on Markdown records inside your git repository: decisions, questions, facts, hypotheses, plans and sources. Every record carries an event history. From it, KBOL rebuilds what is in force on any date, refuses to integrate a change without the approval your policy requires, and checks that every citation points to the exact place in its original document.

![KBOL demo: querying what is in force, searching by text, and the gate blocking a hand edit of an accepted decision](docs/demo.gif)

## Quick start

Build a throwaway project with one approved decision and ask KBOL what is in force (needs git, bash and Python 3):

```bash
uv tool install git+https://github.com/dpalazon-dev/KBOL
git clone https://github.com/dpalazon-dev/KBOL && cd KBOL
bash examples/quickstart.sh /tmp/kbol-demo
```

[`examples/quickstart.sh`](examples/quickstart.sh) creates a role and a person, bootstraps the root of trust, proposes a decision, approves it, integrates it through the gate and queries it:

```text
[APROBADA] «La base de datos es PostgreSQL»
  Rige entera a 23 nov 2026.
  Dice: La base de datos del proyecto es PostgreSQL 16.
  Aprobación de Ana Pérez, el 23 nov 2026, con estas palabras: «Apruebo que la base de datos sea PostgreSQL» (aprobación declarada, sin autenticar).
```

## What it is for

- **Know what has actually been decided.** "Is it still true that our database is PostgreSQL?" `kbol consultar` answers whether it is in force today, since when, who approved it and in which words, and which decision replaced it if it no longer applies. A rule nobody replaced does not expire for being old, and two rules that clash without a resolution come out as a conflict, not as "the most recent one wins".
- **Change things under control.** Records only change through an integration gate (`kbol proponer`): it checks their shape, that closed content is not rewritten and that someone with authority approves, and it leaves a receipt for every operation.
- **Cite without making things up.** A fact cites its source by page and region of a PDF or by lines of a text, against the SHA-256 fingerprint of the original. `kbol citas` tells you whether each citation still resolves.
- **Give an agent reliable context.** `kbol sesion` prepares, for a coding agent, the constraints in force for the current task, and the skill shipped with the package (`kbol exportar_skills`) teaches the agent to query before assuming.

## How it differs

| | ADR folder or wiki | Agent memory or RAG | KBOL |
|---|---|---|---|
| What is in force on a date | You read it by hand | The most similar or most recent chunk | Computed from the event history |
| Two clashing decisions | Whichever you read | The most recent one | A declared conflict until a person resolves it |
| Who approved it | A convention | Unknown | An approval bound to the digest of what was approved, with a receipt |
| Citations | Links | Unversioned chunks | Page, region or lines against the fingerprinted original |
| Who can change it | Any commit | Direct writes | An integration gate |

KBOL is not a semantic search engine, a graph database or a server: it is a CLI over git and Markdown. `kbol buscar` finds records by keywords when you do not know their ID, but `consultar` is what decides what is in force. Approvals today are declared: the literal words of the approver, not authenticated (see [the design choices](docs/elecciones.md#mecanismos-no-conformes)).

The CLI, its messages and the detailed documentation are in Spanish. Command and option names are Spanish words too (`consultar` = query, `buscar` = search, `proponer` = propose, `integrar` = integrate).

## Installation

Requires Python 3.10 or later, git and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/dpalazon-dev/KBOL
```

To pin a version, append its tag to the URL (`…/KBOL@vX.Y.Z`). The command is `kbol`; `kbol --version` prints the installed version. To work on the code, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Getting started

[`docs/primeros-pasos.md`](docs/primeros-pasos.md) (in Spanish) takes an empty repository to an approved, queryable decision in eight steps: a policy with one role and one person, the installation file, the root of trust, the first proposal, its approval and the query.

## Concepts

- **Record.** A Markdown file with a YAML header (`type`, `id`, `estado`, relations and `eventos`) in the records folder. Decisions split their text into clauses (`<clausula id="C1">`), which other decisions can amend or repeal one by one.
- **Installation.** A JSON file in the repository that says where the records are, the scope, the canonical branch and how integration works. The policy (roles and people) is made of records like any other.
- **Root of trust.** The first role and the first person are activated once with `kbol arranque`; from then on, every change goes through integration.
- **Integration.** `kbol proponer` takes files from the working tree to the canonical branch through its own clone, with the approval the policy requires, and leaves a receipt.
- **Cut-off.** Every query takes `--valido-en`, the instant you are asking about, and accepts `--conocido-hasta` to answer with what was known at that time. KBOL never reads the clock on its own.

KBOL implements the KB-DPP contract ([core 0.7](docs/referencias/KB-DPP-nucleo.md) and [implementation 0.8](docs/referencias/KB-DPP-implementacion.md)). What the contract leaves open and how KBOL settles it is in [the design choices](docs/elecciones.md); breaking changes, in [the change notes](docs/cambios.md).

That a function exists here does not prove an operational capability in a project: only its use in an installation, with integration and receipt, does.

## Usage

Reference for every command. From a clone, prefix them with `uv run`; with the tool installed, `kbol` is enough. `kbol --help` lists the options.

```bash
uv run kbol validar RUTA.md [--modo propuesta|canonico|intercambio]
uv run kbol migrar RUTA_DOCS --revision <sha> [--instalacion instalacion.json]
uv run kbol digest RUTA.md --efectos efectos.json
uv run kbol consolidar RAIZ --carpeta kb --revision <sha> --ids DEC-… --valido-en <instante> [--conocido-hasta <instante>] [--heredados] [--instalacion instalacion.json]
uv run kbol listos RAIZ --carpeta kb --revision <sha> --valido-en <instante> [--conocido-hasta <instante>] [--heredados] [--instalacion instalacion.json]
uv run kbol impacto RAIZ --carpeta kb --base <sha> [--revision <sha>]
uv run kbol consultar RAIZ --carpeta kb[,docs/decisions] --ids ID[#ancla] … --valido-en <instante> [--conocido-hasta <instante>]
uv run kbol buscar RAIZ --carpeta kb[,docs/decisions] --consulta "texto" [--incluir propuestas no_vigentes] [--limite N] --valido-en <instante> [--conocido-hasta <instante>] [--llano [--con-ids]]
uv run kbol soporte RAIZ --carpeta kb[,…] --valido-en <instante> [--conocido-hasta <instante>] [--ids ID …] [--antes-valido-en <instante>] [--antes-conocido-hasta <instante>]
uv run kbol vocabulario RAIZ --carpeta kb[,…] --valido-en <instante> [--conocido-hasta <instante>]
uv run kbol preparar_aprobacion RAIZ --carpeta kb[,…] --operacion-id <op> --base <sha> --propuesta <sha> --valido-en <instante> [--conocido-hasta <instante>] [--texto]
uv run kbol proponer RAIZ --instalacion instalacion.json --operacion-id <op> --archivos RUTA… [--efectos efectos.json] [--importaciones importaciones.json] [--aprobaciones aprobaciones.json] [--actor <actor>] [--hasta ensayo|integrar|subir] [--valido-en <instante>] [--texto]
uv run kbol integrar RAIZ --rama-canonica main --carpeta kb[,…] --operacion-id <op> --base <sha> --propuesta <sha> --aprobaciones aprobaciones.json --recibos <dir> [--remoto origin] [--aprobacion decisiva --actor <actor>]
uv run kbol desvios RAIZ --carpeta kb[,…] [--rama-canonica main] [--preparado]
uv run kbol citas RAIZ --carpeta kb[,…] [--almacen DIR]
uv run kbol integridad RAIZ --carpeta kb[,…] [--almacen DIR]
uv run kbol enlaces RAIZ [--carpeta docs[,…]] [--instalacion instalacion.json]
uv run kbol arranque RAIZ --rama-canonica main --carpeta kb[,…] --operacion-id <op> --base <sha> --persona <PER> --roles <ROL>[,…] --declaracion declaracion.json --recibos <dir>
uv run kbol relevo RAIZ --tarea <id> [--guardar relevo.json] [--rama-canonica main]
uv run kbol preparar_contexto RAIZ --tarea <id> --ambito <ámbito> --carpeta kb --instalacion instalacion.json --valido-en <instante> [--objetivo …] [--presupuesto N] [--heredados-carpeta docs] [--texto]
uv run kbol verificar RAIZ --tarea <id> --instalacion instalacion.json --verificacion <id> [--rama-canonica main]
uv run kbol sesion CARPETA --evento inicio|parar|commit --instalacion instalacion.json [--tarea <id>] [--valido-en <instante>] [--origen compact] [--rutas RUTA …] [--texto]
uv run kbol exportar_skills DESTINO [--skills NOMBRE …]
```

Queries never read the environment clock: `--valido-en` is mandatory. Without `--revision` they read the working tree and say so; without `--conocido-hasta` they use the whole admitted history and say so. They only load canonical records of the profile, and an invalid record is reported in the coverage. The legacy format is skipped unless `--heredados` is given (`consultar`, `soporte` and `vocabulario` always read it): it is then read separately, named in the result and never in force ([choices](docs/elecciones.md#lectura-compatible-durante-la-transición)). It is the default legacy format unless the installation declares its own in `formato_heredado` and is passed with `--instalacion` ([choices](docs/elecciones.md#formato-heredado-de-otro-proyecto)).

`sesion` is the command for an installation's hooks ([choices](docs/elecciones.md#órdenes-para-los-hooks-de-una-instalación)) and the only one that reads the clock: on `inicio`, without `--valido-en`, it uses the current instant and declares it in the envelope. With `--texto` it outputs only what the hook injects into the session.

Every output is the contract envelope (`operacion`, `operacion_id`, `revision`, `valido_en`, `conocido_hasta`, `resultado`, `advertencias`, `cobertura`). Exit codes: 0 completed, 1 failed, 2 blocked, 3 partial.

## Modules

The "Control" column points to the KB-DPP contract controls each module implements.

| Module | Responsibility | Control |
|---|---|---|
| `modelo` | Closed vocabulary of the contract: record types, ID prefixes, legacy ID forms and enumerations | — |
| `tiempo` | ISO 8601 instants with time zone and day dates, without reading the environment clock | — |
| `verificacion` | Common error of approval verifiers, whatever their channel, and canonical form of a review to recognise it when repeated | VAL-04 (form) |
| `core` | Safe header parsing (no duplicate keys, tags, aliases or merges; dates as text) and validated writing with round trip | VAL-01 |
| `schema` | Common and per-type fields, relations allowed by origin, nested objects, events by class, body marks; in canonical mode, state against history | VAL-01 |
| `markdown` | Grammar of `<clausula>` and `<hecho>`, ignoring code and escapes | VAL-01, VAL-06 (form) |
| `eventos` | State rebuilt from admitted events and validity in a half-open interval | VAL-05 |
| `proyeccion` | Total projection of `status` for a revision and two explicit cut-offs | VAL-08 |
| `referencias` | Resolvable references, target type, anchors and forbidden cycles over a snapshot | VAL-02, VAL-07 |
| `digest` | Approvable object and contract digest, with published vectors in `kbol/vectores/digest.json` | VAL-04 (digest) |
| `consolidar` | Clauses in force at two cut-offs, for a whole decision or one clause (`ID#ancla`), with origin, chain and declared authority; proposals, future ones and conflicts apart; never revives texts | VAL-05, VAL-06 |
| `dependencias` | `depende_de` conditions and ready milestones; cancelling is not fulfilling | VAL-07 |
| `mutabilidad` | Proposal against the base: records, states, events, closed content, fingerprints and policy changes | VAL-03 |
| `snapshot` | Loading canonical records from disk or from a git revision | VAL-14 (coverage) |
| `autoridad` | Valid approvals under the base policy: computed digest, verified identity, active human person, role held in its scope and role rule | VAL-04 |
| `github` | Verifier of pull request reviews against the GitHub API; disabled without `KB_GITHUB_TOKEN` | VAL-04 |
| `declarada` | Verifier of declared approvals: the person's quote in a conversation, bound to the digests shown to them; never authenticated (choices, "Mecanismos no conformes") | VAL-04 (partial) |
| `arranque` | Root of trust of an installation, once: activates the role that governs the policy and the founding person, with the account verified on GitHub (`GET /user`) or, as a non-conforming mechanism, with their declared and quoted identity; afterwards every change goes through integration | VAL-04 (root) |
| `integrar` | Integration into a canonical branch without checkout: expected base, mutability, authority, admitted events, conflicts, domain vocabulary in the final tree, compare-and-swap commit, idempotent receipt and reconciliation. With `aprobacion="decisiva"`, only decisive changes need approval and every event carries the operation's actor | VAL-13, VAL-15 (partial) |
| `paquete` | Approval package (`kbol preparar_aprobacion`), read-only: per touched record, what changes in the header and in each clause, the requested effects, whether it is decisive and why, its supports and whether they are in force, and its digest; the impact, what it does not evaluate and the skeleton of the declared approval. It uses the same code as the gate and, if the gate would block, blocks first with the same code | — |
| `proponer` | Integration operator (`kbol proponer`): takes files from the working tree to the canonical branch through the integrator's clone (`$KBOL_ESTADO/<repositorio>/integrador.git`). Dry-run by default; `--hasta integrar` writes the clone's canonical branch and `--hasta subir` also runs `git push` without forcing. It does not build approvals: it receives the declared ones and, if one is missing, the dry run returns the approval package and exits with 3. After integrating it runs the steps the installation declares and commits the views they regenerate | VAL-13 (operation) |
| `importacion` | Guard for importing a legacy record: same body except marks and whitespace, regenerated provenance and no new text | VAL-02, VAL-03 |
| `huellas` | Fingerprint of every record written by integration and the root of trust, and `desvios`: records with history edited outside the flow; warns, does not block. With the canonical branch, also the commits that change records without going through the gate | — (local choice) |
| `exportar` | KBOL skills packaged in `kbol/skills/` and `kbol exportar_skills`, which writes them with the installed version in their header; only overwrites what it exported itself | — ([choices](docs/elecciones.md#skills-empaquetadas)) |
| `impacto` | Consumers affected by a change, with cause, path and owner | VAL-09 |
| `relevo` | Task state separate from the conversation (goal, authorisation, limits, checks, blockers and next step), stored locally in `.kbol/relevos/`, with git facts; declares what is missing and runs nothing | ESC-05 |
| `verificar` | Runner of the checks declared in the installation (id, command as an argument list, timeout and expected code), without a shell or caller arguments. Records the result in the task relay with the tested revision and tree | `verificar` operation (partial) |
| `contexto` | `preparar_contexto`: a task's package with the decisive constraints, which are never trimmed; proposals and pending items apart as non-binding; procedures, relay, omissions and refresh conditions | ESC-06, ESC-09 (partial) |
| `sesion` | Commands for an installation's hooks (`kbol sesion`): `inicio` gives the task's context package and the drifts with a single load and reuses it from `.kbol/sesion/` while nothing that decides it changes; `parar` validates as proposals the records with uncommitted changes; `commit` warns about drifts in the git index without blocking | — |
| `consultar` | Query by `ID` or `ID#ancla`: the record with its state at the cut-off, its authority (who approved, when, through which channel and with which words, as the record keeps them; never checked), its relations and the anchor text; for a decision, whether that clause is in force; for its supports, whether they exist and are in force; work fields and, for a person, what is assigned to them | RES-01, RES-04 (partial) |
| `buscar` | In-memory lexical search (`kbol buscar`): candidates by text or alias with ID, anchor, state, validity and snippet; by default only what is in force, with proposals and what is no longer in force counted and shown only on request. It does not decide what is in force | Core §8 (exploration) |
| `sustituciones` | Lexical hint `SUSTITUCION_NO_DECLARADA`: a record that says it replaces or repeals another without declaring it in `modifica` or `deja_obsoleta`. Flags, does not block | — |
| `llano` | Plain-language output of `consultar`, `consolidar` and `buscar` (`--llano`, IDs with `--con-ids`) | — |
| `soporte` | Read-only query (`kbol soporte`): for each record, whether its supports (`basada_en`, `dependencias`, `sources` and `<hecho ref>`) are in force at both cut-offs, with the source field, the situation and its reason, and a summary; with a second pair of cut-offs, the supports whose situation changes and the chain that explains it. Flags, does not block | — |
| `vocabulario` | Domain vocabulary (`kbol vocabulario`): the entity classes declared by decisions with `define` and in force at both cut-offs, their aliases, undetermined and retired terms, and the scopes of active roles; flags undeclared and retired terms with their uses. Flags, does not block; the integration gate blocks activating an entity whose class is not in force | — |
| `migracion` | Read adapter for the legacy format, the default one or the one the installation declares: dry inspection, no writing | — |
| `localizador` | Shape of `sources[].ancla` locators: `lines-v1` (lines), `pdf-v1` (physical page and normalised region) and `norma-v1` (logical unit of a regulation), combinable as `norma-v1:… @ pdf-v1:…` | RES-04 (form) |
| `citas` | Citation resolver (`kbol citas`): fingerprint of the original and the representation, page, region, logical unit and normalised literal quote against an `estructura-v1` structure; text by lines against the blob of the anchored revision; a document without pages (Word, spreadsheet, HTML) by lines of its text representation. It does not read PDFs or import processors | RES-04 (partial) |
| `integridad` | Source integrity (`kbol integridad`): compares each source's `sha256` with the bytes at its `ubicacion`, without normalising them, in the store, in an anchored revision or in the working tree. What could not be looked at is not reported as broken | VAL-10 (partial) |
| `enlaces` | Links in a repository's Markdown documents (`kbol enlaces`): internal paths with their case, fragments against the target's anchors, repeated explicit anchors and absolute local paths, with markdown-it and ignoring code. A broken link exits as failed | — ([choices](docs/elecciones.md#enlaces-de-la-documentación)) |
| `cli` | `kbol` entry point: dispatches the enabled operations, always returns the contract envelope and fails closed on the disabled ones; sets the exit codes | — |

## Limitations

`ingerir` returns `bloqueado` in the CLI. `integridad` checks every time and does not store the last valid check, and `disponible_con_integridad` dependencies still do not use it. `verificar` only runs declared checks and does not isolate them: it limits nothing beyond time, emits no receipts, and on Windows it does not stop a process the command leaves running after finishing. `impacto` is a read-only query between two revisions. `arranque` and `integrar` are exposed in the CLI only with the declared mechanism (choices, "Mecanismos no conformes"). `proponer` is the only command that pushes, only with `--hasta subir` and never forcing; if the remote rejects the push or a later step fails, what was integrated stays in the integrator's clone and the command does not undo it. It does not check that the working tree starts from the head of the canonical branch. Approval through GitHub pull request reviews exists as a library and is not exposed in the CLI, and the GitHub verifier has not been tested against the real service. Backup restore, check isolation and ingestion are missing. Search without an ID (`buscar`) is lexical, with no semantic similarity or persistent index. There are no delegations between roles and no MCP server: the policy is limited to roles and people.

## Tests

`tests/`, on Python 3.10 and 3.14, and those of `tools/di` (document processing with Docling) in their own project. `uv run python tools/comprobar.py` runs everything together with static analysis; `--sin-di` skips `tools/di`, and `--rapido` also runs the suite only once. `uv run python tools/comprobar.py --instalar-hook` installs the quick pass as a `pre-push` hook. `tests/heredados/` holds invented records in the legacy format to test the migration adapter, with their fingerprints in `tests/heredados/LEEME.txt`.

## License

Apache-2.0: [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright 2026 David Palazón.
