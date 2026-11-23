"""Guard of the import of a legacy record: translate the format without adding content or meaning.

An import is correct if the proposed record says the same as its legacy counterpart in the base and nothing more:

- the body is the legacy one, the same words in the same order, except for the clause marks that wrap it and a final
  "Legacy provenance" section, which is regenerated from its fields and has to match ignoring whitespace (only its
  origin line and a YAML block with fields of the legacy record and their same value);
- if it also keeps the lines of the legacy record, the marks only fall between lines; if it redistributes them
  (`redistributes`), a mark can split a sentence and change what is in force in each clause, so whoever integrates
  treats it as decisive;
- the title, the description and the scope are those of the legacy record;
- no text of the record is new: each string appears in the legacy file or is one of the fixed texts of the migration
  ("not extracted…", "not recorded…", the scope of the tasks); the IDs of the relations too, except the milestones
  of a plan, which are its own.

It does not judge whether the translation is the best one: whoever does the migration reviews that. It prevents
content from slipping in.
"""

import re

import yaml

from .core import FormatError, parse

NOT_EXTRACTED = "not extracted"
NOT_RECORDED = "not recorded in the legacy record"
TASK_SCOPE = "the tasks in the body"
PROVENANCE_TITLE = "## Legacy provenance"
# Fields not compared as text: identity and shape (the schema validates them), projections and the installation
# policy (authorizing role and owner), which the migration assigns and the person approves.
NO_TEXT = frozenset({"id", "type", "class", "state", "author", "events", "sources", "authorized_by", "owner", "title"})
NO_TEXT |= {"description", "scope"}  # compared separately, with the legacy record
# Closed-vocabulary values or local identifiers: they are not content.
CLOSED = frozenset({"subtype", "method", "type", "condition", "criterion_id", "check_id", "precision"})
_MARK = re.compile(r'^\s*(<clause id="[^"]+">|</clause>)\s*$')
_PROVENANCE = re.compile(r"^## Legacy provenance\s*$", re.MULTILINE)


def provenance_section(path, fields):
    """The exact "Legacy provenance" section for those fields of the legacy record; used by the migrator and the guard."""
    text = f"{PROVENANCE_TITLE}\n\nImported from `{path}`."
    if fields:
        block = yaml.safe_dump(fields, allow_unicode=True, sort_keys=True, default_flow_style=False, width=10**6)
        text += f"\n\n```yaml\n{block}```"
    return text + "\n"


def _normal(text):
    """The text regardless of whitespace: the marks ask for blank lines around them and a split may redistribute
    line breaks, but no word changes."""
    return " ".join(text.split())


def _lines(text):
    return [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n") if line.strip()]


def redistributes(body, legacy_text):
    """True if the imported body has the words of the legacy record but not its lines: a mark splits a line."""
    try:
        _, legacy_body = parse(legacy_text)
    except FormatError:
        return True
    before, _ = _parts(body)
    unmarked = [line for line in before.split("\n") if not _MARK.match(line)]
    return _lines("\n".join(unmarked)) != _lines(legacy_body)


def _parts(body):
    m = _PROVENANCE.search(body)
    return (body[: m.start()], body[m.start() :]) if m else (body, None)


def _without_marks(text):
    return _normal("\n".join(line for line in text.split("\n") if not _MARK.match(line)))


def _provenance(section, path, meta):
    """None if the section is exactly the one regenerated from its fields; otherwise, the reason."""
    lines = section.replace("\r\n", "\n").rstrip("\n").split("\n")
    fields = {}
    if "```yaml" in lines:
        i = lines.index("```yaml")
        if lines.count("```yaml") != 1 or lines[-1] != "```" or lines.count("```") != 1:
            return "the YAML block of the provenance does not have the expected shape"
        try:
            fields = yaml.safe_load("\n".join(lines[i + 1 : -1]))
        except yaml.YAMLError:
            return "the YAML block of the provenance is unreadable"
        if not isinstance(fields, dict):
            return "the YAML block of the provenance is not a map of fields"
    for k, v in fields.items():
        if k not in meta or meta[k] != v:
            return f"the provenance states {k!r} with a value the legacy record does not have"
    if _normal(section) != _normal(provenance_section(path, fields)):
        return "the provenance carries text that is neither its origin line nor its fields"
    return None


def _chains(value, key=None):
    if isinstance(value, str):
        yield key, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _chains(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from _chains(v, key)


def _fixed(text):
    return text.startswith((NOT_EXTRACTED, NOT_RECORDED)) or text == TASK_SCOPE


def check(record, body, legacy_text, path):
    """List of reasons why the import is not a faithful translation; empty if it is."""
    try:
        meta, legacy_body = parse(legacy_text)
    except FormatError as exc:
        return [f"the legacy record in the base is unreadable: {exc}"]
    reasons = []
    if record.get("title") != meta.get("title"):
        reasons.append("the import changes title")
    if record.get("description") != meta.get("description", meta.get("title")):
        reasons.append("the import changes description")
    if "scope" in meta and record.get("scope") != meta["scope"]:
        reasons.append("the import changes scope")
    before, section = _parts(body)
    if _without_marks(before) != _normal(legacy_body):
        reasons.append("the imported body is not the legacy one except for the clause marks")
    if section is not None:
        reason = _provenance(section, path, meta)
        if reason:
            reasons.append(reason)
    own = record.get("id", "")
    # The values of the legacy record already interpreted: a YAML double-quoted text carries escapes (\") that do
    # not appear as such in the file, but it is content of the legacy record.
    values = {text for _, text in _chains(meta)}
    for key, text in _chains({k: v for k, v in record.items() if k not in NO_TEXT}):
        if key in CLOSED or not text or _fixed(text):
            continue
        if key == "milestones" and re.fullmatch(rf"{re.escape(own)}-H\d+", text):
            continue
        if text.startswith(f"{own}#"):
            continue  # a clause of the record itself (the `by` of an amendment)
        if text not in values and text.split("#", 1)[0] not in legacy_text:
            reasons.append(f"{key}: {text[:60]!r} is not in the legacy record: the import adds no content")
    return reasons
