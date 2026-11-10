#!/usr/bin/env bash
# Temporary: find which Playtomic endpoint answers from GitHub's runners.
Q='sport_id=PADEL&coordinate=51.4545,-2.5879&radius=25000'
UA='User-Agent: padel-watch personal script (low frequency)'
for h in api.playtomic.io playtomic.io playtomic.com api.playtomic.com; do
  echo "DNS $h: $(getent hosts $h | head -1)"
done
for u in \
  "https://playtomic.io/api/v1/tenants?$Q" \
  "https://playtomic.io/api/v1/tenants?$Q&size=50" \
  "https://playtomic.io/api/v1/tenants?$Q&playtomic_status=ACTIVE" \
  "https://api.playtomic.io/v1/tenants?$Q" \
  "https://playtomic.com/api/v1/tenants?$Q" \
  "https://api.playtomic.com/v1/tenants?$Q" \
  "https://playtomic.com/api/v2/tenants?$Q" ; do
  out=$(curl -sS -m 20 -H "$UA" -w '\n__HTTP %{http_code} %{url_effective}' "$u" 2>&1)
  echo "=== $u"; echo "$(tail -1 <<<"$out")"; head -c 400 <<<"$(sed '$d' <<<"$out")"; echo
  if [[ -z "$TID" && "$out" == *'"tenant_id"'* ]]; then
    TID=$(grep -oE '"tenant_id" *: *"[^"]+"' <<<"$out" | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
    BASE=${u%%/tenants*}
  fi
done
echo "first tenant: $TID via $BASE"
if [[ -n "$TID" ]]; then
  D=$(date -u -d tomorrow +%F)
  for p in "start_min=${D}T00:00:00&start_max=${D}T23:59:59" "local_start_min=${D}T00:00:00&local_start_max=${D}T23:59:59"; do
    u="$BASE/availability?sport_id=PADEL&tenant_id=$TID&$p"
    echo "=== $u"; curl -sS -m 20 -H "$UA" -w '\n__HTTP %{http_code}\n' "$u" | head -c 700; echo
  done
fi
