"""Muestra de calibración: lo que entró sin aprobación en el modo de solo lo decisivo.

Aprobar menos no debe ocultar errores. Esta herramienta lee los recibos de integración, reúne los registros que
entraron sin aprobación (modo `decisiva`, registros no decisivos) y escribe una hoja para revisarlos por muestra.
Solo lee: no registra nada, no cambia ningún recibo y no decide si algo estuvo bien.

    uv run python tools/calibracion/muestra.py ~/.kbol/<repo>/recibos [--tamano 10] [--desde INSTANTE] [--salida HOJA.md]

La muestra es determinista: ordena por el SHA-256 de `operacion_id` e ID, así que dos ejecuciones sobre los mismos
recibos dan la misma hoja y nadie elige a mano qué se revisa. Sale con 0 si hay muestra y con 3 si no hay nada que
muestrear, que no es lo mismo que «todo bien»: lo dice.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def candidatos(carpeta, desde=None):
    """(sin_aprobacion, recibos_leidos, ilegibles): registros que entraron sin aprobación, uno por recibo e ID."""
    sin_aprobacion, leidos, ilegibles = [], 0, []
    for ruta in sorted(Path(carpeta).glob("*.json")):
        try:
            recibo = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ilegibles.append(ruta.name)
            continue
        if not isinstance(recibo, dict) or recibo.get("estado") != "integrado":
            continue
        leidos += 1
        if recibo.get("modo_aprobacion") != "decisiva":
            continue
        if desde and str(recibo.get("registrado_en") or "") < desde:
            continue
        decisivos = set(recibo.get("decisivos") or [])
        for ident in recibo.get("registros") or []:
            if ident not in decisivos:
                sin_aprobacion.append(
                    {
                        "operacion_id": recibo.get("operacion_id"),
                        "id": ident,
                        "revision_integrada": recibo.get("revision_integrada"),
                        "registrado_en": recibo.get("registrado_en"),
                        "actor": recibo.get("actor"),
                    }
                )
    return sin_aprobacion, leidos, ilegibles


def muestra(sin_aprobacion, tamano):
    """Los `tamano` primeros por el SHA-256 de operación e ID: determinista y sin elección a mano."""

    def clave(c):
        return hashlib.sha256(f"{c['operacion_id']}\x00{c['id']}".encode()).hexdigest()

    return sorted(sin_aprobacion, key=clave)[:tamano]


def hoja(elegidos, total, leidos, ilegibles):
    lineas = [
        "# Muestra de calibración",
        "",
        f"Recibos de integración leídos: {leidos}. Registros que entraron sin aprobación: {total}. "
        f"En la muestra: {len(elegidos)}.",
    ]
    if ilegibles:
        lineas.append(f"Recibos ilegibles, no contados: {', '.join(ilegibles)}.")
    lineas += [
        "",
        "Para cada uno, comprobar algo concreto: ¿debió pedir aprobación?, ¿su contenido es correcto?",
        "",
        "| Operación | Registro | Revisión integrada | Registrado | Actor | ¿Debió escalarse? | Notas |",
        "|---|---|---|---|---|---|---|",
    ]
    lineas += [
        f"| {c['operacion_id']} | {c['id']} | {str(c['revision_integrada'])[:12]} | {c['registrado_en']} | "
        f"{c['actor']} |  |  |"
        for c in elegidos
    ]
    return "\n".join(lineas) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Muestra de calibración de lo que entró sin aprobación")
    p.add_argument("recibos", help="carpeta de recibos de la instalación")
    p.add_argument("--tamano", type=int, default=10)
    p.add_argument("--desde", help="solo recibos registrados desde este instante (ISO 8601, UTC)")
    p.add_argument("--salida", help="archivo donde escribir la hoja; por defecto, la salida estándar")
    args = p.parse_args(argv)
    if not Path(args.recibos).is_dir():
        print(f"No existe la carpeta de recibos: {args.recibos}", file=sys.stderr)
        return 1
    if args.tamano < 1:
        print("El tamaño de la muestra es un entero mayor que cero", file=sys.stderr)
        return 1
    sin_aprobacion, leidos, ilegibles = candidatos(args.recibos, args.desde)
    if not sin_aprobacion:
        print(
            f"Sin muestra: {leidos} recibos de integración leídos y ningún registro entró sin aprobación. "
            "No hay nada que calibrar; eso no dice que lo integrado esté bien.",
            file=sys.stderr,
        )
        return 3
    texto = hoja(muestra(sin_aprobacion, args.tamano), len(sin_aprobacion), leidos, ilegibles)
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8", newline="\n")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
