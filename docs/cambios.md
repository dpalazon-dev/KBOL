---
type: Especificación
title: Cambios incompatibles de KBOL
description: "Notas de los cambios de esquema o de comportamiento de la CLI de KBOL que pueden romper a quien los consume: por qué se hacen, a quién afectan, qué ocurre y cómo migrar."
clase: fijo
estado: Borrador
status: draft
---

# Cambios incompatibles de KBOL

Todo cambio de esquema o de comportamiento de la CLI se clasifica en una de tres clases :

- **Seguro.** Quien consume KBOL no nota nada: no cambia ninguna salida que dependa de él. No lleva nota.
- **Potencialmente incompatible.** Cambia algo que un consumidor puede estar leyendo (un campo nuevo, un aviso nuevo, un resultado que antes no aparecía) pero no rompe a quien lo ignora con cuidado. Lleva nota.
- **Incompatible.** Un consumidor correcto con la versión anterior puede dejar de serlo (un código de salida, un campo retirado o con otro significado). Lleva nota.

Cada nota usa la misma plantilla:

- **Por qué.** El motivo del cambio.
- **A quién afecta.** Qué consumidores lo notan.
- **Qué ocurre.** El comportamiento anterior y el nuevo.
- **Cómo migrar.** Qué debe cambiar el consumidor.

Las notas van de la más reciente a la más antigua.

## Sin publicar: `buscar`, aviso de sustitución no declarada y `--llano`

Clase: potencialmente incompatible.

- **Por qué.** Sin el ID de un registro no había forma de llegar a él, y una decisión sustituida en parte solo en prosa salía vigente entera sin aviso.
- **A quién afecta.** A quien lea las advertencias de `consultar` y `consolidar`, o los campos de `consultar`; a quien valide la lista de operaciones de la CLI.
- **Qué ocurre.** Nueva orden `buscar` (`--consulta`, `--incluir propuestas no_vigentes`, `--limite`): candidatos por texto, en memoria y sin índice, con su ID, ancla, estado, vigencia y fragmento; por defecto solo lo vigente. `consultar` y `consolidar` añaden la advertencia `SUSTITUCION_NO_DECLARADA` cuando un registro dice sustituir o derogar al consultado (o el consultado a otro) sin declararlo en `modifica` ni en `deja_obsoleta`; no cambia la vigencia ni el código de salida. `consultar` añade `relaciones_inversas` (`dejada_obsoleta_por`, `modificada_por`) y `avisos_sustitucion`. `--llano` presenta `consultar`, `consolidar` y `buscar` en prosa, sin IDs salvo con `--con-ids`; la salida deja de ser JSON.
- **Cómo migrar.** Nada, salvo quien trate toda advertencia como fallo: la nueva es un indicio léxico que no bloquea.

## Sin publicar: aprobaciones con su detalle en `consultar` y `consolidar` con ancla

Clase: potencialmente incompatible.

**Por qué.** Dos fallos de lo que KBOL ya hacía. «¿Quién aprobó X?» no salía de `consultar`, que solo daba el ID de la aprobación aunque el registro conserva la persona, el instante y la cita. Y `consolidar --ids ID#ancla` daba la cláusula por ausente.

**A quién afecta.** A quien lea `resultado.resultados[].autoridad` de `consultar` como lista cerrada de campos, y a quien llame a `consolidar` con anclas.

**Qué ocurre.**

| Dónde | Antes | Ahora |
|---|---|---|
| `consultar`, `autoridad` | `ratificaciones` y `declaradas` como lista de ID | Además `aprobaciones`: por cada ratificación vigente, `aprobacion_id`, `actor`, `roles`, `aprobada_en`, `mecanismo`, `cita` y `autenticada`; lo que el comprobante no trae va en `null`. Sigue `comprobada: false` |
| `consolidar --ids ID#ancla` | La referencia en `ausentes` y el resultado `parcial` | Solo esa cláusula, con su cadena; la `vigencia` es la de la decisión. Un ancla que la decisión no tiene sigue en `ausentes` |

**Cómo migrar.** Quien valide `autoridad` como lista cerrada debe admitir `aprobaciones`. Quien contara con que `consolidar` rechaza las anclas no tiene que hacer nada más: el resultado con ancla es un subconjunto del de la decisión entera.

## 0.11.0: commits fuera del flujo en `desvios`, `kbol exportar_skills` y `tools/di` en la comprobación local

Clase: potencialmente incompatible en `desvios`; seguro lo demás.

**Por qué.** Higiene de garantías. La puerta única dependía de la disciplina: ahora un test cuenta en `kbol/` las órdenes de git que mueven referencias y `desvios` señala los commits de la rama canónica que cambian registros sin pasar por la puerta. Las skills pasan a ser datos del paquete, para que cada instalación reciba la de su versión. La comprobación local incluye los tests de `tools/di`. El detalle está en elecciones, «Huellas y desvíos», «Skills empaquetadas» y «Cero examinados y comprobación local».

**A quién afecta.** A quien lea el resultado de `kbol desvios` con `--rama-canonica`: aparece el campo `commits_fuera_del_flujo` y, si hay alguno, avisos nuevos; el código de salida no cambia. A quien edite las skills de KBOL: la fuente está ahora en `kbol/skills/` y `.claude/skills/` es una exportación. A quien ejecute `tools/comprobar.py` sin `--rapido`: tarda más, porque sincroniza y ejecuta el proyecto de `tools/di`.

**Qué ocurre.**

| Dónde | Antes | Ahora |
|---|---|---|
| `desvios --rama-canonica` | Solo registros editados a mano | También `commits_fuera_del_flujo`, con aviso por commit; `cobertura.no_evaluado` dice qué parte de la historia no se miró |
| `desvios` sin `--rama-canonica` | — | `no_evaluado` incluye «commits de la rama canónica» |
| Skills `kbol` e `incorporar-documento` | Solo en `.claude/skills/` de este repositorio | En `kbol/skills/`, dentro de la rueda; `kbol exportar_skills DESTINO` las escribe con la versión |
| `tools/comprobar.py` | Sin `tools/di`; `desvios` sin rama | Con los tests de `tools/di` (no con `--rapido` ni `--sin-di`); `desvios --rama-canonica main`, que falla con commits fuera del flujo |

**Cómo migrar.** Quien lea `desvios` como lista cerrada de campos debe admitir `commits_fuera_del_flujo`. Una instalación que copió la skill a mano puede sustituirla con `kbol exportar_skills .claude/skills`; si su copia no lleva la marca de exportación, la orden se niega a pisarla y hay que borrarla antes.

## 0.10.0: citas por líneas contra la representación, `kbol integridad`, `kbol enlaces` y skill `kbol`

Clase: incompatible en `integridad`, que deja de devolver `bloqueado`; potencialmente incompatible en las citas; seguro lo demás.

**Por qué.** Tres trabajos que quedaron fuera de `main` se recuperan en una sola versión. Un Word, una hoja de cálculo o una página HTML no tienen páginas físicas y no se pueden citar con `pdf-v1`: su representación común es un Markdown derivado (de Docling o de MarkItDown) y lo natural es citarlo por líneas, pero `lines-v1` solo se resolvía contra el original, que en estos formatos no es texto. La operación `integridad` del contrato estaba reservada y sin habilitar; se habilita en parte: comprueba, no recuerda. `kbol enlaces` es una orden nueva para los enlaces de cualquier Markdown del repositorio, y la skill `kbol` (`.claude/skills/kbol`) lleva la continuidad de una tarea y el cuidado de la base a cualquier repositorio que tenga KBOL instalado. El detalle está en elecciones, «Integridad de las fuentes» y «Enlaces de la documentación».

**A quién afecta.** A quien escriba o lea citas `lines-v1` que lleven `representacion_id`. A quien llamara a `kbol integridad` y contara con `bloqueado` (2). `enlaces` y la skill son nuevos y no cambian ninguna salida anterior.

**Qué ocurre.**

| Dónde | Antes | Ahora |
|---|---|---|
| Cita `lines-v1` sin `representacion_id` | Líneas del original | Igual |
| Cita `lines-v1` con `representacion_id` | Líneas del original; `representacion_id` se ignoraba | Líneas de la representación, que debe ser de texto (`formato: text/…`) y derivar del original por `derivada_de`, directamente o en cadena; `rota` si no |
| Cita por líneas con el original ausente del almacén | — | `no_comprobable` con «representación conforme; original no disponible», como en un PDF |
| `kbol integridad` | `bloqueado` (2): operación no habilitada | Compara el `sha256` de cada fuente con los bytes de su `ubicacion` (`almacen:sha256/…` con `--almacen`, `git:<sha>:<ruta>` o una ruta de la raíz). `fallido` (1, `INTEGRIDAD_ROTA`) si alguna está alterada o ausente; `parcial` (3, `INTEGRIDAD_NO_COMPROBADA`) si alguna quedó sin comprobar, y también sin ninguna fuente o con registros que no cargaron; `bloqueado` (2) solo con la base incoherente |
| `kbol enlaces` | No existía | Revisa rutas internas, fragmentos y anclas de los `.md`; `fallido` (1, `REFERENCIA_AUSENTE`) con algún enlace roto, `parcial` (3) si no revisó ningún documento o alguno no es UTF-8. La instalación declara en `enlaces` lo que no se revisa (`excluir`) y la deuda que no bloquea (`deuda`) |
| Operaciones no habilitadas | `ingerir` e `integridad` | Solo `ingerir` |

**Cómo migrar.** Nada para las citas existentes. Para citar un documento sin páginas: registra el original, la derivación en Markdown con `derivada_de` hacia él (o hacia la derivación intermedia) y `formato: text/markdown`, y cita `lines-v1:<ini>-<fin>` con `representacion_id` y la cita literal en `contexto`. Quien trate el código 2 de `integridad` como «no disponible» debe leer ahora el estado: 1 es una fuente rota y 3, una sin comprobar. `integridad` no guarda la última comprobación y las consultas no la usan: `disponible_con_integridad` sigue fallando cerrado.

## 0.8.0: formato heredado configurable por instalación

Clase: potencialmente incompatible.

**Por qué.** La lectura compatible llevaba cableado un solo formato heredado y daba por inválidos los registros de proyectos que solo difieren en los IDs y en algunas palabras de estado. Una instalación puede ahora declarar su formato heredado (elecciones, «Formato heredado de otro proyecto»).

**A quién afecta.** A quien pase `--instalacion` a una consulta o a `migrar`, a quien lea `relaciones_propuestas` de una pregunta heredada que trae el campo `resuelta_por` y a quien llame como biblioteca a `snapshot.cargar` o `migracion.inspeccionar`. Sin `formato_heredado`, el resultado es el mismo que con 0.7.0.

**Qué ocurre.**

| Dónde | Antes | Ahora |
|---|---|---|
| `--instalacion` en `consolidar`, `listos`, `consultar`, `soporte`, `vocabulario` y `migrar` | Se ignoraba | Se lee su `formato_heredado`; si falta, el formato por defecto. Mal formada o ilegible, `fallido` (1, `ESQUEMA_INVALIDO` o `REFERENCIA_AUSENTE`) |
| `preparar_contexto` | Leía los heredados con el formato por defecto | Con el que declare la instalación; uno mal formado la hace fallar como cualquier instalación mal formada |
| Pregunta heredada «Resuelta» con campo `resuelta_por` | La candidata salía solo del texto del estado | Sale primero del campo y después del texto |
| `snapshot.cargar`, `migracion.inspeccionar` e `inspeccionar_carpeta` | Sin parámetro de formato | Parámetro opcional `formato` (`migracion.formato_de`); sin él, el formato por defecto |
| `snapshot.NOMBRE_DE_REGISTRO` | En `snapshot` | En `migracion`, como parte del formato por defecto |

**Cómo migrar.** Nada, salvo que se pasara `--instalacion` a una consulta con una instalación que no sea JSON válido, o que se importara `NOMBRE_DE_REGISTRO` desde `snapshot`.

## 0.7.0: vocabulario del dominio

Clase: potencialmente incompatible.

**Por qué.** La clase de una entidad era texto libre y ningún módulo la contrastaba: un término inventado o escrito de dos formas solo se descubría tarde. Las decisiones pueden ahora declarar los términos del dominio con `define`, y la puerta no deja pasar a `activa` una entidad cuya clase no rige (elecciones, «Vocabulario del dominio»).

**A quién afecta.** A una instalación que declare vocabulario, a quien lea los recibos y los paquetes de aprobación, a quien lea las relaciones de `consultar` y a quien llame a `integrar.arbol_final` como biblioteca. Una instalación sin ningún `define` que rija se comporta igual que antes: mundo abierto.

**Qué ocurre.**

| Dónde | Antes | Ahora |
|---|---|---|
| Esquema de una decisión | `define` es un campo no declarado | Relación `define`: lista de `{clausula, termino, clase, descripcion, alias?}` |
| `integrar`, efecto que lleva una entidad a `activa` | Integra | Con vocabulario declarado, `bloqueado` (2, `ESQUEMA_INVALIDO`) si su clase no rige en el inicio de validez del efecto o al integrar |
| `integrar`, recibo | Sin avisos de vocabulario | `advertencias` avisa de la clase y el ámbito de los registros tocados y de las entidades cuyo término deja de regir |
| `preparar_aprobacion` | Sin vocabulario | Bloquea como la puerta; clave `vocabulario` con los hallazgos y, si los hay, la sección «Vocabulario del dominio» en `--texto` |
| `consultar`, `relaciones` | Sin `define` | Incluye `define` de una decisión que lo declara |
| `integrar.arbol_final` | Devuelve `(final, advertencias)` | Devuelve `(final, advertencias, vocabulario)` |
| Orden `vocabulario` | No existe | Nueva consulta de solo lectura |

Ningún consumidor correcto con 0.6.0 ve otro código de salida: el bloqueo solo aparece cuando rige un `define`, que 0.6.0 rechazaba en el esquema.

**Cómo migrar.** Nada mientras no se declare vocabulario. La primera decisión con `define` cierra la clase para toda la instalación: declara en ella también las clases que ya usan las entidades, y después `kbol vocabulario` lista como no declaradas las que falten, con sus usos. Quien llame a `arbol_final` desempaqueta tres valores.

## 0.4.1: códigos de salida cuando no se examinó nada

Clase: incompatible.

**Por qué.** Una operación que no examinó nada terminaba `completado` (0) y se leía como «todo en orden». Un fallo de `verificar` tampoco se distinguía de un éxito por su código. Un 0 debe significar que se examinó lo que se pidió y salió bien (elecciones, «Cero examinados y comprobación local»).

**A quién afecta.** A cualquier hook o script que lea los códigos de salida de `kbol`.

**Qué ocurre.**

| Operación | Caso | Antes | Ahora |
|---|---|---|---|
| `listos` | Sin hitos | `completado` (0) | `parcial` (3) |
| `consolidar` | IDs pedidos ausentes | `completado` (0) | `parcial` (3) |
| `citas` | Cero filas | `completado` (0) | `parcial` (3) |
| `citas` | La carpeta no existe | `completado` (0) | `fallido` (1) |
| `desvios` | Cero registros comprobados, o algún registro que no se pudo leer | `completado` (0) | `parcial` (3) |
| `desvios` | Base incoherente (ID repetido o ciclo prohibido) | `completado` (0) | `bloqueado` (2) |
| `migrar` | Ningún registro heredado propuesto | `completado` (0) | `parcial` (3) |
| `preparar_contexto` | Sin registros en el ámbito | `completado` (0) | `parcial` (3) |
| `verificar` | La verificación falla | `completado` (0) | `fallido` (1) |
| `verificar` | El resultado se desconoce | `completado` (0) | `parcial` (3) |

**Cómo migrar.** Trata el 3 como «respuesta con límites»: no es un error ni un éxito pleno. Lee `advertencias` y `cobertura` para saber qué no se examinó y decide según el caso. Si tu script solo acepta el 0, acepta también el 3 donde un resultado vacío sea legítimo, y revisa los avisos donde no lo sea. Un 1 de `verificar` o de `citas` es ahora un fallo real.

## 0.5.0: evidencia de `consultar` y dependencias con sucesora indecidible

Clase: incompatible.

**Por qué.** `consultar` daba por suficiente una cita cuyo destino existía, aunque ya no rigiera. La consulta `soporte` define qué apoyos tiene un registro y si rigen en el corte, y `consultar` usa esa misma regla. Además, una dependencia hacia un hecho con una sucesora cuyo inicio no se puede decidir se daba por satisfecha con un aviso.

**A quién afecta.** A quien lea el bloque `evidencia` de `consultar` y a quien dependa de `listos` o de una dependencia `aceptada_y_vigente` hacia un hecho con sucesora.

**Qué ocurre.**

| Dónde | Antes | Ahora |
|---|---|---|
| `consultar`, bloque `evidencia` | `{citas: {ref: existe}, suficiente}` con `basada_en` y las citas del cuerpo | `{apoyos: [{ref, campo, situacion, motivo, existe}], suficiente, motivo?}`, también con `dependencias` y `sources` |
| `consultar`, `suficiente` | Verdadero si todos los destinos existen | Verdadero solo si todos los apoyos rigen en el corte |
| Dependencia `aceptada_y_vigente` hacia un hecho con sucesora de inicio ambiguo | Satisfecha, con aviso | No satisfecha: `TIEMPO_AMBIGUO` |

**Cómo migrar.** Lee `evidencia.apoyos` en lugar de `evidencia.citas`; la clave `citas` ya no existe. Un `suficiente` falso puede deberse ahora a un apoyo que existe y no rige: su `motivo` lo dice. Para ver todos los apoyos de la base de una vez, usa `kbol soporte`.
