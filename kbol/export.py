"""KBOL skills packaged with the CLI (`kbol export_skills`).

The skills live in `kbol/skills/<name>/SKILL.md`, as package data, so that the skill an installation uses describes
the CLI version it has installed and not another copied by hand. The command writes them to a target (usually
`.claude/skills` of the repository) with a mark right after the header that names the KBOL version.

It only overwrites a file that carries that mark, that is, one this command wrote. If any of the targets exists
without it, it writes nothing and ends blocked: a skill of the installation's own is not overwritten silently.
"""

from importlib import resources
from pathlib import Path

MARK = "<!-- Exported by kbol {version} with `kbol export_skills`. Edit it in kbol/skills/ of KBOL, not here. -->"
# The mark KBOL 0.12 and earlier wrote: an export from those versions is still recognized as one and replaced.
_PREFIXES = ("<!-- Exported by kbol ", "<!-- Exportada por kbol ")


def available():
    """Names of the packaged skills, sorted."""
    root = resources.files("kbol").joinpath("skills")
    return sorted(d.name for d in root.iterdir() if d.is_dir() and d.joinpath("SKILL.md").is_file())


def exported(name, version):
    """Text of the skill as exported: the packaged one with the version mark after the YAML header."""
    text = resources.files("kbol").joinpath("skills", name, "SKILL.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError(f"skill {name} does not start with a YAML header delimited by ---")
    closing = lines.index("---", 1)
    return "\n".join([*lines[: closing + 1], MARK.format(version=version), *lines[closing + 1 :]])


def export(target, version, names=None):
    """{state, written, equal, rejected}: writes the requested skills (all if none given) under `target`."""
    names = list(names) if names else available()
    unknown = sorted(set(names) - set(available()))
    if unknown:
        return {"state": "blocked", "reason": f"unknown skills: {unknown}", "available": available()}
    plan, equal, rejected = [], [], []
    for name in names:
        archive = Path(target) / name / "SKILL.md"
        text = exported(name, version)
        if archive.is_file():
            current = archive.read_text(encoding="utf-8")
            if current == text:
                equal.append(archive.as_posix())
                continue
            if not any(prefix in current for prefix in _PREFIXES):
                rejected.append(
                    {"path": archive.as_posix(), "reason": "exists and was not written by kbol export_skills"}
                )
                continue
        plan.append((archive, text))
    if rejected:
        return {"state": "blocked", "written": [], "equal": equal, "rejected": rejected}
    for archive, text in plan:
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(text, encoding="utf-8", newline="\n")
    return {"state": "completed", "written": [a.as_posix() for a, _ in plan], "equal": equal, "rejected": []}
