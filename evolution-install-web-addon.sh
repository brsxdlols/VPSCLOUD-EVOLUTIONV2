#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/a713327640a86687f7edad65a39f534437fefa3e/evolution-install-web-addon.py" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' 'e1bbce8995e5a779f3f6ff6843721adcfca335e5130c3f7cd7d7b9a66c98cef9' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/a713327640a86687f7edad65a39f534437fefa3e/addon/evolution/index.php" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' '94d91c237f438081dc3177f539403b5c24dae1f05249148428094441824d8170' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/a713327640a86687f7edad65a39f534437fefa3e/addon/evolution/native-menu.js" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' '102d6354498a4e0a3ef1e9f6ebd947f8a8848ef9171ba75f1e0066132f545935' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/a713327640a86687f7edad65a39f534437fefa3e/addon/evolution/reauth.php" -o "$STAGE/addon/evolution/reauth.php"
printf '%s  %s\n' '6b221c16c9d93198b283af3ff05da1388056810e0adefad4854a6399658a6365' "$STAGE/addon/evolution/reauth.php" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js" "$STAGE/addon/evolution/reauth.php"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
