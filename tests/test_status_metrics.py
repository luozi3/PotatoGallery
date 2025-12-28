import json
from datetime import datetime

from test_pipeline import seed_test_root, setup_env


def insert_image(conn, uuid: str, created_at: str) -> None:
    conn.execute(
        """
        INSERT INTO images (
            uuid, original_name, ext, mime, width, height, bytes, sha256, status,
            stored_path, thumb_path, thumb_width, thumb_height, dominant_color,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid,
            f"{uuid}.png",
            ".png",
            "image/png",
            100,
            100,
            1234,
            "deadbeef",
            f"raw/{uuid}.png",
            f"thumb/{uuid}.webp",
            100,
            100,
            "#000000",
            created_at,
            created_at,
        ),
    )


def test_site_age_uses_earliest_image(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    db = modules["app.db"]
    worker = modules["app.worker"]
    config = modules["app.config"]

    config.STATUS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db.transaction() as conn:
        insert_image(conn, "a" * 32, "2024-02-01 00:00:00")
        insert_image(conn, "b" * 32, "2024-01-01 00:00:00")

    metrics = worker.collect_status_metrics()
    started_at = metrics["site_age"]["started_at"]
    assert started_at.startswith("2024-01-01")


def test_site_age_preserves_stored_start(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    db = modules["app.db"]
    worker = modules["app.worker"]
    config = modules["app.config"]

    config.STATUS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    start_iso = "2023-01-01T00:00:00+08:00"
    start_ts = datetime.fromisoformat(start_iso).timestamp()
    payload = {"started_at": start_iso, "started_at_ts": start_ts, "source": "stored"}
    (config.STATUS_DATA_DIR / "site_start.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with db.transaction() as conn:
        insert_image(conn, "c" * 32, "2024-01-01 00:00:00")

    metrics = worker.collect_status_metrics()
    started_at = metrics["site_age"]["started_at"]
    assert started_at.startswith("2023-01-01")
