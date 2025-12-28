import re
from typing import Optional


_REQUEST_RE = re.compile(r'"[A-Z]+\s+([^"\s]+)\s+HTTP/[0-9.]+"')
_PAGE_EXCLUDE_PREFIXES = ("/static/", "/thumb/", "/raw/", "/api/", "/upload/", "/auth/")


def parse_request_path(line: str) -> Optional[str]:
    match = _REQUEST_RE.search(line)
    if not match:
        return None
    path = match.group(1)
    if not path.startswith("/"):
        return None
    return path.split("?", 1)[0]


def is_api_path(path: str) -> bool:
    return path.startswith("/api/")


def is_page_path(path: str) -> bool:
    if not path:
        return False
    if any(path.startswith(prefix) for prefix in _PAGE_EXCLUDE_PREFIXES):
        return False
    return path == "/" or path.endswith("/") or path.endswith(".html")
