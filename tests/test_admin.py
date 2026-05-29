from conftest import TEST_PASSWORD
import json
import time
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
    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    uid = "a" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/images")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["images"]
    assert data["page"] == 1
    assert data["page_size"] == 40
    assert data["total"] >= 1
    assert data["pages"] >= 1

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


def test_admin_purge_trash_page_and_all(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    uid1 = "a" * 32
    uid2 = "b" * 32
    raw_path1 = config.RAW_DIR / f"{uid1}.png"
    raw_path2 = config.RAW_DIR / f"{uid2}.png"
    make_image(raw_path1)
    make_image(raw_path2)
    assert worker.process_file(raw_path1)
    assert worker.process_file(raw_path2)

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post("/upload/admin/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert resp.status_code == 200

    resp = client.post(f"/upload/admin/images/{uid1}/delete")
    assert resp.status_code == 200
    resp = client.post(f"/upload/admin/images/{uid2}/delete")
    assert resp.status_code == 200

    trash_path1 = config.TRASH_DIR / f"{uid1}.png"
    trash_path2 = config.TRASH_DIR / f"{uid2}.png"
    assert trash_path1.exists()
    assert trash_path2.exists()

    resp = client.post("/upload/admin/images/trash/purge", json={"uuids": [uid1]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["deleted"] == 1
    assert not trash_path1.exists()
    with db.connect() as conn:
        row1 = conn.execute("SELECT uuid FROM images WHERE uuid=?", (uid1,)).fetchone()
        row2 = conn.execute("SELECT deleted_at FROM images WHERE uuid=?", (uid2,)).fetchone()
    assert row1 is None
    assert row2 and row2["deleted_at"]

    resp = client.post("/upload/admin/images/trash/purge", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["deleted"] == 1
    assert not trash_path2.exists()
    with db.connect() as conn:
        row2 = conn.execute("SELECT uuid FROM images WHERE uuid=?", (uid2,)).fetchone()
    assert row2 is None


def test_admin_login_requires_group(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("viewer", TEST_PASSWORD, groups=["viewer"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "viewer", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 401


def test_admin_invite_crud(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("boss", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "boss", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200

    payload = {
        "note": "内部测试",
        "max_uses": 3,
        "expires_at": "2030-01-01T00:00",
    }
    resp = client.post("/upload/admin/invites", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["code"]
    invite = data["invite"]
    assert invite["note"] == "内部测试"
    assert invite["max_uses"] == 3

    resp = client.get("/upload/admin/invites")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["invites"]

    invite_id = invite["id"]
    resp = client.post(f"/upload/admin/invites/{invite_id}/disable")
    assert resp.status_code == 200
    resp = client.get("/upload/admin/invites")
    data = resp.get_json()
    disabled = next(item for item in data["invites"] if item["id"] == invite_id)
    assert disabled["is_active"] is False

    resp = client.post(f"/upload/admin/invites/{invite_id}/enable")
    assert resp.status_code == 200
    resp = client.get("/upload/admin/invites")
    data = resp.get_json()
    enabled = next(item for item in data["invites"] if item["id"] == invite_id)
    assert enabled["is_active"] is True

    resp = client.post(f"/upload/admin/invites/{invite_id}/delete")
    assert resp.status_code == 200
    resp = client.get("/upload/admin/invites")
    data = resp.get_json()
    assert all(item["id"] != invite_id for item in data["invites"])


def test_admin_upload_status_progress(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {"tags": [{"tag": "测试", "slug": "test"}]}
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")
    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200

    img_path = tmp_path / "input.png"
    make_image(img_path)
    with img_path.open("rb") as f:
        resp = client.post(
            "/upload/admin/upload",
            data={
                "file": (f, "input.png"),
                "title": "标题",
                "description": "说明",
                "tags": "#测试",
                "collection": "",
            },
            content_type="multipart/form-data",
        )
    assert resp.status_code == 201
    uuid = resp.get_json()["uuid"]

    resp = client.get(f"/upload/admin/upload/status?uuid={uuid}")
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    payload = resp.get_json()
    assert payload["stage"] in {"queued", "processing"}
    assert payload["percent"] > 0

    raw_path = config.RAW_DIR / f"{uuid}.png"
    assert raw_path.exists()
    assert worker.process_file(raw_path)
    resp = client.get(f"/upload/admin/upload/status?uuid={uuid}")
    payload = resp.get_json()
    assert payload["stage"] == "processed"

    assert worker.publish_ready_images()
    resp = client.get(f"/upload/admin/upload/status?uuid={uuid}")
    payload = resp.get_json()
    assert payload["stage"] == "published"


def test_admin_stress_generate_and_cleanup(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200

    resp = client.post("/upload/admin/stress/generate", json={"index": 1, "total": 2})
    assert resp.status_code == 201
    uuid_processed = resp.get_json()["uuid"]
    resp = client.post("/upload/admin/stress/generate", json={"index": 2, "total": 2})
    assert resp.status_code == 201
    uuid_pending = resp.get_json()["uuid"]

    raw_processed = config.RAW_DIR / f"{uuid_processed}.png"
    raw_pending = config.RAW_DIR / f"{uuid_pending}.png"
    assert raw_processed.exists()
    assert raw_pending.exists()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT title, description FROM upload_requests WHERE uuid=?",
            (uuid_processed,),
        ).fetchone()
    assert "第1/2张" in row["title"]
    assert "第1/2张" in row["description"]
    assert worker.process_file(raw_processed)

    resp = client.post("/upload/admin/stress/cleanup/start")
    assert resp.status_code == 200
    payload = resp.get_json()
    task_id = payload["task_id"]
    status = {}
    for _ in range(200):
        resp = client.get(f"/upload/admin/stress/cleanup/status?task_id={task_id}")
        assert resp.status_code == 200
        status = resp.get_json()
        if status["stage"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    assert status.get("stage") == "completed"
    assert status["deleted"] >= 1
    assert status["pending_removed"] >= 1

    with db.connect() as conn:
        row = conn.execute(
            "SELECT deleted_at FROM images WHERE uuid=?",
            (uuid_processed,),
        ).fetchone()
        pending = conn.execute(
            "SELECT 1 FROM upload_requests WHERE uuid=?",
            (uuid_pending,),
        ).fetchone()
    assert row["deleted_at"]
    assert pending is None
    assert not raw_pending.exists()


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
    tags_cfg = {
        "types": [{"type": "general", "label": "普通", "color": "#336699"}],
        "tags": [{"tag": "猫咪", "slug": "cat"}],
    }
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
    assert tagged["猫咪"]["type_color"] == "#336699"
    assert tag_index_payload["types"][0]["type"] == "general"
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

    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
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


def test_admin_tag_types_crud(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/upload/admin/tag-types",
        json={
            "types": [
                {"type": "general", "label": "普通", "color": "#7b8794"},
                {"type": "series", "label": "系列", "color": "#ff0066"},
            ]
        },
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/tag-types")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["types"][1]["type"] == "series"
    assert payload["types"][1]["label"] == "系列"

    resp = client.post(
        "/upload/admin/tags/meta",
        json={"tag": "#TestSeries", "slug": "test_series", "type": "series"},
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/tags")
    data = resp.get_json()
    tags = {item["tag"]: item for item in data["tags"]}
    assert tags["testseries"]["type"] == "series"


def test_admin_wiki_markdown_crud(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("admin", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
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
