#!/usr/bin/env bash
# =============================================================================
# PulseGrid — Smart Traffic & Configuration Manager — One-Line Installer
# =============================================================================
# Usage:
#   Download install.sh, then pass PULSEGRID_PUBLIC_HOST, PULSEGRID_TLS_CERT and
#   PULSEGRID_TLS_KEY to sudo env; see README.md for certificate setup.
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
REF="${PULSEGRID_REF:-main}"

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
  PULSEGRID_PORT, PULSEGRID_REPO_URL, PULSEGRID_REF, PULSEGRID_PUBLIC_HOST, PULSEGRID_CORE_PORT, PULSEGRID_TLS_CERT, PULSEGRID_TLS_KEY
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
  if command -v python3 >/dev/null 2>&1 && command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1 && command -v openssl >/dev/null 2>&1; then
    log "python3 found: $(python3 --version 2>&1)"
    return 0
  fi
  case "$PKG" in
    apt) apt-get update -qq && apt-get install -y -qq python3 curl ca-certificates unzip openssl ;;
    dnf) dnf install -y python3 curl ca-certificates unzip openssl ;;
    apk) apk add --no-cache python3 curl ca-certificates unzip openssl ;;
    pacman) pacman -Sy --noconfirm python3 curl ca-certificates unzip openssl ;;
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
      git -C "$APP_DIR" fetch origin "$REF" && git -C "$APP_DIR" merge --ff-only FETCH_HEAD || die "git update failed; existing code preserved"
    else
      rm -rf "$APP_DIR.tmp" && git clone --depth 1 --branch "$REF" "$REPO_URL" "$APP_DIR.tmp" 2>/dev/null \
        && rm -rf "$APP_DIR" && mv "$APP_DIR.tmp" "$APP_DIR" \
        || warn "git clone failed — trying tarball fallback"
    fi
  fi
  if [ ! -d "$APP_DIR/.git" ]; then
    [ "$REPO_URL" = "https://github.com/hirsad822/UvoVPPnO.git" ] || die "A custom repository requires git"
    log "Downloading release tarball..."
    curl -fsSL "https://codeload.github.com/hirsad822/UvoVPPnO/tar.gz/refs/heads/$REF" -o /tmp/pulsegrid.tar.gz \
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
  # Service user
  if ! id pulsegrid >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin pulsegrid || die "Could not create service user"
  fi
  chown -R pulsegrid:pulsegrid "$DATA_DIR" "$CONFIG_DIR"
  chown -R root:root "$APP_DIR" 2>/dev/null || true
}


build_go_tlscheck() {
  if ! command -v go >/dev/null 2>&1; then
    log "Installing Go for the TLS validation helper..."
    case "$PKG" in
      apt) apt-get update -qq && apt-get install -y golang-go ;;
      dnf) dnf install -y golang ;;
      apk) apk add --no-cache go ;;
      pacman) pacman -Sy --noconfirm go ;;
      *) die "Install Go 1.19 or newer and retry" ;;
    esac
  fi
  mkdir -p "$APP_DIR/bin"
  (cd "$APP_DIR/next/go" && GOTOOLCHAIN=local go build -o "$APP_DIR/bin/tlscheck.tmp" ./cmd/tlscheck) || die "Go TLS helper build failed; existing service may still be running"
  chmod 755 "$APP_DIR/bin/tlscheck.tmp"
  mv -f "$APP_DIR/bin/tlscheck.tmp" "$APP_DIR/bin/tlscheck"
}


build_rust_health() {
  if ! command -v rustc >/dev/null 2>&1; then
    log "Installing Rust for the health worker..."
    case "$PKG" in
      apt) apt-get update -qq && apt-get install -y rustc ;;
      dnf) dnf install -y rust ;;
      apk) apk add --no-cache rust ;;
      pacman) pacman -Sy --noconfirm rust ;;
      *) die "Install rustc and retry" ;;
    esac
  fi
  mkdir -p "$APP_DIR/bin"
  rustc --edition 2021 -O "$APP_DIR/next/rust/health/src/main.rs" -o "$APP_DIR/bin/pulsegrid-health.tmp" || die "Rust worker build failed; existing service may still be running"
  chmod 755 "$APP_DIR/bin/pulsegrid-health.tmp"
  mv -f "$APP_DIR/bin/pulsegrid-health.tmp" "$APP_DIR/bin/pulsegrid-health"
  [ "$("$APP_DIR/bin/pulsegrid-health" 10 0 true true true)" = 100 ] || die "Rust worker self-test failed"
}


install_core() {
  # Pinned upstream release and SHA-256 digests from GitHub release metadata.
  local asset digest tmp
  case "$ARCH_NORM" in
    x86_64) asset=Xray-linux-64.zip; digest=b651f7e1d9966ee2c1b1ee1bf8b52c72771824d3065dce96bbc8bcc19ed95f82 ;;
    arm64) asset=Xray-linux-arm64-v8a.zip; digest=64ed6858982a7f5eb85d88b811089063bd4f17561f4c8f44e0f1dc8e6f6430be ;;
    *) die "Xray core is not available for architecture $ARCH_NORM" ;;
  esac
  command -v systemctl >/dev/null && [ -d /run/systemd/system ] || die "A running systemd is required"
  tmp=$(mktemp -d)
  log "Downloading Xray v26.11.9 ($ARCH_NORM)..."
  if ! curl -fLsS --retry 3 "https://github.com/XTLS/Xray-core/releases/download/v26.11.9/$asset" -o "$tmp/core.zip"; then
    rm -rf "$tmp"; die "Xray download failed; the core was not installed"
  fi
  if ! echo "$digest  $tmp/core.zip" | sha256sum -c -; then
    rm -rf "$tmp"; die "Xray checksum mismatch"
  fi
  unzip -q "$tmp/core.zip" xray geoip.dat geosite.dat -d "$tmp" || { rm -rf "$tmp"; die "Cannot extract Xray"; }
  mkdir -p /opt/pulsegrid-core
  install -m 755 "$tmp/xray" /opt/pulsegrid-core/xray
  install -m 644 "$tmp/geoip.dat" "$tmp/geosite.dat" /opt/pulsegrid-core/
  rm -rf "$tmp"
  /opt/pulsegrid-core/xray version | head -n 1
}

install_certbot() {
  local venv=/opt/pulsegrid-certbot
  if [ -x "$venv/bin/certbot" ] && "$venv/bin/certbot" --version 2>/dev/null | grep -q "certbot 5.4.0"; then return; fi
  log "Installing a dedicated Certbot 5.4 for IP certificate support..."
  if ! python3 -m venv "$venv"; then
    case "$PKG" in
      apt) apt-get update -qq && apt-get install -y python3-venv ;;
      dnf) dnf install -y python3-pip ;;
      apk) apk add --no-cache py3-pip ;;
      pacman) pacman -Sy --noconfirm python-pip ;;
      *) die "Install Python venv support to obtain certificates" ;;
    esac
    rm -rf "$venv"
    python3 -m venv "$venv" || die "Could not create the Certbot virtual environment"
  fi
  "$venv/bin/python" -m pip install 'certbot==5.4.0' || die "Certbot installation failed; check PyPI access"
}

install_renewal_timer() {
  local lineage=$1
  cat > /etc/systemd/system/pulsegrid-certbot-renew.service <<EOF
[Unit]
Description=Renew PulseGrid certificate
After=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/pulsegrid-certbot/bin/certbot renew --quiet --cert-name $lineage
EOF
  cat > /etc/systemd/system/pulsegrid-certbot-renew.timer <<'EOF'
[Unit]
Description=Check PulseGrid certificate renewal twice daily

[Timer]
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=15m
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now pulsegrid-certbot-renew.timer || die "Could not enable certificate renewal timer"
}

configure_core() {
  local core_env="$CONFIG_DIR/core.env" host core_port saved_host="" saved_port="" saved_lineage="" cert key certbot_managed="0" kind lineage
  if [ -f "$core_env" ]; then
    saved_host=$(sed -n 's/^PULSEGRID_PUBLIC_HOST=//p' "$core_env")
    saved_port=$(sed -n 's/^PULSEGRID_CORE_PORT=//p' "$core_env")
    saved_lineage=$(sed -n 's/^PULSEGRID_CERTBOT_LINEAGE=//p' "$core_env")
    certbot_managed=$(sed -n 's/^PULSEGRID_CERTBOT_MANAGED=//p' "$core_env")
  fi
  host="${PULSEGRID_PUBLIC_HOST:-$saved_host}"
  core_port="${PULSEGRID_CORE_PORT:-${saved_port:-10000}}"
  kind=$(cd "$APP_DIR" && python3 -m pulsegrid.address "$host") || die "Set PULSEGRID_PUBLIC_HOST to a public IPv4 address or domain"
  [[ "$core_port" =~ ^[0-9]+$ ]] && (( core_port >= 1024 && core_port <= 65535 && core_port != PORT )) || die "Invalid core port (must be 1024-65535 and differ from dashboard port)"
  lineage="/etc/letsencrypt/live/$host"
  if [[ -n "${PULSEGRID_TLS_CERT:-}" || -n "${PULSEGRID_TLS_KEY:-}" ]]; then
    [[ -n "${PULSEGRID_TLS_CERT:-}" && -n "${PULSEGRID_TLS_KEY:-}" ]] || die "Provide both PULSEGRID_TLS_CERT and PULSEGRID_TLS_KEY"
    cert=$PULSEGRID_TLS_CERT; key=$PULSEGRID_TLS_KEY
    case "$cert" in /etc/letsencrypt/live/*/fullchain.pem) certbot_managed=1; lineage="${cert%/fullchain.pem}" ;; *) certbot_managed=0 ;; esac
  elif [ "$host" = "$saved_host" ] && [ -f "$CONFIG_DIR/tls-current/fullchain.pem" ]; then
    cert="$CONFIG_DIR/tls-current/fullchain.pem"; key="$CONFIG_DIR/tls-current/privkey.pem"
    [ -z "$saved_lineage" ] || lineage="$saved_lineage"
  else
    cert="$lineage/fullchain.pem"; key="$lineage/privkey.pem"
    install_certbot
    if [ ! -f "$cert" ]; then
      log "Requesting a public TLS certificate for $host. Port 80 must be reachable and free."
      if [ "$kind" = ip ]; then
        /opt/pulsegrid-certbot/bin/certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email --preferred-profile shortlived --cert-name "$host" --ip-address "$host" || die "IP certificate issuance failed; check public IP and TCP port 80. Existing service may still be running."
      else
        /opt/pulsegrid-certbot/bin/certbot certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email --cert-name "$host" -d "$host" || die "Certificate issuance failed; check DNS and TCP port 80. Existing service may still be running."
      fi
    fi
    certbot_managed=1
  fi
  "$APP_DIR/bin/tlscheck" "$host" "$cert" "$key" >/dev/null || die "TLS setup failed. Provide a valid certificate and key for $host; any previous service may still be running."
  if [ "$cert" != "$CONFIG_DIR/tls-current/fullchain.pem" ]; then
    bash "$APP_DIR/scripts/deploy-cert.sh" "$host" "$cert" "$key" || die "Could not install TLS certificate"
  fi
  printf 'PULSEGRID_PUBLIC_HOST=%s\nPULSEGRID_CORE_PORT=%s\nPULSEGRID_DASHBOARD_TLS=1\nPULSEGRID_CERTBOT_MANAGED=%s\nPULSEGRID_CERTBOT_LINEAGE=%s\nXRAY_LOCATION_ASSET=/opt/pulsegrid-core\n' "$host" "$core_port" "${certbot_managed:-0}" "$lineage" > "$core_env"
  chown pulsegrid:pulsegrid "$core_env"; chmod 600 "$core_env"
  if [ "${certbot_managed:-0}" = 1 ]; then
    install_certbot
    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    install -m 755 "$APP_DIR/scripts/certbot-deploy.sh" /etc/letsencrypt/renewal-hooks/deploy/pulsegrid
    install_renewal_timer "$(basename "$lineage")"
    log "Automatic renewal timer and deploy hook installed. Keep TCP port 80 reachable and free."
  else
    systemctl disable --now pulsegrid-certbot-renew.timer 2>/dev/null || true
    rm -f /etc/letsencrypt/renewal-hooks/deploy/pulsegrid
    warn "Custom TLS certificate: reinstall it with scripts/deploy-cert.sh after each renewal."
  fi
  log "Core TLS address: $host:$core_port"
  warn "Open TCP port $core_port in your firewall. Traffic metering/quota enforcement is not integrated."
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
Environment=PULSEGRID_HEALTH_BIN=$APP_DIR/bin/pulsegrid-health
EnvironmentFile=$CONFIG_DIR/core.env
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
  systemctl enable "$APP_NAME"
  systemctl restart "$APP_NAME"
}

firewall_hints() {
  warn "Open dashboard TCP port $PORT only to trusted addresses."
  warn "Open the configured core TCP port in your server and cloud firewall."
}

health_check() {
  local host core_port
  host=$(sed -n 's/^PULSEGRID_PUBLIC_HOST=//p' "$CONFIG_DIR/core.env")
  core_port=$(sed -n 's/^PULSEGRID_CORE_PORT=//p' "$CONFIG_DIR/core.env")
  log "Running health checks..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl --noproxy '*' --resolve "$host:$PORT:127.0.0.1" -fsS "https://$host:$PORT/api/health" >/dev/null 2>&1; then
      log "Dashboard HTTPS health check passed"
      break
    fi
    sleep 1
  done
  curl --noproxy '*' --resolve "$host:$PORT:127.0.0.1" -fsS "https://$host:$PORT/api/health" >/dev/null || die "Dashboard HTTPS health check failed — check journalctl -u $APP_NAME"
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if python3 - "$host" "$core_port" <<'PYHEALTH'
import socket, ssl, sys
try:
    with socket.create_connection(('127.0.0.1', int(sys.argv[2])), timeout=2) as sock:
        with ssl.create_default_context().wrap_socket(sock, server_hostname=sys.argv[1]):
            pass
except (OSError, ssl.SSLError) as exc:
    print('Core TLS check:', exc, file=sys.stderr)
    sys.exit(1)
PYHEALTH
    then
      log "Core verified TLS handshake passed"
      return 0
    fi
    sleep 1
  done
  die "Core TLS health check failed — check journalctl -u $APP_NAME -n 100"
}

print_success() {
  TOKEN="$(cat "$CONFIG_DIR/token" 2>/dev/null || echo '<see /etc/pulsegrid/token>')"
  IP="$(sed -n 's/^PULSEGRID_PUBLIC_HOST=//p' "$CONFIG_DIR/core.env")"
  cat <<EOF

${GREEN}✅ PulseGrid installed successfully!${NC}

   Dashboard : https://$IP:$PORT
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
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || die "Python 3.10 or later is required"
  setup_dirs_and_token; build_go_tlscheck; build_rust_health; configure_core; install_core; write_service; firewall_hints; health_check; print_success
}

do_update() {
  require_root; detect_os; install_deps; fetch_code
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || die "Python 3.10 or later is required"
  setup_dirs_and_token; build_go_tlscheck; build_rust_health; configure_core; install_core; write_service
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
  local host
  host=$(sed -n 's/^PULSEGRID_PUBLIC_HOST=//p' "$CONFIG_DIR/core.env" 2>/dev/null || true)
  if [ -n "$host" ]; then
    curl --noproxy '*' --resolve "$host:$PORT:127.0.0.1" -fsS "https://$host:$PORT/api/health" 2>/dev/null && echo " <- health OK" || echo "HTTPS health endpoint: not responding on port $PORT"
  fi
  echo "Logs: journalctl -u $APP_NAME -n 50"
}

do_uninstall() {
  require_root
  PURGE=0
  for a in "$@"; do [ "$a" = "--purge" ] && PURGE=1; done
  log "Uninstalling PulseGrid..."
  systemctl disable --now "$APP_NAME" 2>/dev/null || true
  systemctl disable --now pulsegrid-certbot-renew.timer 2>/dev/null || true
  rm -f "$SERVICE_FILE" /etc/letsencrypt/renewal-hooks/deploy/pulsegrid /etc/systemd/system/pulsegrid-certbot-renew.service /etc/systemd/system/pulsegrid-certbot-renew.timer
  systemctl daemon-reload 2>/dev/null || true
  rm -rf "$APP_DIR" /opt/pulsegrid-core /opt/pulsegrid-certbot
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
