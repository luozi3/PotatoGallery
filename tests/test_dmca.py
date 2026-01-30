import json

from test_pipeline import seed_test_root, setup_env


def _build_payload(work_url: str) -> dict:
    return {
        "full_name": "Alice Example",
        "email": "alice@example.com",
        "region": "CN",
        "contact": "@alice",
        "work_url": work_url,
        "source_url": "https://source.example.com/post/1",
        "claim": "我为该作品原作者，申请删除。",
        "evidence": "https://source.example.com/proof",
        "authority": "owner",
        "authority_note": "",
        "single_work": True,
        "truthful": True,
    }


def test_dmca_submit_and_admin_review(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]

    app = upload_service.create_app()
    client = app.test_client()

    payload = _build_payload("https://example.com/images/1/")
    resp = client.post("/api/dmca", json=payload, base_url="https://example.com")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["ok"] is True
    request_id = data["id"]
    assert data["ticket"].startswith("DMCA-")

    with db.connect() as conn:
        row = conn.execute(
            "SELECT status, full_name, work_url FROM dmca_requests WHERE id=?",
            (request_id,),
        ).fetchone()
    assert row["status"] == "pending"
    assert row["full_name"] == payload["full_name"]
    assert row["work_url"].endswith("/images/1/")

    auth.create_user("admin", "secret", groups=[config.ADMIN_GROUP])
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/dmca?status=pending")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(item["id"] == request_id for item in data["items"])

    resp = client.post(
        f"/upload/admin/dmca/{request_id}/status",
        json={"status": "approved", "note": "已记录"},
    )
    assert resp.status_code == 200

    with db.connect() as conn:
        row = conn.execute(
            "SELECT status, status_note, processed_by FROM dmca_requests WHERE id=?",
            (request_id,),
        ).fetchone()
    assert row["status"] == "approved"
    assert row["status_note"] == "已记录"
    assert row["processed_by"] == "admin"


def test_dmca_rejects_external_work_url(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    upload_service = modules["app.upload_service"]

    app = upload_service.create_app()
    client = app.test_client()

    payload = _build_payload("https://evil.example.com/images/1/")
    resp = client.post("/api/dmca", json=payload, base_url="https://example.com")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "本站" in data["error"]


def test_dmca_rejects_multiple_work_urls(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    upload_service = modules["app.upload_service"]

    app = upload_service.create_app()
    client = app.test_client()

    payload = _build_payload("https://example.com/images/1/ https://example.com/images/2/")
    resp = client.post("/api/dmca", json=payload, base_url="https://example.com")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "单个作品链接" in data["error"]
