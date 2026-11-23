# Registro de cambios

Las versiones siguen la forma `MAYOR.MENOR.PARCHE`. Mientras KBOL esté en 0.x, una versión menor puede romper la CLI: cada cambio incompatible o potencialmente incompatible lleva su nota, con por qué, a quién afecta y cómo migrar, en [docs/cambios.md](docs/cambios.md). Este registro resume; esa nota manda.

0.12.0 es la primera versión publicada en este repositorio. Las anteriores se desarrollaron en un repositorio privado: sus notas se conservan como historia del proyecto, pero no tienen etiqueta aquí.

## Sin publicar

- GIF de demostración en los README (`docs/demo.gif`), grabado con salida real por `tools/demo_gif.py`.
- Prueba rápida en un script, `examples/quickstart.sh`, que la integración continua ejecuta de principio a fin.
- Badges de integración continua, versión, licencia y Python en los README.

## 0.12.0 · 23 nov 2026

Primera versión pública.

- `kbol buscar`: búsqueda léxica por texto o alias, en memoria, para cuando no se conoce el ID. Da candidatos con estado, vigencia y fragmento; por defecto solo lo vigente. No decide qué rige.
- `--llano` en `consultar`, `consolidar` y `buscar`: respuesta en prosa sin IDs, con la etiqueta de cada bloque (`[APROBADA]`, `[PROPUESTA: …]`…); los IDs, con `--con-ids`.
- Aviso `SUSTITUCION_NO_DECLARADA` en `consultar` y `consolidar`: un registro dice en prosa que sustituye a otro sin declararlo. Señala y no bloquea.
- `consultar` da `relaciones_inversas`: qué registros dejan obsoleto o modifican al consultado.
- La skill `kbol` explica cómo consultar qué rige con estas órdenes.
- `kbol relevo`: la primera ruta de `cambios_locales` ya no pierde su primera letra.
- La CLI importa `jsonschema`, `markdown_it` y `urllib.request` solo al usarlos, lo que acorta el arranque.
- README en inglés (`README.md`) y en español (`README.es.md`), guía de primeros pasos (`docs/primeros-pasos.md`), `CONTRIBUTING.md`, plantillas de incidencias y de pull request, integración continua con `tools/comprobar.py --sin-di` y este registro.
- `kbol --version`.
- Sin el formato de un proyecto concreto: el formato heredado que se lee sin declarar otro es el formato heredado por defecto (`migracion.POR_DEFECTO`). El almacén de `tools/di`, sin `KBOL_REPOSITORIO`, pasa a `predeterminado`. Incompatible para quien importara la constante anterior del formato o usara el almacén sin esa variable.
- Licencia Apache-2.0 (`LICENSE`, `NOTICE` y `license` en `pyproject.toml`).
- Los registros de `tests/heredados/` son inventados.

## 0.11.0 · 16 nov 2026 (sin etiqueta)

Higiene de garantías.

- `kbol desvios --rama-canonica` señala en `commits_fuera_del_flujo` los commits de la rama canónica que cambian registros sin pasar por la puerta. Potencialmente incompatible.
- Un test cuenta en `kbol/` las órdenes de git que mueven referencias, para que la puerta siga siendo única.
- Las skills pasan a `kbol/skills/`, dentro del paquete, y `kbol exportar_skills DESTINO` las escribe con la versión instalada.
- `tools/comprobar.py` ejecuta los tests de `tools/di` (salvo con `--rapido` o `--sin-di`) y `desvios` contra `main`.
- El README se contrasta con el código y los registros por test.

## 0.10.0 · 12 nov 2026

- Una cita `lines-v1` con `representacion_id` se resuelve contra la representación en texto de un documento sin páginas (Word, hoja de cálculo, PowerPoint, HTML). Potencialmente incompatible.
- `kbol integridad` compara el `sha256` de cada fuente con sus bytes. Incompatible: deja de devolver `bloqueado`.
- `kbol enlaces` revisa enlaces internos y anclas de los Markdown del repositorio.
- Skill `kbol` para la continuidad de una tarea en cualquier repositorio con KBOL.
- `tools/di` lee Word, hojas, PowerPoint y HTML.

## 0.9.0 · 12 nov 2026

- `kbol sesion` (`inicio`, `parar`, `commit`), órdenes para los hooks de una instalación.
- `kbol proponer`, operador de integración: ensaya por defecto, integra con `--hasta integrar` y sube sin forzar con `--hasta subir`.

## 0.8.0 · 11 nov 2026

- Formato heredado configurable por instalación (`formato_heredado`). Potencialmente incompatible: `--instalacion` deja de ignorarse en las consultas y en `migrar`.

## 0.7.0 · 10 nov 2026

- `kbol vocabulario`: clases de entidad declaradas por decisiones que rigen; la puerta bloquea activar una entidad de una clase que no rige. Potencialmente incompatible.

## 0.6.0 · 10 nov 2026

- `kbol preparar_aprobacion`: paquete de aprobación de solo lectura con los digests que usa la puerta.

## 0.5.0 · 10 nov 2026

- `kbol soporte`: si rigen en un corte los apoyos de cada registro.
- `consultar` informa de la evidencia y las dependencias tratan la sucesora indecidible. Incompatible.

## 0.4.1 · 10 nov 2026

- Una operación que no examina nada termina `parcial` (código 3), no `completado`. Incompatible.
- Comprobación local única (`tools/comprobar.py`) y tests de política.

## 0.4.0 · 10 nov 2026

- Localizadores con perfil (`lines-v1`, `pdf-v1`, `norma-v1`) y resolutor de citas, `kbol citas`.
- `tools/di`, del piloto de Document Intelligence.

## 0.3.2 · 6 nov 2026

- El contexto, el impacto y los desvíos leen también los registros heredados.

## 0.3.1 · 6 nov 2026

- La guarda de importación acepta los valores interpretados del heredado, con escapes de YAML.

## 0.3.0 · 6 nov 2026

- Relevo por tarea (`kbol relevo`) y paquete de contexto (`kbol preparar_contexto`).
- `kbol verificar`: ejecuta las verificaciones que declara la instalación y las anota en el relevo.
- Raíz de confianza (`kbol arranque`) e `impacto` como consulta de solo lectura.
- Gobierno declarado para la primera instalación: verificador de aprobaciones declaradas (cita sin autenticar), arranque e integración declarados desde la CLI, aprobación solo de lo decisivo, importación de heredados con guarda, huellas y `kbol consultar` por ID o ancla.

## 0.2.0 · 4 nov 2026

- KBOL pasa a repositorio propio con el núcleo KB-DPP: esquema, eventos, estado reconstruido, digest, consolidación en dos cortes, dependencias, mutabilidad, autoridad, integración local con recibos, impacto y migración en seco.
