"""Simple in-memory login rate limiter."""
import threading
import time
from typing import Dict, List

from flask import jsonify, request


class LoginRateLimiter:
    """Track failed login attempts per IP and block after threshold."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._attempts: Dict[str, List[float]] = {}

    def _client_ip(self) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"

    def _cleanup(self, ip: str, now: float) -> None:
        cutoff = now - self.window_seconds
        attempts = self._attempts.get(ip)
        if attempts:
            self._attempts[ip] = [t for t in attempts if t > cutoff]
            if not self._attempts[ip]:
                del self._attempts[ip]

    def _status_locked(self, ip: str, now: float) -> dict:
        attempts = self._attempts.get(ip, [])
        retry_after = 0
        reset_at = 0
        if attempts:
            retry_after = max(int(self.window_seconds - (now - attempts[0])) + 1, 1)
            reset_at = int(now + retry_after)
        return {
            "attempts_remaining": max(self.max_attempts - len(attempts), 0),
            "max_attempts": self.max_attempts,
            "retry_after": retry_after,
            "reset_at": reset_at,
        }

    def status(self) -> dict:
        """Return current limiter status for the request IP."""
        ip = self._client_ip()
        now = time.time()
        with self._lock:
            self._cleanup(ip, now)
            return self._status_locked(ip, now)

    def is_blocked(self) -> dict:
        """Return limiter status including whether the current IP is blocked."""
        info = self.status()
        info["blocked"] = info["attempts_remaining"] <= 0 and info["retry_after"] > 0
        return info

    def record_failure(self) -> dict:
        """Record a failed login attempt for the current IP and return status."""
        ip = self._client_ip()
        now = time.time()
        with self._lock:
            self._cleanup(ip, now)
            self._attempts.setdefault(ip, []).append(now)
            return self._status_locked(ip, now)

    def record_success(self) -> None:
        """Clear attempts for the current IP on successful login."""
        ip = self._client_ip()
        with self._lock:
            self._attempts.pop(ip, None)

    def check_and_block(self):
        """Decorator-style: check before login, return error response if blocked."""
        info = self.is_blocked()
        if info.pop("blocked"):
            resp = jsonify({"error": "登录尝试过多", **info})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(info["retry_after"])
            return resp
        return None


# Shared instances: 5 attempts per 5 minutes
auth_login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
