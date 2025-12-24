import hashlib
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Tuple

try:
    import magic  # type: ignore
except Exception:  # pragma: no cover - 依赖缺失时的兜底
    magic = None

from . import config


def fsync_path(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ensure_dirs() -> None:
    for p in [
        config.UPLOAD_TMP,
        config.RAW_DIR,
        config.QUARANTINE_DIR,
        config.THUMB_DIR,
        config.TRASH_DIR,
        config.WWW_DIR,
        config.WWW_STAGING,
        config.STATUS_DATA_DIR,
        config.LOG_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def disk_has_space(target: Path) -> bool:
    usage = shutil.disk_usage(target)
    return usage.free >= config.DISK_LOW_WATERMARK_BYTES


def upload_paused() -> bool:
    return config.UPLOAD_PAUSE_FLAG.exists()


def set_upload_paused(paused: bool, reason: str = "") -> None:
    flag = config.UPLOAD_PAUSE_FLAG
    if paused:
        flag.write_text(reason or "paused", encoding="utf-8")
    else:
        flag.unlink(missing_ok=True)


def write_stream_to_tmp(stream: BinaryIO, tmp_path: Path) -> Tuple[int, str]:
    sha256 = hashlib.sha256()
    written = 0
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        while True:
            chunk = stream.read(config.CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > config.MAX_UPLOAD_BYTES:
                raise ValueError("文件过大")
            f.write(chunk)
            sha256.update(chunk)
        f.flush()
        os.fsync(f.fileno())
    return written, sha256.hexdigest()


def detect_mime(path: Path) -> str:
    if magic:
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(str(path))
        except Exception:
            return ""
    return ""


def atomic_move(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)
    fsync_path(dest.parent)


def move_to_quarantine(src: Path, reason: str) -> Path:
    QUARANTINE_DIR = config.QUARANTINE_DIR
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    target = QUARANTINE_DIR / src.name
    try:
        os.replace(src, target)
        fsync_path(target.parent)
    except Exception:
        # 如果连隔离都失败，尽力删除临时文件
        if target.exists():
            target.unlink(missing_ok=True)
    print(f"[quarantine] {src.name}: {reason}")
    return target


def move_to_trash(src: Path, dest_name: str) -> Path:
    """
    将文件原子移动到 trash 目录，保留文件名可追溯。
    """
    target = config.TRASH_DIR / dest_name
    atomic_move(src, target)
    return target
