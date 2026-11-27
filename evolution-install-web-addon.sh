#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/ba59755e2fd52d42e3e9ece00b62d2090971892d/evolution-install-web-addon.py" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' '16a826ffcf8827ae9cc34322f624b6c83b693184ac2b0dc215f496b42c7f263f' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/ba59755e2fd52d42e3e9ece00b62d2090971892d/addon/evolution/index.php" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' '557ce880b49947babdb2fffdf2baf7c9d9e7239f884dfb74955358d71e82bfde' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/ba59755e2fd52d42e3e9ece00b62d2090971892d/addon/evolution/native-menu.js" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' '5b09bb25a38f5aa96e62fa0f6d3142fc2fb466e8c827def5fea8f832d7c2d91c' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/ba59755e2fd52d42e3e9ece00b62d2090971892d/addon/evolution/reauth.php" -o "$STAGE/addon/evolution/reauth.php"
printf '%s  %s\n' '4396c3899330032c25c47baef19b81ac231b68658df1b7829450ab04de070a16' "$STAGE/addon/evolution/reauth.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/ba59755e2fd52d42e3e9ece00b62d2090971892d/addon/evolution/title-photo.php" -o "$STAGE/addon/evolution/title-photo.php"
printf '%s  %s\n' '4598d431fb916341477664d2d4d7d24e5d108bc1de1c89b9c2b16331fab67366' "$STAGE/addon/evolution/title-photo.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/ba59755e2fd52d42e3e9ece00b62d2090971892d/addon/evolution/title-photo.js" -o "$STAGE/addon/evolution/title-photo.js"
printf '%s  %s\n' '5082075764404ccc1bb504f8592b6531f1e1ee4b2835973120d7e0a9f5b300df' "$STAGE/addon/evolution/title-photo.js" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js" "$STAGE/addon/evolution/reauth.php"
rm -f "$STAGE/addon/evolution/title-photo.php" "$STAGE/addon/evolution/title-photo.js"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
