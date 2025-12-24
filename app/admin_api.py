import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash

from . import config
from . import db
from . import static_site
from . import storage

bp = Blueprint("admin", __name__)


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


def _verify_admin_password(username: str, password: str) -> bool:
    if not password or username != config.ADMIN_USER:
        return False
    if config.ADMIN_PASSWORD_HASH:
        return check_password_hash(config.ADMIN_PASSWORD_HASH, password)
    if config.ADMIN_PASSWORD:
        return config.ADMIN_PASSWORD == password
    return False


def _require_admin() -> Optional[str]:
    token = request.cookies.get(config.ADMIN_COOKIE_NAME, "")
    if not token:
        return None
    serializer = _serializer()
    try:
        data = serializer.loads(token, max_age=config.ADMIN_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("u")


def _touch_rebuild_flag(reason: str) -> None:
    try:
        config.FORCE_REBUILD_FLAG.write_text(reason, encoding="utf-8")
    except Exception:
        pass


def _parse_tags_input(raw: Any) -> Tuple[Optional[List[str]], Optional[str]]:
    if raw is None:
        return [], None
    values: List[str] = []
    if isinstance(raw, str):
        values = [v for v in raw.replace(",", " ").split(" ") if v.strip()]
    elif isinstance(raw, list):
        values = [str(v) for v in raw if str(v).strip()]
    else:
        return None, "标签格式不正确"

    tags: List[str] = []
    for item in values:
        item = item.strip()
        if not item:
            continue
        if not item.startswith("#"):
            return None, "标签必须以 # 开头"
        name = item[1:].strip()
        if not name:
            continue
        normalized = name.casefold()
        if normalized not in tags:
            tags.append(normalized)
    return tags, None


def _load_tags_from_row(row: Dict[str, Any]) -> List[str]:
    raw = row.get("tags_json")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(t) for t in data if str(t).strip()]
    except Exception:
        return []
    return []


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


@bp.post("/upload/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    if not (config.ADMIN_PASSWORD or config.ADMIN_PASSWORD_HASH):
        return _json_error("未配置管理员口令", 503)
    if not _verify_admin_password(username, password):
        return _json_error("账号或口令错误", 401)
    serializer = _serializer()
    token = serializer.dumps({"u": username})
    resp = jsonify({"ok": True, "user": username})
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


@bp.get("/upload/admin/images")
def admin_images():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    status = (request.args.get("status") or "active").lower()
    where = "deleted_at IS NULL" if status != "trash" else "deleted_at IS NOT NULL"
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT uuid, original_name, ext, bytes, width, height, thumb_width, thumb_height,
                   sha256, dominant_color, created_at, thumb_path, stored_path,
                   title_override, description, tags_json, collection_override, deleted_at, trash_path
            FROM images
            WHERE {where}
            ORDER BY created_at DESC
            """
        ).fetchall()

    collections_meta, default_collection, _ = static_site.load_collections_config()
    items = []
    for row in rows:
        row_dict = dict(row)
        uuid = row_dict["uuid"]
        tags = _load_tags_from_row(row_dict)
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
    collections, default_collection = _load_collections_meta()
    return jsonify(
        {
            "ok": True,
            "images": items,
            "collections": collections,
            "default_collection": default_collection,
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
    tags, err = _parse_tags_input(tags_raw)
    if err:
        return _json_error(err)
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


@bp.get("/upload/admin/tags")
def admin_tags():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    db.ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT tags_json FROM images WHERE deleted_at IS NULL"
        ).fetchall()
    counts: Dict[str, int] = {}
    for row in rows:
        for tag in _load_tags_from_row(dict(row)):
            counts[tag] = counts.get(tag, 0) + 1
    tags = [{"tag": tag, "count": count} for tag, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
    return jsonify({"ok": True, "tags": tags})


@bp.post("/upload/admin/tags/rename")
def admin_tags_rename():
    user = _require_admin()
    if not user:
        return _json_error("未授权", 401)
    payload = request.get_json(silent=True) or {}
    from_tag = str(payload.get("from") or "").strip()
    to_tag = str(payload.get("to") or "").strip()
    tags, err = _parse_tags_input([from_tag, to_tag])
    if err:
        return _json_error(err)
    if len(tags) != 2:
        return _json_error("标签格式不正确")
    old_tag, new_tag = tags[0], tags[1]

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
    tags, err = _parse_tags_input([tag])
    if err:
        return _json_error(err)
    if not tags:
        return _json_error("标签不能为空")
    target = tags[0]

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
