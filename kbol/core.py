"""Canonical container: UTF-8 file with a YAML header between `---` and a Markdown body.

Reading is safe and executes nothing: it rejects repeated keys, non-text keys, explicit tags, anchors, aliases and
merge keys. Dates are read as text: the schema decides their precision, not the parser.
Canonical writing validates before writing and rejects fields the schema does not declare.
"""

import os
import re
import tempfile
import uuid
from pathlib import Path

import yaml

from .model import PREFIX

_DELIMITED = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_MERGE = "tag:yaml.org,2002:merge"


class FormatError(ValueError):
    """Content that is not a readable canonical container."""


class _Loader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None) is not None:
            raise FormatError("anchors and aliases not admitted in the header")
        if getattr(event, "tag", None) is not None:
            raise FormatError(f"explicit tag not admitted: {event.tag}")
        return super().compose_node(parent, index)


def _map(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        if key_node.tag == _MERGE:
            raise FormatError("merge keys not admitted")
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise FormatError(f"non-text key: {key!r}")
        if key in result:
            raise FormatError(f"repeated key: {key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _map)
_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def parse(text):
    """Returns (header, body). The body is returned as is, not normalized."""
    m = _DELIMITED.match(text)
    if not m:
        raise FormatError("missing YAML header delimited by ---")
    try:
        data = yaml.load(m.group(1), Loader=_Loader)  # noqa: S506 - own safe loader
    except yaml.YAMLError as exc:
        raise FormatError(str(exc)) from exc
    if not isinstance(data, dict):
        raise FormatError("the header must be a mapping")
    return data, text[m.end() :]


def new_id(type_):
    """New ID with a type prefix and a UUID v4 (KB-DPP contract, "Identity")."""
    return f"{PREFIX[type_]}-{uuid.uuid4()}"


def normalize_body(body):
    return body.replace("\r\n", "\n").replace("\r", "\n")


def serialize(record, body, mode="proposal"):
    """Canonical text of a record valid in `mode` (`proposal` or `canonical`).

    FormatError if it does not validate or does not survive the round trip. Never admits undeclared fields.
    """
    from .schema import validate

    if mode not in ("proposal", "canonical"):
        raise ValueError("writing only admits the proposal and canonical modes")
    errors = [h for h in validate(record, body, mode=mode) if h["severity"] == "error"]
    if errors:
        raise FormatError("INVALID_SCHEMA: " + "; ".join(f"{h['path']}: {h['message']}" for h in errors))
    header = yaml.safe_dump(record, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10**9)
    text = f"---\n{header}---\n{normalize_body(body)}"
    reread, reread_body = parse(text)
    if reread != record or reread_body != normalize_body(body):
        raise FormatError("serialization does not preserve the content")
    return text


def write(path, record, body, mode="proposal"):
    """Writes the record atomically. Writing a file neither accepts nor integrates its content."""
    text = serialize(record, body, mode)
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
