#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bin/deploy_auto.sh [--apply] [--output DIR] [options]

Options:
  --apply             Apply configs to /etc and start services (requires root).
  --output DIR        Render configs to DIR (default: ./deploy/output).
  --enable-cron       Install cron jobs for maintenance/request stats.
  --skip-apt          Skip apt-get install.
  --skip-nginx        Skip nginx install/reload.
  --skip-systemd      Skip systemd install/enable/start.
  --skip-venv         Skip virtualenv + pip install.
  --skip-db           Skip database init.
  --skip-refresh      Skip refresh_static.sh.
  -h, --help          Show this help.

Environment:
  GALLERY_ROOT              Project root (default: /opt/PotatoGallery)
  GALLERY_SERVER_NAME       Nginx server_name (default: example.com)
  GALLERY_UPLOAD_PORT       Upload service port (default: 5000)
  GALLERY_CLIENT_MAX_BODY_SIZE  Nginx client_max_body_size (default: 40m)
  GALLERY_USER              Service user (default: gallery)
  GALLERY_GROUP             Service group (default: www-data)
  GALLERY_CRON_DAILY         Maintenance cron schedule (default: @daily)
  GALLERY_CRON_STATS         Request stats cron schedule (default: */5 * * * *)
  GALLERY_CRON_DAILY_USER    Maintenance cron user (default: GALLERY_USER)
  GALLERY_CRON_STATS_USER    Request stats cron user (default: root)
USAGE
}

ROOT=${GALLERY_ROOT:-/opt/PotatoGallery}
SERVER_NAME=${GALLERY_SERVER_NAME:-example.com}
UPLOAD_PORT=${GALLERY_UPLOAD_PORT:-5000}
CLIENT_MAX_BODY_SIZE=${GALLERY_CLIENT_MAX_BODY_SIZE:-40m}
RUN_AS=${GALLERY_USER:-gallery}
RUN_GROUP=${GALLERY_GROUP:-www-data}
CRON_DAILY=${GALLERY_CRON_DAILY:-@daily}
CRON_STATS=${GALLERY_CRON_STATS:-*/5 * * * *}
CRON_DAILY_USER=${GALLERY_CRON_DAILY_USER:-${RUN_AS}}
CRON_STATS_USER=${GALLERY_CRON_STATS_USER:-root}

APPLY=0
OUTPUT_DIR=""
ENABLE_CRON=0
SKIP_APT=0
SKIP_NGINX=0
SKIP_SYSTEMD=0
SKIP_VENV=0
SKIP_DB=0
SKIP_REFRESH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --output)
      OUTPUT_DIR=${2:-""}
      shift 2
      ;;
    --output=*)
      OUTPUT_DIR=${1#*=}
      shift
      ;;
    --enable-cron)
      ENABLE_CRON=1
      shift
      ;;
    --skip-apt)
      SKIP_APT=1
      shift
      ;;
    --skip-nginx)
      SKIP_NGINX=1
      shift
      ;;
    --skip-systemd)
      SKIP_SYSTEMD=1
      shift
      ;;
    --skip-venv)
      SKIP_VENV=1
      shift
      ;;
    --skip-db)
      SKIP_DB=1
      shift
      ;;
    --skip-refresh)
      SKIP_REFRESH=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
 done

if [ -z "${OUTPUT_DIR}" ]; then
  OUTPUT_DIR="${ROOT}/deploy/output"
fi

log() {
  printf "[deploy] %s\n" "$*"
}

escape_sed() {
  printf '%s' "$1" | sed -e 's/[&|]/\\&/g'
}

render_template() {
  local src=$1
  local dst=$2
  local root_esc
  local server_esc
  local port_esc
  local size_esc
  local user_esc
  local group_esc
  local cron_daily_esc
  local cron_stats_esc
  local cron_daily_user_esc
  local cron_stats_user_esc

  root_esc=$(escape_sed "${ROOT}")
  server_esc=$(escape_sed "${SERVER_NAME}")
  port_esc=$(escape_sed "${UPLOAD_PORT}")
  size_esc=$(escape_sed "${CLIENT_MAX_BODY_SIZE}")
  user_esc=$(escape_sed "${RUN_AS}")
  group_esc=$(escape_sed "${RUN_GROUP}")
  cron_daily_esc=$(escape_sed "${CRON_DAILY}")
  cron_stats_esc=$(escape_sed "${CRON_STATS}")
  cron_daily_user_esc=$(escape_sed "${CRON_DAILY_USER}")
  cron_stats_user_esc=$(escape_sed "${CRON_STATS_USER}")

  sed \
    -e "s|__GALLERY_ROOT__|${root_esc}|g" \
    -e "s|__SERVER_NAME__|${server_esc}|g" \
    -e "s|__UPLOAD_PORT__|${port_esc}|g" \
    -e "s|__CLIENT_MAX_BODY_SIZE__|${size_esc}|g" \
    -e "s|__GALLERY_USER__|${user_esc}|g" \
    -e "s|__GALLERY_GROUP__|${group_esc}|g" \
    -e "s|__CRON_DAILY__|${cron_daily_esc}|g" \
    -e "s|__CRON_STATS__|${cron_stats_esc}|g" \
    -e "s|__CRON_DAILY_USER__|${cron_daily_user_esc}|g" \
    -e "s|__CRON_STATS_USER__|${cron_stats_user_esc}|g" \
    "${src}" > "${dst}"
}

ensure_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "--apply requires root privileges." >&2
    exit 1
  fi
}

render_configs() {
  local tpl_root="${ROOT}/deploy"
  local nginx_tpl="${tpl_root}/nginx/potato_gallery.conf"
  local env_tpl="${tpl_root}/env/gallery_root.env"
  local upload_tpl="${tpl_root}/systemd/gallery-upload.service"
  local worker_tpl="${tpl_root}/systemd/gallery-worker.service"
  local cron_daily_tpl="${tpl_root}/cron/potato_gallery_maintenance"
  local cron_stats_tpl="${tpl_root}/cron/potato_gallery_requests"

  for f in "${nginx_tpl}" "${env_tpl}" "${upload_tpl}" "${worker_tpl}" "${cron_daily_tpl}" "${cron_stats_tpl}"; do
    if [ ! -f "${f}" ]; then
      echo "Template missing: ${f}" >&2
      exit 1
    fi
  done

  mkdir -p "${OUTPUT_DIR}"
  render_template "${nginx_tpl}" "${OUTPUT_DIR}/potato_gallery.conf"
  render_template "${env_tpl}" "${OUTPUT_DIR}/gallery_root.env"
  render_template "${upload_tpl}" "${OUTPUT_DIR}/gallery-upload.service"
  render_template "${worker_tpl}" "${OUTPUT_DIR}/gallery-worker.service"
  mkdir -p "${OUTPUT_DIR}/cron"
  render_template "${cron_daily_tpl}" "${OUTPUT_DIR}/cron/potato_gallery_maintenance"
  render_template "${cron_stats_tpl}" "${OUTPUT_DIR}/cron/potato_gallery_requests"

  log "Rendered configs to ${OUTPUT_DIR}"
}

install_packages() {
  if [ "${SKIP_APT}" -eq 1 ]; then
    return
  fi
  local packages=(python3 python3-venv python3-pip sqlite3 libmagic1 rsync git)
  if [ "${SKIP_NGINX}" -eq 0 ]; then
    packages+=(nginx)
  fi
  log "Installing packages: ${packages[*]}"
  apt-get update
  apt-get install -y "${packages[@]}"
}

ensure_user_group() {
  if ! getent group "${RUN_GROUP}" >/dev/null 2>&1; then
    groupadd --system "${RUN_GROUP}"
  fi
  if ! id "${RUN_AS}" >/dev/null 2>&1; then
    useradd --system --gid "${RUN_GROUP}" --home "${ROOT}" --shell /usr/sbin/nologin "${RUN_AS}"
  fi
}

setup_venv() {
  if [ "${SKIP_VENV}" -eq 1 ]; then
    return
  fi
  if [ ! -x "${ROOT}/venv/bin/python" ]; then
    python3 -m venv "${ROOT}/venv"
  fi
  "${ROOT}/venv/bin/pip" install -r "${ROOT}/requirements.txt"
}

ensure_default_configs() {
  local upload_cfg="${ROOT}/config/upload.json"
  local upload_example="${ROOT}/config/upload.json.example"
  if [ ! -f "${upload_cfg}" ] && [ -f "${upload_example}" ]; then
    cp "${upload_example}" "${upload_cfg}"
  fi
}

init_db() {
  if [ "${SKIP_DB}" -eq 1 ]; then
    return
  fi
  "${ROOT}/venv/bin/python" -c "from app import storage; storage.ensure_dirs()"
  "${ROOT}/venv/bin/python" "${ROOT}/bin/init_db.py"
}

fix_permissions() {
  if [ -d "${ROOT}/storage" ]; then
    chown -R "${RUN_AS}:${RUN_GROUP}" "${ROOT}/storage" || true
  fi
  if [ -d "${ROOT}/db" ]; then
    chown -R "${RUN_AS}:${RUN_GROUP}" "${ROOT}/db" || true
  fi
}

apply_configs() {
  ensure_root
  render_configs

  log "Installing config files"
  mkdir -p /etc/gallery
  install -m 0644 "${OUTPUT_DIR}/gallery_root.env" /etc/gallery/gallery_root.env

  if [ "${SKIP_SYSTEMD}" -eq 0 ]; then
    install -m 0644 "${OUTPUT_DIR}/gallery-upload.service" /etc/systemd/system/gallery-upload.service
    install -m 0644 "${OUTPUT_DIR}/gallery-worker.service" /etc/systemd/system/gallery-worker.service
    systemctl daemon-reload
    systemctl enable gallery-upload gallery-worker
  fi

  if [ "${SKIP_NGINX}" -eq 0 ]; then
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    install -m 0644 "${OUTPUT_DIR}/potato_gallery.conf" /etc/nginx/sites-available/potato_gallery.conf
    ln -sfn /etc/nginx/sites-available/potato_gallery.conf /etc/nginx/sites-enabled/potato_gallery.conf
  fi

  if [ "${ENABLE_CRON}" -eq 1 ]; then
    install -m 0644 "${OUTPUT_DIR}/cron/potato_gallery_maintenance" /etc/cron.d/potato_gallery_maintenance
    install -m 0644 "${OUTPUT_DIR}/cron/potato_gallery_requests" /etc/cron.d/potato_gallery_requests
  fi
}

start_services() {
  if [ "${SKIP_SYSTEMD}" -eq 0 ]; then
    systemctl restart gallery-upload gallery-worker
  fi
  if [ "${SKIP_NGINX}" -eq 0 ]; then
    nginx -t
    systemctl reload nginx
  fi
}

main() {
  if [ ! -d "${ROOT}" ]; then
    echo "Project root not found: ${ROOT}" >&2
    exit 1
  fi

  if [ "${APPLY}" -eq 1 ]; then
    ensure_root
    install_packages
    ensure_user_group
    setup_venv
    ensure_default_configs
    init_db
    fix_permissions
    apply_configs
    if [ "${SKIP_REFRESH}" -eq 0 ]; then
      "${ROOT}/bin/refresh_static.sh"
    fi
    start_services
    log "Auto deploy complete."
  else
    render_configs
    log "Rendered only. Use --apply to install and start services."
  fi
}

main
