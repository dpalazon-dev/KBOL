# KBOL · Knowledge Base Operating Layer

[![CI](https://github.com/dpalazon-dev/KBOL/actions/workflows/comprobar.yml/badge.svg)](https://github.com/dpalazon-dev/KBOL/actions/workflows/comprobar.yml)
[![Release](https://img.shields.io/github/v/release/dpalazon-dev/KBOL)](https://github.com/dpalazon-dev/KBOL/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Decisiones de proyecto que se pueden comprobar: qué regla rige en cada fecha, quién la aprobó y de qué página o líneas sale cada cita.**

[Read in English](README.md)

KBOL es una herramienta de línea de órdenes que trabaja sobre registros en Markdown dentro de tu repositorio git: decisiones, preguntas, hechos, hipótesis, planes y fuentes. Cada registro lleva un historial de eventos. A partir de él, KBOL reconstruye qué rige en cualquier fecha, no deja integrar un cambio sin la aprobación que pide tu política y comprueba que cada cita apunta al sitio exacto de su documento original.

![Demostración de KBOL: qué rige, búsqueda por texto y la puerta bloqueando la edición a mano de una decisión aceptada](docs/demo.gif)

## Prueba rápida

Monta un proyecto de prueba con una decisión aprobada y pregunta a KBOL qué rige (hace falta git, bash y Python 3):

```bash
uv tool install git+https://github.com/dpalazon-dev/KBOL
git clone https://github.com/dpalazon-dev/KBOL && cd KBOL
bash examples/quickstart.sh /tmp/kbol-demo
```

[`examples/quickstart.sh`](examples/quickstart.sh) crea un rol y una persona, arranca la raíz de confianza, propone una decisión, la aprueba, la integra por la puerta y la consulta. Cada paso está explicado en [primeros pasos](docs/primeros-pasos.md).

## Para qué sirve

- **Saber qué está decidido de verdad.** «¿Sigue en vigor que la base de datos es PostgreSQL?» `kbol consultar` responde si rige hoy, desde cuándo, quién lo aprobó y con qué palabras, y qué decisión lo sustituyó si ya no rige. Una regla que nadie sustituyó no caduca por ser antigua, y dos que chocan sin resolverse salen como conflicto, no como «la más reciente».
- **Cambiar con control.** Los registros solo cambian por una puerta de integración (`kbol proponer`): comprueba su forma, que lo cerrado no se reescribe y que lo aprueba quien tiene autoridad, y deja un recibo de cada operación.
- **Citar sin inventar.** Un hecho cita su fuente por página y región de un PDF o por líneas de un texto, contra la huella SHA-256 del original. `kbol citas` dice si cada cita sigue resolviéndose.
- **Dar contexto fiable a un agente.** `kbol sesion` prepara para un agente de código las restricciones que rigen en la tarea, y la skill que trae el paquete (`kbol exportar_skills`) le enseña a consultar antes de suponer.

## En qué se diferencia

| | Carpeta de ADR o wiki | Memoria o RAG para agentes | KBOL |
|---|---|---|---|
| Qué rige en una fecha | Se lee a mano | El fragmento más parecido o más reciente | Se calcula desde el historial de eventos |
| Dos decisiones que chocan | Gana la que leas | Gana la más reciente | Conflicto declarado hasta que una persona lo resuelve |
| Quién lo aprobó | Una convención | No consta | Aprobación ligada al digest de lo aprobado, con recibo |
| Citas | Enlaces | Fragmentos sin versión | Página, región o líneas contra el original con huella |
| Quién puede cambiarlo | Cualquier commit | Escritura directa | Una puerta de integración |

KBOL no es un motor de búsqueda semántica, ni una base de grafos, ni un servidor: es una CLI sobre git y Markdown. `kbol buscar` encuentra registros por palabras cuando no se conoce su ID, pero lo que rige lo decide `consultar`. Las aprobaciones de hoy son declaradas: la cita literal de quien aprueba, sin autenticar (ver [elecciones](docs/elecciones.md#mecanismos-no-conformes)).

## Instalación

Pide Python 3.10 o posterior, git y [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/dpalazon-dev/KBOL
```

Para fijar una versión, añade su etiqueta al final de la URL (`…/KBOL@vX.Y.Z`). La orden queda como `kbol`; `kbol --version` dice la versión instalada. Para trabajar sobre el código, mira [CONTRIBUTING.md](CONTRIBUTING.md).

## Primeros pasos

[`docs/primeros-pasos.md`](docs/primeros-pasos.md) lleva un repositorio vacío hasta una decisión aprobada y consultable: la raíz de confianza (quién aprueba), la instalación, la primera propuesta, su aprobación y la consulta.

## Conceptos

- **Registro.** Un Markdown con cabecera YAML (`type`, `id`, `estado`, relaciones y `eventos`) en la carpeta de registros. Las decisiones dividen su texto en cláusulas (`<clausula id="C1">`), que otras decisiones pueden modificar o derogar una a una.
- **Instalación.** Un JSON del repositorio que dice dónde están los registros, el ámbito, la rama canónica y cómo se integra. La política (roles y personas) son registros como los demás.
- **Raíz de confianza.** El primer rol y la primera persona se activan una sola vez con `kbol arranque`; desde ahí, todo cambio entra por la integración.
- **Integración.** `kbol proponer` lleva los archivos del árbol de trabajo a la rama canónica a través de un clon propio, con la aprobación que pida la política, y deja un recibo.
- **Corte.** Toda consulta pide `--valido-en`, el instante en que se pregunta, y admite `--conocido-hasta` para responder con lo que se sabía entonces. KBOL no lee el reloj por su cuenta.

KBOL implementa el contrato KB-DPP ([núcleo 0.7](docs/referencias/KB-DPP-nucleo.md) e [implementación 0.8](docs/referencias/KB-DPP-implementacion.md)). Lo que el contrato deja abierto y cómo lo concreta KBOL está en [las elecciones](docs/elecciones.md); los cambios incompatibles, en [cambios](docs/cambios.md).

Que una función exista aquí no acredita una capacidad operativa en un proyecto: eso lo acredita su uso en una instalación, con integración y recibo.

## Uso

Referencia de todas las órdenes. Desde un clon van con `uv run` delante; con la herramienta instalada, basta `kbol`. `kbol --help` lista las opciones.

```bash
uv run kbol validar RUTA.md [--modo propuesta|canonico|intercambio]
uv run kbol migrar RUTA_DOCS --revision <sha> [--instalacion instalacion.json]
uv run kbol digest RUTA.md --efectos efectos.json
uv run kbol consolidar RAIZ --carpeta kb --revision <sha> --ids DEC-… --valido-en <instante> [--conocido-hasta <instante>] [--heredados] [--instalacion instalacion.json]
uv run kbol listos RAIZ --carpeta kb --revision <sha> --valido-en <instante> [--conocido-hasta <instante>] [--heredados] [--instalacion instalacion.json]
uv run kbol impacto RAIZ --carpeta kb --base <sha> [--revision <sha>]
uv run kbol consultar RAIZ --carpeta kb[,docs/decisions] --ids ID[#ancla] … --valido-en <instante> [--conocido-hasta <instante>]
uv run kbol buscar RAIZ --carpeta kb[,docs/decisions] --consulta "texto" [--incluir propuestas no_vigentes] [--limite N] --valido-en <instante> [--conocido-hasta <instante>] [--llano [--con-ids]]
uv run kbol soporte RAIZ --carpeta kb[,…] --valido-en <instante> [--conocido-hasta <instante>] [--ids ID …] [--antes-valido-en <instante>] [--antes-conocido-hasta <instante>]
uv run kbol vocabulario RAIZ --carpeta kb[,…] --valido-en <instante> [--conocido-hasta <instante>]
uv run kbol preparar_aprobacion RAIZ --carpeta kb[,…] --operacion-id <op> --base <sha> --propuesta <sha> --valido-en <instante> [--conocido-hasta <instante>] [--texto]
uv run kbol proponer RAIZ --instalacion instalacion.json --operacion-id <op> --archivos RUTA… [--efectos efectos.json] [--importaciones importaciones.json] [--aprobaciones aprobaciones.json] [--actor <actor>] [--hasta ensayo|integrar|subir] [--valido-en <instante>] [--texto]
uv run kbol integrar RAIZ --rama-canonica main --carpeta kb[,…] --operacion-id <op> --base <sha> --propuesta <sha> --aprobaciones aprobaciones.json --recibos <dir> [--remoto origin] [--aprobacion decisiva --actor <actor>]
uv run kbol desvios RAIZ --carpeta kb[,…] [--rama-canonica main] [--preparado]
uv run kbol citas RAIZ --carpeta kb[,…] [--almacen DIR]
uv run kbol integridad RAIZ --carpeta kb[,…] [--almacen DIR]
uv run kbol enlaces RAIZ [--carpeta docs[,…]] [--instalacion instalacion.json]
uv run kbol arranque RAIZ --rama-canonica main --carpeta kb[,…] --operacion-id <op> --base <sha> --persona <PER> --roles <ROL>[,…] --declaracion declaracion.json --recibos <dir>
uv run kbol relevo RAIZ --tarea <id> [--guardar relevo.json] [--rama-canonica main]
uv run kbol preparar_contexto RAIZ --tarea <id> --ambito <ámbito> --carpeta kb --instalacion instalacion.json --valido-en <instante> [--objetivo …] [--presupuesto N] [--heredados-carpeta docs] [--texto]
uv run kbol verificar RAIZ --tarea <id> --instalacion instalacion.json --verificacion <id> [--rama-canonica main]
uv run kbol sesion CARPETA --evento inicio|parar|commit --instalacion instalacion.json [--tarea <id>] [--valido-en <instante>] [--origen compact] [--rutas RUTA …] [--texto]
uv run kbol exportar_skills DESTINO [--skills NOMBRE …]
```

Las consultas no leen el reloj del entorno: `--valido-en` es obligatorio. Sin `--revision` leen el disco y lo declaran; sin `--conocido-hasta` usan todo el historial admitido y lo declaran. Solo cargan registros canónicos del perfil y un registro inválido se informa en la cobertura. El formato heredado se omite, salvo con `--heredados` (`consultar`, `soporte` y `vocabulario` lo leen siempre): entonces se lee aparte, se nombra en el resultado y nunca rige ([elecciones](docs/elecciones.md#lectura-compatible-durante-la-transición)). Es el formato heredado por defecto salvo que la instalación declare el suyo en `formato_heredado` y se pase con `--instalacion` ([elecciones](docs/elecciones.md#formato-heredado-de-otro-proyecto)).

`sesion` es la orden para los hooks de una instalación ([elecciones](docs/elecciones.md#órdenes-para-los-hooks-de-una-instalación)) y la única que lee el reloj: en `inicio`, sin `--valido-en`, usa el instante actual y lo declara en el sobre. Con `--texto` da solo lo que el hook inyecta en la sesión.

Toda salida es el sobre contractual (`operacion`, `operacion_id`, `revision`, `valido_en`, `conocido_hasta`, `resultado`, `advertencias`, `cobertura`). Código de salida: 0 completado, 1 fallido, 2 bloqueado, 3 parcial.

## Módulos

La columna «Control» remite a los controles del contrato KB-DPP que implementa cada módulo.

| Módulo | Responsabilidad | Control |
|---|---|---|
| `modelo` | Vocabulario cerrado del contrato: tipos de registro, prefijos de ID, formas de ID heredadas y enumerados | — |
| `tiempo` | Instantes ISO 8601 con zona y fechas de día, sin leer el reloj del entorno | — |
| `verificacion` | Error común de los verificadores de aprobaciones, sea cual sea su canal, y forma canónica de una revisión para reconocerla repetida | VAL-04 (forma) |
| `core` | Lectura segura de la cabecera (sin claves repetidas, etiquetas, alias ni fusiones; fechas como texto) y escritura validada con ida y vuelta | VAL-01 |
| `schema` | Campos comunes y por tipo, relaciones admitidas por origen, objetos anidados, eventos por clase, marcas del cuerpo; en modo canónico, estado frente a historial | VAL-01 |
| `markdown` | Gramática de `<clausula>` y `<hecho>`, ignorando código y escapes | VAL-01, VAL-06 (forma) |
| `eventos` | Estado reconstruido desde eventos admitidos y validez en intervalo semiabierto | VAL-05 |
| `proyeccion` | Proyección total de `status` para una revisión y dos cortes explícitos | VAL-08 |
| `referencias` | Referencias resolubles, tipo de destino, anclas y ciclos prohibidos sobre un snapshot | VAL-02, VAL-07 |
| `digest` | Objeto aprobable y digest contractual, con vectores publicados en `kbol/vectores/digest.json` | VAL-04 (digest) |
| `consolidar` | Cláusulas que rigen en dos cortes, de una decisión entera o de una cláusula (`ID#ancla`), con origen, cadena y autoridad declarada; propuestas, futuras y conflictos aparte; sin resucitar textos | VAL-05, VAL-06 |
| `dependencias` | Condiciones de `depende_de` y hitos listos; cancelar no equivale a cumplir | VAL-07 |
| `mutabilidad` | Propuesta frente a la base: registros, estados, eventos, contenido cerrado, huellas y cambios de política | VAL-03 |
| `snapshot` | Carga de registros canónicos desde el disco o desde una revisión de git | VAL-14 (cobertura) |
| `autoridad` | Aprobaciones válidas bajo la política de la base: digest calculado, identidad verificada, persona humana activa, rol ocupado en su ámbito y regla del rol | VAL-04 |
| `github` | Verificador de revisiones de PR contra la API de GitHub; sin `KB_GITHUB_TOKEN` no está habilitado | VAL-04 |
| `declarada` | Verificador de aprobaciones declaradas: la cita de la persona en una conversación, ligada a los digests que se le mostraron; nunca autenticada (elecciones, «Mecanismos no conformes») | VAL-04 (parcial) |
| `arranque` | Raíz de confianza de una instalación, una sola vez: activa el rol que gobierna la política y la persona fundadora con la cuenta verificada en GitHub (`GET /user`) o, como mecanismo no conforme, con su identidad declarada y citada; después, todo cambio va por la integración | VAL-04 (raíz) |
| `integrar` | Integración en una rama canónica sin checkout: base esperada, mutabilidad, autoridad, eventos admitidos, conflictos, vocabulario del dominio en el árbol final, commit por compare-and-swap, recibo idempotente y reconciliación. Con `aprobacion="decisiva"`, solo lo decisivo pide aprobación y cada evento lleva el actor de la operación (elecciones, «Mecanismos no conformes») | VAL-13, VAL-15 (parcial) |
| `paquete` | Paquete de aprobación (`kbol preparar_aprobacion`), solo lectura: por registro tocado, qué cambia en la cabecera y en cada cláusula (con el texto que rige y el nuevo si `modifica` otra), los efectos solicitados, si es decisivo y por qué, sus apoyos y si rigen, y su digest; el impacto, lo que no evalúa y el esqueleto de la aprobación declarada, con la base mostrada y los digests y sin identidad, sesión, instante ni cita. Usa el mismo código que la puerta (`integrar.preparar_solicitud` y `integrar.arbol_final`) y, si ella fuera a bloquear, bloquea antes con el mismo código. `--texto` lo presenta a la persona | — |
| `proponer` | Operador de integración (`kbol proponer`): lleva archivos del árbol de trabajo a la rama canónica por el clon del integrador (`$KBOL_ESTADO/<repositorio>/integrador.git`). Trae el remoto sin descartar lo integrado y aún sin subir, escribe la propuesta y su solicitud como un commit con plumbing de git y la pasa por `integrar` sin cambiarlo. Por defecto ensaya en una rama temporal que borra; con `--hasta integrar` escribe la rama canónica del clon y con `--hasta subir` hace además `git push` sin forzar. No arma aprobaciones: recibe las declaradas ya dadas y, si falta una, el ensayo devuelve el paquete de aprobación y termina con 3. Después de integrar ejecuta los pasos que declara la instalación y escribe en un commit propio las vistas que regeneran; si un paso falla o cambia otra cosa, no sube. El remoto, el nombre del estado local, el modo de aprobación, los pasos, las vistas y el autor de sus commits vienen del bloque `integracion` de la instalación, leída de `HEAD` | VAL-13 (operación) |
| `importacion` | Guarda de la importación de un heredado: mismo cuerpo salvo marcas y espacios, procedencia regenerada y ningún texto nuevo | VAL-02, VAL-03 |
| `huellas` | Huella de cada registro que escriben la integración y el arranque, y `desvios`: registros con historial editados fuera del flujo; avisa, no bloquea. Con la rama canónica, también los commits que cambian registros sin pasar por la puerta | — (elección local) |
| `exportar` | Skills de KBOL empaquetadas en `kbol/skills/` y `kbol exportar_skills`, que las escribe con la versión instalada en su cabecera; solo sobrescribe lo que exportó ella misma | — ([elecciones](docs/elecciones.md#skills-empaquetadas)) |
| `impacto` | Consumidores afectados por un cambio, con causa, camino y responsable | VAL-09 |
| `relevo` | Estado de una tarea separado de la conversación (objetivo, autorización, límites, verificaciones, bloqueos y siguiente paso), guardado en local en `.kbol/relevos/`, con hechos de git; declara lo que no consta y no ejecuta nada. Una verificación ejecutada deja de valer si cambia la revisión o el árbol de trabajo, y la que se repite pasa al historial | ESC-05 |
| `verificar` | Ejecutor de las verificaciones declaradas en la instalación (id, orden como lista de argumentos, tiempo límite y código esperado), sin shell ni argumentos de quien la pide. Desde la CLI, la instalación se lee de `HEAD`, dentro de la raíz y sin cambios locales. Corre con un entorno sin `KB_GITHUB_TOKEN` ni `GIT_*`, escribe la salida en la evidencia de `.kbol/verificaciones/` y, si agota el tiempo, se detiene con todos sus procesos. Anota en el relevo el resultado con revisión y árbol probados, instantes, código, duración, evidencia, huella de lo declarado e intérprete usado; si la orden cambia el árbol o la cabeza, queda pendiente de revisión. Sin aislamiento ni recibos | Operación `verificar` (parcial) |
| `contexto` | `preparar_contexto`: paquete de una tarea con las restricciones decisivas, que nunca se recortan; propuestas y pendientes aparte como no vinculantes; procedimientos, relevo, omisiones y condiciones de refresco | ESC-06, ESC-09 (parcial) |
| `sesion` | Órdenes para los hooks de una instalación (`kbol sesion`), desde cualquier carpeta del árbol de trabajo y con la configuración de la instalación: `inicio` da el paquete de contexto de la tarea, que sale de la rama, y los desvíos con una sola carga, y lo reutiliza de `.kbol/sesion/` mientras no cambie la huella de lo que lo decide; `parar` valida como propuestas los registros con cambios sin commitear; `commit` avisa de los desvíos del índice de git sin bloquear | — |
| `consultar` | Consulta por `ID` o `ID#ancla`: el registro con su estado al corte, su autoridad (ratificaciones, declaradas o heredada, y de cada aprobación vigente quién, cuándo, por qué canal y con qué palabras, tal como las conserva el registro; nunca comprobada), sus relaciones y el texto del ancla; en una decisión, si esa cláusula rige; para sus apoyos, si existen y rigen en el corte, y si la evidencia es suficiente; los campos de trabajo y, para una persona, lo que tiene asignado. Un ID heredado se nombra y no rige | RES-01, RES-04 (parcial) |
| `buscar` | Búsqueda léxica en memoria (`kbol buscar`): candidatos por texto o alias con ID, ancla, estado, vigencia y fragmento; por defecto solo lo vigente, y las propuestas y lo que no rige contados y solo si se piden. No decide qué rige | Núcleo §8 (exploración) |
| `sustituciones` | Indicio léxico `SUSTITUCION_NO_DECLARADA`: un registro que dice sustituir o derogar a otro sin declararlo en `modifica` ni en `deja_obsoleta`. Señala y no bloquea | — |
| `llano` | Salida en lenguaje llano de `consultar`, `consolidar` y `buscar` (`--llano`, IDs con `--con-ids`) | — |
| `soporte` | Consulta de solo lectura (`kbol soporte`): para cada registro, si rigen en los dos cortes sus apoyos (`basada_en`, `dependencias`, `sources` y `<hecho ref>`), con el campo de origen, la situación (`rige`, `no_rige`, `indeterminado`, `ausente`, `heredado` o `sin_vigencia`) y su motivo, y un resumen (`intacto`, `roto`, `indeterminado` o `sin_apoyos`); con un segundo par de cortes, los apoyos cuya situación cambia y la cadena que lo explica. La regla de qué rige es `dependencias.rige_al_corte`, la misma de las dependencias y de la evidencia de `consultar`. Señala y no bloquea | — |
| `vocabulario` | Vocabulario del dominio (`kbol vocabulario`): las clases de entidad que declaran las decisiones con `define` y rigen en los dos cortes (una cláusula que rige con el texto de su decisión), sus alias, los términos indeterminados (vigencia ambigua, conflicto o dos definiciones) y retirados, y los ámbitos de los roles activos; señala los términos no declarados y retirados con sus usos y los ámbitos sin rol activo. Sin ningún término declarado, mundo abierto y la cobertura lo dice. Señala y no bloquea; la puerta de integración bloquea el paso a `activa` de una entidad con una clase que no rige | — |
| `migracion` | Adaptador de lectura del formato heredado, el formato por defecto o el que declare la instalación: inspección en seco, sin escribir | — |
| `localizador` | Forma de los localizadores de `sources[].ancla`: `lines-v1` (líneas), `pdf-v1` (página física y región normalizada) y `norma-v1` (unidad lógica de una norma), combinables como `norma-v1:… @ pdf-v1:…`; lee como `lines-v1` las anclas heredadas `l. a-b` y `La-Lb` | RES-04 (forma) |
| `citas` | Resolutor de citas (`kbol citas`): huella del original y de la representación, página, región, unidad lógica y cita literal normalizada (`contexto`) contra una estructura `estructura-v1`; texto por líneas contra el blob de la revisión anclada; un documento sin páginas (Word, hoja, HTML), por líneas de su representación en texto (`representacion_id`), que debe derivar del original. Estados `resuelta`, `rota`, `inconsistente`, `ambigua` y `no_comprobable` (original o representación ausentes: integridad sin comprobar). No lee PDF ni importa procesadores | RES-04 (parcial) |
| `integridad` | Integridad de las fuentes (`kbol integridad`): compara el `sha256` de cada fuente con los bytes de su `ubicacion`, sin normalizarlos, en el almacén (`almacen:sha256/…`), en una revisión anclada (`git:<sha>:<ruta>`) o en el árbol de trabajo (ruta de la raíz). Estados `coincide`, `alterada`, `ausente` y `no_comprobada`, con su causa; lo que no se pudo mirar no se da por roto. Una fuente rota termina `fallido` (`INTEGRIDAD_ROTA`) y una sin comprobar, `parcial`. No guarda la última comprobación | VAL-10 (parcial) |
| `enlaces` | Enlaces de los documentos Markdown de un repositorio (`kbol enlaces`): rutas internas con sus mayúsculas, fragmentos contra las anclas del destino (títulos al estilo de GitHub, `id=` y las marcas de cláusula), anclas explícitas repetidas y rutas absolutas locales, con markdown-it y sin contar el código. Lo que existe es lo que git ve. La instalación declara en `enlaces` lo que no se revisa (`excluir`) y la deuda que no bloquea (`deuda`). Un enlace roto termina `fallido` | — ([elecciones](docs/elecciones.md#enlaces-de-la-documentación)) |
| `cli` | Punto de entrada `kbol`: reparte las operaciones habilitadas, devuelve siempre el sobre contractual y falla cerrado en las no habilitadas; fija los códigos de salida | — |

## Qué no hace todavía

`ingerir` devuelve `bloqueado` en la CLI. `integridad` comprueba cada vez y no guarda la última comprobación válida, y las dependencias `disponible_con_integridad` siguen sin consultarla. `verificar` ejecuta solo verificaciones declaradas y no las aísla: no limita efectos más allá del tiempo, no emite recibos ni hay hitos que la pidan, y en Windows no detiene un proceso que la orden deje vivo después de terminar. Si la raíz no tiene `.venv` propio, `{python}` es el intérprete de KBOL y lo instalado allí como editable puede ser de otra copia: el resultado lo avisa. La huella del árbol no ve los archivos ignorados y cambia con un `git add` aunque el contenido no cambie; `impacto` es una consulta de solo lectura entre dos revisiones, sin reloj. `arranque` e `integrar` se prueban sobre repositorios temporales. La CLI los expone solo con el mecanismo declarado (elecciones, «Mecanismos no conformes»): `integrar` con una lista de aprobaciones declaradas y `arranque` con una declaración; con `--remoto`, `integrar` trae el remoto y exige que la base y la rama local sean su cabeza, y nunca sube nada. `proponer` es la única orden que sube, solo con `--hasta subir` y sin forzar; si el remoto rechaza la subida o un paso posterior falla, lo integrado queda en el clon del integrador sin subir y la orden no lo deshace. Sus pasos posteriores corren sin aislamiento, como `verificar`, y no comprueba que el árbol de trabajo parta de la cabeza de la rama canónica: propone los archivos tal como están en el disco. La aprobación por revisión de pull request en GitHub existe como biblioteca y no está expuesta en la CLI. El verificador de GitHub no se ha probado contra el servicio real. Faltan la restauración de copias, el aislamiento de las verificaciones y la ingesta. La búsqueda sin ID (`buscar`) es léxica, sin similitud semántica ni índice persistente. Tampoco hay delegaciones entre roles ni servidor MCP: la política se limita a roles y personas.

## Pruebas

`tests/`, en Python 3.10 y 3.14, y los de `tools/di` (procesado de documentos con Docling) en su propio proyecto. `uv run python tools/comprobar.py` lo ejecuta todo junto con el análisis estático; con `--sin-di`, sin `tools/di`, y con `--rapido`, además, la suite una sola vez. `uv run python tools/comprobar.py --instalar-hook` instala la pasada rápida como hook `pre-push`. `tests/heredados/` guarda registros inventados con la forma del formato heredado para probar el adaptador de migración, con su huella en `tests/heredados/LEEME.txt`.

## Licencia

Apache-2.0: [LICENSE](LICENSE) y [NOTICE](NOTICE). Copyright 2026 David Palazón.
