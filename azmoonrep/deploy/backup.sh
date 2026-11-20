#!/usr/bin/env bash
# Nightly MongoDB backup for AzmoonRep: a gzip archive per day, the last 14 are kept.
#   crontab -e  ->  30 3 * * * bash /opt/azmoon/azmoonrep/deploy/backup.sh >> /opt/azmoon/backups/backup.log 2>&1
# Copy /opt/azmoon/backups off the server too (scp/rsync from your computer): a backup on the
# same disk does not survive losing the server.
# Restore:  docker exec -i azmoon_mongo mongorestore --archive --gzip -u USER -p PASS \
#             --authenticationDatabase admin --drop < azmoon-YYYY-MM-DD.gz
set -euo pipefail
WORKSPACE="${WORKSPACE:-/opt/azmoon}"
set -a; . "$WORKSPACE/azmoonrep/.env"; set +a
DIR="$WORKSPACE/backups"
mkdir -p "$DIR"
OUT="$DIR/azmoon-$(date +%F).gz"
docker exec azmoon_mongo mongodump --quiet --archive --gzip \
  -u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin --db azmoonrep > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
chmod 600 "$OUT"
ls -1t "$DIR"/azmoon-*.gz | tail -n +15 | xargs -r rm -f
echo "$(date -Is) backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
