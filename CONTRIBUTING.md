# Cómo contribuir a KBOL

KBOL lo mantiene una sola persona y su prioridad es que lo que afirma sea cierto. Antes de proponer una capacidad nueva, abre una incidencia de propuesta para discutirla. Los errores y las mejoras de lo que ya existe son bienvenidos directamente.

## Entorno

Hace falta [uv](https://docs.astral.sh/uv/) y git. uv instala los Python que pida la comprobación.

```bash
git clone https://github.com/dpalazon-dev/KBOL.git
cd KBOL
uv sync
uv run kbol --help
```

## Comprobación local

Todo cambio pasa esta comprobación antes de proponerse:

```bash
uv run python tools/comprobar.py
```

Ejecuta, en orden y parando en el primer fallo, `ruff` sobre `kbol`, `tests` y las herramientas; la suite en Python 3.10 y 3.14; y los tests de `tools/di` (con Docling, la parte lenta). Con `--sin-di` se salta `tools/di`; con `--rapido`, además, la suite corre una sola vez. `uv run python tools/comprobar.py --instalar-hook` deja la pasada rápida como hook `pre-push` de tu copia.

La integración continua (`.github/workflows/comprobar.yml`) ejecuta la misma orden con `--sin-di`. Un verde en local solo acredita tu máquina; el de la integración continua, Linux con las versiones que resolvió uv.

Reglas que la suite hace cumplir y conviene conocer antes de tocar documentación:

- Hay dos README con el mismo contenido: `README.md`, en inglés, y `README.es.md`, en español. Un cambio en uno va también al otro.
- La tabla de módulos de cada README lista exactamente los módulos de `kbol/`, y su sección de uso, exactamente las órdenes habilitadas.
- Toda ruta del repositorio citada entre comillas invertidas en los README o en `docs/elecciones.md` tiene que existir.
- Un README no afirma una capacidad que el código no tenga. Si una función no está acabada, va en sus limitaciones («Qué no hace todavía», «Limitations»).

## Commits

Commits pequeños, cada uno con la comprobación pasando. El mensaje sigue la forma `tipo(ámbito): qué cambia`, en español y en presente, con `feat`, `fix`, `docs`, `chore`, `test` o `refactor`; por ejemplo, `fix(citas): una cita sin contexto no se da por resuelta`. Si el cambio es incompatible para quien consume la CLI, añade su nota en [`docs/cambios.md`](docs/cambios.md) con la plantilla de ese archivo y una entrada en [CHANGELOG.md](CHANGELOG.md).

## Pull requests

El código y la documentación entran por pull request contra `main`. El mantenedor lo revisa, repite la comprobación y lo fusiona.

## Licencia de las contribuciones

KBOL se distribuye bajo Apache-2.0. Lo que contribuyas entra con esa misma licencia (cláusula 5), sin acuerdo aparte.

## Incidencias

Usa las plantillas: error o propuesta. En un error, incluye la orden exacta, la versión (`pyproject.toml` o `kbol.__version__`) y el sobre JSON de la salida, que dice qué no evaluó la orden.
