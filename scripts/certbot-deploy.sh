#!/usr/bin/env bash
# Only deploy the lineage configured for this installation (including IP certs).
set -euo pipefail
config=/etc/pulsegrid/core.env
[ -f "$config" ] || exit 0
host=$(sed -n 's/^PULSEGRID_PUBLIC_HOST=//p' "$config")
lineage=$(sed -n 's/^PULSEGRID_CERTBOT_LINEAGE=//p' "$config")
[ -n "$host" ] && [ -n "$lineage" ] && [ "${RENEWED_LINEAGE:-}" = "$lineage" ] || exit 0
exec /opt/pulsegrid/scripts/deploy-cert.sh "$host" "$lineage/fullchain.pem" "$lineage/privkey.pem" --restart
