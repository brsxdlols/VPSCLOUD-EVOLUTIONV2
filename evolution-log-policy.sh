#!/bin/sh
# Rotates only Evolution-owned host logs. Container logs stay Docker-managed.
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
command -v logrotate >/dev/null || { echo 'ERRO: instale logrotate antes de ativar a politica de logs.'; exit 1; }
B=/opt/vpscloud-evolution-v2/backups/log-policy-$(date +%Y%m%d-%H%M%S)-$$
mkdir -p "$B" /var/lib/logrotate
OLD=/etc/logrotate.d/vpscloud-evolution
if [ -f "$OLD" ]; then
  # Refuse a policy that also owns unrelated logs.
  awk '/^\// && $1 != "/var/log/vpscloud-evolution-cleanup.log" && $1 != "/var/log/vpscloud-evolution-watchdog.log" {bad=1} END{exit bad}' "$OLD" || { echo 'ERRO: logrotate anterior personalizado; revise antes de substituir.'; exit 1; }
  cp -p "$OLD" "$B/previous-logrotate"
fi
# Refuse overlapping custom policies instead of silently rotating a file twice.
for legacy in /etc/logrotate.d/mkauth-recibo-evolution /etc/logrotate-mkauth/recibo-evolution; do
  if [ -f "$legacy" ]; then
    echo "ERRO: politica Recibo anterior encontrada: $legacy. Migre-a antes de ativar a politica unificada."
    exit 1
  fi
done
CONF=/etc/logrotate-vpscloud-evolution.conf
[ ! -f "$CONF" ] || cp -p "$CONF" "$B/previous-policy"
TMP=$(mktemp /etc/logrotate-vpscloud.XXXXXX)
cat > "$TMP" <<'RULES'
/var/log/vpscloud-evolution-cleanup.log /var/log/vpscloud-evolution-watchdog.log {
    daily
    rotate 7
    maxage 7
    maxsize 5M
    missingok
    notifempty
    compress
    delaycompress
    create 0600 root root
    su root root
}
RULES
# This is dockerd's host stdout, not Docker-managed container json logs.
if ! grep -RlF '/var/log/docker.log' /etc/logrotate.d /etc/logrotate.conf >/dev/null 2>&1; then
  cat >> "$TMP" <<'RULES'
/var/log/docker.log {
    daily
    rotate 7
    maxage 7
    maxsize 10M
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    su root root
}
RULES
fi
if [ -d /opt/mk-auth/dados/Recibo_Evolution ]; then
  cat >> "$TMP" <<'RULES'
/opt/mk-auth/dados/Recibo_Evolution/log_pagamentos.txt /opt/mk-auth/dados/Recibo_Evolution/php-errors.log {
    daily
    rotate 7
    maxage 7
    maxsize 5M
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    su root root
}
RULES
fi
logrotate -d -s /var/lib/logrotate/vpscloud-evolution.status "$TMP" > "$B/validation.txt" 2>&1 || { rm -f "$TMP"; echo 'ERRO: politica de logs invalida; configuracao anterior preservada.'; exit 1; }
chmod 644 "$TMP"
mv -f "$TMP" "$CONF"
[ ! -f "$OLD" ] || mv "$OLD" "$B/disabled-daily-policy"
cat > /etc/cron.d/vpscloud-evolution-logrotate <<'CRON'
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5 * * * * root /usr/sbin/logrotate -s /var/lib/logrotate/vpscloud-evolution.status /etc/logrotate-vpscloud-evolution.conf >> /var/log/vpscloud-evolution-cleanup.log 2>&1
CRON
chmod 644 /etc/cron.d/vpscloud-evolution-logrotate
logrotate -s /var/lib/logrotate/vpscloud-evolution.status "$CONF"
echo 'Politica ativa: ate 7 rotacoes/7 dias, compressao e verificacao de tamanho a cada 5 minutos.'
