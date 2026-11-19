#!/usr/bin/env bash
# PulseGrid post-install verification.
# Usage: bash scripts/verify.sh [BASE_URL] [TOKEN]
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${1:-http://127.0.0.1:8080}"
TOKEN="${2:-${PULSEGRID_TOKEN:-}}"
PASS=0; FAIL=0
ok() { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "== PulseGrid verification =="
echo "Base: $BASE"

# 1. Health
if curl -fsS "$BASE/api/health" >/dev/null 2>&1; then ok "Health endpoint responds"; else bad "Health endpoint unreachable"; fi

# 2. Dashboard (needs token)
if [ -n "$TOKEN" ]; then
  if curl -fsS -H "Authorization: Bearer $TOKEN" "$BASE/api/dashboard" >/dev/null 2>&1; then
    ok "Dashboard API (auth) works"
  else bad "Dashboard API failed (check token)"; fi
else
  echo "  ⚠️  No token given — skipping auth checks. Usage: bash scripts/verify.sh $BASE <token>"
fi

# 3. Unit tests
if command -v python3 >/dev/null 2>&1; then
  if python3 -m unittest discover -s tests -q 2>&1 | tail -n 3 | grep -q "OK"; then
    ok "Unit tests pass"
  else
    # unittest prints OK on stderr; re-run verbosely for clarity
    python3 -m unittest discover -s tests -v 2>&1 | tail -n 5 || true
    bad "Unit tests failed (see above)"
  fi
else
  bad "python3 not found"
fi

echo ""
echo "Result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && echo "✅ All checks passed" || echo "⚠️  Some checks failed — see docs/TROUBLESHOOTING.md"
exit "$FAIL"
