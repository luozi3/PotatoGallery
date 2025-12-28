import os
import logging
import shutil
import time

from flask import Flask, jsonify, make_response, request
from waitress import serve
from logging.handlers import RotatingFileHandler
from werkzeug.exceptions import HTTPException

from . import admin_api
from . import auth_api
from . import auth
from . import config
from . import db
from . import storage
from . import user_api


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


def create_app() -> Flask:
    storage.ensure_dirs()
    db.ensure_schema()
    auth.bootstrap_admin_if_needed()
    access_logger, error_logger = _init_loggers()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
    app.register_blueprint(admin_api.bp)
    app.register_blueprint(auth_api.bp)
    app.register_blueprint(user_api.bp)

    def _json_error(message: str, status: int = 400):
        resp = jsonify({"error": message})
        resp.status_code = status
        return resp

    def _prefers_html() -> bool:
        accept = request.accept_mimetypes
        if not accept:
            return False
        best = accept.best
        if best == "text/html":
            return True
        if "text/html" in accept and accept["text/html"] >= accept["application/json"]:
            return True
        return False

    def _load_error_page(status: int) -> str:
        if status == 404:
            path = config.WWW_DIR / "404.html"
            title = "页面未找到"
        elif status == 503:
            path = config.WWW_DIR / "maintenance.html"
            title = "维护中"
        else:
            path = config.WWW_DIR / "error" / "index.html"
            title = "发生错误"
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            error_logger.exception("failed to read error page: %s", path)
        return (
            "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            f"<title>{title}</title></head><body><h1>{title}</h1></body></html>"
        )

    def _render_error_html(status: int):
        html = _load_error_page(status)
        resp = make_response(html, status)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    def _json_error_message(status: int) -> str:
        if status == 401:
            return "未授权"
        if status == 403:
            return "无权限"
        if status == 404:
            return "接口不存在"
        if status == 405:
            return "不支持的请求方法"
        if status == 413:
            return "请求内容过大"
        if status >= 500:
            return "服务暂时不可用"
        return "请求失败"

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        status = exc.code or 500
        if _prefers_html():
            return _render_error_html(status)
        return _json_error(_json_error_message(status), status)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc: Exception):
        error_logger.exception("unhandled error", exc_info=exc)
        if _prefers_html():
            return _render_error_html(500)
        return _json_error("服务暂时不可用", 500)

    @app.get("/health")
    def health():
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

    return app


def main():
    # 仅用于开发调试
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    serve(
        app,
        host="0.0.0.0",
        port=port,
        trusted_proxy="127.0.0.1",
        trusted_proxy_count=1,
        trusted_proxy_headers="x-forwarded-for x-forwarded-proto x-forwarded-host",
        clear_untrusted_proxy_headers=True,
    )


if __name__ == "__main__":
    main()
