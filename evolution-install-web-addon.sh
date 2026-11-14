#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/81d84b02ff92cdaa4b184890556855e2aa78fff3/evolution-install-web-addon.py" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' 'e1bbce8995e5a779f3f6ff6843721adcfca335e5130c3f7cd7d7b9a66c98cef9' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/81d84b02ff92cdaa4b184890556855e2aa78fff3/addon/evolution/index.php" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' 'e47a4ca022bdb27a7bc5fd612da68bee83f3ac1793c42c4938b94f846730dbfe' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/81d84b02ff92cdaa4b184890556855e2aa78fff3/addon/evolution/native-menu.js" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' '102d6354498a4e0a3ef1e9f6ebd947f8a8848ef9171ba75f1e0066132f545935' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/81d84b02ff92cdaa4b184890556855e2aa78fff3/addon/evolution/reauth.php" -o "$STAGE/addon/evolution/reauth.php"
printf '%s  %s\n' 'f03899b6364f7b15fe498569d0ca2caa9eba131687006cf4d0292baec68c5abc' "$STAGE/addon/evolution/reauth.php" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js" "$STAGE/addon/evolution/reauth.php"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
