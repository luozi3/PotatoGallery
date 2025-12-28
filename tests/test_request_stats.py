import importlib.util
from pathlib import Path

from app import request_stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_parse_request_path_strips_query():
    line = (
        '127.0.0.1 - - [27/Dec/2024:12:34:56 +0000] '
        '"GET /search/?q=cat&x=1 HTTP/1.1" 200 123 "-" "UA"'
    )
    assert request_stats.parse_request_path(line) == "/search/"


def test_parse_request_path_handles_api():
    line = (
        '127.0.0.1 - - [27/Dec/2024:12:34:56 +0000] '
        '"POST /api/images/abc123?edit=1 HTTP/1.1" 200 123 "-" "UA"'
    )
    assert request_stats.parse_request_path(line) == "/api/images/abc123"


def test_parse_request_path_invalid_line():
    assert request_stats.parse_request_path("no request here") is None


def test_request_path_classification():
    assert request_stats.is_page_path("/")
    assert request_stats.is_page_path("/status/")
    assert request_stats.is_page_path("/about.html")
    assert not request_stats.is_page_path("/static/app.css")
    assert not request_stats.is_page_path("/thumb/x.webp")
    assert not request_stats.is_page_path("/raw/x.png")
    assert not request_stats.is_page_path("/api/upload")
    assert request_stats.is_api_path("/api/upload")
    assert not request_stats.is_api_path("/upload/admin/login")


def test_collect_request_stats_module_importable(monkeypatch):
    monkeypatch.setenv("GALLERY_ROOT", str(PROJECT_ROOT))
    path = PROJECT_ROOT / "bin" / "collect_request_stats.py"
    spec = importlib.util.spec_from_file_location("collect_request_stats", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert hasattr(module, "normalize_counts")
