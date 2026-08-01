#!/bin/sh
set -u
RETENTION_DAYS="${EVOLUTION_RETENTION_DAYS:-7}"
BACKUP_ROOT="/root/evolution-v1-backups"
LOCK_DIR="/run/lock/vpscloud-evolution-cleanup.lock"
case "$RETENTION_DAYS" in ''|*[!0-9]*) RETENTION_DAYS=7 ;; esac
if ! mkdir "$LOCK_DIR" 2>/dev/null; then echo "Limpeza ja esta em execucao."; exit 0; fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
trim_file() {
  FILE="$1"; MAX_BYTES="$2"; KEEP_BYTES="$3"
  [ -f "$FILE" ] || return 0
  SIZE="$(wc -c < "$FILE" 2>/dev/null || echo 0)"
  [ "$SIZE" -gt "$MAX_BYTES" ] || return 0
  TMP="${FILE}.vpscloud-cleanup.tmp"
  if tail -c "$KEEP_BYTES" "$FILE" > "$TMP" 2>/dev/null; then cat "$TMP" > "$FILE"; fi
  rm -f "$TMP"
}
clear_cache_if_large() {
  CACHE_DIR="$1"
  LIMIT_KB="$2"
  [ -d "$CACHE_DIR" ] || return 0
  SIZE_KB="$(du -sk "$CACHE_DIR" 2>/dev/null | awk '{print $1}')"
  [ -n "$SIZE_KB" ] || return 0
  [ "$SIZE_KB" -gt "$LIMIT_KB" ] || return 0
  rm -rf "$CACHE_DIR"
}
echo "[$(date '+%F %T')] Iniciando limpeza. Retencao: ${RETENTION_DAYS} dias."
if docker inspect evolution_v2_postgres >/dev/null 2>&1; then
  docker exec evolution_v2_postgres psql -U evolution -d evolution_api -v ON_ERROR_STOP=1 -c "DELETE FROM \"Message\" WHERE \"messageTimestamp\" = 0 OR \"messageTimestamp\" < EXTRACT(EPOCH FROM NOW() - (${RETENTION_DAYS} * INTERVAL '1 day'))::integer;" || true
  docker exec evolution_v2_postgres psql -U evolution -d evolution_api -v ON_ERROR_STOP=1 -c 'VACUUM (ANALYZE) "Message";' || true
fi
find /var/lib/docker/containers -type f -name '*-json.log' -size +20M 2>/dev/null | while IFS= read -r LOG_FILE; do trim_file "$LOG_FILE" 20971520 10485760; done
trim_file /var/log/mkauth_radius_ppp_reconcile.log 52428800 10485760
trim_file /var/log/docker_check.log 52428800 10485760
trim_file /var/log/messages 104857600 20971520
trim_file /root/.pm2/pm2.log 52428800 10485760
if [ -d /root/.pm2/logs ]; then
  find /root/.pm2/logs -type f -size +20M 2>/dev/null | while IFS= read -r PM2_LOG; do trim_file "$PM2_LOG" 20971520 10485760; done
fi
clear_cache_if_large /root/.cache/pip 524288
clear_cache_if_large /root/.cache/torch 524288
clear_cache_if_large /root/.cache/puppeteer 524288
clear_cache_if_large /root/.cache/node-gyp 524288
clear_cache_if_large /root/.npm/_cacache 524288
# Conteineres parados sao preservados para permitir rollback da Evolution v1.
docker image prune -a -f --filter until=168h >/dev/null 2>&1 || true
docker builder prune -f --filter until=168h >/dev/null 2>&1 || true
if [ -d "$BACKUP_ROOT" ]; then
  ls -1dt "$BACKUP_ROOT"/v1-* 2>/dev/null | sed -n '3,$p' | while IFS= read -r OLD_BACKUP; do
    case "$OLD_BACKUP" in "$BACKUP_ROOT"/v1-*) rm -rf "$OLD_BACKUP" ;; esac
  done
fi
command -v apt-get >/dev/null 2>&1 && apt-get clean >/dev/null 2>&1 || true
clear_cache_if_large() {
  CACHE_DIR="$1"
  LIMIT_KB="$2"
  [ -d "$CACHE_DIR" ] || return 0
  SIZE_KB="$(du -sk "$CACHE_DIR" 2>/dev/null | awk '{print $1}')"
  [ -n "$SIZE_KB" ] || return 0
  [ "$SIZE_KB" -gt "$LIMIT_KB" ] || return 0
  rm -rf "$CACHE_DIR"
}
echo "[$(date '+%F %T')] Limpeza concluida."
df -h /
