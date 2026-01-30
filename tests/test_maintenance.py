import datetime

from test_pipeline import make_image, seed_test_root, setup_env


def test_cleanup_trash_removes_expired(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    maintenance = modules["app.maintenance"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = "c" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)

    trash_name = f"{uid}.png"
    trash_path = storage.move_to_trash(raw_path, trash_name)
    past = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE images
            SET deleted_at=?, trash_path=?, purge_after=?
            WHERE uuid=?
            """,
            (past.isoformat(), str(trash_path.relative_to(config.STORAGE)), past.isoformat(), uid),
        )

    removed = maintenance.cleanup_trash()
    assert uid in removed
    assert not trash_path.exists()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT trash_path, purge_after FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["trash_path"] is None
    assert row["purge_after"] is None


def test_regenerate_thumbnails_replaces_old_jpg(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    maintenance = modules["app.maintenance"]
    storage = modules["app.storage"]
    worker = modules["app.worker"]
    db = modules["app.db"]

    storage.ensure_dirs()
    uid = "d" * 32
    raw_path = config.RAW_DIR / f"{uid}.png"
    make_image(raw_path)
    assert worker.process_file(raw_path)

    with db.connect() as conn:
        row = conn.execute(
            "SELECT thumb_path FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    old_thumb = config.THUMB_DIR / row["thumb_path"].split("/")[-1]
    assert old_thumb.exists()
    old_jpg = old_thumb.with_suffix(".jpg")
    old_thumb.replace(old_jpg)
    with db.transaction() as conn:
        conn.execute(
            "UPDATE images SET thumb_path=? WHERE uuid=?",
            (f"thumb/{old_jpg.name}", uid),
        )

    report = maintenance.regenerate_thumbnails(publish=False)
    assert report["updated"] == 1

    with db.connect() as conn:
        row = conn.execute(
            "SELECT thumb_path FROM images WHERE uuid=?",
            (uid,),
        ).fetchone()
    assert row["thumb_path"].endswith(".webp")
    assert (config.THUMB_DIR / row["thumb_path"].split("/")[-1]).exists()
    assert not old_jpg.exists()


def test_backup_storage_mirrors_raw_and_www(tmp_path, monkeypatch):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    maintenance = modules["app.maintenance"]

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.WWW_DIR.mkdir(parents=True, exist_ok=True)
    (config.RAW_DIR / "sample.txt").write_text("raw", encoding="utf-8")
    (config.WWW_DIR / "index.html").write_text("www", encoding="utf-8")

    monkeypatch.setattr(maintenance.shutil, "which", lambda _: None)
    report = maintenance.backup_storage(config.CLEANUP_BACKUP_DIR)

    assert report["raw"].endswith("raw_mirror")
    assert report["www"].endswith("www_mirror")
    assert (config.CLEANUP_BACKUP_DIR / "raw_mirror" / "sample.txt").exists()
    assert (config.CLEANUP_BACKUP_DIR / "www_mirror" / "index.html").exists()
