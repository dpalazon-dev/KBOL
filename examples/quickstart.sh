#!/usr/bin/env bash
# KBOL quick start: builds a throwaway project with one approved decision and queries it.
#
#   bash examples/quickstart.sh [folder]      (default: ./kbol-demo)
#
# Needs `kbol` on PATH (or KBOL="uv run --project /path/to/KBOL kbol"), git and Python 3.
# Every step is explained in docs/getting-started.md.
set -euo pipefail

DEST="${1:-kbol-demo}"
read -r -a KBOL <<< "${KBOL:-kbol}"
k() { "${KBOL[@]}" "$@"; }
PY="$(command -v python3 || command -v python)"
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ -e "$DEST" ]; then echo "$DEST already exists; pick another folder" >&2; exit 1; fi
mkdir -p "$DEST" && cd "$DEST"
export KBOL_STATE="$PWD/.state"

echo "==> 1. A repository with a remote (the canonical branch is main)"
git init -q --bare origin.git
git init -q -b main myproject && cd myproject
git config user.name "Ana Pérez"; git config user.email "ana@example.com"; git config core.autocrlf false
mkdir kb

echo "==> 2. The policy: one role and one person"
cat > kb/ROLE-11111111-1111-4111-8111-111111111111.md <<'EOF'
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
EOF
cat > kb/PER-22222222-2222-4222-8222-222222222222.md <<'EOF'
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
EOF

echo "==> 3. The installation file"
cat > kbol.json <<'EOF'
{"records_folder": "kb", "scope": "myproject", "canonical_branch": "main",
 "integration": {"remote": "../origin.git", "repository": "myproject"}}
EOF
printf '.kbol/\n' > .gitignore
git add -A && git commit -q -m "kb: initial policy"
git remote add origin ../origin.git && git push -q origin main

echo "==> 4. Root of trust (once, from a branch other than main)"
git switch -q -c work
printf '{"identity": "declared:ana", "session": "quickstart", "instant": "%s", "quote": "I am Ana and I bootstrap the root of trust of myproject"}\n' "$(now)" > ../declaration.json
k bootstrap . --canonical-branch main --folder kb --operation-id bootstrap-1 --base "$(git rev-parse main)" \
  --person PER-22222222-2222-4222-8222-222222222222 --roles ROLE-11111111-1111-4111-8111-111111111111 \
  --declaration ../declaration.json --receipts "$KBOL_STATE/myproject/receipts" > /dev/null
git push -q origin main && git reset -q --hard main

echo "==> 5. A decision, proposed"
cat > kb/DEC-33333333-3333-4333-8333-333333333333.md <<'EOF'
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
EOF
printf '{"DEC-33333333-3333-4333-8333-333333333333": [{"new_state": "accepted", "valid_from": "%s"}]}\n' "$(date -u +%Y-%m-%dT00:00:00Z)" > ../effects.json
DEC=kb/DEC-33333333-3333-4333-8333-333333333333.md

echo "==> 6. Dry run: what needs approving"
k propose . --installation kbol.json --operation-id decision-db --files "$DEC" --effects ../effects.json > ../dry-run.json || true
"$PY" - ../dry-run.json ../approvals.json "$(now)" <<'EOF'
import json, sys
approvals = json.load(open(sys.argv[1], encoding="utf-8"))["result"]["package"]["approvals"]
for a in approvals:
    a.update(identity="declared:ana", session="quickstart", instant=sys.argv[3], quote="I approve PostgreSQL as the database")
json.dump(approvals, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF

echo "==> 7. Approve, integrate and push through the gate"
k propose . --installation kbol.json --operation-id decision-db --files "$DEC" --effects ../effects.json \
  --approvals ../approvals.json --until push > /dev/null
rm "$DEC" && git fetch -q origin && git reset -q --hard origin/main

echo "==> 8. What is in force?"
echo
echo "\$ kbol query . --folder kb --ids DEC-3333… --valid-at now --plain"
k query . --folder kb --ids DEC-33333333-3333-4333-8333-333333333333 --valid-at "$(now)" --plain
echo
echo "\$ kbol search . --folder kb --query \"database\" --valid-at now --plain"
k search . --folder kb --query "database" --valid-at "$(now)" --plain
echo
echo "Done. The demo project is in $DEST/myproject; the receipts in $DEST/.state."
