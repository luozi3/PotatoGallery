#!/usr/bin/env python3
"""
初始化 SQLite 数据库，应用 schema.sql，确保 WAL / 外键开启。
"""
from pathlib import Path
import sqlite3
import sys

ROOT = Path("/opt/PotatoGallery")
DB_PATH = ROOT / "db" / "gallery.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def ensure_parent():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def apply_schema():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def main():
    if not SCHEMA_PATH.exists():
        print(f"schema 文件不存在: {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)
    ensure_parent()
    apply_schema()
    print(f"数据库初始化完成: {DB_PATH}")


if __name__ == "__main__":
    main()
