import importlib
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def seed_test_root(tmp_root: Path):
    static_src = PROJECT_ROOT / "static"
    shutil.copytree(static_src, tmp_root / "static", dirs_exist_ok=True)
    local_site = tmp_root / "static" / "data" / "site.local.json"
    if local_site.exists():
        local_site.unlink()
    config_src = PROJECT_ROOT / "config" / "auth.json"
    if config_src.exists():
        config_dst = tmp_root / "config"
        config_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_src, config_dst / "auth.json")
    schema_src = PROJECT_ROOT / "db" / "schema.sql"
    schema_dst = tmp_root / "db" / "schema.sql"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(), encoding="utf-8")
    conn = sqlite3.connect(tmp_root / "db" / "gallery.db")
    conn.executescript(schema_dst.read_text())
    conn.commit()
    conn.close()


def reload_modules():
    modules = {}
    for name in [
        "app.config",
        "app.auth",
        "app.auth_api",
        "app.user_api",
        "app.storage",
        "app.db",
        "app.image_utils",
        "app.tagging",
        "app.static_site",
        "app.upload_service",
        "app.worker",
        "app.maintenance",
    ]:
        modules[name] = importlib.reload(importlib.import_module(name))
    return modules


def setup_env(tmp_path: Path):
    os.environ["GALLERY_ROOT"] = str(tmp_path)
    modules = reload_modules()
    return modules


def make_image(path: Path, size=(320, 200), color=(220, 180, 150)):
    img = Image.new("RGB", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def login_user(client, username: str, password: str):
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )


def test_upload_and_raw_write(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    app = upload_service.create_app()
    client = app.test_client()
    auth.create_user("alice", "secret123", groups=["user"])
    resp = login_user(client, "alice", "secret123")
    assert resp.status_code == 200

    img_path = tmp_path / "input.png"
    make_image(img_path)

    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={"file": (f, "input.png")},
            content_type="multipart/form-data",
            headers={"X-Forwarded-Proto": "https"},
            base_url="https://example.com",
        )

    assert resp.status_code == 201
    data = resp.get_json()
    raw_path = config.STORAGE / data["stored"]
    assert raw_path.exists()


def test_parse_tags_allows_spaces(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    tagging = modules["app.tagging"]

    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {
        "tags": [
            {"tag": "long hair", "slug": "long-hair"},
            {"tag": "blue eyes", "slug": "blue-eyes"},
        ]
    }
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")
    alias_map = tagging.build_alias_map(tagging.load_tags_config()[0])
    tags, err = tagging.parse_tags_input("#long hair #blue eyes", alias_map, require_known=True)
    assert err is None
    assert tags == ["long hair", "blue eyes"]


def test_parse_tags_requires_registry(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    tagging = modules["app.tagging"]
    tags, err = tagging.parse_tags_input("#ghost", {}, require_known=True)
    assert tags is None
    assert err


def test_normalize_tag_decodes_percent(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    tagging = modules["app.tagging"]

    assert tagging.normalize_tag("%25E5%2585%BD%25E8%2580%25B3") == "兽耳"


def test_upload_requires_login(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    app = upload_service.create_app()
    client = app.test_client()

    resp = client.post(
        "/api/upload",
        data={"title": "x"},
        content_type="multipart/form-data",
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )
    assert resp.status_code == 401


def test_upload_paused_flag(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    config.UPLOAD_PAUSE_FLAG.write_text("paused", encoding="utf-8")
    app = upload_service.create_app()
    client = app.test_client()
    auth.create_user("alice", "secret123", groups=["user"])
    resp = login_user(client, "alice", "secret123")
    assert resp.status_code == 200

    img_path = tmp_path / "paused.png"
    make_image(img_path)

    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={"file": (f, "paused.png")},
            content_type="multipart/form-data",
            headers={"X-Forwarded-Proto": "https"},
            base_url="https://example.com",
        )

    assert resp.status_code == 503
    data = resp.get_json()
    assert "上传已暂停" in data["error"]


def test_worker_process_and_publish(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    db = modules["app.db"]
    db = modules["app.db"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path, size=(400, 280))

    ok = worker.process_file(raw_path)
    assert ok

    # 处理完成但未发布
    index_html = config.WWW_DIR / "index.html"
    assert not index_html.exists()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT status, thumb_path FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["status"] == "processed"
    thumb_name = Path(row["thumb_path"]).name
    assert re.match(r"^L\d{8}A\d{3}\.webp$", thumb_name)

    published = worker.publish_ready_images()
    assert published

    thumb_path = config.THUMB_DIR / thumb_name
    assert thumb_path.exists()
    assert index_html.exists()
    assert (config.WWW_DIR / "sitemap.xml").exists()
    assert (config.WWW_DIR / "robots.txt").exists()
    assert (config.WWW_DIR / "auth" / "login" / "index.html").exists()
    assert (config.WWW_DIR / "auth" / "register" / "index.html").exists()

    sitemap_text = (config.WWW_DIR / "sitemap.xml").read_text(encoding="utf-8")
    assert "/flow.html" not in sitemap_text
    assert "/wall.html" not in sitemap_text
    assert not (config.WWW_DIR / "wall.html").exists()

    index_html_text = index_html.read_text()
    assert "onerror=\"this.onerror=null;this.src='/raw/" in index_html_text
    assert 'data-collection-tab' in index_html_text
    assert 'data-filter-pill' in index_html_text
    assert 'gallery.js' in index_html_text
    assert "gallery.css?v=" in index_html_text
    assert "gallery.js?v=" in index_html_text
    assert 'data-collection="favorites"' in index_html_text

    with db.connect() as conn:
        row = conn.execute(
            "SELECT status, thumb_width, thumb_height, dominant_color, thumb_path FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["status"] == "published"
    assert row["thumb_width"] and row["thumb_height"]
    html = index_html_text
    assert f"/thumb/{Path(row['thumb_path']).name}" in html
    assert "--thumb-ratio" in html
    css = (config.STATIC / "styles" / "gallery.css").read_text()
    assert "object-fit: contain" in css
    assert (config.WWW_DIR / "static" / "js" / "gallery.js").exists()


def test_small_image_keeps_thumbnail_ratio(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path, size=(120, 80))

    ok = worker.process_file(raw_path)
    assert ok

    assert worker.publish_ready_images()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT thumb_width, thumb_height, thumb_path FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["thumb_width"] == 120
    assert row["thumb_height"] == 80

    html = (config.WWW_DIR / "index.html").read_text()
    assert f"/thumb/{Path(row['thumb_path']).name}" in html


def test_collections_config_respected(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path, size=(360, 480))

    collections_cfg = {
        "collections": {
            "mine": {"title": "我的作品", "description": "自制", "uuids": [uid]},
            "favorites": {"title": "他人作品", "description": "精选", "uuids": []},
        },
        "default_collection": "favorites",
    }
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "collections.json").write_text(json.dumps(collections_cfg, ensure_ascii=False), encoding="utf-8")

    ok = worker.process_file(raw_path)
    assert ok
    assert worker.publish_ready_images()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, status, thumb_path FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["status"] == "published"
    assert re.match(r"^L\d{8}A\d{3}\.webp$", Path(row["thumb_path"]).name)

    index_html = (config.WWW_DIR / "index.html").read_text()
    assert 'data-collection="mine"' in index_html
    assert "我的作品" in index_html

    detail_html = (config.WWW_DIR / f"images/{row['id']}/index.html").read_text()
    assert "我的作品" in detail_html
    assert "/raw/" in detail_html
    assert "gallery.css?v=" in detail_html
    assert "竖屏" in detail_html
    assert "轻量" in detail_html


def test_detail_tag_tree_includes_parents(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)

    tags_cfg = {
        "types": [{"type": "general", "label": "普通", "color": "#7b8794"}],
        "tags": [
            {
                "tag": "parent",
                "intro": "",
                "aliases": [],
                "parents": [],
                "slug": "parent",
                "alias_to": "",
                "type": "general",
            },
            {
                "tag": "child",
                "intro": "",
                "aliases": [],
                "parents": ["parent"],
                "slug": "child",
                "alias_to": "",
                "type": "general",
            },
        ],
    }
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")

    assert worker.process_file(raw_path)
    with db.connect() as conn:
        conn.execute("UPDATE images SET tags_json=? WHERE uuid=?", (json.dumps(["child"]), uid))
        image_id = conn.execute("SELECT id FROM images WHERE uuid=?", (uid,)).fetchone()["id"]
    assert worker.publish_ready_images()

    detail_html = (config.WWW_DIR / f"images/{image_id}/index.html").read_text()
    assert "tag-flat-list" in detail_html
    assert "#child" in detail_html
    assert "#parent" in detail_html


def test_tag_page_tree_toggle_includes_relations(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)

    tags_cfg = {
        "types": [{"type": "general", "label": "普通", "color": "#7b8794"}],
        "tags": [
            {
                "tag": "parent",
                "intro": "",
                "aliases": [],
                "parents": [],
                "slug": "parent",
                "alias_to": "",
                "type": "general",
            },
            {
                "tag": "child",
                "intro": "",
                "aliases": [],
                "parents": ["parent"],
                "slug": "child",
                "alias_to": "",
                "type": "general",
            },
        ],
    }
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")

    assert worker.process_file(raw_path)
    with db.connect() as conn:
        conn.execute("UPDATE images SET tags_json=? WHERE uuid=?", (json.dumps(["child"]), uid))
        image_id = conn.execute("SELECT id FROM images WHERE uuid=?", (uid,)).fetchone()["id"]
    assert worker.publish_ready_images()

    tag_html = (config.WWW_DIR / "tags" / "child" / "index.html").read_text()
    assert "data-tag-tree-toggle" in tag_html
    assert "tag-tree" in tag_html
    assert "#child" in tag_html
    assert "#parent" in tag_html
    assert str(image_id) in tag_html


def test_detail_tag_tree_groups_by_type_order(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)

    tags_cfg = {
        "types": [
            {"type": "artist", "label": "画师", "color": "#f97316"},
            {"type": "general", "label": "普通", "color": "#7b8794"},
        ],
        "tags": [
            {
                "tag": "alice",
                "intro": "",
                "aliases": [],
                "parents": [],
                "slug": "alice",
                "alias_to": "",
                "type": "artist",
            },
            {
                "tag": "clouds",
                "intro": "",
                "aliases": [],
                "parents": [],
                "slug": "clouds",
                "alias_to": "",
                "type": "general",
            },
        ],
    }
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")

    assert worker.process_file(raw_path)
    with db.connect() as conn:
        conn.execute("UPDATE images SET tags_json=? WHERE uuid=?", (json.dumps(["alice", "clouds"]), uid))
        image_id = conn.execute("SELECT id FROM images WHERE uuid=?", (uid,)).fetchone()["id"]
    assert worker.publish_ready_images()

    detail_html = (config.WWW_DIR / f"images/{image_id}/index.html").read_text()
    artist_idx = detail_html.find("画师")
    general_idx = detail_html.find("普通")
    assert artist_idx != -1
    assert general_idx != -1
    assert artist_idx < general_idx
    assert "#alice" in detail_html
    assert "#clouds" in detail_html


def test_detail_uses_numeric_path_and_legacy_redirect(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path, size=(320, 240))

    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()

    with db.connect() as conn:
        image_id = conn.execute("SELECT id FROM images WHERE uuid=?", (uid,)).fetchone()["id"]

    detail_path = config.WWW_DIR / f"images/{image_id}/index.html"
    assert detail_path.exists()
    legacy_path = config.WWW_DIR / f"images/{uid}/index.html"
    assert 'http-equiv="refresh"' in legacy_path.read_text()


def test_static_change_triggers_rebuild(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()
    assert config.LAST_STATIC_MTIME.exists()
    last_mtime = float(config.LAST_STATIC_MTIME.read_text())

    css_path = config.STATIC / "styles" / "gallery.css"
    time.sleep(1)
    css_path.write_text(css_path.read_text() + "\n/*touch*/", encoding="utf-8")

    rebuilt = worker.ensure_static_up_to_date()
    assert rebuilt
    new_mtime = float(config.LAST_STATIC_MTIME.read_text())
    assert new_mtime > last_mtime
    deployed_css = (config.WWW_DIR / "static" / "styles" / "gallery.css").read_text()
    assert "touch" in deployed_css


def test_force_rebuild_flag_triggers_publish(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()
    before_mtime = float(config.LAST_STATIC_MTIME.read_text())

    config.FORCE_REBUILD_FLAG.write_text("1", encoding="utf-8")
    time.sleep(1)
    rebuilt = worker.ensure_static_up_to_date()
    assert rebuilt
    assert not config.FORCE_REBUILD_FLAG.exists()
    after_mtime = float(config.LAST_STATIC_MTIME.read_text())
    assert after_mtime >= before_mtime


def test_www_permissions_repaired(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    static_site = modules["app.static_site"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()

    static_dir = config.WWW_DIR / "static"
    styles_dir = static_dir / "styles"
    css_file = styles_dir / "gallery.css"
    # 模拟权限被意外收紧
    static_dir.chmod(0o700)
    styles_dir.chmod(0o700)
    css_file.chmod(0o600)
    assert (css_file.stat().st_mode & 0o777) == 0o600

    static_site.ensure_www_readable()

    assert (static_dir.stat().st_mode & 0o777) == 0o755
    assert (styles_dir.stat().st_mode & 0o777) == 0o755
    assert (css_file.stat().st_mode & 0o777) == 0o644


def test_status_snapshot_and_page(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()

    status_json = config.WWW_DIR / "static" / "status.json"
    assert status_json.exists()
    data = json.loads(status_json.read_text())
    assert "generated_at" in data
    assert "disk" in data and "free" in data["disk"]
    assert "load" in data and isinstance(data["load"].get("avg"), list)
    assert "memory" in data and "total" in data["memory"]
    assert data["images"]["published"] >= 1

    status_html = config.WWW_DIR / "status.html"
    assert status_html.exists()
    html_text = status_html.read_text()
    assert "/static/status.json" in html_text
    status_dir_index = config.WWW_DIR / "status" / "index.html"
    assert status_dir_index.exists()
    assert "/static/status.json" in status_dir_index.read_text()
    history_json = config.WWW_DIR / "static" / "status_history.json"
    assert history_json.exists()
    history = json.loads(history_json.read_text())
    assert isinstance(history, list) and history
    persist_status = config.STATUS_DATA_DIR / "status.json"
    persist_history = config.STATUS_DATA_DIR / "status_history.json"
    assert persist_status.exists()
    assert persist_history.exists()


def test_status_snapshot_marks_force_rebuild_on_sync_failure(tmp_path, monkeypatch):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()

    config.FORCE_REBUILD_FLAG.unlink(missing_ok=True)

    def deny_copy(*args, **kwargs):
        raise PermissionError("no write")

    monkeypatch.setattr(worker.shutil, "copy2", deny_copy)
    worker.write_status_snapshot()

    assert config.FORCE_REBUILD_FLAG.exists()


def test_upload_requires_https(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    app = upload_service.create_app()
    client = app.test_client()

    img_path = tmp_path / "rate.png"
    make_image(img_path)

    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={"file": (f, "rate.png")},
            content_type="multipart/form-data",
            base_url="http://example.com",
        )
    assert resp.status_code == 403


def test_upload_rejects_bad_content_type(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    app = upload_service.create_app()
    client = app.test_client()
    auth.create_user("alice", "secret123", groups=["user"])
    resp = login_user(client, "alice", "secret123")
    assert resp.status_code == 200

    img_path = tmp_path / "bad.png"
    make_image(img_path)

    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={"file": (f, "bad.png", "text/plain")},
            content_type="multipart/form-data",
            headers={"X-Forwarded-Proto": "https"},
            base_url="https://example.com",
        )
    assert resp.status_code == 400


def test_health_includes_metrics(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    upload_service = modules["app.upload_service"]

    app = upload_service.create_app()
    client = app.test_client()

    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "disk" in data and "free" in data["disk"]
    assert "queue" in data and "raw" in data["queue"]


def test_disk_guard_pause_and_resume(tmp_path, monkeypatch):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    db = modules["app.db"]

    storage.ensure_dirs()
    config.UPLOAD_PAUSE_FLAG.unlink(missing_ok=True)

    import importlib.util
    spec = importlib.util.spec_from_file_location("disk_guard", str(PROJECT_ROOT / "bin" / "disk_guard.py"))
    disk_guard = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(disk_guard)

    usage = shutil.disk_usage(tmp_path)

    def low(_):
        return usage._replace(free=config.DISK_LOW_WATERMARK_BYTES - 1)

    monkeypatch.setattr(disk_guard.shutil, "disk_usage", low)
    assert disk_guard.main() == 1
    assert config.UPLOAD_PAUSE_FLAG.exists()

    def high(_):
        return usage._replace(free=config.DISK_LOW_WATERMARK_BYTES + config.DISK_RESUME_DELTA_BYTES + 1)

    monkeypatch.setattr(disk_guard.shutil, "disk_usage", high)
    assert disk_guard.main() == 0
    assert not config.UPLOAD_PAUSE_FLAG.exists()

    with db.connect() as conn:
        events = [row["event"] for row in conn.execute("SELECT event FROM audit_log").fetchall()]
    assert "disk_guard_pause" in events
    assert "disk_guard_resume" in events


def test_maintenance_scan_and_cleanup(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    maintenance = modules["app.maintenance"]
    db = modules["app.db"]

    storage.ensure_dirs()
    orphan_uuid = uuid4().hex
    orphan_raw = config.RAW_DIR / f"{orphan_uuid}.png"
    make_image(orphan_raw)

    missing_uuid = uuid4().hex
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO images (uuid, original_name, ext, mime, width, height, bytes, sha256, status, stored_path, thumb_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                missing_uuid,
                "missing.png",
                ".png",
                "image/png",
                10,
                10,
                1,
                "deadbeef",
                "published",
                f"raw/{missing_uuid}.png",
                "thumb/missing.webp",
            ),
        )

    orphan_thumb = config.THUMB_DIR / "orphan.webp"
    orphan_thumb.write_text("x", encoding="utf-8")

    report = maintenance.scan_consistency()
    assert orphan_raw.name in report["orphan_raw"]
    assert missing_uuid in report["missing_raw"]
    assert orphan_thumb.name in report["orphan_thumbs"]

    removed = maintenance.cleanup_orphan_thumbs()
    assert orphan_thumb.name in removed
    assert not orphan_thumb.exists()

    staging_dir = config.WWW_STAGING / "old_build"
    staging_dir.mkdir(parents=True, exist_ok=True)
    old_ts = time.time() - 60 * 60 * 48
    os.utime(staging_dir, (old_ts, old_ts))
    removed_staging = maintenance.cleanup_staging(max_age_hours=1)
    assert "old_build" in removed_staging

    tmp_file = config.UPLOAD_TMP / "old.part"
    tmp_file.write_text("x", encoding="utf-8")
    os.utime(tmp_file, (old_ts, old_ts))
    removed_tmp = maintenance.cleanup_upload_tmp(max_age_hours=1)
    assert "old.part" in removed_tmp


def test_seo_pages_and_personalization(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    site_cfg = config.STATIC / "data" / "site.json"
    site_cfg.write_text(
        json.dumps(
            {
                "site_name": "测试站点",
                "site_description": "测试描述",
                "site_url": "https://example.com",
                "live2d": {"enabled": True},
                "counter": {"enabled": True, "img_url": "https://example.com/counter.png"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    storage.ensure_dirs()
    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path, size=(260, 200))
    assert worker.process_file(raw_path)
    assert worker.publish_ready_images()

    index_html = (config.WWW_DIR / "index.html").read_text()
    assert 'class="skip-link"' in index_html
    assert "og:title" in index_html
    assert "application/ld+json" in index_html
    assert "id=\"landlord\"" in index_html
    assert "live2d.css" in index_html
    assert "counter.png" in index_html

    sitemap = (config.WWW_DIR / "sitemap.xml").read_text()
    with db.connect() as conn:
        image_id = conn.execute("SELECT id FROM images WHERE uuid=?", (uid,)).fetchone()["id"]
    assert f"https://example.com/images/{image_id}/index.html" in sitemap
    robots = (config.WWW_DIR / "robots.txt").read_text()
    assert "Sitemap: https://example.com/sitemap.xml" in robots

    assert (config.WWW_DIR / "404.html").exists()
    assert (config.WWW_DIR / "maintenance.html").exists()
    assert (config.WWW_DIR / "error" / "index.html").exists()
    assert (config.WWW_DIR / "legal" / "index.html").exists()


def test_publish_only_when_pending(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()

    # 没有待发布内容时不触发构建
    assert worker.publish_ready_images() is False
    with db.connect() as conn:
        build_count = conn.execute("SELECT COUNT(*) AS c FROM builds").fetchone()["c"]
    assert build_count == 0

    uid1 = uuid4().hex
    uid2 = uuid4().hex
    make_image(config.RAW_DIR / f"{uid1}.png", size=(180, 120))
    make_image(config.RAW_DIR / f"{uid2}.png", size=(200, 180))

    assert worker.process_file(config.RAW_DIR / f"{uid1}.png")
    assert worker.process_file(config.RAW_DIR / f"{uid2}.png")

    with db.connect() as conn:
        statuses = conn.execute(
            "SELECT uuid, status FROM images WHERE uuid IN (?, ?)",
            (uid1, uid2),
        ).fetchall()
    assert all(row["status"] == "processed" for row in statuses)

    assert worker.publish_ready_images() is True
    assert (config.WWW_DIR / "index.html").exists()

    with db.connect() as conn:
        build_count_after = conn.execute("SELECT COUNT(*) AS c FROM builds").fetchone()["c"]
        statuses_after = conn.execute(
            "SELECT uuid, status FROM images WHERE uuid IN (?, ?)",
            (uid1, uid2),
        ).fetchall()
    assert build_count_after == 1
    assert all(row["status"] == "published" for row in statuses_after)

    # 无新增处理内容时不重复发布
    assert worker.publish_ready_images() is False


def test_error_pages_follow_accept_header(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    (config.WWW_DIR / "404.html").write_text("NOT FOUND", encoding="utf-8")
    error_dir = config.WWW_DIR / "error"
    error_dir.mkdir(parents=True, exist_ok=True)
    (error_dir / "index.html").write_text("SERVER ERROR", encoding="utf-8")
    (config.WWW_DIR / "maintenance.html").write_text("MAINTENANCE", encoding="utf-8")

    app = upload_service.create_app()
    client = app.test_client()

    html_resp = client.get("/api/does-not-exist", headers={"Accept": "text/html"})
    assert html_resp.status_code == 404
    assert "NOT FOUND" in html_resp.get_data(as_text=True)
    assert html_resp.mimetype == "text/html"

    json_resp = client.get("/api/does-not-exist", headers={"Accept": "application/json"})
    assert json_resp.status_code == 404
    data = json_resp.get_json()
    assert data["error"]
