from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from . import config
from . import db


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    is_active: bool


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_user_groups (
            user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, group_id),
            FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES auth_groups(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_user_groups_group_id ON auth_user_groups(group_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_hash TEXT NOT NULL UNIQUE,
            code_prefix TEXT NOT NULL,
            max_uses INTEGER,
            used_count INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_invite_usages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invite_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ip TEXT,
            used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invite_id) REFERENCES auth_invites(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_invite_usages_invite_id ON auth_invite_usages(invite_id)"
    )


def ensure_group(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM auth_groups WHERE name=?", (name,)).fetchone()
    if row:
        return int(row["id"])
    conn.execute("INSERT INTO auth_groups (name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM auth_groups WHERE name=?", (name,)).fetchone()
    return int(row["id"])


def _normalize_groups(groups: Optional[Iterable[str]]) -> list[str]:
    if not groups:
        return []
    return [g.strip() for g in groups if g and str(g).strip()]


def _hash_invite(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_invite(
    code: str,
    *,
    max_uses: Optional[int] = None,
    note: str = "",
    created_by: Optional[str] = None,
    conn=None,
) -> int:
    if not code:
        raise ValueError("邀请码不能为空")
    if max_uses is not None and max_uses < 1:
        raise ValueError("最大使用次数必须大于 0")
    owned_conn = conn is None
    if owned_conn:
        conn = db.connect()
    try:
        ensure_schema(conn)
        code_hash = _hash_invite(code)
        code_prefix = code[:6]
        conn.execute(
            """
            INSERT INTO auth_invites (code_hash, code_prefix, max_uses, note, created_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (code_hash, code_prefix, max_uses, note, created_by),
        )
        row = conn.execute(
            "SELECT id FROM auth_invites WHERE code_hash=?",
            (code_hash,),
        ).fetchone()
        invite_id = int(row["id"])
        if owned_conn:
            conn.commit()
        return invite_id
    except Exception:
        if owned_conn:
            conn.rollback()
        raise
    finally:
        if owned_conn:
            conn.close()


def consume_invite(code: str, user_id: int, *, ip: Optional[str] = None, conn) -> Optional[str]:
    if not code:
        return "邀请码不能为空"
    ensure_schema(conn)
    code_hash = _hash_invite(code)
    row = conn.execute(
        """
        SELECT id, max_uses, used_count, is_active
        FROM auth_invites
        WHERE code_hash=?
        """,
        (code_hash,),
    ).fetchone()
    if not row or not row["is_active"]:
        return "邀请码无效"
    max_uses = row["max_uses"]
    invite_id = int(row["id"])
    if max_uses is not None:
        result = conn.execute(
            """
            UPDATE auth_invites
            SET used_count=used_count+1
            WHERE id=? AND used_count < max_uses
            """,
            (invite_id,),
        )
        if result.rowcount == 0:
            return "邀请码已用完"
    else:
        conn.execute(
            "UPDATE auth_invites SET used_count=used_count+1 WHERE id=?",
            (invite_id,),
        )
    conn.execute(
        """
        INSERT INTO auth_invite_usages (invite_id, user_id, ip)
        VALUES (?, ?, ?)
        """,
        (invite_id, user_id, ip),
    )
    return None


def create_user(
    username: str,
    password: str,
    *,
    groups: Optional[Iterable[str]] = None,
    is_active: bool = True,
    conn=None,
) -> AuthUser:
    if not username or not password:
        raise ValueError("用户名或密码不能为空")
    owned_conn = conn is None
    if owned_conn:
        conn = db.connect()
    try:
        ensure_schema(conn)
        password_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO auth_users (username, password_hash, is_active) VALUES (?, ?, ?)",
            (username, password_hash, 1 if is_active else 0),
        )
        user_row = conn.execute(
            "SELECT id, username, is_active FROM auth_users WHERE username=?",
            (username,),
        ).fetchone()
        user_id = int(user_row["id"])
        for group in _normalize_groups(groups):
            group_id = ensure_group(conn, group)
            conn.execute(
                "INSERT OR IGNORE INTO auth_user_groups (user_id, group_id) VALUES (?, ?)",
                (user_id, group_id),
            )
        if owned_conn:
            conn.commit()
        return AuthUser(id=user_id, username=user_row["username"], is_active=bool(user_row["is_active"]))
    except Exception:
        if owned_conn:
            conn.rollback()
        raise
    finally:
        if owned_conn:
            conn.close()


def set_password(username: str, password: str, *, conn=None) -> None:
    if not password:
        raise ValueError("密码不能为空")
    owned_conn = conn is None
    if owned_conn:
        conn = db.connect()
    try:
        ensure_schema(conn)
        password_hash = generate_password_hash(password)
        conn.execute(
            "UPDATE auth_users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE username=?",
            (password_hash, username),
        )
        if owned_conn:
            conn.commit()
    except Exception:
        if owned_conn:
            conn.rollback()
        raise
    finally:
        if owned_conn:
            conn.close()


def authenticate(username: str, password: str, *, required_group: Optional[str] = None) -> Optional[AuthUser]:
    if not username or not password:
        return None
    with db.connect() as conn:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT id, username, password_hash, is_active FROM auth_users WHERE username=?",
            (username,),
        ).fetchone()
        if not row:
            return None
        if not row["is_active"]:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        if required_group:
            group_row = conn.execute(
                """
                SELECT 1
                FROM auth_user_groups ug
                JOIN auth_groups g ON ug.group_id = g.id
                WHERE ug.user_id=? AND g.name=?
                """,
                (row["id"], required_group),
            ).fetchone()
            if not group_row:
                return None
        return AuthUser(
            id=int(row["id"]),
            username=str(row["username"]),
            is_active=bool(row["is_active"]),
        )


def get_user_groups(user_id: int) -> list[str]:
    with db.connect() as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT g.name
            FROM auth_user_groups ug
            JOIN auth_groups g ON ug.group_id = g.id
            WHERE ug.user_id=?
            ORDER BY g.name ASC
            """,
            (user_id,),
        ).fetchall()
    return [str(row["name"]) for row in rows]


def get_user_in_group(username: str, group: str) -> Optional[AuthUser]:
    if not username or not group:
        return None
    with db.connect() as conn:
        ensure_schema(conn)
        row = conn.execute(
            """
            SELECT u.id, u.username, u.is_active
            FROM auth_users u
            JOIN auth_user_groups ug ON ug.user_id = u.id
            JOIN auth_groups g ON ug.group_id = g.id
            WHERE u.username=? AND u.is_active=1 AND g.name=?
            """,
            (username, group),
        ).fetchone()
        if not row:
            return None
        return AuthUser(
            id=int(row["id"]),
            username=str(row["username"]),
            is_active=bool(row["is_active"]),
        )


def has_any_users() -> bool:
    with db.connect() as conn:
        ensure_schema(conn)
        row = conn.execute("SELECT 1 FROM auth_users LIMIT 1").fetchone()
    return bool(row)


def bootstrap_admin_if_needed() -> bool:
    """
    可选的启动引导：仅在设置了环境变量且系统尚无用户时创建管理员。
    """
    user = config.ADMIN_BOOTSTRAP_USER
    password = config.ADMIN_BOOTSTRAP_PASSWORD
    if not user or not password:
        return False
    with db.connect() as conn:
        ensure_schema(conn)
        row = conn.execute("SELECT 1 FROM auth_users LIMIT 1").fetchone()
        if row:
            return False
        create_user(user, password, groups=[config.ADMIN_GROUP], conn=conn)
        conn.commit()
        return True
