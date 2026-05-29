from conftest import TEST_PASSWORD
import datetime
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
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
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
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
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
        json={"username": "user1", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 403

    resp = client.post(
        "/auth/register",
        json={
            "username": "bad' OR 1=1",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
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
        json={"username": "user1", "password": TEST_PASSWORD},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/auth/register",
        json={"username": "user1", "password": TEST_PASSWORD, "password_confirm": "wrong"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/auth/register",
        json={"username": "user1", "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 201


def test_invite_expired_rejected(tmp_path):
    seed_test_root(tmp_path)
    _set_registration_mode(tmp_path, "invite")
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    past = datetime.datetime.now() - datetime.timedelta(days=1)
    auth.create_invite("invite-expired", max_uses=2, note="test", expires_at=past)

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/auth/register",
        json={
            "username": "user1",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
            "invite_code": "invite-expired",
        },
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 400


def test_auth_schema_cache_marks_db_path(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    db = modules["app.db"]

    with db.connect() as conn:
        auth.ensure_schema(conn)

    assert auth._SCHEMA_READY is True
    assert auth._SCHEMA_READY_DB == str(db.DB_PATH)


def test_login_sets_custom_session_days_cookie(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    upload_service = modules["app.upload_service"]

    auth.create_user("user1", TEST_PASSWORD, groups=["user"])
    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/auth/login",
        json={"username": "user1", "password": TEST_PASSWORD, "session_days": 30},
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    assert any("Max-Age=2592000" in cookie for cookie in cookies)


def test_register_does_not_auto_login(tmp_path):
    seed_test_root(tmp_path)
    _set_registration_mode(tmp_path, "open")
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    upload_service = modules["app.upload_service"]

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/auth/register",
        json={"username": "user1", "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD},
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )
    assert resp.status_code == 201
    cookies = resp.headers.getlist("Set-Cookie")
    assert not any(config.USER_COOKIE_NAME in cookie for cookie in cookies)


def test_delete_user_cleans_upload_and_images(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    db = modules["app.db"]

    auth.create_user("user1", TEST_PASSWORD, groups=["user"])

    with db.connect() as conn:
        user_row = conn.execute("SELECT id FROM auth_users WHERE username='user1'").fetchone()
        user_id = int(user_row["id"])
        conn.execute(
            """
            INSERT INTO images (uuid, original_name, ext, mime, bytes, sha256, stored_path, owner_user_id)
            VALUES ('img-1', 'img.png', 'png', 'image/png', 12, 'abc', 'raw/img-1.png', ?)
            """,
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO upload_requests (uuid, owner_user_id, title)
            VALUES ('up-1', ?, 'demo')
            """,
            (user_id,),
        )
        conn.commit()

    assert auth.delete_user("user1") is True

    with db.connect() as conn:
        user_row = conn.execute("SELECT 1 FROM auth_users WHERE username='user1'").fetchone()
        request_row = conn.execute("SELECT 1 FROM upload_requests WHERE uuid='up-1'").fetchone()
        image_row = conn.execute("SELECT owner_user_id FROM images WHERE uuid='img-1'").fetchone()

    assert user_row is None
    assert request_row is None
    assert image_row["owner_user_id"] is None
