---
type: Referencia
title: "Sistema documental y base de conocimiento: guía de implementación"
description: "Contrato KB-DPP preservado para la instalación."
clase: fijo
estado: Borrador
status: draft
---

# Sistema documental y base de conocimiento: guía de implementación

**Versión:** 0.8 · **Estado:** referencia de implementación del sistema objetivo · **Fecha:** 3 nov 2026 · **Documento complementario:** [Núcleo 0.7](KB-DPP-nucleo.md)

Esta guía especifica una implementación completa por incrementos, con contratos, modelo normativo incorporado, escenarios y criterios de entrega. No declara qué está desplegado en un proyecto. No autoriza acciones sobre repositorios o servicios por contener ejemplos de ellas. Cada instalación documenta sus elecciones, responsables, versiones, evidencias y límites.

La unidad de avance es un recorrido que funciona: una persona o agente resuelve una tarea, la escritura pasa los controles requeridos, el resultado se integra y se observa su coste. Un documento aprobado, una rama preparada o una suite verde no equivalen por sí solos a una capacidad en uso.

## Contrato de lectura y resultados

Este documento es una referencia primaria del sistema objetivo, no una revisión de antecedentes ni un inventario de recomendaciones. Contiene las reglas necesarias para comprender y ejecutar su propósito sin recuperar conversaciones, informes de investigación o decisiones de una instalación concreta. Las decisiones de diseño que formula son el punto de partida; los parámetros propios de cada instalación se completan con datos reales.

**DEBE** expresa una condición de conformidad; **NO DEBE**, una prohibición; **POR DEFECTO**, una elección que solo se cambia mediante una diferencia registrada y evaluada; **OPCIONAL**, una capacidad que no se exige mientras no se anuncie. «Se conserva», «se valida», «requiere» y las condiciones de las tablas son requisitos, salvo que el texto los identifique como ejemplo o alternativa.

El núcleo responde qué sistema se quiere, cómo se comporta y qué resultados debe producir. La implementación responde cómo materializar ese comportamiento, en qué orden y con qué evidencia. Cada archivo contiene el contrato necesario para su responsabilidad. Los enlaces entre ambos facilitan navegación, pero no son precondiciones de lectura. La implementación incorpora una reproducción versionada de las reglas normativas necesarias; no puede redefinirlas. Toda actualización conjunta compara esos bloques para evitar divergencias.

La referencia de diseño y el estado construido son cosas distintas. Un requisito aquí escrito no se convierte en capacidad implementada hasta que su prueba y su uso lo acreditan. La conformidad se declara por resultado y alcance, nunca por la mera presencia de estos documentos.

| Resultado | Comportamiento observable | Evidencia mínima para declararlo conseguido |
| --- | --- | --- |
| RES-01. Conocer qué rige | Una consulta distingue cláusulas vigentes, sustituidas y propuestas, conserva condiciones y muestra autoridad. | Casos de sustitución total, parcial, futura y conflictiva con salidas esperadas. |
| RES-02. Cambiar conocimiento con control | Solo se integra como aceptado el contenido aprobado por la autoridad correspondiente. | Rechazo de aprobación ficticia, contenido cambiado y autoampliación de permisos; recibo de una aceptación válida. |
| RES-03. Retomar trabajo | Una sesión reconstruye objetivo, autorización, restricciones, pendientes y siguiente paso sin presentar propuestas como hechos. | Interrupción y reanudación de una tarea real con cambios aún no integrados. |
| RES-04. Responder con evidencia | Una respuesta llega a la fuente y representación utilizadas, conserva condiciones y declara insuficiencia cuando falta evidencia decisiva. | Preguntas revisadas, citas resolubles, contraste con fuentes y prueba de ablación. |
| RES-05. Mantener coherencia | Una actualización identifica consumidores afectados y conserva la historia sin modificar derivaciones antiguas. | Cambio de fuente, resolución de impacto y comparación de consultas actuales e históricas. |
| RES-06. Operar y recuperarse | Un fallo parcial no duplica efectos ni se declara éxito; una restauración recupera un conjunto consistente. | Reintento idempotente, reconciliación y restauración con consultas y citas comprobadas. |
| RES-07. Ahorrar esfuerzo sin perder corrección | Las tareas representativas requieren menos tiempo humano total o justifican su coste mediante una mejora de corrección acordada. | Comparación con línea base, mantenimiento incluido, revisión de errores tardíos y límites de calidad satisfechos. |

Los resultados son la unidad de priorización y de aceptación. Cada incremento declara qué RES entrega, qué escenarios cubre y qué evidencia falta. Los módulos, documentos y tests son medios para producir esos resultados. Ninguna mejora de velocidad compensa una aceptación no autorizada, una condición decisiva omitida o una exposición de datos fuera del alcance permitido.

**Recorrido inicial completo.** Capturar una fuente textual → proponer una decisión sustentada en ella → revisar y ratificar su contenido → integrar → consultar qué rige → proponer y aceptar una modificación parcial → consultar el consolidado y su historia → interrumpir y reanudar el trabajo → registrar el coste humano. Este recorrido permite comprobar RES-01 a RES-05 sin necesitar ingesta multimodal ni varios escritores. RES-06 se comprueba antes de confiar en la instalación; RES-07 requiere uso sostenido.

**Parámetros que requieren información de la instalación:** personas y ámbitos reales, canales de identidad, clasificación de datos, herramientas disponibles, presupuesto, volumen, tareas y línea base. La ausencia de un parámetro crítico bloquea solo la capacidad que depende de él. No se rellena con una suposición ni se exige decidir toda la evolución futura antes de empezar.

**Política ante contradicciones de diseño.** Los contratos normativos tienen prioridad sobre ejemplos, recomendaciones de herramienta y parámetros locales. Si dos requisitos normativos son incompatibles, se registra el conflicto y se corrige la referencia antes de implementar ese comportamiento. El código, una fuente externa o una conversación no sustituyen silenciosamente el contrato.


## 1. Alcance del primer incremento

Antes de elegir herramientas, completar una ficha breve con:

| Dato | Qué debe quedar decidido |
| --- | --- |
| Usuarios y tareas | Quién necesita qué; tres tareas prioritarias con ejemplos reales. |
| Problema observable | Error o fricción, ejemplo concreto, frecuencia conocida o pendiente de medir. |
| Perfil inicial | Gobierno operativo, conocimiento documental o ambos; contratos habilitados. |
| Corpus y volumen | Fuentes, formatos, número de registros, crecimiento previsto y alcance excluido. |
| Acceso | Quién puede leer qué; si todos leen todo, qué material queda fuera. |
| Autoridad | Quién ratifica cada ámbito, quién administra controles y cómo se acredita identidad. |
| Escritores y clientes | Número de ejecutores, herramientas, caminos de escritura y sincronización. |
| Línea base | Cómo se resuelven hoy las tareas, coste humano completo, errores y evidencia disponible. |
| Operación | Presupuesto técnico y humano, tiempos de respuesta, respaldo y responsable de incidentes. |
| Criterio de continuidad | Qué resultado permite ampliar, simplificar o abandonar el incremento. |

Los objetivos de mejora se fijan después de tomar la línea base y antes de evaluar el cambio. Las restricciones de autorización, integridad e aislamiento se exigen desde que se habilita el camino correspondiente. No se inventan porcentajes de ahorro ni se adopta una tecnología por una cifra de un benchmark ajeno.

El primer piloto puede limitarse a un proyecto, un cliente, un escritor y un grupo con acceso común. Esa limitación es un perfil operativo explícito, no una promesa de que varios escritores o permisos parciales ya funcionan.

<a id="cómo-se-decide"></a>
<a id="casa-del-sistema-y-mapa-de-dueños"></a>
## 2. Fuente de diseño, versiones y decisiones

### Mapa de dueños

| Contenido | Dueño recomendado |
| --- | --- |
| Propósito, semántica, invariantes y garantías | Núcleo versionado. |
| Esquemas serializados, contratos de consulta, proyección y catálogo de errores | Especificación ejecutable del sistema, alineada con el núcleo. |
| Herramientas, rutas, valores operativos y capacidades activadas | Documento de instalación. |
| Autoridad y vocabulario de negocio | Registros y configuración del proyecto. |
| Estado desplegado y resultados de pruebas | Manifiesto de versión y evidencia de entrega. |
| Material de investigación y antecedentes | Fuentes conservadas, sin fuerza normativa automática. |

No se mantienen dos definiciones independientes de una regla. Los bloques normativos reproducidos para autocontención conservan el mismo texto y versión en ambos documentos; su edición se sincroniza. Los ejemplos se comprueban contra el contrato incluido. Los conflictos entre documentos se resuelven antes de implementar la regla afectada.

El sistema se distribuye como paquete o repositorio versionado. Cada proyecto fija una versión reproducible y declara diferencias compatibles. Una copia citada por revisión puede servir como transición, con comprobación de divergencia. Separar la fuente común no exige publicar un servicio ni detener el uso existente.

El manifiesto de entrega identifica: versión de núcleo, esquema, comprobador, adaptador, perfil de intercambio, política de autoridad y revisión de datos migrados. Una modificación del núcleo no actualiza automáticamente instalaciones antiguas.

### Registro de elecciones

Cada elección discrecional relevante conserva opciones, criterios, motivo, consecuencias y condición de revisión. Una corrección demostrada puede justificar por qué no existe alternativa razonable. Las decisiones se agrupan para ahorrar atención, manteniendo visible el esfuerzo y los cambios individuales.

Antes de adoptar una recomendación de una fuente, registrar si es observación local, resultado externo contrastado, hipótesis o preferencia. Si una cifra externa decide la arquitectura, verificar fuente primaria, condiciones y localizador. Las fuentes históricas no se editan para hacerlas concordar con el diseño posterior.

## 3. Arquitectura y selección de herramientas

**Punto de partida:** archivos canónicos, Git, una biblioteca de dominio, un ejecutable de consultas/validación y adaptadores finos. Separar dentro del programa:

- Lectura y validación sintáctica.
- Modelo de registros, eventos y relaciones.
- Política de autoridad y comprobación de aprobaciones.
- Resolución temporal, cláusulas e impacto.
- Consultas y ensamblado de contexto.
- Generación de vistas y exportaciones.
- Ingesta y comprobación de originales.
- Ejecución aislada de verificaciones.
- Telemetría y evaluación.

Son responsabilidades, no servicios obligatorios. No se crea una abstracción por anticipación: se separa lo que permite probar y cambiar contratos sin mezclar permisos, lectura y ejecución.

| Necesidad | Inicio razonable | Condición para ampliar |
| --- | --- | --- |
| Consultas normativas | Cabeceras y eventos cargados en memoria; caché por revisión si hace falta. | Latencia o coste de carga medidos por encima del presupuesto. |
| Recorrido de relaciones | Estructuras de adyacencia; biblioteca de grafos si reduce código y mantenimiento. | Consultas necesarias que exceden el recorrido implementado. |
| Patrón y agregación | Consulta sobre el modelo cargado. | Vista relacional embebida si simplifica consultas o mejora rendimiento medido. |
| Descubrimiento textual | Texto y alias con filtros de ámbito. | Índice léxico cuando el coste o los fallos lo justifiquen. |
| Descubrimiento semántico | No obligatorio. | Candidatos por similitud cuando mejoren cobertura sobre un conjunto evaluado. |
| Validación de esquemas | Esquema formal y validador mantenido o código propio pequeño. | Elegir por coste total; no excluir bibliotecas de validación por principio. |
| Procesamiento documental | Un motor adecuado al corpus piloto y parsers nativos necesarios. | Otro procesador solo para fallos o costes de formatos concretos. |
| Orquestación | Ejecución explícita y trabajos simples. | Colas o coordinador cuando concurrencia, reintentos o volumen lo exijan. |

Las vistas llevan revisión origen, versión de generador y política. Se reconstruyen sin llamadas a un modelo cuando representan datos deterministas. Un resumen generado por IA no es una vista determinista: es una síntesis versionada con procedencia y revisión.

<a id="esquema-concreto"></a>
## 4. Contrato de registros y formato

### Identidad y paquete

La instalación fija prefijos y un generador de IDs sin colisiones prácticas: UUID/ULID o identificadores distribuidos equivalentes; los IDs heredados pueden conservarse. No se exige continuidad numérica. La identidad no cambia al mover archivos ni al integrar ramas. Los nombres de archivo y alias se validan sin convertir una renumeración en requisito de fusión.

La raíz del paquete de conocimiento se separa de instrucciones, README y archivos operativos que no sean conceptos. El perfil operativo está definido íntegramente aquí. Implementarlo no requiere leer OKF ni otro estándar externo. La compatibilidad completa con un formato externo se trata como adaptador opcional, se fija a una versión y se prueba antes de anunciarla.

Los metadatos comunes del perfil propio incluyen identidad, tipo, clase documental, título, descripción, ámbito, estado materializado, eventos y procedencia. Las fechas de evento usan ISO 8601 con zona; la precisión original de fechas históricas se conserva. `fecha` heredada no se convierte silenciosamente en un instante exacto.

### Estados y transiciones mínimas

Esta tabla define el contrato de referencia. El esquema distingue estados iniciales, transiciones y actor autorizado; no se limita a validar una lista de palabras.

| Tipo | Estados escritos admitidos | Condición relevante |
| --- | --- | --- |
| Decisión | propuesta, aceptada, rechazada | Aceptar exige aprobación; después de aceptada, cambios normativos mediante sucesión. |
| Hecho | propuesta, aceptada, rechazada | Aceptado significa admitido bajo una política de evidencia, no certeza factual. |
| Pregunta | abierta, resuelta, descartada | Cierre normativo por decisión; cierre factual con evidencia y revisión; descarte motivado. |
| Hipótesis | abierta, validada, refutada, retirada | Resultado con protocolo y evidencia; «validada» se limita a condiciones probadas. |
| Supuesto | activo, retirado | Lleva revisión; su caducidad se deriva. Convertirlo en hipótesis o hecho requiere registro trazable. |
| Plan | propuesto, autorizado, cerrado, cancelado | Autorización con alcance; cierre no acredita automáticamente todos los resultados. |
| Hito | propuesto, autorizado, en_curso, completado, cancelado | Completar exige aceptación y evidencia; bloqueo y reclamación son dimensiones separadas. |
| Fuente | registrada, retirada | Calidad de procesamiento, actualidad de versión e integridad son dimensiones separadas. |
| Persona, rol, entidad | propuesta, activa, retirada | Activar identidad o autoridad pasa por su política; un agente no ratifica. |
| Síntesis | borrador, vigente, retirada | Vigente exige verificación del contenido y dependencias requeridas. |

Transiciones iniciales de referencia: propuesta→aceptada/rechazada; abierta→resuelta/descartada; hipótesis abierta→validada/refutada/retirada; supuesto activo→retirado; plan propuesto→autorizado/cancelado y autorizado→cerrado/cancelado; hito propuesto→autorizado/cancelado, autorizado→en_curso/cancelado y en_curso→completado/cancelado; fuente registrada→retirada; persona/rol/entidad propuesta→activa/retirada y activa→retirada; síntesis borrador→vigente/retirada y vigente→borrador/retirada cuando se revisa su contenido.

Reaperturas y correcciones de un cierre requieren un evento motivado con política explícita y reevaluación del impacto. No se admite una transición inversa por simple edición de `estado`. La revisión de un hecho o hipótesis consolidado conserva la versión anterior y su evidencia.

### Eventos, relaciones y lectores

Cada evento registra `evento_id`, `tipo_evento`, `actor`, `registrado_en`, `valido_desde`, `valido_hasta` opcional, `motivo`, estado anterior/posterior cuando aplique y referencia de evidencia. Los nombres son contrato del esquema del sistema; las instalaciones no inventan variantes equivalentes sin un adaptador de migración.

Los campos de relación son listas de IDs u objetos tipados. Los comentarios van separados. `depende_de` declara una condición, por ejemplo decisión aceptada y aplicable, pregunta resuelta o hito completado con evidencia. Un plan propuesto no bloquea por asociación un hito independiente, pero ese hito necesita su propia autorización suficiente para ejecutarse.

Los eventos sensibles son producidos o admitidos por el mecanismo de integración confiable. Un evento escrito a mano no se considera autenticado por contener `human:`. El esquema distingue referencia a evidencia y comprobación de esa evidencia.

Cada campo declara qué consulta, regla, vista o requisito de auditoría lo necesita. El catálogo evita campos sin uso; no elimina evidencia histórica porque su consulta sea infrecuente.

### Proyección total de `status`

Para cada snapshot y tiempo de exportación se genera `status`; nadie lo edita manualmente. Se aplican estas reglas por orden, para cubrir todos los estados anteriores:

1. Clase **archivo**, estado rechazado/rechazada, descartada, retirada, cancelado, hipótesis refutada, o sucesión efectiva completa: `deprecated`.
2. Decisión/hecho/persona/rol/entidad en propuesta; plan/hito propuesto; síntesis borrador; hipótesis abierta; supuesto activo: `draft`.
3. Decisión/hecho aceptado con inicio de validez todavía futuro: `draft` hasta su entrada en vigor; la aceptación y el calendario se mantienen visibles.
4. Los restantes casos de la tabla: `stable`, con los estados detallados y advertencias del perfil propio.

`stable` expresa estabilidad del registro para intercambio, no verdad, permiso de ejecución ni calidad de extracción. Una pregunta abierta puede ser estable como registro; una fuente registrada puede tener extracción parcial. Una decisión parcialmente vigente conserva `stable` y expone qué cláusulas aplican. Disputa, integridad, caducidad y calidad viajan como campos/advertencias adicionales: un lector que no los entiende no es un cliente operativo certificado.

Las vistas no son registros autoritativos. Si una vista se exporta como concepto, su proyección se calcula del contenido representado y su contrato; no recibe `stable` como vía para eludir estas reglas. Una verificación de fuente que falla no se oculta cambiando solo `status`.

El paso del tiempo puede cambiar una proyección sin commits de usuario. Las exportaciones se generan para un corte explícito y llevan su fecha; la consulta en vivo calcula vigencia en tiempo de lectura. Un archivo exportado viejo nunca se anuncia como estado en tiempo real.

### Compatibilidad y parseo

Respetar las formas fijadas de `generated`, `verified`, `sources`, `stale_after` y `status`. No reutilizar un booleano como `generated`, una fecha como toda la lista `verified`, un plazo relativo como `stale_after` o `ruta` donde el perfil exige `resource`.

Las evaluaciones del perfil propio incluyen resultado positivo/negativo/parcial, alcance, digest y limitaciones. `verified` no se usa como mecanismo único de aceptación ni como destino de evaluaciones negativas. Al cambiar el contenido, la vista de verificación vigente solo considera eventos ligados a ese contenido; los anteriores permanecen en el historial de evaluaciones.

Las cláusulas y hechos en el cuerpo tienen anclas explícitas y gramática definida. Probar etiquetas dentro de bloques de código, escapes, texto mal formado, anclas duplicadas y visores que oculten marcas. Los campos por tipo, las transiciones y los escenarios de este documento determinan las pruebas que debe materializar la implementación; crear sus archivos de prueba es trabajo de construcción, no una decisión de diseño externa.

<a id="repositorio-remoto-y-escritura"></a>
## 5. Autoridad e integración

### Elecciones obligatorias

Definir proveedor de identidad o mecanismo equivalente, canal de aprobación, raíz inicial de confianza, responsables por ámbito, permisos de administración y política de delegación. Si hay varios responsables del mismo ámbito, fijar si se exige uno, todos o un quorum; no dejarlo a la interpretación del agente.

El permiso de modificar un archivo no es la autoridad de aprobar su contenido. La aprobación se liga al digest de la propuesta y a la base revisada. La política anterior autoriza cambios de roles, permisos y comprobadores. Un administrador no obtiene una excepción invisible por ser administrador.

El remoto debe poder exigir validación y revisión antes de modificar la rama canónica. Si no lo permite, se introduce una puerta controlada equivalente o se declara que esa garantía no está disponible; no basta con instalar hooks locales.

### Secuencia de escritura

1. Crear propuesta con ID de operación y revisión base.
2. Validar forma, referencias, transiciones y modificaciones de campos protegidos.
3. Calcular efectos normativos, impacto y ámbitos afectados sobre esa base.
4. Mostrar contenido, consecuencias y evidencia a los aprobadores necesarios.
5. Registrar aprobaciones autenticadas del contenido exacto.
6. Volver a validar contra la base canónica más reciente y la política de autoridad vigente.
7. Preparar eventos admitidos y proyecciones deterministas; comprobar el árbol final.
8. Integrar atómicamente cuando sea posible; emitir recibo y registrar deuda de impacto autorizada.
9. Si el resultado es desconocido, inspeccionar por ID de operación antes de reintentar.

Cambios de forma que alteren el digest o el significado requieren la política de reaprobación correspondiente. Los campos generados excluidos del digest tienen que estar definidos y validados, no formar una vía para introducir texto no revisado.

### Revisores por ámbito

Generar los revisores desde roles puede reducir duplicación, pero hay dos fuentes de alcance: archivos tocados y relaciones/impacto hacia otros ámbitos. Una lista basada solo en rutas no cubre la segunda. El comprobador calcula el conjunto y el mecanismo de integración verifica las aprobaciones de cada ámbito requerido sobre la versión revisada.

Se registran aprobación, rechazo, solicitud de cambios y aplazamiento. La ausencia de respuesta nunca cuenta como aceptación. Un cambio de aprobación o de contenido se refleja en las vistas y evita integrar con una revisión caducada.

<a id="comprobador-y-recuperación"></a>
## 6. Catálogo mínimo de controles

Los IDs siguientes identifican controles de esta versión, no reutilizan números locales de una instalación. Cada implementación mantiene trazabilidad entre control, función, prueba y error comunicado.

| Control | Qué verifica | Ante fallo |
| --- | --- | --- |
| VAL-01 | Parseo, esquema, tipos y estados permitidos. | Bloquear el cambio inválido. |
| VAL-02 | Identidad única, referencias y alias resolubles. | Bloquear duplicación o referencia requerida ausente. |
| VAL-03 | Mutabilidad y eventos append-only. | Rechazar alteración de contenido protegido. |
| VAL-04 | Identidad, autoridad previa, digest y vigencia de aprobación. | Bloquear aceptación o integración. |
| VAL-05 | Tiempos, precisión y orden de sucesión explícito. | Bloquear ambigüedad normativa; conservar incertidumbre histórica declarada. |
| VAL-06 | Alcance y composición de modificaciones de cláusula. | Rechazar conflicto no resuelto o destino inexistente. |
| VAL-07 | Ciclos prohibidos por relación y condiciones de dependencia. | Bloquear dependencia imposible; permitir ciclos contextuales válidos. |
| VAL-08 | Vistas reproducibles y proyección total de `status`. | Regenerar antes de integrar o rechazar discrepancia. |
| VAL-09 | Dependencias de síntesis y deuda de impacto. | Avisar o bloquear según el uso y política; nunca ocultar. |
| VAL-10 | Integridad de originales y derivaciones, localizadores y representación leída. | Retirar de usos afectados o bloquear usos que exijan esa evidencia. |
| VAL-11 | Permisos en lectura, expansión, exportación y procesamiento. | Denegar acceso sin filtrar información restringida. |
| VAL-12 | Autorización, aislamiento y resultado de comandos. | No ejecutar o registrar fallo/no ejecutado. |
| VAL-13 | Revisión base, reintentos y reclamaciones si se activan. | Revalidar o rechazar ejecutor caducado. |
| VAL-14 | Cobertura y limitaciones visibles al recuperar. | No presentar resultado como completo. |
| VAL-15 | Recibos y consistencia de restauración. | Reconciliar y declarar resultado parcial/desconocido. |

No hace falta activar todos los módulos antes del primer uso, pero toda capacidad habilitada exige sus controles. Por ejemplo, no se ofrece ratificación automática con solo VAL-01/02; no se ofrece ingesta de originales externos sin VAL-10/11. La matriz de entrega marca **implementado**, **probado**, **no probado** o **fuera de alcance**, con evidencia.

## 7. Temporalidad, consolidación e impacto

### Contrato de consulta histórica

Ejemplo de interfaz, adaptable al cliente sin cambiar su significado:

```text
consulta --id DEC-ejemplo --valido-en 2026-11-13T12:00:00+01:00 \
  --conocido-hasta 2026-11-14T23:59:59+01:00 --revision <revision>
```

La respuesta identifica ambos cortes y la precisión de los datos. Si se omite el corte de conocimiento se usa el último snapshot admitido y se declara. La revisión canónica identifica los eventos disponibles; el reloj de la consulta es entrada explícita, no una dependencia oculta del entorno.

Los datos heredados con solo fecha conservan `precision: dia` o equivalente. Un mismo día con eventos cuyo orden no pueda reconstruirse se marca ambiguo. No rellenar horas artificiales ni usar el orden alfabético de archivos para decidir vigencia.

### Casos obligatorios de cláusulas

- Sustituir C1 conserva C2 y su procedencia.
- Una propuesta de sustitución aparece como no vinculante.
- Una modificación futura no altera el consolidado actual.
- Dos cambios solapados sin sucesión explícita producen conflicto.
- Una cadena de sustituciones conserva el origen de cada cláusula.
- Derogar una modificadora no reactiva automáticamente el texto anterior.
- Una adición distingue identidad de cláusula y posición; no depende de numeraciones consecutivas.
- Un cambio retroactivo modifica «lo que hoy sabemos» sin reescribir «lo que se sabía entonces».

### Impacto y síntesis

El análisis combina referencias explícitas, cláusulas utilizadas, estados y política. Comparar solo bytes de una decisión inmutable no detecta que otra la ha derogado: la firma de dependencia incluye su estado efectivo y sus sucesoras pertinentes en el corte de evaluación.

El cambio genera una lista de afectados con causa y camino. Cada resolución identifica actualizado, no afecta con motivo o pendiente con responsable y plazo. La integración puede aceptar deuda visible si la política lo permite; no puede aceptar como segura una acción que requiere una dependencia invalidada.

Una nueva versión de fuente deja **impacto pendiente** en sus consumidores. Las derivaciones históricas siguen siendo válidas para el original que representan. Una síntesis efectivamente basada en contenido o vigencia cambiados aparece desfasada hasta revisarla. La revisión puede confirmar que no cambia su conclusión y registrar esa evidencia sin reescribirla innecesariamente.

<a id="harness"></a>
## 8. Recuperación, adaptadores y continuidad

Cada consulta declara entrada, salida, snapshot, reloj, permisos, presupuesto y errores. Las salidas incluyen campos estructurados para herramientas y una presentación comprensible. El contrato común se prueba por cliente; no se presupone que todos ofrezcan los mismos hooks o momentos de compactación.

### Contratos de adaptador

| Momento | Entrada y resultado esperado |
| --- | --- |
| Apertura | Cargar versión de método, configuración de proyecto y snapshot; mostrar restricciones y relevo. |
| Lectura | Recuperar evidencia con condiciones; registrar cobertura y representación leída sin copiar datos sensibles innecesarios. |
| Preparación de escritura | Propuesta y revisión base; separar autorización de la intención inferida. |
| Cierre de operación | Recibo o estado desconocido/parcial con ruta de reconciliación. |
| Compactación/reanudación | Persistir lo necesario y reconstruir objetivo, límites, pendientes y siguiente paso. |
| Fin de sesión | Registrar resultado provisional, propuesta de decisiones no capturadas y medida humana pendiente si falta. |
| Bloqueo | Motivo, alcance afectado y condición para continuar; permitir trabajo independiente ya autorizado. |

La constitución del sistema, las instrucciones de proyecto y el relevo tienen responsabilidades separadas. Su carga no puede depender de una ruta flotante no versionada. La entrada desde fuentes no puede elevarse a instrucciones de mayor prioridad.

### Relevo mínimo

Incluye objetivo y referencia de autorización; alcance y tolerancias; revisión base; trabajo integrado; cambios locales o de rama pendientes; última evidencia de verificación con revisión y antigüedad; bloqueos y preguntas; siguiente paso y su fundamento; cambios ajenos pertinentes.

Si se pierde un matiz que no está registrado, se declara. Un registro mínimo de intención puede ser necesario y se evalúa por su coste; «deducido por script» no justifica afirmar que el sistema conoce información nunca persistida. El resumen conversacional puede ayudar, pero no sustituye el estado normativo.

Un límite inicial de extensión se ajusta con evaluación. Los truncamientos indican qué quedó fuera. Nunca se elimina una restricción decisiva para cumplir cuarenta líneas u otra cifra de presentación.

### Descubrimiento y búsqueda

Probar preguntas con ID conocido y preguntas sin él. Separar recuperación de candidatos, filtrado normativo y uso de evidencia. Los índices léxicos o semánticos se comparan contra la búsqueda existente sobre tareas propias; el mismo conjunto de permisos y advertencias se aplica a todos.

Una copia sincronizada lleva revisión y fecha de corte visibles. Si no puede comprobarse su actualidad, sirve para consultas históricas o exploración con límites declarados; no es una base fiable para ratificar el estado actual.

<a id="ingesta"></a>
<a id="procesador"></a>
<a id="almacén-de-originales"></a>
<a id="integridad"></a>
<a id="piloto"></a>
## 9. Ingesta documental

### Piloto separado y conectado

Elegir entre cinco y diez documentos que hoy generen preguntas o trabajo manual. Registrar formatos cubiertos y no probados. No añadir documentos artificiales solo para completar una lista de modalidades, aunque sí crear casos adversos específicos para probar controles.

Antes de procesar, definir preguntas, evidencia esperada, límites de salida a servicios externos y tiempo humano de preparación/revisión. Una prueba aislada de extracción puede empezar pronto; un piloto integrado necesita previamente identidad, fuente/derivación, localizadores, permisos y comprobación de integridad.

### Procesadores

Seleccionar un motor estructurado como candidato —por ejemplo, Docling— o un conversor ligero si el corpus no necesita más. Comprobar capacidades en la versión fijada y en documentos propios. XML, hojas y datos pueden exigir parsers específicos; no se presupone que un conversor universal preserve sus semánticas.

Conservar la representación nativa necesaria y un contrato común mínimo. Un formato de intercambio adicional solo entra cuando un consumidor lo necesita. Alternativas como otros motores de OCR o de documentos científicos se incorporan por fallos concretos o ventaja medida, no por completar un catálogo.

Cada ejecución registra entradas, procesador, versión, configuración identificable, modalidad, recursos consumidos, resultado, errores y calidad. Las conversiones se cachean por identidad de entrada y configuración; un cambio de procesador produce otra derivación y una evaluación de regresión.

### Originales, derivaciones y localizadores

El almacén puede ser almacenamiento de archivos grandes, objetos o una unidad controlada. Debe permitir comprobar huellas, mantener versiones, aplicar permisos y restaurar el conjunto. La organización por carpetas es operativa, no identidad.

SHA-256 es el algoritmo inicial del perfil. Cada original y cada derivación tienen su huella propia. El linaje no sustituye la huella del resultado. Los punteros pueden cambiar solo después de comprobar el contenido; el reprocesado nunca sobrescribe una derivación histórica.

Una cita conserva:

- ID del original y localizador lógico.
- ID de la representación usada para resolverlo.
- Huella o versión inmutable de esa representación.
- Evidencia recuperada y contexto requerido, dentro de los límites de almacenamiento y privacidad.

Si una tabla recibe otro identificador tras reprocesar, la cita previa sigue resolviendo en su representación anterior o se marca pendiente de reparación. No se redirige silenciosamente a una tabla distinta con el mismo nombre.

### Calidad y aceptación

Separar que el proceso termine de que su salida sea fiel. La muestra de revisión incluye tablas, unidades, negaciones, fórmulas, leyendas y orden de lectura pertinentes. Un documento con texto correcto y diagrama pendiente no se sirve como completo para una pregunta que depende del diagrama.

El revisor puede registrar resultado negativo, parcial o no comprobado. Una evaluación negativa bloquea los usos afectados y abre corrección/reprocesado. No se cambia la salida inmutable ni se expresa el desacuerdo añadiendo solo `verified` positivo.

**Pruebas del piloto integrado:**

1. Mover una fuente conserva identidad y citas internas; los enlaces externos afectados se reparan o declaran.
2. Cada localizador usado resuelve en la representación identificada.
3. Una nueva versión conserva las derivaciones antiguas y marca impacto en consumidores pertinentes.
4. Reprocesar no cambia silenciosamente el contenido al que apuntaba una cita.
5. Alterar un original o derivación se detecta; un fallo de acceso se distingue de un cambio de bytes.
6. Una extracción parcial o errónea se comunica y no se usa como evidencia completa.
7. Una pregunta que combina modalidades llega a la evidencia original de ambas, si está dentro del alcance piloto.
8. Las instrucciones maliciosas del documento no cambian permisos ni disparan comandos en los escenarios ensayados.
9. Las respuestas preservan condiciones decisivas y reducen o justifican su coste humano frente a la línea base.

## 10. Interfaz humana, captura y colas

Observar primero dónde se toman decisiones. Puede ser una reunión, revisión de código, chat o documento. Elegir el canal mínimo que permita proponer con poco esfuerzo y ratificar con identidad verificable. No hacer depender la utilidad del método de que todos adopten un panel nuevo.

El prototipo de revisión muestra cambio, evidencia, consecuencias, incertidumbre, recomendación y opciones pertinentes. Se prueba que la persona entiende qué acepta y qué queda sin resolver. La capa técnica puede usar Git; la interfaz no tiene por qué exponer IDs, YAML o todo el diff por defecto.

Fijar por rol presupuesto de revisión, plazo, sustituto y política ante cola saturada. Agrupar causas comunes; mantener visibles decisiones pendientes y omisiones detectadas. Una cola que no recibe atención no se resuelve produciendo más propuestas.

Para el sensor de decisiones no registradas, empezar con una salida agrupada y revisable. Medir falsos positivos y omisiones mediante muestra, junto con el tiempo que consume. Las propuestas aceptadas no justifican por sí solas que el sensor compense.

La muestra de acciones autónomas incluye algunas decisiones de no escalar y acciones con impacto alto dentro de delegación. Se calibra el criterio sin exigir revisar cada operación rutinaria. La mejora se mide en comprensión, resultados y esfuerzo, no en cantidad de aprobaciones.

## 11. Seguridad, operación y concurrencia

### Perfil de seguridad inicial

Documentar activos, actores, límites de confianza y acciones permitidas. Probar al menos una fuente con instrucciones maliciosas, una aprobación falsificada, un intento de ampliar permisos y un cambio que desactive su propio comprobador.

El proponente no dispone libremente de credenciales de ratificación o integración. Los procesos de ingesta y pruebas se ejecutan con rutas, red, recursos y secretos limitados. Los comandos propuestos se revisan como código; no se ejecuta directamente una cadena extraída de un documento.

Permisos heredados se aplican también a índices, logs, cachés y exportaciones. Si no existen permisos parciales, se excluye material incompatible con el grupo de lectura. La política de retirada excepcional especifica quién puede ordenarla, qué copias deben tratarse y cómo se comunica lo que no pueda eliminarse con garantías.

### Presupuestos y recuperación

Fijar volumen esperado, concurrencia, latencia p50/p95, presupuesto de modelos y procesamiento, límite de cola humana, antigüedad admisible de integridad, objetivo de recuperación y pérdida de datos tolerada. Elegir cifras después de conocer tareas y baseline; registrar mediciones en hardware/entorno identificado.

Las verificaciones periódicas de originales pueden empezar con una cadencia sencilla y ajustarse por uso e impacto. Una operación sensible puede exigir verificación al leer, sin esperar al calendario. La periodicidad no permite afirmar integridad continua.

Probar fallos de red, original ausente, credencial vencida, telemetría caída, índice atrasado, escritura parcial y pérdida de respuesta tras integrar. Cada uno tiene estado, mensaje, responsable y acción de recuperación. Un error de sensor no debe paralizar automáticamente una consulta segura; un error de autoridad sí bloquea la operación que la necesita.

Los respaldos conservan una revisión consistente de registros, originales externos y evidencia de aprobación. Un clon de Git no incluye necesariamente los objetos pesados ni los eventos de un proveedor externo. La prueba de restauración reconstruye consultas y citas, además de abrir archivos.

### Varios escritores, cuando se necesiten

Activar por una necesidad observada de concurrencia. Antes: IDs estables, integración contra base actual, aprobación por contenido, conflictos de cláusulas y recibos idempotentes.

Si se añaden reclamaciones, definir adquisición atómica, vencimiento, renovación, generación y liberación. El ejecutor conserva el número de generación y la puerta rechaza resultados de una reclamación vencida o sustituida. En ausencia de conexión se puede preparar trabajo aislado, pero no anunciar exclusividad no comprobada.

Una reclamación no es una excepción para escribir sin control en la rama principal. Su evento pasa por una operación autorizada y automatizable, con controles proporcionales. Si los efectos externos no pueden comprobar la generación, se declara la limitación y se restringe su ejecución.

<a id="atención-y-medida"></a>
## 12. Evaluación y definición de terminado

### Banco mínimo previo

Usar ejemplos reales con respuestas revisadas y variantes adversas. Escribir la expectativa antes de implementar:

| Caso | Resultado necesario |
| --- | --- |
| Ratificación humana declarada solo en YAML | No acepta ni integra como aprobada. |
| Contenido modificado tras aprobar | Aprobación inválida para ese contenido. |
| Cambio de rol que se autoriza a sí mismo | Rechazo bajo la política anterior. |
| Sustitución parcial y propuesta pendiente | Conserva cláusulas no afectadas y separa lo no vinculante. |
| Dos cambios incompatibles | Conflicto explícito antes de integrar. |
| Consulta histórica con corrección tardía | Diferencia entre validez y conocimiento. |
| Evidencia decisiva omitida | Declara insuficiencia; no completa con certeza inventada. |
| Síntesis cuyo texto fuente no cambia pero pierde vigencia | Detecta el cambio de dependencia. |
| Reanudación con cambios sin integrar | Recupera objetivo y límites; separa pendiente de aceptado. |
| Escritura completada con respuesta perdida | Reconcilia sin duplicar el efecto. |
| Fuente parcial o localizador reprocesado | Limitación visible y referencia estable. |

Las pruebas deterministas comprueban reglas y propiedades; las evaluaciones de IA comprueban respuesta y conducta. Comparar fuentes completas, contexto servido y ablación; no tomar la salida de otro modelo como verdad automática. Etiquetar manualmente evidencia decisiva y condiciones. Un juez de IA puede asistir si se calibra y audita su desacuerdo.

El conjunto independiente de evaluación no se utiliza íntegramente para ajustar prompts. Registrar versiones, parámetros, corpus, resultados por caso, latencia, coste y errores. La calidad mínima se comprueba antes de integrar cambios de recuperación, aunque el tiempo humano parezca mejorar.

### Medición en uso

Registro ligero por tarea/sesión: resultado previsto, tiempo humano observado o estimado, interrupciones, correcciones, resultado provisional y seguimiento. Marcar explícitamente los datos ausentes. Las correcciones tardías actualizan la evaluación de la tarea original.

Reportar tiempo de instalación y tiempo recurrente; incluir intentos fallidos y mantenimiento compartido mediante una regla de atribución. Separar tipos de tarea y dificultad. Mantener tokens y latencia de toda la cadena como métricas secundarias.

La proporción de decisiones sobre el sistema es una señal, no una meta que pueda mejorarse agrupando veinte cambios bajo un solo ID. Medir minutos de mantenimiento y decisiones de negocio retrasadas. Un aumento de aprobaciones tampoco demuestra éxito sin comprobar calidad y comprensión.

### Definición de terminado del incremento

- Contrato y versión identificados; ejemplos coherentes con el esquema.
- Controles de la capacidad activada implementados y probados.
- Migración revisada, con diferencias y reversión o recuperación definida.
- Integración canónica completada y recibo disponible.
- Una sesión nueva usa el recorrido integrado, con autoridad y límites conservados.
- Evidencia de resultado correcto y primera medida humana; lo aún no probado queda visible.
- Responsable de operación y respuesta a fallos asignado.

La evaluación sostenida del beneficio es otra puerta: exige suficientes tareas representativas y seguimiento. Una primera sesión correcta habilita aprendizaje, no una afirmación general de ahorro.

<a id="puesta-en-marcha"></a>
## 13. Secuencia de desarrollo recomendada

**Enfoque:** especificaciones ejecutables para significado y contratos; TDD para reglas deterministas; evaluación empírica para IA; validación de producto con personas. La especificación se ajusta al aprender, sin imponer una fase de diseño exhaustivo antes del primer resultado.

### Fase 0. Establecer la base

Inventariar código, revisiones, ramas y entregas existentes; distinguir implementado, descrito y pendiente. Resolver solo las discrepancias que afectan al incremento elegido. Tomar una línea base y acordar quién decide y qué puede escribir el agente.

**Puerta:** revisión base reproducible, tarea elegida, autoridad mínima y caso de aceptación conocido. No crear otra arquitectura paralela por no haber localizado el trabajo previo.

### Fase 1. Entregar un recorrido pequeño

Elegir una tarea con valor inmediato: consultar una decisión modificada, retomar trabajo o registrar una propuesta con aprobación. Implementar conjuntamente datos, consulta, control e interfaz necesarios. Si el camino escribe conocimiento aceptado, la autoridad autenticada entra aquí, no en una fase posterior.

Integrar primero mejoras existentes compatibles, con pruebas y sin arrastrar cambios de gobierno no revisados. Instrumentar lo mínimo para observar coste y errores.

**Puerta:** recorrido en la versión canónica, prueba de regresión y una sesión real con resultado verificable. Una rama sin integrar no pasa esta puerta.

### Fase 2. Corregir el dato y extender contratos

Migrar estados en prosa, relaciones ambiguas, cláusulas y dependencias según necesidad demostrada. Añadir temporalidad y consolidación al ampliar consultas históricas. Revisar individualmente migraciones que cambian significado; muestrear solo transformaciones mecánicas de riesgo acotado.

**Puerta:** casos reales responden correctamente, conflictos se rechazan y la migración conserva procedencia y precisión histórica.

### Fase 3. Consolidar continuidad y revisión humana

Probar apertura, interrupción y reanudación; corregir pérdida de intención y estados pendientes. Ajustar captura y revisión a los canales utilizados. Verificar que los adaptadores implementan el mismo contrato.

**Puerta:** una sesión nueva retoma trabajo sin atribuir autoridad inexistente ni perder restricciones; una persona puede revisar el cambio y sus consecuencias sin reconstruir todo el historial.

### Línea documental. Piloto integrado cuando exista una necesidad

Una prueba de extracción aislada puede ejecutarse durante la fase 0. Para integrar sus resultados hacen falta esquema fuente/derivación, localizadores versionados, controles de acceso, integridad y evaluación de fidelidad. El piloto no se coloca por calendario antes de sus dependencias.

**Puerta:** preguntas reales sobre el corpus se resuelven con evidencia y límites correctos, y el coste de preparación/revisión está medido. Los formatos no cubiertos siguen declarados como no probados.

### Fase 4. Uso sostenido y decisión de ampliación

Usar el sistema durante un periodo que aporte tareas representativas; observar correcciones tardías, mantenimiento, colas y adopción. Separar cambios cuando sea posible para atribuir resultados. Revisar causas antes de revertir automáticamente por cualquier oscilación de una serie corta.

**Puerta:** evidencia suficiente para mantener, simplificar o retirar mecanismos. Ampliar proyectos, escritores o modalidades exige una necesidad concreta y contratos probados, no solo haber llegado al final del plan.

### Extensiones activadas por necesidad

El contrato de capa de operación de este documento define tres ampliaciones independientes. (1) Añadir MCP como adaptador del núcleo cuando haya un cliente que lo consuma, pasando ESC-09; empezar local si cubre el caso. (2) Incorporar un conector incremental cuando una fuente cambie con frecuencia y sea costoso revisarla manualmente, pasando ESC-11. (3) Experimentar con mejora del harness solo tras disponer de fallos reproducibles, línea base y evaluación independiente, pasando ESC-10. Ninguna ampliación es requisito universal para entregar el recorrido inicial. La plataforma remota requiere además demostrar la necesidad de acceso y operación compartidos y completar sus controles antes de activarla.

Cada experimento compara el incremento con el núcleo estable sobre tareas equivalentes. Se acuerdan por adelantado calidad, coste, límites y condición de retirada; si no aporta un resultado RES verificable, se aplaza o se simplifica. La configuración de herramientas concreta pertenece al plan de desarrollo, no altera los contratos de esta referencia.

## 14. Migración desde versiones anteriores

Antes de actualizar, conservar copia verificable y manifiesto del estado inicial. La migración se ejecuta primero en seco y produce diff, errores, ambigüedades y casos que requieren revisión humana.

| Cambio de diseño | Tratamiento de datos existentes |
| --- | --- |
| IDs sin obligación de secuencia | Conservar IDs válidos; dejar de rechazar huecos. No renumerar el corpus sin necesidad. |
| `estado` y eventos | Crear un evento de importación con procedencia histórica; no inventar una aprobación autenticada del pasado. |
| Fechas precisas y dos tiempos | Conservar fecha original y precisión; registrar cuándo se importa. Separar fecha declarada de incorporación comprobada. |
| Ratificación autenticada | Clasificar evidencia heredada como comprobada, pendiente o insuficiente. Revalidar lo necesario para nuevos usos. |
| `modifica` tipado | Proponer anclas y alcance; revisión humana de sustituciones parciales o contradictorias. |
| Estados en prosa | Preservar el texto como avance/historia; no inferir resuelta o autorizada por longitud o palabra aislada. |
| Relaciones limpias | Extraer candidatos y validar destino, sentido y condición; separar notas. |
| Campos OKF | Convertir formas incompatibles; conservar significado anterior en la trazabilidad de migración. |
| Huellas y derivaciones | Calcular huella propia para cada artefacto disponible; identificar faltantes sin fabricar integridad pasada. |
| Citas a representaciones | Fijar la representación conocida; si no se sabe cuál se usó, marcar la incertidumbre y revisar usos relevantes. |
| Proyección `status` | Regenerar con la función total y snapshot temporal; comprobar consumidores externos. |
| Autoridad y configuración | Fijar raíz de confianza y revisión de políticas sin permitir autoaprobación. |

La reversión de código/esquema se distingue de deshacer decisiones ya integradas o efectos externos. No se restaura un backup sobre actividad nueva sin reconciliarla. Si no existe una migración inversa segura, documentar recuperación hacia delante.

Los consumidores viejos se identifican antes de cambiar el esquema. Un lector genérico que ignora estados y extensiones puede leer contenido, pero no actuar como ejecutor normativo. Versionar y probar los adaptadores necesarios.

<a id="qué-no-entra-por-defecto"></a>
<a id="pendiente-de-decisión"></a>
## 15. Reservas y decisiones que siguen siendo locales

| Capacidad | Disparador admisible |
| --- | --- |
| Índice semántico | Fallos de recuperación por significado que mejora una evaluación propia. |
| Vista relacional o motor de grafos | Consultas o costes observados que el modelo actual no resuelve con mantenimiento razonable. |
| Consolidación o fase de sueño | Recurrencia útil y coste evitable demostrados; propuestas evaluadas antes de promocionar. |
| Lint semántico periódico | Incidentes, contradicciones o envejecimiento que justifiquen su coste; no hace falta esperar para corregir un error conocido. |
| Reclamaciones y múltiples escritores | Necesidad de coordinación real, con exclusión y caducidad comprobables. |
| Permisos parciales | Usuarios o datos que los requieren; evaluación de todas las rutas de exposición. |
| Procesadores adicionales | Clase documental donde el primero falla o cuesta más de lo aceptable. |
| Firma o atestación adicional | Amenaza, interoperabilidad o tercero que necesita comprobar procedencia más allá del mecanismo de confianza existente. |
| Evaluación ampliada | Mayor riesgo, escala o incertidumbre; el banco mínimo nunca queda en reserva. |

Permanecen como elecciones de instalación: lenguaje y librerías, remoto, almacén de originales, canal de aprobación, distribución del paquete, parámetros de rendimiento, retención, revisión humana y clases de entidad. Su elección no puede cambiar silenciosamente las garantías del núcleo.

<a id="fuentes-de-esta-guía"></a>
<a id="registro-de-cambios"></a>
## 16. Contratos y escenarios incorporados

Los apartados siguientes son parte normativa de esta guía. Reproducen el modelo y las reglas necesarios para implementarla sin abrir otro archivo. Comparten significado con el núcleo 0.7; los parámetros locales solo concretan herramientas y recursos, no cambian estas reglas.

## Glosario autónomo de implementación

| Término | Significado |
| --- | --- |
| Registro | Unidad identificable de conocimiento o gobierno, con tipo, procedencia, estado y relaciones. |
| Fuente | Original conservado o representación derivada identificada y vinculada a un original. |
| Representación / derivación | Resultado de un procesado de una fuente concreta; tiene identidad, huella y limitaciones propias. |
| Localizador | Dirección de evidencia dentro de una versión: página, sección, tabla, celda, región, intervalo o símbolo de código. |
| Decisión | Elección normativa adoptada por una autoridad identificada. No prueba que sus premisas sean ciertas ni que se haya ejecutado. |
| Cláusula / ancla | Parte estable de una decisión que puede modificarse sin sustituir las demás. |
| Hecho | Afirmación con fuente, fecha y clase de evidencia; puede ser incierta, discutida o corregida. El nombre del tipo no implica certeza. |
| Clase de evidencia | Observado, calculado, declarado, modelado, predicho o supuesto; describe el origen de una afirmación, no su fuerza normativa. |
| Ratificación | Aprobación autenticada de un contenido concreto por quien tenía autoridad para hacerlo. |
| Verificación | Comprobación de contenido frente a evidencia, con alcance y resultado; no equivale por sí sola a ratificación. |
| Autoridad delegada | Permiso previo, limitado y verificable para ejecutar una clase de acciones. No permite al agente ampliar sus propios permisos. |
| Vigencia | Aplicabilidad de un registro o cláusula en un instante, calculada a partir de eventos, fechas y relaciones efectivas. |
| Tiempo de validez | Cuándo se considera aplicable una afirmación o decisión en el dominio. |
| Tiempo de conocimiento | Cuándo quedó registrado y aceptado un evento en la base autorizada. |
| As-of | Consulta histórica que declara tanto la fecha de validez como hasta cuándo se considera conocido el historial. |
| Fijo / síntesis | Documento mantenido que integra registros y declara sus dependencias y verificaciones. |
| Vista | Proyección regenerable: índice, consolidado, agenda o panel. No añade hechos ni autorizaciones propios. |
| Comprobador | Núcleo determinista de validación y cálculo; comparte modelo con las consultas, sin necesitar un único módulo monolítico. |
| Harness | Adaptador a un cliente de agente que implementa los contratos de apertura, lectura, escritura, parada y reanudación. |
| Relevo | Contexto breve reconstruido desde registros y evidencia de sesión, con objetivo, límites, estado y siguiente paso. |
| Recibo | Evidencia de una operación: propuesta, estado anterior, resultado observado y revisión donde quedó incorporada. |
| Impacto pendiente | Dependencia que requiere reevaluación; no equivale a demostrar que su contenido sea falso. |
| Integridad rota / no comprobada | Contenido ausente o alterado frente a una comprobación que no pudo completarse; se distinguen sus causas. |
| Informe de excepción | Desviación, evidencia, opciones pertinentes, recomendación, decisión requerida y consecuencia de esperar. |
| Presupuesto de atención | Tiempo y capacidad de revisión disponibles, incluyendo la cola pendiente y su antigüedad. |
| Reserva | Capacidad no activada, con coste, responsable y disparador observable. |
| Contrato de pregunta | Preguntas que una nueva estructura debe permitir responder y prueba de la mejora que aporta. |


## Contrato normativo incorporado: modelo de conocimiento

### Tipos y clases

Tipos fundamentales: **fuente, hecho, decisión, persona y rol**. Tipos activados según los casos de uso: **pregunta, hipótesis/supuesto, entidad, plan, hito y síntesis**. Un perfil de instalación declara cuáles usa y sus dependencias; no puede ofrecer autorización verificable sin identidad y roles, ni ejecución gobernada sin un objeto que recoja su autorización y aceptación.

| Tipo | Contenido y finalidad |
| --- | --- |
| Fuente | Original o derivación, ubicación, identidad, huella, procedencia y calidad aplicable. |
| Hecho | Afirmación, evidencia, alcance temporal y fuentes; las correcciones conservan la afirmación anterior. |
| Decisión | Cláusulas, justificación, autoridad, alternativas pertinentes, ámbito y efectos temporales. |
| Persona | Identidad de participante humano o agente y ocupaciones de roles con intervalo. Solo datos necesarios. |
| Rol | Ámbito, capacidad de ratificación y condiciones de delegación. |
| Pregunta | Incógnita, incidencia o discrepancia factual, responsable, plazo y condición de cierre. |
| Hipótesis/supuesto | Afirmación sometida a prueba o asumida sin ella; criterio de refutación o fecha de revisión y consecuencia de fallar. |
| Entidad | Identidad, nombre, alias y clase del dominio. Sus atributos con significado factual se expresan mediante hechos. |
| Plan | Objetivo y agrupación de hitos; aprobación, restricciones y dependencias. No autoriza implícitamente toda acción futura. |
| Hito | Resultado esperado, alcance, autorización necesaria, tolerancias, criterios de aceptación y verificaciones. |
| Síntesis | Texto derivado, dependencias de contenido y de vigencia, revisión y frescura. |

Las clases documentales describen mantenimiento: **registro**, **fuente**, **fijo**, **vista** y **archivo**. Archivar cambia la participación en vistas de trabajo, no borra la identidad ni impide consultas históricas. Una fuente archivada sigue siendo evidencia del contenido conservado; no se presenta como versión actual por ese motivo.

Un hecho recibe archivo propio cuando es reutilizado, trata de una entidad o necesita ciclo de revisión independiente. Los demás pueden ser afirmaciones marcadas dentro de un registro, con ancla, fecha, clase y cita. Dos citas al mismo fragmento son una señal para revisar duplicación, no prueba de que expresen el mismo hecho.

### Estado, evidencia y verificación

Son ejes distintos:

- **Estado de gobierno:** propuesta, aceptada, rechazada; o el enumerado correspondiente al tipo.
- **Vigencia y dependencias:** total, parcial o no vigente; en disputa, caducada, base invalidada, impacto pendiente.
- **Clase de evidencia:** observado, calculado, declarado, modelado, predicho o supuesto.
- **Verificación:** qué se comprobó, sobre qué contenido, por quién, cuándo y con qué resultado.
- **Calidad de representación:** cobertura y fidelidad por dimensión, errores y elementos pendientes.

Una revisión humana no convierte automáticamente una inferencia en observación. Una decisión puede estar aceptada y basarse en supuestos. Un hecho calculado puede proceder de entradas erróneas. Toda salida debe preservar estas distinciones.

Los cambios de estado se representan como eventos append-only vinculados al registro: identidad del evento, estado anterior y posterior, actor, motivo, tiempo de registro, efecto temporal y evidencia de autorización cuando proceda. `estado` representa la última transición admitida y se comprueba contra esos eventos. Los eventos no son otro almacén: forman parte del registro canónico. El historial de Git permite auditar su incorporación.

La transición a aceptada requiere ratificación válida. Rechazar no equivale a derogar una decisión antes aceptada: su retirada normativa requiere una decisión sucesora. Cada tipo tiene una tabla completa de transiciones; la instalación no inventa estados fuera de ella. «Impacto sin resolver» es motivo de una pregunta abierta, no un estado añadido informalmente.

### Relaciones

Cada relación se escribe en un lado. Su inversa se calcula. Las relaciones de una propuesta no producen efectos normativos. Las aristas que necesitan fechas o procedencia usan objetos tipados, no prosa mezclada con IDs.

| Relación | Origen → destino | Semántica |
| --- | --- | --- |
| `resuelta_por` | pregunta → decisión | Resuelve una elección normativa; exige decisión aceptada. |
| `cuestiona` | pregunta → cláusula | Abre una disputa normativa, sin derogar automáticamente. |
| `modifica` | decisión → cláusula o registro decisorio | Sustitución, derogación o adición con alcance explícito. |
| `deja_obsoleta` | decisión, hecho o fuente → registro del mismo tipo | Sucesión completa, con fecha y autoridad o procedencia aplicables. |
| `depende_de` | pregunta, decisión, plan o hito → registro/cláusula | Dependencia tipada con condición de satisfacción; no basta con que exista el destino. |
| `pone_a_prueba` | hipótesis → cláusula | Contrasta una premisa o consecuencia de una decisión; fallar activa revisión, no una derogación automática. |
| `basada_en` | decisión, hecho, hipótesis o pregunta → fuente/hecho | Evidencia de una afirmación o de una resolución factual. |
| `derivada_de` | fuente derivada → fuente | Linaje de un proceso sobre una versión concreta; nunca presupone fidelidad perfecta. |
| `afecta_a` | decisión, hecho o pregunta → entidad/registro/síntesis | Alcance o impacto; por sí sola no implica dependencia causal ni bloqueo. |
| `autorizado_por` | decisión, plan o hito → rol | Capacidad requerida; se acompaña de aprobación o delegación autenticada. |
| `ocupa` | persona → rol | Ocupación con intervalo, incorporada bajo autoridad previa. |
| `veta` | decisión → patrón y ámbito | Restricción terminológica o de uso definida, con exclusiones y excepciones. |

Una pregunta factual puede resolverse mediante evidencia `basada_en` y un evento de cierre verificado; no se inventa una decisión normativa para declarar un resultado de medición. Una discrepancia entre fuentes se representa como pregunta que afecta a ambas y conserva sus evidencias. `cuestiona` no sustituye a una relación universal de contradicción entre hechos.

Se prohíben ciclos en las cadenas de sucesión, derivación y dependencia ejecutable. Los ciclos entre relaciones de contexto pueden ser legítimos: una pregunta resuelta por una decisión que afecta a esa pregunta no debe rechazarse. Las consultas usan conjuntos de visitados y límites de expansión.

Los vetos se aplican al uso prescrito en contenido operativo, no indiscriminadamente a originales, citas históricas, explicaciones de la propia prohibición o identificadores. Un patrón léxico es un control limitado; no determina por sí solo equivalencia semántica.

### Ampliación del esquema

Una extensión propone preguntas concretas, ejemplos, lectores, coste de captura, reglas y migración. Un tipo nuevo necesita un ciclo de vida o relaciones que no se expresen adecuadamente con los existentes. Los proyectos definen clases de entidad y vocabulario del dominio; los cambios a contratos generales se versionan en el sistema. Las diferencias declaradas no pueden rebajar silenciosamente autoridad, integridad o permisos.


## Contrato normativo incorporado: mutabilidad y tiempo

### Matriz de mutabilidad

| Elemento | Cambio permitido |
| --- | --- |
| Propuesta no aceptada | Edición por revisión; invalida las verificaciones del contenido anterior que ya no correspondan. |
| Cláusula aceptada y su ancla | No se reescribe ni elimina; otra decisión la modifica o deroga. |
| Afirmación factual consolidada | Corrección mediante nueva afirmación y sucesión explícita; conservar evidencia del error. |
| Eventos de aprobación, estado y ocupación | Append-only; correcciones mediante eventos posteriores, sin fabricar actividad histórica. |
| Puntero de un original | Puede cambiar con comprobación de que conserva la identidad y huella esperadas. |
| Original y derivación | Contenido inmutable; cambio de bytes o reprocesado produce otra versión identificada. |
| Síntesis | Edición versionada y nueva verificación del contenido cambiado. |
| Vista / `status` de interoperabilidad | Regeneración determinista desde una revisión y un instante explícitos. |
| Título, alias y descripción | Cambio versionado; evaluar si altera significado o referencias. No reabre por defecto una cláusula intacta. |

La política de huellas distingue identidad binaria de normalización para comparaciones. No se normalizan originales para comprobar su integridad. Los hashes de síntesis incluyen las dependencias semánticamente relevantes: cláusula, estado y versión de política, no solo su texto. Una derogación puede invalidar una síntesis aunque el texto original siga idéntico.

### Dos tiempos y una revisión

Cada evento canónico tiene `registrado_en`, instante con zona asignado por el mecanismo de integración, y un inicio de validez `valido_desde`; el fin, cuando existe, define un intervalo semiabierto `[desde, hasta)`. Las fechas declaradas por usuarios o fuentes se conservan separadas de la evidencia de incorporación. Las marcas de autor de un commit no son por sí solas un reloj autenticado.

Una consulta temporal recibe:

- `valido_en`: instante del dominio sobre el que se pregunta.
- `conocido_hasta`: corte del historial admitido.
- `revision`: snapshot canónico usado para reconstruir la respuesta.

Si solo se proporciona `valido_en`, el modo por defecto es «lo que hoy sabemos sobre esa fecha» y se muestra el corte utilizado. «Lo que se sabía entonces» fija también `conocido_hasta`. No se infieren diferencias dentro del día cuando los datos heredados solo tienen fecha: se declara la precisión y la ambigüedad.

Ejemplo: una decisión incorporada el día 10 entra en vigor el 15. Una corrección incorporada el 20 y válida desde el 12 afecta a la consulta del día 13 con conocimiento hasta el 20, pero no a la misma consulta con conocimiento hasta el 14. La política debe admitir expresamente esa retroactividad y la aprobación debe cubrirla. Nunca se reescribe `registrado_en` para simular que ya se conocía.

### Modificación por cláusulas

`modifica` lleva `destino`, `tipo` y, cuando corresponda, `por`:

- **Sustitución:** destino `ID#ancla`; `por` identifica la cláusula nueva del registro modificador.
- **Derogación:** destino `ID#ancla`; no admite `por`.
- **Adición:** destino de decisión; `por` identifica una cláusula nueva y su posición lógica explícita.

La modificación solo se aplica cuando está aceptada y es válida en el corte consultado. El consolidado devuelve cada cláusula con su procedencia y efectos. No resume creativamente ni oculta propuestas pendientes.

Dos cambios sobre la misma cláusula y con intervalos solapados no se ordenan por fecha de archivo o por orden de lectura. El posterior debe declarar la sucesión y dependencia respecto del anterior, especificar el contenido resultante y pasar revisión sobre la base actual. Si persiste ambigüedad, la integración se bloquea. Retirar una modificadora no resucita automáticamente la cláusula previa: se requiere una decisión que establezca qué rige desde entonces.

### Estados derivados e impacto

Se calculan, no se editan: `en_vigor`, `en_disputa`, `base_invalidada`, `caducada`, `desfasada`, `impacto_pendiente` y estados de integridad. Una pregunta abierta sobre una cláusula deja de disputarla cuando se resuelve o la cláusula deja de estar vigente; la pregunta puede seguir requiriendo cierre explícito.

Una versión nueva de una fuente no altera sus derivaciones históricas. Quienes se apoyaban en la versión anterior requieren revisión de impacto. El análisis identifica dependencia, causa, revisión origen, responsable, plazo y resolución: actualizado, no afecta con justificación o pendiente. La deuda se registra durante la integración del cambio; no depende de que el agente la recuerde en otra sesión.

El impacto se propaga por dependencias declaradas, con trazabilidad del camino y control de cascadas. No se promete detectar dependencias escondidas en prosa. Una lectura semántica periódica o motivada por incidentes puede proponer las relaciones faltantes. Ausencia de arista significa ausencia de relación declarada, no independencia demostrada.


## Contrato normativo incorporado: autoridad y escritura

### Identidad y aprobación

La evidencia mínima de ratificación contiene identidad autenticada, capacidad ejercida, contenido aprobado, revisión base, fecha de aprobación, ámbito y efecto temporal autorizado. Se vincula a un digest canónico de la propuesta: cláusulas, relaciones, fechas y campos que cambian su significado. Los eventos de auditoría y proyecciones generadas se excluyen de ese digest mediante una regla explícita para evitar autorreferencia.

`verified`, `autor`, trailers o `autorizado_por` escritos por un agente son declaraciones hasta contrastarlos con el mecanismo de confianza. La aprobación puede originarse en una revisión autenticada, un panel controlado u otro canal con identidad verificable. Copiar una frase de conversación no la convierte automáticamente en un evento de aprobación.

La política de autoridad se evalúa desde la base anterior al cambio y en el momento de aprobar. Una operación no puede concederse autoridad y usarla para aprobarse. El arranque inicial declara una raíz humana de confianza y deja evidencia de su configuración. La revocación de un rol no borra aprobaciones históricas; su efecto sobre aprobaciones aún no integradas se aplica según la política explícita y se revalida al integrar.

Un cambio sustantivo posterior exige nueva aprobación. Un cambio de la base exige revalidar el impacto; si cambia el significado o alcance aprobado, también la aprobación. Un agente no ocupa un rol ratificador. Las acciones bajo delegación se registran como ejecuciones de esa delegación, no como nuevas decisiones humanas.

### Puerta de integración

Git conserva snapshots y diffs; el servidor o mecanismo de integración aplica la puerta efectiva. Un hook local ayuda, pero no es la frontera de seguridad. Se protegen la rama canónica, los controles obligatorios, el comprobador, los esquemas y la política de autoridad. Las excepciones administrativas son explícitas, limitadas y auditadas; no se anuncian garantías sobre caminos que permiten omitirlas.

Flujo: propuesta en rama aislada → validación → revisión de contenido e impacto → aprobación autenticada → revalidación contra la base actual → integración → recibo. El usuario ve diferencias comprensibles y evidencia relevante; no se presupone que un diff de YAML sea una interfaz suficiente.

Todo escritor pasa por la misma puerta. Restringir temporalmente a un único escritor puede reducir coordinación, pero no sustituye los controles. Una lectura autorizada utiliza un snapshot canónico; lo propuesto y lo no confirmado se muestran separados.

### Recibos y fallos parciales

Una operación registra ID idempotente, base esperada, propuesta, resultado observado y revisión integrada, si existe. Se distingue entre propuesta preparada, escritura local, integración canónica y efecto externo confirmado. El recibo se construye desde la relectura del estado real y la evidencia del sistema que realizó la operación.

Si hay discrepancia o pérdida de respuesta, el estado es **resultado desconocido o parcial**, no «no ocurrió». Se inspecciona antes de reintentar y se reconcilia o compensa lo que sí ocurrió. Un commit no acredita por sí solo que un correo se envió, un despliegue terminó o un archivo externo se guardó.


## Instrucciones persistentes, procedimientos y referencias resolubles

### Distribución de responsabilidades

Las instrucciones persistentes del agente describen su comportamiento en todas las sesiones: criterio, iniciativa dentro del encargo, relación con la persona, comunicación, tratamiento de evidencia e incertidumbre y respeto por la autorización vigente. Los archivos de entrada de cada cliente cargan ese perfil mediante un mecanismo probado. No son la definición del sistema ni una copia de su manual operativo.

Los conceptos, contratos y resultados pertenecen a las referencias de diseño. Los responsables, ámbitos, permisos y parámetros pertenecen a políticas y configuración versionadas. Los pasos para investigar, registrar, verificar o entregar pertenecen a procedimientos y skills cargados cuando corresponda. Las restricciones verificables se aplican en el núcleo y en las puertas de efectos e integración. El contexto de tarea reúne objetivo, restricciones, evidencias y estado pertinente. Extraer un protocolo de las instrucciones permanentes exige mantener un punto de entrada que lo descubra y un responsable que lo aplique.

El comportamiento permanente debe ser breve y estable; no incluye catálogos de comandos, esquemas, listas de validaciones ni tablas completas de herramientas. Una restricción esencial puede expresarse también como comportamiento esperado, pero su cumplimiento mecánico no depende solo de que el modelo recuerde una frase. El código acredita comportamiento implementado; la política o decisión aceptada acredita lo autorizado o deseado. Una discrepancia entre ambos se identifica y resuelve sin convertir automáticamente uno en sustituto del otro.

### Referencias navegables y locales al repositorio

Toda referencia destinada a llevar al lector a otro documento o sección usa un enlace Markdown con destino resoluble. Las referencias internas usan rutas relativas al archivo que contiene el enlace; las secciones utilizan fragmentos estables. Los nombres de archivo entre comillas de código sirven para nombrar artefactos, no sustituyen un enlace cuando se pide consultarlos. Se evita depender de numeración de sección, títulos abreviados o ubicaciones descritas solo en prosa.

Ejemplo de sintaxis desde un archivo en la raíz, con destino ficticio que la instalación debe crear y validar:

```markdown
Consulta [el contrato de integración](docs/sistema/integracion.md#puerta-integracion).
```

Un ancla explícita como `<a id="puerta-integracion"></a>` conserva identidad aunque cambie el título visible, siempre que el visor utilizado la soporte. La instalación prueba sus visores; si requiere otra convención de fragmentos, la declara y valida. Cambiar o mover un destino exige actualizar referencias o conservar un alias resoluble. Las citas de evidencia externa fijan versión o revisión y localizador cuando la reproducción lo requiera; las referencias operativas a documentación vigente se resuelven dentro de la revisión del proyecto.

El mismo criterio se aplica a documentación, skills, descripciones de agentes y comentarios que remiten a documentación. En comentarios Python, JavaScript o shell, el enlace sigue siendo texto comentado. Las relaciones estructuradas del conocimiento conservan IDs y tipos del contrato; el renderizador genera sus enlaces. No se introduce Markdown dentro de un campo de IDs para hacerlo navegable.

### Enlazar, importar y recuperar son operaciones distintas

Un enlace identifica un destino; no demuestra que el agente haya leído su contenido. Un import incorpora contenido al contexto. Solo se utiliza una sintaxis de importación en archivos y clientes cuyo adaptador la soporte y se haya probado; `@ruta` no se presume una convención universal ni un permiso para ejecutar el contenido importado. Tampoco se presume soporte de imports de fragmentos. No se importan desde la entrada permanente el núcleo, el manual de procedimientos ni cadenas que acaben cargándolos completos.

El adaptador descubre los destinos declarados, comprueba acceso y recupera lo necesario para la tarea. La carga transitiva tiene límites de alcance, profundidad y presupuesto; informa ciclos, ausencias y contenido omitido. Leer un archivo enlazado no eleva las instrucciones contenidas en una fuente a política del sistema.

`rg` o `git grep` sirven para localizar referencias y buscar el fragmento de interés en archivos ya identificados. No sustituyen al parser de enlaces ni garantizan cobertura completa. La lectura puede acotarse por ancla o sección mediante una herramienta que conserve límites y condiciones pertinentes; no se extrae una coincidencia aislada si su significado depende del resto de la sección.

### Validación y migración

El validador de referencias comprueba existencia y capitalización de rutas, resolución y unicidad de fragmentos, enlaces tras movimientos y los imports efectivamente habilitados. Respeta bloques de código, escapes y ejemplos literales para no tratarlos como referencias activas. Los imports tienen validación específica por cliente y se prueban al cambiar su versión. Las comprobaciones externas distinguen enlace inaccesible, acceso denegado y recurso ausente; una comprobación no realizada no se declara válida.

La migración inventaría referencias informales, resuelve su destino y propone enlaces. No convierte automáticamente una numeración de sección en un ancla supuesta. Prioriza documentos vigentes y caminos operativos; los registros aceptados o históricos mantienen su protección y pasan por el procedimiento autorizado de corrección o por una vista navegable derivada. El inventario mantiene visibles los casos históricos pendientes hasta cubrir todo el alcance del repositorio. La CI bloquea nuevas referencias operativas irresolubles; la deuda anterior se registra explícitamente sin imponer una reescritura histórica silenciosa.

**Aceptación:** mover un destino conserva o repara los enlaces entrantes; renombrar un título conserva su ancla estable; un fragmento inexistente falla; los ejemplos literales no disparan cargas; el import permanente no arrastra procedimientos completos; una tarea descubre y carga su procedimiento por el punto de entrada previsto. Este control amplía VAL-02 y VAL-14 y acompaña a ESC-05 y ESC-09 cuando sus adaptadores estén habilitados.

## Capa de operación, acceso y mejora del harness

### Responsabilidad y límites

La capa de operación del conocimiento entrega a cada tarea evidencia, reglas vigentes, procedimientos aplicables y estado de ejecución; recibe propuestas y resultados mediante operaciones controladas. «KOL» es aquí una denominación descriptiva de esta responsabilidad, no un estándar de conformidad ni una nueva clase de registro. Su éxito se mide por RES-01 a RES-07. Un grafo, un repositorio o un servidor accesible por agentes no demuestran por sí solos ese resultado.

Se distinguen tres objetos: **conocimiento del dominio** (qué se sabe y qué rige), **conocimiento procedimental** (cómo abordar una clase de trabajo) y **estado de ejecución** (qué ocurrió en una tarea concreta). Una traza no se transforma automáticamente en procedimiento; un procedimiento no concede permiso; una decisión histórica no se generaliza fuera de su ámbito y condiciones. La frecuencia de uso, la valoración positiva y la confianza declarada por un modelo son señales para investigar, no pruebas de verdad ni autoridad.

Un procedimiento reutilizable se representa mediante los tipos existentes: `sintesis` para una guía derivada; `decision` para reglas ratificadas; `plan` e `hito` para trabajo concreto y su aceptación. Su cuerpo debe identificar ámbito, entradas, precondiciones, pasos, salidas observables, comprobaciones, efectos externos, condiciones de parada, recuperación y fuentes. Estos son apartados del contenido, no nuevos campos YAML obligatorios ni código ejecutable. El adaptador que automatice pasos necesita además un contrato ejecutable validado. Una guía derivada no sustituye las decisiones que cita ni hereda su autoridad sobre contenidos añadidos.

### Un núcleo, varios canales y almacenes con dueño explícito

Git es el almacén versionado elegido para los registros canónicos. GitHub puede alojarlo y facilitar revisión e integración; no es obligatorio ni sustituye los controles del núcleo. MCP es un protocolo de acceso a capacidades, no el almacén de conocimiento, el sistema de autorización del negocio ni el ciclo de vida del agente. El harness coordina cuándo se consultan esas capacidades y cómo se aplican sus resultados durante la tarea.

Arquitectura inicial: **agente o persona → adaptador CLI/biblioteca/MCP → núcleo de dominio → registros canónicos y fuentes autorizadas**. El núcleo reúne consulta, temporalidad, autoridad, validación e integración. Los adaptadores traducen entradas y salidas sin duplicar esas reglas. No se requiere desplegar microservicios: biblioteca y adaptadores pueden ejecutarse en un único proceso o equipo.

Se conserva un único dueño por clase de dato: registros aceptados y sus eventos normativos en el almacén canónico; originales en el repositorio de evidencias autorizado; índices como vistas reconstruibles; trazas, colas y recibos operativos en el registro de ejecución definido por la instalación. Este último puede ser inicialmente un conjunto de archivos. Sus resultados se incorporan al conocimiento mediante referencias y propuestas explícitas. No se copian todos los logs a Git ni se crea una segunda verdad normativa. Los cambios entre almacenes usan identificador idempotente y reconciliación; no se presupone una transacción distribuida.

La primera entrega necesita un canal operativo completo. El adaptador MCP se incorpora cuando un cliente concreto vaya a usarlo y pueda pasar la misma aceptación que la CLI. Un servidor MCP local no exige construir una plataforma alojada. El servicio remoto se justifica cuando exista una necesidad de acceso compartido, clientes sin copia local, disponibilidad central, revisión accesible a otros perfiles o permisos incompatibles con repartir el repositorio completo. Antes de activarlo se prueban identidad, aislamiento, concurrencia, recuperación y operación del servicio.

La identidad proviene del canal autenticado y su mapeo autorizado, nunca de un `actor` enviado libremente por el modelo. Consultar, proponer e integrar son capacidades separadas. Si el perfil no habilita una operación, el adaptador no la expone o la rechaza. Toda operación con efectos revalida permisos en el núcleo. Una interfaz MCP no protege contra escrituras directas al almacén: las credenciales, rutas de escritura e integración deben cerrar los caminos fuera del control declarado. En perfiles con lectores de distinto alcance no se distribuye a todos una copia Git con todo el historial; las respuestas, índices y cachés deben respetar el alcance efectivo.

El harness solicita contexto al iniciar o reanudar y ante cambios materiales de objetivo, fuente, autorización o revisión. Verifica precondiciones antes de los efectos y registra el resultado al cerrar. Exponer una herramienta no garantiza que el agente la llame. Donde la consulta sea obligatoria, el punto de entrada controlado verifica que se hizo y bloquea el efecto si falta; un recordatorio en el prompt solo ofrece una garantía de mejor esfuerzo.

### Paquete de contexto para una tarea

Se incorpora la operación `preparar_contexto`, de solo lectura. Recibe `tarea`, `objetivo`, `ambito`, `revision`, los cortes temporales y `presupuesto_contexto`; el núcleo obtiene el principal del canal. Devuelve el sobre común de operaciones y un paquete con:

- Identificador del paquete, tarea, revisión y política aplicadas, instante de preparación y alcance autorizado.
- Objetivo y restricciones pertinentes; decisiones y cláusulas efectivas; procedimientos aplicables y sus precondiciones.
- Evidencias con versiones y localizadores; pendientes, conflictos, incertidumbres y condiciones de parada.
- Estado persistido de la tarea, propuestas aún no integradas y siguiente paso justificado, diferenciados.
- Elementos incluidos y omitidos, motivo, cobertura y dependencias cuya modificación exige refrescar el paquete.

El presupuesto declara cantidad y unidad; si usa tokens, identifica el contador o la estimación aplicada. Limita el contexto, no permite omitir silenciosamente una condición decisiva. Si las condiciones obligatorias no caben, el resultado es parcial o bloqueado y permite reducir el alcance o ampliar el presupuesto. Un paquete puede referenciar evidencia recuperable bajo demanda; no carga toda la base. No concede una autorización portable ni permite ejecutar con permisos revocados: cada efecto revalida autoridad y precondiciones. La caché incluye revisión, parámetros temporales, alcance de acceso, versión de política y generador; ante una revocación se invalida antes de servir de nuevo. Una sesión abierta no prolonga el acceso por sí misma. La revocación impide nuevas entregas y efectos; no borra información ya recibida por un cliente, cuyo tratamiento exige controles propios de retención y sesión.

### Fuentes federadas y cambios externos

La fuente operativa conserva la responsabilidad sobre sus hechos; la base conserva sus interpretaciones, decisiones y versiones de evidencia permitidas. Conectar un sistema externo no exige trasladar todo su contenido ni convierte sus mensajes en instrucciones. Los eventos disparan revisión o ingesta propuesta; no ratifican decisiones. Para cada conector se declara sistema origen, alcance de acceso, política de copia/retención, mecanismo de cambios, última comprobación y demora admisible para el uso previsto.

Cada observación registra identidad del objeto, versión o huella, identificador del evento si existe, instante del origen cuando esté disponible, instante de recepción y comprobación de acceso. Si no hay identificador de evento, el conector deriva una clave estable del origen, objeto y versión; si no puede distinguir versiones no declara entrega única garantizada. Los reintentos no duplican propuestas; los eventos fuera de orden no revierten la versión vigente. El checkpoint se avanza solo después de persistir el recibo y el estado recuperable correspondiente.

Webhooks y sondeos pueden perder cambios. Se declara y prueba la reconciliación periódica con el origen; no se promete tiempo real sin medirlo. Una desconexión informa cobertura y antigüedad; si la frescura exigida no puede acreditarse, se bloquea la conclusión o acción que dependa de ella. Un cambio marca consumidores para revisión, conservando historia. Una baja o revocación de acceso retira el contenido de las respuestas e invalida índices y cachés afectados; la conservación restringida de evidencia depende de la política autorizada, no de que Git permita guardar historia. Si el almacén no puede cumplir eliminación o aislamiento exigidos, esa clase de datos no se incorpora allí.

### Mejora del harness con promoción controlada

El conocimiento puede ayudar a mejorar un harness y el harness puede proponer mejoras de conocimiento. Ambos ciclos se separan: **capturar → interpretar → validar → aceptar conocimiento** y **observar fallos → proponer un cambio operativo → experimentar → evaluar → promocionar una versión del harness**. Un éxito de tarea no prueba que su estrategia sea generalizable; el resultado de una ejecución tampoco ratifica los hechos que el modelo haya supuesto.

El perfil declara una superficie ajustable: selección y orden del contexto, instrucciones de tarea, procedimientos, estrategias de herramientas o scripts de alcance acotado. Quedan fuera del permiso del optimizador las raíces de confianza, autorizaciones, aislamiento, controles de integración, datos y evaluadores reservados, y criterios de aceptación de su propio experimento. Cambiar esos elementos requiere un procedimiento de gobierno separado. Un optimizador no obtiene derechos nuevos por modificar un prompt, una skill o un plugin. El código y los plugins candidatos se prueban aislados y no se instalan en producción como consecuencia de una reflexión.

Cada candidato conserva fallo observado, hipótesis, versión base, diferencia exacta, alcance, presupuesto, experimentos y resultados favorables y negativos. El experimento fija versiones de modelo, cliente, harness, herramientas, corpus y evaluador. Usa tareas de desarrollo para ajustar y tareas independientes para aceptar; el optimizador no accede a respuestas reservadas ni altera su evaluador. Se controla acceso a red cuando pueda contaminar la evaluación. El juicio de otro modelo es una señal complementaria, no una prueba independiente suficiente de corrección o autorización.

La promoción exige invariantes sin regresión, criterio de calidad previamente fijado y coste total dentro del presupuesto, incluyendo intentos descartados y tiempo humano. La mejora agregada no oculta una regresión crítica por tipo de tarea. La evidencia y sus límites quedan revisables. La promoción automática solo puede operar dentro de una delegación previa y acotada para cambios operativos; cambios normativos siguen su ratificación. Se conserva la versión anterior y se prueba reversión del harness; revertirlo no deshace efectos externos ya producidos, que requieren reconciliación o compensación propia.

La biblioteca de experiencia conserva condiciones de aplicabilidad, evidencia, contraejemplos y caducidad. Recuperar una lección antigua obliga a comprobar precondiciones actuales; no basta la similitud textual. Las lecciones obsoletas se retiran del uso vigente sin perder trazabilidad. Cada ciclo tiene límites de coste, tiempo e iteraciones y se detiene si no hay evidencia de mejora. Esta capacidad es opcional: el primer recorrido útil se entrega con un harness estable, y la experimentación empieza cuando existan fallos repetidos, trazas y una línea base evaluable.

### Aceptación de estas capacidades

**ESC-09 — Acceso equivalente y contexto restringido (RES-01, RES-03, RES-04).** Con el mismo principal, revisión y consulta, CLI y MCP devuelven las mismas cláusulas, citas, advertencias y decisión de acceso, aunque cambie la presentación. Un usuario sin acceso no recibe el contenido ni indicios sensibles en errores. Un presupuesto insuficiente no elimina la restricción decisiva. Revocar acceso después de preparar el paquete impide reutilizarlo para leer de nuevo o ejecutar. El escenario del segundo adaptador es exigible al anunciarlo; no obliga a construirlo en la primera entrega.

**ESC-10 — Optimización sin autoautorización (RES-02, RES-06, RES-07).** Un candidato reduce latencia eliminando una comprobación obligatoria: se rechaza aunque mejore la media. Otro mejora recuperación sin cambiar permisos: solo se promociona tras evaluación independiente y aprobación o delegación válida. Su versión y recibo permiten restaurar el harness anterior. Si el candidato falla, su coste sigue incluido en la medición. El optimizador no puede editar el test que le ha rechazado.

**ESC-11 — Cambios, duplicados y pérdida de acceso (RES-04, RES-05, RES-06).** Una fuente emite versión 2, repite el evento y luego llega versión 1: se conserva una única propuesta para versión 2, sin retroceder. Un fallo antes de persistir el recibo permite reintentar sin perder el cambio. La reconciliación detecta una versión omitida por el webhook. Una revocación retira respuestas y cachés afectadas; una consulta histórica informa el límite de acceso sin revelar el texto. La demora de detección queda medida frente al presupuesto declarado.

## Contratos concretos de referencia

Esta sección fija convenciones suficientes para producir la primera implementación sin recurrir a otra especificación. Las extensiones se versionan. Los ejemplos utilizan identidades ficticias y no configuran una autoridad real.

### Registro y eventos

El contenedor canónico es un archivo UTF-8 con cabecera YAML delimitada por `---` y cuerpo Markdown. La cabecera es un mapa; se rechazan claves repetidas, etiquetas de construcción de objetos y valores cuyo tipo no coincida con el contrato. Se usa un parser seguro. Los campos desconocidos se conservan en intercambios y se rechazan en escritura canónica hasta que el esquema declare su lector. No se ejecuta contenido de la cabecera ni del cuerpo.

Campos comunes obligatorios: `id` (cadena estable), `type` (tipo), `clase` (clase documental), `title` (cadena), `description` (cadena de una línea), `ambito` (ID de ámbito), `estado` (enumerado del tipo), `autor` (ID de actor), `eventos` (lista) y `sources` (lista, vacía si no hay fuentes). Los IDs nuevos son prefijo de tipo más UUID; los heredados únicos se conservan. Los prefijos de referencia son F, HE, DEC, PER, ROL, Q, HIP, SUP, ENT, PL, HI y SIN. La clase documental es registro, fuente, fijo, vista o archivo.

Cada evento admitido contiene `evento_id`, `tipo_evento`, `actor`, `registrado_en`, `valido_desde`, `motivo` y `evidencia_evento`. `valido_hasta` es opcional. Una transición contiene además `estado_anterior` y `estado_nuevo`; en el evento inicial, el anterior es nulo. Los timestamps llevan zona. La evidencia del evento identifica el mecanismo y el comprobante con el que se verificó su incorporación. Los eventos locales no admitidos permanecen en la propuesta; no inventan fecha canónica ni autenticación.

El estado materializado debe coincidir con el historial admitido. Una transición de aceptación que todavía no entra en vigor puede estar aceptada como acto, pero la consulta de vigencia la muestra como futura. Las consultas históricas reconstruyen el estado desde los eventos admitidos hasta el corte de conocimiento; nunca filtran únicamente la cabecera actual.

| Tipo | Campos adicionales mínimos |
| --- | --- |
| Fuente original | `subtipo: original`, `origen`, `ubicacion`, `formato`, `sha256`, `acceso`. |
| Fuente derivada | `subtipo: derivada`, `derivada_de`, `ubicacion`, `formato`, `sha256`, `procesador`, `version_procesador`, `configuracion_ref`, `procesado_en`, `procesamiento`, `calidad`, `acceso`. |
| Hecho | `afirmacion`, `clase_evidencia`, `basada_en`; fecha o intervalo de la afirmación, con su precisión. |
| Decisión | `autorizado_por`, `alternativas`, `criterios`, `justificacion`; cláusulas en el cuerpo; efectos temporales en sus eventos. |
| Persona | `naturaleza: humana` o `agente`, `identidad_ref`, `ocupa`. |
| Rol | `ambitos`, `capacidades`, `regla_aprobacion`; el cambio de estos campos requiere autoridad previa. |
| Entidad | `nombre`, `alias` y `clase_entidad`. |
| Pregunta | `subtipo: incognita`, `incidencia` o `discrepancia`, `responsable`, `condicion_cierre`; plazo cuando exista. |
| Hipótesis | `afirmacion`, `plan_prueba`, `criterio_refutacion`, `consecuencia_si_falla`. |
| Supuesto | `afirmacion`, `revisar_en`, `consecuencia_si_falla`. |
| Plan | `objetivo`, `hitos`, `autorizado_por`, `restricciones`. |
| Hito | `objetivo`, `alcance`, `autorizado_por`, `aceptacion`, `tolerancias`, `verificaciones`. |
| Síntesis | `dependencias`, `evaluaciones`; contenido en el cuerpo. |

`autorizado_por` es una lista no vacía de roles cuando se solicita aceptación/autorización. `regla_aprobacion` admite `uno`, `todos` o `quorum` con entero explícito. Por defecto se exige un ocupante humano válido por cada rol requerido; si un rol exige todos o quorum se aplica además ese requisito. Ningún rol relevante puede quedar satisfecho solo con actores agentes. Un mismo humano puede satisfacer varios roles que ocupe salvo que la política exija separación de funciones.

Las alternativas se guardan como objetos con identidad, descripción y motivo de selección/descarte. Cuando no hay elección real, se usa lista vacía y `sin_alternativas_motivo` obligatorio. No se añade una opción ficticia para cumplir forma.

`sources` contiene objetos `{id, resource}` y opcionalmente `ancla`, `representacion_id`, `hash` y `contexto`. `resource` identifica el registro fuente o artefacto, no una instrucción. Una cita a contenido transformado incluye `representacion_id`; el hash de la representación puede resolverse desde su ficha inmutable. Una referencia a un artefacto mutable externo necesita versión o hash explícito.

`calidad` contiene dimensiones evaluadas con método, resultado y límites. No evaluar una dimensión se representa como `no_evaluado`, no con cero errores. `procesamiento` admite pendiente, procesado, parcial o fallido. La admisión de una fuente y el resultado de su extracción se evalúan por separado.

### Relaciones serializadas

`resuelta_por`, `cuestiona`, `deja_obsoleta`, `pone_a_prueba`, `basada_en`, `derivada_de`, `afecta_a` y `autorizado_por` son listas de IDs o de `ID#ancla` donde la semántica admite cláusulas. Una fuente derivada tiene un original principal identificado en `derivada_de`; un resultado de múltiples entradas conserva la lista completa y describe el papel de cada entrada en procedencia.

`modifica` es una lista de `{destino, tipo, por?}`: sustitución y adición exigen `por`; derogación lo prohíbe. `depende_de` es una lista de `{destino, condicion}`; las condiciones iniciales son `aceptada_y_vigente`, `resuelta`, `completado_con_evidencia` y `disponible_con_integridad`. Otra condición exige extensión explícita. `ocupa` contiene `{rol, desde, hasta?}` más la evidencia de sus eventos. `veta` contiene `{patron, ambito, uso, exclusiones}`; el motor de patrones y sus límites se fijan en la versión del esquema y no ejecutan código arbitrario.

Por defecto una dependencia normativa inválida bloquea el trabajo que la necesita; una mera relación `afecta_a` genera contexto o impacto, no bloqueo automático. Los comentarios explicativos se guardan aparte de las referencias. El campo `hitos` del plan agrupa trabajo, pero no crea por sí solo una autorización ni una dependencia.

### Cláusulas y afirmaciones en Markdown

Una cláusula comienza con `<clausula id="C1">` en una línea propia y termina con `</clausula>` en otra. Su identificador cumple `C` seguido de letras, números, guion o subrayado; es único en la decisión y no depende de posición. No se anidan cláusulas. El texto dentro puede ser Markdown. Las marcas dentro de bloques de código delimitados por tres o más acentos graves o tildes no se interpretan. Una marca escapada tampoco abre una cláusula. Apertura sin cierre, cierre sin apertura o ID repetido son errores.

Una afirmación factual en línea usa `<hecho id="H1" evidencia="declarado" fuente="s1">…</hecho>`, con ID único, clase del enumerado y fuente existente en `sources`; su fecha se recoge en el contenido marcado o en el registro de hecho enlazado. Si tiene ciclo de vida propio se crea un registro hecho y se cita mediante `<hecho ref="HE-id">…</hecho>`. El texto visible conserva condiciones y unidades aunque el visor oculte las marcas.

### Digest y aprobación

El contenido aprobable se convierte a un objeto JSON con `id`, `type`, `clase`, `title`, `description`, `ambito`, `autor`, `cuerpo`, `campos` y `efectos_solicitados`. `campos` contiene todos los campos de contenido y relaciones del registro excepto eventos, proyecciones, cachés, recibos, `verified`, evaluaciones y referencias a la aprobación. `efectos_solicitados` contiene transiciones y sus fechas de validez, sin los timestamps de incorporación aún desconocidos. Por tanto, cambiar una fecha efectiva o una relación cambia el digest.

Serialización del perfil: claves ordenadas por código Unicode; arrays en el orden declarado; sin espacios; UTF-8 sin BOM; caracteres Unicode sin normalización; escape JSON obligatorio de comillas, barra inversa y controles; saltos del cuerpo normalizados a LF. Los valores numéricos del objeto son enteros exactos; los decimales se serializan como cadenas en el esquema. Campos volátiles no se eliminan heurísticamente. Digest = SHA-256 de esos bytes. Se publican vectores de prueba al implementar el serializador y todos los adaptadores deben producir el mismo digest.

La aprobación admitida registra `{aprobacion_id, actor, identidad_ref, roles, digest, revision_base, aprobada_en, politica_revision, comprobante}`. El comprobante debe poder contrastarse mediante una identidad/servicio de confianza; guardar ese objeto sin verificarlo no acredita nada. Rechazos y revocaciones son eventos separados. Cambiar contenido cubierto por el digest invalida la aprobación para la nueva propuesta. Un cambio de base obliga a recalcular alcance y vigencia antes de reutilizar una aprobación; un cambio semántico exige renovarla.

### Tipos canónicos, ejecución y evaluación

Los valores de `type` son exactamente `fuente`, `hecho`, `decision`, `persona`, `rol`, `pregunta`, `hipotesis`, `supuesto`, `entidad`, `plan`, `hito` y `sintesis`. Los nombres con acentos utilizados en prosa son etiquetas de presentación. Los estados serializados son los literales de la tabla de estados de este documento. Los actores usan `human:<id>`, `process:<id>` o `<productor>/<version>`; su cadena identifica, pero no autentica.

Eventos iniciales admitidos: `creacion`, `transicion`, `ratificacion`, `revocacion_aprobacion`, `evaluacion`, `cambio_ocupacion`, `resolucion_impacto` e `importacion`. Los eventos contienen solo los campos pertinentes a su clase. La política valida el actor y la evidencia para cada uno. La incorporación de una propuesta nueva crea su evento de creación; en una propuesta aún no incorporada la lista puede estar vacía y no tiene tiempo canónico.

Por defecto no se reabre una decisión o hecho aceptado: se crea su sucesor. Una pregunta resuelta o descartada y un hito completado pueden reabrirse mediante transición motivada del mismo nivel de autoridad que autorizó su cierre, conservando el cierre anterior e indicando qué evidencia lo invalida. El destino es `abierta` para preguntas y `autorizado` para hitos, sujeto a que la autorización siga vigente. Una hipótesis validada/refutada se revisa mediante una nueva hipótesis vinculada; no se borra su resultado experimental anterior.

`tolerancias` es un objeto con límites declarados de tiempo, coste, recursos y alcance. Un límite ausente no significa ilimitado: se hereda de la delegación cuando esta lo define o la acción que lo necesita queda pendiente de autorización. `aceptacion` es una lista de `{criterio_id, descripcion, metodo, obligatorio}`; `metodo` es `comando`, `revision_humana` o `evaluacion_ia_asistida`. Esta última requiere rúbrica y criterio humano de resolución del desacuerdo.

`verificaciones` contiene `{verificacion_id, criterio_id, ejecutor, entrada, entorno_ref, timeout, efectos_permitidos}`. El ejecutor resuelve un comando o función aprobados desde configuración controlada; el texto de una fuente no se interpola en una shell. La entrada no puede introducir rutas o argumentos fuera del alcance autorizado. Un comando exige código de salida esperado y evidencia capturada; un criterio semántico exige además la comprobación que declare su método.

Cada resultado de verificación contiene `{verificacion_id, revision_probada, entorno_ref, iniciado_en, terminado_en, resultado, evidencia_ref, observaciones}`. `resultado` es `superado`, `fallido`, `no_ejecutado` o `requiere_revision`. Completar un hito requiere todos los criterios obligatorios superados sobre la revisión aplicable y aceptación humana cuando el método la exige. Un test omitido nunca equivale a superado. La política determina si una modificación posterior invalida evidencia por dependencia; no se reutiliza un resultado de otra revisión sin justificar esa equivalencia.

Una evaluación de contenido o representación contiene `{evaluacion_id, sujeto_id, digest_o_huella, dimensiones, metodo, actor, realizada_en, resultado, evidencia_ref, limitaciones}`. `resultado` admite `conforme`, `no_conforme`, `parcial` y `no_evaluado`. Una evaluación humana puede ser negativa. Una nueva evaluación no borra la anterior; la consulta muestra la aplicable al contenido y las discrepancias sin resolver.

Una delegación contiene `{delegacion_id, otorgante, beneficiario, ambitos, operaciones, recursos, limites, valido_desde, valido_hasta, revocada, aprobacion_ref}`. La puerta verifica identidad y autoridad del otorgante, vigencia, no revocación y correspondencia de la acción con todos los límites. El beneficiario no puede editar esa delegación para ampliar su alcance.

### Ejemplo completo de propuesta de decisión

Esta propuesta ficticia todavía no está integrada y no tiene ratificación. `DEC-EJEMPLO` y `ROL-EJEMPLO` son identidades del corpus de prueba. La prueba de referencias crea primero el rol; no se permite resolverlo por el nombre visible de una persona.

```yaml
---
id: DEC-EJEMPLO
type: decision
clase: registro
title: Calendario de entrega del informe
description: Entregar el informe los martes usando solo datos verificados.
ambito: operaciones
estado: propuesta
autor: agente-ejemplo/1
eventos: []
sources: []
autorizado_por: [ROL-EJEMPLO]
alternativas:
  - id: A
    descripcion: Entrega los lunes.
    seleccionada: false
    motivo: No deja un día para verificar los datos del cierre semanal.
  - id: B
    descripcion: Entrega los martes.
    seleccionada: true
    motivo: Reserva el lunes para verificar los datos.
criterios: [Disponibilidad de datos verificados, Plazo de entrega]
justificacion: Se propone reservar un día para la verificación.
---
```

Cuerpo Markdown de esa misma propuesta:

```markdown
<clausula id="C1">
El informe se entrega los martes.
</clausula>

<clausula id="C2">
El informe solo incluye datos verificados.
</clausula>
```

La propuesta puede validarse como propuesta si el rol y el ámbito existen. No autoriza la entrega del informe ni acredita la aceptación de la política. Para aceptarla, la operación solicita una transición con fecha de validez, calcula el digest que la incluye, obtiene el comprobante autenticado y genera los eventos admitidos al integrar. Cambiar martes por miércoles después de aprobar requiere otro digest y nueva aprobación.

### De resultado a trabajo implementable

Cada unidad de desarrollo contiene estos campos, cumplimentados con información concreta: `resultado_res`, `escenario_esc`, `comportamiento_actual`, `comportamiento_esperado`, `cambio_minimo`, `dependencias`, `prueba`, `criterio_integracion`, `evidencia_entrega` y `limites`. No se acepta como tarea terminada «crear módulo» o «redactar documento» sin vincularlo a un comportamiento verificable.

Ejemplo: RES-01 / ESC-01; la consulta devuelve la decisión antigua completa; debe devolver C1 de DEC-B y C2 de DEC-A; cambio mínimo en resolución de cláusulas y presentación; prueba con los tres registros del escenario; integración sin conflictos; evidencia de consulta en una sesión nueva. No requiere incorporar un índice vectorial ni un segundo cliente para terminar.


### Interfaces mínimas

Las interfaces pueden ser CLI, biblioteca o API; su semántica es la misma. Toda respuesta incluye `operacion_id`, `revision`, `valido_en`, `conocido_hasta`, `resultado`, `advertencias` y `cobertura`. Si un campo temporal no aplica se devuelve nulo, no una fecha inventada. `cobertura` identifica alcance examinado, truncamiento y elementos no evaluados.

| Operación | Entrada mínima | Salida y efecto |
| --- | --- | --- |
| `validar` | Propuesta, revisión base, política. | Errores y cambios derivados; no integra. |
| `consultar` | ID o criterio, nivel, revisión y cortes temporales. | Contenido, procedencia, autoridad, vigencia y límites; no escribe ni ejecuta verificaciones. |
| `preparar_contexto` | Tarea, objetivo, ámbito, revisión, cortes y presupuesto. | Paquete contextual autorizado con restricciones, evidencia, omisiones y condiciones de refresco; solo lectura. |
| `consolidar` | Decisión, revisión y cortes. | Cláusulas efectivas con origen; propuestas separadas. |
| `impacto` | Propuesta/cambio y revisión base. | Afectados, caminos, responsables y resoluciones pendientes. |
| `integrar` | ID idempotente, propuesta, base y aprobaciones. | Revisión integrada y recibo, conflicto o resultado por reconciliar. |
| `relevo` | Sesión/tarea y revisión. | Objetivo, autorización, límites, estado persistido y próximos pasos justificados. |
| `verificar` | Hito, revisión, ejecutor y autorización. | Resultado por criterio, entorno, tiempos, evidencias y efectos; requiere aislamiento. |
| `ingerir` | Fuente, política de acceso y perfil de procesamiento. | Fuente/derivación propuesta, procedencia y calidad; no ratifica interpretación. |
| `integridad` | Fuentes y política de comprobación. | Coincide, alterada, ausente o no comprobada, con causa y última comprobación válida. |

Errores mínimos: `ESQUEMA_INVALIDO`, `REFERENCIA_AUSENTE`, `AUTORIDAD_INSUFICIENTE`, `APROBACION_CADUCADA`, `BASE_CAMBIADA`, `CONFLICTO_NORMATIVO`, `TIEMPO_AMBIGUO`, `INTEGRIDAD_ROTA`, `INTEGRIDAD_NO_COMPROBADA`, `EVIDENCIA_INSUFICIENTE`, `ACCESO_DENEGADO` y `RESULTADO_DESCONOCIDO`. Un código describe causa; `bloqueado`, `parcial` o `fallido` describen resultado operativo. No se confunden.

La integración revalida la base antes de escribir. Un cambio de base devuelve `BASE_CAMBIADA` y no reintenta una nueva decisión silenciosamente. Repetir el mismo ID con el mismo contenido devuelve el recibo previo; con contenido distinto se rechaza. Las acciones externas usan además su propia evidencia idempotente o requieren reconciliación cuando el proveedor no la permite.

### Parámetros iniciales y ausencia de datos

Perfil inicial: un proyecto, un escritor, miembros con lectura común, consultas sobre archivos, integración controlada y fuentes textuales. Las acciones externas están deshabilitadas hasta declarar su delegación. No hay ejecución automática de verificaciones al abrir una sesión. Las excepciones críticas pausan el trabajo afectado cuando no pueden revisarse; las ordinarias se agrupan para la siguiente revisión del responsable.

No se puede activar escritura aceptada sin identidad, raíz de confianza y responsables. No se puede activar procesamiento externo sin clases de datos y destinos autorizados. No se puede afirmar ahorro sin línea base ni corrección sin rúbrica. Los presupuestos de rendimiento, atención y retención son parámetros reales de instalación; el implementador debe obtenerlos o declarar explícitamente la capacidad no habilitada, sin crear números ficticios.

## Escenarios de aceptación autocontenidos

Los escenarios siguientes fijan resultados esperados. Son datos de prueba ficticios y no decisiones de un proyecto. La implementación los convierte en pruebas reproducibles; sus IDs cortos se admiten como IDs heredados del corpus de prueba. Se ejecutan con un reloj fijado y un snapshot identificado.

### ESC-01. Sustitución parcial sin pérdida de condiciones

Base conocida hasta el 3 de noviembre de 2026 a las 12:00 UTC:

- DEC-A, aceptada el 1 de noviembre y válida desde ese instante: C1 «El informe se entrega los lunes»; C2 «El informe solo incluye datos verificados».
- DEC-B, aceptada el 2 de noviembre y válida desde ese instante: C1 «El informe se entrega los martes». Declara `modifica: [{destino: DEC-A#C1, tipo: sustitucion, por: DEC-B#C1}]`.
- DEC-C, propuesta: C1 «El informe incluye también datos estimados». Propone sustituir DEC-A#C2, sin aprobación.

**Resultado esperado:** consolidar DEC-A devuelve la entrega los martes con origen DEC-B#C1 y la restricción de datos verificados con origen DEC-A#C2. DEC-A está parcialmente vigente. DEC-C aparece como propuesta no vinculante. Responder que se admiten estimados, que DEC-A murió entera o que sigue entregándose los lunes es un fallo.

**Variante de conflicto:** otra decisión aceptada pretende reemplazar DEC-A#C1 en el mismo intervalo sin declarar sucesión respecto de DEC-B. La integración devuelve `CONFLICTO_NORMATIVO`; el estado canónico conserva el resultado anterior.

### ESC-02. Dos cortes temporales

DEC-T se registra el 10 de noviembre a las 09:00 UTC, con validez desde el día 15: C1 «El plazo es de cinco días». El día 20 a las 09:00 UTC se admite DEC-U, bajo una aprobación que autoriza expresamente retroactividad desde el día 12: C1 «El plazo es de siete días». DEC-U añade esa regla desde el día 12 y sustituye expresamente DEC-T#C1 durante el intervalo en que esta habría aplicado. No hay otra regla previa.

**Consulta A:** válido el día 13 a las 12:00, conocido hasta el día 14 a las 12:00. Resultado: no consta una regla aplicable; DEC-T es futura y DEC-U todavía no se conoce.

**Consulta B:** válido el día 13 a las 12:00, conocido hasta el día 21 a las 12:00. Resultado: siete días, con aviso de incorporación posterior y efecto retroactivo.

**Consulta C:** válido el día 16 a las 12:00, conocido hasta el día 17 a las 12:00. Resultado: cinco días. La misma fecha de validez con conocimiento hasta el día 21 devuelve siete días. Nunca se cambia el instante real de incorporación de DEC-U.

### ESC-03. Autoridad vinculada al contenido

Una persona humana ocupa ROL-OPERACION y puede ratificar una decisión de ese ámbito. Un agente puede proponerla. La propuesta tiene digest D1 y base R1.

1. El agente añade por sí mismo `verified: [{by: human:persona, at: ...}]`: no hay aprobación autenticada; no se acepta.
2. La persona aprueba D1 por el canal confiable: la propuesta puede integrarse si las demás reglas pasan.
3. El agente cambia una cláusula y obtiene D2: la aprobación de D1 no autoriza D2.
4. El agente propone atribuirse el rol y aceptar su propia decisión en una operación: se evalúa la autoridad anterior y se rechaza.
5. Se pierde la respuesta después de integrar D1: repetir su ID de operación devuelve la revisión y recibo existentes, sin una segunda aceptación.

### ESC-04. Fuente, representación e impacto

F-A es un original; F-AR es su derivación y contiene una tabla citada por HE-A. HE-A conserva original, localizador y representación F-AR. Se ingresa F-B como nueva versión documental y se procesa como F-BR.

**Resultado esperado:** F-A y F-AR mantienen contenido y huellas; la consulta histórica resuelve la cita de HE-A en F-AR. HE-A requiere revisión de impacto, pero no se declara falso automáticamente. Reprocesar F-A produce F-AR2; no sustituye silenciosamente la tabla de una cita previa. Cambiar solo la ruta con la misma huella no invalida el contenido.

**Variante de calidad:** F-AR omite una columna que cambia la respuesta. Una evaluación negativa impide usarla como representación suficiente para esa pregunta; el sistema consulta el original o declara insuficiencia. Un timeout del almacén produce `INTEGRIDAD_NO_COMPROBADA`, no una acusación de manipulación.

### ESC-05. Continuidad sin autorización inventada

HI-A está autorizado para preparar un informe, con prohibición de enviarlo. La sesión redactó una propuesta en su rama, aún sin integrar, y una comprobación no se ejecutó por falta de acceso. Se interrumpe la sesión.

**Resultado esperado:** el relevo conserva objetivo, límite de no enviar, base, ubicación de la propuesta, estado no integrado y comprobación no ejecutada. El siguiente paso puede ser completar la verificación o pedir el acceso faltante. No anuncia informe entregado, no da la comprobación por superada y no ejecuta comandos para construir el relevo.

### ESC-06. Evidencia decisiva ausente y uso de IA

La pregunta es «¿Puede el informe incluir datos estimados?». La referencia revisada es ESC-01. Se prueba con las fuentes completas, con el consolidado suficiente y con un paquete al que se ha quitado la cláusula decisiva pero que declara cobertura incompleta.

**Resultado esperado:** las dos primeras respuestas conservan la restricción de datos verificados y la condición no vinculante de DEC-C. En la ablación, el agente declara que falta evidencia para determinar la política, o consulta la cláusula faltante si tiene permiso. No toma la propuesta como autorización. La evaluación comprueba conducta y significado, no coincidencia literal de frases.

### ESC-07. Medición del resultado

En una ventana, dos tareas cumplen su rúbrica y una falla. Entre ejecución, revisión, intento fallido y mantenimiento atribuible se consumen treinta minutos humanos.

**Resultado esperado:** se reportan tres intentos, dos resultados correctos, un fallo y quince minutos humanos por resultado correcto, además del desglose. Si una tarea correcta exige después diez minutos de corrección, se incorporan al coste y se actualiza su clasificación según la rúbrica. No se elimina el intento fallido para mejorar la razón.

### ESC-08. Conformidad y entrega

Una entrega pasa pruebas y tiene una rama preparada, pero no se ha integrado ni usado en una sesión nueva. Su estado es **preparada**, no **operativa**. Tras integración, recibo y recorrido real correcto se declara **operativa en el alcance probado**. El beneficio sostenido sigue pendiente hasta medir tareas representativas y errores tardíos.

La matriz final contiene por RES: escenarios ejecutados, revisión, entorno, resultado, evidencia, límites y responsable. Los fallos críticos de autoridad, condiciones normativas, integridad requerida o permisos impiden declarar conforme el resultado afectado. Los demás resultados independientes pueden avanzar dentro de su alcance autorizado.


## Identificación de esta referencia

Implementación 0.8, 3 nov 2026. Contiene el contrato necesario para construir y comprobar el sistema objetivo. Sustituye la guía 0.7; no declara migrada ni operativa ninguna instalación.


