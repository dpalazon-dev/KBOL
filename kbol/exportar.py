"""Skills de KBOL empaquetadas con la CLI (`kbol exportar_skills`).

Las skills viven en `kbol/skills/<nombre>/SKILL.md`, como datos del paquete, para que la skill que use una instalación
describa la versión de la CLI que tiene instalada y no otra copiada a mano. La orden las escribe en un destino
(normalmente `.claude/skills` del repositorio) con una marca justo después de la cabecera que nombra la versión de KBOL.

Solo sobrescribe un archivo que lleve esa marca, es decir, que escribió esta orden. Si alguno de los destinos existe sin
ella, no escribe nada y termina bloqueada: una skill propia de la instalación no se pisa en silencio.
"""

from importlib import resources
from pathlib import Path

MARCA = "<!-- Exportada por kbol {version} con `kbol exportar_skills`. Se edita en kbol/skills/ de KBOL, no aquí. -->"
_PREFIJO = "<!-- Exportada por kbol "


def disponibles():
    """Nombres de las skills empaquetadas, ordenados."""
    raiz = resources.files("kbol").joinpath("skills")
    return sorted(d.name for d in raiz.iterdir() if d.is_dir() and d.joinpath("SKILL.md").is_file())


def exportada(nombre, version):
    """Texto de la skill tal como se exporta: la empaquetada con la marca de versión tras la cabecera YAML."""
    texto = resources.files("kbol").joinpath("skills", nombre, "SKILL.md").read_text(encoding="utf-8")
    lineas = texto.split("\n")
    if not lineas or lineas[0] != "---" or "---" not in lineas[1:]:
        raise ValueError(f"la skill {nombre} no empieza con una cabecera YAML delimitada por ---")
    cierre = lineas.index("---", 1)
    return "\n".join([*lineas[: cierre + 1], MARCA.format(version=version), *lineas[cierre + 1 :]])


def exportar(destino, version, nombres=None):
    """{estado, escritos, iguales, rechazados}: escribe las skills pedidas (todas si no se dan) bajo `destino`."""
    nombres = list(nombres) if nombres else disponibles()
    desconocidas = sorted(set(nombres) - set(disponibles()))
    if desconocidas:
        return {"estado": "bloqueado", "motivo": f"skills desconocidas: {desconocidas}", "disponibles": disponibles()}
    plan, iguales, rechazados = [], [], []
    for nombre in nombres:
        archivo = Path(destino) / nombre / "SKILL.md"
        texto = exportada(nombre, version)
        if archivo.is_file():
            actual = archivo.read_text(encoding="utf-8")
            if actual == texto:
                iguales.append(archivo.as_posix())
                continue
            if _PREFIJO not in actual:
                rechazados.append({"ruta": archivo.as_posix(), "motivo": "existe y no la escribió kbol exportar_skills"})
                continue
        plan.append((archivo, texto))
    if rechazados:
        return {"estado": "bloqueado", "escritos": [], "iguales": iguales, "rechazados": rechazados}
    for archivo, texto in plan:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8", newline="\n")
    return {"estado": "completado", "escritos": [a.as_posix() for a, _ in plan], "iguales": iguales, "rechazados": []}
