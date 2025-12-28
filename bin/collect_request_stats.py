#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_gallery_root() -> str:
    root = os.environ.get("GALLERY_ROOT", "/opt/PotatoGallery")
    env_path = Path("/etc/gallery/gallery_root.env")
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("GALLERY_ROOT="):
                    root = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    os.environ["GALLERY_ROOT"] = root
    return root


root_path = load_gallery_root()
if root_path and root_path not in sys.path:
    sys.path.insert(0, root_path)

from app import config  # noqa: E402
from app import request_stats  # noqa: E402


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    try:
        os.chmod(path, 0o644)
    except PermissionError:
        pass


def normalize_counts(raw: dict, now_iso: str) -> dict:
    return {
        "total_requests": int(raw.get("total_requests", 0) or 0),
        "page_requests": int(raw.get("page_requests", 0) or 0),
        "api_requests": int(raw.get("api_requests", 0) or 0),
        "started_at": raw.get("started_at") or now_iso,
        "updated_at": raw.get("updated_at") or now_iso,
    }


def normalize_state(raw: dict) -> dict:
    return {
        "inode": raw.get("inode"),
        "offset": int(raw.get("offset", 0) or 0),
    }


def main() -> int:
    log_path = Path("/var/log/nginx/access.log")
    counts_path = config.STATUS_DATA_DIR / "request_counts.json"
    state_path = config.STATUS_DATA_DIR / "request_counts_state.json"
    if not log_path.exists():
        return 0

    stat = log_path.stat()
    now_iso = datetime.now(timezone.utc).isoformat()
    counts = normalize_counts(read_json(counts_path), now_iso)
    state = normalize_state(read_json(state_path))

    inode = stat.st_ino
    offset = state.get("offset", 0)
    if state.get("inode") != inode or stat.st_size < offset:
        offset = 0

    total_inc = 0
    page_inc = 0
    api_inc = 0
    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(offset)
        for line in f:
            total_inc += 1
            path = request_stats.parse_request_path(line)
            if not path:
                continue
            if request_stats.is_api_path(path):
                api_inc += 1
            if request_stats.is_page_path(path):
                page_inc += 1
        offset = f.tell()

    counts["total_requests"] += total_inc
    counts["page_requests"] += page_inc
    counts["api_requests"] += api_inc
    counts["updated_at"] = now_iso
    write_json(counts_path, counts)

    state_payload = {"inode": inode, "offset": offset, "updated_at": now_iso}
    write_json(state_path, state_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
