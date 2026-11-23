# Primeros pasos

De un repositorio vacío a una decisión aprobada y consultable, en ocho pasos. Las órdenes son de bash (en Windows, Git Bash). Se supone `kbol` instalado ([README](../README.es.md#instalación)) y git con nombre y correo configurados.

Al final tendrás:

- una política con un rol y una persona, activados por la raíz de confianza;
- una decisión aceptada que entró por la puerta de integración, con la cita de quien la aprobó y un recibo;
- la respuesta de KBOL a «¿qué rige sobre la base de datos?».

## 1. Repositorio y remoto

KBOL integra en la rama canónica (aquí `main`) a través de un clon propio de tu remoto, así que hace falta uno. Para probar, sirve un repositorio vacío en la carpeta de al lado:

```bash
git init --bare origen.git
git init -b main miproyecto
cd miproyecto
mkdir kb
```

`kb/` es la carpeta de registros. KBOL guarda su estado local (el clon del integrador y los recibos) en `$KBOL_ESTADO/<repositorio>/`, por defecto `~/.kbol/<repositorio>/`.

## 2. La política: un rol y una persona

Quien aprueba es una persona que ocupa un rol. Los dos son registros, como las decisiones. Crea `kb/ROL-11111111-1111-4111-8111-111111111111.md`:

```markdown
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
```

Y `kb/PER-22222222-2222-4222-8222-222222222222.md`:

```markdown
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
```

Los IDs son `<PREFIJO>-<UUID v4>`; para los tuyos, genera un UUID nuevo. Todo registro nuevo lleva `eventos: []`, porque el historial lo escribe KBOL, y un `autor` con la forma `human:<alias>`, `process:<nombre>` o `cliente/modelo`. `kbol validar --modo propuesta <archivo>` dice si un registro está bien formado.

## 3. La instalación

`instalacion.json`, en la raíz, dice dónde están los registros y cómo se integra:

```json
{
  "carpeta_registros": "kb",
  "ambito": "miproyecto",
  "rama_canonica": "main",
  "integracion": {"remoto": "../origen.git", "repositorio": "miproyecto"}
}
```

`remoto` es la URL o la ruta de tu remoto canónico, y `repositorio`, el nombre de su estado local. Las demás claves (verificaciones, pasos tras integrar, modo de aprobación) están en [elecciones](elecciones.md#autoridad-e-integración).

Ignora el estado local que KBOL deja en el repositorio, y sube la base:

```bash
printf '.kbol/\n' > .gitignore
git add -A
git commit -m "kb: política inicial"
git remote add origin ../origen.git
git push origin main
```

## 4. La raíz de confianza

La primera persona no puede aprobarse a sí misma por la puerta, así que se activa una sola vez con `kbol arranque`. La rama canónica no puede tener checkout mientras KBOL escribe en ella: trabaja en otra rama.

```bash
git switch -c trabajo
cat > ../declaracion.json <<EOF
{"identidad": "declarada:ana", "sesion": "terminal de Ana", "instante": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "cita": "Soy Ana y arranco la raíz de confianza de miproyecto"}
EOF
kbol arranque . --rama-canonica main --carpeta kb --operacion-id arranque-1 \
  --base "$(git rev-parse main)" \
  --persona PER-22222222-2222-4222-8222-222222222222 \
  --roles ROL-11111111-1111-4111-8111-111111111111 \
  --declaracion ../declaracion.json --recibos ~/.kbol/miproyecto/recibos
git push origin main
git reset --hard main
```

La declaración es la cita de la persona que arranca: `identidad` tiene que ser el `identidad_ref` de su registro y `instante`, el momento real en que lo dijo. Se guarda fuera del repositorio. Es un mecanismo declarado, sin autenticar: KBOL deja constancia de lo que se dijo, pero no comprueba quién lo dijo ([mecanismos no conformes](elecciones.md#mecanismos-no-conformes)).

## 5. La primera decisión

Una decisión divide su texto en cláusulas, cada una con su ancla. Crea `kb/DEC-33333333-3333-4333-8333-333333333333.md`:

```markdown
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
```

Entra como propuesta. Lo que se pide es aceptarla, y eso se declara como efecto, en un archivo fuera del repositorio:

```bash
cat > ../efectos.json <<EOF
{"DEC-33333333-3333-4333-8333-333333333333": [{"estado_nuevo": "aceptada", "valido_desde": "$(date -u +%Y-%m-%dT00:00:00Z)"}]}
EOF
```

## 6. El ensayo: qué hay que aprobar

`kbol proponer` sin `--hasta` solo ensaya. Si falta una aprobación, termina con código 3 (`pendiente_de_aprobacion`) y devuelve el paquete de aprobación: qué cambia, su digest y el esqueleto de la aprobación.

```bash
kbol proponer . --instalacion instalacion.json --operacion-id decision-bd \
  --archivos kb/DEC-33333333-3333-4333-8333-333333333333.md \
  --efectos ../efectos.json > ../ensayo.json
```

`resultado.paquete.aprobaciones` trae el esqueleto con `base_mostrada` y los `digests` de lo que se aprueba. Se muestra a quien aprueba; con su respuesta, se completan `identidad`, `sesion`, `instante` (el momento real, posterior al arranque) y `cita` (sus palabras literales), y se guarda como `../aprobaciones.json`:

```json
[
  {
    "mecanismo": "declarada",
    "identidad": "declarada:ana",
    "sesion": "terminal de Ana",
    "instante": "2026-11-23T09:00:00Z",
    "cita": "Apruebo que la base de datos sea PostgreSQL",
    "base_mostrada": "<la del ensayo>",
    "digests": {"DEC-33333333-3333-4333-8333-333333333333": "<el del ensayo>"}
  }
]
```

Si el contenido cambia después de aprobarlo, el digest deja de coincidir y la puerta responde `APROBACION_CADUCADA`.

## 7. Integrar y subir

```bash
kbol proponer . --instalacion instalacion.json --operacion-id decision-bd \
  --archivos kb/DEC-33333333-3333-4333-8333-333333333333.md \
  --efectos ../efectos.json --aprobaciones ../aprobaciones.json --hasta subir
```

La puerta comprueba la forma, la mutabilidad frente a la base y que la persona ocupa el rol que autoriza la decisión; escribe los eventos de creación, ratificación y aceptación; confirma en el clon del integrador y sube sin forzar. El recibo queda en `$KBOL_ESTADO/miproyecto/recibos/`.

Tu archivo de trabajo sigue siendo el borrador, sin eventos. Sustitúyelo por lo integrado:

```bash
rm kb/DEC-33333333-3333-4333-8333-333333333333.md
git fetch origin
git reset --hard origin/main
```

## 8. Consultar

```bash
kbol consultar . --carpeta kb --ids DEC-33333333-3333-4333-8333-333333333333 \
  --valido-en "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --llano
```

```text
[APROBADA] «La base de datos es PostgreSQL»
  Rige entera a 23 nov 2026.
  Dice: La base de datos del proyecto es PostgreSQL 16.
  Aprobación de Ana Pérez, el 23 nov 2026, con estas palabras: «Apruebo que la base de datos sea PostgreSQL» (aprobación declarada, sin autenticar).
```

Sin el ID, `kbol buscar . --carpeta kb --consulta "base de datos" --valido-en … --llano` da la misma decisión como candidata. Sin `--llano`, toda orden devuelve un sobre JSON con lo que examinó y lo que no.

## Y después

- **Cambiar una decisión aceptada.** No se edita: una decisión nueva la modifica cláusula a cláusula (`modifica`) o la deja obsoleta entera (`deja_obsoleta`), y entra por la misma puerta. `kbol consolidar` muestra qué cláusulas rigen tras las modificaciones.
- **Con un agente de código.** `kbol exportar_skills .claude/skills` instala la skill de KBOL, y `kbol sesion . --evento inicio --instalacion instalacion.json --texto` da el contexto que un hook de arranque inyecta en la sesión.
- **Fuentes y citas.** Un hecho cita su fuente por líneas o por página; `kbol citas` e `kbol integridad` lo comprueban. Para PDF y otros documentos está `tools/di`.
- **Todas las órdenes**, en el [README](../README.es.md#uso).
