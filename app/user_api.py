import json
import re
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import auth
from . import config
from . import db
from . import static_site
from . import storage
from . import tagging

bp = Blueprint("user", __name__)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.USER_SECRET, salt="gallery-user")


def _json_error(message: str, status: int = 400):
    resp = jsonify({"error": message})
    resp.status_code = status
    return resp


def _is_https_request() -> bool:
    if request.is_secure:
        return True
    proto = request.headers.get("X-Forwarded-Proto", "")
    if proto:
        return proto.split(",")[0].strip().lower() == "https"
    return False


def _require_https():
    if not config.AUTH_REQUIRE_HTTPS:
        return None
    if _is_https_request():
        return None
    return _json_error("仅允许 HTTPS 访问", 403)


def _load_user_from_cookie() -> Optional[auth.AuthUser]:
    token = request.cookies.get(config.USER_COOKIE_NAME, "")
    if not token:
        return None
    serializer = _serializer()
    try:
        data = serializer.loads(token, max_age=config.USER_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    user_id = data.get("id")
    if not user_id:
        return None
    with db.connect() as conn:
        auth.ensure_schema(conn)
        row = conn.execute(
            "SELECT id, username, is_active FROM auth_users WHERE id=?",
            (user_id,),
        ).fetchone()
    if not row or not row["is_active"]:
        return None
    return auth.AuthUser(id=int(row["id"]), username=str(row["username"]), is_active=bool(row["is_active"]))


_UPLOAD_UUID_RE = re.compile(r"^[0-9a-f]{32}$")


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


def _require_user() -> Tuple[Optional[auth.AuthUser], Optional[object]]:
    https_error = _require_https()
    if https_error:
        return None, https_error
    user = _load_user_from_cookie()
    if not user:
        return None, _json_error("未授权", 401)
    return user, None


def _is_admin(user: auth.AuthUser) -> bool:
    return config.ADMIN_GROUP in auth.get_user_groups(user.id)


def _load_alias_map() -> dict:
    meta, _ = tagging.load_tags_config()
    return tagging.build_alias_map(meta)


def _parse_tags_input(raw: Any, *, require_hash: bool = False) -> Tuple[Optional[List[str]], Optional[str]]:
    return tagging.parse_tags_input(
        raw,
        _load_alias_map(),
        require_known=True,
        require_hash=require_hash,
    )


def _missing_parent_tags(tags: List[str]) -> List[str]:
    meta, _ = tagging.load_tags_config()
    alias_map = tagging.build_alias_map(meta)
    parent_map = tagging.build_parent_map(meta, alias_map)
    return tagging.missing_parent_tags(tags, parent_map)


def _load_tags_from_row(row: dict) -> List[str]:
    return tagging.parse_tags_json(row.get("tags_json"), _load_alias_map(), drop_unknown=True)


def _allowed_extension_from_mime(mime: str) -> Optional[str]:
    return config.ALLOWED_MIME.get(mime)


def _resolve_collection(
    row: dict,
    collections_meta: dict,
    default_collection: str,
) -> str:
    collection_override = row.get("collection_override")
    if collection_override:
        return collection_override
    uuid = row.get("uuid")
    for key, meta in collections_meta.items():
        if uuid in meta.get("uuids", set()):
            return key
    return default_collection


def _build_image_item(
    row_dict: dict,
    collections_meta: dict,
    default_collection: str,
) -> dict:
    uuid = row_dict.get("uuid") or ""
    image_id = row_dict.get("image_id")
    tags = _load_tags_from_row(row_dict)
    title = row_dict.get("title_override") or static_site.simple_title(row_dict.get("original_name") or "")
    collection = _resolve_collection(row_dict, collections_meta, default_collection)
    collection_title = collections_meta.get(collection, {}).get("title", collection)
    thumb_path_value = row_dict.get("thumb_path")
    thumb_name = Path(thumb_path_value).name if thumb_path_value else ""
    item = {
        "uuid": uuid,
        "image_id": image_id,
        "detail_path": static_site.image_detail_path(image_id, uuid),
        "title": title,
        "description": row_dict.get("description") or "",
        "tags": tags,
        "collection": collection,
        "collection_title": collection_title,
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
    }
    if row_dict.get("favorited_at"):
        item["favorited_at"] = row_dict.get("favorited_at")
    if row_dict.get("added_at"):
        item["added_at"] = row_dict.get("added_at")
    return item


def _parse_upload_form() -> Tuple[Optional[dict], Optional[str]]:
    title = str(request.form.get("title") or "").strip()
    description = str(request.form.get("description") or "").strip()
    tags_raw = request.form.get("tags")
    collection = str(request.form.get("collection") or "").strip()

    tags, err = _parse_tags_input(tags_raw, require_hash=True)
    if err:
        return None, err
    missing_parents = _missing_parent_tags(tags or [])
    if missing_parents:
        return None, f"缺少父标签: {', '.join(missing_parents)}"

    collections_meta, _, _ = static_site.load_collections_config()
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


@bp.post("/api/upload")
def user_upload():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
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
                    user.id,
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
        db.insert_audit("user_upload_committed", upload_uuid, f"user={user.username}")
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


@bp.get("/api/upload/status")
def user_upload_status():
    user, err = _require_user()
    if err:
        return err
    uuid_value = _normalize_upload_uuid(request.args.get("uuid") or "")
    if not uuid_value:
        return _json_error("参数错误", 400)
    status = _resolve_upload_status(uuid_value, user.id)
    resp = jsonify({"ok": True, **status})
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.get("/api/my/images")
def my_images():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id AS image_id, uuid, original_name, ext, bytes, width, height, thumb_width, thumb_height,
                   dominant_color, created_at, thumb_path, stored_path,
                   title_override, description, tags_json, collection_override
            FROM images
            WHERE deleted_at IS NULL AND owner_user_id=?
            ORDER BY created_at DESC
            """,
            (user.id,),
        ).fetchall()

    collections_meta, default_collection, _ = static_site.load_collections_config()
    items = []
    for row in rows:
        item = _build_image_item(dict(row), collections_meta, default_collection)
        items.append(item)

    collections, default_collection = _load_collections_list()
    return jsonify(
        {
            "ok": True,
            "images": items,
            "collections": collections,
            "default_collection": default_collection,
        }
    )


def _load_collections_list() -> Tuple[List[dict], str]:
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


@bp.get("/api/favorites")
def list_favorites():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT i.id AS image_id,
                   f.image_uuid AS uuid,
                   f.created_at AS favorited_at,
                   i.original_name, i.ext, i.bytes, i.width, i.height,
                   i.thumb_width, i.thumb_height, i.dominant_color, i.created_at,
                   i.thumb_path, i.stored_path,
                   i.title_override, i.description, i.tags_json, i.collection_override
            FROM user_favorites f
            JOIN images i ON i.uuid = f.image_uuid
            WHERE f.user_id=? AND i.deleted_at IS NULL
            ORDER BY f.created_at DESC
            """,
            (user.id,),
        ).fetchall()

    collections_meta, default_collection, _ = static_site.load_collections_config()
    items = []
    for row in rows:
        item = _build_image_item(dict(row), collections_meta, default_collection)
        items.append(item)
    return jsonify({"ok": True, "images": items, "total": len(items)})


@bp.post("/api/favorites/<uuid>/toggle")
def toggle_favorite(uuid: str):
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT uuid, deleted_at FROM images WHERE uuid=?",
            (uuid,),
        ).fetchone()
    if not row:
        return _json_error("作品不存在", 404)
    if row["deleted_at"]:
        return _json_error("作品已删除", 409)

    status = "added"
    with db.transaction() as conn:
        exists = conn.execute(
            "SELECT 1 FROM user_favorites WHERE user_id=? AND image_uuid=?",
            (user.id, uuid),
        ).fetchone()
        if exists:
            conn.execute(
                "DELETE FROM user_favorites WHERE user_id=? AND image_uuid=?",
                (user.id, uuid),
            )
            status = "removed"
        else:
            conn.execute(
                "INSERT INTO user_favorites (user_id, image_uuid) VALUES (?, ?)",
                (user.id, uuid),
            )
    return jsonify({"ok": True, "status": status})


def _load_gallery(conn, gallery_id: int, user_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT id, title, description, cover_uuid, created_at, updated_at
        FROM user_galleries
        WHERE id=? AND user_id=?
        """,
        (gallery_id, user_id),
    ).fetchone()
    return dict(row) if row else None


@bp.get("/api/galleries")
def list_galleries():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.title, g.description, g.cover_uuid, g.created_at, g.updated_at,
                   COUNT(gi.image_uuid) AS count
            FROM user_galleries g
            LEFT JOIN user_gallery_images gi ON g.id = gi.gallery_id
            WHERE g.user_id=?
            GROUP BY g.id
            ORDER BY g.updated_at DESC
            """,
            (user.id,),
        ).fetchall()
    galleries = []
    for row in rows:
        item = dict(row)
        item["count"] = int(item.get("count") or 0)
        galleries.append(item)
    return jsonify({"ok": True, "galleries": galleries})


@bp.post("/api/galleries")
def create_gallery():
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not title:
        return _json_error("画廊名称不能为空")
    db.ensure_schema()
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO user_galleries (user_id, title, description)
            VALUES (?, ?, ?)
            """,
            (user.id, title, description or None),
        )
        gallery_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({"ok": True, "id": gallery_id})


@bp.post("/api/galleries/<int:gallery_id>/update")
def update_gallery(gallery_id: int):
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not title:
        return _json_error("画廊名称不能为空")
    db.ensure_schema()
    with db.transaction() as conn:
        gallery = _load_gallery(conn, gallery_id, user.id)
        if not gallery:
            return _json_error("画廊不存在", 404)
        conn.execute(
            """
            UPDATE user_galleries
            SET title=?, description=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND user_id=?
            """,
            (title, description or None, gallery_id, user.id),
        )
    return jsonify({"ok": True})


@bp.post("/api/galleries/<int:gallery_id>/delete")
def delete_gallery(gallery_id: int):
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.transaction() as conn:
        gallery = _load_gallery(conn, gallery_id, user.id)
        if not gallery:
            return _json_error("画廊不存在", 404)
        conn.execute(
            "DELETE FROM user_galleries WHERE id=? AND user_id=?",
            (gallery_id, user.id),
        )
    return jsonify({"ok": True})


@bp.get("/api/galleries/<int:gallery_id>/images")
def gallery_images(gallery_id: int):
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        gallery = _load_gallery(conn, gallery_id, user.id)
        if not gallery:
            return _json_error("画廊不存在", 404)
        rows = conn.execute(
            """
            SELECT i.id AS image_id,
                   i.uuid, i.original_name, i.ext, i.bytes, i.width, i.height,
                   i.thumb_width, i.thumb_height, i.dominant_color, i.created_at,
                   i.thumb_path, i.stored_path,
                   i.title_override, i.description, i.tags_json, i.collection_override,
                   gi.created_at AS added_at
            FROM user_gallery_images gi
            JOIN images i ON i.uuid = gi.image_uuid
            WHERE gi.gallery_id=? AND i.deleted_at IS NULL
            ORDER BY gi.position DESC, gi.created_at DESC
            """,
            (gallery_id,),
        ).fetchall()

    collections_meta, default_collection, _ = static_site.load_collections_config()
    items = []
    for row in rows:
        item = _build_image_item(dict(row), collections_meta, default_collection)
        items.append(item)
    return jsonify({"ok": True, "gallery": gallery, "images": items})


@bp.post("/api/galleries/<int:gallery_id>/items")
def update_gallery_items(gallery_id: int):
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    uuid = str(payload.get("uuid") or "").strip()
    action = str(payload.get("action") or "add").strip().lower()
    if not uuid:
        return _json_error("作品不能为空")
    db.ensure_schema()
    with db.connect() as conn:
        gallery = _load_gallery(conn, gallery_id, user.id)
        if not gallery:
            return _json_error("画廊不存在", 404)
        row = conn.execute(
            "SELECT uuid, deleted_at FROM images WHERE uuid=?",
            (uuid,),
        ).fetchone()
    if not row:
        return _json_error("作品不存在", 404)
    if row["deleted_at"]:
        return _json_error("作品已删除", 409)

    with db.transaction() as conn:
        if action == "remove":
            conn.execute(
                "DELETE FROM user_gallery_images WHERE gallery_id=? AND image_uuid=?",
                (gallery_id, uuid),
            )
            status = "removed"
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_gallery_images (gallery_id, image_uuid)
                VALUES (?, ?)
                """,
                (gallery_id, uuid),
            )
            status = "added"
    return jsonify({"ok": True, "status": status})


@bp.get("/api/images/<uuid>")
def image_meta(uuid: str):
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT id AS image_id, uuid, original_name, title_override, description, tags_json, collection_override, owner_user_id, deleted_at
            FROM images
            WHERE uuid=?
            """,
            (uuid,),
        ).fetchone()
    if not row:
        return _json_error("作品不存在", 404)
    if row["deleted_at"]:
        return _json_error("作品已删除", 409)

    is_admin = _is_admin(user)
    is_owner = row["owner_user_id"] == user.id
    if not (is_admin or is_owner):
        return _json_error("无权限", 403)

    collections_meta, default_collection, _ = static_site.load_collections_config()
    tags = _load_tags_from_row(dict(row))
    collection = _resolve_collection(dict(row), collections_meta, default_collection)
    collections, default_collection = _load_collections_list()

    return jsonify(
        {
            "ok": True,
            "can_edit": True,
            "is_admin": is_admin,
            "is_owner": is_owner,
            "image": {
                "uuid": row["uuid"],
                "image_id": row.get("image_id"),
                "detail_path": static_site.image_detail_path(row.get("image_id"), row["uuid"]),
                "title": row["title_override"] or static_site.simple_title(row["original_name"] or ""),
                "description": row["description"] or "",
                "tags": tags,
                "collection": collection,
            },
            "collections": collections,
            "default_collection": default_collection,
        }
    )


def _touch_rebuild_flag(reason: str) -> None:
    try:
        config.FORCE_REBUILD_FLAG.write_text(reason, encoding="utf-8")
    except Exception:
        pass


@bp.post("/api/images/<uuid>/update")
def update_image(uuid: str):
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    collection = str(payload.get("collection") or "").strip()
    tags_raw = payload.get("tags")
    tags, err = _parse_tags_input(tags_raw)
    if err:
        return _json_error(err)
    missing_parents = _missing_parent_tags(tags or [])
    if missing_parents:
        return _json_error(f"缺少父标签: {', '.join(missing_parents)}")
    collections_meta, default_collection, _ = static_site.load_collections_config()
    if collection and collection not in collections_meta and collection != "auto":
        return _json_error("分区不存在")
    if collection == "auto" or not collection:
        collection = ""

    db.ensure_schema()
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT owner_user_id, deleted_at FROM images WHERE uuid=?",
            (uuid,),
        ).fetchone()
        if not row:
            return _json_error("作品不存在", 404)
        if row["deleted_at"]:
            return _json_error("作品已删除", 409)
        is_admin = _is_admin(user)
        is_owner = row["owner_user_id"] == user.id
        if not (is_admin or is_owner):
            return _json_error("无权限", 403)
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

    _touch_rebuild_flag("user_image_updated")
    try:
        db.insert_audit("user_update_image", uuid, user.username)
    except Exception:
        pass
    return jsonify({"ok": True})
