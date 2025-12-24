import base64
import os
import logging
import shutil
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Dict, Optional

from flask import Flask, jsonify, request
from waitress import serve
from logging.handlers import RotatingFileHandler

from . import admin_api
from . import config
from . import db
from . import storage


def allowed_extension_from_mime(mime: str) -> Optional[str]:
    return config.ALLOWED_MIME.get(mime)


def _extract_token_from_authorization(header: str) -> Optional[str]:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, value = parts[0].lower(), parts[1].strip()
    if scheme == "bearer":
        return value
    if scheme == "basic":
        try:
            decoded = base64.b64decode(value).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None
        if ":" not in decoded:
            return None
        username, password = decoded.split(":", 1)
        if config.UPLOAD_TOKEN_USER and username != config.UPLOAD_TOKEN_USER:
            return None
        return password
    return None


def require_upload_token():
    expected = config.UPLOAD_TOKEN
    if not expected:
        return None

    token = _extract_token_from_authorization(request.headers.get("Authorization", ""))
    if not token:
        token = request.headers.get("X-Upload-Token")

    if token != expected:
        try:
            db.insert_audit("upload_auth_failed", request.remote_addr, "invalid_token")
        except Exception:
            pass
        resp = jsonify({"error": "未授权"})
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = f'Bearer realm="{config.UPLOAD_REALM}"'
        return resp
    return None


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: Dict[str, deque] = {}

    def allow(self, key: str) -> Optional[int]:
        if self.max_requests <= 0:
            return None
        now = time.time()
        with self._lock:
            queue = self._hits.get(key)
            if queue is None:
                queue = deque()
                self._hits[key] = queue
            while queue and now - queue[0] > self.window_seconds:
                queue.popleft()
            if len(queue) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - queue[0])) + 1
                return max(retry_after, 1)
            queue.append(now)
        return None


_rate_limiter = RateLimiter(
    config.UPLOAD_RATE_LIMIT_MAX, config.UPLOAD_RATE_LIMIT_WINDOW_SECONDS
)


def _init_loggers() -> tuple[logging.Logger, logging.Logger]:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    access_logger = logging.getLogger("gallery_upload_access")
    error_logger = logging.getLogger("gallery_upload_error")
    if access_logger.handlers:
        for handler in list(access_logger.handlers):
            access_logger.removeHandler(handler)
            handler.close()
    if error_logger.handlers:
        for handler in list(error_logger.handlers):
            error_logger.removeHandler(handler)
            handler.close()
    if not access_logger.handlers:
        handler = RotatingFileHandler(
            config.LOG_DIR / "upload_access.log",
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        access_logger.addHandler(handler)
        access_logger.setLevel(logging.INFO)
    if not error_logger.handlers:
        handler = RotatingFileHandler(
            config.LOG_DIR / "upload_error.log",
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        error_logger.addHandler(handler)
        error_logger.setLevel(logging.WARNING)
    return access_logger, error_logger


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def _rate_limit_key() -> str:
    token = _extract_token_from_authorization(request.headers.get("Authorization", ""))
    if not token:
        token = request.headers.get("X-Upload-Token") or "anon"
    return f"{_client_ip()}:{token}"


def create_app() -> Flask:
    storage.ensure_dirs()
    db.ensure_schema()
    access_logger, error_logger = _init_loggers()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
    app.register_blueprint(admin_api.bp)

    @app.get("/health")
    def health():
        unauthorized = require_upload_token()
        if unauthorized:
            error_logger.warning("health unauthorized ip=%s", _client_ip())
            return unauthorized
        disk = shutil.disk_usage(config.STORAGE)
        queue = {"raw": 0, "processed": 0, "published": 0, "quarantined": 0}
        try:
            queue["raw"] = len([p for p in config.RAW_DIR.iterdir() if p.is_file()])
        except Exception:
            queue["raw"] = 0
        try:
            with db.connect() as conn:
                for row in conn.execute("SELECT status, COUNT(*) AS c FROM images GROUP BY status"):
                    queue[row["status"]] = row["c"]
        except Exception:
            pass
        payload = {
            "status": "ok",
            "generated_at": time.time(),
            "upload_paused": storage.upload_paused(),
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "low_watermark": config.DISK_LOW_WATERMARK_BYTES,
            },
            "queue": queue,
        }
        return jsonify(payload)

    @app.post("/upload")
    def upload():
        unauthorized = require_upload_token()
        if unauthorized:
            error_logger.warning("upload unauthorized ip=%s", _client_ip())
            return unauthorized
        retry_after = _rate_limiter.allow(_rate_limit_key())
        if retry_after:
            try:
                db.insert_audit("upload_rate_limited", _client_ip(), f"retry_after={retry_after}")
            except Exception:
                pass
            error_logger.warning("upload rate_limited ip=%s retry_after=%s", _client_ip(), retry_after)
            resp = jsonify({"error": "上传过于频繁，请稍后再试"})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(retry_after)
            return resp
        if storage.upload_paused():
            error_logger.warning("upload paused ip=%s", _client_ip())
            return jsonify({"error": "上传已暂停：磁盘保护"}), 503
        if not storage.disk_has_space(config.STORAGE):
            error_logger.warning("upload no_space ip=%s", _client_ip())
            return jsonify({"error": "磁盘空间不足，已暂停上传"}), 503

        file = request.files.get("file")
        if not file or not file.stream:
            try:
                db.insert_audit("upload_error", _client_ip(), "missing_file")
            except Exception:
                pass
            error_logger.warning("upload missing_file ip=%s", _client_ip())
            return jsonify({"error": "缺少文件"}), 400

        original_name = file.filename or "upload"
        file_mime = file.mimetype or ""
        if file_mime and file_mime not in config.ALLOWED_MIME:
            try:
                db.insert_audit("upload_rejected", original_name, f"content_type={file_mime}")
            except Exception:
                pass
            error_logger.warning("upload reject content_type=%s name=%s", file_mime, original_name)
            return jsonify({"error": "不支持的文件类型"}), 400
        ext_from_name = Path(original_name).suffix.lower()
        if ext_from_name and ext_from_name not in config.ALLOWED_MIME.values():
            try:
                db.insert_audit("upload_rejected", original_name, f"extension={ext_from_name}")
            except Exception:
                pass
            error_logger.warning("upload reject extension=%s name=%s", ext_from_name, original_name)
            return jsonify({"error": "不支持的文件扩展名"}), 400
        upload_uuid = uuid.uuid4().hex
        tmp_path = config.UPLOAD_TMP / f"{upload_uuid}.part"

        try:
            bytes_written, sha256 = storage.write_stream_to_tmp(file.stream, tmp_path)
        except ValueError as exc:
            storage.move_to_quarantine(tmp_path, f"size_error: {exc}")
            try:
                db.insert_audit("upload_quarantine", original_name, f"size_error:{exc}")
            except Exception:
                pass
            error_logger.warning("upload size_error name=%s err=%s", original_name, exc)
            return jsonify({"error": str(exc)}), 413
        except Exception as exc:  # noqa: BLE001
            storage.move_to_quarantine(tmp_path, f"write_error: {exc}")
            try:
                db.insert_audit("upload_quarantine", original_name, f"write_error:{exc}")
            except Exception:
                pass
            error_logger.warning("upload write_error name=%s err=%s", original_name, exc)
            return jsonify({"error": "写入失败"}), 500

        mime = storage.detect_mime(tmp_path)
        ext = allowed_extension_from_mime(mime or "")
        if not ext:
            storage.move_to_quarantine(tmp_path, f"mime_not_allowed: {mime}")
            try:
                db.insert_audit("upload_quarantine", original_name, f"mime_not_allowed:{mime}")
            except Exception:
                pass
            error_logger.warning("upload mime_not_allowed name=%s mime=%s", original_name, mime)
            return jsonify({"error": "不支持的文件类型"}), 400

        target_name = f"{upload_uuid}{ext}"
        raw_path = config.RAW_DIR / target_name

        try:
            storage.atomic_move(tmp_path, raw_path)
        except Exception as exc:  # noqa: BLE001
            storage.move_to_quarantine(tmp_path, f"move_error: {exc}")
            try:
                db.insert_audit("upload_quarantine", original_name, f"move_error:{exc}")
            except Exception:
                pass
            error_logger.warning("upload move_error name=%s err=%s", original_name, exc)
            return jsonify({"error": "提交失败"}), 500

        resp: Dict[str, object] = {
            "uuid": upload_uuid,
            "original_name": original_name,
            "stored": str(raw_path.relative_to(config.STORAGE)),
            "bytes": bytes_written,
            "sha256": sha256,
            "mime": mime,
        }
        try:
            db.insert_audit("upload_committed", upload_uuid, f"bytes={bytes_written}")
        except Exception:
            pass
        access_logger.info("upload ok uuid=%s bytes=%s name=%s", upload_uuid, bytes_written, original_name)
        return jsonify(resp), 201

    return app


def main():
    # 仅用于开发调试
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
