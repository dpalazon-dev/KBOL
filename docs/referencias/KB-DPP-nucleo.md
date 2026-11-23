---
type: Referencia
title: "Sistema documental y base de conocimiento: núcleo"
description: "Contrato KB-DPP preservado para la instalación."
clase: fijo
estado: Borrador
status: draft
---

# Sistema documental y base de conocimiento: núcleo

**Versión:** 0.7 · **Estado:** referencia de diseño del sistema objetivo · **Fecha:** 3 nov 2026 · **Documento complementario:** [Implementación 0.8](KB-DPP-implementacion.md)

Este documento define el sistema general: propósito, conceptos, invariantes, contratos y límites. Incluye comportamiento, contratos concretos, escenarios y aceptación. La guía complementaria desarrolla la secuencia de construcción. Ninguno describe el estado desplegado de un proyecto. Adoptar esta revisión requiere una migración explícita; editar el diseño no modifica repositorios, permisos ni decisiones existentes.

La base conserva conocimiento en texto legible y versionado, con procedencia, autoridad y vigencia explícitas. Los agentes ayudan a descubrir, interpretar, proponer y ejecutar dentro de una autorización; las personas gobiernan las decisiones; el código aplica las restricciones que pueden comprobarse mecánicamente. Las garantías se limitan al alcance declarado y a los caminos efectivamente controlados.

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


<a id="objetivo-misión-y-visión"></a>
<a id="problema"></a>
<a id="propuesta"></a>
<a id="qué-no-es-el-sistema"></a>
## 1. Propósito, problema y alcance

**Objetivo.** Aumentar el trabajo correctamente resuelto con IA y reducir el tiempo humano total necesario para lograrlo, incluyendo explicación, supervisión, revisión, corrección y mantenimiento del propio sistema. Ocultar problemas para interrumpir menos es una regresión.

El problema aparece cuando una sesión no sabe qué parte de una decisión sigue vigente, confunde una propuesta con una autorización, utiliza una síntesis desfasada o pierde el objetivo y las restricciones al reanudarse. Disponer de más documentos o de una ventana de contexto mayor no resuelve por sí solo esas ambigüedades.

El sistema ofrece dos capacidades conectadas, con implantación y evaluación separables:

1. **Gobierno y continuidad operativa:** decisiones, preguntas, planes e hitos; autoridad; consultas de vigencia; evidencia de ejecución; relevo entre sesiones.
2. **Ingesta y conocimiento documental:** inventario de fuentes, representaciones, localizadores, extracción e interpretación, limitaciones de calidad y recuperación de evidencia.

La primera puede empezar con fuentes textuales ya disponibles. La segunda se amplía cuando tareas reales requieren documentos o modalidades que aún no se recuperan adecuadamente. No se exige resolver todas las modalidades para mejorar la continuidad.

**Casos de uso de referencia:** consultar qué rige y por qué; retomar una tarea con sus límites; proponer y ratificar un cambio; detectar qué queda afectado por una actualización; responder una pregunta con evidencia localizable o declarar qué falta. Cada instalación selecciona sus casos prioritarios y mide su línea base.

**Fuera del alcance de las garantías:** demostrar la verdad de cualquier afirmación, eliminar las alucinaciones, descubrir todas las relaciones implícitas, reemplazar el criterio de negocio, garantizar la mantenibilidad solo con tests o certificar cumplimiento normativo. Tampoco se pretende sustituir los sistemas de origen ni construir por defecto un gestor general de proyectos o una plataforma multiagente.

Sí es un método de trabajo apoyado por software: prescribe ciclos de conocimiento, revisión y recuperación. Su portabilidad es una propiedad deseable; su valor se demuestra en las tareas de quienes lo usan.

<a id="glosario"></a>
## 2. Glosario

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

<a id="principios-fundacionales-del-sistema-documental-y-base-de-conocimiento"></a>
<a id="dónde-se-aplica-cada-principio"></a>
## 3. Principios del sistema

Los identificadores P1–P25 permiten trazar requisitos, controles y resultados. El significado normativo completo se define en esta versión.

<a id="P1"></a>**P1. Acumular conocimiento reutilizable.** Conservar resultados útiles evita redescubrirlos; reutilizarlos exige comprobar vigencia y condiciones.

<a id="P2"></a>**P2. Separar original, representación e interpretación.** Una interpretación no reemplaza silenciosamente la evidencia de la que procede.

<a id="P3"></a>**P3. La IA propone y opera; las personas gobiernan.** El agente puede ejecutar dentro de una delegación verificable. No ratifica decisiones ni convierte su salida en evidencia observada.

<a id="P4"></a>**P4. Mantener lo que se usa.** Detectar contradicciones, dependencias desfasadas y conocimiento sin utilidad; revisar sin generar una burocracia automática por cada hallazgo.

<a id="P5"></a>**P5. Identidad estable y responsabilidad única.** Cada dato tiene dueño. Las proyecciones y la separación modular no crean un segundo dueño si su origen es explícito.

<a id="P6"></a>**P6. Texto legible como registro canónico.** Los registros normativos viven en archivos versionados; los originales y representaciones que requieren otros formatos se conservan como tales. Los índices son reconstruibles.

<a id="P7"></a>**P7. Procedencia, vigencia y límites viajan con el dato.** Una cita resoluble no prueba por sí sola que respalde la afirmación.

<a id="P8"></a>**P8. Lectura progresiva.** Servir primero lo necesario para decidir qué abrir, sin omitir condiciones que cambian la respuesta.

<a id="P9"></a>**P9. Portabilidad mediante contratos.** Fijar versiones, formatos y pruebas de conformidad; no prometer independencia de herramientas sin probar sus adaptadores.

<a id="P10"></a>**P10. Autoridad escrita y autenticada.** Los campos describen la autoridad; una evidencia verificable acredita quién aprobó qué contenido y bajo qué política.

<a id="P11"></a>**P11. Distinguir conocimiento normativo y factual.** La autoridad decide qué política rige. La corrección factual requiere evidencia; ambas pueden coexistir con incertidumbre.

<a id="P12"></a>**P12. Relaciones tipadas y semántica explícita.** Cada arista tiene un dueño y una dirección; las inversas se calculan. Las restricciones de ciclos dependen de la relación.

<a id="P13"></a>**P13. Conservar historia y corregir mediante eventos.** Las cláusulas aceptadas no se reescriben. La mutabilidad se define por campo. Existe un procedimiento excepcional para retirar contenido que no deba conservarse.

<a id="P14"></a>**P14. Validar mecánicamente lo verificable.** Determinismo significa reproducibilidad con las mismas entradas, no verdad semántica. Las comprobaciones de contenido se evalúan aparte.

<a id="P15"></a>**P15. Separar datos y control con barreras efectivas.** Las fuentes no conceden permisos ni ejecutan instrucciones. La integración y las acciones externas tienen controles independientes del texto propuesto.

<a id="P16"></a>**P16. Contexto suficiente al menor coste útil.** Reducir lecturas y tokens sin perder evidencia decisiva. La relevancia selecciona candidatos; autoridad, vigencia y permisos determinan cómo utilizarlos.

<a id="P17"></a>**P17. Continuidad reconstruible.** El relevo se deriva de estado persistido y evidencia de ejecución. Lo no registrado no puede deducirse mágicamente: se declara como faltante.

<a id="P18"></a>**P18. Evidencia observable y verificable.** Un hito necesita criterios de aceptación y resultados vinculados a la revisión probada. Un comando correcto es evidencia parcial cuando el resultado requiere juicio humano.

<a id="P19"></a>**P19. Autonomía proporcional y revisión por excepción.** Combinar autorización, alcance, reversibilidad, impacto, tolerancia e intervenibilidad. La reversibilidad por sí sola no autoriza una acción.

<a id="P19bis"></a>**P19 bis. Alternativas donde existe una elección real.** Las decisiones discrecionales relevantes conservan opciones, criterios y motivos. No se inventan alternativas para corregir un error demostrado o cumplir una restricción ya fijada; la ausencia justificada queda registrada.

<a id="P20"></a>**P20. Medir uso y corrección.** Minutos humanos totales por resultado correcto, con límites de calidad y seguridad. Los indicadores intermedios no sustituyen el resultado.

<a id="P21"></a>**P21. Añadir estructura por utilidad demostrable.** Cada campo nuevo declara su lector o requisito de auditoría; cada tipo o relación, su contrato de pregunta. El mantenimiento cuenta como coste.

<a id="P22"></a>**P22. Evolucionar en incrementos revisables.** Agrupar decisiones reduce interrupciones; no debe esconder su número, esfuerzo ni impacto. Corregir fallos en su pieza responsable antes de añadir reglas generales.

<a id="P23"></a>**P23. Complejidad proporcional.** Reutilizar herramientas y dependencias cuando su coste total sea menor que construirlas. Modularidad no implica microservicios ni vocabulario duplicado.

<a id="P24"></a>**P24. Cobertura documental explícita y fidelidad evaluada.** Toda promesa de conocimiento se limita a fuentes, modalidades y calidad comprobadas. La ingesta es esencial para los casos que la necesitan, sin exigir soporte universal antes de aportar valor.

<a id="P25"></a>**P25. Separar método, dominio e instalación.** El sistema define contratos generales; el proyecto, significado y autoridad del dominio; la instalación, herramientas y operación. Se relacionan por versiones explícitas.

<a id="componentes-del-sistema"></a>
## 4. Componentes y responsabilidades

| Componente | Responsabilidad | Límite |
| --- | --- | --- |
| Fuentes e ingesta | Inventariar, capturar, procesar y registrar calidad y procedencia. | No ratifica decisiones ni declara completitud sin evaluación. |
| Registros | Representar decisiones, afirmaciones, preguntas, identidad y trabajo autorizado. | No convierte un campo escrito por el agente en una aprobación. |
| Fijos y vistas | Sintetizar o proyectar registros para personas y agentes. | No oculta condiciones ni actúa como una autoridad independiente. |
| Gobierno | Políticas, roles, delegaciones y comprobación de aprobaciones. | Cambiar permisos requiere autoridad previa al cambio. |
| Validación y consultas | Aplicar esquemas, transiciones, vigencia, impacto y recuperación. | No certifica la corrección del significado de cualquier texto. |
| Adaptadores | Implementar apertura, herramientas, recibos y continuidad por cliente. | No introduce reglas de negocio escondidas. |
| Medición y evaluación | Registrar uso, resultados, coste y fallos; contrastar cambios. | No evalúa calidad solo contando citas, tokens o tests. |
| Evolución | Decidir qué corregir, retirar o ampliar a partir de evidencia. | No transforma toda recurrencia en una nueva estructura. |

Pueden implementarse en un monolito modular. Validación, generación de vistas, ejecución de comandos e ingesta mantienen interfaces separadas aunque compartan biblioteca. Las consultas no ejecutan comandos de hitos para responder a una lectura.

<a id="ontología-mínima"></a>
<a id="de-la-taxonomía-al-grafo-de-conocimiento"></a>
## 5. Modelo de conocimiento

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

<a id="cambios-hechos-fuera-del-agente"></a>
<a id="cómo-se-sabe-que-algo-cambió"></a>
<a id="cómo-se-sabe-si-el-cambio-es-válido"></a>
<a id="lo-que-no-está-en-un-commit-no-existe"></a>
<a id="cuando-el-cambio-afecta-a-otros-archivos-sin-relacionarlos"></a>
<a id="procedimiento-de-edición-directa"></a>
## 6. Mutabilidad, vigencia e historia

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

<a id="por-qué-git"></a>
## 7. Autoridad, aprobación y escritura

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

<a id="la-señal-qué-se-sirve-al-modelo"></a>
<a id="el-motor-de-recuperación"></a>
<a id="cómo-recupera-de-más-barato-a-más-caro"></a>
<a id="qué-viaja-con-cada-resultado"></a>
<a id="qué-no-hace"></a>
<a id="dónde-vive"></a>
<a id="por-qué-es-así"></a>
<a id="el-sistema-no-es-rag-ni-graphrag"></a>
<a id="el-problema-de-los-harness-actuales-con-contexto-y-memoria"></a>
## 8. Recuperación y contexto

### Contrato de consulta

Las consultas deterministas operan sobre revisión, reloj y política explícitos. Devuelven IDs, contenido al nivel solicitado, autoridad, vigencia, evidencia, calidad, procedencia y advertencias. Su salida incluye cobertura examinada, truncamientos y opciones para ampliar; un límite de presupuesto no se presenta como resultado exhaustivo.

| Consulta | Resultado |
| --- | --- |
| Relevo | Objetivo, autorización, alcance, trabajo integrado y pendiente, resultados de verificación, siguiente paso y preguntas relevantes. |
| Por ID | L0: identidad y descripción; L1: contenido operativo y condiciones; L2: registro completo. |
| Consolidado | Texto de cláusulas aplicables con su procedencia y modificaciones propuestas separadas. |
| As-of | Estado reconstruido bajo los dos cortes temporales. |
| Entidad | Hechos, decisiones y preguntas relacionados, sin convertir falta de resultados en ausencia de conocimiento. |
| Listos | Hitos con autorización, dependencias satisfechas y, si procede, reclamación válida. |
| Agenda | Revisiones y decisiones por plazo, consecuencias y responsable. |
| Impacto | Dependencias afectadas, causa y estado de resolución. |
| Integridad y síntesis | Evidencia de última comprobación, incidencias y dependencias desfasadas. |
| Exploración | Candidatos por texto, alias, estructura, relaciones o similitud, sujetos al mismo filtro de permisos y vigencia. |

El siguiente paso del relevo es una recomendación derivada de datos registrados. El primer test fallido no siempre indica qué hacer: puede ser un fallo del entorno, una comprobación omitida o una restricción de autorización. Los resultados de verificación llevan revisión, entorno y antigüedad; consultar el relevo no los vuelve a ejecutar automáticamente.

### Relevancia y autoridad

La búsqueda léxica o semántica encuentra candidatos; no determina qué es verdadero ni qué rige. Recuperación por ID, relaciones y estados es preferente para preguntas normativas. Preguntas abiertas pueden necesitar texto completo, búsqueda híbrida o exploración. Se elige con evaluaciones de la instalación, no por excluir categorías enteras de herramientas.

Orden práctico: relevo e identidad cuando se conocen; filtros de ámbito y entidad; exploración acotada; expansión y lectura de evidencia. Los permisos se aplican antes de exponer candidatos y durante su expansión. Un fragmento siempre viaja con la identidad y condiciones de su registro.

Se distinguen: sin coincidencias, fuente no inventariada, fuente no procesada, extracción parcial, restricción de acceso y evidencia insuficiente. Los mensajes no revelan la existencia de material restringido a quien no puede conocerla. El mapa de ignorancia contiene preguntas conocidas; no acredita que se hayan descubierto todas las incógnitas.

### Cuellos de botella y presupuesto

La prioridad combina trabajo realmente bloqueado, plazo útil para intervenir, consecuencias, fragilidad de premisas y señales observadas. El número de aristas no equivale por sí solo a valor de negocio. La instalación publica su criterio y permite explicar por qué una cuestión aparece antes que otra.

El contexto tiene un presupuesto ajustable. Si no cabe la evidencia decisiva, se amplía la lectura, se ofrece una respuesta limitada o se solicita la información necesaria. Una condición de seguridad o autorización no se elimina para cumplir un número de líneas.

<a id="ingesta-y-comprensión-documental"></a>
<a id="documentación-no-equivale-a-conocimiento-disponible"></a>
<a id="responsabilidad"></a>
<a id="flujo"></a>
<a id="procesado-por-tipo-de-contenido"></a>
<a id="tres-representaciones"></a>
<a id="localizadores-y-atomización-selectiva"></a>
<a id="calidad-documental-medible"></a>
<a id="registro-documental"></a>
<a id="integridad-de-los-originales"></a>
<a id="principios-de-la-ingesta"></a>
<a id="fuera-de-alcance"></a>
<a id="criterios-de-éxito"></a>
<a id="resultado-esperado"></a>
<a id="capacidades-complementarias"></a>
## 9. Ingesta y comprensión documental

### Alcance y flujo

Inventariar → capturar versión → extraer estructura → evaluar calidad → proponer interpretación → integrar bajo las reglas del registro → recuperar evidencia. La entrada distingue fuentes conocidas, accesibles, procesadas y evaluadas. «Disponible» no significa que todo su significado esté representado.

Cada fuente recibe el tratamiento más barato que preserve lo necesario para sus tareas. Se escala a otro procesador o modalidad cuando la calidad o una pregunta real lo exige. No es obligatorio ejecutar OCR, visión y extracción semántica sobre cada documento.

| Contenido | Tratamiento y límites que declarar |
| --- | --- |
| Texto y correo | Extracción nativa, autoría, fecha e hilo; distinguir cita de instrucción. |
| PDF nativo o escaneado | Orden de lectura, páginas, tablas, figuras y OCR donde proceda. |
| Hoja de cálculo | Celdas, fórmulas, valores disponibles, unidades y dependencias; distinguir valor almacenado de recálculo. |
| XML y datos | Parser de esquema; conservar tipos y estructura. No aplanar series o tablas masivas a prosa. |
| Imagen, diagrama o gráfico | Región, contexto, leyendas y límites de interpretación visual. |
| Audio y vídeo | Intervalos, participantes cuando se conozcan, incertidumbre de transcripción y relación entre imagen y voz. |
| Código | Revisión, archivo y símbolo; el grafo de código no sustituye al de decisiones. |
| Web | Captura fechada y con huella; la URL es origen, no una versión inmutable. |

### Identidad, representaciones y citas

Original, representación estructurada e interpretación semántica tienen identidades y ciclos separados. La identidad de fuente es un ID estable, no la ruta ni el hash. Contenido binario igual, parecido visual y referencia al mismo concepto son equivalencias diferentes; no se fusionan automáticamente.

La ficha del original conserva ID, procedencia, fecha de ingreso, ubicación, formato, política de acceso y huella. La derivación añade `derivada_de`, procesador, versión, configuración identificable, fecha, huella propia, cobertura y calidad. Una configuración sensible se referencia de forma segura, sin guardar secretos.

La cita canónica señala el original y su localizador. La evidencia de lectura conserva además la identidad y huella de la representación utilizada. Si el localizador depende del procesador, se vincula a esa representación; una derivación nueva no cambia silenciosamente la resolución de citas previas. Un mapa entre localizadores de versiones debe comprobarse; si no puede, la cita requiere revisión.

Una derivación no ratifica una decisión. Puede ser el artefacto leído, y debe poder reconstruirse ese hecho. Los registros se fundamentan en la fuente original, declarando las transformaciones usadas. Un hecho calculado cita entradas, código/configuración y ejecución; el resultado calculado es información nueva, no una mera copia.

Un fragmento no necesita archivo propio solo por ser citable. Recibe identidad independiente cuando se reutiliza o necesita mantenimiento propio, conservando contexto, jerarquía y vínculo a su origen.

### Calidad y correcciones

Se evalúan cobertura, fidelidad textual, estructura, tablas/unidades, elementos visuales, trazabilidad y calidad semántica. Un porcentaje global no compensa la pérdida de una negación, una unidad o una figura decisiva.

El estado de procesamiento —pendiente, procesado, parcial o fallido— se separa de la calidad y de la revisión. El procesador puede reportar métricas; no se certifica a sí mismo como correcto por haber terminado. La evaluación registra método, muestra, dimensiones, resultado y elementos no comprobados.

Una persona que detecta un error añade una evaluación negativa o incidencia vinculada a la derivación. Esta se excluye de usos afectados, se consulta el original o se reprocesa. No se altera la salida histórica para hacerla coincidir ni se añade únicamente una marca positiva de «revisado».

### Integridad y actualización

Originales y derivaciones llevan huellas criptográficas propias. Mover un recurso conserva su ID si se verifica la huella. Reprocesar crea una derivación nueva. Una nueva versión documental es otra fuente, vinculada por sucesión; las derivaciones anteriores siguen representando su original y no se reescriben.

La comprobación periódica detecta alteraciones, desapariciones y fallos de acceso. Un timeout o credencial vencida produce integridad no comprobada, no prueba de manipulación. La salida incluye cuándo se verificó por última vez; la política fija cuándo una evidencia demasiado antigua impide un uso sensible. Para operaciones que lo exigen, se verifica al leer o se emplea una copia inmutable verificada.

El cambio de fuente activa impacto sobre quienes la citan. La propagación no invalida todo el corpus por defecto ni interpreta cualquier revisión editorial como cambio de todas sus conclusiones.

<a id="desacoplamiento-humano-ia"></a>
<a id="por-qué-la-persona-no-puede-revisarlo-todo"></a>
<a id="reglas"></a>
<a id="lo-que-no-se-hace"></a>
## 10. Interacción humana y autonomía

La interfaz de revisión muestra qué cambia, por qué, evidencia, impacto, incertidumbre y efecto de esperar. Permite aceptar, rechazar, pedir cambios y diferir. Las acciones se vinculan al contenido revisado. Un panel es una vista; sus eventos de entrada se registran mediante la puerta de autoridad.

La captura debe encajar en los canales que las personas usan. Poco uso de un panel es una señal para investigar el flujo, no prueba de falta de disciplina. Las propuestas desde conversaciones se agrupan y muestran como tales; una frase ambigua no se transforma en una ratificación.

El sensor de decisiones no registradas puede proponer al cierre decisiones, compromisos y supuestos detectados. Su eficacia se mide por propuestas útiles, omisiones en una muestra revisada y coste de revisión, no solo por tasa de aceptación. No ve conversaciones a las que no tiene acceso.

Una acción autónoma necesita una delegación vigente y límites de tipo de operación, objetivo, recursos, coste, plazo y efectos externos. La escalada considera impacto y posibilidad de corrección, además de reversibilidad. Se interviene con margen real; no se espera siempre al último instante teórico.

Se agrupan excepciones de causa común y se eliminan duplicados. Las alertas críticas no se suprimen por cuota: al agotarse la capacidad, el trabajo afectado se pausa y se hace visible el desbordamiento. La cola tiene responsable, antigüedad y política de escalado; el silencio no equivale a aprobación.

Las alternativas se requieren en decisiones con opciones reales. Correcciones demostradas, ejecución delegada y cumplimiento de una restricción pueden justificarse sin fabricarlas. Conservar alternativas descartadas sirve para reabrir una elección si cambian sus condiciones.

La muestra de calibración revisa acciones autónomas y decisiones de no escalar, combinando selección aleatoria y casos de mayor impacto. Más aprobaciones y menos comentarios son señales a investigar, no prueba automática de habituación. La revisión pide comprobar algo concreto, no leer una explicación extensa del agente como sustituto de evidencia.

## 11. Seguridad, privacidad y límites de ejecución

El modelo de amenazas incluye errores, instrucciones maliciosas en documentos, suplantación de aprobación, modificación de controles, fuga entre ámbitos y ejecución de comandos inseguros. Las defensas se prueban sobre los caminos habilitados.

- Fuentes, conversiones y respuestas de herramientas son datos sin capacidad de cambiar políticas.
- Los agentes y procesadores reciben permisos mínimos; las credenciales de aprobación e integración no quedan disponibles al proponente sin restricciones.
- Los comandos de verificación se tratan como código: revisión, entorno aislado, límites de recursos y red, sin secretos innecesarios. Las consultas leen resultados, no ejecutan comandos incrustados en fuentes.
- Se controlan rutas, archivos enlazados, acceso de red y formatos potencialmente activos durante la ingesta.
- Las derivaciones, hechos, índices, cachés, logs y exportaciones heredan las restricciones de sus fuentes. La agregación no elimina confidencialidad.
- Un servicio externo solo procesa clases de datos autorizadas bajo una política explícita de tratamiento y retención.

El perfil inicial puede asumir que todos los miembros autorizados leen todo el repositorio. En ese caso no ingresa material que requiera permisos parciales. Separar repositorios es una opción; una futura capa de permisos requiere pruebas que incluyan búsquedas, relaciones, índices y errores.

La política de conservación contempla retirada excepcional de secretos, datos expuestos por error o contenido que no deba retenerse. Incluye originales, derivaciones, historial, clones, índices y copias de respaldo, con límites de eliminación verificable. Se conserva el mínimo registro permitido del incidente sin volver a copiar el contenido retirado. P13 no impide esta respuesta.

<a id="varios-responsables-sobre-una-misma-base"></a>
## 12. Concurrencia, fallos y operación

Los IDs canónicos son estables y no requieren secuencias sin huecos. Una etiqueta numérica de presentación es opcional. No se renumeran identidades publicadas para resolver colisiones; las instalaciones heredadas mantienen alias y migraciones explícitas.

Cada sesión usa una base identificada y un espacio aislado. Antes de integrar se revalida contra el estado canónico actual: permisos, aprobaciones, referencias, vigencia y conflictos semánticos. Un merge textual limpio no demuestra compatibilidad normativa.

Las reclamaciones se activan solo cuando varios ejecutores necesitan coordinación. Se adquieren atómicamente mediante la puerta de integración o un coordinador cuyo estado y autoridad se declaran. Incluyen dueño, vencimiento, renovación y un número de generación que invalida ejecutores antiguos. Un aviso informativo no basta para prometer exclusión mutua. Las acciones externas también comprueban la vigencia de la reclamación cuando dependen de ella.

| Fallo | Comportamiento |
| --- | --- |
| No puede comprobarse autorización o integridad requerida | Bloquear la escritura o acción afectada y explicar la condición. |
| Consulta o índice no disponible | Lectura de snapshot validado si la política y permisos lo permiten, declarando antigüedad y límites. |
| Telemetría no disponible | Registrar el hueco; permitir trabajo no crítico si la política lo admite. No inventar medidas. |
| Original inaccesible | Diferenciar inexistencia, permiso y fallo transitorio; utilizar solo evidencia cuya política permita el estado observado. |
| Resultado de escritura desconocido | Reconciliar antes de reintentar; evitar duplicados y declarar efectos parciales. |
| Sincronización de una copia atrasada | Mostrar revisión y corte; no ratificar cambios contra una copia cuya base no pueda verificarse. |

La instalación fija volumen, concurrencia, presupuesto, tiempos de respuesta, disponibilidad y tolerancia a pérdida de datos. Las afirmaciones de rendimiento se miden. Los respaldos incluyen originales externos, políticas y evidencia de aprobación, no solo Git; se prueba restaurar un conjunto consistente. Las vistas pueden borrarse y reconstruirse desde ese conjunto.

<a id="por-qué-llm-wiki-y-okf"></a>
<a id="cómo-se-aplica-okf"></a>
<a id="por-qué-no-sql-como-almacén-de-la-verdad"></a>
<a id="por-qué-no-nosql-como-almacén-de-la-verdad"></a>
<a id="por-qué-no-neo4j-como-almacén-de-la-verdad"></a>
## 13. Formato, Git e interoperabilidad

Markdown con cabecera YAML y Git son las elecciones del registro normativo de este diseño. Su justificación es la escala de equipos y corpus revisables, la disponibilidad de herramientas y el valor de los diffs. No se afirma que otros almacenes sean incapaces de auditar o que cualquier base de datos sea un segundo dueño.

Una base relacional, índice léxico, grafo en memoria o índice vectorial puede ser una vista reconstruible. Se incorpora por necesidad medida, incluidos coste de consulta, concurrencia y operación. Si las premisas del almacén canónico dejan de cumplirse, se abre una decisión arquitectónica; no se oculta el coste para proteger una preferencia.

El formato operativo se define por completo en este documento: Markdown, YAML y el perfil de campos, estados y eventos descrito aquí. Usa convenciones de intercambio inspiradas en OKF 0.2. No hace falta consultar ese estándar para implementar el perfil propio. Declarar compatibilidad externa completa es una capacidad opcional que exige contrastar el adaptador con la versión externa correspondiente. Un lector genérico no tiene por qué ejecutar la semántica normativa del sistema.

- Un concepto por archivo, con `type`, `title`, `description` y un `id` estable propio. El identificador por ruta del formato externo se mantiene separado; mover archivos puede romper enlaces de lectores externos y requiere alias o actualización comprobada.
- `generated: {by, at}` identifica el productor; no otorga confianza ni privilegios. `process:` no significa que el contenido sea determinista o verdadero.
- `verified` conserva eventos positivos compatibles con el formato; se vinculan al digest del contenido verificado. Resultados negativos, parciales y caducados viven en evaluaciones explícitas del perfil propio, sin forzar significado dentro de `verified`.
- `sources` utiliza `resource` e identificador de cita, con extensiones para localizador, representación y huella cuando sean necesarias.
- `stale_after` es un instante con zona; se calcula con una política declarada. Tiempo transcurrido y derogación son causas diferentes de revisión.
- `status` es una proyección de interoperabilidad generada, no autoridad propia. La tabla total de proyección figura en el contrato de estados de este documento. Los lectores operativos usan el estado detallado y las advertencias.
- `index.md` se genera bajo el formato fijado. La raíz del paquete contiene los conceptos; las instrucciones ajenas a ese formato quedan fuera. Si no se usa el formato reservado de `log.md`, la bitácora lleva otro nombre.

Las marcas de cláusula y afirmación siguen la gramática del contrato concreto y los escenarios incluidos en este documento. El parser debe distinguir texto, código, etiquetas escapadas y citas; no se da por trivial. Los visores utilizados se prueban para evitar ocultar condiciones o anclas.

Las modificaciones automáticas de proyecciones ocurren antes de cerrar la revisión final del árbol integrado, o mediante una operación controlada y reproducible. La CI valida el resultado; no modifica silenciosamente el contenido que la persona aprobó.

<a id="cómo-se-mide"></a>
<a id="contraste-con-los-marcos-de-gestión-del-conocimiento-organizativo"></a>
## 14. Medición y evaluación

### Métrica principal

**Minutos humanos por resultado correcto = todo el tiempo humano atribuible / número de resultados que cumplen la rúbrica acordada.** El numerador incluye intentos fallidos, revisión, captura, aprendizaje y mantenimiento; los costes compartidos se asignan por un criterio publicado. Si no hay resultados correctos, se informa el tiempo y el fallo, no una razón favorable.

Los resultados se agrupan por tipo y complejidad para evitar aparentes mejoras por tareas más fáciles. El coste de instalación se muestra separado del coste recurrente, pero no desaparece. Los errores tardíos se atribuyen al resultado original con una ventana de seguimiento declarada.

La línea HUMANO puede ser un registro ligero de minutos, interrupciones legítimas/evitables, resultado provisional y correcciones. El agente no inventa minutos ni corrección. Tiempo entre mensajes no equivale a atención activa; se usa solo como aproximación identificada y se contrasta con muestras.

### Indicadores y límites

| Indicador | Uso y cautela |
| --- | --- |
| Interrupciones y cola | Contar las evitables, pero vigilar omisiones de escalado, antigüedad y desbordamiento. |
| Retrabajo y errores | Severidad, causa, detección y tiempo de reparación; no solo cantidad. |
| Tokens, latencia y coste | Cadena completa: ingesta, extracción, reintentos, navegación, generación y revisión automática. |
| Recuperación | Cobertura de evidencia decisiva, obsoletos servidos como actuales y búsquedas fallidas. |
| Señal útil y respaldo | Las citas son un proxy; una muestra evalúa si respaldan la afirmación y si faltan condiciones. |
| Adopción y legibilidad | Tareas completadas, comprensión, abandono y esfuerzo por rol/canal. |
| Mantenimiento | Tiempo dedicado al sistema frente al negocio; agrupar decisiones no debe ocultarlo. |
| Calidad documental | Fidelidad por formato y elemento; distinguir evaluado, no evaluado y fallido. |

### Tres niveles de prueba

1. **Invariantes deterministas:** esquemas, estados, autoridad, temporalidad, cláusulas, impacto, idempotencia y restauración. Pruebas positivas, negativas y de propiedades.
2. **Evaluación de IA:** fuentes y respuestas revisadas, contexto completo, contexto servido y ablación de evidencia decisiva; comprobar conclusión, condiciones, citas y abstención. La respuesta del modelo con todo el contexto no es automáticamente la referencia correcta.
3. **Validación en uso:** tareas reales, coste humano total, adopción y errores tardíos. Complementa las pruebas previas; no las sustituye.

El conjunto mínimo de regresión se ejecuta antes de cambiar recuperación o gobierno, aunque el ahorro parezca bueno. La evaluación extensa puede activarse por escala o incertidumbre. Se conservan versiones de modelo, prompts, herramientas, corpus y resultados; se reserva un conjunto independiente para evitar ajustar y evaluar sobre los mismos ejemplos.

Los umbrales de mejora se fijan tras la línea base y antes de evaluar el incremento. Los invariantes de autorización y aislamiento no esperan a ella. No se atribuye causalidad por una única serie corta: se comparan tareas equivalentes, cambios aislados cuando sea posible y causas de regresión. Un mecanismo se simplifica o retira si su coste neto no compensa, conservando las protecciones necesarias.

<a id="sistema-y-proyecto-las-dos-capas"></a>
<a id="herramientas-de-memoria-y-contexto-comparables"></a>
<a id="qué-herramientas-se-alinean-con-los-principios-fundacionales"></a>
## 15. Evolución orientada a resultados

El sistema evoluciona mediante un ciclo: problema observado → resultado RES elegido → escenario y contrato → implementación → prueba → integración → uso → medida. Cada incremento debe producir un recorrido completo y una evidencia que permita mantenerlo, corregirlo o retirarlo.

Las capacidades opcionales —fase de sueño, lint semántico, captura de procedimientos, otros índices o múltiples escritores— proponen mejoras y se activan por una necesidad observada. No ratifican conocimiento ni promocionan una afirmación por frecuencia. Un error conocido se corrige sin esperar al calendario de una capacidad opcional.

Las hipótesis de rendimiento o ahorro se registran como tales hasta medirlas. Las comparaciones con otras herramientas no sustituyen los escenarios propios. La arquitectura se juzga por resultados, corrección y coste de mantenimiento, no por el número de componentes o documentos.

La siguiente decisión de desarrollo debe identificar el resultado buscado, el caso que falla, el cambio mínimo y la prueba que lo demostraría. Si no se puede formular esa relación, la propuesta requiere aclaración antes de convertirse en trabajo.

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


## Contrato de estados e interoperabilidad

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

### Proyección total de `status`

Para cada snapshot y tiempo de exportación se genera `status`; nadie lo edita manualmente. Se aplican estas reglas por orden, para cubrir todos los estados anteriores:

1. Clase **archivo**, estado rechazado/rechazada, descartada, retirada, cancelado, hipótesis refutada, o sucesión efectiva completa: `deprecated`.
2. Decisión/hecho/persona/rol/entidad en propuesta; plan/hito propuesto; síntesis borrador; hipótesis abierta; supuesto activo: `draft`.
3. Decisión/hecho aceptado con inicio de validez todavía futuro: `draft` hasta su entrada en vigor; la aceptación y el calendario se mantienen visibles.
4. Los restantes casos de la tabla: `stable`, con los estados detallados y advertencias del perfil propio.

`stable` expresa estabilidad del registro para intercambio, no verdad, permiso de ejecución ni calidad de extracción. Una pregunta abierta puede ser estable como registro; una fuente registrada puede tener extracción parcial. Una decisión parcialmente vigente conserva `stable` y expone qué cláusulas aplican. Disputa, integridad, caducidad y calidad viajan como campos/advertencias adicionales: un lector que no los entiende no es un cliente operativo certificado.

Las vistas no son registros autoritativos. Si una vista se exporta como concepto, su proyección se calcula del contenido representado y su contrato; no recibe `stable` como vía para eludir estas reglas. Una verificación de fuente que falla no se oculta cambiando solo `status`.

El paso del tiempo puede cambiar una proyección sin commits de usuario. Las exportaciones se generan para un corte explícito y llevan su fecha; la consulta en vivo calcula vigencia en tiempo de lectura. Un archivo exportado viejo nunca se anuncia como estado en tiempo real.


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

Núcleo 0.7, 3 nov 2026. Define el sistema objetivo y su aceptación. Sustituye la revisión 0.6 como referencia de diseño; no acredita capacidades desplegadas. Los antecedentes y la bibliografía no son dependencias de comprensión ni de ejecución de este contrato.


