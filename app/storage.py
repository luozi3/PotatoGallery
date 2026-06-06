import errno
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Iterable, Optional, Tuple
from uuid import uuid4

try:
    import magic  # type: ignore
except Exception:  # pragma: no cover - 依赖缺失时的兜底
    magic = None

from . import config


def fsync_path(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError:
        # Directory fsync is not supported on every platform, especially Windows.
        return
    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        os.close(fd)


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
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


def check_storage_devices(
    base: Optional[Path] = None,
    paths: Optional[Iterable[Path]] = None,
    logger: Optional[logging.Logger] = None,
) -> list[str]:
    """
    启动时检查 storage 子目录是否在同一分区，避免 os.replace 跨分区失败。
    """
    base_path = (base or config.STORAGE).resolve(strict=False)
    try:
        base_dev = base_path.stat().st_dev
    except Exception as exc:
        msg = f"[storage] 无法读取基础目录设备号: {base_path} ({exc})"
        if logger:
            logger.warning(msg)
        else:
            print(msg)
        return [msg]

    default_paths = [
        config.UPLOAD_TMP,
        config.RAW_DIR,
        config.QUARANTINE_DIR,
        config.THUMB_DIR,
        config.TRASH_DIR,
        config.WWW_DIR,
        config.WWW_STAGING,
        config.STATUS_DATA_DIR,
        config.LOG_DIR,
    ]
    check_paths = list(paths) if paths is not None else default_paths
    messages: list[str] = []
    for path in check_paths:
        resolved = path.resolve(strict=False)
        try:
            dev = resolved.stat().st_dev
        except Exception as exc:
            messages.append(f"[storage] 无法读取设备号: {resolved} ({exc})")
            continue
        if dev != base_dev:
            messages.append(
                f"[storage] 跨分区路径: {resolved} (dev {dev}) != {base_path} (dev {base_dev})"
            )

    for msg in messages:
        if logger:
            logger.warning(msg)
        else:
            print(msg)
    return messages


def _replace_file_cross_device(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.tmp_{uuid4().hex}"
    try:
        shutil.copy2(src, tmp)
        _fsync_file(tmp)
        os.replace(tmp, dest)
        fsync_path(dest.parent)
        src.unlink(missing_ok=True)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _replace_dir_cross_device(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.tmp_{uuid4().hex}"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(src, tmp, copy_function=shutil.copy2)
        fsync_path(tmp)
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            else:
                dest.unlink(missing_ok=True)
        os.replace(tmp, dest)
        fsync_path(dest.parent)
        shutil.rmtree(src, ignore_errors=True)
    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        raise


def replace_path(src: Path, dest: Path) -> None:
    """
    跨分区时退化为复制+替换，保持写入路径可用。
    """
    try:
        os.replace(src, dest)
        fsync_path(dest.parent)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise

    if src.is_dir():
        _replace_dir_cross_device(src, dest)
    else:
        _replace_file_cross_device(src, dest)


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
            if config.ENFORCE_UPLOAD_SIZE and written > config.MAX_UPLOAD_BYTES:
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
    replace_path(src, dest)


def move_to_quarantine(src: Path, reason: str) -> Path:
    QUARANTINE_DIR = config.QUARANTINE_DIR
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    target = QUARANTINE_DIR / src.name
    try:
        replace_path(src, target)
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
