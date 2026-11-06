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
printf '%s  %s\n' 'ffbae7f78182842d2f1c36f3e017f73081f23e154380122e661efa6a0215b9a4' "$STAGE/monitor-hook.cjs" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/monitor.html" -o "$STAGE/monitor.html"
printf '%s  %s\n' 'fa8375da13093daf91e533c20acb5dc96970d0c906f683b3efa1b2b7a93f617a' "$STAGE/monitor.html" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-watchdog.py" -o "$STAGE/evolution-watchdog.py"
printf '%s  %s\n' 'fdfb7c58bda1783690c98f18a1cc76377658aeeef7583483a4c35da85df5f2f1' "$STAGE/evolution-watchdog.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-enable-monitor.py" -o "$STAGE/evolution-enable-monitor.py"
printf '%s  %s\n' '43eb7ca92268ea5cd6af61c6084f34bc951bea47467e3074f391fe42a06435e6' "$STAGE/evolution-enable-monitor.py" | sha256sum -c - >/dev/null
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
