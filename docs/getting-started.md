# Getting started

From an empty repository to an approved, queryable decision, in eight steps. The commands are bash (on Windows, Git Bash). It assumes `kbol` is installed ([README](../README.md#installation)) and git has a name and email configured. [`examples/quickstart.sh`](../examples/quickstart.sh) runs the same steps in one go.

At the end you will have:

- a policy with one role and one person, activated by the root of trust;
- an accepted decision that came in through the integration gate, with the quote of whoever approved it and a receipt;
- KBOL's answer to "what is in force about the database?".

## 1. Repository and remote

KBOL integrates into the canonical branch (here `main`) through its own clone of your remote, so you need one. To try it out, an empty repository in the folder next door will do:

```bash
git init --bare origin.git
git init -b main myproject
cd myproject
mkdir kb
```

`kb/` is the records folder. KBOL keeps its local state (the integrator's clone and the receipts) in `$KBOL_STATE/<repository>/`, by default `~/.kbol/<repository>/`.

## 2. The policy: one role and one person

Whoever approves is a person who holds a role. Both are records, like decisions. Create `kb/ROLE-11111111-1111-4111-8111-111111111111.md`:

```markdown
---
id: ROLE-11111111-1111-4111-8111-111111111111
type: role
class: record
scope: myproject
author: human:ana
events: []
title: Owner
description: Ratifies decisions and governs the policy.
state: proposed
sources: []
scopes:
- myproject
capabilities:
- ratify
- govern_policy
approval_rule: one
---
Owner role of the project.
```

And `kb/PER-22222222-2222-4222-8222-222222222222.md`:

```markdown
---
id: PER-22222222-2222-4222-8222-222222222222
type: person
class: record
scope: myproject
author: human:ana
events: []
sources: []
title: Ana Pérez
description: Owner of the project.
state: proposed
nature: human
identity_ref: declared:ana
holds:
- role: ROLE-11111111-1111-4111-8111-111111111111
  from: '2026-01-01T00:00:00Z'
---
Person who owns the project.
```

IDs are `<PREFIX>-<UUID v4>`; for your own, generate a new UUID. Every new record carries `events: []`, because KBOL writes the history, and an `author` of the form `human:<alias>`, `process:<name>` or `client/model`. `kbol validate --mode proposal <file>` tells you whether a record is well formed.

## 3. The installation

`kbol.json`, at the root, says where the records are and how integration works:

```json
{
  "records_folder": "kb",
  "scope": "myproject",
  "canonical_branch": "main",
  "integration": {"remote": "../origin.git", "repository": "myproject"}
}
```

`remote` is the URL or path of your canonical remote, and `repository`, the name of its local state. The other keys (checks, steps after integrating, approval mode) are in [the design choices](design-choices.md#authority-and-integration).

Ignore the local state KBOL leaves in the repository, and push the base:

```bash
printf '.kbol/\n' > .gitignore
git add -A
git commit -m "kb: initial policy"
git remote add origin ../origin.git
git push origin main
```

## 4. The root of trust

The first person cannot approve themselves through the gate, so they are activated once with `kbol bootstrap`. The canonical branch cannot be checked out while KBOL writes to it: work on another branch.

```bash
git switch -c work
cat > ../declaration.json <<EOF
{"identity": "declared:ana", "session": "Ana's terminal", "instant": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "quote": "I am Ana and I bootstrap the root of trust of myproject"}
EOF
kbol bootstrap . --canonical-branch main --folder kb --operation-id bootstrap-1 \
  --base "$(git rev-parse main)" \
  --person PER-22222222-2222-4222-8222-222222222222 \
  --roles ROLE-11111111-1111-4111-8111-111111111111 \
  --declaration ../declaration.json --receipts ~/.kbol/myproject/receipts
git push origin main
git reset --hard main
```

The declaration is the quote of the person who bootstraps: `identity` must be the `identity_ref` of their record and `instant`, the real moment they said it. It is kept outside the repository. It is a declared mechanism, not authenticated: KBOL records what was said, but does not check who said it ([non-conforming mechanisms](design-choices.md#non-conforming-mechanisms)).

## 5. The first decision

A decision splits its text into clauses, each with its anchor. Create `kb/DEC-33333333-3333-4333-8333-333333333333.md`:

```markdown
---
id: DEC-33333333-3333-4333-8333-333333333333
type: decision
class: record
scope: myproject
author: human:ana
events: []
title: The database is PostgreSQL
description: Which database the project uses.
state: proposed
sources: []
authorized_by:
- ROLE-11111111-1111-4111-8111-111111111111
alternatives:
- id: A
  description: PostgreSQL
  selected: true
  reason: Supports several writers and the team knows it.
- id: B
  description: SQLite
  selected: false
  reason: A single writer.
criteria:
- Concurrency
rationale: The service has several processes writing at the same time.
---
<clause id="C1">

The project database is PostgreSQL 16.

</clause>
```

It comes in as a proposal. What you ask for is to accept it, and that is declared as an effect, in a file outside the repository:

```bash
cat > ../effects.json <<EOF
{"DEC-33333333-3333-4333-8333-333333333333": [{"new_state": "accepted", "valid_from": "$(date -u +%Y-%m-%dT00:00:00Z)"}]}
EOF
```

## 6. The dry run: what needs approving

`kbol propose` without `--until` only does a dry run. If an approval is missing, it exits with code 3 (`pending_approval`) and returns the approval package: what changes, its digest and the skeleton of the approval.

```bash
kbol propose . --installation kbol.json --operation-id decision-db \
  --files kb/DEC-33333333-3333-4333-8333-333333333333.md \
  --effects ../effects.json > ../dry-run.json
```

`result.package.approvals` holds the skeleton with `base_shown` and the `digests` of what is being approved. Show it to the approver; with their answer, fill in `identity`, `session`, `instant` (the real moment, after the bootstrap) and `quote` (their literal words), and save it as `../approvals.json`:

```json
[
  {
    "mechanism": "declared",
    "identity": "declared:ana",
    "session": "Ana's terminal",
    "instant": "2026-11-23T09:00:00Z",
    "quote": "I approve PostgreSQL as the database",
    "base_shown": "<the one from the dry run>",
    "digests": {"DEC-33333333-3333-4333-8333-333333333333": "<the one from the dry run>"}
  }
]
```

If the content changes after it is approved, the digest no longer matches and the gate answers `STALE_APPROVAL`.

## 7. Integrate and push

```bash
kbol propose . --installation kbol.json --operation-id decision-db \
  --files kb/DEC-33333333-3333-4333-8333-333333333333.md \
  --effects ../effects.json --approvals ../approvals.json --until push
```

The gate checks the shape, the mutability against the base and that the person holds the role that authorizes the decision; it writes the creation, ratification and acceptance events; it commits in the integrator's clone and pushes without forcing. The receipt stays in `$KBOL_STATE/myproject/receipts/`.

Your working file is still the draft, without events. Replace it with what was integrated:

```bash
rm kb/DEC-33333333-3333-4333-8333-333333333333.md
git fetch origin
git reset --hard origin/main
```

## 8. Query

```bash
kbol query . --folder kb --ids DEC-33333333-3333-4333-8333-333333333333 \
  --valid-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --plain
```

```text
[APPROVED] «The database is PostgreSQL»
  In force in full on 23 Nov 2026.
  Says: The project database is PostgreSQL 16.
  Approved by Ana Pérez on 23 Nov 2026, in these words: «I approve PostgreSQL as the database» (declared approval, not authenticated).
```

Without the ID, `kbol search . --folder kb --query "database" --valid-at … --plain` gives the same decision as a candidate. Without `--plain`, every command returns a JSON envelope with what it examined and what it did not.

## What next

- **Changing an accepted decision.** It is not edited: a new decision amends it clause by clause (`amends`) or supersedes it entirely (`supersedes`), and comes in through the same gate. `kbol consolidate` shows which clauses are in force after the amendments.
- **With a coding agent.** `kbol export_skills .claude/skills` installs the KBOL skill, and `kbol session . --event start --installation kbol.json --text` gives the context a start-up hook injects into the session.
- **Sources and citations.** A fact cites its source by lines or by page; `kbol citations` and `kbol integrity` check it. For PDFs and other documents there is `tools/di`.
- **Every command**, in the [README](../README.md#usage).
