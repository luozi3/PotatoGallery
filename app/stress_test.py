import datetime
import io
import random
import threading
import time
import uuid
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw

from . import config
from . import db
from . import storage


STATUS_RUNNING = "running"
STATUS_STOPPING = "stopping"
STATUS_STOPPED = "stopped"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CLEANED = "cleaned"

DEFAULT_TOTAL = 500
DEFAULT_MIN_SIZE = 360
DEFAULT_MAX_SIZE = 900
DEFAULT_FORMAT = "WEBP"

_STATE_LOCK = threading.Lock()
_STATE = {"thread": None, "stop_event": None, "job_id": None}


def _utcnow() -> str:
    return datetime.datetime.utcnow().isoformat()


def _update_job(
    job_id: int,
    *,
    status: Optional[str] = None,
    generated: Optional[int] = None,
    message: Optional[str] = None,
) -> None:
    updates = []
    params = []
    if status is not None:
        updates.append("status=?")
        params.append(status)
    if generated is not None:
        updates.append("generated=?")
        params.append(generated)
    if message is not None:
        updates.append("message=?")
        params.append(message)
    updates.append("updated_at=?")
    params.append(_utcnow())
    params.append(job_id)
    with db.transaction() as conn:
        conn.execute(f"UPDATE stress_jobs SET {', '.join(updates)} WHERE id=?", params)


def _load_job(job_id: int) -> Optional[dict]:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT j.id, j.owner_user_id, j.status, j.total, j.generated,
                   j.min_width, j.max_width, j.min_height, j.max_height, j.format,
                   j.message, j.created_at, j.updated_at, u.username
            FROM stress_jobs j
            LEFT JOIN auth_users u ON u.id = j.owner_user_id
            WHERE j.id=?
            """,
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def _find_active_job() -> Optional[dict]:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT j.id, j.owner_user_id, j.status, j.total, j.generated,
                   j.min_width, j.max_width, j.min_height, j.max_height, j.format,
                   j.message, j.created_at, j.updated_at, u.username
            FROM stress_jobs j
            LEFT JOIN auth_users u ON u.id = j.owner_user_id
            WHERE j.status IN (?, ?)
            ORDER BY j.id DESC
            LIMIT 1
            """,
            (STATUS_RUNNING, STATUS_STOPPING),
        ).fetchone()
    return dict(row) if row else None


def _count_progress(job_id: int) -> Dict[str, int]:
    counts: Dict[str, int] = {"queued": 0, "processed": 0, "published": 0, "quarantined": 0}
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM upload_requests WHERE stress_job_id=?",
            (job_id,),
        ).fetchone()
        counts["queued"] = int(row["c"]) if row else 0
        for row in conn.execute(
            "SELECT status, COUNT(*) AS c FROM images WHERE stress_job_id=? GROUP BY status",
            (job_id,),
        ):
            status = str(row["status"] or "")
            counts[status] = int(row["c"] or 0)
    return counts


def _build_status(job: dict) -> dict:
    counts = _count_progress(job["id"])
    processed = int(counts.get("processed", 0))
    published = int(counts.get("published", 0))
    quarantined = int(counts.get("quarantined", 0))
    queued = int(counts.get("queued", 0))
    total = int(job.get("total") or 0)
    generated = int(job.get("generated") or 0)
    active_processing = queued + processed > 0
    active = job.get("status") in {STATUS_RUNNING, STATUS_STOPPING} or active_processing
    percent = int((published / total) * 100) if total else 0
    return {
        "job": job,
        "counts": {
            "queued": queued,
            "processed": processed,
            "published": published,
            "quarantined": quarantined,
        },
        "active": active,
        "percent": percent,
    }


def get_status_for_admin() -> dict:
    db.ensure_schema()
    job = _find_active_job()
    if not job:
        with db.connect() as conn:
            row = conn.execute(
                """
                SELECT j.id, j.owner_user_id, j.status, j.total, j.generated,
                       j.min_width, j.max_width, j.min_height, j.max_height, j.format,
                       j.message, j.created_at, j.updated_at, u.username
                FROM stress_jobs j
                LEFT JOIN auth_users u ON u.id = j.owner_user_id
                ORDER BY j.id DESC
                LIMIT 1
                """
            ).fetchone()
        job = dict(row) if row else None
    if not job:
        return {"active": False, "job": None, "counts": {}}
    return _build_status(job)


def get_status_for_user(owner_user_id: int) -> dict:
    db.ensure_schema()
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT j.id, j.owner_user_id, j.status, j.total, j.generated,
                   j.min_width, j.max_width, j.min_height, j.max_height, j.format,
                   j.message, j.created_at, j.updated_at, u.username
            FROM stress_jobs j
            LEFT JOIN auth_users u ON u.id = j.owner_user_id
            WHERE j.owner_user_id=?
            ORDER BY j.id DESC
            LIMIT 1
            """,
            (owner_user_id,),
        ).fetchone()
    if not row:
        return {"active": False, "job": None, "counts": {}}
    job = dict(row)
    return _build_status(job)


def _clamp_range(min_value: int, max_value: int) -> Tuple[int, int]:
    min_value = max(120, int(min_value))
    max_value = max(min_value, int(max_value))
    return min_value, max_value


def _make_image_bytes(width: int, height: int, seed: int) -> bytes:
    rng = random.Random(seed)
    base = (rng.randint(30, 225), rng.randint(30, 225), rng.randint(30, 225))
    img = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 6)):
        x1 = rng.randint(0, max(0, width - 1))
        y1 = rng.randint(0, max(0, height - 1))
        x2 = rng.randint(x1, width)
        y2 = rng.randint(y1, height)
        color = (rng.randint(20, 235), rng.randint(20, 235), rng.randint(20, 235))
        draw.rectangle([x1, y1, x2, y2], fill=color)
    buf = io.BytesIO()
    img.save(buf, format=DEFAULT_FORMAT, quality=72, method=4)
    return buf.getvalue()


def _write_stress_file(
    job_id: int,
    owner_user_id: int,
    index: int,
    min_width: int,
    max_width: int,
    min_height: int,
    max_height: int,
) -> bool:
    width = random.randint(min_width, max_width)
    height = random.randint(min_height, max_height)
    payload = _make_image_bytes(width, height, job_id * 100000 + index)
    upload_uuid = uuid.uuid4().hex
    tmp_path = config.UPLOAD_TMP / f"{upload_uuid}.part"
    try:
        storage.write_stream_to_tmp(io.BytesIO(payload), tmp_path)
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"stress_write_error:{exc}")
        return False
    mime = storage.detect_mime(tmp_path) or "image/webp"
    ext = config.ALLOWED_MIME.get(mime)
    if not ext:
        storage.move_to_quarantine(tmp_path, f"stress_mime_not_allowed:{mime}")
        return False

    title = f"压测-{index:04d}"
    try:
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO upload_requests (uuid, owner_user_id, title, description, tags_json, collection_override, stress_job_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_uuid,
                    owner_user_id,
                    title,
                    "",
                    "[]",
                    None,
                    job_id,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"stress_meta_error:{exc}")
        return False

    raw_path = config.RAW_DIR / f"{upload_uuid}{ext}"
    try:
        storage.atomic_move(tmp_path, raw_path)
    except Exception as exc:  # noqa: BLE001
        storage.move_to_quarantine(tmp_path, f"stress_move_error:{exc}")
        with db.transaction() as conn:
            conn.execute("DELETE FROM upload_requests WHERE uuid=?", (upload_uuid,))
        return False
    return True


def _run_job(job_id: int) -> None:
    job = _load_job(job_id)
    if not job:
        return
    total = int(job.get("total") or 0)
    min_width, max_width = _clamp_range(job.get("min_width") or DEFAULT_MIN_SIZE, job.get("max_width") or DEFAULT_MAX_SIZE)
    min_height, max_height = _clamp_range(job.get("min_height") or DEFAULT_MIN_SIZE, job.get("max_height") or DEFAULT_MAX_SIZE)
    owner_user_id = int(job.get("owner_user_id") or 0)
    generated = int(job.get("generated") or 0)
    failures = 0
    max_attempts = max(total * 2, total + 10)
    attempts = 0
    while generated < total and attempts < max_attempts:
        attempts += 1
        with _STATE_LOCK:
            stop_event = _STATE.get("stop_event")
        if stop_event and stop_event.is_set():
            _update_job(job_id, status=STATUS_STOPPED, generated=generated, message="手动停止")
            break
        if storage.upload_paused() or not storage.disk_has_space(config.STORAGE):
            _update_job(job_id, status=STATUS_FAILED, generated=generated, message="磁盘空间不足")
            break
        ok = _write_stress_file(job_id, owner_user_id, generated + 1, min_width, max_width, min_height, max_height)
        if ok:
            generated += 1
            if generated % 5 == 0 or generated == total:
                _update_job(job_id, generated=generated)
        else:
            failures += 1
            if failures >= 8:
                _update_job(job_id, status=STATUS_FAILED, generated=generated, message="生成失败过多")
                break
        time.sleep(0.01)
    else:
        if generated >= total:
            _update_job(job_id, status=STATUS_DONE, generated=generated, message="生成完成")
    with _STATE_LOCK:
        if _STATE.get("job_id") == job_id:
            _STATE["thread"] = None
            _STATE["job_id"] = None
            stop_event = _STATE.get("stop_event")
            if stop_event:
                stop_event.clear()


def start_job(
    owner_user_id: int,
    *,
    total: int = DEFAULT_TOTAL,
    min_size: int = DEFAULT_MIN_SIZE,
    max_size: int = DEFAULT_MAX_SIZE,
) -> Tuple[bool, str, Optional[dict]]:
    db.ensure_schema()
    if storage.upload_paused():
        return False, "上传已暂停：磁盘保护", None
    if not storage.disk_has_space(config.STORAGE):
        return False, "磁盘空间不足，已暂停上传", None
    active = _find_active_job()
    if active:
        return False, "已有进行中的压测任务", active
    total = max(1, int(total))
    min_size, max_size = _clamp_range(min_size, max_size)
    with db.transaction() as conn:
        cursor = conn.execute(
            """
            INSERT INTO stress_jobs (owner_user_id, status, total, generated, min_width, max_width, min_height, max_height, format, message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_user_id,
                STATUS_RUNNING,
                total,
                0,
                min_size,
                max_size,
                min_size,
                max_size,
                DEFAULT_FORMAT,
                "启动中",
                _utcnow(),
                _utcnow(),
            ),
        )
        job_id = int(cursor.lastrowid or 0)
    if not job_id:
        return False, "创建压测任务失败", None
    with _STATE_LOCK:
        stop_event = threading.Event()
        thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
        _STATE["thread"] = thread
        _STATE["stop_event"] = stop_event
        _STATE["job_id"] = job_id
        thread.start()
    job = _load_job(job_id)
    return True, "压测任务已启动", job


def stop_job(job_id: Optional[int] = None) -> Tuple[bool, str, Optional[dict]]:
    db.ensure_schema()
    active = _find_active_job()
    if not active:
        return False, "当前没有进行中的压测任务", None
    if job_id and int(active["id"]) != int(job_id):
        return False, "压测任务不匹配", active
    _update_job(int(active["id"]), status=STATUS_STOPPING, message="停止中")
    with _STATE_LOCK:
        stop_event = _STATE.get("stop_event")
        if stop_event:
            stop_event.set()
    return True, "已提交停止请求", _load_job(int(active["id"]))


def cleanup_job(job_id: Optional[int] = None) -> Tuple[bool, str, Optional[dict]]:
    db.ensure_schema()
    job = _load_job(job_id) if job_id else None
    if not job:
        job = _find_active_job()
    if not job:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT id, owner_user_id, status, total, generated FROM stress_jobs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        job = dict(row) if row else None
    if not job:
        return False, "没有可清理的压测任务", None

    if job.get("status") in {STATUS_RUNNING, STATUS_STOPPING}:
        with _STATE_LOCK:
            stop_event = _STATE.get("stop_event")
            if stop_event:
                stop_event.set()
    job_id = int(job["id"])

    with db.transaction() as conn:
        pending = conn.execute(
            "SELECT uuid FROM upload_requests WHERE stress_job_id=?",
            (job_id,),
        ).fetchall()
        conn.execute("DELETE FROM upload_requests WHERE stress_job_id=?", (job_id,))
    for row in pending:
        uuid_value = str(row["uuid"])
        for ext in set(config.ALLOWED_MIME.values()):
            raw_path = config.RAW_DIR / f"{uuid_value}{ext}"
            if raw_path.exists():
                try:
                    storage.move_to_trash(raw_path, raw_path.name)
                except Exception:
                    pass

    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT uuid, stored_path, thumb_path, ext, deleted_at FROM images WHERE stress_job_id=?",
            (job_id,),
        ).fetchall()
        for row in rows:
            if row["deleted_at"]:
                continue
            uuid_value = row["uuid"]
            raw_path = config.STORAGE / row["stored_path"]
            trash_name = f"{uuid_value}{row['ext'] or ''}"
            trash_path = ""
            if raw_path.exists():
                try:
                    trash_path = str(storage.move_to_trash(raw_path, trash_name).relative_to(config.STORAGE))
                except Exception:
                    trash_path = ""
            thumb_path = row["thumb_path"]
            if thumb_path:
                try:
                    (config.STORAGE / thumb_path).unlink(missing_ok=True)
                except Exception:
                    pass
            now = datetime.datetime.utcnow()
            purge_after = now + datetime.timedelta(days=config.TRASH_RETENTION_DAYS)
            conn.execute(
                """
                UPDATE images
                SET deleted_at=?, trash_path=?, purge_after=?, updated_at=CURRENT_TIMESTAMP
                WHERE uuid=?
                """,
                (now.isoformat(), trash_path, purge_after.isoformat(), uuid_value),
            )
        conn.execute(
            "UPDATE stress_jobs SET status=?, message=?, updated_at=? WHERE id=?",
            (STATUS_CLEANED, "已清理", _utcnow(), job_id),
        )
    try:
        config.FORCE_REBUILD_FLAG.write_text("stress_cleanup", encoding="utf-8")
    except Exception:
        pass
    return True, "压测数据已清理", _load_job(job_id)
