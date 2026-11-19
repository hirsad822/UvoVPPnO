#!/usr/bin/env bash
# =============================================================================
# PulseGrid — Smart Traffic & Configuration Manager — One-Line Installer
# =============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/hirsad822/UvoVPPnO/main/install.sh | sudo bash
#   sudo bash install.sh [--update|--status|--uninstall|--purge|--help]
#
# Subcommands:
#   (default)   Install or reinstall (idempotent — safe to re-run)
#   --update    Update code to latest, keep data & token
#   --status    Show install + health status
#   --uninstall Remove service & files (keeps data unless --purge)
#   --purge     Remove everything including data (with --uninstall)
#   --help      Show help
# =============================================================================
set -euo pipefail

APP_NAME="pulsegrid"
APP_DIR="/opt/pulsegrid"
DATA_DIR="/var/lib/pulsegrid"
CONFIG_DIR="/etc/pulsegrid"
SERVICE_FILE="/etc/systemd/system/pulsegrid.service"
PORT="${PULSEGRID_PORT:-8080}"
REPO_URL="${PULSEGRID_REPO_URL:-https://github.com/hirsad822/UvoVPPnO.git}"
RAW_BASE="${PULSEGRID_RAW_BASE:-https://raw.githubusercontent.com/hirsad822/UvoVPPnO/main}"

# --- colours (only if tty) ---------------------------------------------------
if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; NC=''
fi
log()  { printf "%b[PulseGrid]%b %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%b[PulseGrid]%b %s\n" "$YELLOW" "$NC" "$*"; }
die()  { printf "%b[PulseGrid]%b ERROR: %s\n" "$RED" "$NC" "$*" >&2; exit 1; }

usage() {
  cat <<EOF
PulseGrid installer — Smart Traffic & Configuration Manager

Usage: sudo bash install.sh [OPTION]

Options:
  (none)        Install / reinstall (idempotent)
  --update      Update code, keep data & token
  --status      Show install + health status
  --uninstall   Remove service & files (data kept)
  --purge       With --uninstall: also remove data
  --help        Show this help

Env overrides:
  PULSEGRID_PORT, PULSEGRID_REPO_URL, PULSEGRID_RAW_BASE
EOF
}

# --- helpers -----------------------------------------------------------------
require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "Please run as root or with sudo:  sudo bash install.sh"
  fi
}

detect_os() {
  OS_ID="unknown"; OS_VER=""
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_ID="${ID:-unknown}"; OS_VER="${VERSION_ID:-}"
  fi
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ARCH_NORM="x86_64" ;;
    aarch64|arm64) ARCH_NORM="arm64" ;;
    *) ARCH_NORM="$ARCH" ;;
  esac
  log "Detected OS: $OS_ID $OS_VER | arch: $ARCH_NORM"
  case "$OS_ID" in
    debian|ubuntu|raspbian|linuxmint|pop) PKG="apt" ;;
    rhel|centos|fedora|rocky|almalinux) PKG="dnf" ;;
    alpine) PKG="apk" ;;
    arch|manjaro) PKG="pacman" ;;
    *) warn "Unknown OS '$OS_ID' — attempting generic install (python3 required)"; PKG="generic" ;;
  esac
}

install_deps() {
  log "Ensuring python3 is available..."
  if command -v python3 >/dev/null 2>&1; then
    log "python3 found: $(python3 --version 2>&1)"
    return 0
  fi
  case "$PKG" in
    apt) apt-get update -qq && apt-get install -y -qq python3 curl ca-certificates ;;
    dnf) dnf install -y python3 curl ca-certificates ;;
    apk) apk add --no-cache python3 curl ca-certificates ;;
    pacman) pacman -Sy --noconfirm python3 curl ca-certificates ;;
    *) die "python3 not found and package manager '$PKG' unsupported. Install python3 manually." ;;
  esac
  command -v python3 >/dev/null 2>&1 || die "python3 installation failed"
  log "python3 installed: $(python3 --version 2>&1)"
}

fetch_code() {
  log "Fetching PulseGrid code..."
  mkdir -p "$APP_DIR"
  # Prefer git clone; fall back to tarball download
  if command -v git >/dev/null 2>&1; then
    if [ -d "$APP_DIR/.git" ]; then
      git -C "$APP_DIR" pull --ff-only 2>/dev/null || warn "git pull failed — keeping existing code"
    else
      rm -rf "$APP_DIR.tmp" && git clone --depth 1 "$REPO_URL" "$APP_DIR.tmp" 2>/dev/null \
        && rm -rf "$APP_DIR" && mv "$APP_DIR.tmp" "$APP_DIR" \
        || warn "git clone failed — trying tarball fallback"
    fi
  fi
  if [ ! -f "$APP_DIR/pulsegrid/__main__.py" ]; then
    log "Downloading release tarball..."
    curl -fsSL "https://codeload.github.com/hirsad822/UvoVPPnO/tar.gz/refs/heads/main" -o /tmp/pulsegrid.tar.gz \
      || die "Failed to download PulseGrid. Check network connectivity."
    rm -rf "$APP_DIR.tmp" && mkdir -p "$APP_DIR.tmp"
    tar -xzf /tmp/pulsegrid.tar.gz -C "$APP_DIR.tmp" --strip-components=1
    rm -rf "$APP_DIR" && mv "$APP_DIR.tmp" "$APP_DIR"
    rm -f /tmp/pulsegrid.tar.gz
  fi
  [ -f "$APP_DIR/pulsegrid/__main__.py" ] || die "PulseGrid code not found after fetch"
  log "Code ready in $APP_DIR"
}

setup_dirs_and_token() {
  mkdir -p "$DATA_DIR" "$CONFIG_DIR"
  chmod 750 "$DATA_DIR" "$CONFIG_DIR" 2>/dev/null || true
  if [ ! -f "$CONFIG_DIR/token" ]; then
    TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    printf '%s\n' "$TOKEN" > "$CONFIG_DIR/token"
    chmod 600 "$CONFIG_DIR/token"
    TOKEN_CREATED=1
  else
    TOKEN_CREATED=0
  fi
  # Service user (best effort)
  if ! id pulsegrid >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin pulsegrid 2>/dev/null || true
  fi
  chown -R pulsegrid:pulsegrid "$DATA_DIR" "$CONFIG_DIR" 2>/dev/null || true
  chown -R root:root "$APP_DIR" 2>/dev/null || true
}

write_service() {
  log "Writing systemd service..."
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=PulseGrid — Smart Traffic & Configuration Manager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pulsegrid
Group=pulsegrid
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 -m pulsegrid --host 0.0.0.0 --port $PORT
Environment=PULSEGRID_CONFIG_DIR=$CONFIG_DIR
Environment=PULSEGRID_DATA_DIR=$DATA_DIR
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$DATA_DIR $CONFIG_DIR

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now "$APP_NAME" 2>/dev/null || systemctl enable "$APP_NAME"
}

firewall_hints() {
  log "Firewall hints (open port $PORT if needed):"
  if command -v ufw >/dev/null 2>&1; then
    ufw allow "$PORT/tcp" comment 'PulseGrid dashboard' 2>/dev/null || true
    log "  ufw: allowed $PORT/tcp"
  elif command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="$PORT/tcp" 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    log "  firewalld: allowed $PORT/tcp"
  else
    warn "  No ufw/firewalld found — open port $PORT in your cloud firewall / security group."
  fi
}

health_check() {
  log "Running health check..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
      log "Health check passed ✓"
      return 0
    fi
    sleep 1
  done
  warn "Health check did not respond yet — check: journalctl -u $APP_NAME -f"
  return 0
}

print_success() {
  TOKEN="$(cat "$CONFIG_DIR/token" 2>/dev/null || echo '<see /etc/pulsegrid/token>')"
  IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [ -z "$IP" ] && IP="<your-server-ip>"
  cat <<EOF

${GREEN}✅ PulseGrid installed successfully!${NC}

   Dashboard : http://$IP:$PORT
   Token     : $TOKEN
   Service   : systemctl status $APP_NAME
   Logs      : journalctl -u $APP_NAME -f
   Status    : sudo bash install.sh --status
   Update    : sudo bash install.sh --update
   Uninstall : sudo bash install.sh --uninstall

   Next: open the dashboard, paste the token, pick a preset, add a user.
   Docs: $APP_DIR/docs/TROUBLESHOOTING.md
EOF
  if [ "${TOKEN_CREATED:-0}" = "1" ]; then
    warn "Save the token above — it is also in $CONFIG_DIR/token (0600)."
  fi
}

do_install() {
  require_root; detect_os; install_deps; fetch_code
  setup_dirs_and_token; write_service; firewall_hints; health_check; print_success
}

do_update() {
  require_root; detect_os; install_deps; fetch_code
  setup_dirs_and_token; write_service; systemctl restart "$APP_NAME" || true
  health_check
  log "Update complete. Data & token preserved."
  print_success
}

do_status() {
  echo "=== PulseGrid status ==="
  if systemctl is-active --quiet "$APP_NAME" 2>/dev/null; then
    echo "Service: active"
    systemctl status "$APP_NAME" --no-pager -l | head -n 12 || true
  else
    echo "Service: NOT active (not installed or stopped)"
  fi
  echo "---"
  if [ -f "$APP_DIR/pulsegrid/__main__.py" ]; then echo "Code: present ($APP_DIR)"; else echo "Code: MISSING"; fi
  if [ -f "$CONFIG_DIR/token" ]; then echo "Token: present ($CONFIG_DIR/token)"; else echo "Token: MISSING"; fi
  if [ -f "$DATA_DIR/pulsegrid.db" ]; then echo "Data: present ($DATA_DIR/pulsegrid.db)"; else echo "Data: not created yet"; fi
  echo "---"
  curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null && echo " <- health OK" || echo "Health endpoint: not responding on port $PORT"
  echo "Logs: journalctl -u $APP_NAME -n 50"
}

do_uninstall() {
  require_root
  PURGE=0
  for a in "$@"; do [ "$a" = "--purge" ] && PURGE=1; done
  log "Uninstalling PulseGrid..."
  systemctl disable --now "$APP_NAME" 2>/dev/null || true
  rm -f "$SERVICE_FILE"
  systemctl daemon-reload 2>/dev/null || true
  rm -rf "$APP_DIR"
  if [ "$PURGE" = "1" ]; then
    rm -rf "$DATA_DIR" "$CONFIG_DIR"
    log "Purged data & config."
  else
    log "Data kept in $DATA_DIR and $CONFIG_DIR (use --purge to remove)."
  fi
  log "Uninstall complete."
}

# --- main --------------------------------------------------------------------
case "${1:-}" in
  --update) do_update ;;
  --status) do_status ;;
  --uninstall) shift; do_uninstall "$@" ;;
  --help|-h) usage ;;
  "") do_install ;;
  *) usage; exit 1 ;;
esac
