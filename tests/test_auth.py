import json

from test_pipeline import seed_test_root, setup_env


def _set_registration_mode(tmp_path, mode: str) -> None:
    cfg_path = tmp_path / "config" / "auth.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"registration_mode": mode}, ensure_ascii=False, indent=2), encoding="utf-8")


def test_invite_register_and_limit(tmp_path):
    seed_test_root(tmp_path)
    _set_registration_mode(tmp_path, "invite")
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    db = modules["app.db"]
    upload_service = modules["app.upload_service"]

    auth.create_invite("invite-1", max_uses=1, note="test")

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/auth/register",
        json={
            "username": "user1",
            "password": "secret123",
            "password_confirm": "secret123",
            "invite_code": "invite-1",
        },
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"] == "user1"
    assert "user" in data["groups"]

    with db.connect() as conn:
        usage = conn.execute("SELECT COUNT(*) AS c FROM auth_invite_usages").fetchone()
    assert usage["c"] == 1

    resp = client.post(
        "/auth/register",
        json={
            "username": "user2",
            "password": "secret123",
            "password_confirm": "secret123",
            "invite_code": "invite-1",
        },
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400


def test_auth_requires_https_and_rejects_bad_username(tmp_path):
    seed_test_root(tmp_path)
    _set_registration_mode(tmp_path, "invite")
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_invite("invite-2", max_uses=2, note="test")
    app = upload_service.create_app()
    client = app.test_client()

    resp = client.post(
        "/auth/login",
        json={"username": "user1", "password": "secret123"},
    )
    assert resp.status_code == 403

    resp = client.post(
        "/auth/register",
        json={
            "username": "bad' OR 1=1",
            "password": "secret123",
            "password_confirm": "secret123",
            "invite_code": "invite-2",
        },
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400


def test_open_register_requires_password_confirmation(tmp_path):
    seed_test_root(tmp_path)
    _set_registration_mode(tmp_path, "open")
    modules = setup_env(tmp_path)
    upload_service = modules["app.upload_service"]

    app = upload_service.create_app()
    client = app.test_client()

    resp = client.post(
        "/auth/register",
        json={"username": "user1", "password": "secret123"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/auth/register",
        json={"username": "user1", "password": "secret123", "password_confirm": "wrong"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/auth/register",
        json={"username": "user1", "password": "secret123", "password_confirm": "secret123"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 201
