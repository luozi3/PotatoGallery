import errno
from pathlib import Path
from types import SimpleNamespace

from test_pipeline import seed_test_root, setup_env


def test_check_storage_devices_warns_on_cross_device(tmp_path, monkeypatch):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    storage = modules["app.storage"]
    config = modules["app.config"]
    storage.ensure_dirs()

    base = config.STORAGE
    other = config.WWW_DIR
    base_resolved = str(base.resolve(strict=False))
    other_resolved = str(other.resolve(strict=False))

    def fake_stat(self: Path):
        path_str = str(self)
        if path_str == base_resolved:
            return SimpleNamespace(st_dev=100)
        if path_str == other_resolved:
            return SimpleNamespace(st_dev=200)
        return SimpleNamespace(st_dev=100)

    monkeypatch.setattr(Path, "stat", fake_stat, raising=False)

    messages = storage.check_storage_devices(base=base, paths=[other])
    assert messages
    assert "跨分区" in messages[0]


def test_replace_path_cross_device_file(tmp_path, monkeypatch):
    modules = setup_env(tmp_path)
    storage = modules["app.storage"]
    config = modules["app.config"]
    storage.ensure_dirs()

    src = config.UPLOAD_TMP / "sample.bin"
    dest = config.RAW_DIR / "sample.bin"
    src.write_bytes(b"hello")

    real_replace = storage.os.replace

    def fake_replace(src_path, dest_path):
        if Path(src_path) == src and Path(dest_path) == dest:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return real_replace(src_path, dest_path)

    monkeypatch.setattr(storage.os, "replace", fake_replace)

    storage.replace_path(src, dest)
    assert dest.read_bytes() == b"hello"
    assert not src.exists()


def test_replace_path_cross_device_dir(tmp_path, monkeypatch):
    modules = setup_env(tmp_path)
    storage = modules["app.storage"]
    config = modules["app.config"]
    storage.ensure_dirs()

    src_dir = config.WWW_STAGING / "build_test"
    src_dir.mkdir(parents=True)
    (src_dir / "index.html").write_text("ok", encoding="utf-8")
    dest_dir = config.WWW_DIR

    real_replace = storage.os.replace

    def fake_replace(src_path, dest_path):
        if Path(src_path) == src_dir and Path(dest_path) == dest_dir:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return real_replace(src_path, dest_path)

    monkeypatch.setattr(storage.os, "replace", fake_replace)

    storage.replace_path(src_dir, dest_dir)
    assert (dest_dir / "index.html").read_text(encoding="utf-8") == "ok"
    assert not src_dir.exists()
