import json

from test_pipeline import seed_test_root, setup_env


def test_admin_can_toggle_registration_mode(tmp_path):
    seed_test_root(tmp_path)
    cfg_path = tmp_path / "config" / "auth.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"registration_mode": "open"}, ensure_ascii=False), encoding="utf-8")

    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    config = modules["app.config"]
    upload_service = modules["app.upload_service"]

    auth.create_user("boss", "secret123", groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()

    resp = client.post(
        "/upload/admin/login",
        json={"username": "boss", "password": "secret123"},
    )
    assert resp.status_code == 200

    resp = client.get("/upload/admin/auth-config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["registration_mode"] == "open"

    resp = client.post("/upload/admin/auth-config", json={"registration_mode": "invite"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["registration_mode"] == "invite"
    assert config.AUTH_REGISTRATION_MODE == "invite"

    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["registration_mode"] == "invite"
