import hashlib
from pathlib import Path

import pytest
from di.store import IntegrityError, capture, default_store, read


def test_capture_is_idempotent(tmp_path):
    origin = tmp_path / "norm.pdf"
    origin.write_bytes(b"%PDF original")
    store = tmp_path / "store"
    first = capture(origin, store, media_type="application/pdf")
    second = capture(origin, store, media_type="application/pdf")
    assert first == second
    assert first["sha256"] == hashlib.sha256(b"%PDF original").hexdigest()
    assert read(first["sha256"], store) == b"%PDF original"


def test_another_origin_with_the_same_bytes_is_recorded(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    store = tmp_path / "store"
    capture(a, store)
    meta = capture(b, store)
    assert meta["origins"] == [str(a), str(b)]


def test_an_altered_object_is_detected(tmp_path):
    origin = tmp_path / "n.pdf"
    origin.write_bytes(b"good bytes")
    store = tmp_path / "store"
    meta = capture(origin, store)
    (store / meta["path"]).write_bytes(b"bad bytes")
    with pytest.raises(IntegrityError):
        read(meta["sha256"], store)
    with pytest.raises(IntegrityError):
        capture(origin, store)


def test_default_store_in_the_local_state(tmp_path, monkeypatch):
    monkeypatch.delenv("KBOL_STORE", raising=False)
    monkeypatch.delenv("KBOL_REPOSITORY", raising=False)
    monkeypatch.setenv("KBOL_STATE", str(tmp_path))
    assert default_store() == tmp_path / "default" / "store"
    monkeypatch.delenv("KBOL_STATE")
    assert default_store() == Path.home() / ".kbol" / "default" / "store"
    monkeypatch.setenv("KBOL_STORE", str(tmp_path / "other"))
    assert default_store() == tmp_path / "other"


def test_store_of_another_installation_by_its_repository(tmp_path, monkeypatch):
    monkeypatch.delenv("KBOL_STORE", raising=False)
    monkeypatch.setenv("KBOL_STATE", str(tmp_path))
    monkeypatch.setenv("KBOL_REPOSITORY", "other-project")
    assert default_store() == tmp_path / "other-project" / "store"
    monkeypatch.setenv("KBOL_REPOSITORY", "../outside")
    with pytest.raises(ValueError, match="KBOL_REPOSITORY"):
        default_store()
