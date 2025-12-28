import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from . import config

DB_PATH = config.ROOT / "db" / "gallery.db"
_SCHEMA_READY = False


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def ensure_schema() -> None:
    """
    轻量迁移：为现有库补齐新字段与索引。
    """
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with connect() as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(images)").fetchall()}
        additions = {
            "title_override": "title_override TEXT",
            "description": "description TEXT",
            "tags_json": "tags_json TEXT",
            "collection_override": "collection_override TEXT",
            "owner_user_id": "owner_user_id INTEGER",
            "deleted_at": "deleted_at DATETIME",
            "trash_path": "trash_path TEXT",
            "purge_after": "purge_after DATETIME",
        }
        for name, ddl in additions.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE images ADD COLUMN {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_deleted_at ON images(deleted_at)")
        from . import auth

        auth.ensure_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_requests (
                uuid TEXT PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                title TEXT,
                description TEXT,
                tags_json TEXT,
                collection_override TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_user_id) REFERENCES auth_users(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_upload_requests_owner ON upload_requests(owner_user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id INTEGER NOT NULL,
                image_uuid TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, image_uuid),
                FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
                FOREIGN KEY (image_uuid) REFERENCES images(uuid) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_user ON user_favorites(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_favorites_image ON user_favorites(image_uuid)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_favorites_created ON user_favorites(user_id, created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_galleries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                cover_uuid TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
                FOREIGN KEY (cover_uuid) REFERENCES images(uuid)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_galleries_user ON user_galleries(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_gallery_images (
                gallery_id INTEGER NOT NULL,
                image_uuid TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (gallery_id, image_uuid),
                FOREIGN KEY (gallery_id) REFERENCES user_galleries(id) ON DELETE CASCADE,
                FOREIGN KEY (image_uuid) REFERENCES images(uuid) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_gallery_images_gallery ON user_gallery_images(gallery_id)"
        )
    _SCHEMA_READY = True


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_audit(event: str, ref: Optional[str], payload: Optional[str] = None) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO audit_log (event, ref, payload) VALUES (?, ?, ?)",
            (event, ref, payload),
        )
