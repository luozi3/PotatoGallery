import datetime
import io
import json
import random
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from PIL import Image, ImageDraw
from . import auth
from . import config
from . import db
from . import static_site
from . import tagging
from . import storage

bp = Blueprint("admin", __name__)

_UPLOAD_UUID_RE = re.compile(r"^[0-9a-f]{32}$")
STRESS_TAG = "__stress_test__"
STRESS_TITLE = "压测随机图"
STRESS_DESCRIPTION = "压测工具自动生成"
_STRESS_TASK_TTL = 30 * 60
_STRESS_TASKS: Dict[str, Dict[str, Any]] = {}
_STRESS_TASK_LOCK = threading.Lock()


def _format_stress_title(index: Optional[int], total: Optional[int]) -> str:
    if index and total:
        return f"{STRESS_TITLE} 第{index}/{total}张"
    if index:
        return f"{STRESS_TITLE} 第{index}张"
    return STRESS_TITLE


def _format_stress_description(index: Optional[int], total: Optional[int]) -> str:
    if index and total:
        return f"{STRESS_DESCRIPTION}（第{index}/{total}张）"
    if index:
        return f"{STRESS_DESCRIPTION}（第{index}张）"
    return STRESS_DESCRIPTION


def _parse_positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _parse_invite_expires_at(raw: Any) -> Tuple[Optional[datetime.datetime], Optional[str]]:
    if raw is None:
        return None, None
    if isinstance(raw, str):
        raw_value = raw.strip()
        if not raw_value:
            return None, None
    else:
        raw_value = str(raw).strip()
        if not raw_value:
            return None, None
    normalized = raw_value.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(normalized, fmt), None
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(normalized), None
    except ValueError:
        return None, "过期时间格式不正确"


def _prune_stress_tasks(now_ts: Optional[float] = None) -> None:
    now = now_ts or time.time()
    expired = []
    for task_id, task in _STRESS_TASKS.items():
        updated_at = float(task.get("updated_at") or 0)
        if now - updated_at > _STRESS_TASK_TTL:
            expired.append(task_id)
    for task_id in expired:
        _STRESS_TASKS.pop(task_id, None)


def _create_stress_task(total: int) -> Dict[str, Any]:
    now = time.time()
    task_id = uuid.uuid4().hex
    task = {
        "task_id": task_id,
        "stage": "queued",
        "total": int(total or 0),
        "done": 0,
        "deleted": 0,
        "pending_removed": 0,
        "message": "",
        "created_at": now,
        "updated_at": now,
    }
    with _STRESS_TASK_LOCK:
        _prune_stress_tasks(now)
        _STRESS_TASKS[task_id] = task
    return dict(task)


def _get_stress_task(task_id: str) -> Optional[Dict[str, Any]]:
    if not task_id:
        return None
    with _STRESS_TASK_LOCK:
        task = _STRESS_TASKS.get(task_id)
        return dict(task) if task else None


def _update_stress_task(task_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
    if not task_id:
        return None
    with _STRESS_TASK_LOCK:
        task = _STRESS_TASKS.get(task_id)
        if not task:
            return None
        task.update(updates)
        task["updated_at"] = time.time()
        return dict(task)


def _wiki_path() -> Path:
    return config.STATIC / "data" / "wiki.md"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.ADMIN_SECRET, salt="gallery-admin")


def _json_error(message: str, status: int = 400):
    resp = jsonify({"error": message})
    resp.status_code = status
    return resp


def _set_admin_cookie(resp, token: str) -> None:
    resp.set_cookie(
        config.ADMIN_COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
        secure=config.ADMIN_COOKIE_SECURE,
        max_age=config.ADMIN_SESSION_MAX_AGE,
    )


def _clear_admin_cookie(resp) -> None:
    resp.set_cookie(
        config.ADMIN_COOKIE_NAME,
        "",
        httponly=True,
        samesite="Lax",
        secure=config.ADMIN_COOKIE_SECURE,
        expires=0,
    )


def _require_admin() -> Optional[str]:
    token = request.cookies.get(config.ADMIN_COOKIE_NAME, "")
    if not token:
        return None
    serializer = _serializer()
    try:
        data = serializer.loads(token, max_age=config.ADMIN_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    username = data.get("u")
    if not username:
        return None
    user = auth.get_user_in_group(username, config.ADMIN_GROUP)
    if not user:
        return None
    return user.username


def _touch_rebuild_flag(reason: str) -> None:
    try:
        config.FORCE_REBUILD_FLAG.write_text(reason, encoding="utf-8")
    except Exception:
        pass


def _load_alias_map() -> Dict[str, str]:
    meta, _ = tagging.load_tags_config()
    return tagging.build_alias_map(meta)


def _parse_tags_input(
    raw: Any,
    *,
    apply_aliases: bool = True,
    require_registered: bool = False,
    require_hash: bool = False,
) -> Tuple[Optional[List[str]], Optional[str]]:
    alias_map = _load_alias_map() if apply_aliases else None
    return tagging.parse_tags_input(
        raw,
        alias_map,
        require_known=require_registered,
        require_hash=require_hash,
    )


def _missing_parent_tags(tags: List[str]) -> List[str]:
    meta, _ = tagging.load_tags_config()
    alias_map = tagging.build_alias_map(meta)
    parent_map = tagging.build_parent_map(meta, alias_map)
    return tagging.missing_parent_tags(tags, parent_map)


def _allowed_extension_from_mime(mime: str) -> Optional[str]:
    return config.ALLOWED_MIME.get(mime)


def _get_user_id(username: str) -> Optional[int]:
    if not username:
        return None
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM auth_users WHERE username=?",
            (username,),
        ).fetchone()
    if not row:
        return None
    return int(row["id"])


def _normalize_upload_uuid(value: str) -> Optional[str]:
    cleaned = (value or "").strip().lower()
    if not cleaned or not _UPLOAD_UUID_RE.fullmatch(cleaned):
        return None
    return cleaned


def _file_exists_with_uuid(directory: Path, uuid_value: str) -> bool:
    for ext in set(config.ALLOWED_MIME.values()):
        if (directory / f"{uuid_value}{ext}").exists():
            return True
    return False


def _resolve_upload_status(uuid_value: str, owner_user_id: int) -> dict:
    db.ensure_schema()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT status FROM images WHERE uuid=? AND owner_user_id=?",
            (uuid_value, owner_user_id),
        ).fetchone()
        if row:
            status = str(row["status"] or "")
            if status == "published":
                return {"stage": "published", "percent": 100, "message": "已发布"}
            if status == "processed":
                return {"stage": "processed", "percent": 85, "message": "等待发布"}
            if status == "quarantined":
                return {"stage": "failed", "percent": 100, "message": "已隔离"}
        pending = conn.execute(
            "SELECT 1 FROM upload_requests WHERE uuid=? AND owner_user_id=?",
            (uuid_value, owner_user_id),
        ).fetchone()
        if pending:
            return {"stage": "queued", "percent": 25, "message": "排队中"}

    if _file_exists_with_uuid(config.RAW_DIR, uuid_value):
        return {"stage": "processing", "percent": 60, "message": "处理中"}
    if _file_exists_with_uuid(config.QUARANTINE_DIR, uuid_value):
        return {"stage": "failed", "percent": 100, "message": "已隔离"}
    return {"stage": "missing", "percent": 0, "message": "未找到记录"}


def _random_color() -> Tuple[int, int, int]:
    return (
        random.randint(24, 220),
        random.randint(24, 220),
        random.randint(24, 220),
    )


def _generate_stress_image() -> Tuple[bytes, int, int]:
    width = random.randint(480, 1080)
    height = random.randint(360, 900)
    img = Image.new("RGB", (width, height), _random_color())
    draw = ImageDraw.Draw(img)
    for _ in range(random.randint(4, 9)):
        x1 = random.randint(0, max(0, width - 40))
        y1 = random.randint(0, max(0, height - 40))
        x2 = random.randint(x1 + 20, width)
        y2 = random.randint(y1 + 20, height)
        draw.rectangle([x1, y1, x2, y2], fill=_random_color())
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), width, height


def _count_pending_stress_requests(conn) -> int:
    marker = f'%"{STRESS_TAG}"%'
    row = conn.execute(
        "SELECT COUNT(1) AS total FROM upload_requests WHERE tags_json LIKE ?",
        (marker,),
    ).fetchone()
    return int(row["total"] or 0) if row else 0


def _count_stress_images(conn) -> int:
    marker = f'%"{STRESS_TAG}"%'
    row = conn.execute(
        "SELECT COUNT(1) AS total FROM images WHERE deleted_at IS NULL AND tags_json LIKE ?",
        (marker,),
    ).fetchone()
    return int(row["total"] or 0) if row else 0


def _list_pending_stress_requests(conn) -> List[str]:
    marker = f'%"{STRESS_TAG}"%'
    rows = conn.execute(
        "SELECT uuid FROM upload_requests WHERE tags_json LIKE ?",
        (marker,),
    ).fetchall()
    return [row["uuid"] for row in rows]


def _list_stress_images(conn) -> List[Dict[str, Any]]:
    marker = f'%"{STRESS_TAG}"%'
    rows = conn.execute(
        """
        SELECT uuid, stored_path, thumb_path, ext, deleted_at
        FROM images
        WHERE deleted_at IS NULL AND tags_json LIKE ?
        """,
        (marker,),
    ).fetchall()
    return [dict(row) for row in rows]


def _cleanup_pending_stress_requests(conn) -> int:
    marker = f'%"{STRESS_TAG}"%'
    rows = conn.execute(
        "SELECT uuid FROM upload_requests WHERE tags_json LIKE ?",
        (marker,),
    ).fetchall()
    removed = 0
    for row in rows:
        uuid_value = row["uuid"]
        for ext in set(config.ALLOWED_MIME.values()):
            raw_path = config.RAW_DIR / f"{uuid_value}{ext}"
            if raw_path.exists():
                try:
                    storage.move_to_trash(raw_path, raw_path.name)
                except Exception:
                    raw_path.unlink(missing_ok=True)
        conn.execute("DELETE FROM upload_requests WHERE uuid=?", (uuid_value,))
        removed += 1
    return removed


def _cleanup_stress_images(conn) -> int:
    marker = f'%"{STRESS_TAG}"%'
    rows = conn.execute(
        """
        SELECT uuid, stored_path, thumb_path, ext, deleted_at
        FROM images
        WHERE deleted_at IS NULL AND tags_json LIKE ?
        """,
        (marker,),
    ).fetchall()
    deleted = 0
    for row in rows:
        if row["deleted_at"]:
            continue
        uuid_value = row["uuid"]
        raw_path = config.STORAGE / row["stored_path"] if row["stored_path"] else None
        trash_path = ""
        ext = row["ext"] or ""
        if raw_path and raw_path.exists():
            try:
                trash_path = str(
                    storage.move_to_trash(raw_path, f"{uuid_value}{ext}").relative_to(config.STORAGE)
                )
            except Exception:
                raw_path.unlink(missing_ok=True)
        thumb_path = row["thumb_path"]
        if thumb_path:
            try:
                (config.STORAGE / thumb_path).unlink(missing_ok=True)
            except Exception:
                pass
        now = datetime.datetime.utcnow()
        purge_after = now + datetime.timedelta(days=config.TRASH_RETENTION_DAYS)
        conn.execute(
            """
            UPDATE images
            SET deleted_at=?, trash_path=?, purge_after=?, updated_at=CURRENT_TIMESTAMP
            WHERE uuid=?
            """,
            (now.isoformat(), trash_path, purge_after.isoformat(), uuid_value),
        )
        deleted += 1
    return deleted


def _delete_pending_stress_request(uuid_value: str) -> None:
    for ext in set(config.ALLOWED_MIME.values()):
        raw_path = config.RAW_DIR / f"{uuid_value}{ext}"
        if raw_path.exists():
            try:
                storage.move_to_trash(raw_path, raw_path.name)
            except Exception:
                raw_path.unlink(missing_ok=True)
    with db.transaction() as conn:
        conn.execute("DELETE FROM upload_requests WHERE uuid=?", (uuid_value,))


def _delete_stress_image_row(row: Dict[str, Any]) -> None:
    uuid_value = row.get("uuid")
    if not uuid_value:
        return
    raw_path = config.STORAGE / row["stored_path"] if row.get("stored_path") else None
    trash_path = ""
    ext = row.get("ext") or ""
    if raw_path and raw_path.exists():
        try:
            trash_path = str(storage.move_to_trash(raw_path, f"{uuid_value}{ext}").relative_to(config.STORAGE))
        except Exception:
            raw_path.unlink(missing_ok=True)
    thumb_path = row.get("thumb_path")
    if thumb_path:
        try:
            (config.STORAGE / thumb_path).unlink(missing_ok=True)
        except Exception:
            pass
    now = datetime.datetime.utcnow()
    purge_after = now + datetime.timedelta(days=config.TRASH_RETENTION_DAYS)
    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE images
            SET deleted_at=?, trash_path=?, purge_after=?, updated_at=CURRENT_TIMESTAMP
            WHERE uuid=?
            """,
            (now.isoformat(), trash_path, purge_after.isoformat(), uuid_value),
        )


def _run_stress_cleanup_task(task_id: str) -> None:
    deleted = 0
    pending_removed = 0
    try:
        db.ensure_schema()
        with db.connect() as conn:
            pending = _list_pending_stress_requests(conn)
            images = _list_stress_images(conn)
        total = len(pending) + len(images)
        _update_stress_task(
            task_id,
            stage="deleting",
            total=total,
            done=0,
            deleted=0,
            pending_removed=0,
            message="清理中",
        )
        for uuid_value in pending:
            _delete_pending_stress_request(uuid_value)
            pending_removed += 1
            _update_stress_task(
                task_id,
                done=deleted + pending_removed,
                pending_removed=pending_removed,
                deleted=deleted,
                message=f"已删除 {deleted} 张，清理待处理 {pending_removed} 张",
            )
        for row in images:
            _delete_stress_image_row(row)
            deleted += 1
            _update_stress_task(
                task_id,
                done=deleted + pending_removed,
                pending_removed=pending_removed,
                deleted=deleted,
                message=f"已删除 {deleted} 张，清理待处理 {pending_removed} 张",
            )
        if deleted or pending_removed:
            _touch_rebuild_flag("stress_cleanup")
        _update_stress_task(
            task_id,
            stage="completed",
            message=f"已删除 {deleted} 张，清理待处理 {pending_removed} 张",
        )
    except Exception as exc:  # noqa: BLE001
        _update_stress_task(task_id, stage="failed", message=f"清理失败: {exc}")


def _parse_upload_form() -> Tuple[Optional[dict], Optional[str]]:
    title = str(request.form.get("title") or "").strip()
    description = str(request.form.get("description") or "").strip()
    tags_raw = request.form.get("tags")
    collection = str(request.form.get("collection") or "").strip()

    tags, err = _parse_tags_input(tags_raw, require_registered=True, require_hash=True)
    if err:
        return None, err
    missing_parents = _missing_parent_tags(tags or [])
    if missing_parents:
        return None, f"缺少父标签: {', '.join(missing_parents)}"

    collections_meta, default_collection, _ = static_site.load_collections_config()
    if collection and collection not in collections_meta and collection != "auto":
        return None, "分区不存在"
    if collection == "auto" or not collection:
        collection = ""

    payload = {
        "title": title or None,
        "description": description or None,
        "tags_json": json.dumps(tags or [], ensure_ascii=False),
        "collection_override": collection or None,
    }
    return payload, None


def _load_tags_from_row(row: Dict[str, Any], alias_map: Optional[Dict[str, str]] = None) -> List[str]:
    return tagging.parse_tags_json(row.get("tags_json"), alias_map, drop_unknown=True)


def _load_collections_meta() -> Tuple[List[Dict[str, str]], str]:
    meta, default_collection, order = static_site.load_collections_config()
    items = []
    for key in order:
        info = meta.get(key)
        if not info:
            continue
        items.append(
            {
                "slug": key,
                "title": info.get("title") or key,
                "description": info.get("description") or "",
            }
        )
    return items, default_collection


def _normalize_registration_mode(mode: str) -> Optional[str]:
    value = (mode or "").strip().lower()
    if value in {"open", "invite", "closed"}:
        return value
    return None


@bp.post("/upload/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    auth.bootstrap_admin_if_needed()
    user = auth.authenticate(username, password, required_group=config.ADMIN_GROUP)
    if not user:
        if not auth.has_any_users():
            return _json_error("未配置管理员账号，请先创建用户", 503)
        return _json_error("账号或密码错误", 401)
    serializer = _serializer()
    token = serializer.dumps({"u": user.username})
    resp = jsonify({"ok": True, "user": user.username})
    _set_admin_cookie(resp, token)
    return resp


@bp.post("/upload/admin/logout")
def admin_logout():
    resp = jsonify({"ok": True})
    _clear_admin_cookie(resp)
    return resp


@bp.get("/upload/admin/me")
def admin_me():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    return jsonify({"ok": True, "user": user})


@bp.get("/upload/admin/collections")
def admin_collections():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    collections, default_collection = _load_collections_meta()
    return jsonify({"ok": True, "collections": collections, "default_collection": default_collection})


@bp.post("/upload/admin/collections")
def admin_update_collections():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    collections = payload.get("collections")
    default_collection = str(payload.get("default_collection") or "").strip()
    if not isinstance(collections, list) or not collections:
        return _json_error("分区列表不能为空")
    cleaned: List[Dict[str, str]] = []
    slugs = []
    for item in collections:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if not slug or not title:
            return _json_error("分区 slug 与标题不能为空")
        if slug in slugs:
            return _json_error(f"分区 slug 重复: {slug}")
        slugs.append(slug)
        cleaned.append({"slug": slug, "title": title, "description": description})
    if default_collection not in slugs:
        default_collection = slugs[0]

    data = {
        "default_collection": default_collection,
        "collections": {item["slug"]: {"title": item["title"], "description": item["description"], "uuids": []} for item in cleaned},
        "order": slugs,
    }
    cfg_path = config.STATIC / "data" / "collections.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(cfg_path)
    try:
        storage.fsync_path(cfg_path.parent)
    except Exception:
        pass
    _touch_rebuild_flag("collections_updated")
    return jsonify({"ok": True, "collections": cleaned, "default_collection": default_collection})


@bp.get("/upload/admin/auth-config")
def admin_get_auth_config():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    return jsonify(
        {
            "ok": True,
            "registration_mode": config.AUTH_REGISTRATION_MODE,
        }
    )


@bp.post("/upload/admin/auth-config")
def admin_update_auth_config():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    mode = _normalize_registration_mode(str(payload.get("registration_mode") or ""))
    if not mode:
        return _json_error("注册模式不正确")
    config.update_auth_config({"registration_mode": mode})
    _touch_rebuild_flag("auth_config_updated")
    return jsonify({"ok": True, "registration_mode": config.AUTH_REGISTRATION_MODE})


@bp.get("/upload/admin/invites")
def admin_list_invites():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, code_prefix, max_uses, used_count, note, is_active, created_by, created_at, expires_at
            FROM auth_invites
            ORDER BY created_at DESC
            """
        ).fetchall()
    invites = []
    for row in rows:
        invites.append(
            {
                "id": row["id"],
                "code_prefix": row["code_prefix"],
                "max_uses": row["max_uses"],
                "used_count": row["used_count"],
                "note": row["note"] or "",
                "is_active": bool(row["is_active"]),
                "created_by": row["created_by"] or "",
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
            }
        )
    return jsonify({"ok": True, "invites": invites})


@bp.post("/upload/admin/invites")
def admin_create_invite():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    note = str(payload.get("note") or "").strip()
    max_uses_raw = payload.get("max_uses", None)
    max_uses = None
    if max_uses_raw not in (None, ""):
        max_uses = _parse_positive_int(max_uses_raw)
        if not max_uses:
            return _json_error("最大使用次数必须大于 0")
    expires_at, err = _parse_invite_expires_at(payload.get("expires_at"))
    if err:
        return _json_error(err)
    code = str(payload.get("code") or "").strip()
    if not code:
        code = secrets.token_urlsafe(12)
    db.ensure_schema()
    try:
        with db.transaction() as conn:
            invite_id = auth.create_invite(
                code,
                max_uses=max_uses,
                note=note,
                created_by=user,
                expires_at=expires_at,
                conn=conn,
            )
            row = conn.execute(
                """
                SELECT id, code_prefix, max_uses, used_count, note, is_active, created_by, created_at, expires_at
                FROM auth_invites
                WHERE id=?
                """,
                (invite_id,),
            ).fetchone()
    except ValueError as exc:
        return _json_error(str(exc))
    invite = {
        "id": row["id"],
        "code_prefix": row["code_prefix"],
        "max_uses": row["max_uses"],
        "used_count": row["used_count"],
        "note": row["note"] or "",
        "is_active": bool(row["is_active"]),
        "created_by": row["created_by"] or "",
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    }
    resp = jsonify({"ok": True, "code": code, "invite": invite})
    resp.status_code = 201
    return resp


@bp.post("/upload/admin/invites/<int:invite_id>/disable")
def admin_disable_invite(invite_id: int):
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    with db.transaction() as conn:
        auth.ensure_schema(conn)
        result = conn.execute(
            "UPDATE auth_invites SET is_active=0 WHERE id=?",
            (invite_id,),
        )
        if result.rowcount == 0:
            return _json_error("邀请码不存在", 404)
    return jsonify({"ok": True})


@bp.post("/upload/admin/upload")
def admin_upload():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    if storage.upload_paused():
        return _json_error("上传已暂停：磁盘保护", 503)
    if not storage.disk_has_space(config.STORAGE):
        return _json_error("磁盘空间不足，已暂停上传", 503)

    payload, err = _parse_upload_form()
    if err:
        return _json_error(err)

    file = request.files.get("file")
    if not file or not file.stream:
        return _json_error("缺少文件")

    original_name = file.filename or "upload"
    file_mime = file.mimetype or ""
    if file_mime and file_mime not in config.ALLOWED_MIME:
        return _json_error("不支持的文件类型")
    ext_from_name = Path(original_name).suffix.lower()
    if ext_from_name and ext_from_name not in config.ALLOWED_MIME.values():
        return _json_error("不支持的文件扩展名")

    owner_id = _get_user_id(user)
    if not owner_id:
        return _json_error("管理员账号不存在", 500)

    upload_uuid = uuid.uuid4().hex
    tmp_path = config.UPLOAD_TMP / f"{upload_uuid}.part"

    try:
        bytes_written, sha256 = storage.write_stream_to_tmp(file.stream, tmp_path)
    except ValueError as exc:
        storage.move_to_quarantine(tmp_path, f"size_error: {exc}")
        return _json_error(str(exc), 413)
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"write_error: {exc}")
        return _json_error("写入失败", 500)

    mime = storage.detect_mime(tmp_path)
    ext = _allowed_extension_from_mime(mime or "")
    if not ext:
        storage.move_to_quarantine(tmp_path, f"mime_not_allowed: {mime}")
        return _json_error("不支持的文件类型")

    try:
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO upload_requests (uuid, owner_user_id, title, description, tags_json, collection_override)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_uuid,
                    owner_id,
                    payload["title"],
                    payload["description"],
                    payload["tags_json"],
                    payload["collection_override"],
                ),
            )
    except Exception:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, "meta_error")
        return _json_error("记录上传信息失败", 500)

    raw_name = f"{upload_uuid}{ext}"
    raw_path = config.RAW_DIR / raw_name
    try:
        storage.atomic_move(tmp_path, raw_path)
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"move_error: {exc}")
        with db.transaction() as conn:
            conn.execute("DELETE FROM upload_requests WHERE uuid=?", (upload_uuid,))
        return _json_error("提交失败", 500)

    try:
        db.insert_audit("admin_upload_committed", upload_uuid, f"user={user}")
    except Exception:
        pass

    return jsonify(
        {
            "ok": True,
            "uuid": upload_uuid,
            "original_name": original_name,
            "stored": str(raw_path.relative_to(config.STORAGE)),
            "bytes": bytes_written,
            "sha256": sha256,
            "mime": mime,
        }
    ), 201


@bp.get("/upload/admin/upload/status")
def admin_upload_status():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    owner_id = _get_user_id(user)
    if not owner_id:
        return _json_error("管理员账号不存在", 500)
    uuid_value = _normalize_upload_uuid(request.args.get("uuid") or "")
    if not uuid_value:
        return _json_error("参数错误", 400)
    status = _resolve_upload_status(uuid_value, owner_id)
    resp = jsonify({"ok": True, **status})
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.post("/upload/admin/stress/generate")
def admin_stress_generate():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    if storage.upload_paused():
        return _json_error("上传已暂停：磁盘保护", 503)
    if not storage.disk_has_space(config.STORAGE):
        return _json_error("磁盘空间不足，已暂停上传", 503)

    owner_id = _get_user_id(user)
    if not owner_id:
        return _json_error("管理员账号不存在", 500)

    payload = request.get_json(silent=True) or {}
    index = _parse_positive_int(payload.get("index"))
    total = _parse_positive_int(payload.get("total"))
    if total and index and index > total:
        total = index
    title = _format_stress_title(index, total)
    description = _format_stress_description(index, total)

    upload_uuid = uuid.uuid4().hex
    tmp_path = config.UPLOAD_TMP / f"{upload_uuid}.part"
    try:
        image_bytes, width, height = _generate_stress_image()
        bytes_written, sha256 = storage.write_stream_to_tmp(io.BytesIO(image_bytes), tmp_path)
    except ValueError as exc:
        storage.move_to_quarantine(tmp_path, f"size_error: {exc}")
        return _json_error(str(exc), 413)
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"write_error: {exc}")
        return _json_error("写入失败", 500)

    mime = "image/png"
    ext = _allowed_extension_from_mime(mime) or ".png"
    if ext not in config.ALLOWED_MIME.values():
        storage.move_to_quarantine(tmp_path, "stress_ext_not_allowed")
        return _json_error("不支持的文件类型")

    try:
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO upload_requests (uuid, owner_user_id, title, description, tags_json, collection_override)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_uuid,
                    owner_id,
                    title,
                    description,
                    json.dumps([STRESS_TAG], ensure_ascii=False),
                    None,
                ),
            )
    except Exception:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, "meta_error")
        return _json_error("记录上传信息失败", 500)

    raw_name = f"{upload_uuid}{ext}"
    raw_path = config.RAW_DIR / raw_name
    try:
        storage.atomic_move(tmp_path, raw_path)
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"move_error: {exc}")
        with db.transaction() as conn:
            conn.execute("DELETE FROM upload_requests WHERE uuid=?", (upload_uuid,))
        return _json_error("提交失败", 500)

    try:
        db.insert_audit("admin_stress_generate", upload_uuid, f"user={user}")
    except Exception:
        pass

    return jsonify(
        {
            "ok": True,
            "uuid": upload_uuid,
            "bytes": bytes_written,
            "sha256": sha256,
            "mime": mime,
            "width": width,
            "height": height,
            "index": index,
            "total": total,
        }
    ), 201


@bp.post("/upload/admin/stress/cleanup/start")
def admin_stress_cleanup_start():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    with db.connect() as conn:
        total = _count_pending_stress_requests(conn) + _count_stress_images(conn)
    task = _create_stress_task(total)
    if total <= 0:
        _update_stress_task(task["task_id"], stage="completed", message="没有可清理的压测图片")
        return jsonify(
            {
                "ok": True,
                "task_id": task["task_id"],
                "total": 0,
                "stage": "completed",
                "message": "没有可清理的压测图片",
            }
        )
    _update_stress_task(task["task_id"], stage="deleting", message="清理中")
    thread = threading.Thread(target=_run_stress_cleanup_task, args=(task["task_id"],), daemon=True)
    thread.start()
    return jsonify(
        {
            "ok": True,
            "task_id": task["task_id"],
            "total": int(total),
            "stage": "deleting",
        }
    )


@bp.get("/upload/admin/stress/cleanup/status")
def admin_stress_cleanup_status():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    task_id = str(request.args.get("task_id") or "").strip()
    task = _get_stress_task(task_id)
    if not task:
        return _json_error("任务不存在", 404)
    total = int(task.get("total") or 0)
    done = int(task.get("done") or 0)
    percent = 0
    if total > 0:
        percent = min(100, max(0, round(done * 100 / total)))
    resp = jsonify(
        {
            "ok": True,
            "task_id": task_id,
            "stage": task.get("stage") or "queued",
            "total": total,
            "done": done,
            "percent": percent,
            "message": task.get("message") or "",
            "deleted": int(task.get("deleted") or 0),
            "pending_removed": int(task.get("pending_removed") or 0),
        }
    )
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.post("/upload/admin/stress/cleanup")
def admin_stress_cleanup():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    with db.transaction() as conn:
        pending_removed = _cleanup_pending_stress_requests(conn)
        deleted = _cleanup_stress_images(conn)
    if deleted or pending_removed:
        _touch_rebuild_flag("stress_cleanup")
    try:
        db.insert_audit("admin_stress_cleanup", "", f"user={user}")
    except Exception:
        pass
    return jsonify({"ok": True, "deleted": deleted, "pending_removed": pending_removed})


@bp.get("/upload/admin/images")
def admin_images():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    status = (request.args.get("status") or "active").lower()
    query = (request.args.get("q") or "").strip()
    collection_filter = (request.args.get("collection") or "all").strip()
    try:
        page = max(1, int(request.args.get("p") or request.args.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    page_size = 40
    where = "deleted_at IS NULL" if status != "trash" else "deleted_at IS NOT NULL"
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id AS image_id, uuid, original_name, ext, bytes, width, height, thumb_width, thumb_height,
                   sha256, dominant_color, created_at, thumb_path, stored_path,
                   title_override, description, tags_json, collection_override, deleted_at, trash_path
            FROM images
            WHERE {where}
            ORDER BY created_at DESC
            """
        ).fetchall()

    alias_map = _load_alias_map()
    collections_meta, default_collection, _ = static_site.load_collections_config()
    items = []
    for row in rows:
        row_dict = dict(row)
        uuid = row_dict["uuid"]
        tags = _load_tags_from_row(row_dict, alias_map)
        title = row_dict.get("title_override") or static_site.simple_title(row_dict.get("original_name") or "")
        collection_override = row_dict.get("collection_override")
        collection = collection_override or default_collection
        if not collection_override:
            for key, meta in collections_meta.items():
                if uuid in meta.get("uuids", set()):
                    collection = key
                    break
        thumb_path_value = row_dict.get("thumb_path")
        thumb_name = Path(thumb_path_value).name if thumb_path_value else ""
        item = {
            "uuid": uuid,
            "image_id": row_dict.get("image_id"),
            "detail_path": static_site.image_detail_path(row_dict.get("image_id"), uuid),
            "title": title,
            "description": row_dict.get("description") or "",
            "tags": tags,
            "collection": collection,
            "original_name": row_dict.get("original_name") or "",
            "raw_filename": f"{uuid}{row_dict.get('ext') or ''}",
            "thumb_filename": thumb_name,
            "bytes_human": static_site.human_bytes(int(row_dict.get("bytes") or 0)),
            "width": row_dict.get("width"),
            "height": row_dict.get("height"),
            "thumb_width": row_dict.get("thumb_width"),
            "thumb_height": row_dict.get("thumb_height"),
            "dominant_color": row_dict.get("dominant_color"),
            "created_at": row_dict.get("created_at"),
            "orientation": static_site.classify_orientation(row_dict.get("width"), row_dict.get("height")),
            "size_bucket": static_site.size_bucket(row_dict.get("width"), row_dict.get("height")),
            "deleted_at": row_dict.get("deleted_at"),
            "trash_path": row_dict.get("trash_path"),
        }
        items.append(item)

    def matches_filter(item: dict) -> bool:
        if collection_filter and collection_filter != "all":
            if item.get("collection") != collection_filter:
                return False
        if not query:
            return True
        term = query.lower()
        if term.startswith("#"):
            term = term[1:].strip()
            if not term:
                return True
            return any(term in str(tag).lower() for tag in (item.get("tags") or []))
        hay = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
        if term in hay:
            return True
        return any(term in str(tag).lower() for tag in (item.get("tags") or []))

    filtered_items = [item for item in items if matches_filter(item)]
    total = len(filtered_items)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = filtered_items[start:end]
    collections, default_collection = _load_collections_meta()
    return jsonify(
        {
            "ok": True,
            "images": paged_items,
            "collections": collections,
            "default_collection": default_collection,
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": pages,
        }
    )


@bp.post("/upload/admin/images/<uuid>/update")
def admin_update_image(uuid: str):
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    collection = str(payload.get("collection") or "").strip()
    tags_raw = payload.get("tags")
    tags, err = _parse_tags_input(tags_raw, require_registered=True)
    if err:
        return _json_error(err)
    missing_parents = _missing_parent_tags(tags or [])
    if missing_parents:
        return _json_error(f"缺少父标签: {', '.join(missing_parents)}")
    collections_meta, default_collection, _ = static_site.load_collections_config()
    if collection and collection not in collections_meta:
        return _json_error("分区不存在")
    if collection == "auto" or not collection:
        collection = ""

    db.ensure_schema()
    with db.transaction() as conn:
        row = conn.execute("SELECT uuid FROM images WHERE uuid=?", (uuid,)).fetchone()
        if not row:
            return _json_error("作品不存在", 404)
        conn.execute(
            """
            UPDATE images
            SET title_override=?, description=?, tags_json=?, collection_override=?, updated_at=CURRENT_TIMESTAMP
            WHERE uuid=?
            """,
            (
                title or None,
                description or None,
                json.dumps(tags or [], ensure_ascii=False),
                collection or None,
                uuid,
            ),
        )
    _touch_rebuild_flag("image_metadata_updated")
    try:
        db.insert_audit("admin_update_image", uuid, user)
    except Exception:
        pass
    return jsonify({"ok": True})


@bp.post("/upload/admin/images/<uuid>/delete")
def admin_delete_image(uuid: str):
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT stored_path, thumb_path, ext, deleted_at FROM images WHERE uuid=?",
            (uuid,),
        ).fetchone()
        if not row:
            return _json_error("作品不存在", 404)
        if row["deleted_at"]:
            return _json_error("作品已删除", 409)
        raw_path = config.STORAGE / row["stored_path"]
        trash_name = f"{uuid}{row['ext'] or ''}"
        trash_path = ""
        if raw_path.exists():
            trash_path = str(storage.move_to_trash(raw_path, trash_name).relative_to(config.STORAGE))
        thumb_path = row["thumb_path"]
        if thumb_path:
            try:
                (config.STORAGE / thumb_path).unlink(missing_ok=True)
            except Exception:
                pass
        now = datetime.datetime.utcnow()
        purge_after = now + datetime.timedelta(days=config.TRASH_RETENTION_DAYS)
        conn.execute(
            """
            UPDATE images
            SET deleted_at=?, trash_path=?, purge_after=?, updated_at=CURRENT_TIMESTAMP
            WHERE uuid=?
            """,
            (now.isoformat(), trash_path, purge_after.isoformat(), uuid),
        )
    _touch_rebuild_flag("image_deleted")
    try:
        db.insert_audit("admin_delete_image", uuid, user)
    except Exception:
        pass
    return jsonify({"ok": True})


def _safe_unlink(path: Optional[Path]) -> None:
    if not path:
        return
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _purge_trash_rows(conn, rows: List[Any]) -> int:
    uuids: List[str] = []
    for row in rows:
        row_dict = dict(row)
        uuid_value = row_dict.get("uuid")
        if not uuid_value:
            continue
        uuids.append(str(uuid_value))
        trash_path = row_dict.get("trash_path")
        stored_path = row_dict.get("stored_path")
        thumb_path = row_dict.get("thumb_path")
        if trash_path:
            _safe_unlink(config.STORAGE / trash_path)
        if stored_path:
            _safe_unlink(config.STORAGE / stored_path)
        if thumb_path:
            _safe_unlink(config.STORAGE / thumb_path)
    if not uuids:
        return 0
    placeholders = ",".join(["?"] * len(uuids))
    conn.execute(f"DELETE FROM jobs WHERE image_uuid IN ({placeholders})", uuids)
    conn.execute(f"DELETE FROM images WHERE uuid IN ({placeholders})", uuids)
    return len(uuids)


def _purge_trash_by_uuids(conn, uuids: Optional[List[str]]) -> int:
    if uuids is not None:
        if not uuids:
            return 0
        placeholders = ",".join(["?"] * len(uuids))
        rows = conn.execute(
            f"""
            SELECT uuid, stored_path, thumb_path, trash_path
            FROM images
            WHERE deleted_at IS NOT NULL AND uuid IN ({placeholders})
            """,
            uuids,
        ).fetchall()
        return _purge_trash_rows(conn, rows)

    deleted = 0
    cursor = conn.execute(
        """
        SELECT uuid, stored_path, thumb_path, trash_path
        FROM images
        WHERE deleted_at IS NOT NULL
        """
    )
    while True:
        batch = cursor.fetchmany(200)
        if not batch:
            break
        deleted += _purge_trash_rows(conn, batch)
    return deleted


@bp.post("/upload/admin/images/trash/purge")
def admin_purge_trash():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    uuids_raw = payload.get("uuids")
    uuids: Optional[List[str]] = None
    if uuids_raw is not None:
        if not isinstance(uuids_raw, list):
            return _json_error("参数错误")
        uuids = [str(item).strip() for item in uuids_raw if str(item).strip()]
    db.ensure_schema()
    with db.transaction() as conn:
        deleted = _purge_trash_by_uuids(conn, uuids)
    try:
        db.insert_audit("admin_purge_trash", f"deleted={deleted}", user)
    except Exception:
        pass
    return jsonify({"ok": True, "deleted": deleted})


@bp.get("/upload/admin/tags")
def admin_tags():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    meta, order = tagging.load_tags_config()
    alias_map = tagging.build_alias_map(meta)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT tags_json FROM images WHERE deleted_at IS NULL"
        ).fetchall()
    counts: Dict[str, int] = {}
    for row in rows:
        for tag in _load_tags_from_row(dict(row), alias_map):
            counts[tag] = counts.get(tag, 0) + 1
    ordered = (order or []) + sorted(meta.keys())
    seen = set()
    tags = []
    for tag in ordered:
        if tag in seen:
            continue
        seen.add(tag)
        info = meta.get(tag, {})
        if not info:
            continue
        alias_to = info.get("alias_to") or ""
        canonical = tagging.normalize_tag(alias_to) or tag
        count = counts.get(canonical, 0) if alias_to else counts.get(tag, 0)
        tags.append(
            {
                "tag": tag,
                "count": count,
                "intro": info.get("intro") or "",
                "aliases": info.get("aliases") or [],
                "parents": info.get("parents") or [],
                "slug": info.get("slug") or tagging.safe_tag_slug(tag),
                "alias_to": alias_to,
                "type": info.get("type") or "general",
            }
        )
    return jsonify({"ok": True, "tags": tags})


@bp.get("/upload/admin/tag-types")
def admin_tag_types():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    meta, order = tagging.load_tag_types_config()
    ordered = (order or []) + sorted(meta.keys())
    seen = set()
    types = []
    for tag_type in ordered:
        if tag_type in seen:
            continue
        info = meta.get(tag_type) or {}
        types.append(
            {
                "type": tag_type,
                "label": info.get("label") or tag_type,
                "color": info.get("color") or "#7b8794",
            }
        )
        seen.add(tag_type)
    return jsonify({"ok": True, "types": types})


@bp.post("/upload/admin/tag-types")
def admin_tag_types_update():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    items = payload.get("types")
    if not isinstance(items, list):
        return _json_error("类型列表格式不正确")
    cleaned = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            return _json_error("类型列表格式不正确")
        tag_type = tagging.normalize_tag_type_key(item.get("type") or "")
        if not tag_type:
            return _json_error("类型标识仅允许小写英文、数字、- 与 _")
        if tag_type in seen:
            return _json_error("类型标识不能重复")
        label = str(item.get("label") or item.get("name") or "").strip()
        if not label:
            return _json_error("类型名称不能为空")
        color = tagging.normalize_tag_color(item.get("color"))
        if not color:
            return _json_error("颜色格式不正确（例：#7b8794）")
        cleaned.append({"type": tag_type, "label": label, "color": color})
        seen.add(tag_type)
    if not cleaned:
        return _json_error("至少保留一个类型")
    tagging.save_tag_types_config(cleaned)
    _touch_rebuild_flag("tag_types_updated")
    return jsonify({"ok": True, "types": cleaned})


@bp.post("/upload/admin/tags/meta")
def admin_tags_meta():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    raw_tag = str(payload.get("tag") or "").strip()
    if raw_tag.startswith("#"):
        raw_tag = raw_tag[1:]
    tag = tagging.normalize_tag(raw_tag)
    if not tag:
        return _json_error("标签不能为空")
    intro = str(payload.get("intro") or "").strip()
    aliases = tagging.normalize_aliases(payload.get("aliases"))
    aliases = [alias for alias in aliases if alias != tag]
    parents = tagging.normalize_parents(payload.get("parents"))
    parents = [parent for parent in parents if parent != tag]
    slug_raw = tagging.normalize_slug(payload.get("slug") or "")
    tag_types_meta, tag_types_order = tagging.load_tag_types_config()
    allowed_types = set(tag_types_meta.keys())
    default_type = tagging.default_tag_type(tag_types_meta, tag_types_order)
    tag_type = tagging.normalize_tag_type(payload.get("type"), allowed_types)
    raw_alias_to = str(payload.get("alias_to") or "").strip()
    if raw_alias_to.startswith("#"):
        raw_alias_to = raw_alias_to[1:]
    alias_to = tagging.normalize_tag(raw_alias_to)
    if alias_to == tag:
        alias_to = ""
    meta, order = tagging.load_tags_config()
    existing = meta.get(tag, {})
    slug = slug_raw or (existing.get("slug") or "")
    if not tag_type:
        tag_type = existing.get("type") or default_type
    if not slug:
        return _json_error("URL 名称不能为空")
    if not tagging.is_valid_slug(slug):
        return _json_error("URL 名称仅允许小写英文、数字、- 与 _")
    for existing_tag, info in meta.items():
        if existing_tag == tag:
            continue
        if (info.get("slug") or "") == slug:
            return _json_error("URL 名称已被占用")
    if alias_to:
        target = meta.get(alias_to)
        if not target:
            return _json_error("主标签不存在")
        if target.get("alias_to"):
            return _json_error("主标签不能是别名")
        if parents:
            return _json_error("合并标签不能设置父标签")
        tag_type = target.get("type") or tag_type
    if parents:
        for parent in parents:
            parent_meta = meta.get(parent)
            if not parent_meta:
                return _json_error(f"父标签不存在: {parent}")
            if parent_meta.get("alias_to"):
                return _json_error(f"父标签不能是别名: {parent}")
    meta[tag] = {
        "tag": tag,
        "intro": intro,
        "aliases": aliases,
        "parents": parents,
        "slug": slug,
        "alias_to": alias_to,
        "type": tag_type,
    }
    if tag not in order:
        order.append(tag)
    parent_map = tagging.build_parent_map(meta)
    cycle = tagging.find_parent_cycles(parent_map)
    if cycle:
        return _json_error(f"父子标签存在循环: {' > '.join(cycle)}")
    tagging.save_tags_config(meta, order)
    _touch_rebuild_flag("tag_meta_updated")
    return jsonify({"ok": True, "tag": tag})


@bp.post("/upload/admin/tags/meta/delete")
def admin_tags_meta_delete():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    raw_tag = str(payload.get("tag") or "").strip()
    if raw_tag.startswith("#"):
        raw_tag = raw_tag[1:]
    tag = tagging.normalize_tag(raw_tag)
    if not tag:
        return _json_error("标签不能为空")
    meta, order = tagging.load_tags_config()
    if tag in meta:
        meta.pop(tag, None)
    for info in meta.values():
        if tagging.normalize_tag(info.get("alias_to") or "") == tag:
            info["alias_to"] = ""
    order = [item for item in order if item != tag]
    tagging.save_tags_config(meta, order)
    _touch_rebuild_flag("tag_meta_deleted")
    return jsonify({"ok": True})


@bp.get("/upload/admin/wiki")
def admin_wiki_read():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    markdown = ""
    wiki_path = _wiki_path()
    if wiki_path.exists():
        try:
            markdown = wiki_path.read_text(encoding="utf-8")
        except Exception:
            markdown = ""
    return jsonify({"ok": True, "markdown": markdown})


@bp.post("/upload/admin/wiki")
def admin_wiki_write():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    markdown = str(payload.get("markdown") or "")
    if len(markdown) > 200000:
        return _json_error("Wiki 内容过长")
    wiki_path = _wiki_path()
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = wiki_path.with_suffix(".tmp")
    tmp.write_text(markdown, encoding="utf-8")
    tmp.replace(wiki_path)
    _touch_rebuild_flag("wiki_updated")
    return jsonify({"ok": True})


@bp.post("/upload/admin/tags/rename")
def admin_tags_rename():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    from_tag = str(payload.get("from") or "").strip()
    to_tag = str(payload.get("to") or "").strip()
    tags, err = _parse_tags_input([from_tag, to_tag], apply_aliases=False)
    if err:
        return _json_error(err)
    if len(tags) != 2:
        return _json_error("标签格式不正确")
    old_tag, new_tag = tags[0], tags[1]
    meta, order = tagging.load_tags_config()
    if old_tag not in meta:
        return _json_error("标签未注册")
    if new_tag in meta:
        return _json_error("新标签已存在")

    db.ensure_schema()
    updated = 0
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT uuid, tags_json FROM images WHERE deleted_at IS NULL"
        ).fetchall()
        for row in rows:
            tag_list = _load_tags_from_row(dict(row))
            if old_tag not in tag_list:
                continue
            new_list = []
            for tag in tag_list:
                if tag == old_tag:
                    if new_tag not in new_list:
                        new_list.append(new_tag)
                elif tag not in new_list:
                    new_list.append(tag)
            conn.execute(
                "UPDATE images SET tags_json=?, updated_at=CURRENT_TIMESTAMP WHERE uuid=?",
                (json.dumps(new_list, ensure_ascii=False), row["uuid"]),
            )
            updated += 1
    if old_tag in meta:
        info = meta.pop(old_tag)
        info["tag"] = new_tag
        meta[new_tag] = info
        order = [new_tag if item == old_tag else item for item in order]
        for item in meta.values():
            if tagging.normalize_tag(item.get("alias_to") or "") == old_tag:
                item["alias_to"] = new_tag
        tagging.save_tags_config(meta, order)
    if updated:
        _touch_rebuild_flag("tags_renamed")
    return jsonify({"ok": True, "updated": updated})


@bp.post("/upload/admin/tags/delete")
def admin_tags_delete():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    tag = str(payload.get("tag") or "").strip()
    tags, err = _parse_tags_input([tag], apply_aliases=False)
    if err:
        return _json_error(err)
    if not tags:
        return _json_error("标签不能为空")
    target = tags[0]
    meta, order = tagging.load_tags_config()
    if target in meta:
        meta.pop(target, None)
        for info in meta.values():
            if tagging.normalize_tag(info.get("alias_to") or "") == target:
                info["alias_to"] = ""
        order = [item for item in order if item != target]
        tagging.save_tags_config(meta, order)

    db.ensure_schema()
    updated = 0
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT uuid, tags_json FROM images WHERE deleted_at IS NULL"
        ).fetchall()
        for row in rows:
            tag_list = _load_tags_from_row(dict(row))
            if target not in tag_list:
                continue
            new_list = [t for t in tag_list if t != target]
            conn.execute(
                "UPDATE images SET tags_json=?, updated_at=CURRENT_TIMESTAMP WHERE uuid=?",
                (json.dumps(new_list, ensure_ascii=False), row["uuid"]),
            )
            updated += 1
    if updated:
        _touch_rebuild_flag("tags_deleted")
    return jsonify({"ok": True, "updated": updated})
