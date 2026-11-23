#!/usr/bin/env bash
# KBOL quick start: builds a throwaway project with one approved decision and queries it.
#
#   bash examples/quickstart.sh [folder]      (default: ./kbol-demo)
#
# Needs `kbol` on PATH (or KBOL="uv run --project /path/to/KBOL kbol"), git and Python 3.
# Every step is explained in docs/primeros-pasos.md.
set -euo pipefail

DEST="${1:-kbol-demo}"
read -r -a KBOL <<< "${KBOL:-kbol}"
k() { "${KBOL[@]}" "$@"; }
PY="$(command -v python3 || command -v python)"
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ -e "$DEST" ]; then echo "$DEST already exists; pick another folder" >&2; exit 1; fi
mkdir -p "$DEST" && cd "$DEST"
export KBOL_ESTADO="$PWD/.estado"

echo "==> 1. A repository with a remote (the canonical branch is main)"
git init -q --bare origen.git
git init -q -b main miproyecto && cd miproyecto
git config user.name "Ana Pérez"; git config user.email "ana@example.com"; git config core.autocrlf false
mkdir kb

echo "==> 2. The policy: one role and one person"
cat > kb/ROL-11111111-1111-4111-8111-111111111111.md <<'EOF'
---
id: ROL-11111111-1111-4111-8111-111111111111
type: rol
clase: registro
ambito: miproyecto
autor: human:ana
eventos: []
title: Responsable
description: Ratifica decisiones y gobierna la política.
estado: propuesta
sources: []
ambitos:
- miproyecto
capacidades:
- ratificar
- gobernar_politica
regla_aprobacion: uno
---
Rol responsable del proyecto.
EOF
cat > kb/PER-22222222-2222-4222-8222-222222222222.md <<'EOF'
---
id: PER-22222222-2222-4222-8222-222222222222
type: persona
clase: registro
ambito: miproyecto
autor: human:ana
eventos: []
sources: []
title: Ana Pérez
description: Responsable del proyecto.
estado: propuesta
naturaleza: humana
identidad_ref: declarada:ana
ocupa:
- rol: ROL-11111111-1111-4111-8111-111111111111
  desde: '2026-01-01T00:00:00Z'
---
Persona responsable del proyecto.
EOF

echo "==> 3. The installation file"
cat > instalacion.json <<'EOF'
{"carpeta_registros": "kb", "ambito": "miproyecto", "rama_canonica": "main",
 "integracion": {"remoto": "../origen.git", "repositorio": "miproyecto"}}
EOF
printf '.kbol/\n' > .gitignore
git add -A && git commit -q -m "kb: initial policy"
git remote add origin ../origen.git && git push -q origin main

echo "==> 4. Root of trust (once, from a branch other than main)"
git switch -q -c trabajo
printf '{"identidad": "declarada:ana", "sesion": "quickstart", "instante": "%s", "cita": "I am Ana and I bootstrap the root of trust"}\n' "$(now)" > ../declaracion.json
k arranque . --rama-canonica main --carpeta kb --operacion-id arranque-1 --base "$(git rev-parse main)" \
  --persona PER-22222222-2222-4222-8222-222222222222 --roles ROL-11111111-1111-4111-8111-111111111111 \
  --declaracion ../declaracion.json --recibos "$KBOL_ESTADO/miproyecto/recibos" > /dev/null
git push -q origin main && git reset -q --hard main

echo "==> 5. A decision, proposed"
cat > kb/DEC-33333333-3333-4333-8333-333333333333.md <<'EOF'
---
id: DEC-33333333-3333-4333-8333-333333333333
type: decision
clase: registro
ambito: miproyecto
autor: human:ana
eventos: []
title: La base de datos es PostgreSQL
description: Qué base de datos usa el proyecto.
estado: propuesta
sources: []
autorizado_por:
- ROL-11111111-1111-4111-8111-111111111111
alternativas:
- id: A
  descripcion: PostgreSQL
  seleccionada: true
  motivo: Admite varios escritores y el equipo lo conoce.
- id: B
  descripcion: SQLite
  seleccionada: false
  motivo: Un solo escritor.
criterios:
- Concurrencia
justificacion: El servicio tiene varios procesos que escriben a la vez.
---
<clausula id="C1">

La base de datos del proyecto es PostgreSQL 16.

</clausula>
EOF
printf '{"DEC-33333333-3333-4333-8333-333333333333": [{"estado_nuevo": "aceptada", "valido_desde": "%s"}]}\n' "$(date -u +%Y-%m-%dT00:00:00Z)" > ../efectos.json
DEC=kb/DEC-33333333-3333-4333-8333-333333333333.md

echo "==> 6. Dry run: what needs approving"
k proponer . --instalacion instalacion.json --operacion-id decision-bd --archivos "$DEC" --efectos ../efectos.json > ../ensayo.json || true
"$PY" - ../ensayo.json ../aprobaciones.json "$(now)" <<'EOF'
import json, sys
apr = json.load(open(sys.argv[1], encoding="utf-8"))["resultado"]["paquete"]["aprobaciones"]
for a in apr:
    a.update(identidad="declarada:ana", sesion="quickstart", instante=sys.argv[3], cita="Apruebo que la base de datos sea PostgreSQL")
json.dump(apr, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF

echo "==> 7. Approve, integrate and push through the gate"
k proponer . --instalacion instalacion.json --operacion-id decision-bd --archivos "$DEC" --efectos ../efectos.json \
  --aprobaciones ../aprobaciones.json --hasta subir > /dev/null
rm "$DEC" && git fetch -q origin && git reset -q --hard origin/main

echo "==> 8. What is in force?"
echo
echo "\$ kbol consultar . --carpeta kb --ids DEC-3333… --valido-en now --llano"
k consultar . --carpeta kb --ids DEC-33333333-3333-4333-8333-333333333333 --valido-en "$(now)" --llano
echo
echo "\$ kbol buscar . --carpeta kb --consulta \"base de datos\" --valido-en now --llano"
k buscar . --carpeta kb --consulta "base de datos" --valido-en "$(now)" --llano
echo
echo "Done. The demo project is in $DEST/miproyecto; the receipts in $DEST/.estado."
