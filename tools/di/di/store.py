"""Content-addressed store of originals and representations.

Each object lives at `<store>/sha256/<fingerprint>` and is never overwritten: another version is another object.
Next to it, `<store>/meta/<fingerprint>.json` records where it came from and when it was first captured. The
identity of the source is not the fingerprint: it is the `SRC-…` record that cites it; the store only guarantees
that the bytes are the ones it claims.
"""

import hashlib
import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

AGENT = "kbol-di/0.1 (+public regulation capture)"
# Local state the store uses when KBOL_REPOSITORY is not given.
DEFAULT_REPOSITORY = "default"
_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class IntegrityError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_origin(origin: str | Path) -> bytes:
    text = str(origin)
    if text.startswith(("https://", "http://")):
        request = urllib.request.Request(text, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(request, timeout=120) as resp:  # noqa: S310 - URL given by the operator
            return resp.read()
    return Path(origin).read_bytes()


def save(data: bytes, store: Path) -> tuple[str, Path]:
    """Writes the bytes in place if they were not there and checks the fingerprint on reread. Returns (fingerprint, path)."""
    fingerprint = hashlib.sha256(data).hexdigest()
    target = Path(store) / "sha256" / fingerprint
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != fingerprint:
            raise IntegrityError(f"the object {target} does not have the fingerprint of its name")
        return fingerprint, target
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != fingerprint:
        raise IntegrityError(f"rereading {target} does not match")
    return fingerprint, target


def capture(origin: str | Path, store: Path, media_type: str | None = None) -> dict:
    """Captures an original (URL or file). A retry with the same bytes returns the first capture."""
    data = _read_origin(origin)
    fingerprint, _ = save(data, store)
    meta_path = Path(store) / "meta" / f"{fingerprint}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if str(origin) not in meta["origins"]:
            meta["origins"].append(str(origin))
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return meta
    meta = {
        "sha256": fingerprint,
        "bytes": len(data),
        "path": f"sha256/{fingerprint}",
        "media_type": media_type,
        "origins": [str(origin)],
        "captured_at": _now(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def read(fingerprint: str, store: Path) -> bytes:
    path = Path(store) / "sha256" / fingerprint
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != fingerprint:
        raise IntegrityError(f"the object {path} does not have the fingerprint of its name")
    return data


def default_store() -> Path:
    """KBOL_STORE or the store in the installation's local state: `$KBOL_STATE/<repo>/store`.

    The repository is the name of the installation's local state (the `integration.repository` that
    `kbol propose` uses) and is given in KBOL_REPOSITORY. Without it, it is `DEFAULT_REPOSITORY`: the commands run
    from `tools/di`, not from the installation, so there is nowhere to infer it from.
    """
    if os.environ.get("KBOL_STORE"):
        return Path(os.environ["KBOL_STORE"])
    repository = os.environ.get("KBOL_REPOSITORY") or DEFAULT_REPOSITORY
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError(f"KBOL_REPOSITORY is not a folder name: {repository!r}")
    return Path(os.environ.get("KBOL_STATE") or Path.home() / ".kbol") / repository / "store"
