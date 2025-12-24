#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=/opt/PotatoGallery
PYTHON="/opt/PotatoGallery/venv/bin/python"

if [ -x "$PYTHON" ]; then
  "$PYTHON" /opt/PotatoGallery/bin/maintenance.py --scan --clean --vacuum --backup
else
  python3 /opt/PotatoGallery/bin/maintenance.py --scan --clean --vacuum --backup
fi
