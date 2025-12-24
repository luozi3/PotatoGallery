#!/usr/bin/env bash
set -euo pipefail

GALLERY_ROOT=${GALLERY_ROOT:-/opt/PotatoGallery}
if [ -f /etc/gallery/gallery_root.env ]; then
  # shellcheck disable=SC1090
  . /etc/gallery/gallery_root.env
  GALLERY_ROOT=${GALLERY_ROOT:-/opt/PotatoGallery}
fi

export GALLERY_ROOT
export PYTHONPATH="$GALLERY_ROOT"
PYTHON="$GALLERY_ROOT/venv/bin/python"

if [ -x "$PYTHON" ]; then
  "$PYTHON" "$GALLERY_ROOT/bin/maintenance.py" --scan --clean --vacuum --backup
else
  python3 "$GALLERY_ROOT/bin/maintenance.py" --scan --clean --vacuum --backup
fi
