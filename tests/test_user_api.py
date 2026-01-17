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


def test_home_api_pagination_and_filters(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    worker = modules["app.worker"]
    upload_service = modules["app.upload_service"]
    config = modules["app.config"]
    db = modules["app.db"]

    data_dir = config.STATIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    tags_cfg = {"tags": [{"tag": "猫咪", "slug": "cat"}]}
    (data_dir / "tags.json").write_text(json.dumps(tags_cfg, ensure_ascii=False), encoding="utf-8")
    collections_cfg = {
        "default_collection": "main",
        "collections": [
            {"slug": "main", "title": "主分区", "uuids": ["a" * 32, "c" * 32]},
            {"slug": "alt", "title": "副分区", "uuids": ["b" * 32]},
        ],
    }
    (data_dir / "collections.json").write_text(
        json.dumps(collections_cfg, ensure_ascii=False),
        encoding="utf-8",
    )

    raw_a = config.RAW_DIR / ("a" * 32 + ".png")
    raw_b = config.RAW_DIR / ("b" * 32 + ".png")
    raw_c = config.RAW_DIR / ("c" * 32 + ".png")
    make_image(raw_a, size=(600, 400))
    make_image(raw_b, size=(400, 600))
    make_image(raw_c, size=(500, 500))
    assert worker.process_file(raw_a)
    assert worker.process_file(raw_b)
    assert worker.process_file(raw_c)

    with db.connect() as conn:
        conn.execute("UPDATE images SET tags_json=? WHERE uuid=?", (json.dumps(["猫咪"], ensure_ascii=False), "a" * 32))
        conn.execute("UPDATE images SET tags_json=? WHERE uuid=?", (json.dumps(["猫咪"], ensure_ascii=False), "b" * 32))
        conn.execute("UPDATE images SET tags_json=? WHERE uuid=?", (json.dumps(["猫咪"], ensure_ascii=False), "c" * 32))

    app = upload_service.create_app()
    client = app.test_client()
    base_url = "https://example.com"
    headers = {"X-Forwarded-Proto": "https"}

    resp = client.get("/api/home/images?limit=2", headers=headers, base_url=base_url)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert len(payload["items"]) == 2
    assert payload["has_more"] is True
    cursor = payload["next_cursor"]
    assert cursor
    assert payload["items"][0]["id"] > payload["items"][1]["id"]

    resp = client.get(f"/api/home/images?limit=2&cursor={cursor}", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert len(payload["items"]) == 1
    assert payload["has_more"] is False

    resp = client.get("/api/home/images?orientation=portrait", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["orientation"] == "portrait"

    resp = client.get("/api/home/images?collection=alt", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["collection"] == "alt"
    assert payload["items"][0]["tags"][0]["slug"] == "cat"
    assert "--tag-color" in payload["items"][0]["tags"][0]["style"]


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

    resp = client.get(f"/api/favorites/{uid}", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert payload["favorited"] is True
    assert "no-store" in resp.headers.get("Cache-Control", "")

    resp = client.post(
        f"/api/favorites/{uid}/meta",
        json={"rating": 4, "flag": "pick", "color_label": "red"},
        headers=headers,
        base_url=base_url,
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["rating"] == 4
    assert payload["flag"] == "pick"
    assert payload["color_label"] == "red"

    resp = client.get("/api/favorites", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["images"][0]["uuid"] == uid
    assert data["images"][0]["rating"] == 4
    assert data["images"][0]["flag"] == "pick"
    assert data["images"][0]["color_label"] == "red"
    assert "no-store" in resp.headers.get("Cache-Control", "")

    resp = client.post(f"/api/favorites/{uid}/toggle", headers=headers, base_url=base_url)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "removed"
    resp = client.get(f"/api/favorites/{uid}", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert payload["favorited"] is False
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

    resp = client.get(f"/api/favorites/{uid}", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert payload["favorited"] is True

    resp = client.get("/api/favorites", headers=headers, base_url=base_url)
    payload = resp.get_json()
    assert payload["total"] == 1

    resp = client.get(f"/api/galleries/{gallery_id}/images", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["images"][0]["uuid"] == uid
    assert "no-store" in resp.headers.get("Cache-Control", "")

    resp = client.get(f"/api/galleries?uuid={uid}", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["galleries"][0]["contains"] is True
    assert "no-store" in resp.headers.get("Cache-Control", "")

    resp = client.post(
        f"/api/galleries/{gallery_id}/update",
        json={"title": "2025 壁纸精选", "description": "", "cover_uuid": uid},
        headers=headers,
        base_url=base_url,
    )
    assert resp.status_code == 200

    resp = client.get("/api/galleries", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["galleries"][0]["cover_uuid"] == uid
    assert data["galleries"][0]["cover_is_manual"] is True
    assert "no-store" in resp.headers.get("Cache-Control", "")

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

    resp = client.get(f"/api/galleries?uuid={uid}", headers=headers, base_url=base_url)
    data = resp.get_json()
    assert data["galleries"][0]["contains"] is False
