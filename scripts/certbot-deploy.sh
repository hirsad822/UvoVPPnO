#!/usr/bin/env bash
# Certbot deploy hook: only install a renewed certificate covering our domain.
set -euo pipefail
config=/etc/pulsegrid/core.env
[ -f "$config" ] || exit 0
host=$(sed -n 's/^PULSEGRID_PUBLIC_HOST=//p' "$config")
[ -n "$host" ] && [ -n "${RENEWED_LINEAGE:-}" ] || exit 0
case " ${RENEWED_DOMAINS:-} " in
  *" $host "*) ;;
  *) exit 0 ;;
esac
exec /opt/pulsegrid/scripts/deploy-cert.sh "$host" "$RENEWED_LINEAGE/fullchain.pem" "$RENEWED_LINEAGE/privkey.pem" --restart
