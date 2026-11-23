"""Records the README demo GIF from real KBOL output, drawn frame by frame with Pillow.

    uv run --with pillow python tools/demo_gif.py [--salida docs/demo.gif]

It builds the quick-start project in a temporary folder (examples/quickstart.sh), runs each command of the scenes
below for real and draws a terminal that types the command and prints its actual output. Needs bash, git and uv.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
DEC = "DEC-33333333-3333-4333-8333-333333333333"

ANCHO, ALTO, MARGEN, COLUMNAS, FILAS = 1180, 700, 26, 96, 24
FONDO, TEXTO, PROMPT, COMENTARIO, BARRA = "#1e1e2e", "#cdd6f4", "#a6e3a1", "#7f849c", "#313244"
ETIQUETA = {"[APROBADA]": "#a6e3a1", "[CANDIDATO": "#f9e2af", "bloqueado": "#f38ba8"}


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fuente():
    for ruta in ("C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                 "/System/Library/Fonts/Menlo.ttc"):
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, 17)
    return ImageFont.load_default()


class Terminal:
    def __init__(self):
        self.lineas = []  # (texto, color)
        self.fotogramas, self.duraciones = [], []
        self.fuente = fuente()
        self.alto_linea = int(self.fuente.size * 1.45)

    def _dibujar(self, cursor=False):
        img = Image.new("RGB", (ANCHO, ALTO), FONDO)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, ANCHO, 34], fill=BARRA)
        for i, color in enumerate(("#f38ba8", "#f9e2af", "#a6e3a1")):
            d.ellipse([16 + i * 22, 11, 28 + i * 22, 23], fill=color)
        d.text((ANCHO // 2 - 60, 9), "kbol demo", font=self.fuente, fill=COMENTARIO)
        visibles = self.lineas[-FILAS:]
        for n, (texto, color) in enumerate(visibles):
            y = 34 + MARGEN // 2 + n * self.alto_linea
            d.text((MARGEN, y), texto, font=self.fuente, fill=color)
            if cursor and n == len(visibles) - 1:
                x = MARGEN + d.textlength(texto, font=self.fuente)
                d.rectangle([x + 2, y + 2, x + 11, y + self.fuente.size + 2], fill=TEXTO)
        return img

    def foto(self, ms, cursor=False):
        self.fotogramas.append(self._dibujar(cursor))
        self.duraciones.append(ms)

    def escribir(self, orden, comentario=False, continuacion=False):
        prefijo = "" if comentario else ("> " if continuacion else "$ ")
        color = COMENTARIO if comentario else TEXTO
        self.lineas.append((prefijo, PROMPT))
        for i in range(0, len(orden) + 1, 3):
            self.lineas[-1] = (prefijo + orden[:i], color if comentario else TEXTO)
            self.foto(45, cursor=True)
        self.lineas[-1] = (prefijo + orden, color)
        self.foto(350 if comentario else 500)

    def salida(self, texto, pausa):
        for linea in texto.rstrip("\n").splitlines() or [""]:
            for trozo in textwrap.wrap(linea, COLUMNAS, subsequent_indent="    ") or [""]:
                color = next((c for k, c in ETIQUETA.items() if trozo.lstrip().startswith(k)), TEXTO)
                self.lineas.append((trozo, color))
        self.lineas.append(("", TEXTO))
        self.foto(pausa)

    def limpiar(self):
        self.lineas = []
        self.foto(200)


def ejecutar(args, cwd, env):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=str(RAIZ / "docs" / "demo.gif"))
    args = ap.parse_args(argv)
    bash = shutil.which("bash")
    if os.name == "nt" and Path("C:/Program Files/Git/bin/bash.exe").exists():
        bash = "C:/Program Files/Git/bin/bash.exe"  # no el bash de WSL
    kbol = ["uv", "run", "-q", "--project", str(RAIZ), "kbol"]
    with tempfile.TemporaryDirectory() as tmp:
        demo = Path(tmp) / "kbol-demo"
        env = {**os.environ, "KBOL": " ".join(kbol).replace(str(RAIZ), RAIZ.as_posix())}
        subprocess.run([bash, (RAIZ / "examples" / "quickstart.sh").as_posix(), demo.as_posix()], env=env,
                       check=True, capture_output=True)
        proyecto = demo / "miproyecto"
        env = {**os.environ, "KBOL_ESTADO": str(demo / ".estado")}
        subprocess.run(["git", "switch", "-q", "-c", "cambio"], cwd=proyecto, check=True)
        t = Terminal()
        t.foto(400)

        t.escribir("# A project with one decision, approved and integrated through KBOL's gate.", comentario=True)
        t.escribir(f"DEC={DEC}")
        t.escribir("# What is in force today, and who approved it?", comentario=True)
        t.escribir("kbol consultar . --carpeta kb --ids $DEC --valido-en $(date -u +%FT%TZ) --llano")
        t.salida(ejecutar([*kbol, "consultar", ".", "--carpeta", "kb", "--ids", DEC, "--valido-en", ahora(), "--llano"],
                          proyecto, env), 4200)

        t.escribir("# No ID at hand? Search by text.", comentario=True)
        t.escribir('kbol buscar . --carpeta kb --consulta "base de datos" --valido-en $(date -u +%FT%TZ) --llano')
        t.salida(ejecutar([*kbol, "buscar", ".", "--carpeta", "kb", "--consulta", "base de datos", "--valido-en",
                           ahora(), "--llano"], proyecto, env), 4200)

        t.limpiar()
        t.escribir("# Someone rewrites the accepted decision by hand...", comentario=True)
        t.escribir("sed -i 's/PostgreSQL 16/SQLite 3/' kb/$DEC.md")
        ruta = proyecto / "kb" / f"{DEC}.md"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace("PostgreSQL 16", "SQLite 3"), encoding="utf-8")
        t.foto(400)
        t.escribir("# ...and tries to integrate it through the gate:", comentario=True)
        t.escribir("kbol proponer . --instalacion instalacion.json --operacion-id cambio --archivos kb/$DEC.md \\")
        t.escribir("  | jq -r '.resultado | .estado, .motivo, .hallazgos[].mensaje'", continuacion=True)
        sobre = json.loads(ejecutar([*kbol, "proponer", ".", "--instalacion", "instalacion.json", "--operacion-id",
                                     "cambio", "--archivos", f"kb/{DEC}.md"], proyecto, env))
        r = sobre["resultado"]
        t.salida("\n".join([r["estado"],r.get("motivo", ""), *(h["mensaje"] for h in r.get("hallazgos", []))]),
                 1500)
        t.escribir("# Closed clauses are never rewritten: a new decision has to amend them.", comentario=True)
        t.foto(5000)

    salida = Path(args.salida)
    paleta = [f.quantize(colors=64, method=Image.Quantize.MEDIANCUT) for f in t.fotogramas]
    paleta[0].save(salida, save_all=True, append_images=paleta[1:], duration=t.duraciones, loop=0, optimize=True,
                   disposal=1)
    print(f"{salida}: {len(paleta)} fotogramas, {sum(t.duraciones) / 1000:.1f} s, {salida.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
