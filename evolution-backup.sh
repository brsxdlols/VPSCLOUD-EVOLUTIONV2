#!/bin/sh
# Coordinated backup for the standard PostgreSQL + Redis layout.
# Stops only the API briefly and always attempts to bring it back on exit.
set -eu
umask 077
PROJECT_DIR=${EVOLUTION_PROJECT_DIR:-/opt/vpscloud-evolution-v2}
API=evolution_v2_api
PG=evolution_v2_postgres
REDIS=evolution_v2_redis
[ "$(id -u)" = 0 ] || { echo 'ERRO: execute como root.'; exit 1; }
for dep in docker sha256sum tar df awk; do command -v "$dep" >/dev/null || exit 1; done
LOCK=/run/lock/vpscloud-evolution-session.lock
mkdir "$LOCK" 2>/dev/null || { echo 'ERRO: operacao de sessao em andamento ou lock pendente.'; exit 1; }
STOPPED=0
finish() {
  rc=$?
  trap - EXIT
  if [ "$STOPPED" = 1 ]; then docker start "$API" >/dev/null || rc=1; fi
  rmdir "$LOCK" 2>/dev/null || true
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for c in "$API" "$PG" "$REDIS"; do
  [ "$(docker inspect --format '{{.State.Running}}' "$c")" = true ] || { echo "ERRO: $c nao esta ativo."; exit 1; }
done
for pair in "$PG:/var/lib/postgresql/data" "$REDIS:/data"; do
  c=${pair%%:*}; dest=${pair#*:}
  docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "$c" | grep -qx "$dest" || exit 1
done
# Only the backend validated in this investigation is supported by this helper.
docker exec "$API" node -e 'if(process.env.PROVIDER_ENABLED==="true"||process.env.CACHE_REDIS_ENABLED!=="true"||process.env.CACHE_REDIS_SAVE_INSTANCES!=="true")process.exit(1)' || {
  echo 'ERRO: backend nao padrao; backup de autenticacao deve ser planejado manualmente.'; exit 1;
}
[ -d "$PROJECT_DIR" ] || exit 1
FREE=$(df -Pk "$PROJECT_DIR" | awk 'NR==2 {print $4}')
[ "$FREE" -ge 2097152 ] || { echo 'ERRO: necessario ao menos 2 GiB livres; confira tambem o tamanho dos dados.'; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S)-$$
B="$PROJECT_DIR/backups/session-$STAMP"
mkdir -p "$B"
docker inspect "$API" "$PG" "$REDIS" > "$B/containers.json"
if [ -f "$PROJECT_DIR/evolution-v2.env" ]; then cp -p "$PROJECT_DIR/evolution-v2.env" "$B/"; fi
if [ -d "$PROJECT_DIR/manager-dist" ]; then tar -C "$PROJECT_DIR" -cf "$B/manager.tar" manager-dist; fi
IMAGE=$(docker inspect --format '{{.Image}}' "$API")
docker image save "$IMAGE" > "$B/api-image.tar"
# Never print the credential; retrieve from the effective container environment.
RP=$(docker exec "$API" node -e 'const u=new URL(process.env.CACHE_REDIS_URI);process.stdout.write(decodeURIComponent(u.password))')
[ -n "$RP" ] || { echo 'ERRO: Redis sem senha ou URI nao suportada.'; exit 1; }
STOPPED=1
docker stop -t 30 "$API" >/dev/null
docker exec "$PG" pg_dump -U evolution -d evolution_api -Fc > "$B/postgres.dump"
[ -s "$B/postgres.dump" ] || exit 1
TMP="/tmp/evolution-verify-$STAMP.dump"
docker cp "$B/postgres.dump" "$PG:$TMP"
docker exec "$PG" pg_restore -l "$TMP" > "$B/postgres-catalog.txt"
docker exec "$PG" rm -f "$TMP"
docker exec -e REDISCLI_AUTH="$RP" "$REDIS" redis-cli SAVE >/dev/null
docker exec "$REDIS" redis-check-rdb /data/dump.rdb > "$B/redis-check.txt"
docker cp "$REDIS:/data/dump.rdb" "$B/redis.rdb"
docker start "$API" >/dev/null
STOPPED=0
chmod 600 "$B"/*
(cd "$B" && sha256sum postgres.dump redis.rdb api-image.tar > SHA256SUMS)
printf '%s\n' "$B" > "$PROJECT_DIR/backups/LATEST-SESSION-BACKUP"
printf 'BACKUP=%s\nCatalogo e RDB verificados. Teste restauracao isolada antes de upgrade.\n' "$B"
