#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/6478b1029762e24babac63b67e3db9471d86a934/evolution-install-web-addon.py" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' '18a6f2ab81bd90fb542e01a84a82c566355b86f177cfb6b04ef6a3e19ee486fc' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/6478b1029762e24babac63b67e3db9471d86a934/addon/evolution/index.php" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' '3431f3b04291543dbbd9702f01d523c6d8c2b8354888f8950da473569e55c363' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/6478b1029762e24babac63b67e3db9471d86a934/addon/evolution/native-menu.js" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' '7c402e68e934208298c8fd0c82c9b47327504a6bfe75497f2e3c4d19bed5fb24' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
