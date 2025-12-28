import json
import os
from pathlib import Path

# 路径配置（支持 GALLERY_ROOT 覆盖以便测试）
ROOT = Path(os.environ.get("GALLERY_ROOT", "/opt/PotatoGallery"))
STATIC = ROOT / "static"
STORAGE = ROOT / "storage"
UPLOAD_TMP = STORAGE / ".upload_tmp"
RAW_DIR = STORAGE / "raw"
QUARANTINE_DIR = STORAGE / "quarantine"
THUMB_DIR = STORAGE / "thumb"
TRASH_DIR = STORAGE / "trash"
WWW_DIR = STORAGE / "www"
WWW_STAGING = STORAGE / "www_staging"
UPLOAD_PAUSE_FLAG = STORAGE / ".upload_paused"
FORCE_REBUILD_FLAG = STORAGE / ".force_rebuild"
LAST_STATIC_MTIME = WWW_DIR / ".last_static_mtime"
STATUS_DATA_DIR = STORAGE / "status_data"

# 上传限制
MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # 30MB
CHUNK_SIZE = 512 * 1024             # 512KB
DISK_LOW_WATERMARK_BYTES = 200 * 1024 * 1024  # 200MB 剩余空间以下拒绝写入
DISK_RESUME_DELTA_BYTES = 50 * 1024 * 1024    # 触发恢复的回退余量，避免频繁切换
UPLOAD_RATE_LIMIT_MAX = int(os.environ.get("GALLERY_UPLOAD_RATE_MAX", "30"))
UPLOAD_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("GALLERY_UPLOAD_RATE_WINDOW", "60"))

# 维护/清理策略
CLEANUP_STAGING_MAX_AGE_HOURS = int(os.environ.get("GALLERY_CLEANUP_STAGING_HOURS", "24"))
CLEANUP_TMP_MAX_AGE_HOURS = int(os.environ.get("GALLERY_CLEANUP_TMP_HOURS", "12"))
CLEANUP_BACKUP_DIR = STORAGE / "backups"
SITE_CONFIG_PATH = STATIC / "data" / "site.json"
SITE_CONFIG_LOCAL_PATH = STATIC / "data" / "site.local.json"
LOG_DIR = STORAGE / "logs"
LOG_MAX_BYTES = int(os.environ.get("GALLERY_LOG_MAX_BYTES", "2097152"))
LOG_BACKUP_COUNT = int(os.environ.get("GALLERY_LOG_BACKUPS", "5"))
TRASH_RETENTION_DAYS = int(os.environ.get("GALLERY_TRASH_RETENTION_DAYS", "5"))
AUTH_CONFIG_PATH = ROOT / "config" / "auth.json"

# 图片处理限制
MAX_PIXELS = 50_000_000             # 避免超大分辨率
THUMB_SIZE = (960, 960)
THUMB_QUALITY = 82
THUMB_FORMAT = os.environ.get("GALLERY_THUMB_FORMAT", "WEBP").upper()
THUMB_EXT = ".webp" if THUMB_FORMAT == "WEBP" else ".jpg"

ALLOWED_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# 访问控制（上传口令可选，未设置则不校验）
UPLOAD_TOKEN = os.environ.get("GALLERY_UPLOAD_TOKEN")
UPLOAD_TOKEN_USER = os.environ.get("GALLERY_UPLOAD_USER")
UPLOAD_REALM = os.environ.get("GALLERY_UPLOAD_REALM", "gallery-upload")

# 管理后台鉴权（账号数据来自 SQLite，以下变量仅用于引导初始化）
ADMIN_GROUP = os.environ.get("GALLERY_ADMIN_GROUP", "admin")
ADMIN_BOOTSTRAP_USER = os.environ.get("GALLERY_ADMIN_BOOTSTRAP_USER") or os.environ.get(
    "GALLERY_ADMIN_USER"
)
ADMIN_BOOTSTRAP_PASSWORD = os.environ.get("GALLERY_ADMIN_BOOTSTRAP_PASSWORD") or os.environ.get(
    "GALLERY_ADMIN_PASSWORD"
)
ADMIN_SECRET = os.environ.get("GALLERY_ADMIN_SECRET", "gallery-admin-secret")
ADMIN_SESSION_MAX_AGE = int(os.environ.get("GALLERY_ADMIN_SESSION_MAX_AGE", "604800"))
ADMIN_COOKIE_NAME = os.environ.get("GALLERY_ADMIN_COOKIE_NAME", "gallery_admin")
ADMIN_COOKIE_SECURE = os.environ.get("GALLERY_ADMIN_COOKIE_SECURE", "0") == "1"


def _load_auth_config() -> dict:
    defaults = {
        "registration_mode": "open",
        "default_groups": ["user"],
        "require_https": True,
        "session_days": 15,
        "password_min_length": 8,
        "username_pattern": "^[a-zA-Z0-9_-]{3,32}$",
        "invite_default_uses": 10,
    }
    if not AUTH_CONFIG_PATH.exists():
        return defaults
    try:
        raw = json.loads(AUTH_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if not isinstance(raw, dict):
        return defaults
    merged = dict(defaults)
    merged.update(raw)
    return merged


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, int):
        return value != 0
    return default


AUTH_CONFIG = _load_auth_config()
USER_COOKIE_NAME = os.environ.get("GALLERY_USER_COOKIE_NAME", "gallery_user")
USER_SECRET = os.environ.get("GALLERY_USER_SECRET", ADMIN_SECRET)


def _apply_auth_config(auth_cfg: dict) -> None:
    global AUTH_CONFIG
    global AUTH_REGISTRATION_MODE
    global AUTH_DEFAULT_GROUPS
    global AUTH_REQUIRE_HTTPS
    global AUTH_PASSWORD_MIN_LENGTH
    global AUTH_USERNAME_PATTERN
    global AUTH_INVITE_DEFAULT_USES
    global USER_SESSION_MAX_AGE
    global USER_COOKIE_SECURE

    AUTH_CONFIG = auth_cfg
    AUTH_REGISTRATION_MODE = str(auth_cfg.get("registration_mode") or "invite").lower()
    if AUTH_REGISTRATION_MODE not in {"open", "invite", "closed"}:
        AUTH_REGISTRATION_MODE = "invite"
    AUTH_DEFAULT_GROUPS = auth_cfg.get("default_groups") or ["user"]
    if not isinstance(AUTH_DEFAULT_GROUPS, list):
        AUTH_DEFAULT_GROUPS = ["user"]
    AUTH_REQUIRE_HTTPS = _to_bool(auth_cfg.get("require_https", True), True)
    AUTH_PASSWORD_MIN_LENGTH = int(auth_cfg.get("password_min_length", 8))
    AUTH_USERNAME_PATTERN = str(auth_cfg.get("username_pattern") or "^[a-zA-Z0-9_-]{3,32}$")
    AUTH_INVITE_DEFAULT_USES = int(auth_cfg.get("invite_default_uses", 10))
    USER_SESSION_MAX_AGE = int(
        os.environ.get(
            "GALLERY_USER_SESSION_MAX_AGE",
            str(int(auth_cfg.get("session_days", 15)) * 86400),
        )
    )
    USER_COOKIE_SECURE = os.environ.get(
        "GALLERY_USER_COOKIE_SECURE",
        "1" if AUTH_REQUIRE_HTTPS else "0",
    ) == "1"


def update_auth_config(updates: dict) -> dict:
    current = _load_auth_config()
    if isinstance(updates, dict):
        current.update(updates)
    AUTH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = AUTH_CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(AUTH_CONFIG_PATH)
    _apply_auth_config(current)
    return current


_apply_auth_config(AUTH_CONFIG)
