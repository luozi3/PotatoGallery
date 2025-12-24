import json
from pathlib import Path
from urllib.parse import quote

from test_pipeline import make_image, seed_test_root, setup_env


def test_admin_update_and_delete(tmp_path, monkeypatch):
    seed_test_root(tmp_path)
    monkeypatch.setenv("GALLERY_ADMIN_USER", "admin")
    monkeypatch.setenv("GALLERY_ADMIN_PASSWORD", "secret")
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    uid = "a" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/images")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["images"]

    resp = client.post(
        f"/upload/admin/images/{uid}/update",
        json={"title": "新标题", "description": "说明", "tags": "#测试", "collection": ""},
    )
    assert resp.status_code == 200
    with db.connect() as conn:
        row = conn.execute(
            "SELECT title_override, description, tags_json FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["title_override"] == "新标题"
    assert row["description"] == "说明"
    assert json.loads(row["tags_json"]) == ["测试"]

    resp = client.post(f"/upload/admin/images/{uid}/delete")
    assert resp.status_code == 200
    assert not raw_path.exists()
    trash_path = config.TRASH_DIR / f"{uid}.png"
    assert trash_path.exists()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT deleted_at FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["deleted_at"]


def test_search_index_and_tags_pages(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = "b" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    with db.transaction() as conn:
        conn.execute(
            "UPDATE images SET tags_json=? WHERE uuid=?",
            (json.dumps(["猫咪"], ensure_ascii=False), uid),
        )

    assert worker.publish_ready_images()
    search_index = config.WWW_DIR / "static" / "data" / "search_index.json"
    assert search_index.exists()
    payload = json.loads(search_index.read_text())
    assert payload["images"]
    assert payload["tags"]
    tag_slug = quote("猫咪", safe="")
    tag_page = config.WWW_DIR / "tags" / tag_slug / "index.html"
    assert tag_page.exists()
