#!/usr/bin/env python3
"""磁盘水位巡检：低于阈值自动暂停上传，恢复后解除。"""
import shutil
from datetime import datetime

from app import config, db, storage


def main() -> int:
    usage = shutil.disk_usage(config.STORAGE)
    free = usage.free
    paused = storage.upload_paused()
    resume_threshold = config.DISK_LOW_WATERMARK_BYTES + config.DISK_RESUME_DELTA_BYTES

    if free < config.DISK_LOW_WATERMARK_BYTES:
        storage.set_upload_paused(
            True,
            f"paused_at={datetime.utcnow().isoformat()} free={free}",
        )
        try:
            db.insert_audit("disk_guard_pause", None, f"free={free}")
        except Exception:
            pass
        print(f"[disk_guard] paused upload: free={free}")
        return 1

    if paused and free >= resume_threshold:
        storage.set_upload_paused(False)
        try:
            db.insert_audit("disk_guard_resume", None, f"free={free}")
        except Exception:
            pass
        print(f"[disk_guard] resume upload: free={free}")
    else:
        print(f"[disk_guard] ok: free={free}, paused={paused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
