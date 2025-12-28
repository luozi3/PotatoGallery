import datetime
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from . import auth
from . import config
from . import db
from . import static_site
from . import tagging
from . import storage

bp = Blueprint("admin", __name__)


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
    tag_type = tagging.normalize_tag_type(payload.get("type"))
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
        tag_type = existing.get("type") or "general"
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
