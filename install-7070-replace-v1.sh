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

API_IMAGE="evoapicloud/evolution-api:v2.3.7"
PG_IMAGE="postgres:15-alpine"
REDIS_IMAGE="redis:7.4-alpine"
API_PORT="${EVOLUTION_PORT:-7070}"
API_KEY=""
LOGO_URL="https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/main/assets/evolution-logo-header.jpg"
OLD_LOGO_URL="https://evolution-api.com/files/evo/evolution-logo-white.svg"
OLD_LOGO_URL_ALT="https://evolution-api.com/files/evo/evolution-logo.svg"
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
install_log_rotation() {
  # Docker containers already use json-file with max-size=10m and max-file=3.
  # Rotate only the installer-owned host log; never truncate Docker-managed files.
  cat > /etc/logrotate.d/vpscloud-evolution <<'EOF'
/var/log/vpscloud-evolution-cleanup.log {
    daily
    rotate 3
    maxsize 10M
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    su root root
}
EOF
  chmod 644 /etc/logrotate.d/vpscloud-evolution
  if command -v logrotate >/dev/null 2>&1; then
    if logrotate -d /etc/logrotate.d/vpscloud-evolution >/dev/null 2>&1; then
      echo "OK: logrotate diario configurado para o log de limpeza."
    else
      echo "AVISO: logrotate instalado, mas a configuracao precisa ser revisada."
    fi
  else
    echo "AVISO: logrotate nao instalado; instale o pacote logrotate para ativar a rotacao do log de limpeza."
  fi
}
install_mkauth_recibo_log_rotation() {
  # Optional MK-AUTH integration. Never change payment data or addon code.
  if [ "${MKAUTH_RECIBO_LOGROTATE:-0}" != "1" ]; then
    echo "INFO: rotacao de logs do MK-AUTH opcional (MKAUTH_RECIBO_LOGROTATE=1)."
    return
  fi
  RECIBO_LOG="/opt/mk-auth/dados/Recibo_Evolution/log_pagamentos.txt"
  if [ ! -f "$RECIBO_LOG" ]; then
    echo "INFO: log do Recibo_Evolution nao encontrado; configuracao ignorada."
    return
  fi
  if ! command -v logrotate >/dev/null 2>&1 || [ ! -x /usr/sbin/logrotate ]; then
    echo "AVISO: logrotate nao instalado; configuracao do Recibo_Evolution ignorada."
    return
  fi
  if [ -e /etc/logrotate.d/mkauth-recibo-evolution ]; then
    echo "AVISO: configuracao anterior em /etc/logrotate.d/mkauth-recibo-evolution; ajuste manualmente para evitar duplicidade."
    return
  fi
  mkdir -p /etc/logrotate-mkauth
  RECIBO_CONF="/etc/logrotate-mkauth/recibo-evolution"
  RECIBO_CRON="/etc/cron.d/mkauth-recibo-evolution-logs"
  if [ -e "$RECIBO_CONF" ] || [ -e "$RECIBO_CRON" ]; then
    echo "INFO: rotina de logs Recibo_Evolution ja configurada; preservando configuracao existente."
    return
  fi
  cat > "$RECIBO_CONF" <<'EOF'
/opt/mk-auth/dados/Recibo_Evolution/log_pagamentos.txt {
    hourly
    maxsize 10M
    rotate 72
    maxage 3
    missingok
    notifempty
    compress
    copytruncate
    su www-data www-data
}
EOF
  chmod 644 "$RECIBO_CONF"
  if ! logrotate -d -s /var/lib/logrotate/mkauth-recibo-evolution.status "$RECIBO_CONF" >/dev/null 2>&1; then
    rm -f "$RECIBO_CONF"
    echo "AVISO: validacao do logrotate do Recibo_Evolution falhou; cron nao instalado."
    return
  fi
  cat > "$RECIBO_CRON" <<'EOF'
7 * * * * root /usr/sbin/logrotate -s /var/lib/logrotate/mkauth-recibo-evolution.status /etc/logrotate-mkauth/recibo-evolution
EOF
  chmod 644 "$RECIBO_CRON"
  echo "OK: rotacao horaria opcional do Recibo_Evolution configurada (retencao ate 3 dias nas rotacoes)."
}
remove_v1() {
  V1_IMAGE=""
  if docker container inspect evolution_api >/dev/null 2>&1; then
    V1_IMAGE="$(docker inspect --format '{{.Config.Image}}' evolution_api)"
    echo "Parando e removendo completamente a Evolution v1..."
    docker rm -f evolution_api >/dev/null
  fi
  # Keep the legacy image available for rollback.
  echo "Container Evolution v1 removido; imagem e backups preservados."
}
create_env() {
  if [ -s "$ENV_FILE" ]; then
    chmod 600 "$ENV_FILE"
    return
  fi

  API_KEY="123456"
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
DATABASE_SAVE_MESSAGE_UPDATE=false
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
  echo "ERRO: Evolution API nao respondeu HTTP 200. Consulte logs localmente, pois podem conter dados sensiveis."
  exit 1
}

patch_existing_v2() {
  echo "Evolution V2 existente detectada. Entrando em modo PATCH seguro."
  [ -d "$MANAGER_DIR" ] || { echo "ERRO: Manager nao encontrado em $MANAGER_DIR."; exit 1; }
  JS="$(find "$MANAGER_DIR/assets" -maxdepth 1 -type f -name 'index-*.js' | head -n 1)"
  [ -n "$JS" ] && [ -f "$JS" ] || { echo "ERRO: bundle JS do Manager nao encontrado."; exit 1; }
  STAMP="$(date +%Y%m%d-%H%M%S)"
  PATCH_BACKUP="$PROJECT_DIR/backups/manager-before-patch-$STAMP"
  mkdir -p "$PROJECT_DIR/backups"; cp -a "$MANAGER_DIR" "$PATCH_BACKUP"
  echo "Backup do Manager: $PATCH_BACKUP"
  CHANGED=0
  if grep -q 'placeholder:"16999998888"' "$JS"; then
    echo "OK: placeholder sem DDI ja aplicado."
  elif grep -q 'placeholder:"5511999999999"' "$JS"; then
    sed -i 's/placeholder:"5511999999999"/placeholder:"16999998888"/g' "$JS"; CHANGED=1
    echo "PATCH: placeholder sem DDI aplicado."
  else
    echo "INFO: Manager sem placeholder no campo de numero; nenhuma alteracao necessaria."
  fi
  if ! grep -q 'length===10' "$JS" || ! grep -q 'length===11' "$JS" || ! grep -q '"55"+h.number.replace' "$JS"; then
    if grep -qF 'number:h.number===""?null:h.number' "$JS"; then
      sed -i 's@number:h\\.number===""?null:h\\.number@...(h.number==null||h.number===""?{}:{number:h.number.replace(/[^0-9]/g,"").length===10||h.number.replace(/[^0-9]/g,"").length===11?"55"+h.number.replace(/[^0-9]/g,""):h.number.replace(/[^0-9]/g,"")})@g' "$JS"
      CHANGED=1; echo "PATCH: normalizacao 10/11 digitos + DDI 55 aplicada."
    else echo "ERRO: rotina de numero nao reconhecida."; rm -rf "$MANAGER_DIR"; cp -a "$PATCH_BACKUP" "$MANAGER_DIR"; exit 1; fi
  else echo "OK: normalizacao 10/11 digitos + DDI 55 ja aplicada."; fi
  if ! grep -q 'document.execCommand("copy")' "$JS"; then
    if grep -qF 'const U5=e=>{navigator.clipboard.writeText(e),me.success("Copiado para a área de transferência")};' "$JS"; then
      sed -i 's@const U5=e=>{navigator.clipboard.writeText(e),me.success("Copiado para a área de transferência")};@const U5=e=>{const t=()=>{const n=document.createElement("textarea");n.value=e,n.style.position="fixed",n.style.opacity="0",document.body.appendChild(n),n.focus(),n.select();const r=document.execCommand("copy");n.remove(),r?me.success("Copiado para a área de transferência"):me.error("Não foi possível copiar")};navigator.clipboard\\&\\&window.isSecureContext?navigator.clipboard.writeText(e).then(()=>me.success("Copiado para a área de transferência")).catch(t):t()};@g' "$JS"
      CHANGED=1; echo "PATCH: clipboard seguro aplicado."
    else echo "ERRO: rotina de clipboard nao reconhecida."; rm -rf "$MANAGER_DIR"; cp -a "$PATCH_BACKUP" "$MANAGER_DIR"; exit 1; fi
  else echo "OK: clipboard seguro ja aplicado."; fi
  if [ ! -s "$MANAGER_DIR/logo-header.jpg" ]; then curl -fsSL "$LOGO_URL" -o "$MANAGER_DIR/logo-header.jpg"; CHANGED=1; echo "PATCH: logo personalizada instalada."; fi
  LOGO_FILES="$(grep -RIlE 'https://evolution-api\\.com/files/evo/evolution-logo(-white)?\\.svg' "$MANAGER_DIR" 2>/dev/null || true)"
  if [ -n "$LOGO_FILES" ]; then
    for FILE in $LOGO_FILES; do sed -i -e "s#${OLD_LOGO_URL}#/manager/logo-header.jpg#g" -e "s#${OLD_LOGO_URL_ALT}#/manager/logo-header.jpg#g" "$FILE"; done
    CHANGED=1; echo "PATCH: referencias da logo personalizadas."
  else echo "OK: referencias antigas da logo nao encontradas."; fi
  chmod -R a+rX "$MANAGER_DIR"
  if ! grep -q 'length===10' "$JS" || ! grep -q 'length===11' "$JS" || ! grep -q '"55"+h.number.replace' "$JS" || ! grep -q 'navigator.clipboard' "$JS" || ! grep -q 'document.execCommand("copy")' "$JS" || ! grep -q '/manager/logo-header.jpg' "$JS"; then
    echo "ERRO: validacao final falhou. Restaurando backup."; rm -rf "$MANAGER_DIR"; cp -a "$PATCH_BACKUP" "$MANAGER_DIR"; exit 1
  fi
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/" || true)"
  [ "$CODE" = "200" ] || { echo "ERRO: API existente nao respondeu HTTP 200 (retorno: $CODE)."; exit 1; }
  if [ "$CHANGED" -eq 0 ]; then echo "Evolution V2 ja estava totalmente corrigida. Nenhuma alteracao necessaria."; else echo "PATCH concluido e validado com sucesso."; fi
  install_log_rotation
  install_mkauth_recibo_log_rotation
  echo "API: HTTP $CODE"
  exit 0
}
# Instalacao nova/migracao V1; se V2 ja existir, aplica somente patches seguros.
if docker container inspect "$API_CONTAINER" >/dev/null 2>&1; then patch_existing_v2; fi
for existing in "$PG_CONTAINER" "$REDIS_CONTAINER"; do
  if docker container inspect "$existing" >/dev/null 2>&1; then
    echo "ERRO: encontrado $existing sem o container $API_CONTAINER."
    echo "Estado parcial detectado; instalacao automatica abortada para proteger os dados."
    exit 1
  fi
done

create_env
API_KEY="$(env_value AUTHENTICATION_API_KEY)"
if [ -z "$API_KEY" ]; then
  echo "ERRO: AUTHENTICATION_API_KEY ausente no arquivo de configuracao."
  exit 1
fi

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
  grep -RIlE 'https://evolution-api\.com/files/evo/evolution-logo(-white)?\.svg' "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -z "$MATCHES" ]; then
  echo "ERRO: URL original do logo nao encontrada no Manager."
  exit 1
fi
for FILE in $MATCHES; do
  sed -i -e "s#${OLD_LOGO_URL}#/manager/logo-header.jpg#g" -e "s#${OLD_LOGO_URL_ALT}#/manager/logo-header.jpg#g" "$FILE"
done

NUMBER_MATCHES="$(
  grep -RIlF 'number:h.number===""?null:h.number' "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -z "$NUMBER_MATCHES" ]; then
  echo "ERRO: rotina original do campo de numero nao encontrada no Manager."
  exit 1
fi
for FILE in $NUMBER_MATCHES; do
  sed -i \
    's@number:h\.number===""?null:h\.number@...(h.number==null||h.number===""?{}:{number:h.number.replace(/[^0-9]/g,"").length===10||h.number.replace(/[^0-9]/g,"").length===11?"55"+h.number.replace(/[^0-9]/g,""):h.number.replace(/[^0-9]/g,"")})@g' \
    "$FILE"
done

PLACEHOLDER_MATCHES="$(
  grep -RIlF 'placeholder:"5511999999999"' "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -n "$PLACEHOLDER_MATCHES" ]; then
  for FILE in $PLACEHOLDER_MATCHES; do
    sed -i 's/placeholder:"5511999999999"/placeholder:"16999998888"/g' "$FILE"
  done
  echo "PATCH: placeholder do numero atualizado."
else
  echo "INFO: esta versao do Manager nao possui placeholder no campo de numero; seguindo sem altera-lo."
fi

COPY_MATCHES="$(
  grep -RIlF 'const U5=e=>{navigator.clipboard.writeText(e),me.success("Copiado para a área de transferência")};' "$MANAGER_DIR.new" 2>/dev/null || true
)"
if [ -z "$COPY_MATCHES" ]; then
  echo "ERRO: rotina original do botao copiar nao encontrada no Manager."
  exit 1
fi
for FILE in $COPY_MATCHES; do
  sed -i \
    's@const U5=e=>{navigator.clipboard.writeText(e),me.success("Copiado para a área de transferência")};@const U5=e=>{const t=()=>{const n=document.createElement("textarea");n.value=e,n.style.position="fixed",n.style.opacity="0",document.body.appendChild(n),n.focus(),n.select();const r=document.execCommand("copy");n.remove(),r?me.success("Copiado para a área de transferência"):me.error("Não foi possível copiar")};navigator.clipboard\&\&window.isSecureContext?navigator.clipboard.writeText(e).then(()=>me.success("Copiado para a área de transferência")).catch(t):t()};@g' \
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

# Only retire the legacy v1 container after v2 is healthy.
remove_v1

install_daily_cleanup
install_log_rotation
install_mkauth_recibo_log_rotation

echo
echo "Evolution API v2 instalada com sucesso."
echo "Porta: $API_PORT"
echo "Manager: $(env_value SERVER_URL)/manager"
echo "Global API Key: consulte AUTHENTICATION_API_KEY em $ENV_FILE (arquivo protegido)"
echo "Evolution v1: container antigo removido apos validacao; imagem e backups preservados"
docker ps -a --filter name=evolution_v2_ \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
