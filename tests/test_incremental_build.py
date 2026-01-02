import importlib
import os
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def seed_test_root(tmp_root: Path):
    static_src = PROJECT_ROOT / "static"
    shutil.copytree(static_src, tmp_root / "static", dirs_exist_ok=True)
    local_site = tmp_root / "static" / "data" / "site.local.json"
    if local_site.exists():
        local_site.unlink()
    schema_src = PROJECT_ROOT / "db" / "schema.sql"
    schema_dst = tmp_root / "db" / "schema.sql"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(), encoding="utf-8")
    conn = sqlite3.connect(tmp_root / "db" / "gallery.db")
    conn.executescript(schema_dst.read_text())
    conn.commit()
    conn.close()


def reload_modules():
    modules = {}
    for name in ["app.config", "app.db", "app.worker", "app.static_site"]:
        modules[name] = importlib.reload(importlib.import_module(name))
    return modules


def setup_env(tmp_path: Path):
    os.environ["GALLERY_ROOT"] = str(tmp_path)
    return reload_modules()


def insert_image(db_module, uuid: str, status: str) -> int:
    db_module.ensure_schema()
    sha = ("0" * 64)[:64]
    with db_module.transaction() as conn:
        conn.execute(
            """
            INSERT INTO images (uuid, original_name, ext, mime, width, height, bytes, sha256, status, stored_path, thumb_path, thumb_width, thumb_height, dominant_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid,
                f"{uuid}.png",
                ".png",
                "image/png",
                640,
                480,
                1234,
                sha,
                status,
                f"raw/{uuid}.png",
                f"thumb/{uuid}.webp",
                320,
                240,
                "#ffffff",
            ),
        )
    with db_module.connect() as conn:
        row = conn.execute("SELECT id FROM images WHERE uuid=?", (uuid,)).fetchone()
    return int(row["id"])


def test_incremental_build_reuses_detail_pages(tmp_path):
    seed_test_root(tmp_path)
    modules = setup_env(tmp_path)
    config = modules["app.config"]
    db_module = modules["app.db"]
    worker = modules["app.worker"]
    static_site = modules["app.static_site"]

    uuid1 = uuid4().hex
    image_id1 = insert_image(db_module, uuid1, "published")
    staging1 = static_site.build_site(worker.images_for_site(), full_rebuild=True)
    static_site.publish(staging1)

    base_detail = config.WWW_DIR / "images" / str(image_id1) / "index.html"
    base_inode = base_detail.stat().st_ino
    base_search_inode = (config.WWW_DIR / "static" / "data" / "search_index.json").stat().st_ino

    uuid2 = uuid4().hex
    image_id2 = insert_image(db_module, uuid2, "processed")
    staging2 = static_site.build_site(
        worker.images_for_site(),
        base_dir=config.WWW_DIR,
        changed_uuids=[uuid2],
        full_rebuild=False,
    )

    new_detail = staging2 / "images" / str(image_id1) / "index.html"
    assert new_detail.stat().st_ino == base_inode
    new_search_inode = (staging2 / "static" / "data" / "search_index.json").stat().st_ino
    assert new_search_inode != base_search_inode
    assert (staging2 / "images" / str(image_id2) / "index.html").exists()
