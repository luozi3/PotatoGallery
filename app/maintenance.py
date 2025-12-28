import datetime
import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from . import config
from . import db
from . import image_utils
from . import static_site
from . import worker


def _now_ts() -> float:
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


def _age_hours(path: Path) -> float:
    return (_now_ts() - path.stat().st_mtime) / 3600.0


def cleanup_staging(max_age_hours: int = config.CLEANUP_STAGING_MAX_AGE_HOURS) -> List[str]:
    removed: List[str] = []
    if not config.WWW_STAGING.exists():
        return removed
    for path in config.WWW_STAGING.iterdir():
        if not path.is_dir():
            continue
        try:
            if _age_hours(path) >= max_age_hours:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(path.name)
        except Exception:
            continue
    return removed


def cleanup_upload_tmp(max_age_hours: int = config.CLEANUP_TMP_MAX_AGE_HOURS) -> List[str]:
    removed: List[str] = []
    if not config.UPLOAD_TMP.exists():
        return removed
    for path in config.UPLOAD_TMP.iterdir():
        if not path.is_file():
            continue
        try:
            if _age_hours(path) >= max_age_hours:
                path.unlink(missing_ok=True)
                removed.append(path.name)
        except Exception:
            continue
    return removed


def cleanup_orphan_thumbs() -> List[str]:
    removed: List[str] = []
    if not config.THUMB_DIR.exists():
        return removed
    with db.connect() as conn:
        rows = conn.execute("SELECT thumb_path FROM images WHERE thumb_path IS NOT NULL").fetchall()
    keep = {Path(row["thumb_path"]).name for row in rows if row["thumb_path"]}
    for path in config.THUMB_DIR.iterdir():
        if not path.is_file():
            continue
        if path.name not in keep:
            try:
                path.unlink(missing_ok=True)
                removed.append(path.name)
            except Exception:
                continue
    return removed


def cleanup_trash() -> List[str]:
    removed: List[str] = []
    now = datetime.datetime.utcnow()
    db.ensure_schema()
    with db.transaction() as conn:
        rows = conn.execute(
            """
            SELECT uuid, trash_path, purge_after
            FROM images
            WHERE deleted_at IS NOT NULL AND purge_after IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            purge_after = row["purge_after"]
            if not purge_after:
                continue
            try:
                ts = datetime.datetime.fromisoformat(purge_after)
            except Exception:
                continue
            if ts > now:
                continue
            trash_path = row["trash_path"]
            if trash_path:
                try:
                    (config.STORAGE / trash_path).unlink(missing_ok=True)
                except Exception:
                    pass
            conn.execute(
                "UPDATE images SET trash_path=NULL, purge_after=NULL WHERE uuid=?",
                (row["uuid"],),
            )
            removed.append(row["uuid"])
    return removed


def scan_consistency() -> Dict[str, List[str]]:
    raw_files = [p for p in config.RAW_DIR.iterdir() if p.is_file()] if config.RAW_DIR.exists() else []
    raw_map = {}
    invalid_raw: List[str] = []
    for path in raw_files:
        uuid = worker.parse_uuid_from_name(path)
        if not uuid:
            invalid_raw.append(path.name)
            continue
        raw_map[uuid] = path

    with db.connect() as conn:
        rows = conn.execute("SELECT uuid, stored_path, thumb_path FROM images").fetchall()
    db_map = {row["uuid"]: row for row in rows}

    orphan_raw: List[str] = []
    for uuid, path in raw_map.items():
        if uuid not in db_map:
            orphan_raw.append(path.name)
            try:
                db.insert_audit("orphan_raw", uuid, path.name)
            except Exception:
                pass

    missing_raw: List[str] = []
    for uuid, row in db_map.items():
        raw_path = config.STORAGE / row["stored_path"]
        if not raw_path.exists():
            missing_raw.append(uuid)
            try:
                db.insert_audit("missing_raw", uuid, row["stored_path"])
            except Exception:
                pass

    with db.connect() as conn:
        thumb_rows = conn.execute("SELECT thumb_path FROM images WHERE thumb_path IS NOT NULL").fetchall()
    keep_thumbs = {Path(row["thumb_path"]).name for row in thumb_rows if row["thumb_path"]}
    orphan_thumbs: List[str] = []
    if config.THUMB_DIR.exists():
        for path in config.THUMB_DIR.iterdir():
            if not path.is_file():
                continue
            if path.name not in keep_thumbs:
                orphan_thumbs.append(path.name)
                try:
                    db.insert_audit("orphan_thumb", path.name, "")
                except Exception:
                    pass

    return {
        "orphan_raw": orphan_raw,
        "missing_raw": missing_raw,
        "invalid_raw": invalid_raw,
        "orphan_thumbs": orphan_thumbs,
    }


def vacuum_db() -> None:
    with db.connect() as conn:
        conn.execute("VACUUM")


def backup_db(target_dir: Path = config.CLEANUP_BACKUP_DIR) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dst = target_dir / f"gallery_{ts}.db"
    shutil.copy2(db.DB_PATH, dst)
    try:
        os.chmod(dst, 0o640)
    except PermissionError:
        pass
    return dst


def run_maintenance() -> Dict[str, List[str]]:
    report = scan_consistency()
    report["removed_staging"] = cleanup_staging()
    report["removed_tmp"] = cleanup_upload_tmp()
    report["removed_thumb"] = cleanup_orphan_thumbs()
    report["removed_trash"] = cleanup_trash()
    try:
        static_site.ensure_www_readable()
        report["permissions_checked"] = ["ok"]
    except Exception:
        report["permissions_checked"] = ["failed"]
    return report


def regenerate_thumbnails(publish: bool = True) -> Dict[str, object]:
    """
    重新从原图生成缩略图，替换旧 JPG/WebP。
    """
    db.ensure_schema()
    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    updated = 0
    missing_raw: List[str] = []
    failed: List[str] = []
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT uuid, stored_path, thumb_path, deleted_at
            FROM images
            """
        ).fetchall()

    for row in rows:
        if row["deleted_at"]:
            continue
        uuid = row["uuid"]
        stored_path = row["stored_path"]
        raw_path = config.STORAGE / stored_path
        if not raw_path.exists():
            missing_raw.append(uuid)
            continue
        old_thumb_path = row["thumb_path"] or ""
        old_name = Path(old_thumb_path).name if old_thumb_path else ""
        if old_name:
            stem = Path(old_name).stem
            new_name = f"{stem}{config.THUMB_EXT}"
        else:
            new_name = worker.next_thumb_filename()
        new_path = config.THUMB_DIR / new_name
        try:
            thumb_width, thumb_height = image_utils.make_thumbnail(raw_path, new_path)
            color = image_utils.dominant_color(new_path)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{uuid}:{exc}")
            continue
        with db.transaction() as conn:
            conn.execute(
                """
                UPDATE images
                SET thumb_path=?, thumb_width=?, thumb_height=?, dominant_color=?, updated_at=CURRENT_TIMESTAMP
                WHERE uuid=?
                """,
                (f"thumb/{new_name}", thumb_width, thumb_height, color, uuid),
            )
        if old_name and old_name != new_name:
            old_file = config.THUMB_DIR / old_name
            try:
                old_file.unlink(missing_ok=True)
            except Exception:
                pass
        updated += 1

    if publish:
        worker.rebuild_and_publish()
        worker.write_status_snapshot()

    return {"updated": updated, "missing_raw": missing_raw, "failed": failed}
