import re
import sqlite3
from typing import Optional

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import auth
from . import config
from . import db

bp = Blueprint("auth", __name__)

_USERNAME_RE = re.compile(config.AUTH_USERNAME_PATTERN)


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


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def _set_user_cookie(resp, token: str) -> None:
    resp.set_cookie(
        config.USER_COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
        secure=config.USER_COOKIE_SECURE,
        max_age=config.USER_SESSION_MAX_AGE,
    )


def _clear_user_cookie(resp) -> None:
    resp.set_cookie(
        config.USER_COOKIE_NAME,
        "",
        httponly=True,
        samesite="Lax",
        secure=config.USER_COOKIE_SECURE,
        expires=0,
    )


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


def _validate_username(username: str) -> Optional[str]:
    if not username:
        return "用户名不能为空"
    if not _USERNAME_RE.match(username):
        return "用户名格式不正确"
    return None


def _validate_password(password: str, *, check_length: bool = True) -> Optional[str]:
    if not password:
        return "密码不能为空"
    if check_length and len(password) < config.AUTH_PASSWORD_MIN_LENGTH:
        return f"密码至少 {config.AUTH_PASSWORD_MIN_LENGTH} 位"
    return None


@bp.post("/auth/register")
def register():
    https_error = _require_https()
    if https_error:
        return https_error
    if config.AUTH_REGISTRATION_MODE == "closed":
        return _json_error("注册已关闭", 403)
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    password_confirm = str(payload.get("password_confirm") or "")
    invite_code = str(payload.get("invite_code") or "").strip()

    err = _validate_username(username)
    if err:
        return _json_error(err)
    err = _validate_password(password)
    if err:
        return _json_error(err)
    if not password_confirm:
        return _json_error("请再次输入密码")
    if password != password_confirm:
        return _json_error("两次密码不一致")

    if config.AUTH_REGISTRATION_MODE == "invite" and not invite_code:
        return _json_error("邀请码不能为空")

    groups = [str(g) for g in config.AUTH_DEFAULT_GROUPS if str(g).strip()] or ["user"]
    try:
        with db.transaction() as conn:
            user = auth.create_user(username, password, groups=groups, conn=conn)
            if config.AUTH_REGISTRATION_MODE == "invite":
                invite_err = auth.consume_invite(invite_code, user.id, ip=_client_ip(), conn=conn)
                if invite_err:
                    raise ValueError(invite_err)
    except ValueError as exc:
        return _json_error(str(exc))
    except sqlite3.IntegrityError:
        return _json_error("用户名已存在", 409)
    except Exception:
        return _json_error("注册失败", 500)

    groups = auth.get_user_groups(user.id)
    serializer = _serializer()
    token = serializer.dumps({"id": user.id, "u": user.username})
    resp = jsonify({"ok": True, "user": user.username, "groups": groups})
    resp.status_code = 201
    _set_user_cookie(resp, token)
    return resp


@bp.post("/auth/login")
def login():
    https_error = _require_https()
    if https_error:
        return https_error
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    err = _validate_username(username)
    if err:
        return _json_error(err)
    err = _validate_password(password, check_length=False)
    if err:
        return _json_error(err)
    user = auth.authenticate(username, password)
    if not user:
        return _json_error("账号或密码错误", 401)
    groups = auth.get_user_groups(user.id)
    serializer = _serializer()
    token = serializer.dumps({"id": user.id, "u": user.username})
    resp = jsonify({"ok": True, "user": user.username, "groups": groups})
    _set_user_cookie(resp, token)
    return resp


@bp.post("/auth/logout")
def logout():
    https_error = _require_https()
    if https_error:
        return https_error
    resp = jsonify({"ok": True})
    _clear_user_cookie(resp)
    return resp


@bp.get("/auth/me")
def me():
    https_error = _require_https()
    if https_error:
        return https_error
    user = _load_user_from_cookie()
    if not user:
        return _json_error("未授权", 401)
    groups = auth.get_user_groups(user.id)
    return jsonify({"ok": True, "user": user.username, "groups": groups})
