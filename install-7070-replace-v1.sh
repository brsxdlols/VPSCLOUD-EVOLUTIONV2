#!/bin/sh
set -eu
umask 077

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

API_IMAGE="evoapicloud/evolution-api@sha256:1bd8afc4a6cf48822e6cf02469aeae7bd35a12a6b616eacd1291926307f4d339"
PG_IMAGE="postgres:15-alpine"
REDIS_IMAGE="redis:7.4-alpine"
API_PORT="${EVOLUTION_PORT:-7070}"
API_KEY=""
LOGO_URL="https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/8896d7497d34795fd65ce68ce452f985c287baaa/assets/evolution-logo-header.jpg"
OLD_LOGO_URL="https://evolution-api.com/files/evo/evolution-logo-white.svg"
OLD_LOGO_URL_ALT="https://evolution-api.com/files/evo/evolution-logo.svg"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker nao encontrado."
  exit 1
fi

# Fail before any filesystem or Docker mutation in ambiguous environments.
if [ "${EVOLUTION_MODE:-apply}" = diagnose ]; then
  docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}'
  docker volume ls --format '{{.Name}}'
  exit 0
fi
for dep in curl openssl sed awk grep find od sha256sum mktemp; do
  command -v "$dep" >/dev/null 2>&1 || { echo "ERRO: dependencia ausente: $dep"; exit 1; }
done
[ "$(id -u)" = 0 ] || { echo "ERRO: execute como root."; exit 1; }
case "$API_PORT" in ''|*[!0-9]*) echo "ERRO: porta invalida."; exit 1 ;; esac
[ "$API_PORT" -ge 1 ] && [ "$API_PORT" -le 65535 ] || exit 1
if ! docker container inspect "$API_CONTAINER" >/dev/null 2>&1; then
  if docker container inspect evolution_api >/dev/null 2>&1; then
    echo "ERRO: V1 encontrada. Migracao automatica nao comprovada; V1 preservada."
    exit 1
  fi
  for volume in "$PG_VOLUME" "$REDIS_VOLUME"; do
    if docker volume inspect "$volume" >/dev/null 2>&1; then
      echo "ERRO: volume preexistente sem API. Recuperacao supervisionada necessaria: $volume"
      exit 1
    fi
  done
  # Detect nonstandard names without assuming that unknown data can be reused.
  if docker ps -a --format '{{.Image}}' | grep -qi evolution; then
    echo "ERRO: Evolution com nomes diferentes. Inventarie a instalacao antes de continuar."
    exit 1
  fi
fi
LOCK_DIR=/run/lock/vpscloud-evolution-install.lock
mkdir "$LOCK_DIR" 2>/dev/null || { echo "ERRO: instalador em execucao ou lock pendente: $LOCK_DIR"; exit 1; }
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$PROJECT_DIR" "$BACKUP_ROOT"
chmod 700 "$PROJECT_DIR" "$BACKUP_ROOT"

install_daily_cleanup() {
  # Maintenance is opt-in and confined to the installer-owned log.
  # Never fetch or execute legacy cleanup.sh from a mutable branch.
  if [ "${EVOLUTION_INSTALL_CLEANUP:-0}" != 1 ]; then
    echo "INFO: manutencao automatica nao alterada. Revise crons antigos de limpeza."
    return
  fi
  cat > /usr/local/sbin/vpscloud-evolution-cleanup <<'CLEANUP'
#!/bin/sh
set -eu
printf '[%s] Evolution: verifique espaco e rotacao de logs.\n' "$(date -Iseconds)"
df -h /
CLEANUP
  chmod 700 /usr/local/sbin/vpscloud-evolution-cleanup
  printf '25 3 * * * root /usr/local/sbin/vpscloud-evolution-cleanup >> /var/log/vpscloud-evolution-cleanup.log 2>&1\n' > /etc/cron.d/vpscloud-evolution-cleanup
  chmod 644 /etc/cron.d/vpscloud-evolution-cleanup
}
install_log_rotation() {
  mkdir -p "$PROJECT_DIR/monitor"
  POLICY_TMP=$(mktemp "$PROJECT_DIR/monitor/.log-policy.XXXXXX")
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-log-policy.sh" -o "$POLICY_TMP"
printf '%s  %s\n' '7b3888377a98bbd14a0d5b8718c78edba67c27acf9dab165ebbaf96910d8a9d1' "$POLICY_TMP" | sha256sum -c - >/dev/null
  chmod 600 "$POLICY_TMP"
  mv -f "$POLICY_TMP" "$PROJECT_DIR/monitor/evolution-log-policy.sh"
  sh "$PROJECT_DIR/monitor/evolution-log-policy.sh"
}
install_mkauth_recibo_log_rotation() { :; } # Covered by the unified policy.
install_integrations() {
  if [ "${EVOLUTION_INSTALL_MONITOR:-1}" = 1 ]; then
    /usr/local/sbin/evolution-install-monitor
  fi
  if [ -d /opt/mk-auth/admin ] && [ "${EVOLUTION_INSTALL_RECIBO:-1}" = 1 ]; then
    /usr/local/sbin/evolution-install-recibo
  fi
}
install_session_helpers() {
  HELPER_TMP=$(mktemp /usr/local/sbin/evolution-install-recibo.tmp.XXXXXX)
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-install-recibo.sh" -o "$HELPER_TMP"
printf '%s  %s\n' '4b13ae4bbd73afc2953ef0512632f1595fd7f22b18c6759e23d09800eb90de9d' "$HELPER_TMP" | sha256sum -c - >/dev/null
  chmod 700 "$HELPER_TMP"
  mv -f "$HELPER_TMP" /usr/local/sbin/evolution-install-recibo

  HELPER_TMP=$(mktemp /usr/local/sbin/evolution-install-monitor.tmp.XXXXXX)
  if curl -fsSL "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-install-monitor.sh" -o "$HELPER_TMP" &&
     printf '%s  %s\n' 'edf7f69013fa6022b1d0ee4e7c558313afb9dca1902a497f72f2259feb00dab1' "$HELPER_TMP" | sha256sum -c - >/dev/null 2>&1; then
    chmod 700 "$HELPER_TMP"
    mv -f "$HELPER_TMP" /usr/local/sbin/evolution-install-monitor
  else
    rm -f "$HELPER_TMP"
    echo "AVISO: auxiliar de monitoramento nao instalado; download ou hash invalido."
  fi
  HELPER_TMP=$(mktemp /usr/local/sbin/evolution-qr-terminal.tmp.XXXXXX)
  if curl -fsSL "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-qr-terminal.sh" -o "$HELPER_TMP" &&
     printf '%s  %s\n' '8ce1b975ea9765dd70cc92610e2c786cd6eb609bba34df264aa1206553502740' "$HELPER_TMP" | sha256sum -c - >/dev/null 2>&1; then
    chmod 700 "$HELPER_TMP"
    mv -f "$HELPER_TMP" /usr/local/sbin/evolution-qr-terminal
  else
    rm -f "$HELPER_TMP"
    echo "AVISO: auxiliar QR nao instalado; download ou hash invalido."
  fi
  HELPER_TMP=$(mktemp /usr/local/sbin/evolution-backup.tmp.XXXXXX)
  if curl -fsSL "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-backup.sh" -o "$HELPER_TMP" &&
     printf '%s  %s\n' 'e2acebc15d3dac8438f58d127e4a05acc612ce2a14017105ec7384649bccdf28' "$HELPER_TMP" | sha256sum -c - >/dev/null 2>&1; then
    chmod 700 "$HELPER_TMP"
    mv -f "$HELPER_TMP" /usr/local/sbin/evolution-backup
  else
    rm -f "$HELPER_TMP"
    echo "AVISO: auxiliar evolution-backup nao instalado; download ou hash invalido."
  fi
  HELPER_TMP=$(mktemp /usr/local/sbin/evolution-reconnect.tmp.XXXXXX)
  if curl -fsSL "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-reconnect.sh" -o "$HELPER_TMP" &&
     printf '%s  %s\n' '97f647f48daa4aabdd45f332c475df76d3cf888008c588131d4916022f9e9fae' "$HELPER_TMP" | sha256sum -c - >/dev/null 2>&1; then
    chmod 700 "$HELPER_TMP"
    mv -f "$HELPER_TMP" /usr/local/sbin/evolution-reconnect
  else
    rm -f "$HELPER_TMP"
    echo "AVISO: auxiliar evolution-reconnect nao instalado; download ou hash invalido."
  fi
}

create_env() {
  if [ -s "$ENV_FILE" ]; then
    chmod 600 "$ENV_FILE"
    return
  fi

  API_KEY="$(openssl rand -hex 32)"
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
AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=false
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
       docker exec -e REDISCLI_AUTH="$(env_value REDIS_PASSWORD)" "$REDIS_CONTAINER" redis-cli ping 2>/dev/null |
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

upgrade_existing_api() {
  CURRENT_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$API_CONTAINER")" || exit 1
  if [ "$(docker inspect --format '{{.Image}}' "$API_CONTAINER")" = "$(docker image inspect --format '{{.Id}}' "$API_IMAGE" 2>/dev/null || echo unavailable)" ]; then
    echo "OK: API ja utiliza $API_IMAGE."
    return 0
  fi
  echo "Atualizacao detectada: $CURRENT_IMAGE -> $API_IMAGE"
  [ -s "$ENV_FILE" ] || { echo "ERRO: arquivo ENV ausente; atualizacao abortada."; exit 1; }
  for item in "$PG_CONTAINER" "$REDIS_CONTAINER"; do
    docker inspect "$item" >/dev/null 2>&1 || { echo "ERRO: dependencia $item ausente."; exit 1; }
    [ "$(docker inspect --format '{{.State.Running}}' "$item")" = true ] || { echo "ERRO: $item nao esta ativo."; exit 1; }
  done
  [ "$(docker inspect --format '{{.State.Running}}' "$API_CONTAINER")" = true ] || { echo "ERRO: API nao esta ativa."; exit 1; }
  docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "$PG_CONTAINER" | grep -qx '/var/lib/postgresql/data' || { echo "ERRO: volume persistente PostgreSQL nao encontrado."; exit 1; }
  docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "$REDIS_CONTAINER" | grep -qx '/data' || { echo "ERRO: volume persistente Redis nao encontrado."; exit 1; }
  [ "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$API_CONTAINER")" = "$NETWORK" ] || { echo "ERRO: rede da API diferente do padrao; atualizacao manual necessaria."; exit 1; }
  [ "$(docker inspect --format '{{.HostConfig.RestartPolicy.Name}}' "$API_CONTAINER")" != "" ] || exit 1
  [ -n "$(env_value AUTHENTICATION_API_KEY)" ] || { echo "ERRO: chave API nao encontrada."; exit 1; }
  [ -n "$(env_value DATABASE_PASSWORD)" ] || { echo "ERRO: credencial PostgreSQL nao encontrada."; exit 1; }
  [ -n "$(env_value REDIS_PASSWORD)" ] || { echo "ERRO: credencial Redis nao encontrada."; exit 1; }
  echo "Verificando Docker e capacidade de backup..."
  docker info >/dev/null 2>&1 || { echo "ERRO: daemon Docker indisponivel."; exit 1; }
  docker exec "$PG_CONTAINER" pg_isready -U evolution -d evolution_api >/dev/null 2>&1 || { echo "ERRO: PostgreSQL nao esta pronto."; exit 1; }
  STAMP_UPGRADE="$(date +%Y%m%d-%H%M%S)"
  UPGRADE_DIR="$PROJECT_DIR/backups/api-upgrade-$STAMP_UPGRADE"
  mkdir -p "$UPGRADE_DIR"
  chmod 700 "$UPGRADE_DIR"
  cp -p "$ENV_FILE" "$UPGRADE_DIR/evolution-v2.env"
  docker inspect "$API_CONTAINER" > "$UPGRADE_DIR/api-container-inspect.json"
  docker inspect "$PG_CONTAINER" > "$UPGRADE_DIR/postgres-container-inspect.json"
  docker inspect "$REDIS_CONTAINER" > "$UPGRADE_DIR/redis-container-inspect.json"
  echo "Gerando backup PostgreSQL..."
  if ! docker exec "$PG_CONTAINER" pg_dump -U evolution -d evolution_api -Fc > "$UPGRADE_DIR/postgres.dump"; then
    echo "ERRO: pg_dump falhou; atualizacao abortada."
    exit 1
  fi
  [ -s "$UPGRADE_DIR/postgres.dump" ] || { echo "ERRO: backup vazio; abortando."; exit 1; }
  echo "AVISO: este dump preparatorio nao inclui autenticacao Redis. Use evolution-backup antes de qualquer troca."
  # Avoid Docker 18.09 stdin streaming failures (connection reset by peer).
  # Copy archive into PostgreSQL container, validate locally, then remove copy.
  PG_BACKUP_TMP="/tmp/evolution-upgrade-$STAMP_UPGRADE.dump"
  if ! docker cp "$UPGRADE_DIR/postgres.dump" "$PG_CONTAINER:$PG_BACKUP_TMP"; then
    echo "ERRO: nao foi possivel copiar backup para validacao; atualizacao abortada."
    exit 1
  fi
  # Docker 18.09 occasionally resets the socket on exec. Retry validation
  # without treating a failed attempt as a successful archive verification.
  VALIDATED=0
  ATTEMPT=1
  while [ "$ATTEMPT" -le 3 ]; do
    if docker exec "$PG_CONTAINER" pg_restore -l "$PG_BACKUP_TMP" > "$UPGRADE_DIR/postgres-catalog.txt"; then
      VALIDATED=1
      break
    fi
    echo "AVISO: falha na validacao do backup (tentativa $ATTEMPT/3)."
    ATTEMPT=$((ATTEMPT + 1))
    sleep 2
  done
  docker exec "$PG_CONTAINER" rm -f "$PG_BACKUP_TMP" || true
  if [ "$VALIDATED" -ne 1 ]; then
    echo "ERRO: nao foi possivel validar o catalogo do backup; atualizacao abortada."
    exit 1
  fi
  [ -s "$UPGRADE_DIR/postgres-catalog.txt" ] || { echo "ERRO: catalogo do backup vazio."; exit 1; }
  chmod 600 "$UPGRADE_DIR"/*
  echo "Dump preparatorio gerado e catalogo validado: $UPGRADE_DIR"
  echo "Baixando $API_IMAGE..."
  docker pull "$API_IMAGE" || { echo "ERRO: falha ao baixar imagem; API atual preservada."; exit 1; }
  echo "ATENCAO: atualizacoes podem alterar o esquema do banco. Uma falha exige recuperacao supervisionada."
  if [ "${EVOLUTION_ALLOW_API_UPGRADE:-0}" != "1" ]; then
    echo "Atualizacao nao executada. Leia docs/OPERACAO-SEGURA.md; troca automatica permanece bloqueada."
    return 0
  fi
  echo "ERRO: substituicao automatica bloqueada ate validacao de compatibilidade e plano de recuperacao do banco."
  echo "API atual preservada. Backup: $UPGRADE_DIR"
  return 1
}

patch_chat_button() {
  CHAT_BUNDLE="$1"
  # Execute only the patcher, never the API entrypoint. The bind mount is staging.
  docker run --rm -i --network none --entrypoint node \
    -v "$(dirname "$CHAT_BUNDLE"):/patch" "$API_IMAGE" - <<'MANAGER_PATCH'
const fs=require("fs");const dir="/patch";const files=fs.readdirSync(dir).filter(x=>/^index-.*\.js$/.test(x));
if(files.length!==1)throw Error("Manager bundle ambiguo");
const p=dir+"/"+files[0];let s=fs.readFileSync(p,"utf8");
const needle='className:"w-full justify-start gap-2 px-2 text-left",children:';
if(s.includes("VPSCLOUD_NEW_CHAT_V1"))process.exit(0);
const patch='className:"w-full justify-start gap-2 px-2 text-left",onClick:()=>{const x=window.prompt("Numero do destinatario com DDI e DDD");if(x===null)return;let y=x.replace(/[^0-9]/g,"");if(y.length===10||y.length===11)y="55"+y;if(y.length<12||y.length>15){window.alert("Informe um numero com DDI e DDD");return}m(y+"@s.whatsapp.net")},children:';
if(s.includes(patch))process.exit(0);
if(s.split(needle).length!==2)throw Error("Manager desconhecido: botao Chat");
// Resolve the existing navigation callback in this exact Chat component.
const at=s.indexOf(needle);const prefix=s.slice(Math.max(0,at-2000),at);
const nav=prefix.match(/const ([A-Za-z_$][\w$]*)=([A-Za-z_$][\w$]*)=>\{[A-Za-z_$][\w$]*\(`\/manager\/instance\/\$\{[A-Za-z_$][\w$]*\}\/chat\/\$\{\2\}`\)\};return/);
if(!nav)throw Error("Componente Chat nao reconhecido");
s=s.replace(needle,patch.replace("m(y+",nav[1]+"(y+"))+"\n/* VPSCLOUD_NEW_CHAT_V1 */\n";
require("child_process").execFileSync(process.execPath,["--input-type=module","--check"],{input:s,stdio:["pipe","ignore","pipe"]});
fs.writeFileSync(p+".tmp",s);fs.renameSync(p+".tmp",p);
MANAGER_PATCH
}

patch_existing_v2() {
  echo "Evolution V2 existente detectada. Entrando em modo PATCH seguro."
  [ -s "$ENV_FILE" ] || { echo "ERRO: ENV ausente; nenhuma alteracao aplicada."; exit 1; }
  [ "$(docker inspect --format '{{.State.Running}}' "$API_CONTAINER")" = true ] || { echo "ERRO: API parada; recuperacao manual necessaria."; exit 1; }
  [ "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$API_CONTAINER")" = "$NETWORK" ] || { echo "ERRO: topologia nao padrao; PATCH abortado."; exit 1; }
  for dependency in "$PG_CONTAINER" "$REDIS_CONTAINER"; do
    [ "$(docker inspect --format '{{.State.Running}}' "$dependency")" = true ] || { echo "ERRO: dependencia parada ou ausente."; exit 1; }
  done
  docker update --restart=always "$API_CONTAINER" "$PG_CONTAINER" "$REDIS_CONTAINER" >/dev/null
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
  if ! grep -qF '.length===10' "$JS" || ! grep -qF '.length===11' "$JS" || { ! grep -qF '"55"+h.number.replace' "$JS" && ! grep -qF '"55"+d.number.replace' "$JS"; }; then
    if grep -qF 'number:h.number===""?null:h.number' "$JS"; then
      sed -i 's@number:h\.number===""?null:h\.number@...(h.number==null||h.number===""?{}:{number:h.number.replace(/[^0-9]/g,"").length===10||h.number.replace(/[^0-9]/g,"").length===11?"55"+h.number.replace(/[^0-9]/g,""):h.number.replace(/[^0-9]/g,"")})@g' "$JS"
      CHANGED=1; echo "PATCH: normalizacao 10/11 digitos + DDI 55 aplicada."
    elif grep -qF 'number:d.number===""?null:d.number' "$JS"; then
      sed -i 's@number:d\.number===""?null:d\.number@...(d.number==null||d.number===""?{}:{number:d.number.replace(/[^0-9]/g,"").length===10||d.number.replace(/[^0-9]/g,"").length===11?"55"+d.number.replace(/[^0-9]/g,""):d.number.replace(/[^0-9]/g,"")})@g' "$JS"
      CHANGED=1; echo "PATCH: normalizacao 10/11 digitos + DDI 55 aplicada (d.number)."
    else echo "ERRO: rotina de numero nao reconhecida."; rm -rf "$MANAGER_DIR"; cp -a "$PATCH_BACKUP" "$MANAGER_DIR"; exit 1; fi
  else echo "OK: normalizacao 10/11 digitos + DDI 55 ja aplicada."; fi
  if ! grep -q 'document.execCommand("copy")' "$JS"; then
    if grep -qF 'const U5=e=>{navigator.clipboard.writeText(e),me.success("Copiado para a área de transferência")};' "$JS"; then
      sed -i 's@const U5=e=>{navigator.clipboard.writeText(e),me.success("Copiado para a área de transferência")};@const U5=e=>{const t=()=>{const n=document.createElement("textarea");n.value=e,n.style.position="fixed",n.style.opacity="0",document.body.appendChild(n),n.focus(),n.select();const r=document.execCommand("copy");n.remove(),r?me.success("Copiado para a área de transferência"):me.error("Não foi possível copiar")};navigator.clipboard\&\&window.isSecureContext?navigator.clipboard.writeText(e).then(()=>me.success("Copiado para a área de transferência")).catch(t):t()};@g' "$JS"
      CHANGED=1; echo "PATCH: clipboard seguro aplicado."
    else echo "ERRO: rotina de clipboard nao reconhecida."; rm -rf "$MANAGER_DIR"; cp -a "$PATCH_BACKUP" "$MANAGER_DIR"; exit 1; fi
  else echo "OK: clipboard seguro ja aplicado."; fi
  if [ ! -s "$MANAGER_DIR/logo-header.jpg" ]; then curl -fsSL "$LOGO_URL" -o "$MANAGER_DIR/logo-header.jpg"; CHANGED=1; echo "PATCH: logo personalizada instalada."; fi
  LOGO_FILES="$(grep -RIlE 'https://evolution-api\.com/files/evo/evolution-logo(-white)?\\.svg' "$MANAGER_DIR" 2>/dev/null || true)"
  if [ -n "$LOGO_FILES" ]; then
    for FILE in $LOGO_FILES; do sed -i -e "s#${OLD_LOGO_URL}#/manager/logo-header.jpg#g" -e "s#${OLD_LOGO_URL_ALT}#/manager/logo-header.jpg#g" "$FILE"; done
    CHANGED=1; echo "PATCH: referencias da logo personalizadas."
  else echo "OK: referencias antigas da logo nao encontradas."; fi
  if ! patch_chat_button "$JS"; then
    cp -a "$PATCH_BACKUP/." "$MANAGER_DIR/"
    echo "ERRO: patch de conversa abortado; Manager restaurado."; exit 1
  fi
  chmod -R a+rX "$MANAGER_DIR"
  if ! grep -qF '.length===10' "$JS" || ! grep -qF '.length===11' "$JS" || { ! grep -qF '"55"+h.number.replace' "$JS" && ! grep -qF '"55"+d.number.replace' "$JS"; } || ! grep -q 'navigator.clipboard' "$JS" || ! grep -q 'document.execCommand("copy")' "$JS" || ! grep -q '/manager/logo-header.jpg' "$JS"; then
    echo "ERRO: validacao final falhou. Restaurando backup."; rm -rf "$MANAGER_DIR"; cp -a "$PATCH_BACKUP" "$MANAGER_DIR"; exit 1
  fi
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/" || true)"
  [ "$CODE" = "200" ] || { echo "ERRO: API existente nao respondeu HTTP 200 (retorno: $CODE)."; exit 1; }
  if [ "$CHANGED" -eq 0 ]; then echo "Evolution V2 ja estava totalmente corrigida. Nenhuma alteracao necessaria."; else echo "PATCH concluido e validado com sucesso."; fi
  install_log_rotation
  install_mkauth_recibo_log_rotation
  install_session_helpers
  install_integrations
  echo "API: HTTP $CODE"
  install_daily_cleanup
  upgrade_existing_api
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

# Extract files from a stopped container; no WhatsApp socket is started here.
EXTRACT_CONTAINER="evolution_v2_manager_extract_$$"
docker create --name "$EXTRACT_CONTAINER" "$API_IMAGE" >/dev/null
if [ -e "$MANAGER_DIR.new" ]; then
  echo "ERRO: staging anterior encontrado; preserve e revise $MANAGER_DIR.new"
  docker rm "$EXTRACT_CONTAINER" >/dev/null
  exit 1
fi
mkdir -p "$MANAGER_DIR.new"
if ! docker cp "$EXTRACT_CONTAINER:/evolution/manager/dist/." "$MANAGER_DIR.new/"; then
  docker rm "$EXTRACT_CONTAINER" >/dev/null
  exit 1
fi
docker rm "$EXTRACT_CONTAINER" >/dev/null
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
patch_chat_button "$(find "$MANAGER_DIR.new/assets" -maxdepth 1 -name 'index-*.js' | head -1)"
if [ -d "$MANAGER_DIR" ]; then
  mv "$MANAGER_DIR" "$MANAGER_DIR.previous.$(date +%Y%m%d-%H%M%S)"
fi
mv "$MANAGER_DIR.new" "$MANAGER_DIR"
chmod -R a+rX "$MANAGER_DIR"

docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --name "$API_CONTAINER" \
  --restart always \
  --network "$NETWORK" \
  --env-file "$ENV_FILE" \
  -p "${API_PORT}:8080" \
  -v "$MANAGER_DIR:/evolution/manager/dist:ro" \
  "$API_IMAGE" >/dev/null

wait_api

# No legacy deployment is retired automatically.
echo "INFO: nenhuma instalacao V1 foi removida."

install_daily_cleanup
install_log_rotation
install_mkauth_recibo_log_rotation
install_session_helpers
install_integrations

echo
echo "Evolution API v2 instalada com sucesso."
echo "Porta: $API_PORT"
echo "Manager: $(env_value SERVER_URL)/manager"
echo "Global API Key: consulte AUTHENTICATION_API_KEY em $ENV_FILE (arquivo protegido)"
echo "Evolution v1: preservada; migracao exige procedimento separado."
docker ps -a --filter name=evolution_v2_ \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

