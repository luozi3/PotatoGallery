#!/usr/bin/env bash
set -euo pipefail

GALLERY_ROOT=${GALLERY_ROOT:-/opt/PotatoGallery}
if [ -f /etc/gallery/gallery_root.env ]; then
  # shellcheck disable=SC1090
  . /etc/gallery/gallery_root.env
  GALLERY_ROOT=${GALLERY_ROOT:-/opt/PotatoGallery}
fi

cd "$GALLERY_ROOT"
export GALLERY_ROOT
export PYTHONPATH="$GALLERY_ROOT"
PYTHON="$GALLERY_ROOT/venv/bin/python"
RUN_AS="gallery"

echo "[refresh] ensure dirs, rebuild, publish, write status..."
if id "$RUN_AS" >/dev/null 2>&1 && command -v runuser >/dev/null 2>&1; then
  runuser -u "$RUN_AS" -- "$PYTHON" - <<'PY'
from app import worker, storage
storage.ensure_dirs()
staging = worker.rebuild_and_publish()
worker.write_status_snapshot()
print(f"rebuild published from {staging}")
print("status files:", (worker.config.WWW_DIR / "status.html"), (worker.config.WWW_DIR / "status" / "index.html"), (worker.config.WWW_DIR / "static" / "status.json"))
PY
else
  "$PYTHON" - <<'PY'
from app import worker, storage
storage.ensure_dirs()
staging = worker.rebuild_and_publish()
worker.write_status_snapshot()
print(f"rebuild published from {staging}")
print("status files:", (worker.config.WWW_DIR / "status.html"), (worker.config.WWW_DIR / "status" / "index.html"), (worker.config.WWW_DIR / "static" / "status.json"))
PY
fi

if command -v chown >/dev/null 2>&1; then
  chown -R gallery:www-data "$GALLERY_ROOT/storage/www" || true
fi

if command -v systemctl >/dev/null 2>&1; then
  echo "[refresh] restarting gallery-worker..."
  systemctl restart gallery-worker || true
fi

echo "[refresh] done."
