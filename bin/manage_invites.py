#!/usr/bin/env python3
import argparse
import os
import secrets
import sys
from typing import Optional
from pathlib import Path

ROOT = Path(os.environ.get("GALLERY_ROOT", "/opt/PotatoGallery"))
sys.path.insert(0, str(ROOT))

from app import auth  # noqa: E402
from app import config  # noqa: E402
from app import db  # noqa: E402


def _ensure_schema() -> None:
    db.ensure_schema()


def _generate_code() -> str:
    return secrets.token_urlsafe(12)


def cmd_create(args) -> int:
    _ensure_schema()
    code = args.code or _generate_code()
    max_uses = args.max_uses if args.max_uses is not None else config.AUTH_INVITE_DEFAULT_USES
    note = args.note or ""
    try:
        auth.create_invite(code, max_uses=max_uses, note=note, created_by=args.created_by)
    except Exception as exc:  # noqa: BLE001
        print(f"创建失败: {exc}", file=sys.stderr)
        return 1
    print(f"邀请码: {code}")
    print(f"最大可用次数: {max_uses}")
    return 0


def cmd_list(args) -> int:
    _ensure_schema()
    with db.connect() as conn:
        auth.ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT id, code_prefix, max_uses, used_count, note, is_active, created_at
            FROM auth_invites
            ORDER BY created_at DESC
            """
        ).fetchall()
    for row in rows:
        status = "启用" if row["is_active"] else "停用"
        max_uses = row["max_uses"] or "-"
        print(f"{row['id']}\t{row['code_prefix']}****\t{row['used_count']}/{max_uses}\t{status}\t{row['note'] or ''}")
    return 0


def cmd_disable(args) -> int:
    _ensure_schema()
    with db.transaction() as conn:
        auth.ensure_schema(conn)
        conn.execute("UPDATE auth_invites SET is_active=0 WHERE id=?", (args.invite_id,))
    print(f"已停用邀请码 {args.invite_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 PotatoGallery 邀请码")
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create", help="创建邀请码")
    create_cmd.add_argument("--code", help="手动指定邀请码（不填则随机生成）")
    create_cmd.add_argument("--max-uses", type=int, default=None, help="最大使用次数（默认取配置）")
    create_cmd.add_argument("--note", help="邀请码来源备注")
    create_cmd.add_argument("--created-by", dest="created_by", help="创建人标记")
    create_cmd.set_defaults(func=cmd_create)

    list_cmd = sub.add_parser("list", help="列出邀请码")
    list_cmd.set_defaults(func=cmd_list)

    disable_cmd = sub.add_parser("disable", help="停用邀请码")
    disable_cmd.add_argument("invite_id", type=int)
    disable_cmd.set_defaults(func=cmd_disable)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
