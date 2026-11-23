# kbol-di · Document Intelligence

Herramientas de Document Intelligence de KBOL: llevan un documento desde su origen hasta una representación que `kbol citas` sabe comprobar y una carpeta que se puede navegar y relacionar. Nacieron con el primer piloto (normativa: CRA, R. 2025/2392, NIS2 y ENS); desde la 0.2 sirven para un PDF cualquiera y desde la 0.3 para Word, hojas de cálculo, PowerPoint y HTML. Proyecto uv aparte para que Docling y torch no entren en el núcleo ni en las instalaciones. No integra registros ni habilita `ingerir`: produce artefactos en un almacén y los datos para escribir fuentes derivadas.

Contrato: los localizadores de `kbol/localizador.py`; el resolutor que los comprueba es `kbol citas`. El procedimiento para incorporar un documento y citarlo está en la skill [incorporar-documento](../../.claude/skills/incorporar-documento/SKILL.md).

```bash
cd tools/di
uv sync                      # docling 2.142.1, exclude-newer 2026-10-24, CPU
uv run python -m pytest -q
uv run python -m di incorporar <URL o archivo> --nombre usad   # de principio a fin, con su carpeta
uv run python -m di localizar <sha256 del JSON de Docling> "<cita literal>"
```

| Formato | Procesador | Representación que se cita | Cita | Contraste |
|---|---|---|---|---|
| PDF con capa de texto | Docling, con las figuras como imagen | Estructura genérica | `pdf-v1:p=…` | pypdf, por página |
| PowerPoint | Docling | Estructura genérica (una diapositiva por página) | `pdf-v1:p=<diapositiva>` | ninguno |
| Word, hoja de cálculo | Docling | Su exportación a Markdown | `lines-v1:…` con `representacion_id` | ninguno |
| HTML | MarkItDown | El Markdown que produce | `lines-v1:…` con `representacion_id` | ninguno |

El formato sale de la extensión del origen. Un origen sin extensión (la URL de un PDF en EUR-Lex) se trata como PDF, como siempre; `--formato pdf|docx|pptx|xlsx|html` lo declara a mano cuando el origen no lo dice o lleva otra extensión.

Citar por líneas una representación, y no el original, necesita KBOL 0.10.0 o posterior. Un HTML no tiene estructura ni carpeta: solo su Markdown.

## La carpeta del documento

Con `--nombre`, `incorporar` genera `documentos/<nombre>/` junto al almacén (o en `--destino`); `di proyectar <sha256 de la estructura> --nombre <nombre>` la regenera sin volver a procesar.

```
documentos/usad/
  usad.pdf                     el original
  index.md                     qué es el documento y qué hay en la carpeta
  contenidos/NN-<título>.md    una sección por fichero
  recursos/tablas/tabla-M.md   cada tabla en Markdown y cada dato con sus cabeceras
  recursos/figuras/figura-M.*  la imagen y su ficha
  recursos/bibliografia.md     las entradas de la bibliografía con su clave
```

Cada fichero lleva una cabecera YAML de estilo OKF: `id` (`usad#seccion=17`), `type`, `title`, `description`, y lo propio de su tipo. Una sección añade `numero`, `profundidad`, `padre`, `hijos`, `ruta`, `tipo`, `paginas` (o `lineas` en un documento sin páginas), `referencias`, `recursos`, `origen` (las huellas y las unidades de la estructura que cubre) y `generated`. El cuerpo es el texto del documento con marcas XML que no lo alteran: `<pagina n="7"/>`, `<ref clave="17">[17]</ref>`, `<recurso tipo="tabla" id="tabla-2" ref="…">leyenda</recurso>`, `<nota>`, `<formula>`.

La carpeta es una vista generada, no conocimiento registrado: sale del mismo cálculo que la estructura, se regenera entera y no se edita a mano (si la carpeta de destino existe y no la generó esta herramienta, no la toca). Las citas se escriben contra la estructura o el Markdown, con la página o las líneas que dice cada fichero. Como contiene una copia del documento, va fuera del repositorio.

Las órdenes sueltas, que `incorporar` encadena y que el flujo de normas usa una a una:

```bash
uv run python -m di capturar <URL o archivo> --medio application/pdf
uv run python -m di procesar <sha256 del original> [--formato .pdf|.docx|.pptx|.xlsx|.html]
uv run python -m di estructura <sha256 del JSON de Docling> --original <sha256> [--perfil norma [--ordenar] | --perfil generica [--sin-corregir]]
uv run python -m di fidelidad <sha256 de la estructura> --original <sha256> [--editor <sha256> --tipo eurlex|boe]
```

El almacén es `KBOL_ALMACEN` o `$KBOL_ESTADO/<repositorio>/almacen`, donde el repositorio es el nombre del estado local de la instalación y se da en `KBOL_REPOSITORIO`; sin esa variable vale `predeterminado` (por defecto, `~/.kbol/predeterminado/almacen`). Guarda `sha256/<huella>` para cada objeto (nunca se sobrescribe) y `meta/<huella>.json` con sus orígenes y la fecha de la primera captura.

## Dos perfiles de estructura

Los dos producen `estructura-v1`, la representación que lee el resolutor. Cambia cómo se agrupa el documento y, con ello, cómo se cita.

| | `norma` | `generica` |
|---|---|---|
| Para | Redacción normativa de la UE y del BOE | Cualquier otro PDF: informe, artículo, manual, contrato |
| Unidades | Considerando, artículo, apartado, punto, letra, anexo… (`norma-v1`) | Sección por página (`seccion=n;pagina=p`), tabla y figura con leyenda |
| Cita | Lógica y física: `norma-v1:art=14;ap=2 @ pdf-v1:p=37;r=…` | Solo física: `pdf-v1:p=8;r=…` |
| Fidelidad | Por unidad contra el texto del editor (EUR-Lex, BOE) | Contraste por página con pypdf |
| Orden de lectura | El de Docling; `--ordenar` lo corrige | Corregido, junto con rótulos y flotantes; `--sin-corregir` deja lo que da Docling |

Desde la 0.2 del segmentador, cada unidad del perfil genérico lleva además su contexto en el documento, sin interpretar lo que dice:

| Campo | En | Qué es |
|---|---|---|
| `numero`, `profundidad`, `padre` | sección | Numeración («5.3»), nivel y clave de la sección que la contiene, sacados de la numeración del título |
| `ruta` | sección, tabla, figura | Títulos desde la raíz: `["5 Experiments and results", "5.3 Training time"]` |
| `tipo` | sección, tabla, figura | `resumen`, `introduccion`, `trabajos_relacionados`, `metodo`, `experimentos`, `resultados`, `conclusiones`, `referencias`, `anexo` o `agradecimientos`; una subsección sin tipo propio hereda el de su padre |
| `referencias` | sección | Claves de la bibliografía que cita ese trozo («17», o «feng 2021» en estilo autor-año) |
| `leyenda` | tabla, figura | Su pie («Table 2: Performance comparison…») |
| `celdas` | tabla | Cada dato con su página, fila, columna, las cabeceras de su columna (`["SWaT", "Without", "F1"]`) y la etiqueta de su fila (`["USAD"]`) |

La estructura trae también `referencias` en la raíz: las entradas de la bibliografía con su clave, texto, páginas y sección. Una cita del texto sin entrada en la bibliografía queda en `avisos`. El `texto` de cada unidad sigue siendo el del PDF: las cabeceras resueltas van aparte para que no se citen como si estuvieran escritas así.

Las claves del perfil genérico no son un localizador `norma-v1` a propósito: nombran unidades de esta representación y no una división estable del documento. La sección se parte por página para que la página de la cita se compruebe de verdad; un párrafo partido entre dos páginas se resuelve en las dos.

Lo que el resolutor comprueba en una cita solo física es la huella del original y de la representación, que la página existe y que la cita literal está en el texto de esa página. La región (`r=`) queda escrita para que una persona encuentre el pasaje, pero `kbol citas` no la contrasta si la cita no lleva parte lógica: una región equivocada en la página correcta se da por buena.

## Módulos

| Módulo | Qué hace | Límites |
|---|---|---|
| `almacen` | Captura por URL o archivo, relee y comprueba la huella; reintento idempotente | Un escritor; sin bloqueo |
| `procesar` | Docling en CPU, sin OCR, tablas en modo preciso y figuras como imagen a doble resolución; guarda el JSON nativo de DoclingDocument y, para Word y hojas de cálculo, su Markdown; un HTML pasa por MarkItDown | Terminar no prueba fidelidad; un PDF escaneado sale vacío; las cuatro normas del primer piloto se procesaron sin imágenes |
| `estructura` | Unidades `norma-v1` con páginas, regiones y texto; recupera encabezados que Docling dejó como cabecera, descarta entradas de índice y sustituye el glifo U+0840 que Docling lee en lugar de U+2003 en el BOE, todo declarado en `avisos` | Redacción de la UE y del BOE |
| `generica` | Unidades por título, página, tabla y figura de cualquier PDF; un rótulo de algoritmo, tabla o figura no abre sección, un título repetido tampoco, y cada tabla o figura va a la sección que la menciona, todo declarado en `avisos` | La sección es la que detecta Docling; sin leyenda numerada, un flotante se queda donde cae |
| `contexto` | Jerarquía de secciones por su numeración, tipo de parte por el título, celdas de tabla con cabeceras resueltas a través de las combinadas, y llamadas a la bibliografía numéricas o de autor y año | Docling da a todos los títulos el mismo nivel: sin numeración no hay jerarquía; el tipo se deduce del título y no del contenido; un apartado «1.» tras «3.3» se toma por apartado y se avisa; corchetes con números mayores que la bibliografía no cuentan como cita |
| `orden` | Orden de lectura por página a partir de la posición de los bloques: bandas, dos columnas y renglones; deja sin tocar la página que no entiende y lo dice | Dos columnas como mucho; no lee el contenido |
| `editor` | Unidades según el HTML de EUR-Lex y el XML del BOE, sin notas al pie | Los puntos internos de un anexo de EUR-Lex se miden al nivel del anexo |
| `fidelidad` | Por unidad de norma: existencia y unicidad, recuerdo de palabras, fechas, negaciones y excepciones; documento: recuerdo y palabras partidas frente a pypdf | Las tablas se miden por su texto, no celda a celda |
| `contraste` | Sin editor: por página, qué parte de lo que lee pypdf está en la estructura y al revés, y las cifras una a una; declara las páginas sin capa de texto | Dos lecturas de la misma capa de texto comparten sus errores; no mide orden ni sentido; no detecta un texto colocado en la página contigua a la suya |
| `localizar` | Página y región de una cita literal, para escribir su `pdf-v1` | No busca en notas al pie; recorre el orden de Docling, así que una cita a caballo entre dos bloques que `orden` recoloca puede no encontrarse |
| `incorporar` | Encadena captura, procesado, estructura genérica, contraste (solo PDF) y, con `--nombre`, la carpeta; devuelve los datos de las fichas y qué revisar | No escribe registros ni juzga la calidad |
| `proyectar` | Carpeta navegable del documento desde su estructura: índice, una sección por fichero con su contexto, tablas, figuras y bibliografía | Vista regenerable; no borra una carpeta que no generó |

## Lo medido

Corregir el orden de lectura en las cuatro normas del primer piloto, medido con `fidelidad` contra el texto del editor (10 nov 2026, DoclingDocument de Docling 2.142.1 ya en el almacén). Sin `--ordenar`, la estructura sale byte a byte igual que la registrada entonces.

| Norma | Unidades únicas | Recuerdo medio | Orden de artículos | Páginas recolocadas |
|---|---|---|---|---|
| CRA | 600 → 607 de 607 | 0,9982 → 0,9997 | 0,9859 → 1,0 | 3 de 81 |
| NIS2 | 603 de 603, igual | 0,9999, igual | 1,0, igual | 3 de 73 |
| R. 2025/2392 | 16 de 16, igual | 1,0, igual | 1,0, igual | 1 de 11 |
| ENS | 178 → 179 de 187 | 0,9788 → 0,9929 | 0,9524, igual | 81 de 90 |

Ninguna métrica empeora. `--ordenar` no es el valor por defecto en el perfil de normas porque cambiaría las derivaciones que ya citan los hechos registrados: usarlo produce una derivación nueva, y sustituir la anterior es una decisión de quien mantiene esos registros. El artefacto sin `--ordenar` es el mismo, pero su ficha no: `codigo_sha256` cambia porque `estructura.py` ha cambiado, y gana el campo `configuracion`.

El perfil genérico se ha probado de principio a fin, con el Docling fijado, en un artículo a dos columnas de ACM (11 páginas, 110 s en CPU): secciones en su orden, citas resueltas en su página y rotas en la contigua, y contraste con pypdf de 0,996 de recuerdo y 0,998 de respaldo, con la página de fórmulas como único aviso. La segmentación y el orden se han probado además sobre DoclingDocument de otra versión de Docling (2.150, con OCR) de tres artículos más: dos columnas de IEEE, una columna de Springer y una revisión de 42 páginas. Informes con diseño gráfico, diapositivas, formularios y cualquier maquetación a tres columnas siguen sin probar.
