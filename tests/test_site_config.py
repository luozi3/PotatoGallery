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
