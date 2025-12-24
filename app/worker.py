import datetime
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import List, Optional
try:
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from . import config
from . import db
from . import image_utils
from . import static_site
from .storage import detect_mime, ensure_dirs, fsync_path, move_to_quarantine


def parse_uuid_from_name(path: Path) -> Optional[str]:
    match = re.match(r"^([0-9a-fA-F]{32})", path.name)
    return match.group(1).lower() if match else None


THUMB_NAME_PATTERN = re.compile(r"^L(\d{8})A(\d{3})\.jpg$")


def next_thumb_filename(today: Optional[datetime.date] = None) -> str:
    """
    生成短路径缩略图名：L + 日期 + 序号（如 L20251220A001）。
    单线程 worker，按 DB 已有记录递增，确保可维护与可追踪。
    """
    date = today or datetime.date.today()
    date_str = date.strftime("%Y%m%d")
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT thumb_path FROM images WHERE thumb_path LIKE ?",
            (f"thumb/L{date_str}A%",),
        ).fetchall()
    max_seq = 0
    for row in rows:
        name = Path(row["thumb_path"]).name if row["thumb_path"] else ""
        match = THUMB_NAME_PATTERN.match(name)
        if match:
            max_seq = max(max_seq, int(match.group(2)))
    return f"L{date_str}A{max_seq + 1:03d}.jpg"


def next_raw_file() -> Optional[Path]:
    candidates = sorted(
        [p for p in config.RAW_DIR.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    with db.connect() as conn:
        for path in candidates:
            uuid = parse_uuid_from_name(path)
            if not uuid:
                move_to_quarantine(path, "invalid_filename")
                db.insert_audit("quarantine", path.name, "invalid filename")
                continue
            row = conn.execute("SELECT status FROM images WHERE uuid=?", (uuid,)).fetchone()
            if row and row["status"] in ("processed", "published", "quarantined"):
                continue
            return path
    return None


def process_file(path: Path) -> bool:
    db.ensure_schema()
    ensure_dirs()
    uuid = parse_uuid_from_name(path)
    if not uuid:
        move_to_quarantine(path, "invalid_filename")
        db.insert_audit("quarantine", path.name, "invalid filename")
        return False

    ext = path.suffix.lower()
    if ext not in config.ALLOWED_MIME.values():
        move_to_quarantine(path, f"ext_not_allowed:{ext}")
        db.insert_audit("quarantine", path.name, f"ext_not_allowed:{ext}")
        return False

    mime = detect_mime(path)
    with db.connect() as conn:
        existing = conn.execute(
            "SELECT thumb_path FROM images WHERE uuid=?",
            (uuid,),
        ).fetchone()
    thumb_filename = (
        Path(existing["thumb_path"]).name
        if existing and existing["thumb_path"]
        else next_thumb_filename()
    )
    thumb_path = config.THUMB_DIR / thumb_filename
    try:
        width, height = image_utils.read_dimensions(path)
        sha256 = image_utils.compute_sha256(path)
        size_bytes = path.stat().st_size
        thumb_width, thumb_height = image_utils.make_thumbnail(path, thumb_path)
        color = image_utils.dominant_color(thumb_path)
    except Exception as exc:  # noqa: BLE001
        move_to_quarantine(path, f"processing_failed:{exc}")
        db.insert_audit("quarantine", path.name, f"processing_failed:{exc}")
        return False

    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO images (uuid, original_name, ext, mime, width, height, bytes, sha256, status, stored_path, thumb_path, thumb_width, thumb_height, dominant_color, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(uuid) DO UPDATE SET
                ext=excluded.ext,
                mime=excluded.mime,
                width=excluded.width,
                height=excluded.height,
                bytes=excluded.bytes,
                sha256=excluded.sha256,
                status='processed',
                stored_path=excluded.stored_path,
                thumb_path=excluded.thumb_path,
                thumb_width=excluded.thumb_width,
                thumb_height=excluded.thumb_height,
                dominant_color=excluded.dominant_color,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                uuid,
                path.name,
                ext,
                mime or "",
                width,
                height,
                size_bytes,
                sha256,
                f"raw/{path.name}",
                f"thumb/{thumb_filename}",
                thumb_width,
                thumb_height,
                color,
            ),
        )
        conn.execute(
            "INSERT INTO jobs (image_uuid, stage, status, message) VALUES (?, ?, ?, ?)",
            (uuid, "process", "done", ""),
        )

    return True


def rebuild_and_publish(log_build: bool = True) -> Path:
    build_id = f"build_{int(time.time())}"
    rows = images_for_site()
    staging_dir = static_site.build_site(rows)
    static_site.publish(staging_dir)
    write_last_static_mtime(latest_static_mtime())
    clear_force_flag()
    if log_build:
        try:
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO builds (build_id, status, staging_path, published_at, created_at, updated_at) VALUES (?, 'published', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (build_id, str(staging_dir)),
                )
        except Exception:
            pass
    return staging_dir


def images_for_site() -> List[dict]:
    db.ensure_schema()
    with db.connect() as conn:
        return conn.execute(
            """
            SELECT uuid, original_name, ext, bytes, width, height, thumb_width, thumb_height, sha256, dominant_color, created_at, thumb_path,
                   title_override, description, tags_json, collection_override
            FROM images
            WHERE status IN ('processed','published')
              AND deleted_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()


def publish_ready_images() -> bool:
    with db.connect() as conn:
        pending = [row["uuid"] for row in conn.execute("SELECT uuid FROM images WHERE status='processed'").fetchall()]
    if not pending:
        return False

    staging_dir = rebuild_and_publish(log_build=False)

    with db.transaction() as conn:
        conn.execute(
            "UPDATE images SET status='published', updated_at=CURRENT_TIMESTAMP WHERE status='processed'"
        )
        conn.executemany(
            "INSERT INTO jobs (image_uuid, stage, status, message) VALUES (?, ?, ?, ?)",
            [(uuid, "publish", "done", "published to www") for uuid in pending],
        )
        conn.execute(
            "INSERT INTO builds (build_id, status, staging_path, published_at, created_at, updated_at) VALUES (?, 'published', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (f"build_{int(time.time())}", str(staging_dir)),
        )
    write_status_snapshot()
    return True


def latest_static_mtime() -> float:
    """
    获取 static 目录内最新修改时间，用于判断是否需要无图也重建站点。
    """
    newest = 0.0
    for path in config.STATIC.rglob("*"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except FileNotFoundError:
            continue
    return newest


def read_last_static_mtime() -> float:
    try:
        return float(config.LAST_STATIC_MTIME.read_text())
    except Exception:
        return 0.0


def write_last_static_mtime(ts: float) -> None:
    config.LAST_STATIC_MTIME.parent.mkdir(parents=True, exist_ok=True)
    config.LAST_STATIC_MTIME.write_text(str(ts), encoding="utf-8")


def clear_force_flag() -> None:
    if config.FORCE_REBUILD_FLAG.exists():
        try:
            config.FORCE_REBUILD_FLAG.unlink()
        except OSError:
            pass


def collect_status_metrics() -> dict:
    """
    汇总运行状态，写入静态探针。
    """
    tz = ZoneInfo("Asia/Shanghai") if ZoneInfo else datetime.timezone(datetime.timedelta(hours=8))
    disk = shutil.disk_usage(config.STORAGE)
    paused = config.UPLOAD_PAUSE_FLAG.exists()
    statuses: dict = {"total": 0, "processed": 0, "published": 0, "quarantined": 0}
    last_build = {}
    with db.connect() as conn:
        for row in conn.execute("SELECT status, COUNT(*) AS c FROM images GROUP BY status"):
            statuses[row["status"]] = row["c"]
            statuses["total"] += row["c"]
        build = conn.execute(
            "SELECT build_id, published_at FROM builds ORDER BY published_at DESC LIMIT 1"
        ).fetchone()
        if build:
            published_at = build["published_at"]
            published_local = ""
            try:
                dt = datetime.datetime.fromisoformat(published_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                published_local = dt.astimezone(tz).isoformat()
            except Exception:
                published_local = published_at or ""
            last_build = {"id": build["build_id"], "published_at": published_at, "published_at_local": published_local}

    raw_files = len([p for p in config.RAW_DIR.glob("*") if p.is_file()])
    thumb_files = len([p for p in config.THUMB_DIR.glob("*") if p.is_file()])
    load1, load5, load15 = os.getloadavg()
    cpu_count = os.cpu_count() or 1

    meminfo = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, value = line.split(":", 1)
                meminfo[key.strip()] = int(value.strip().split()[0]) * 1024  # kB→B
    except Exception:
        meminfo = {}
    mem_total = meminfo.get("MemTotal", 0)
    mem_available = meminfo.get("MemAvailable", 0)
    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)

    metrics = {
        "generated_at": datetime.datetime.now(tz).isoformat(),
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "low_watermark": config.DISK_LOW_WATERMARK_BYTES,
            "paused": paused,
        },
        "images": {
            "total": statuses.get("total", 0),
            "processed": statuses.get("processed", 0),
            "published": statuses.get("published", 0),
            "quarantined": statuses.get("quarantined", 0),
        },
        "raw_files": raw_files,
        "thumb_files": thumb_files,
        "last_build": last_build,
        "upload_paused": paused,
        "load": {"avg": [load1, load5, load15], "cpus": cpu_count},
        "memory": {
            "total": mem_total,
            "available": mem_available,
            "swap_total": swap_total,
            "swap_free": swap_free,
        },
    }
    return metrics


def write_status_snapshot() -> None:
    """
    写入静态探针文件，供 /status.html 读取。
    """
    metrics = collect_status_metrics()
    persist_dir = config.STATUS_DATA_DIR
    persist_dir.mkdir(parents=True, exist_ok=True)
    tmp = persist_dir / "status.json.tmp"
    final = persist_dir / "status.json"
    tmp.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, final)
    try:
        os.chmod(final, 0o644)
    except PermissionError:
        pass
    fsync_path(final.parent)

    history_path = persist_dir / "status_history.json"
    history = []
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []
    history.append(metrics)
    history = history[-120:]  # 保留最近 120 条
    tmp_hist = persist_dir / "status_history.json.tmp"
    tmp_hist.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_hist, history_path)
    try:
        os.chmod(history_path, 0o644)
    except PermissionError:
        pass
    fsync_path(history_path.parent)

    target_dir = config.WWW_DIR / "static"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        try:
            config.FORCE_REBUILD_FLAG.write_text("status_sync_failed", encoding="utf-8")
        except Exception:
            pass
        return

    sync_failed = not os.access(target_dir, os.W_OK)
    for name in ["status.json", "status_history.json"]:
        src = persist_dir / name
        dst = target_dir / name
        try:
            shutil.copy2(src, dst)
            os.chmod(dst, 0o644)
        except PermissionError:
            sync_failed = True
        except Exception:
            continue
    fsync_path(target_dir)
    if sync_failed:
        try:
            config.FORCE_REBUILD_FLAG.write_text("status_sync_failed", encoding="utf-8")
        except Exception:
            pass


def ensure_static_up_to_date() -> bool:
    """
    即使没有新图片，只要前端源码变更或存在强制标记，就重建并发布。
    返回是否执行了重建。
    """
    force = config.FORCE_REBUILD_FLAG.exists()
    current_mtime = latest_static_mtime()
    last_mtime = read_last_static_mtime()
    need_rebuild = force or current_mtime > last_mtime
    if not need_rebuild:
        return False

    staging_dir = rebuild_and_publish()
    write_last_static_mtime(current_mtime)
    clear_force_flag()
    write_status_snapshot()
    return True


def loop(interval: int = 5) -> None:
    static_site.ensure_www_readable()
    last_perm_fix = time.time()
    while True:
        ensure_dirs()
        now = time.time()
        if now - last_perm_fix >= 60:
            static_site.ensure_www_readable()
            last_perm_fix = now

        processed_any = False
        while True:
            path = next_raw_file()
            if not path:
                break
            ok = process_file(path)
            processed_any = processed_any or ok

        if publish_ready_images():
            static_site.ensure_www_readable()
            last_perm_fix = time.time()
            continue

        ensure_static_up_to_date()

        write_status_snapshot()
        if not processed_any:
            time.sleep(interval)


def main():
    loop()


if __name__ == "__main__":
    main()
