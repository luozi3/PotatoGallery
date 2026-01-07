import time

from test_pipeline import login_user, seed_test_root, setup_env


def _wait_for(predicate, *, timeout=6.0, interval=0.05) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_admin_stress_test_flow(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    auth = modules["app.auth"]
    stress_test = modules["app.stress_test"]
    db = modules["app.db"]
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    auth.create_user("admin", "secret", groups=[config.ADMIN_GROUP])
    auth.create_user("luozi_sama", "secret123", groups=["user"])

    app = upload_service.create_app()
    client = app.test_client()
    resp = client.post(
        "/upload/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/upload/admin/stress-test/start",
        json={"username": "luozi_sama", "count": 2, "min_size": 360, "max_size": 380},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    job_id = payload["job"]["id"]

    def job_done():
        status = stress_test.get_status_for_admin()
        job = status.get("job") or {}
        if job.get("id") != job_id:
            return False
        if int(job.get("generated") or 0) >= 2:
            return True
        return job.get("status") in {"failed", "stopped", "done"}

    assert _wait_for(job_done)

    resp = client.get("/upload/admin/stress-test/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"]
    assert data["job"]["id"] == job_id
    assert "counts" in data

    resp = client.post("/upload/admin/stress-test/cleanup", json={"job_id": job_id})
    assert resp.status_code == 200
    with db.connect() as conn:
        row = conn.execute("SELECT status FROM stress_jobs WHERE id=?", (job_id,)).fetchone()
    assert row["status"] == "cleaned"
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM upload_requests WHERE stress_job_id=?",
            (job_id,),
        ).fetchone()
    assert row["c"] == 0


def test_user_stress_status(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    auth = modules["app.auth"]
    stress_test = modules["app.stress_test"]
    storage = modules["app.storage"]
    upload_service = modules["app.upload_service"]

    storage.ensure_dirs()
    owner = auth.create_user("luozi_sama", "secret123", groups=["user"])
    ok, _message, _job = stress_test.start_job(owner.id, total=1, min_size=360, max_size=360)
    assert ok

    app = upload_service.create_app()
    client = app.test_client()
    resp = login_user(client, "luozi_sama", "secret123")
    assert resp.status_code == 200

    resp = client.get(
        "/api/stress-test/status",
        headers={"X-Forwarded-Proto": "https"},
        base_url="https://example.com",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"]
    assert data["job"]["owner_user_id"] == owner.id
