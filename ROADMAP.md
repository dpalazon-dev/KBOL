# Roadmap

KBOL is alpha software maintained by one person. This page says what works today, what is being built and what is planned. Planned items are intentions, not commitments: each one ships when it is done and tested, and the [changelog](CHANGELOG.md) records what actually shipped.

## Status

- **Version 0.13.** The engine, the CLI and the integration gate work and are covered by about 1,000 tests on Python 3.10 and 3.14, on Linux (CI) and Windows.
- **In use** in the maintainer's own projects. No third-party installation yet: if you try it, your feedback shapes what comes next.
- **Language.** From 0.13 (KB-DPP 1.0) the contract, the record format, the CLI, the messages, the code and the documentation are in English. [`docs/glossary-es-en.md`](docs/glossary-es-en.md) maps the 0.12 names.

## In progress

- **Migrating 0.12 records.** `kbol migrate` will convert records and installation files written in the 0.12 (Spanish) format to the 0.13 names, following the glossary. Until then the conversion is manual.
- **Use it in your project.** A `kbol init` command that sets up a repository in one step (installation file, policy, root of trust, agent skills and hooks), a guided setup skill for coding agents, and a router skill that points the agent to the right action: record a decision, ask what is in force, resume a task or check citations.
- **Visual explanation.** An animation of how a knowledge base forms: paths, YAML headers, clauses, relations and vocabulary, event history, what is in force on a date, and the context package an agent receives.

## Next

- **A public benchmark.** A question bank over an invented corpus, with a scored baseline, so that every change to KBOL can be measured against the same questions.
- **Friendlier CLI.** Help per command and validation errors written for people.
- **Pull request approvals from the CLI.** The GitHub review verifier exists as a library; exposing it in `kbol propose` turns approvals from declared quotes into authenticated reviews.

## Later

- **A Rust engine.** Port the engine to Rust for a single binary with no Python or uv to install, and faster start-up in agent hooks. The port will keep the CLI and its JSON envelope, and the Python test suite will act as the oracle: same input, same output.
- **Ingestion, backups and isolated checks**, the parts of the KB-DPP contract that KBOL does not implement yet (see the limitations in the [README](README.md#limitations)).
