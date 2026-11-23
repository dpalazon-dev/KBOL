"""Records the README demo GIF from real KBOL output, drawn frame by frame with Pillow.

    uv run --with pillow python tools/demo_gif.py [--output docs/demo.gif]

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

ROOT = Path(__file__).resolve().parent.parent
DEC = "DEC-33333333-3333-4333-8333-333333333333"

# Drawn at twice the display size, so it stays sharp on high-density screens.
S = 2
WIDTH, HEIGHT, MARGIN, COLUMNS, ROWS = 1180 * S, 700 * S, 26 * S, 96, 24
BAR_HEIGHT = 34 * S
BACKGROUND, TEXT, PROMPT, COMMENT, BAR = "#1e1e2e", "#cdd6f4", "#a6e3a1", "#7f849c", "#313244"
LABEL = {"[APPROVED]": "#a6e3a1", "[CANDIDATE": "#f9e2af", "blocked": "#f38ba8"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def font():
    for path in ("C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                 "/System/Library/Fonts/Menlo.ttc"):
        if Path(path).exists():
            return ImageFont.truetype(path, 17 * S)
    return ImageFont.load_default()


class Terminal:
    def __init__(self):
        self.lines = []  # (text, color)
        self.frames, self.durations = [], []
        self.font = font()
        self.line_height = int(self.font.size * 1.45)

    def _draw(self, cursor=False):
        img = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, WIDTH, BAR_HEIGHT], fill=BAR)
        for i, color in enumerate(("#f38ba8", "#f9e2af", "#a6e3a1")):
            d.ellipse([(16 + i * 22) * S, 11 * S, (28 + i * 22) * S, 23 * S], fill=color)
        d.text((WIDTH // 2 - 60 * S, 9 * S), "kbol demo", font=self.font, fill=COMMENT)
        visible = self.lines[-ROWS:]
        for n, (text, color) in enumerate(visible):
            y = BAR_HEIGHT + MARGIN // 2 + n * self.line_height
            d.text((MARGIN, y), text, font=self.font, fill=color)
            if cursor and n == len(visible) - 1:
                x = MARGIN + d.textlength(text, font=self.font)
                d.rectangle([x + 2 * S, y + 2 * S, x + 11 * S, y + self.font.size + 2 * S], fill=TEXT)
        return img

    def snap(self, ms, cursor=False):
        self.frames.append(self._draw(cursor))
        self.durations.append(ms)

    def write(self, command, comment=False, continuation=False):
        prefix = "" if comment else ("> " if continuation else "$ ")
        color = COMMENT if comment else TEXT
        self.lines.append((prefix, PROMPT))
        for i in range(0, len(command) + 1, 3):
            self.lines[-1] = (prefix + command[:i], color if comment else TEXT)
            self.snap(45, cursor=True)
        self.lines[-1] = (prefix + command, color)
        self.snap(350 if comment else 500)

    def output(self, text, pause):
        for line in text.rstrip("\n").splitlines() or [""]:
            for chunk in textwrap.wrap(line, COLUMNS, subsequent_indent="    ") or [""]:
                color = next((c for k, c in LABEL.items() if chunk.lstrip().startswith(k)), TEXT)
                self.lines.append((chunk, color))
        self.lines.append(("", TEXT))
        self.snap(pause)

    def clear(self):
        self.lines = []
        self.snap(200)


def run(args, cwd, env):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=str(ROOT / "docs" / "demo.gif"))
    args = ap.parse_args(argv)
    bash = shutil.which("bash")
    if os.name == "nt" and Path("C:/Program Files/Git/bin/bash.exe").exists():
        bash = "C:/Program Files/Git/bin/bash.exe"  # not WSL's bash
    kbol = ["uv", "run", "-q", "--project", str(ROOT), "kbol"]
    with tempfile.TemporaryDirectory() as tmp:
        demo = Path(tmp) / "kbol-demo"
        env = {**os.environ, "KBOL": " ".join(kbol).replace(str(ROOT), ROOT.as_posix())}
        subprocess.run([bash, (ROOT / "examples" / "quickstart.sh").as_posix(), demo.as_posix()], env=env,
                       check=True, capture_output=True)
        project = demo / "myproject"
        env = {**os.environ, "KBOL_STATE": str(demo / ".state")}
        subprocess.run(["git", "switch", "-q", "-c", "change"], cwd=project, check=True)
        t = Terminal()
        t.snap(400)

        t.write("# A project with one decision, approved and integrated through KBOL's gate.", comment=True)
        t.write(f"DEC={DEC}")
        t.write("# What is in force today, and who approved it?", comment=True)
        t.write("kbol query . --folder kb --ids $DEC --valid-at $(date -u +%FT%TZ) --plain")
        t.output(run([*kbol, "query", ".", "--folder", "kb", "--ids", DEC, "--valid-at", now(), "--plain"],
                     project, env), 4200)

        t.write("# No ID at hand? Search by text.", comment=True)
        t.write('kbol search . --folder kb --query "database" --valid-at $(date -u +%FT%TZ) --plain')
        t.output(run([*kbol, "search", ".", "--folder", "kb", "--query", "database", "--valid-at",
                      now(), "--plain"], project, env), 4200)

        t.clear()
        t.write("# Someone rewrites the accepted decision by hand...", comment=True)
        t.write("sed -i 's/PostgreSQL 16/SQLite 3/' kb/$DEC.md")
        path = project / "kb" / f"{DEC}.md"
        path.write_text(path.read_text(encoding="utf-8").replace("PostgreSQL 16", "SQLite 3"), encoding="utf-8")
        t.snap(400)
        t.write("# ...and tries to integrate it through the gate:", comment=True)
        t.write("kbol propose . --installation kbol.json --operation-id change --files kb/$DEC.md \\")
        t.write("  | jq -r '.result | .state, .reason, .findings[].message'", continuation=True)
        envelope = json.loads(run([*kbol, "propose", ".", "--installation", "kbol.json", "--operation-id",
                                   "change", "--files", f"kb/{DEC}.md"], project, env))
        r = envelope["result"]
        t.output("\n".join([r["state"], r.get("reason", ""), *(h["message"] for h in r.get("findings", []))]),
                 1500)
        t.write("# Closed clauses are never rewritten: a new decision has to amend them.", comment=True)
        t.snap(5000)

    output = Path(args.output)
    palette = [f.quantize(colors=64, method=Image.Quantize.MEDIANCUT) for f in t.frames]
    palette[0].save(output, save_all=True, append_images=palette[1:], duration=t.durations, loop=0, optimize=True,
                    disposal=1)
    print(f"{output}: {len(palette)} frames, {sum(t.durations) / 1000:.1f} s, {output.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
