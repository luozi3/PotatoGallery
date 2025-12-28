import json
from uuid import uuid4

from test_pipeline import make_image, seed_test_root, setup_env


def test_admin_update_and_delete(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {"tags": [{"tag": "测试", "slug": "test"}]}
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")
    auth.create_user("admin", "secret", groups=[config.ADMIN_GROUP])
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


def test_admin_login_requires_group(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("viewer", "secret", groups=["viewer"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "viewer", "password": "secret"},
    )
    assert resp.status_code == 401


def test_search_index_and_tags_pages(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {"tags": [{"tag": "猫咪", "slug": "cat"}]}
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")
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
    tag_index = config.WWW_DIR / "static" / "data" / "tag_index.json"
    assert tag_index.exists()
    tag_index_payload = json.loads(tag_index.read_text())
    tagged = {item["tag"]: item for item in tag_index_payload.get("tags", [])}
    assert tagged["猫咪"]["type"] == "general"
    tag_slug = "cat"
    tag_page = config.WWW_DIR / "tags" / tag_slug / "index.html"
    assert tag_page.exists()
    manifest = config.WWW_DIR / "static" / "data" / "search_manifest.json"
    assert manifest.exists()


def test_admin_tag_meta_crud(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("admin", "secret", groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/upload/admin/tags/meta",
        json={
            "tag": "#TestTag",
            "slug": "test_tag",
            "intro": "简介",
            "aliases": "alias_one | alias two",
            "type": "artist",
        },
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/tags")
    assert resp.status_code == 200
    data = resp.get_json()
    tags = {item["tag"]: item for item in data["tags"]}
    assert "testtag" in tags
    assert tags["testtag"]["intro"] == "简介"
    assert "alias_one" in tags["testtag"]["aliases"]
    assert "alias two" in tags["testtag"]["aliases"]
    assert tags["testtag"]["slug"] == "test_tag"
    assert tags["testtag"]["type"] == "artist"

    resp = client.post("/upload/admin/tags/meta/delete", json={"tag": "#TestTag"})
    assert resp.status_code == 200


def test_admin_wiki_markdown_crud(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("admin", "secret", groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert resp.status_code == 200

    resp = client.post("/upload/admin/wiki", json={"markdown": "# Wiki\\n\\n测试内容"})
    assert resp.status_code == 200
    wiki_path = config.STATIC / "data" / "wiki.md"
    assert wiki_path.exists()
    assert "测试内容" in wiki_path.read_text(encoding="utf-8")

    resp = client.get("/upload/admin/wiki")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["markdown"].startswith("# Wiki")
def test_tag_alias_intro_and_slug(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    tagging = modules["app.tagging"]

    storage.ensure_dirs()
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {
        "tags": [
            {"tag": "long hair", "intro": "长发标签", "aliases": ["长发"], "slug": "long-hair"},
            {"tag": "long_hair", "slug": "long-hair-alt", "alias_to": "long hair"},
        ]
    }
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")

    uid = uuid4().hex
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)
    with db.transaction() as conn:
        conn.execute(
            "UPDATE images SET tags_json=? WHERE uuid=?",
            (json.dumps(["long_hair"], ensure_ascii=False), uid),
        )
    assert worker.publish_ready_images()

    tag_slug = "long-hair"
    tag_page = config.WWW_DIR / "tags" / tag_slug / "index.html"
    assert tag_page.exists()
    assert "长发标签" in tag_page.read_text(encoding="utf-8")
    sitemap = (config.WWW_DIR / "sitemap.xml").read_text(encoding="utf-8")
    assert "/tags/long-hair/" in sitemap
    alias_slug = "long-hair-alt"
    alias_page = config.WWW_DIR / "tags" / alias_slug / "index.html"
    assert alias_page.exists()
    alias_html = alias_page.read_text(encoding="utf-8")
    assert "合并至" in alias_html
