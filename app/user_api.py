import json
import re
import time
import uuid
from urllib.parse import urlparse
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

HOME_DEFAULT_LIMIT = 40
HOME_MAX_LIMIT = 80
HOME_CHUNK_FACTOR = 3
HOME_MAX_PAGES = 8
PROFILE_MAX_NAME = 32
PROFILE_MAX_INTRO = 240
PROFILE_MAX_WEBSITE = 200
PROFILE_MAX_LOCATION = 60
PROFILE_ALLOWED_GENDERS = {"", "male", "female", "other", "secret"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DMCA_ALLOWED_AUTHORITY = {"owner", "authorized"}
DMCA_ALLOWED_STATUS = {"pending", "approved", "rejected"}
DMCA_MAX_NAME = 80
DMCA_MAX_EMAIL = 120
DMCA_MAX_REGION = 80
DMCA_MAX_CONTACT = 120
DMCA_MAX_URL = 500
DMCA_MAX_TEXT = 4000


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
    if token:
        serializer = _serializer()
        try:
            data = serializer.loads(token, max_age=config.USER_SESSION_MAX_AGE)
        except (BadSignature, SignatureExpired):
            data = None
        if data:
            user_id = data.get("id")
            if user_id:
                with db.connect() as conn:
                    auth.ensure_schema(conn)
                    row = conn.execute(
                        "SELECT id, username, is_active FROM auth_users WHERE id=?",
                        (user_id,),
                    ).fetchone()
                if row and row["is_active"]:
                    return auth.AuthUser(
                        id=int(row["id"]),
                        username=str(row["username"]),
                        is_active=bool(row["is_active"]),
                    )
    return _load_admin_from_cookie()


def _load_admin_from_cookie() -> Optional[auth.AuthUser]:
    token = request.cookies.get(config.ADMIN_COOKIE_NAME, "")
    if not token:
        return None
    serializer = URLSafeTimedSerializer(config.ADMIN_SECRET, salt="gallery-admin")
    try:
        data = serializer.loads(token, max_age=config.ADMIN_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    username = data.get("u")
    if not username:
        return None
    return auth.get_user_in_group(str(username), config.ADMIN_GROUP)


_UPLOAD_UUID_RE = re.compile(r"^[0-9a-f]{32}$")


def _normalize_upload_uuid(value: str) -> Optional[str]:
    cleaned = (value or "").strip().lower()
    if not cleaned or not _UPLOAD_UUID_RE.fullmatch(cleaned):
        return None
    return cleaned


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _clean_dmca_text(value: Any, *, max_len: int, required: bool, label: str) -> Tuple[Optional[str], Optional[str]]:
    text = str(value or "").strip()
    if required and not text:
        return None, f"请填写{label}"
    if text and len(text) > max_len:
        return None, f"{label}长度不能超过 {max_len} 字符"
    return text, None


def _allowed_dmca_hosts(site_url: str) -> set[str]:
    hosts: set[str] = set()
    normalized_site = (site_url or "").strip()
    if normalized_site:
        parsed = urlparse(normalized_site if "://" in normalized_site else f"https://{normalized_site}")
        if parsed.netloc:
            hosts.add(parsed.netloc.lower())
    if request.host:
        hosts.add(request.host.lower())
    return hosts


def _normalize_dmca_work_url(raw: Any, *, site_url: str) -> Tuple[Optional[str], Optional[str]]:
    value = str(raw or "").strip()
    if not value:
        return None, "请填写作品链接"
    if re.search(r"\s", value) or len(re.findall(r"https?://", value, flags=re.I)) > 1:
        return None, "仅受理单个作品链接，多张链接不予处理"
    parsed = urlparse(value)
    path = parsed.path or ""
    if parsed.scheme and parsed.netloc:
        if parsed.scheme.lower() not in {"http", "https"}:
            return None, "作品链接格式不正确"
        allowed_hosts = _allowed_dmca_hosts(site_url)
        if parsed.netloc.lower() not in allowed_hosts:
            return None, "作品链接必须为本站链接"
    else:
        if not value.startswith("/"):
            return None, "作品链接格式不正确"
        path = value
    if not path.startswith("/images/"):
        return None, "作品链接必须指向本站图片详情页"
    if len(value) > DMCA_MAX_URL:
        return None, f"作品链接长度不能超过 {DMCA_MAX_URL} 字符"
    if parsed.scheme and parsed.netloc:
        return value, None
    base = site_url.strip() if site_url else ""
    if not base and request.host:
        base = f"https://{request.host}"
    normalized = f"{base.rstrip('/')}{path}"
    return normalized or value, None


def _normalize_dmca_source_url(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    value = str(raw or "").strip()
    if not value:
        return None, "请填写原始作品来源链接"
    if len(value) > DMCA_MAX_URL:
        return None, f"原始作品来源链接长度不能超过 {DMCA_MAX_URL} 字符"
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None, "原始作品来源链接格式不正确"
    if parsed.scheme.lower() not in {"http", "https"}:
        return None, "原始作品来源链接格式不正确"
    return value, None


def _value_is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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


def _normalize_profile_text(value: Any, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_len]


def _normalize_gender(value: Any) -> Optional[str]:
    gender = str(value or "").strip().lower()
    if gender not in PROFILE_ALLOWED_GENDERS:
        return None
    return gender


def _normalize_profile_url(value: Any) -> Tuple[str, Optional[str]]:
    raw = str(value or "").strip()
    if not raw:
        return "", None
    if len(raw) > PROFILE_MAX_WEBSITE:
        return "", "个人主页过长"
    if not (raw.startswith("http://") or raw.startswith("https://")):
        return "", "个人主页需以 http:// 或 https:// 开头"
    return raw, None


def _avatar_url(avatar_path: str) -> str:
    cleaned = (avatar_path or "").lstrip("/")
    if not cleaned:
        return ""
    return f"/raw/{cleaned}"


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
        "bytes": row_dict.get("bytes"),
        "bytes_human": static_site.human_bytes(int(row_dict.get("bytes") or 0)),
        "width": row_dict.get("width"),
        "height": row_dict.get("height"),
        "thumb_width": row_dict.get("thumb_width"),
        "thumb_height": row_dict.get("thumb_height"),
        "dominant_color": row_dict.get("dominant_color"),
        "created_at": row_dict.get("created_at"),
        "rating": int(row_dict.get("rating") or 0),
        "flag": row_dict.get("flag") or "",
        "color_label": row_dict.get("color_label") or "",
    }
    if row_dict.get("favorited_at"):
        item["favorited_at"] = row_dict.get("favorited_at")
    if row_dict.get("added_at"):
        item["added_at"] = row_dict.get("added_at")
    return item


def _parse_limit(raw: Optional[str], default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(str(raw or "").strip())
    except (TypeError, ValueError):
        return default
    if value < min_value:
        return min_value
    return min(value, max_value)


def _parse_home_cursor(raw: str) -> Optional[Tuple[str, int]]:
    text = str(raw or "").strip()
    if not text:
        return None
    if "|" not in text:
        return None
    created_at, id_part = text.split("|", 1)
    created_at = created_at.strip()
    if not created_at:
        return None
    try:
        image_id = int(id_part.strip())
    except (TypeError, ValueError):
        return None
    return created_at, image_id


def _cursor_from_row(row: dict) -> Optional[str]:
    created_at = row.get("created_at")
    image_id = row.get("id")
    if not created_at or image_id is None:
        return None
    return f"{created_at}|{int(image_id)}"


def _build_tag_maps(tags_meta: Optional[dict] = None) -> Tuple[dict, dict, dict]:
    if tags_meta is None:
        tags_meta, _ = tagging.load_tags_config()
    tag_types_meta, tag_types_order = tagging.load_tag_types_config()
    alias_map = tagging.build_alias_map(tags_meta)
    tag_slug_map = {
        tag: (info.get("slug") or tagging.safe_tag_slug(tag))
        for tag, info in tags_meta.items()
        if not info.get("alias_to")
    }
    default_tag_type = tagging.default_tag_type(tag_types_meta, tag_types_order)
    tag_type_styles: dict = {}
    ordered_types = (tag_types_order or []) + sorted(tag_types_meta.keys())
    seen_types = set()
    for type_id in ordered_types:
        if type_id in seen_types:
            continue
        seen_types.add(type_id)
        info = tag_types_meta.get(type_id) or {}
        color = str(info.get("color") or "#7b8794")
        style = static_site._tag_style(color)
        tag_type_styles[type_id] = {
            "type": type_id,
            "label": info.get("label") or type_id,
            "color": color,
            "style": style["style"],
        }
    default_style = tag_type_styles.get(default_tag_type) or static_site._tag_style("#7b8794")
    tag_style_map: dict = {}
    for tag, info in tags_meta.items():
        canonical = tagging.normalize_tag(info.get("alias_to") or "") or tag
        canonical_info = tags_meta.get(canonical) or info
        type_id = canonical_info.get("type") or default_tag_type
        style_info = tag_type_styles.get(type_id) or default_style
        tag_style_map[tag] = style_info.get("style", "")
    return alias_map, tag_slug_map, tag_style_map


def _build_tag_slug_map(tags_meta: dict) -> dict:
    slug_map: dict = {}
    for tag, info in tags_meta.items():
        slug = tagging.normalize_slug(info.get("slug") or "")
        if not slug:
            slug = tagging.safe_tag_slug(tag)
        canonical = tagging.normalize_tag(info.get("alias_to") or "") or tag
        if slug and slug not in slug_map:
            slug_map[slug] = canonical
    return slug_map


def _collect_tag_descendants(tag: str, child_map: dict) -> List[str]:
    collected: List[str] = []
    stack = [tag]
    seen = {tag}
    while stack:
        current = stack.pop()
        for child in child_map.get(current, []):
            if child in seen:
                continue
            seen.add(child)
            collected.append(child)
            stack.append(child)
    return collected


def _build_collection_lookup(collections_meta: dict) -> dict:
    lookup: dict = {}
    for key, info in collections_meta.items():
        for uid in info.get("uuids", set()) or []:
            lookup[str(uid).lower()] = key
    return lookup


def _resolve_collection_cached(
    row_dict: dict,
    collection_lookup: dict,
    default_collection: str,
) -> str:
    override = row_dict.get("collection_override")
    if override:
        return str(override)
    uuid = str(row_dict.get("uuid") or "").lower()
    return collection_lookup.get(uuid, default_collection)


def _build_home_item(
    row_dict: dict,
    alias_map: dict,
    tag_slug_map: dict,
    tag_style_map: dict,
    collection_lookup: dict,
    default_collection: str,
    collections_meta: dict,
) -> dict:
    uuid = row_dict.get("uuid") or ""
    image_id = row_dict.get("id")
    width = row_dict.get("width")
    height = row_dict.get("height")
    tags = tagging.parse_tags_json(row_dict.get("tags_json"), alias_map, drop_unknown=True)
    tag_items = [
        {
            "tag": tag,
            "slug": tag_slug_map.get(tag, tagging.safe_tag_slug(tag)),
            "style": tag_style_map.get(tag, ""),
        }
        for tag in tags
    ]
    collection = row_dict.get("collection") or _resolve_collection_cached(
        row_dict,
        collection_lookup,
        default_collection,
    )
    collection_title = collections_meta.get(collection, {}).get("title", collection)
    orientation = row_dict.get("orientation") or static_site.classify_orientation(
        int(width) if width else None,
        int(height) if height else None,
    )
    size_bucket = row_dict.get("size_bucket") or static_site.size_bucket(
        int(width) if width else None,
        int(height) if height else None,
    )
    thumb_path_value = row_dict.get("thumb_path")
    thumb_name = Path(thumb_path_value).name if thumb_path_value else ""
    return {
        "id": int(image_id) if image_id is not None else None,
        "uuid": uuid,
        "detail_path": static_site.image_detail_path(image_id, uuid),
        "title": row_dict.get("title_override")
        or static_site.simple_title(row_dict.get("original_name") or ""),
        "description": row_dict.get("description") or "",
        "tags": tag_items,
        "collection": collection,
        "collection_title": collection_title,
        "raw_filename": f"{uuid}{row_dict.get('ext') or ''}",
        "thumb_filename": thumb_name,
        "bytes_human": static_site.human_bytes(int(row_dict.get("bytes") or 0)),
        "width": width,
        "height": height,
        "thumb_width": row_dict.get("thumb_width"),
        "thumb_height": row_dict.get("thumb_height"),
        "dominant_color": row_dict.get("dominant_color"),
        "created_at": row_dict.get("created_at"),
        "orientation": orientation,
        "size_bucket": size_bucket,
    }


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
    ext_from_name = Path(original_name).suffix.lower()
    if config.ENFORCE_MIME and file_mime and file_mime not in config.ALLOWED_MIME:
        return _json_error("不支持的文件类型")
    if config.ENFORCE_EXTENSION and ext_from_name and ext_from_name not in config.ALLOWED_MIME.values():
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
    if config.ENFORCE_MIME and not ext:
        storage.move_to_quarantine(tmp_path, f"mime_not_allowed: {mime}")
        return _json_error("不支持的文件类型")
    if not ext:
        if ext_from_name:
            ext = ext_from_name
        else:
            storage.move_to_quarantine(tmp_path, f"ext_missing: {mime}")
            return _json_error("无法识别文件类型")

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


@bp.post("/api/dmca")
def dmca_submit():
    db.ensure_schema()
    payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    if not isinstance(payload, dict):
        return _json_error("提交内容有误")

    full_name, err = _clean_dmca_text(payload.get("full_name"), max_len=DMCA_MAX_NAME, required=True, label="姓名")
    if err:
        return _json_error(err)
    email, err = _clean_dmca_text(payload.get("email"), max_len=DMCA_MAX_EMAIL, required=True, label="邮箱")
    if err:
        return _json_error(err)
    if "@" not in email:
        return _json_error("邮箱格式不正确")
    region, err = _clean_dmca_text(payload.get("region"), max_len=DMCA_MAX_REGION, required=True, label="国家/地区")
    if err:
        return _json_error(err)
    contact, err = _clean_dmca_text(payload.get("contact"), max_len=DMCA_MAX_CONTACT, required=False, label="联系方式")
    if err:
        return _json_error(err)

    site = static_site.load_site_config()
    work_url, err = _normalize_dmca_work_url(payload.get("work_url"), site_url=str(site.get("site_url") or ""))
    if err:
        return _json_error(err)
    source_url, err = _normalize_dmca_source_url(payload.get("source_url"))
    if err:
        return _json_error(err)

    claim, err = _clean_dmca_text(payload.get("claim"), max_len=DMCA_MAX_TEXT, required=True, label="侵权说明")
    if err:
        return _json_error(err)
    evidence, err = _clean_dmca_text(payload.get("evidence"), max_len=DMCA_MAX_TEXT, required=True, label="证明材料")
    if err:
        return _json_error(err)

    authority = str(payload.get("authority") or "").strip().lower()
    if authority not in DMCA_ALLOWED_AUTHORITY:
        return _json_error("请选择权利身份")
    authority_note, err = _clean_dmca_text(
        payload.get("authority_note"),
        max_len=DMCA_MAX_TEXT,
        required=False,
        label="授权说明",
    )
    if err:
        return _json_error(err)

    if not _value_is_true(payload.get("single_work")):
        return _json_error("请确认仅提交单个作品链接")
    if not _value_is_true(payload.get("truthful")):
        return _json_error("请确认信息真实准确")

    ip = _client_ip()
    user_agent = str(request.headers.get("User-Agent") or "").strip()

    try:
        with db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO dmca_requests
                (status, full_name, email, region, contact, work_url, source_url, claim, evidence, authority, authority_note,
                 status_note, processed_by, processed_at, ip, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "pending",
                    full_name,
                    email,
                    region,
                    contact,
                    work_url,
                    source_url,
                    claim,
                    evidence,
                    authority,
                    authority_note,
                    None,
                    None,
                    None,
                    ip,
                    user_agent,
                ),
            )
            request_id = int(cursor.lastrowid)
    except Exception:  # noqa: BLE001
        return _json_error("提交失败，请稍后重试", 500)

    try:
        db.insert_audit("dmca_submit", str(request_id), email)
    except Exception:
        pass

    ticket = f"DMCA-{request_id:06d}"
    return jsonify({"ok": True, "id": request_id, "ticket": ticket}), 201


@bp.get("/api/my/images")
def my_images():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    query = (request.args.get("q") or "").strip()
    collection_filter = (request.args.get("collection") or "all").strip()
    try:
        page = max(1, int(request.args.get("p") or request.args.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    page_size = 40
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

    collections, default_collection = _load_collections_list()
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


@bp.get("/api/user/profile")
def user_profile():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        account = conn.execute(
            "SELECT username, created_at FROM auth_users WHERE id=?",
            (user.id,),
        ).fetchone()
        profile = conn.execute(
            """
            SELECT display_name, gender, intro, website, location, avatar_path, updated_at
            FROM user_profiles
            WHERE user_id=?
            """,
            (user.id,),
        ).fetchone()
        works_row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM images
            WHERE owner_user_id=? AND deleted_at IS NULL AND status='published'
            """,
            (user.id,),
        ).fetchone()
        favorited_row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM user_favorites f
            JOIN images i ON i.uuid = f.image_uuid
            WHERE i.owner_user_id=? AND i.deleted_at IS NULL AND i.status='published'
            """,
            (user.id,),
        ).fetchone()
    groups = auth.get_user_groups(user.id)
    display_name = ""
    gender = ""
    intro = ""
    website = ""
    location = ""
    avatar_path = ""
    updated_at = ""
    if profile:
        display_name = str(profile["display_name"] or "").strip()
        gender = str(profile["gender"] or "").strip()
        intro = str(profile["intro"] or "").strip()
        website = str(profile["website"] or "").strip()
        location = str(profile["location"] or "").strip()
        avatar_path = str(profile["avatar_path"] or "").strip()
        updated_at = str(profile["updated_at"] or "").strip()
    resp = jsonify(
        {
            "ok": True,
            "user": account["username"] if account else user.username,
            "groups": groups,
            "profile": {
                "display_name": display_name,
                "gender": gender,
                "intro": intro,
                "website": website,
                "location": location,
                "avatar_url": _avatar_url(avatar_path),
                "updated_at": updated_at,
            },
            "account": {
                "created_at": str(account["created_at"] or "") if account else "",
            },
            "stats": {
                "works": int(works_row["c"] or 0) if works_row else 0,
                "favorited": int(favorited_row["c"] or 0) if favorited_row else 0,
            },
        }
    )
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.post("/api/user/profile")
def user_profile_update():
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    display_name = _normalize_profile_text(payload.get("display_name"), PROFILE_MAX_NAME)
    intro = _normalize_profile_text(payload.get("intro"), PROFILE_MAX_INTRO)
    location = _normalize_profile_text(payload.get("location"), PROFILE_MAX_LOCATION)
    gender = _normalize_gender(payload.get("gender"))
    if gender is None:
        return _json_error("性别参数错误")
    website, err_msg = _normalize_profile_url(payload.get("website"))
    if err_msg:
        return _json_error(err_msg)
    db.ensure_schema()
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO user_profiles (user_id, display_name, gender, intro, website, location, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                gender=excluded.gender,
                intro=excluded.intro,
                website=excluded.website,
                location=excluded.location,
                updated_at=CURRENT_TIMESTAMP
            """,
            (user.id, display_name, gender, intro, website, location),
        )
    return jsonify(
        {
            "ok": True,
            "profile": {
                "display_name": display_name,
                "gender": gender,
                "intro": intro,
                "website": website,
                "location": location,
            },
        }
    )


@bp.post("/api/user/avatar")
def user_avatar_update():
    user, err = _require_user()
    if err:
        return err
    file = request.files.get("avatar")
    if not file or not file.filename:
        return _json_error("请选择头像文件")
    ext = Path(file.filename).suffix.lower()
    if ext not in AVATAR_ALLOWED_EXTS:
        return _json_error("头像仅支持 png/jpg/webp")
    tmp_name = uuid.uuid4().hex
    tmp_path = config.UPLOAD_TMP / "avatars" / f"{tmp_name}.part"
    try:
        bytes_written, _ = storage.write_stream_to_tmp(file.stream, tmp_path)
    except ValueError as exc:
        tmp_path.unlink(missing_ok=True)
        return _json_error(str(exc))
    if bytes_written > AVATAR_MAX_BYTES:
        tmp_path.unlink(missing_ok=True)
        return _json_error("头像文件过大")
    dest_dir = config.RAW_DIR / "avatars"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"user_{user.id}_{int(time.time())}{ext}"
    dest_path = dest_dir / dest_name
    try:
        storage.atomic_move(tmp_path, dest_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        return _json_error("头像保存失败", 500)
    avatar_rel = f"avatars/{dest_name}"
    old_avatar = ""
    db.ensure_schema()
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT avatar_path FROM user_profiles WHERE user_id=?",
            (user.id,),
        ).fetchone()
        if row:
            old_avatar = str(row["avatar_path"] or "")
        conn.execute(
            """
            INSERT INTO user_profiles (user_id, avatar_path, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                avatar_path=excluded.avatar_path,
                updated_at=CURRENT_TIMESTAMP
            """,
            (user.id, avatar_rel),
        )
    if old_avatar and old_avatar != avatar_rel and old_avatar.startswith("avatars/"):
        old_path = config.RAW_DIR / old_avatar
        old_path.unlink(missing_ok=True)
    return jsonify({"ok": True, "avatar_url": _avatar_url(avatar_rel)})


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


@bp.get("/api/home/images")
def home_images():
    db.ensure_schema()
    limit = _parse_limit(request.args.get("limit"), HOME_DEFAULT_LIMIT, 1, HOME_MAX_LIMIT)
    cursor = _parse_home_cursor(request.args.get("cursor") or "")
    if request.args.get("cursor") and not cursor:
        return _json_error("参数错误", 400)

    collections_meta, default_collection, _ = static_site.load_collections_config()
    collection_lookup = _build_collection_lookup(collections_meta)
    collection_filter = str(request.args.get("collection") or "all").strip().lower()
    if collection_filter != "all" and collection_filter not in collections_meta:
        return _json_error("分区不存在", 400)

    orientation_filter = str(request.args.get("orientation") or "all").strip().lower()
    allowed_orientations = {"all", "portrait", "landscape", "square", "unknown"}
    if orientation_filter not in allowed_orientations:
        return _json_error("参数错误", 400)

    size_filter = str(request.args.get("size") or "all").strip().lower()
    allowed_sizes = {"all", "ultra", "large", "medium", "compact", "unknown"}
    if size_filter not in allowed_sizes:
        return _json_error("参数错误", 400)

    alias_map, tag_slug_map, tag_style_map = _build_tag_maps()

    items: List[dict] = []
    next_cursor: Optional[str] = None
    has_more = False
    chunk_size = min(limit * HOME_CHUNK_FACTOR, 200)
    current_cursor = cursor
    last_row: Optional[dict] = None

    with db.connect() as conn:
        for _ in range(HOME_MAX_PAGES):
            params: List[object] = []
            cursor_clause = ""
            if current_cursor:
                cursor_clause = "AND (created_at < ? OR (created_at = ? AND id < ?))"
                params.extend([current_cursor[0], current_cursor[0], current_cursor[1]])
            rows = conn.execute(
                f"""
                SELECT id, uuid, original_name, ext, bytes, width, height, thumb_width, thumb_height,
                       dominant_color, created_at, thumb_path,
                       title_override, description, tags_json, collection_override
                FROM images
                WHERE status IN ('processed','published')
                  AND deleted_at IS NULL
                  {cursor_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (*params, chunk_size),
            ).fetchall()
            if not rows:
                break

            processed_in_batch = 0
            stop = False
            for row in rows:
                processed_in_batch += 1
                row_dict = dict(row)
                last_row = row_dict
                collection = _resolve_collection_cached(row_dict, collection_lookup, default_collection)
                if collection_filter != "all" and collection != collection_filter:
                    continue
                orientation = static_site.classify_orientation(
                    int(row_dict.get("width")) if row_dict.get("width") else None,
                    int(row_dict.get("height")) if row_dict.get("height") else None,
                )
                if orientation_filter != "all" and orientation != orientation_filter:
                    continue
                size_bucket = static_site.size_bucket(
                    int(row_dict.get("width")) if row_dict.get("width") else None,
                    int(row_dict.get("height")) if row_dict.get("height") else None,
                )
                if size_filter != "all" and size_bucket != size_filter:
                    continue
                row_dict["collection"] = collection
                row_dict["orientation"] = orientation
                row_dict["size_bucket"] = size_bucket
                item = _build_home_item(
                    row_dict,
                    alias_map,
                    tag_slug_map,
                    tag_style_map,
                    collection_lookup,
                    default_collection,
                    collections_meta,
                )
                items.append(item)
                if len(items) >= limit:
                    has_more = processed_in_batch < len(rows) or len(rows) == chunk_size
                    next_cursor = _cursor_from_row(row_dict)
                    stop = True
                    break

            if stop:
                break
            if len(rows) < chunk_size:
                break
            if not last_row:
                break
            current_cursor = (str(last_row.get("created_at") or ""), int(last_row.get("id") or 0))
        else:
            if last_row:
                next_cursor = _cursor_from_row(last_row)
                has_more = True

    return jsonify({"ok": True, "items": items, "next_cursor": next_cursor, "has_more": has_more})


@bp.get("/api/tags/<slug>/images")
def tag_images(slug: str):
    db.ensure_schema()
    limit = _parse_limit(request.args.get("limit"), HOME_DEFAULT_LIMIT, 1, HOME_MAX_LIMIT)
    cursor = _parse_home_cursor(request.args.get("cursor") or "")
    if request.args.get("cursor") and not cursor:
        return _json_error("参数错误", 400)

    tags_meta, _ = tagging.load_tags_config()
    slug_map = _build_tag_slug_map(tags_meta)
    canonical = slug_map.get(tagging.normalize_slug(slug))
    if not canonical:
        return _json_error("标签不存在", 404)

    alias_map, tag_slug_map, tag_style_map = _build_tag_maps(tags_meta)
    parent_map = tagging.build_parent_map(tags_meta, alias_map)
    child_map: dict = {}
    for tag, parents in parent_map.items():
        for parent in parents:
            child_map.setdefault(parent, []).append(tag)
    target_tags = {canonical}
    target_tags.update(_collect_tag_descendants(canonical, child_map))

    collections_meta, default_collection, _ = static_site.load_collections_config()
    collection_lookup = _build_collection_lookup(collections_meta)

    items: List[dict] = []
    next_cursor: Optional[str] = None
    has_more = False
    chunk_size = min(limit * HOME_CHUNK_FACTOR, 200)
    current_cursor = cursor
    last_row: Optional[dict] = None

    with db.connect() as conn:
        for _ in range(HOME_MAX_PAGES):
            params: List[object] = []
            cursor_clause = ""
            if current_cursor:
                cursor_clause = "AND (created_at < ? OR (created_at = ? AND id < ?))"
                params.extend([current_cursor[0], current_cursor[0], current_cursor[1]])
            rows = conn.execute(
                f"""
                SELECT id, uuid, original_name, ext, bytes, width, height, thumb_width, thumb_height,
                       dominant_color, created_at, thumb_path,
                       title_override, description, tags_json, collection_override
                FROM images
                WHERE status IN ('processed','published')
                  AND deleted_at IS NULL
                  {cursor_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (*params, chunk_size),
            ).fetchall()
            if not rows:
                break

            processed_in_batch = 0
            stop = False
            for row in rows:
                processed_in_batch += 1
                row_dict = dict(row)
                last_row = row_dict
                tags = tagging.parse_tags_json(row_dict.get("tags_json"), alias_map, drop_unknown=True)
                if not tags or not any(tag in target_tags for tag in tags):
                    continue
                row_dict["collection"] = _resolve_collection_cached(
                    row_dict,
                    collection_lookup,
                    default_collection,
                )
                item = _build_home_item(
                    row_dict,
                    alias_map,
                    tag_slug_map,
                    tag_style_map,
                    collection_lookup,
                    default_collection,
                    collections_meta,
                )
                items.append(item)
                if len(items) >= limit:
                    has_more = processed_in_batch < len(rows) or len(rows) == chunk_size
                    next_cursor = _cursor_from_row(row_dict)
                    stop = True
                    break

            if stop:
                break
            if len(rows) < chunk_size:
                break
            if not last_row:
                break
            current_cursor = (str(last_row.get("created_at") or ""), int(last_row.get("id") or 0))
        else:
            if last_row:
                next_cursor = _cursor_from_row(last_row)
                has_more = True

    return jsonify({"ok": True, "items": items, "next_cursor": next_cursor, "has_more": has_more})


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
                   f.rating, f.flag, f.color_label,
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
    resp = jsonify({"ok": True, "images": items, "total": len(items)})
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.get("/api/favorites/<uuid>")
def favorite_status(uuid: str):
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    with db.connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM user_favorites WHERE user_id=? AND image_uuid=?",
            (user.id, uuid),
        ).fetchone()
        if exists:
            resp = jsonify({"ok": True, "favorited": True})
            resp.headers["Cache-Control"] = "no-store, max-age=0"
            return resp
        in_gallery = conn.execute(
            """
            SELECT 1
            FROM user_gallery_images gi
            JOIN user_galleries g ON g.id = gi.gallery_id
            WHERE g.user_id=? AND gi.image_uuid=?
            LIMIT 1
            """,
            (user.id, uuid),
        ).fetchone()
    if in_gallery:
        with db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO user_favorites (user_id, image_uuid) VALUES (?, ?)",
                (user.id, uuid),
            )
        resp = jsonify({"ok": True, "favorited": True})
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp
    resp = jsonify({"ok": True, "favorited": False})
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


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
            conn.execute(
                """
                DELETE FROM user_gallery_images
                WHERE image_uuid=? AND gallery_id IN (
                    SELECT id FROM user_galleries WHERE user_id=?
                )
                """,
                (uuid, user.id),
            )
            status = "removed"
        else:
            conn.execute(
                "INSERT INTO user_favorites (user_id, image_uuid) VALUES (?, ?)",
                (user.id, uuid),
            )
    return jsonify({"ok": True, "status": status})


@bp.post("/api/favorites/<uuid>/meta")
def update_favorite_meta(uuid: str):
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    rating_value = payload.get("rating") if "rating" in payload else None
    flag_value = payload.get("flag") if "flag" in payload else None
    color_value = payload.get("color_label") if "color_label" in payload else None

    rating = None
    if rating_value is not None:
        try:
            rating = int(rating_value)
        except (TypeError, ValueError):
            return _json_error("评分不合法")
        if rating < 0 or rating > 5:
            return _json_error("评分不合法")

    flag = None
    if flag_value is not None:
        flag = str(flag_value or "").strip().lower()
        if flag and flag not in {"pick", "reject"}:
            return _json_error("旗标不合法")

    color_label = None
    if color_value is not None:
        color_label = str(color_value or "").strip().lower()
        if color_label and color_label not in {"red", "yellow", "green", "blue", "purple"}:
            return _json_error("颜色不合法")

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

    with db.transaction() as conn:
        existing = conn.execute(
            """
            SELECT rating, flag, color_label
            FROM user_favorites
            WHERE user_id=? AND image_uuid=?
            """,
            (user.id, uuid),
        ).fetchone()
        current_rating = int(existing["rating"] or 0) if existing else 0
        current_flag = existing["flag"] if existing else ""
        current_color = existing["color_label"] if existing else ""
        new_rating = current_rating if rating is None else rating
        new_flag = current_flag if flag is None else flag
        new_color = current_color if color_label is None else color_label
        if existing:
            conn.execute(
                """
                UPDATE user_favorites
                SET rating=?, flag=?, color_label=?
                WHERE user_id=? AND image_uuid=?
                """,
                (new_rating, new_flag or None, new_color or None, user.id, uuid),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_favorites (user_id, image_uuid, rating, flag, color_label)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user.id, uuid, new_rating, new_flag or None, new_color or None),
            )
    return jsonify(
        {
            "ok": True,
            "rating": new_rating,
            "flag": new_flag or "",
            "color_label": new_color or "",
        }
    )


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


def _can_use_cover(conn, user_id: int, uuid: str, gallery_id: Optional[int] = None) -> bool:
    row = conn.execute(
        "SELECT uuid, deleted_at FROM images WHERE uuid=?",
        (uuid,),
    ).fetchone()
    if not row or row["deleted_at"]:
        return False
    exists = conn.execute(
        "SELECT 1 FROM user_favorites WHERE user_id=? AND image_uuid=?",
        (user_id, uuid),
    ).fetchone()
    if exists:
        return True
    if gallery_id is not None:
        exists = conn.execute(
            "SELECT 1 FROM user_gallery_images WHERE gallery_id=? AND image_uuid=?",
            (gallery_id, uuid),
        ).fetchone()
        if exists:
            return True
    return False


@bp.get("/api/galleries")
def list_galleries():
    user, err = _require_user()
    if err:
        return err
    db.ensure_schema()
    target_uuid = str(request.args.get("uuid") or "").strip()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.title, g.description, g.cover_uuid, g.created_at, g.updated_at,
                   COUNT(gi.image_uuid) AS count,
                   SUM(CASE WHEN gi.image_uuid = ? THEN 1 ELSE 0 END) AS contains,
                   COALESCE(
                       g.cover_uuid,
                       (
                           SELECT gi2.image_uuid
                           FROM user_gallery_images gi2
                           WHERE gi2.gallery_id = g.id
                           ORDER BY gi2.position DESC, gi2.created_at DESC
                           LIMIT 1
                       )
                   ) AS resolved_cover_uuid,
                   i.thumb_path AS cover_thumb_path,
                   i.thumb_width AS cover_thumb_width,
                   i.thumb_height AS cover_thumb_height,
                   i.dominant_color AS cover_dominant_color
            FROM user_galleries g
            LEFT JOIN user_gallery_images gi ON g.id = gi.gallery_id
            LEFT JOIN images i ON i.uuid = COALESCE(
                g.cover_uuid,
                (
                    SELECT gi2.image_uuid
                    FROM user_gallery_images gi2
                    WHERE gi2.gallery_id = g.id
                    ORDER BY gi2.position DESC, gi2.created_at DESC
                    LIMIT 1
                )
            )
            WHERE g.user_id=?
            GROUP BY g.id
            ORDER BY g.updated_at DESC
            """,
            (target_uuid, user.id),
        ).fetchall()
    galleries = []
    for row in rows:
        item = dict(row)
        item["count"] = int(item.get("count") or 0)
        item["contains"] = bool(item.get("contains"))
        cover_thumb = item.get("cover_thumb_path")
        item["cover_thumb_filename"] = Path(cover_thumb).name if cover_thumb else ""
        item["cover_resolved_uuid"] = item.get("resolved_cover_uuid")
        item["cover_is_manual"] = bool(item.get("cover_uuid"))
        galleries.append(item)
    resp = jsonify({"ok": True, "galleries": galleries})
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@bp.post("/api/galleries")
def create_gallery():
    user, err = _require_user()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    cover_uuid = str(payload.get("cover_uuid") or "").strip()
    if not title:
        return _json_error("画廊名称不能为空")
    db.ensure_schema()
    with db.transaction() as conn:
        if cover_uuid and not _can_use_cover(conn, user.id, cover_uuid, None):
            return _json_error("封面无效", 400)
        conn.execute(
            """
            INSERT INTO user_galleries (user_id, title, description, cover_uuid)
            VALUES (?, ?, ?, ?)
            """,
            (user.id, title, description or None, cover_uuid or None),
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
    cover_uuid = payload.get("cover_uuid") if "cover_uuid" in payload else None
    if not title:
        return _json_error("画廊名称不能为空")
    db.ensure_schema()
    with db.transaction() as conn:
        gallery = _load_gallery(conn, gallery_id, user.id)
        if not gallery:
            return _json_error("画廊不存在", 404)
        cover_value = gallery.get("cover_uuid")
        if cover_uuid is not None:
            cover_uuid = str(cover_uuid or "").strip()
            if cover_uuid:
                if not _can_use_cover(conn, user.id, cover_uuid, gallery_id):
                    return _json_error("封面无效", 400)
                cover_value = cover_uuid
            else:
                cover_value = None
        conn.execute(
            """
            UPDATE user_galleries
            SET title=?, description=?, cover_uuid=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND user_id=?
            """,
            (title, description or None, cover_value, gallery_id, user.id),
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
                   gi.created_at AS added_at,
                   f.created_at AS favorited_at,
                   f.rating, f.flag, f.color_label
            FROM user_gallery_images gi
            JOIN images i ON i.uuid = gi.image_uuid
            LEFT JOIN user_favorites f ON f.user_id=? AND f.image_uuid = i.uuid
            WHERE gi.gallery_id=? AND i.deleted_at IS NULL
            ORDER BY gi.position DESC, gi.created_at DESC
            """,
            (user.id, gallery_id),
        ).fetchall()

    collections_meta, default_collection, _ = static_site.load_collections_config()
    items = []
    for row in rows:
        item = _build_image_item(dict(row), collections_meta, default_collection)
        items.append(item)
    if gallery:
        gallery["count"] = len(items)
        gallery["cover_is_manual"] = bool(gallery.get("cover_uuid"))
    resp = jsonify({"ok": True, "gallery": gallery, "images": items})
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


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
            conn.execute(
                "UPDATE user_galleries SET updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (gallery_id, user.id),
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
            conn.execute(
                "INSERT OR IGNORE INTO user_favorites (user_id, image_uuid) VALUES (?, ?)",
                (user.id, uuid),
            )
            conn.execute(
                "UPDATE user_galleries SET updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (gallery_id, user.id),
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

    row_dict = dict(row)
    collections_meta, default_collection, _ = static_site.load_collections_config()
    tags = _load_tags_from_row(row_dict)
    collection = _resolve_collection(row_dict, collections_meta, default_collection)
    collections, default_collection = _load_collections_list()

    return jsonify(
        {
            "ok": True,
            "can_edit": True,
            "is_admin": is_admin,
            "is_owner": is_owner,
            "image": {
                "uuid": row_dict["uuid"],
                "image_id": row_dict.get("image_id"),
                "detail_path": static_site.image_detail_path(row_dict.get("image_id"), row_dict["uuid"]),
                "title": row_dict["title_override"] or static_site.simple_title(row_dict["original_name"] or ""),
                "description": row_dict["description"] or "",
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
