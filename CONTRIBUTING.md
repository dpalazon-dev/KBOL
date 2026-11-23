# Contributing to KBOL

KBOL is maintained by one person and its priority is that what it claims is true. Before proposing a new capability, open a proposal issue to discuss it. Bug reports and improvements to what already exists are welcome directly.

## Environment

You need [uv](https://docs.astral.sh/uv/) and git. uv installs the Python versions the check asks for.

```bash
git clone https://github.com/dpalazon-dev/KBOL.git
cd KBOL
uv sync
uv run kbol --help
```

## Local check

Every change passes this check before it is proposed:

```bash
uv run python tools/check.py
```

It runs, in order and stopping at the first failure, `ruff` over `kbol`, `tests` and the tools; the suite on Python 3.10 and 3.14; and the tests of `tools/di` (with Docling, the slow part). With `--no-di` it skips `tools/di`; with `--quick`, the suite also runs only once. `uv run python tools/check.py --install-hook` sets up the quick pass as a `pre-push` hook in your copy.

Continuous integration (`.github/workflows/check.yml`) runs the same command with `--no-di`. A green run locally only vouches for your machine; the one in continuous integration, for Linux with the versions uv resolved.

Rules the suite enforces, worth knowing before touching documentation:

- There is a single README, `README.md`, in English.
- The module table of the README lists exactly the modules of `kbol/`, and its usage section, exactly the enabled commands.
- Every repository path cited between backticks in the README or in `docs/design-choices.md` has to exist.
- The README does not claim a capability the code does not have. If a feature is not finished, it goes in its limitations ("Limitations").

## Demo

The README GIF (`docs/demo.gif`) is drawn from the real output of the commands: `uv run --with pillow python tools/demo_gif.py`. Regenerate it if what `query`, `search` or `propose` show changes.

## Commits

Small commits, each with the check passing. The message follows the form `type(scope): what changes`, in English and in the present tense, with `feat`, `fix`, `docs`, `chore`, `test` or `refactor`; for example, `fix(citations): a citation without context is not taken as resolved`. Commits before 0.13 are in Spanish. If the change is breaking for whoever consumes the CLI, add its note in [`docs/breaking-changes.md`](docs/breaking-changes.md) with that file's template and an entry in [CHANGELOG.md](CHANGELOG.md).

## Pull requests

Code and documentation come in through pull requests against `main`. The maintainer reviews, repeats the check and merges.

## License of contributions

KBOL is distributed under Apache-2.0. What you contribute comes in under that same license (section 5), with no separate agreement.

## Issues

Use the templates: bug or proposal. In a bug, include the exact command, the version (`pyproject.toml` or `kbol.__version__`) and the JSON envelope of the output, which says what the command did not evaluate.
