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
LOG_DIR = STORAGE / "logs"
LOG_MAX_BYTES = int(os.environ.get("GALLERY_LOG_MAX_BYTES", "2097152"))
LOG_BACKUP_COUNT = int(os.environ.get("GALLERY_LOG_BACKUPS", "5"))
TRASH_RETENTION_DAYS = int(os.environ.get("GALLERY_TRASH_RETENTION_DAYS", "5"))

# 图片处理限制
MAX_PIXELS = 50_000_000             # 避免超大分辨率
THUMB_SIZE = (960, 960)
THUMB_QUALITY = 85

ALLOWED_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# 访问控制（上传口令可选，未设置则不校验）
UPLOAD_TOKEN = os.environ.get("GALLERY_UPLOAD_TOKEN")
UPLOAD_TOKEN_USER = os.environ.get("GALLERY_UPLOAD_USER")
UPLOAD_REALM = os.environ.get("GALLERY_UPLOAD_REALM", "gallery-upload")

# 管理后台鉴权
ADMIN_USER = os.environ.get("GALLERY_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("GALLERY_ADMIN_PASSWORD")
ADMIN_PASSWORD_HASH = os.environ.get("GALLERY_ADMIN_PASSWORD_HASH")
ADMIN_SECRET = os.environ.get("GALLERY_ADMIN_SECRET", "gallery-admin-secret")
ADMIN_SESSION_MAX_AGE = int(os.environ.get("GALLERY_ADMIN_SESSION_MAX_AGE", "604800"))
ADMIN_COOKIE_NAME = os.environ.get("GALLERY_ADMIN_COOKIE_NAME", "gallery_admin")
ADMIN_COOKIE_SECURE = os.environ.get("GALLERY_ADMIN_COOKIE_SECURE", "0") == "1"
