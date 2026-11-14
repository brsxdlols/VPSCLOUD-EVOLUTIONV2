#!/bin/sh
# Installs the web panel and watchdog for the standard 7070 layout.
# Retains API image, configuration and mounts; one brief API restart on first install.
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo "ERRO: execute como root."; exit 1; }
for dep in curl sha256sum python3 docker mktemp; do command -v "$dep" >/dev/null || exit 1; done
PROJECT=/opt/vpscloud-evolution-v2
[ -d "$PROJECT" ] || { echo "ERRO: instalacao padrao ausente."; exit 1; }
STAGE=$(mktemp -d "$PROJECT/.monitor-download.XXXXXX")
trap 'rmdir "$STAGE/assets" "$STAGE" 2>/dev/null || true' EXIT
mkdir -p "$STAGE/assets"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/monitor-hook.cjs" -o "$STAGE/monitor-hook.cjs"
printf '%s  %s\n' 'b01ada707acc25fe4e7bfe3a544c7b2f4157eb9e48930536cf5ccf8babf6c239' "$STAGE/monitor-hook.cjs" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/monitor.html" -o "$STAGE/monitor.html"
printf '%s  %s\n' '188237ee4c58428aadbe5f7c1ca6f01a8c10909cb861a0c096c36edd5a5e647d' "$STAGE/monitor.html" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/evolution-watchdog.py" -o "$STAGE/evolution-watchdog.py"
printf '%s  %s\n' 'd6b016b5369eb75ff7592a9b56672b2172ca0c71bd127177470bb2570616dce5' "$STAGE/evolution-watchdog.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/evolution-enable-monitor.py" -o "$STAGE/evolution-enable-monitor.py"
printf '%s  %s\n' 'f546f8cf58227afe4bff44f138cb7128b3adcd988000d2434443da075f854c65' "$STAGE/evolution-enable-monitor.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/assets/alerts/critical.png" -o "$STAGE/assets/critical.png"
printf '%s  %s\n' '3c8762ae380641167045c53f4c3d7f1c5f4d6881a4d45822af9315e414661942' "$STAGE/assets/critical.png" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/assets/alerts/whatsapp.png" -o "$STAGE/assets/whatsapp.png"
printf '%s  %s\n' 'cd0f70546aca263fc800b699d6c711922ecba666766a3f2dbe30b0b236622458' "$STAGE/assets/whatsapp.png" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/assets/alerts/recovery.png" -o "$STAGE/assets/recovery.png"
printf '%s  %s\n' '20a8fb03853b5f9f2ed8ed6c58e065524ed34ea28f84a8c9cbab9447f79229cf' "$STAGE/assets/recovery.png" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/evolution-log-policy.sh" -o "$STAGE/evolution-log-policy.sh"
printf '%s  %s\n' '7b3888377a98bbd14a0d5b8718c78edba67c27acf9dab165ebbaf96910d8a9d1' "$STAGE/evolution-log-policy.sh" | sha256sum -c - >/dev/null
MONITOR="$PROJECT/monitor"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/45a730f5e3ffcd04da3372fa0c301acee9354152/mkauth-bridge.cjs" -o "$STAGE/mkauth-bridge.cjs"
printf '%s  %s\n' 'a0f4f9fa41aad5a46b2a8f8ba33202979e3450e88e6384a8f16540fcbe88742f' "$STAGE/mkauth-bridge.cjs" | sha256sum -c - >/dev/null
mkdir -p "$MONITOR"
chmod 700 "$MONITOR"
for file in monitor-hook.cjs mkauth-bridge.cjs; do
  if [ ! -f "$MONITOR/$file" ] || ! cmp -s "$STAGE/$file" "$MONITOR/$file"; then touch "$MONITOR/.reload-required"; fi
done
for file in monitor-hook.cjs mkauth-bridge.cjs monitor.html evolution-watchdog.py evolution-enable-monitor.py evolution-log-policy.sh; do
  chmod 600 "$STAGE/$file"
  mv -f "$STAGE/$file" "$MONITOR/$file"
done
mkdir -p "$MONITOR/assets"
chmod 700 "$MONITOR/assets"
for file in critical.png whatsapp.png recovery.png; do
  chmod 600 "$STAGE/assets/$file"
  mv -f "$STAGE/assets/$file" "$MONITOR/assets/$file"
done
rmdir "$STAGE/assets"
rmdir "$STAGE"
trap - EXIT
if [ "${1:-}" = --prepare-only ]; then echo "Auxiliares do monitor preparados."; exit 0; fi
sh "$MONITOR/evolution-log-policy.sh"
exec python3 "$MONITOR/evolution-enable-monitor.py" "$@"
