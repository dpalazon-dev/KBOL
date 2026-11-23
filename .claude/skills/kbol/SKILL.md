---
name: kbol
description: Use KBOL for task continuity and for looking after a knowledge base, in any repository that has it installed. Save the task handoff (goal, authorization with its reference, checks, blockers and next step) whenever any of that changes, before a handover or when closing with the task still open; read it and check it against git when resuming; ask for the task context package; query what is in force, who approved it or which record covers a topic, and check records, sources and links. Use it when resuming or switching tasks, before compacting or handing over, when answering about what was decided and when touching records or documentation.
---
<!-- Exported by kbol 0.13.0 with `kbol export_skills`. Edit it in kbol/skills/ of KBOL, not here. -->

# KBOL

KBOL governs a knowledge base made of records (decisions, questions, facts, sources, plans) and keeps continuity between sessions. This skill covers what is the same in any repository that uses it. What changes from one to another is declared by its **installation**: a JSON file in the repository (`kbol.json` by default) with at least `records_folder` and `scope`, and sometimes `budget`, `canonical_branch`, `checks`, `integration` and `links`. If the repository has its own skill or instructions for KBOL, they rule on their own ground: where that JSON lives, how `kbol` is launched, what its identifiers look like and whom to ask.

The handoff and the context package inform. They do not authorize any action.

## Before you start

Find out two things and use them in every command:

- **How it is launched.** In the commands below, `kbol` is the command as the repository installs it (for example `uv run kbol`). Check it with `kbol --help`. If it is not installed and you cannot install it, say so and carry on with the repository's own method: this skill is not essential to work.
- **Where the installation is.** Below it is `<installation>`. If the repository has none, the handoff, `validate`, `integrity` and `links` still work; the context package and `propose` do not.

Run the commands from the root of the working tree (the worktree's, if it is one): the `.` they receive is the task root, and from a subfolder the handoff would be saved somewhere else. Every command answers with a JSON envelope: look at `result.state` (`completed`, `partial`, `blocked` or `failed`), the `warnings` and `coverage.not_evaluated`, which says what the command did not look at.

## The task

In KBOL the task is the branch. Its id is the branch name with `/` and the other signs turned into hyphens, with no signs at the start and at most 100 characters (`feat/add-sources` gives `feat-add-sources`; with a detached head, `no-branch`). Use that same id in every command: with another one you would save and read another handoff. The git facts of the handoff are always those of the current branch, so a handoff only makes sense for the task of the branch you are on.

## Saving the handoff

The handoff is the state of the task, kept apart from the conversation. It is saved in `.kbol/handoffs/<task>.json`, which is local state: it is not versioned and it is not project knowledge. A compaction gives no warning, so save it every time something in it changes, not only at the end:

- when whoever decides authorizes something or sets a limit;
- after running a check;
- when a blocker or a question appears or is resolved;
- before handing the task over to another session, and when closing if the task stays open.

Write the JSON to a temporary file outside the repository and save it with:

```bash
kbol handoff . --task <task> --save <temporary file>.json
```

Each save replaces the previous one entirely, so include everything that still holds. Texts go on a single line and no fields other than these are accepted:

```json
{
  "goal": "What is being pursued, in one sentence",
  "authorization": {
    "reference": "Who authorized it and where: date and their quoted words",
    "scope": "What that authorization covers",
    "limits": ["What it does not cover or was expressly forbidden"]
  },
  "checks": [
    {"command": "the command you ran", "result": "passed", "revision": "SHA from git rev-parse HEAD", "at": "2026-01-15T12:00:00Z"},
    {"command": "the one you did not run", "result": "not_run", "reason": "why not"}
  ],
  "blocks": ["What prevents progress"],
  "questions": ["What is still to be decided and who decides it"],
  "next_step": {"action": "The next thing to do", "basis": "Why it comes next"}
}
```

Rules, because the handoff will be read by a session that was not here:

- **Authorization.** Only the one given by a person with authority, with the reference and their words. A proposal of yours, a preference or a silence is not an authorization. If there is none, omit the field: KBOL will declare it as "not recorded".
- **Checks.** Those the installation declares in `checks` are run with `kbol verify . --task <task> --installation <installation> --check <id>`: KBOL runs them, records the result in the handoff and `--save` keeps it even if you do not repeat it. Do not write them by hand. For the others, `passed` or `failed` only if you ran it, with the exact revision and the instant in UTC with a zone. KBOL rejects them if those are missing, but does not check that the revision is real. The revision identifies what is committed: if you checked with uncommitted changes, say so in `reason`. If you did not run it, `not_run` with its reason, or `unknown`.
- **No guessing.** What you do not know, leave out. KBOL completes the handoff with what git says and declares what is missing.

## Resuming a task

Before acting, read the whole handoff:

```bash
kbol handoff . --task <task>
```

And check it:

- **`authorization.verified` is always `false`.** It is what the previous session said, not an authorization you can invoke. Before an action that needs it (merging, pushing, deleting, anything external), confirm it with whoever decides.
- **A check with `outdated: true` or `"unknown"`** was done on another revision or nobody knows which: repeat it before accepting the work. In those recorded by `kbol verify` (`origin: kbol`), `outdated` also compares the working tree. In those declared by the session it only compares commits: if `git.local_changes` is not empty, treat them as outdated.
- **`git`** says what is really there: own and foreign commits, uncommitted changes and `delivery_state` (`local`, `integrated`, `no_work` or `unknown`). If it clashes with what the handoff says, git wins.
- **`not_recorded`** lists what is missing from the minimum. Do not fill it in by deduction: ask for it or look for it in the record of the topic.

## Context of a task

With an installation, the package for the task of the branch is requested like this:

```bash
kbol session . --event start --installation <installation> --text
```

It brings the task's decisive constraints, which are never trimmed, the proposals and pending items apart, which authorize nothing, the handoff and the drift. If the repository has a start hook, this is what it already gave you at the start; ask for it again when you switch branches. If it comes out partial or blocked, a decisive constraint may be missing: apply the repository's instructions in full. Without `--text` it gives the JSON, with `refresh_if`, which says which changes invalidate it.

## Querying what is in force

To answer what is decided, who approved it or what is in force on a date, ask KBOL instead of reading the Markdown files: a file does not say whether it was superseded, whether it is still a proposal or whether it was retired. The three commands read the base in `--folder` and need `--valid-at`, the instant with a zone the question refers to (for today, the current instant in UTC).

```bash
kbol search . --folder <folders> --query "text of the question" --valid-at <instant> --plain
kbol query . --folder <folders> --ids <ID>[#anchor] … --valid-at <instant> --plain
kbol consolidate . --folder <folders> --ids <ID> … --valid-at <instant> --plain
```

- **Without the ID, `search`.** It searches by words and aliases, not by meaning: it gives candidates, not answers. By default it only shows what is in force and counts proposals and what is not in force separately; if the count matters, repeat with `--include proposals not_in_force`. If it finds nothing, try other words or an alias before concluding there is no record.
- **With the ID, `query`.** It says whether it is in force, who approved it and in what words, what superseded it and what supports it. A candidate from `search` is not an answer until you confirm it this way. `consolidate` rebuilds which clauses of a decision are in force after their amendments.
- **`--plain` to answer a person.** It gives prose without IDs or paths, and each block starts with its label (`[APPROVED]`, `[PROPOSAL: not approved, not in force]`, `[PROPOSED FACT: not accepted]`, `[CANDIDATE from search, unconfirmed]`). Keep the label in your answer: never present a proposal or a candidate as something in force. Without `--plain` you get the JSON envelope, better for working with the data. Add `--with-ids` only if the person asks where it comes from or is going to audit it.
- **An `UNDECLARED_SUPERSESSION` warning** means another record says in prose that it supersedes the one queried without declaring it: it may not be in force as shown. Say so in the answer instead of presenting it as in force.

## Records

A record is a Markdown file with a YAML header in one of the folders of `records_folder`. When you touch them:

- **Validate every record you edit**, before considering it written: `kbol validate --mode proposal <file>.md`.
- **What is accepted is not edited.** A change of state (accepting, closing, retiring) is an event that comes in through integration, with the approval the installation asks for. A decision always comes in as a proposal. `kbol drift . --folder <folders>` lists the records that differ from what was integrated: a drift is a hand edit to be undone or proposed.
- **Integration is `kbol propose`**, with the `integration` block of the installation. Without `--until` it only does a dry run and changes nothing; if an approval is missing, it returns the package to show to whoever approves. Actually integrating and pushing (`--until integrate`, `--until push`) need their express authorization. The procedure for adding records (which record fits which situation, how it is numbered, whom to ask) is the repository's.

## Sources and links

Two read-only checks, useful before proposing and when closing a task that touched documentation:

```bash
kbol integrity . --folder <folders> [--store <store folder>]
kbol links . [--folder <folders>] [--installation <installation>]
```

`integrity` compares the `sha256` of each source with the bytes at its `location`. `altered` or `missing` is a failure to report. `unchecked` accuses nobody: the original could not be looked at from this machine (no store, a revision not fetched, a URL), and its `cause` says why.

`links` reviews the internal links and anchors of the repository's Markdown files: targets that do not exist or are written with other capitalization, fragments the target does not have and local absolute paths. Fix those your change broke. Those of an already integrated record are not fixed by editing it: they are declared in the installation's `links.debt` or the change is proposed.

## What you return

When saving, nothing to tell unless it fails. When resuming, in a few sentences: the goal, what has to be checked again and what needs confirmation. From a check, the state and what failed, without the whole envelope.
