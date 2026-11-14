#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "WEB_INSTALLER_URL" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' 'WEB_INSTALLER_SHA' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "WEB_INDEX_URL" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' 'WEB_INDEX_SHA' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "WEB_MENU_URL" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' 'WEB_MENU_SHA' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
