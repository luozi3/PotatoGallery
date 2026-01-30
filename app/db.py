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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_images_publish_order ON images(status, deleted_at, created_at, id)"
        )
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
            CREATE TABLE IF NOT EXISTS dmca_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                region TEXT NOT NULL,
                contact TEXT,
                work_url TEXT NOT NULL,
                source_url TEXT NOT NULL,
                claim TEXT NOT NULL,
                evidence TEXT NOT NULL,
                authority TEXT NOT NULL,
                authority_note TEXT,
                status_note TEXT,
                processed_by TEXT,
                processed_at DATETIME,
                ip TEXT,
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        dmca_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(dmca_requests)").fetchall()
        }
        dmca_additions = {
            "status": "status TEXT NOT NULL DEFAULT 'pending'",
            "full_name": "full_name TEXT NOT NULL",
            "email": "email TEXT NOT NULL",
            "region": "region TEXT NOT NULL",
            "contact": "contact TEXT",
            "work_url": "work_url TEXT NOT NULL",
            "source_url": "source_url TEXT NOT NULL",
            "claim": "claim TEXT NOT NULL",
            "evidence": "evidence TEXT NOT NULL",
            "authority": "authority TEXT NOT NULL",
            "authority_note": "authority_note TEXT",
            "status_note": "status_note TEXT",
            "processed_by": "processed_by TEXT",
            "processed_at": "processed_at DATETIME",
            "ip": "ip TEXT",
            "user_agent": "user_agent TEXT",
            "created_at": "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for name, ddl in dmca_additions.items():
            if name not in dmca_cols:
                conn.execute(f"ALTER TABLE dmca_requests ADD COLUMN {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dmca_status ON dmca_requests(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dmca_created_at ON dmca_requests(created_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id INTEGER NOT NULL,
                image_uuid TEXT NOT NULL,
                rating INTEGER DEFAULT 0,
                flag TEXT,
                color_label TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, image_uuid),
                FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
                FOREIGN KEY (image_uuid) REFERENCES images(uuid) ON DELETE CASCADE
            )
            """
        )
        favorite_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(user_favorites)").fetchall()
        }
        favorite_additions = {
            "rating": "rating INTEGER DEFAULT 0",
            "flag": "flag TEXT",
            "color_label": "color_label TEXT",
        }
        for name, ddl in favorite_additions.items():
            if name not in favorite_cols:
                conn.execute(f"ALTER TABLE user_favorites ADD COLUMN {ddl}")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT,
                gender TEXT,
                intro TEXT,
                website TEXT,
                location TEXT,
                avatar_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
            )
            """
        )
        profile_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(user_profiles)").fetchall()
        }
        profile_additions = {
            "display_name": "display_name TEXT",
            "gender": "gender TEXT",
            "intro": "intro TEXT",
            "website": "website TEXT",
            "location": "location TEXT",
            "avatar_path": "avatar_path TEXT",
        }
        for name, ddl in profile_additions.items():
            if name not in profile_cols:
                conn.execute(f"ALTER TABLE user_profiles ADD COLUMN {ddl}")
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
