---
name: incorporar-documento
description: Incorpora un documento (PDF con capa de texto, Word, hoja de cálculo, PowerPoint o HTML) a una base de conocimiento de KBOL para citarlo de forma comprobable y navegarlo como carpeta. Úsala cuando haya que registrar un documento como fuente, citar una frase o una cifra suya en un registro, consultar qué dice un documento ya incorporado, o comprobar que sus citas se resuelven. No sirve para PDF escaneados.
---

# Incorporar un documento

Un PDF pasa a ser citable cuando existen tres cosas: el original guardado con su huella, una representación de ese original (`estructura-v1`) y una cita que `kbol citas` comprueba contra las dos. Esta skill produce las tres. No acepta conocimiento: las fichas y los hechos entran como propuesta, por el procedimiento de la instalación donde se registran.

Las herramientas están en `tools/di` de KBOL, con su propio entorno (Docling fijado, en CPU). Todas las órdenes se lanzan desde esa carpeta. El almacén es `$KBOL_ESTADO/<repositorio>/almacen`, con el nombre de la instalación en `KBOL_REPOSITORIO` (sin esa variable, `~/.kbol/predeterminado/almacen`); para una prueba que no deba dejar rastro, apunta `KBOL_ALMACEN` a una carpeta temporal antes de empezar.

## 1. Incorporar

```bash
cd <raíz de KBOL>/tools/di
uv sync                                         # solo la primera vez
uv run python -m di incorporar <archivo o URL> --nombre <nombre corto> > <carpeta de trabajo fuera de KBOL>/incorporacion.json
```

`--nombre` es el de la carpeta del documento (`usad`, `cra-2024`): minúsculas, sin espacios. El formato sale de la extensión; un origen sin extensión se toma por PDF, y `--formato html` (o `docx`, `pptx`, `xlsx`, `pdf`) lo declara cuando la URL no lo dice. Tarda dos o tres segundos por página, más un minuto largo de arranque. El progreso sale por la salida de errores y no ensucia el JSON. La salida trae:

- `original` y, según el formato, `docling`, `estructura` y `markdown`: la huella (`sha256`) de cada objeto y los datos de su ficha.
- `contraste` (solo PDF): el resumen de comparar la estructura con una segunda lectura (pypdf).
- `carpeta`: dónde quedó la carpeta del documento y cuántas secciones, tablas y figuras tiene.
- `revisar`: lo que hay que mirar antes de citar.

| Formato | Qué se cita | Cómo |
|---|---|---|
| PDF, PowerPoint | La estructura | Por página (`pdf-v1:p=…`; en un PowerPoint, la diapositiva) |
| Word, hoja de cálculo | El Markdown que exporta Docling | Por líneas (`lines-v1:…`) |
| HTML | El Markdown que produce MarkItDown | Por líneas; no tiene estructura ni carpeta |

## La carpeta del documento: por dónde empezar a leerlo

Queda en `documentos/<nombre>/`, junto al almacén. Es la forma de entender el documento sin abrir el original:

- `index.md`: qué es, la lista de secciones con sus páginas, las tablas, las figuras y los avisos de la segmentación.
- `contenidos/NN-<título>.md`: una sección por fichero. La cabecera dice su ruta en el documento, su tipo (método, resultados…), sus páginas o líneas, a qué referencias de la bibliografía llama y qué tablas y figuras contiene.
- `recursos/tablas/tabla-M.md`: la tabla y, debajo, cada dato con su fila y sus cabeceras («USAD · SWaT › Without › F1 = 0.7917 (pág. 7)»). Para una pregunta sobre una cifra, empieza aquí.
- `recursos/bibliografia.md`: las entradas, con la clave que usan las marcas `<ref clave="17">` del texto.

La carpeta no se edita: se regenera. Para citar, no copies del cuerpo de estos ficheros sin más: localiza la cita como dice el paso 4, contra la estructura o el Markdown.

## 2. Leer `revisar` antes de seguir

Cada objeto del almacén está en `<almacén>/sha256/<huella>`, sin extensión. El informe del contraste (`contraste.sha256`) y la estructura (`estructura.sha256`) son JSON. El informe trae, por página, el recuerdo, el respaldo y las cifras discrepantes una a una; no trae el texto perdido. Para ver qué leyó Docling en una página, mira `unidades[].texto` de la estructura: es también donde se elige qué citar.

| Aviso | Qué significa | Qué hacer |
|---|---|---|
| Páginas sin capa de texto | Son imágenes: Docling no ha leído nada en ellas | No cites esas páginas. Un PDF escaneado entero no se puede incorporar con esta skill: dilo y para |
| Páginas donde la estructura pierde texto | pypdf ve texto que la estructura no tiene | Compara el texto de la estructura en esa página con el PDF antes de citar de ella, o no cites de ella. Suele ser una página de fórmulas |
| Páginas con texto que pypdf no ve ahí | Texto asignado a otra página, o fórmulas y símbolos que cada lector escribe distinto | Comprueba en el PDF la página de lo que cites de ahí |
| Cifras ausentes o sin respaldo | Un número está en una lectura y no en la otra | Si vas a citar una cifra de esa página, compárala con el PDF a ojo. Los números de ecuación y los rangos de páginas suelen ser ruido; una cifra de una tabla, no |
| Páginas sin ninguna unidad | La estructura no cubre esa página | No se puede citar nada de ella |

Un contraste limpio no prueba que la lectura sea correcta: los dos lectores comparten la capa de texto del PDF, y el contraste no mide el orden de lectura ni el sentido. Sirve para saber dónde mirar.

## 3. Escribir las tres fichas de fuente

Una por objeto, con un ID nuevo (`F-` más un UUID). El ámbito, la clase, el autor y el prefijo del ID de los demás registros son los de la instalación; copia la forma de sus registros existentes. Tres campos no salen de la orden y los pones tú: `origen` lleva la procedencia real del documento (editor, DOI, URL), no solo la ruta local desde la que se capturó; `acceso` es texto libre que dice quién puede leerlo; las fechas van en ISO 8601 con zona (`2026-11-10T17:49:21+01:00`). Un valor con llaves, comas o dos puntos va entre comillas simples. Los campos que salen de `incorporacion.json`:

```yaml
# Original
type: fuente
subtipo: original
title: '<título del documento>: PDF'
origen: <de dónde salió y cuándo: original.origenes y original.capturado_en>
ubicacion: almacen:sha256/<original.sha256>
formato: application/pdf
sha256: <original.sha256>
acceso: <quién puede leerlo; hereda la restricción del documento>
```

```yaml
# DoclingDocument
type: fuente
subtipo: derivada
title: '<título>: DoclingDocument'
ubicacion: almacen:sha256/<docling.sha256>
formato: application/json
sha256: <docling.sha256>
acceso: <la del original>
derivada_de: [<ID de la ficha del original>]
procesador: docling
version_procesador: <docling.version>
configuracion_ref: '{"configuracion": <docling.configuracion>, "versiones": <docling.versiones>}'
procesado_en: <docling.procesado_en>
procesamiento: procesado
```

```yaml
# Estructura: la representación que citan los registros
type: fuente
subtipo: derivada
title: '<título>: estructura de unidades (estructura-v1)'
ubicacion: almacen:sha256/<estructura.sha256>
formato: application/json
sha256: <estructura.sha256>
acceso: <la del original>
derivada_de: [<ID de la ficha del DoclingDocument>]
procesador: kbol-di/generica
version_procesador: '<estructura.version>'
configuracion_ref: 'tools/di de KBOL, código sha256 <estructura.codigo_sha256>, configuración <estructura.configuracion como JSON>'
procesado_en: <la fecha de hoy, con zona>
procesamiento: procesado
calidad:
  contraste_con_pypdf:
    metodo: Contraste por página con pypdf (kbol-di contraste, informe <contraste.sha256> en el almacén)
    resultado: <conforme si revisar está vacía; parcial si no>
    limites: <el resumen en una frase: recuerdo, respaldo, cifras discrepantes y páginas afectadas>
  orden_lectura:
    metodo: no_evaluado
```

Escribe en `calidad` lo que dice el informe, también cuando es malo. No pongas `conforme` por haber terminado el proceso, y no dejes fuera los avisos de la estructura (`estructura.avisos`) que afecten a lo que se va a citar.

## 4. Citar

Para cada frase o cifra, saca su página y su región:

```bash
uv run python -m di localizar <docling.sha256> "<cita literal, tal como está en el PDF>"
```

Devuelve una lista de hallazgos; cada uno, una región por página. Con el resultado se escribe la cita en `sources` del registro:

```yaml
sources:
- id: s1
  resource: <ID de la ficha del original>
  representacion_id: <ID de la ficha de la estructura>
  hash: <original.sha256>
  ancla: pdf-v1:p=<p>;r=<r[0]>,<r[1]>,<r[2]>,<r[3]>
  contexto: <la cita literal>
```

- Lista vacía: la frase no está tal cual. Acórtala o corrige las comillas y los guiones; no la des por buena.
- Más de un hallazgo: la frase aparece en varios sitios. Elige mirando el PDF, o alarga la cita hasta que sea única.
- Un hallazgo con dos regiones: la frase cruza un salto de página. Cita la página donde empieza.
- Una tabla se localiza celda a celda: busca el valor solo (`"63.74"`), no la fila. La cita lleva ese valor en `contexto`. A qué fila y columna pertenece está en la estructura: la unidad de la tabla (`seccion=n;tabla=m`) trae en `celdas` cada dato con su página, sus cabeceras y la etiqueta de su fila (`"cabeceras": ["SWaT", "Without", "F1"], "fila": ["USAD"]`). Escríbelo en el cuerpo del registro. Si el valor se repite, las celdas dicen cuál es cuál; elige por cabeceras y fila, no por el primer hallazgo de `localizar`.
- Para situar lo que citas, usa la `ruta` de la unidad («5 Experiments › 5.3 Training time») y su `tipo` (resultados, método…). Si el pasaje cita bibliografía, `referencias` de la unidad da las claves y `referencias` en la raíz de la estructura, sus entradas.
- Las regiones vienen como texto con cuatro decimales: cópialas tal cual. La de una frase es la de su párrafo entero.
- La cita literal es texto del documento, no un resumen. Lo que el registro afirma va en su cuerpo; lo que el documento dice va en `contexto`.

### Word, hoja de cálculo o HTML: por líneas del Markdown

No tienen páginas: se citan por líneas de su representación en Markdown (`markdown.sha256` en la salida), que necesita su propia ficha de fuente derivada con `formato: text/markdown` y `derivada_de` hacia el DoclingDocument (en un HTML, hacia el original). Para encontrar las líneas, cada fichero de `contenidos/` dice en `lineas` las que ocupa su sección; dentro de ese tramo, busca la frase en el Markdown del almacén y anota su línea de inicio y de fin.

```yaml
sources:
- id: s1
  resource: <ID de la ficha del original>
  representacion_id: <ID de la ficha del Markdown>
  hash: <original.sha256>
  ancla: lines-v1:<inicio>-<fin>
  contexto: <la cita literal, tal como está en el Markdown>
```

## 5. Comprobar

Con las fichas y los registros en una carpeta de la instalación:

```bash
cd <raíz de la instalación>
uv run kbol citas . --carpeta <carpeta de los registros> --almacen <almacén>
```

Si la instalación no tiene KBOL en su entorno, `uv run --project <raíz de KBOL> kbol citas <raíz de la instalación> …`. La salida es un JSON con una fila por cita, el `recuento` por estado y las `advertencias`; con alguna cita rota la orden termina con código 3 y estado `parcial`. Cada cita tiene que salir `resuelta`. Los demás estados:

| Estado | Causa habitual |
|---|---|
| `rota` | La página no es esa, la cita literal no está en esa página o una huella no coincide |
| `no_comprobable` | El original o la estructura no están en el almacén de esta máquina, o falta `--almacen` |
| `inconsistente`, `ambigua` | Solo en citas de normas con parte lógica |

Una cita `rota` no se arregla cambiando la página hasta que pase: vuelve a `localizar` y mira el PDF.

`resuelta` significa que las huellas coinciden y que la cita literal está en el texto de esa página. No comprueba la región ni que el registro afirme lo mismo que el documento: eso lo revisa una persona con la página abierta.

## Límites

- Un PDF escaneado no se puede incorporar: sin capa de texto, Docling no lee nada y no hay contraste posible.
- Word, hojas de cálculo, PowerPoint y HTML no tienen segunda lectura con la que contrastar: lo que cites de ellos, revísalo a ojo. Citar un Word o un HTML por líneas necesita KBOL 0.10.0 o posterior.
- Dos columnas como mucho. Una página con otra maquetación conserva el orden de Docling y lo dice en los avisos.
- Las fórmulas no se leen: quedan como hueco, y sus números aparecen como cifras ausentes.
- Las normas de la UE y del BOE tienen un perfil propio con cita por artículo y medida contra el texto del editor: para ellas, las órdenes sueltas de `tools/di/README.md`, no `incorporar`.
- Reprocesar con otra versión o configuración da otra huella: es otra derivación, con su ficha. Las citas ya escritas siguen apuntando a la anterior.
