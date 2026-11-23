# Spanish to English glossary (KB-DPP 1.0, KBOL 0.13)

Until 0.12, the KB-DPP contract, the record format, the CLI and the code of KBOL were written in Spanish. From KB-DPP 1.0 and KBOL 0.13 everything is in English. This table is the single source of truth for the renaming, and the base of `kbol migrate` for records written in the old format. A term not listed here is translated literally, in `snake_case` for fields and values and `UPPER_SNAKE_CASE` for codes.

## Record types and ID prefixes

| 0.12 type | 1.0 type | 0.12 prefix | 1.0 prefix |
|---|---|---|---|
| fuente | source | F | SRC |
| hecho | fact | HE | FACT |
| decision | decision | DEC | DEC |
| persona | person | PER | PER |
| rol | role | ROL | ROLE |
| pregunta | question | Q | Q |
| hipotesis | hypothesis | HIP | HYP |
| supuesto | assumption | SUP | ASM |
| entidad | entity | ENT | ENT |
| plan | plan | PL | PLAN |
| hito | milestone | HI | MS |
| sintesis | synthesis | SIN | SYN |

Record classes (`clase` → `class`): registro → record, fuente → source, fijo → fixed, vista → view, archivo → archive.

## States

| 0.12 | 1.0 |
|---|---|
| propuesta, propuesto | proposed |
| aceptada | accepted |
| rechazada | rejected |
| abierta | open |
| resuelta | resolved |
| descartada | discarded |
| validada | validated |
| refutada | refuted |
| retirada, retirado | retired |
| activo, activa | active |
| autorizado | authorized |
| en_curso | in_progress |
| completado | completed |
| cerrado | closed |
| cancelado | cancelled |
| registrada | registered |
| borrador | draft |
| vigente (synthesis state) | current |

## Common fields

| 0.12 | 1.0 |
|---|---|
| tipo / type | type (unchanged key `type`) |
| estado | state |
| eventos | events |
| ambito | scope |
| ambitos | scopes |
| autor | author |
| clase | class |
| cuerpo | body |
| afirmacion | claim |
| fecha | date |
| intervalo (desde, hasta) | interval (from, until) |
| precision: instante, minuto, hora, dia, mes, anio | precision: instant, minute, hour, day, month, year |
| alternativas (id, descripcion, seleccionada, motivo) | alternatives (id, description, selected, reason) |
| criterios | criteria |
| justificacion | rationale |
| naturaleza: humana | nature: human |
| identidad_ref | identity_ref |
| capacidades: ratificar, gobernar_politica | capabilities: ratify, govern_policy |
| regla_aprobacion: uno, todos, {quorum: N} | approval_rule: one, all, {quorum: N} |
| ocupa (rol, desde, hasta) | holds (role, from, until) |
| responsable | owner |
| evidencia | evidence |
| implementacion: completa, parcial, pendiente, no aplica | implementation: complete, partial, pending, not_applicable |
| hitos | milestones |
| dependencias | dependencies |
| condicion | condition |
| aceptacion, verificaciones, tolerancias | acceptance, checks, tolerances |
| alcance (milestone) | work_scope |
| objetivo, restricciones | goal, constraints |
| locator profiles lines-v1, pdf-v1, norma-v1 | lines-v1, pdf-v1, norm-v1 |
| structure format estructura-v1 | structure-v1 |
| criterio_id, metodo, obligatorio | criterion_id, method, required |
| metodo: comando, revision_humana, evaluacion_ia_asistida | method: command, human_review, ai_assisted_evaluation |
| rubrica, resolucion_desacuerdo | rubric, disagreement_resolution |
| subtipo: original, derivada | subtype: original, derived |
| ubicacion, acceso, formato, calidad, procesamiento | location, access, format, quality, processing |
| procesamiento: pendiente, procesado, parcial, fallido | processing: pending, processed, partial, failed |
| clasificacion, dimensiones, resultado | classification, dimensions, result |
| resultado: conforme, no_conforme, parcial, no_evaluado | result: conforming, non_conforming, partial, not_evaluated |
| clase_evidencia: observado, calculado, declarado, modelado, predicho, supuesto | evidence_class: observed, computed, declared, modeled, predicted, assumed |
| ancla (in `sources`) | anchor |
| representacion_id, contexto | representation_id, context |
| define (clausula, termino, clase, descripcion, alias) | defines (clause, term, class, description, aliases) |
| clase_entidad | entity_class |
| veta (patron) | vetoes (pattern) |

## Relations

| 0.12 | 1.0 |
|---|---|
| resuelta_por | resolved_by |
| cuestiona | challenges |
| deja_obsoleta | supersedes |
| pone_a_prueba | tests |
| somete_a_prueba | tests_hypothesis |
| basada_en | based_on |
| derivada_de | derived_from |
| afecta_a | affects |
| autorizado_por | authorized_by |
| cierra | closes |
| avanza | advances |
| produce | produces |
| se_apoya_en | relies_on |
| modifica (destino, operacion: sustituye, deroga, adicion; por, posicion) | amends (target, operation: replaces, repeals, adds; by, position) |
| depende_de (destino, condicion) | depends_on (target, condition) |
| conditions: aceptada_y_vigente, resuelta, completado_con_evidencia, disponible_con_integridad | accepted_and_in_force, resolved, completed_with_evidence, available_with_integrity |

## Events

| 0.12 | 1.0 |
|---|---|
| tipo_evento | event_type |
| creacion | creation |
| transicion | transition |
| ratificacion | ratification |
| revocacion_aprobacion | approval_revocation |
| evaluacion | evaluation |
| cambio_ocupacion | holding_change |
| resolucion_impacto | impact_resolution |
| importacion | import |
| estado_anterior, estado_nuevo | previous_state, new_state |
| valido_desde, valido_hasta | valid_from, valid_until |
| registrado_en | recorded_at |
| evidencia_evento (mecanismo, comprobante) | event_evidence (mechanism, proof) |
| aprobacion, aprobaciones | approval, approvals |
| actor | actor |
| autoridad_heredada | inherited_authority |
| procedencia | provenance |

## Body markup

| 0.12 | 1.0 |
|---|---|
| `<clausula id="C1">` | `<clause id="C1">` |
| `<hecho ref="…">` | `<fact ref="…">` |

## Error and warning codes

| 0.12 | 1.0 |
|---|---|
| ESQUEMA_INVALIDO | INVALID_SCHEMA |
| REFERENCIA_AUSENTE | MISSING_REFERENCE |
| AUTORIDAD_INSUFICIENTE | INSUFFICIENT_AUTHORITY |
| APROBACION_CADUCADA | STALE_APPROVAL |
| BASE_CAMBIADA | BASE_CHANGED |
| CONFLICTO_NORMATIVO | NORMATIVE_CONFLICT |
| TIEMPO_AMBIGUO | AMBIGUOUS_TIME |
| INTEGRIDAD_ROTA | INTEGRITY_BROKEN |
| INTEGRIDAD_NO_COMPROBADA | INTEGRITY_UNCHECKED |
| EVIDENCIA_INSUFICIENTE | INSUFFICIENT_EVIDENCE |
| ACCESO_DENEGADO | ACCESS_DENIED |
| RESULTADO_DESCONOCIDO | UNKNOWN_RESULT |
| SUSTITUCION_NO_DECLARADA | UNDECLARED_SUPERSESSION |
| RAIZ_YA_ESTABLECIDA | ROOT_ALREADY_ESTABLISHED |

## Output envelope

| 0.12 | 1.0 |
|---|---|
| operacion, operacion_id | operation, operation_id |
| revision | revision |
| valido_en, conocido_hasta | valid_at, known_until |
| resultado, advertencias, cobertura | result, warnings, coverage |
| result state: completado, parcial, bloqueado, fallido | completed, partial, blocked, failed |
| codigo, motivo, hallazgos, mensaje, severidad | code, reason, findings, message, severity |
| no_evaluado, truncado, alcance | not_evaluated, truncated, scope |

Exit codes do not change: 0 completed, 1 failed, 2 blocked, 3 partial.

## CLI commands

| 0.12 | 1.0 |
|---|---|
| validar | validate |
| migrar | migrate |
| digest | digest |
| consolidar | consolidate |
| listos | ready |
| impacto | impact |
| relevo | handoff |
| preparar_contexto | context |
| verificar | verify |
| consultar | query |
| buscar | search |
| integrar | integrate |
| arranque | bootstrap |
| desvios | drift |
| citas | citations |
| enlaces | links |
| integridad | integrity |
| soporte | support |
| preparar_aprobacion | approval_package |
| vocabulario | vocabulary |
| sesion | session |
| proponer | propose |
| exportar_skills | export_skills |
| ingerir | ingest |

## CLI options

| 0.12 | 1.0 |
|---|---|
| --carpeta | --folder |
| --valido-en, --conocido-hasta | --valid-at, --known-until |
| --antes-valido-en, --antes-conocido-hasta | --before-valid-at, --before-known-until |
| --instalacion | --installation |
| --revision, --base, --propuesta | --revision, --base, --proposal |
| --modo: propuesta, canonico, intercambio | --mode: proposal, canonical, exchange |
| --efectos, --importaciones, --aprobaciones | --effects, --imports, --approvals |
| --aprobacion: toda, decisiva | --approval: all, decisive |
| --hasta: ensayo, integrar, subir | --until: dry_run, integrate, push |
| --archivos, --rutas | --files, --paths |
| --operacion-id | --operation-id |
| --rama-canonica | --canonical-branch |
| --recibos, --remoto, --almacen | --receipts, --remote, --store |
| --persona, --roles, --declaracion | --person, --roles, --declaration |
| --tarea, --guardar, --objetivo, --ambito, --presupuesto | --task, --save, --goal, --scope, --budget |
| --heredados, --heredados-carpeta | --legacy, --legacy-folder |
| --verificacion | --check |
| --evento: inicio, parar, commit; --origen | --event: start, stop, commit; --origin |
| --texto | --text |
| --preparado | --staged |
| --consulta, --incluir (propuestas, no_vigentes), --limite | --query, --include (proposals, not_in_force), --limit |
| --llano, --con-ids | --plain, --with-ids |
| --skills, --actor, --ids, --version | unchanged |

## Installation file

The installation file keeps its role and is named `kbol.json` by default (`--installation` points to another path).

| 0.12 | 1.0 |
|---|---|
| carpeta_registros | records_folder |
| ambito | scope |
| presupuesto | budget |
| rama_canonica | canonical_branch |
| verificaciones (id, orden, timeout, codigo_esperado) | checks (id, command, timeout, expected_code) |
| integracion (remoto, repositorio, aprobacion, despues_de_integrar, vistas, autor) | integration (remote, repository, approval, after_integrate, views, author) |
| enlaces (excluir, deuda) | links (exclude, debt) |
| formato_heredado (registros, equivalencias, separadores) | legacy_format (records, equivalences, separators) |

## Local state and environment

| 0.12 | 1.0 |
|---|---|
| KBOL_ESTADO | KBOL_STATE |
| KBOL_REPOSITORIO | KBOL_REPOSITORY |
| KB_GITHUB_TOKEN | unchanged |
| `.kbol/relevos/`, `.kbol/sesion/`, `.kbol/verificaciones/` | `.kbol/handoffs/`, `.kbol/session/`, `.kbol/checks/` |
| `$KBOL_STATE/<repo>/integrador.git`, `recibos/`, `almacen/` | `integrator.git`, `receipts/`, `store/` |
| `<records>/_huellas.json`, `_solicitudes/` | `_fingerprints.json`, `_requests/` |

## Modules of `kbol/`

modelo → model, tiempo → timeutil, verificacion → verification, core, schema, markdown, eventos → events, proyeccion → projection, referencias → references, digest, consolidar → consolidate, dependencias → dependencies, mutabilidad → mutability, snapshot, autoridad → authority, github, declarada → declared, arranque → bootstrap, integrar → integrate, paquete → package, proponer → propose, importacion → importing, huellas → fingerprints, exportar → export, impacto → impact, relevo → handoff, verificar → verify, contexto → context, sesion → session, consultar → query, buscar → search, sustituciones → supersessions, llano → plain, soporte → support, vocabulario → vocabulary, migracion → migration, localizador → locator, citas → citations, integridad → integrity, enlaces → links, cli.

## Legacy format

The default legacy format (numbered ADRs, QD, HD, plans and milestones) reads English labels (`type: Decision`, `Accepted`, `Superseded by …`). A project whose legacy records use other words (for example Spanish) declares them in `legacy_format.equivalences`.

## Skills

`kbol` keeps its name; `incorporar-documento` becomes `add-document`. Both are written in English.
