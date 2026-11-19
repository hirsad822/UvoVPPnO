#!/usr/bin/env bash
# Install a validated certificate pair atomically for the unprivileged service.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root' >&2; exit 1; }
[ "$#" -ge 3 ] || { echo 'Usage: deploy-cert.sh domain fullchain key [--restart]' >&2; exit 1; }
host=$1; cert=$2; key=$3; restart=${4:-}
config=/etc/pulsegrid
app=/opt/pulsegrid
"$app/bin/tlscheck" "$host" "$cert" "$key" >/dev/null
tmp=$(mktemp -d "$config/tls.XXXXXXXX")
cleanup() { [ -z "${tmp:-}" ] || rm -rf -- "$tmp"; }
trap cleanup EXIT
install -m 600 -o pulsegrid -g pulsegrid "$cert" "$tmp/fullchain.pem"
install -m 600 -o pulsegrid -g pulsegrid "$key" "$tmp/privkey.pem"
chown pulsegrid:pulsegrid "$tmp"; chmod 700 "$tmp"
"$app/bin/tlscheck" "$host" "$tmp/fullchain.pem" "$tmp/privkey.pem" >/dev/null
link="$config/tls-next-$$"
ln -s "$(basename "$tmp")" "$link"
mv -Tf "$link" "$config/tls-current"
tmp=""
if [ "$restart" = "--restart" ]; then
  systemctl restart pulsegrid
fi
