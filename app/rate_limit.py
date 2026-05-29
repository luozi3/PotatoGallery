"""Simple in-memory login rate limiter."""
import threading
import time
from functools import wraps
from typing import Dict, List, Tuple

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

    def is_blocked(self) -> Tuple[bool, int]:
        """Check if the current IP is blocked. Returns (blocked, retry_after)."""
        ip = self._client_ip()
        now = time.time()
        with self._lock:
            self._cleanup(ip, now)
            attempts = self._attempts.get(ip, [])
            if len(attempts) >= self.max_attempts:
                oldest = attempts[0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                return True, max(retry_after, 1)
            return False, 0

    def record_failure(self) -> None:
        """Record a failed login attempt for the current IP."""
        ip = self._client_ip()
        now = time.time()
        with self._lock:
            self._cleanup(ip, now)
            self._attempts.setdefault(ip, []).append(now)

    def record_success(self) -> None:
        """Clear attempts for the current IP on successful login."""
        ip = self._client_ip()
        with self._lock:
            self._attempts.pop(ip, None)

    def check_and_block(self):
        """Decorator-style: check before login, return error response if blocked."""
        blocked, retry_after = self.is_blocked()
        if blocked:
            resp = jsonify({
                "error": f"登录尝试过多，请 {retry_after} 秒后再试",
                "retry_after": retry_after,
            })
            resp.status_code = 429
            return resp
        return None


# Shared instances: 5 attempts per 5 minutes
auth_login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
admin_login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
