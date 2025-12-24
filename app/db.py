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
            "deleted_at": "deleted_at DATETIME",
            "trash_path": "trash_path TEXT",
            "purge_after": "purge_after DATETIME",
        }
        for name, ddl in additions.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE images ADD COLUMN {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_deleted_at ON images(deleted_at)")
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
