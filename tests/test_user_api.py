import json

from test_pipeline import make_image, seed_test_root, setup_env


def _login(client, username: str, password: str):
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )


def test_user_upload_and_permissions(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    worker = modules["app.worker"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]
    config = modules["app.config"]

    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {
        "tags": [
            {"tag": "猫咪", "slug": "cat"},
            {"tag": "天空", "slug": "sky"},
            {"tag": "新标签", "slug": "new-tag"},
        ]
    }
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")

    auth.create_user("alice", "secret123", groups=["user"])
    auth.create_user("bob", "secret123", groups=["user"])

    app = upload_service.create_app()
    client = app.test_client()
    resp = _login(client, "alice", "secret123")
    assert resp.status_code == 200

    img_path = tmp_path / "input.png"
    make_image(img_path)
    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={
                "file": (f, "input.png"),
                "title": "标题",
                "description": "说明",
                "tags": "#猫咪 #天空",
                "collection": "",
            },
            content_type="multipart/form-data",
            headers={"X-Forwarded-Proto": "https"},
            base_url="https://example.com",
        )
    assert resp.status_code == 201
    payload = resp.get_json()
    uuid = payload["uuid"]

    with db.connect() as conn:
        row = conn.execute(
            "SELECT owner_user_id, tags_json FROM upload_requests WHERE uuid=?",
            (uuid,),
        ).fetchone()
    assert row

    raw_path = config.RAW_DIR / f"{uuid}.png"
    assert raw_path.exists()
    assert worker.process_file(raw_path)

    with db.connect() as conn:
        row = conn.execute(
            "SELECT owner_user_id, title_override, description, tags_json FROM images WHERE uuid=?",
            (uuid,),
        ).fetchone()
    assert row["owner_user_id"]
    assert row["title_override"] == "标题"
    assert row["description"] == "说明"
    assert json.loads(row["tags_json"]) == ["猫咪", "天空"]

    resp = _login(client, "bob", "secret123")
    assert resp.status_code == 200
    resp = client.post(
        f"/api/images/{uuid}/update",
        json={"title": "改名", "description": "", "tags": "#新标签", "collection": ""},
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )
    assert resp.status_code == 403

    resp = _login(client, "alice", "secret123")
    assert resp.status_code == 200
    resp = client.post(
        f"/api/images/{uuid}/update",
        json={"title": "改名", "description": "", "tags": "#新标签", "collection": ""},
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )
    assert resp.status_code == 200


def test_user_upload_rejects_unregistered_tag(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]
    auth.create_user("alice", "secret123", groups=["user"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = _login(client, "alice", "secret123")
    assert resp.status_code == 200

    img_path = tmp_path / "input.png"
    make_image(img_path)
    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={
                "file": (f, "input.png"),
                "title": "标题",
                "description": "说明",
                "tags": "#ghost",
                "collection": "",
            },
            content_type="multipart/form-data",
            headers={"X-Forwarded-Proto": "https"},
            base_url="https://example.com",
        )
    assert resp.status_code == 400


def test_user_upload_status_progress(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    worker = modules["app.worker"]
    upload_service = modules["app.upload_service"]
    config = modules["app.config"]

    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {"tags": [{"tag": "猫咪", "slug": "cat"}]}
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")

    auth.create_user("alice", "secret123", groups=["user"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = _login(client, "alice", "secret123")
    assert resp.status_code == 200

    img_path = tmp_path / "input.png"
    make_image(img_path)
    with img_path.open("rb") as f:
        resp = client.post(
            "/api/upload",
            data={
                "file": (f, "input.png"),
                "title": "标题",
                "description": "说明",
                "tags": "#猫咪",
                "collection": "",
            },
            content_type="multipart/form-data",
            headers={"X-Forwarded-Proto": "https"},
            base_url="https://example.com",
        )
    assert resp.status_code == 201
    uuid = resp.get_json()["uuid"]

    headers = {"X-Forwarded-Proto": "https"}
    base_url = "https://example.com"
    resp = client.get(f"/api/upload/status?uuid={uuid}", headers=headers, base_url=base_url)
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    payload = resp.get_json()
    assert payload["stage"] in {"queued", "processing"}
    assert payload["percent"] > 0

    raw_path = config.RAW_DIR / f"{uuid}.png"
    assert raw_path.exists()
    assert worker.process_file(raw_path)
    resp = client.get(f"/api/upload/status?uuid={uuid}", headers=headers, base_url=base_url)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["stage"] == "processed"

    assert worker.publish_ready_images()
    resp = client.get(f"/api/upload/status?uuid={uuid}", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert payload["stage"] == "published"


def test_user_favorites_flow(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    worker = modules["app.worker"]
    upload_service = modules["app.upload_service"]
    config = modules["app.config"]
    storage = modules["app.storage"]

    storage.ensure_dirs()
    auth.create_user("alice", "secret123", groups=["user"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = _login(client, "alice", "secret123")
    assert resp.status_code == 200

    uid = "f" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)

    headers = {"X-Forwarded-Proto": "https"}
    base_url = "https://example.com"
    resp = client.post(f"/api/favorites/{uid}/toggle", headers=headers, base_url=base_url)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "added"

    resp = client.get("/api/favorites", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["images"][0]["uuid"] == uid

    resp = client.post(f"/api/favorites/{uid}/toggle", headers=headers, base_url=base_url)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "removed"
    resp = client.get("/api/favorites", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["total"] == 0


def test_user_gallery_flow(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    worker = modules["app.worker"]
    upload_service = modules["app.upload_service"]
    config = modules["app.config"]
    storage = modules["app.storage"]

    storage.ensure_dirs()
    auth.create_user("alice", "secret123", groups=["user"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = _login(client, "alice", "secret123")
    assert resp.status_code == 200

    uid = "c" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)

    headers = {"X-Forwarded-Proto": "https"}
    base_url = "https://example.com"
    resp = client.post(
        "/api/galleries",
        json={"title": "2025 壁纸", "description": "收藏集"},
        headers=headers,
        base_url=base_url,
    )
    assert resp.status_code == 200
    gallery_id = resp.get_json()["id"]

    resp = client.post(
        f"/api/galleries/{gallery_id}/items",
        json={"uuid": uid, "action": "add"},
        headers=headers,
        base_url=base_url,
    )
    assert resp.status_code == 200

    resp = client.get(f"/api/galleries/{gallery_id}/images", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["images"][0]["uuid"] == uid

    resp = client.post(
        f"/api/galleries/{gallery_id}/update",
        json={"title": "2025 壁纸精选", "description": ""},
        headers=headers,
        base_url=base_url,
    )
    assert resp.status_code == 200

    resp = client.post(
        f"/api/galleries/{gallery_id}/items",
        json={"uuid": uid, "action": "remove"},
        headers=headers,
        base_url=base_url,
    )
    assert resp.status_code == 200
    resp = client.get(f"/api/galleries/{gallery_id}/images", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert not data["images"]
