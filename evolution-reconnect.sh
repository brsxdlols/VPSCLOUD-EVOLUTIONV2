#!/bin/sh
# Explicitly renew one WhatsApp pairing. Does not delete the Evolution instance.
set -eu
INSTANCE=${1:-}
if [ -z "$INSTANCE" ] || [ "${EVOLUTION_CONFIRM_RECONNECT:-}" != "$INSTANCE" ]; then
  echo 'Esta operacao encerra a sessao WhatsApp e exige escanear novo QR.'
  echo 'Tenha o celular correto disponivel. O backup nao reativa credenciais revogadas pelo WhatsApp.'
  echo 'Uso: EVOLUTION_CONFIRM_RECONNECT=MKAUTH evolution-reconnect MKAUTH'
  exit 2
fi
BACKUP=${EVOLUTION_BACKUP_HELPER:-/usr/local/sbin/evolution-backup}
[ -x "$BACKUP" ] || { echo 'ERRO: evolution-backup nao instalado.'; exit 1; }
"$BACKUP"
# The API needs time to start after the coordinated backup.
i=0
while [ "$i" -lt 90 ]; do
  if docker exec -i -e RECONNECT_INSTANCE="$INSTANCE" evolution_v2_api node <<'NODE'
// This probe only checks HTTP readiness; it does not connect or log out.
fetch('http://127.0.0.1:8080/',{signal:AbortSignal.timeout(3000)})
 .then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1));
NODE
  then break; fi
  i=$((i+1)); sleep 2
done
[ "$i" -lt 90 ] || { echo 'ERRO: API nao voltou. Backup preservado; logout nao executado.'; exit 1; }
docker exec -i -e RECONNECT_INSTANCE="$INSTANCE" evolution_v2_api node <<'NODE'
(async()=>{
 const name=process.env.RECONNECT_INSTANCE;
 const r=await fetch('http://127.0.0.1:8080/instance/logout/'+encodeURIComponent(name),{
   method:'DELETE',headers:{apikey:process.env.AUTHENTICATION_API_KEY},signal:AbortSignal.timeout(20000)
 });
 if(!r.ok){console.error('Logout nao confirmado. HTTP',r.status);process.exit(1)}
 console.log('Sessao encerrada. Gere um novo QR no Manager ou use evolution-qr-terminal '+name);
})().catch(()=>{console.error('Falha no logout; verifique o estado antes de repetir.');process.exit(1)});
NODE
echo 'Valide texto, PDF e resposta com destinatario controlado. Confira o numero remetente.'
