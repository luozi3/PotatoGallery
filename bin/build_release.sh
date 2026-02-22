#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
OUT_DIR=${OUT_DIR:-"${ROOT}/dist"}
IGNORE_FILE="${ROOT}/deploy/.releaseignore"

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync not found; please install rsync." >&2
  exit 1
fi

if [ ! -f "${IGNORE_FILE}" ]; then
  echo "release ignore file not found: ${IGNORE_FILE}" >&2
  exit 1
fi

VERSION="dev"
if [ -f "${ROOT}/VERSION" ]; then
  VERSION=$(cat "${ROOT}/VERSION" | tr -d '[:space:]')
fi

TS=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="PotatoGallery_${VERSION}_${TS}"
STAGING=$(mktemp -d)

mkdir -p "${OUT_DIR}"

rsync -a --delete --exclude-from="${IGNORE_FILE}" "${ROOT}/" "${STAGING}/${PACKAGE_NAME}/"

# Ensure runtime directories exist in the package
mkdir -p "${STAGING}/${PACKAGE_NAME}/storage"/{.upload_tmp,raw,thumb,www,www_staging,quarantine,status_data,logs,backups,trash,config}

tar -czf "${OUT_DIR}/${PACKAGE_NAME}.tar.gz" -C "${STAGING}" "${PACKAGE_NAME}"
rm -rf "${STAGING}"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "${OUT_DIR}" && sha256sum "${PACKAGE_NAME}.tar.gz" > "${PACKAGE_NAME}.sha256")
  echo "Checksum created: ${OUT_DIR}/${PACKAGE_NAME}.sha256"
fi

echo "Release package created: ${OUT_DIR}/${PACKAGE_NAME}.tar.gz"
