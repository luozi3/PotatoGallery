import importlib
import json
import os
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def seed_test_root(tmp_root: Path):
    static_src = PROJECT_ROOT / "static"
    shutil.copytree(static_src, tmp_root / "static", dirs_exist_ok=True)


def reload_modules():
    modules = {}
    for name in ["app.config", "app.static_site"]:
        modules[name] = importlib.reload(importlib.import_module(name))
    return modules


def setup_env(tmp_path: Path):
    os.environ["GALLERY_ROOT"] = str(tmp_path)
    return reload_modules()


def test_site_local_config_overrides(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    static_site = modules["app.static_site"]

    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "site.json").write_text(
        json.dumps(
            {
                "site_name": "Base Gallery",
                "brand_tagline": "Base Tagline",
                "counter": {"enabled": False, "img_url": ""},
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "site.local.json").write_text(
        json.dumps(
            {
                "site_name": "Local Gallery",
                "counter": {"enabled": True, "img_url": "https://example.com/c.png"},
            }
        ),
        encoding="utf-8",
    )

    site = static_site.load_site_config()
    assert site["site_name"] == "Local Gallery"
    assert site["brand_name"] == "Local Gallery"
    assert site["brand_tagline"] == "Base Tagline"
    assert site["counter"]["enabled"] is True


def test_upload_config_overrides(tmp_path):
    seed_test_root(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "upload.json").write_text(
        json.dumps(
            {
                "max_upload_mb": 5,
                "chunk_size_kb": 256,
                "max_pixels": 12345,
                "allowed_mime": {"image/jpeg": ".jpg"},
                "enforce_mime": False,
                "enforce_extension": False,
            }
        ),
        encoding="utf-8",
    )

    modules = setup_env(tmp_path)
    config = modules["app.config"]

    assert config.MAX_UPLOAD_BYTES == 5 * 1024 * 1024
    assert config.CHUNK_SIZE == 256 * 1024
    assert config.MAX_PIXELS == 12345
    assert config.ALLOWED_MIME == {"image/jpeg": ".jpg"}
    assert config.ENFORCE_MIME is False
    assert config.ENFORCE_EXTENSION is False


def test_static_site_reload_auth_config(tmp_path):
    seed_test_root(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    auth_cfg = config_dir / "auth.json"
    auth_cfg.write_text(json.dumps({"registration_mode": "closed"}), encoding="utf-8")

    modules = setup_env(tmp_path)
    static_site = modules["app.static_site"]

    auth_cfg.write_text(json.dumps({"registration_mode": "open"}), encoding="utf-8")
    staging_dir = static_site.build_site([])
    index_html = (staging_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="/auth/register/"' in index_html
