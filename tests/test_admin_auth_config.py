from conftest import TEST_PASSWORD
import json
import os

from test_pipeline import seed_test_root, setup_env


def _login_admin(client, username: str, password: str):
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-Forwarded-Proto": "https"},
        base_url="http://localhost",
    )


def test_admin_can_toggle_registration_mode(tmp_path):
    seed_test_root(tmp_path)
    cfg_path = tmp_path / "config" / "auth.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"registration_mode": "open"}, ensure_ascii=False), encoding="utf-8")

    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    config = modules["app.config"]
    upload_service = modules["app.upload_service"]

    auth.create_user("boss", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
    app = upload_service.create_app()
    client = app.test_client()

    resp = _login_admin(client, "boss", TEST_PASSWORD)
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


def test_admin_auth_config_fallback_write(tmp_path):
    seed_test_root(tmp_path)
    cfg_dir = tmp_path / "config"
    cfg_path = cfg_dir / "auth.json"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"registration_mode": "open"}, ensure_ascii=False), encoding="utf-8")

    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    config = modules["app.config"]
    upload_service = modules["app.upload_service"]

    os.chmod(cfg_dir, 0o555)
    try:
        auth.create_user("boss", TEST_PASSWORD, groups=[config.ADMIN_GROUP])
        app = upload_service.create_app()
        client = app.test_client()

        resp = _login_admin(client, "boss", TEST_PASSWORD)
        assert resp.status_code == 200

        resp = client.post("/upload/admin/auth-config", json={"registration_mode": "closed"})
        assert resp.status_code == 200

        saved = json.loads(config.AUTH_CONFIG_FALLBACK_PATH.read_text(encoding="utf-8"))
        assert saved["registration_mode"] == "closed"
    finally:
        os.chmod(cfg_dir, 0o755)
