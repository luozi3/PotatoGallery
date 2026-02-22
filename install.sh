#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=${GALLERY_ROOT:-"${SCRIPT_DIR}"}
export GALLERY_ROOT="${ROOT}"

HAS_APPLY=0
HAS_CRON=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --apply)
      HAS_APPLY=1
      ;;
    --enable-cron)
      HAS_CRON=1
      ;;
  esac
  ARGS+=("$arg")
 done

if [ "${HAS_APPLY}" -eq 0 ]; then
  ARGS=("--apply" "${ARGS[@]}")
fi
if [ "${HAS_CRON}" -eq 0 ]; then
  ARGS=("--enable-cron" "${ARGS[@]}")
fi

if [ ! -x "${ROOT}/bin/deploy_auto.sh" ]; then
  echo "deploy script not found: ${ROOT}/bin/deploy_auto.sh" >&2
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    exec sudo -E env GALLERY_ROOT="${GALLERY_ROOT}" "${ROOT}/bin/deploy_auto.sh" "${ARGS[@]}"
  fi
  echo "Please run as root or install sudo." >&2
  exit 1
fi

exec "${ROOT}/bin/deploy_auto.sh" "${ARGS[@]}"
