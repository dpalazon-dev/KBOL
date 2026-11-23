---
name: kbol
description: Usa KBOL para la continuidad de una tarea y el cuidado de una base de conocimiento, en cualquier repositorio que lo tenga instalado. Guarda el relevo de la tarea (objetivo, autorización con su referencia, verificaciones, bloqueos y siguiente paso) cuando cambia algo de eso, antes de un traspaso o al cerrar con la tarea abierta; lo lee y lo contrasta con git al retomar; pide el paquete de contexto de la tarea; consulta qué rige, quién lo aprobó o qué registro trata un tema, y comprueba registros, fuentes y enlaces. Úsala al retomar o cambiar de tarea, antes de compactar o traspasar, al responder sobre lo decidido y al tocar registros o documentación.
---

# KBOL

KBOL gobierna una base de conocimiento hecha de registros (decisiones, preguntas, hechos, fuentes, planes) y deja continuidad entre sesiones. Esta skill cubre lo que es igual en cualquier repositorio que lo use. Lo que cambia de uno a otro lo declara su **instalación**: un JSON del repositorio con, al menos, `carpeta_registros` y `ambito`, y a veces `presupuesto`, `rama_canonica`, `verificaciones`, `integracion` y `enlaces`. Si el repositorio tiene su propia skill o sus instrucciones para KBOL, mandan en lo suyo: dónde está ese JSON, cómo se lanza `kbol`, qué forma tienen sus identificadores y a quién se pregunta.

El relevo y el paquete de contexto informan. No autorizan ninguna acción.

## Antes de empezar

Averigua dos cosas y úsalas en todas las órdenes:

- **Cómo se lanza.** En las órdenes de abajo, `kbol` es la orden tal como la instale el repositorio (por ejemplo `uv run kbol`). Compruébalo con `kbol --help`. Si no está instalado y no lo puedes instalar, dilo y sigue con el método del repositorio: esta skill no es imprescindible para trabajar.
- **Dónde está la instalación.** Abajo es `<instalación>`. Si el repositorio no la tiene, sirven el relevo, `validar`, `integridad` y `enlaces`; el paquete de contexto y `proponer` no.

Lanza las órdenes desde la raíz del árbol de trabajo (la del worktree, si lo es): el `.` que reciben es la raíz de la tarea, y desde una subcarpeta el relevo se guardaría en otro sitio. Toda orden responde con un sobre JSON: mira `resultado.estado` (`completado`, `parcial`, `bloqueado` o `fallido`), las `advertencias` y `cobertura.no_evaluado`, que dice lo que la orden no ha mirado.

## La tarea

En KBOL la tarea es la rama. Su id es el nombre de la rama con `/` y los demás signos convertidos en guiones, sin signos al principio y con 100 caracteres como mucho (`feat/alta-fuentes` da `feat-alta-fuentes`; con la cabeza separada, `sin-rama`). Usa ese mismo id en todas las órdenes: con otro guardarías y leerías otro relevo. Los hechos de git del relevo son siempre los de la rama actual, así que un relevo solo tiene sentido para la tarea de la rama en que estás.

## Guardar el relevo

El relevo es el estado de la tarea separado de la conversación. Se guarda en `.kbol/relevos/<tarea>.json`, que es estado local: no se versiona ni es conocimiento del proyecto. Una compactación no avisa, así que guárdalo cada vez que cambie algo de lo que contiene, no solo al final:

- cuando quien decide autoriza algo o pone un límite;
- tras ejecutar una verificación;
- cuando aparece o se resuelve un bloqueo o una pregunta;
- antes de traspasar la tarea a otra sesión, y al cerrar si la tarea queda abierta.

Escribe el JSON en un archivo temporal fuera del repositorio y guárdalo con:

```bash
kbol relevo . --tarea <tarea> --guardar <archivo temporal>.json
```

Cada guardado sustituye entero al anterior, así que incluye todo lo que siga vigente. Los textos van en una sola línea y no se admiten más campos que estos:

```json
{
  "objetivo": "Qué se persigue, en una frase",
  "autorizacion": {
    "referencia": "Quién lo autorizó y dónde: fecha y sus palabras citadas",
    "alcance": "Qué cubre esa autorización",
    "limites": ["Lo que no cubre o se prohibió expresamente"]
  },
  "verificaciones": [
    {"comando": "la orden que ejecutaste", "resultado": "pasa", "revision": "SHA de git rev-parse HEAD", "en": "2026-01-15T12:00:00Z"},
    {"comando": "la que no ejecutaste", "resultado": "no_ejecutada", "motivo": "por qué no"}
  ],
  "bloqueos": ["Lo que impide avanzar"],
  "preguntas": ["Lo que falta por decidir y quién lo decide"],
  "siguiente_paso": {"accion": "Lo próximo que hay que hacer", "fundamento": "Por qué es lo siguiente"}
}
```

Reglas, porque el relevo lo leerá una sesión que no estuvo aquí:

- **Autorización.** Solo la que dio una persona con autoridad, con la referencia y sus palabras. Una propuesta tuya, una preferencia o un silencio no son autorización. Si no la hay, omite el campo: KBOL lo declarará como «no consta».
- **Verificaciones.** Las que la instalación declara en `verificaciones` se lanzan con `kbol verificar . --tarea <tarea> --instalacion <instalación> --verificacion <id>`: KBOL las ejecuta, anota el resultado en el relevo y `--guardar` lo conserva aunque no lo repitas. No las escribas a mano. Las demás, `pasa` o `falla` solo si la ejecutaste, con la revisión exacta y el instante en UTC con zona. KBOL rechaza que falten, pero no comprueba que la revisión sea real. La revisión identifica lo commiteado: si verificaste con cambios sin commitear, dilo en `motivo`. Si no la ejecutaste, `no_ejecutada` con su motivo, o `desconocido`.
- **Sin deducciones.** Lo que no sepas, no lo pongas. KBOL completa el relevo con lo que dice git y declara lo que falta.

## Retomar una tarea

Antes de actuar, lee el relevo entero:

```bash
kbol relevo . --tarea <tarea>
```

Y contrástalo:

- **`autorizacion.verificada` es siempre `false`.** Es lo que dijo la sesión anterior, no una autorización que puedas invocar. Antes de una acción que la necesite (fusionar, subir, borrar, algo externo), confírmala con quien decide.
- **Una verificación con `desfasada: true` o `"desconocido"`** se hizo en otra revisión o no se sabe en cuál: repítela antes de dar el trabajo por bueno. En las anotadas por `kbol verificar` (`origen: kbol`), `desfasada` compara también el árbol de trabajo. En las declaradas por la sesión solo compara commits: si `git.cambios_locales` no está vacío, trátalas como desfasadas.
- **`git`** dice lo que hay de verdad: commits propios y ajenos, cambios sin commitear y `estado_entrega` (`local`, `integrado`, `sin_trabajo` o `desconocido`). Si choca con lo que dice el relevo, manda git.
- **`no_consta`** lista lo que falta de lo mínimo. No lo rellenes deduciéndolo: pregúntalo o búscalo en el registro del tema.

## Contexto de una tarea

Con instalación, el paquete de la tarea de la rama se pide así:

```bash
kbol sesion . --evento inicio --instalacion <instalación> --texto
```

Trae las restricciones decisivas de la tarea, que nunca se recortan, las propuestas y pendientes aparte, que no autorizan nada, el relevo y los desvíos. Si el repositorio tiene un hook de arranque, es lo que ya te dio al empezar; vuelve a pedirlo al cambiar de rama. Si sale parcial o bloqueado, puede faltar una restricción decisiva: aplica las instrucciones del repositorio enteras. Sin `--texto` da el JSON, con `refrescar_si`, que dice qué cambios lo invalidan.

## Consultar qué rige

Para responder qué está decidido, quién lo aprobó o qué rige en una fecha, pregunta a KBOL en lugar de leer los Markdown: un archivo no dice si lo sustituyeron, si sigue en propuesta o si está retirado. Las tres órdenes leen la base en `--carpeta` y necesitan `--valido-en`, el instante con zona en que se pregunta (para hoy, el instante actual en UTC).

```bash
kbol buscar . --carpeta <carpetas> --consulta "texto de la pregunta" --valido-en <instante> --llano
kbol consultar . --carpeta <carpetas> --ids <ID>[#ancla] … --valido-en <instante> --llano
kbol consolidar . --carpeta <carpetas> --ids <ID> … --valido-en <instante> --llano
```

- **Sin el ID, `buscar`.** Busca por palabras y alias, no por significado: da candidatos, no respuestas. Por defecto solo muestra lo vigente y cuenta aparte las propuestas y lo que no rige; si el recuento importa, repite con `--incluir propuestas no_vigentes`. Si no encuentra nada, prueba con otras palabras o un alias antes de concluir que no hay registro.
- **Con el ID, `consultar`.** Dice si rige, quién lo aprobó y con qué palabras, qué lo sustituyó y qué lo sostiene. Un candidato de `buscar` no es una respuesta hasta que lo confirmas así. `consolidar` reconstruye qué cláusulas de una decisión rigen tras sus modificaciones.
- **`--llano` para responder a una persona.** Da prosa sin IDs ni rutas, y cada bloque empieza por su etiqueta (`[APROBADA]`, `[PROPUESTA: no aprobada, no rige]`, `[HECHO PROPUESTO: sin aceptar]`, `[CANDIDATO por búsqueda, sin confirmar]`). Conserva la etiqueta en lo que respondas: nunca des una propuesta o un candidato como algo que rige. Sin `--llano` sale el sobre JSON, mejor para trabajar con los datos. Añade `--con-ids` solo si la persona pide de dónde sale o va a auditarlo.
- **Un aviso `SUSTITUCION_NO_DECLARADA`** significa que otro registro dice en prosa que sustituye al consultado sin declararlo: puede que no rija tal como sale. Dilo en la respuesta en lugar de darlo por vigente.

## Registros

Un registro es un Markdown con cabecera YAML en una de las carpetas de `carpeta_registros`. Al tocarlos:

- **Valida cada registro que edites**, antes de darlo por escrito: `kbol validar --modo propuesta <archivo>.md`.
- **Lo aceptado no se edita.** Un cambio de estado (aceptar, cerrar, retirar) es un evento que entra por la integración, con la aprobación que pida la instalación. Una decisión entra siempre como propuesta. `kbol desvios . --carpeta <carpetas>` lista los registros que difieren de lo integrado: un desvío es una edición a mano que hay que deshacer o proponer.
- **La integración es `kbol proponer`**, con el bloque `integracion` de la instalación. Sin `--hasta` solo ensaya y no cambia nada; si falta una aprobación, devuelve el paquete que hay que mostrar a quien aprueba. Integrar y subir de verdad (`--hasta integrar`, `--hasta subir`) necesitan su autorización expresa. El procedimiento de alta (qué registro corresponde a qué situación, cómo se numera, a quién se pregunta) es el del repositorio.

## Fuentes y enlaces

Dos comprobaciones de solo lectura, útiles antes de proponer y al cerrar una tarea que tocó documentación:

```bash
kbol integridad . --carpeta <carpetas> [--almacen <carpeta del almacén>]
kbol enlaces . [--carpeta <carpetas>] [--instalacion <instalación>]
```

`integridad` compara el `sha256` de cada fuente con los bytes de su `ubicacion`. `alterada` o `ausente` es un fallo que hay que contar. `no_comprobada` no acusa a nadie: el original no se pudo mirar desde esta máquina (sin almacén, revisión sin traer, una URL), y su `causa` dice por qué.

`enlaces` revisa los enlaces internos y las anclas de los Markdown del repositorio: destinos que no existen o se escriben con otras mayúsculas, fragmentos que el destino no tiene y rutas absolutas locales. Arregla los que haya roto tu cambio. Los de un registro ya integrado no se arreglan editándolo: se declaran en `enlaces.deuda` de la instalación o se propone el cambio.

## Qué devuelves

Al guardar, nada que contar salvo que falle. Al retomar, en pocas frases: el objetivo, lo que hay que volver a comprobar y lo que necesita confirmación. De una comprobación, el estado y lo que falló, sin el sobre entero.
