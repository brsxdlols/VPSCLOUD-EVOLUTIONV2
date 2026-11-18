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
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/monitor-hook.cjs" -o "$STAGE/monitor-hook.cjs"
printf '%s  %s\n' 'a4589e2d89a7287997d5c34ecbe0b179137faf06d87c387fba68ad246d806b35' "$STAGE/monitor-hook.cjs" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/monitor.html" -o "$STAGE/monitor.html"
printf '%s  %s\n' '188237ee4c58428aadbe5f7c1ca6f01a8c10909cb861a0c096c36edd5a5e647d' "$STAGE/monitor.html" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/evolution-watchdog.py" -o "$STAGE/evolution-watchdog.py"
printf '%s  %s\n' 'bb28f03be58715ee64c1763fa77534cee4aabfe285ccfa4ee2692fdb3c8904c8' "$STAGE/evolution-watchdog.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/evolution-enable-monitor.py" -o "$STAGE/evolution-enable-monitor.py"
printf '%s  %s\n' '42a151fb554a3355907e16b41dd3c3f2c1aaa192535417d1b22f59d160355943' "$STAGE/evolution-enable-monitor.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/assets/alerts/critical.png" -o "$STAGE/assets/critical.png"
printf '%s  %s\n' '3c8762ae380641167045c53f4c3d7f1c5f4d6881a4d45822af9315e414661942' "$STAGE/assets/critical.png" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/assets/alerts/whatsapp.png" -o "$STAGE/assets/whatsapp.png"
printf '%s  %s\n' 'cd0f70546aca263fc800b699d6c711922ecba666766a3f2dbe30b0b236622458' "$STAGE/assets/whatsapp.png" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/assets/alerts/recovery.png" -o "$STAGE/assets/recovery.png"
printf '%s  %s\n' '20a8fb03853b5f9f2ed8ed6c58e065524ed34ea28f84a8c9cbab9447f79229cf' "$STAGE/assets/recovery.png" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/evolution-log-policy.sh" -o "$STAGE/evolution-log-policy.sh"
printf '%s  %s\n' '7b3888377a98bbd14a0d5b8718c78edba67c27acf9dab165ebbaf96910d8a9d1' "$STAGE/evolution-log-policy.sh" | sha256sum -c - >/dev/null
MONITOR="$PROJECT/monitor"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/mkauth-bridge.cjs" -o "$STAGE/mkauth-bridge.cjs"
printf '%s  %s\n' 'a0f4f9fa41aad5a46b2a8f8ba33202979e3450e88e6384a8f16540fcbe88742f' "$STAGE/mkauth-bridge.cjs" | sha256sum -c - >/dev/null
mkdir -p "$MONITOR"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/4e5a636144f0455b387af9336e9a96cbf8142985/manual-title-media.cjs" -o "$STAGE/manual-title-media.cjs"
printf '%s  %s\n' 'a68edd43bbe5f3a5cd8253c89e213695cab1b8456c6c37624faa883997467be1' "$STAGE/manual-title-media.cjs" | sha256sum -c - >/dev/null
chmod 700 "$MONITOR"
for file in monitor-hook.cjs mkauth-bridge.cjs manual-title-media.cjs; do
  if [ ! -f "$MONITOR/$file" ] || ! cmp -s "$STAGE/$file" "$MONITOR/$file"; then touch "$MONITOR/.reload-required"; fi
done
for file in monitor-hook.cjs mkauth-bridge.cjs manual-title-media.cjs monitor.html evolution-watchdog.py evolution-enable-monitor.py evolution-log-policy.sh; do
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
