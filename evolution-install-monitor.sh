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
trap 'rmdir "$STAGE" 2>/dev/null || true' EXIT
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/monitor-hook.cjs" -o "$STAGE/monitor-hook.cjs"
printf '%s  %s\n' '5d65c3577ac2bad3b1100545a924082604cebdb9a53c1786fdd9501bdcc52c35' "$STAGE/monitor-hook.cjs" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/monitor.html" -o "$STAGE/monitor.html"
printf '%s  %s\n' 'f825af6938fa4a6f139a5efd122b3e94c4e4870f0431fec5bbdbcf98809db688' "$STAGE/monitor.html" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-watchdog.py" -o "$STAGE/evolution-watchdog.py"
printf '%s  %s\n' '19af2a0adce2fd1ae6ec6d34f3ffa0038d82e45c6d610b69a15ea01e0def6eb0' "$STAGE/evolution-watchdog.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-enable-monitor.py" -o "$STAGE/evolution-enable-monitor.py"
printf '%s  %s\n' '41131b119d4dde28a5ba9b21a91438b3aa5d22de7e0c49f249fa668c5b43ab6a' "$STAGE/evolution-enable-monitor.py" | sha256sum -c - >/dev/null
MONITOR="$PROJECT/monitor"
mkdir -p "$MONITOR"
chmod 700 "$MONITOR"
for file in monitor-hook.cjs monitor.html evolution-watchdog.py evolution-enable-monitor.py; do
  chmod 600 "$STAGE/$file"
  mv -f "$STAGE/$file" "$MONITOR/$file"
done
rmdir "$STAGE"
trap - EXIT
exec python3 "$MONITOR/evolution-enable-monitor.py"
