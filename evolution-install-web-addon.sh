#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/6b8c32efebd259cbb819e594a9b4be9dde7876b7/evolution-install-web-addon.py" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' '2ce7086e95912aa8ccc362ab818f17c9a32a73a49b80bd8515dcf96176f99a8f' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/6b8c32efebd259cbb819e594a9b4be9dde7876b7/addon/evolution/index.php" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' 'f43f52fb6930cd01c433e50fea594588ef4894460a8ceaad8b8aa90f214c2e71' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/6b8c32efebd259cbb819e594a9b4be9dde7876b7/addon/evolution/native-menu.js" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' '51d519ed4b9ed848805895103c47e509f86b8906922c044429e9782c0e23b8ba' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
