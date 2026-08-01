#!/bin/sh
set -eu

PROJECT_DIR="/opt/vpscloud-evolution-v2"
ENV_FILE="$PROJECT_DIR/evolution-v2.env"
MANAGER_DIR="$PROJECT_DIR/manager-dist"
BACKUP_ROOT="/root/evolution-v1-backups"

API_CONTAINER="evolution_v2_api"
PG_CONTAINER="evolution_v2_postgres"
REDIS_CONTAINER="evolution_v2_redis"
NETWORK="evolution_v2_net"
PG_VOLUME="evolution_v2_postgres_data"
REDIS_VOLUME="evolution_v2_redis_data"

API_IMAGE="evoapicloud/evolution-api:v2.3.4"
PG_IMAGE="postgres:15-alpine"
REDIS_IMAGE="redis:7.4-alpine"
API_PORT="${EVOLUTION_PORT:-7070}"
API_KEY="123456"
LOGO_URL="https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/assets/evolution-logo-header.jpg"
OLD_LOGO_URL="https://evolution-api.com/files/evo/evolution-logo-white.svg"
CLEANUP_URL="https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/cleanup.sh"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker nao encontrado."
  exit 1
fi

mkdir -p "$PROJECT_DIR" "$BACKUP_ROOT"
chmod 700 "$PROJECT_DIR" "$BACKUP_ROOT"

install_daily_cleanup() {
  curl -fsSL "$CLEANUP_URL" -o /usr/local/sbin/vpscloud-evolution-cleanup
  chmod 700 /usr/local/sbin/vpscloud-evolution-cleanup
  cat > /etc/cron.d/vpscloud-evolution-cleanup <<EOF
25 3 * * * root EVOLUTION_RETENTION_DAYS=${EVOLUTION_RETENTION_DAYS:-7} /usr/local/sbin/vpscloud-evolution-cleanup >> /var/log/vpscloud-evolution-cleanup.log 2>&1
EOF
  chmod 644 /etc/cron.d/vpscloud-evolution-cleanup
  /usr/local/sbin/vpscloud-evolution-cleanup >> /var/log/vpscloud-evolution-cleanup.log 2>&1 || true
}
backup_v1() {
  if ! docker inspect evolution_api >/dev/null 2>&1; then
    return
  fi

  STAMP="$(date +%Y%m%d-%H%M%S)"
  BACKUP_DIR="$BACKUP_ROOT/v1-$STAMP"
  mkdir -p "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR"

  docker inspect evolution_api > "$BACKUP_DIR/evolution_api.inspect.json"
  docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' evolution_api \
    > "$BACKUP_DIR/evolution_api.env"
  chmod 600 "$BACKUP_DIR/evolution_api.inspect.json" "$BACKUP_DIR/evolution_api.env"

  if docker exec evolution_api test -d /evolution >/dev/null 2>&1; then
    docker cp evolution_api:/evolution "$BACKUP_DIR/evolution"
  fi

  printf '%s\n' "$BACKUP_DIR" > "$BACKUP_ROOT/LAST_BACKUP"
  echo "Backup da v1: $BACKUP_DIR"
}

remove_v1() {
  if ! docker inspect evolution_api >/dev/null 2>&1; then
    echo "Evolution v1 nao encontrada."
    return
  fi

  V1_IMAGE="$(docker inspect --format '{{.Config.Image}}' evolution_api)"
  echo "Parando e removendo completamente o conteiner Evolution v1..."
  docker rm -f -v evolution_api >/dev/null

  if [ -n "$V1_IMAGE" ]; then
    docker image rm "$V1_IMAGE" >/dev/null 2>&1 || true
  fi

  echo "Evolution v1 removida. Backup preservado em $BACKUP_ROOT."
}
create_env() {
  if [ -s "$ENV_FILE" ]; then
    return
  fi

  DB_PASSWORD="$(openssl rand -hex 24)"
  REDIS_PASSWORD="$(openssl rand -hex 24)"
  HOST_ADDRESS="$(
    hostname -I 2>/dev/null |
      awk '{print $1}'
  )"
  if [ -z "$HOST_ADDRESS" ]; then
    HOST_ADDRESS="127.0.0.1"
  fi
  SERVER_URL="${EVOLUTION_SERVER_URL:-http://${HOST_ADDRESS}:${API_PORT}}"

  cat > "$ENV_FILE" <<EOF
SERVER_NAME=EvolutionAPI
SERVER_TYPE=http
SERVER_PORT=8080
SERVER_URL=${SERVER_URL}
SERVER_DISABLE_DOCS=true
SERVER_DISABLE_MANAGER=false
LANGUAGE=pt-BR
CORS_ORIGIN=*
CORS_METHODS=POST,GET,PUT,DELETE,OPTIONS
CORS_CREDENTIALS=true
DATABASE_PROVIDER=postgresql
DATABASE_USER=evolution
DATABASE_PASSWORD=${DB_PASSWORD}
DATABASE_DB=evolution_api
DATABASE_CONNECTION_URI=postgresql://evolution:${DB_PASSWORD}@${PG_CONTAINER}:5432/evolution_api?schema=public
DATABASE_CONNECTION_CLIENT_NAME=mkauth_evolution_v2
DATABASE_SAVE_DATA_INSTANCE=true
DATABASE_SAVE_DATA_NEW_MESSAGE=true
DATABASE_SAVE_MESSAGE_UPDATE=true
DATABASE_SAVE_DATA_CONTACTS=true
DATABASE_SAVE_DATA_CHATS=true
DATABASE_SAVE_DATA_HISTORIC=true
DATABASE_SAVE_DATA_LABELS=true
DATABASE_SAVE_IS_ON_WHATSAPP=true
DATABASE_SAVE_IS_ON_WHATSAPP_DAYS=7
DATABASE_DELETE_MESSAGE=false
CACHE_REDIS_ENABLED=true
REDIS_PASSWORD=${REDIS_PASSWORD}
CACHE_REDIS_URI=redis://:${REDIS_PASSWORD}@${REDIS_CONTAINER}:6379/6
CACHE_REDIS_PREFIX_KEY=evolution-cache
CACHE_REDIS_TTL=604800
CACHE_REDIS_SAVE_INSTANCES=true
CACHE_LOCAL_ENABLED=true
CACHE_LOCAL_TTL=86400
AUTHENTICATION_API_KEY=${API_KEY}
AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
LOG_LEVEL=ERROR,WARN,INFO,LOG
LOG_COLOR=true
LOG_BAILEYS=error
DEL_INSTANCE=false
DEL_TEMP_INSTANCES=true
WEBSOCKET_ENABLED=true
WEBSOCKET_GLOBAL_EVENTS=true
WEBSOCKET_ALLOWED_HOSTS=
QRCODE_LIMIT=30
QRCODE_COLOR=#198754
CONFIG_SESSION_PHONE_CLIENT=Evolution
CONFIG_SESSION_PHONE_NAME=Evolution
CONFIG_SESSION_PHONE_VERSION=2.3000.1028788854
CHATWOOT_ENABLED=true
CHATWOOT_MESSAGE_DELETE=false
CHATWOOT_MESSAGE_READ=true
CHATWOOT_BOT_CONTACT=true
CHATWOOT_IMPORT_PLACEHOLDER_MEDIA_MESSAGE=false
TZ=America/Sao_Paulo
EOF
  chmod 600 "$ENV_FILE"
}

env_value() {
  sed -n "s/^$1=//p" "$ENV_FILE" |
    head -n 1
}

wait_postgres_redis() {
  i=0
  while [ "$i" -lt 60 ]; do
    if docker exec "$PG_CONTAINER" pg_isready -U evolution -d evolution_api >/dev/null 2>&1 &&
       docker exec "$REDIS_CONTAINER" redis-cli -a "$(env_value REDIS_PASSWORD)" ping 2>/dev/null |
         grep -q PONG; then
      return
    fi
    i=$((i + 1))
    sleep 2
  done
  echo "ERRO: PostgreSQL ou Redis nao ficou pronto."
  exit 1
}

wait_api() {
  i=0
  while [ "$i" -lt 90 ]; do
    CODE="$(
      curl -sS -o /tmp/evolution-v2-health.out -w '%{http_code}' \
        -H "apikey: $API_KEY" \
        "http://127.0.0.1:${API_PORT}/instance/fetchInstances" || true
    )"
    if [ "$CODE" = "200" ]; then
      return
    fi
    i=$((i + 1))
    sleep 2
  done
  echo "ERRO: Evolution API nao respondeu HTTP 200."
  docker logs --tail 100 "$API_CONTAINER" 2>&1 || true
  exit 1
}

backup_v1
create_env

echo "Baixando imagens..."
docker pull "$PG_IMAGE"
docker pull "$REDIS_IMAGE"
docker pull "$API_IMAGE"

docker network inspect "$NETWORK" >/dev/null 2>&1 ||
  docker network create "$NETWORK" >/dev/null
docker volume inspect "$PG_VOLUME" >/dev/null 2>&1 ||
  docker volume create "$PG_VOLUME" >/dev/null
docker volume inspect "$REDIS_VOLUME" >/dev/null 2>&1 ||
  docker volume create "$REDIS_VOLUME" >/dev/null

docker rm -f "$API_CONTAINER" "$PG_CONTAINER" "$REDIS_CONTAINER" >/dev/null 2>&1 || true

docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --name "$PG_CONTAINER" \
  --restart always \
  --network "$NETWORK" \
  -e POSTGRES_USER=evolution \
  -e POSTGRES_PASSWORD="$(env_value DATABASE_PASSWORD)" \
  -e POSTGRES_DB=evolution_api \
  -v "$PG_VOLUME:/var/lib/postgresql/data" \
  "$PG_IMAGE" >/dev/null

docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --name "$REDIS_CONTAINER" \
  --restart always \
  --network "$NETWORK" \
  -v "$REDIS_VOLUME:/data" \
  "$REDIS_IMAGE" \
  redis-server --appendonly yes --requirepass "$(env_value REDIS_PASSWORD)" >/dev/null

wait_postgres_redis

remove_v1

docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --name "$API_CONTAINER" \
  --restart on-failure \
  --network "$NETWORK" \
  --env-file "$ENV_FILE" \
  -p "${API_PORT}:8080" \
  "$API_IMAGE" \
  node ./dist/src/main.js >/dev/null

rm -rf "$MANAGER_DIR.new"
mkdir -p "$MANAGER_DIR.new"
docker cp "$API_CONTAINER:/evolution/manager/dist/." "$MANAGER_DIR.new/"
curl -fsSL "$LOGO_URL" -o "$MANAGER_DIR.new/logo-header.jpg"

MAGIC="$(od -An -tx1 -N3 "$MANAGER_DIR.new/logo-header.jpg" | tr -d ' \n')"
if [ "$MAGIC" != "ffd8ff" ]; then
  echo "ERRO: logo baixado do GitHub nao e JPEG valido."
  exit 1
fi

MATCHES="$(
  grep -RIl "$OLD_LOGO_URL" "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -z "$MATCHES" ]; then
  echo "ERRO: URL original do logo nao encontrada no Manager."
  exit 1
fi
for FILE in $MATCHES; do
  sed -i "s#${OLD_LOGO_URL}#/manager/logo-header.jpg#g" "$FILE"
done

NUMBER_MATCHES="$(
  grep -RIlF 'number:d.number===""?null:d.number' "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -z "$NUMBER_MATCHES" ]; then
  echo "ERRO: rotina original do campo de numero nao encontrada no Manager."
  exit 1
fi
for FILE in $NUMBER_MATCHES; do
  sed -i \
    's@number:d\.number===""?null:d\.number@...(d.number==null||d.number===""?{}:{number:d.number.replace(/[^0-9]/g,"").length===10||d.number.replace(/[^0-9]/g,"").length===11?"55"+d.number.replace(/[^0-9]/g,""):d.number.replace(/[^0-9]/g,"")})@g' \
    "$FILE"
done

COPY_MATCHES="$(
  grep -RIlF 'const x8=e=>{navigator.clipboard.writeText(e),Z.success("Copiado para a área de transferência")};' "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -z "$COPY_MATCHES" ]; then
  echo "ERRO: rotina original do botao copiar nao encontrada no Manager."
  exit 1
fi
for FILE in $COPY_MATCHES; do
  sed -i \
    's@const x8=e=>{navigator.clipboard.writeText(e),Z.success("Copiado para a área de transferência")};@const x8=e=>{const t=()=>{const n=document.createElement("textarea");n.value=e,n.style.position="fixed",n.style.opacity="0",document.body.appendChild(n),n.focus(),n.select();const r=document.execCommand("copy");n.remove(),r?Z.success("Copiado para a área de transferência"):Z.error("Não foi possível copiar")};navigator.clipboard\&\&window.isSecureContext?navigator.clipboard.writeText(e).then(()=>Z.success("Copiado para a área de transferência")).catch(t):t()};@g' \
    "$FILE"
done
rm -rf "$MANAGER_DIR.previous"
if [ -d "$MANAGER_DIR" ]; then
  mv "$MANAGER_DIR" "$MANAGER_DIR.previous"
fi
mv "$MANAGER_DIR.new" "$MANAGER_DIR"
chmod -R a+rX "$MANAGER_DIR"

docker rm -f "$API_CONTAINER" >/dev/null
docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --name "$API_CONTAINER" \
  --restart on-failure \
  --network "$NETWORK" \
  --env-file "$ENV_FILE" \
  -p "${API_PORT}:8080" \
  -v "$MANAGER_DIR:/evolution/manager/dist:ro" \
  "$API_IMAGE" \
  node ./dist/src/main.js >/dev/null

wait_api

install_daily_cleanup

echo
echo "Evolution API v2 instalada com sucesso."
echo "Porta: $API_PORT"
echo "Manager: $(env_value SERVER_URL)/manager"
echo "Global API Key: $API_KEY"
echo "Evolution v1: removida do Docker (backup preservado)"
docker ps -a --filter name=evolution_v2_ \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
