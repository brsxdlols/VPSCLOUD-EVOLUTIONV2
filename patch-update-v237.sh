#!/bin/sh
# VPSCloud Evolution v2: patch for existing MK-AUTH installations.
# Upgrades ONLY the API container; PostgreSQL, Redis and WhatsApp sessions are preserved.
set -eu
umask 077

API=evolution_v2_api
PG=evolution_v2_postgres
REDIS=evolution_v2_redis
IMAGE=evoapicloud/evolution-api:v2.3.7
DIR=/opt/vpscloud-evolution-v2
ENV_FILE=$DIR/evolution-v2.env
MANAGER=$DIR/manager-dist
NETWORK=evolution_v2_net
PORT=${EVOLUTION_PORT:-7070}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/root/backup-evolution/patch-v237-$STAMP
OLD=${API}_rollback_$STAMP
OLD_STOPPED=0
NEW_CREATED=0

die() { echo "ERRO: $*" >&2; exit 1; }
get_env() { sed -n "s/^$1=//p" "$ENV_FILE" | head -n 1; }
running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = true ]; }
rollback() {
  echo "Falha no patch. Tentando restaurar o container antigo..."
  if [ "$NEW_CREATED" -eq 1 ]; then docker rm -f "$API" >/dev/null 2>&1 || true; fi
  if [ "$OLD_STOPPED" -eq 1 ]; then
    docker rename "$OLD" "$API" >/dev/null 2>&1 || true
    docker start "$API" >/dev/null 2>&1 || true
  fi
}
trap 'rollback' 0
trap 'exit 1' 1 2 3 15

[ "$(id -u)" -eq 0 ] || die "Execute como root."
command -v docker >/dev/null 2>&1 || die "Docker nao instalado."
command -v curl >/dev/null 2>&1 || die "curl nao instalado."
[ -s "$ENV_FILE" ] || die "Arquivo de ambiente nao encontrado."
[ -d "$MANAGER" ] || die "Manager personalizado nao encontrado."
running "$API" || die "API atual nao esta em execucao."
running "$PG" || die "PostgreSQL nao esta em execucao."
running "$REDIS" || die "Redis nao esta em execucao."
docker network inspect "$NETWORK" >/dev/null 2>&1 || die "Rede Docker ausente."
[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$API")" = "$NETWORK" ] || die "Rede do container difere do esperado."
[ "$(docker inspect -f '{{(index (index .NetworkSettings.Ports "8080/tcp") 0).HostPort}}' "$API")" = "$PORT" ] || die "Mapeamento de porta inesperado."
docker inspect "$API" -f '{{range .Mounts}}{{if eq .Destination "/evolution/manager/dist"}}{{.Source}}{{end}}{{end}}' | grep -Fx "$MANAGER" >/dev/null || die "Mount do Manager difere do esperado."
[ "$(docker inspect -f '{{.Config.Image}}' "$API")" != "$IMAGE" ] || {
  echo "API ja utiliza $IMAGE. Nada a atualizar."; trap - 0; exit 0;
}
[ "$(get_env DATABASE_SAVE_MESSAGE_UPDATE)" = false ] || die "DATABASE_SAVE_MESSAGE_UPDATE deve ser false; revise o .env antes de atualizar."
KEY=$(get_env AUTHENTICATION_API_KEY)
[ -n "$KEY" ] || die "Chave de API nao encontrada."
[ -n "$(get_env DATABASE_PASSWORD)" ] || die "Senha PostgreSQL nao encontrada."
[ -z "$(docker ps -a --filter "name=^/${OLD}$" --format '{{.Names}}')" ] || die "Nome de backup ja utilizado."

mkdir -p "$BACKUP"
chmod 700 "$BACKUP"
cp -p "$ENV_FILE" "$BACKUP/evolution-v2.env"
docker inspect "$API" > "$BACKUP/api-inspect.json"
docker inspect "$PG" > "$BACKUP/postgres-inspect.json"
docker inspect "$REDIS" > "$BACKUP/redis-inspect.json"
echo "Salvando backup do PostgreSQL em $BACKUP..."
docker exec "$PG" pg_dump -U evolution -d evolution_api -Fc > "$BACKUP/postgres.dump" || die "Falha no pg_dump."
[ -s "$BACKUP/postgres.dump" ] || die "Backup PostgreSQL vazio."
# Preserve Redis in place. No Redis container, volume or credentials are modified.
echo "Baixando imagem $IMAGE..."
docker pull "$IMAGE"
echo "Iniciando troca controlada somente da API..."
docker stop "$API" >/dev/null || die "Nao foi possivel parar a API."
OLD_STOPPED=1
docker rename "$API" "$OLD" || die "Falha ao renomear API antiga."
docker run -d \
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \
  --name "$API" --restart on-failure \
  --network "$NETWORK" --env-file "$ENV_FILE" \
  -p "$PORT:8080" \
  -v "$MANAGER:/evolution/manager/dist:ro" \
  "$IMAGE" node ./dist/src/main.js >/dev/null || die "Falha ao iniciar API nova."
NEW_CREATED=1
i=0
while [ "$i" -lt 90 ]; do
  if running "$API"; then
    CODE=$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' \
      -H "apikey: $KEY" "http://127.0.0.1:$PORT/instance/fetchInstances" 2>/dev/null || true)
    if [ "$CODE" = 200 ]; then
      echo "API v2.3.7 respondeu HTTP 200."
      echo "Container anterior preservado parado: $OLD"
      echo "Backup PostgreSQL e configuracoes: $BACKUP"
      echo "Redis e PostgreSQL nao foram reiniciados."
      echo "Teste o envio e recebimento pelo Evolution Manager e MK-AUTH."
      trap - 0
      exit 0
    fi
  fi
  i=$((i + 1))
  sleep 2
done
die "API nova nao respondeu no prazo; rollback automatico sera tentado."
