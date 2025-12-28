#!/usr/bin/env python3
import argparse
import getpass
import os
import sys
from typing import Optional
from pathlib import Path

ROOT = Path(os.environ.get("GALLERY_ROOT", "/opt/PotatoGallery"))
sys.path.insert(0, str(ROOT))

from app import auth  # noqa: E402
from app import config  # noqa: E402
from app import db  # noqa: E402


def _split_groups(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _prompt_password(prompt: str) -> str:
    while True:
        value = getpass.getpass(prompt)
        if value:
            return value
        print("口令不能为空，请重试。", file=sys.stderr)


def _ensure_schema():
    db.ensure_schema()


def cmd_create(args) -> int:
    _ensure_schema()
    password = args.password or _prompt_password("口令: ")
    groups = _split_groups(args.groups) or [config.ADMIN_GROUP]
    try:
        auth.create_user(args.username, password, groups=groups)
    except Exception as exc:  # noqa: BLE001
        print(f"创建失败: {exc}", file=sys.stderr)
        return 1
    print(f"已创建用户 {args.username}，分组: {', '.join(groups)}")
    return 0


def cmd_set_password(args) -> int:
    _ensure_schema()
    password = args.password or _prompt_password("新口令: ")
    try:
        auth.set_password(args.username, password)
    except Exception as exc:  # noqa: BLE001
        print(f"更新失败: {exc}", file=sys.stderr)
        return 1
    print(f"已更新用户 {args.username} 的口令")
    return 0


def cmd_list(args) -> int:
    _ensure_schema()
    with db.connect() as conn:
        auth.ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT u.username, u.is_active, GROUP_CONCAT(g.name, ',') AS groups
            FROM auth_users u
            LEFT JOIN auth_user_groups ug ON ug.user_id = u.id
            LEFT JOIN auth_groups g ON ug.group_id = g.id
            GROUP BY u.id
            ORDER BY u.username ASC
            """
        ).fetchall()
    for row in rows:
        status = "启用" if row["is_active"] else "停用"
        groups = row["groups"] or "-"
        print(f"{row['username']}\t{status}\t{groups}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 PotatoGallery 后台用户")
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create", help="创建用户（默认加入管理员分组）")
    create_cmd.add_argument("username")
    create_cmd.add_argument("--password", help="口令（留空则交互输入）")
    create_cmd.add_argument("--groups", help="分组列表，逗号分隔")
    create_cmd.set_defaults(func=cmd_create)

    passwd_cmd = sub.add_parser("set-password", help="修改用户口令")
    passwd_cmd.add_argument("username")
    passwd_cmd.add_argument("--password", help="新口令（留空则交互输入）")
    passwd_cmd.set_defaults(func=cmd_set_password)

    list_cmd = sub.add_parser("list", help="列出用户与分组")
    list_cmd.set_defaults(func=cmd_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
