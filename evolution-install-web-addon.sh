#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
STAGE=$(mktemp -d "$PROJECT/.web-addon.XXXXXX")
mkdir -p "$STAGE/addon/evolution"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cefed826a23eb65b6569811aa89df6063d9bf36b/evolution-install-web-addon.py" -o "$STAGE/evolution-install-web-addon.py"
printf '%s  %s\n' '726e8c4aa306a747909757c56bad8b74f8bf710b6e051f302703f2556c746da0' "$STAGE/evolution-install-web-addon.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cefed826a23eb65b6569811aa89df6063d9bf36b/addon/evolution/index.php" -o "$STAGE/addon/evolution/index.php"
printf '%s  %s\n' 'a68ec3194202b2d03c54e681e4d67fdf47bcd044bd8bc169c641e51b773a6b25' "$STAGE/addon/evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cefed826a23eb65b6569811aa89df6063d9bf36b/addon/evolution/native-menu.js" -o "$STAGE/addon/evolution/native-menu.js"
printf '%s  %s\n' '102d6354498a4e0a3ef1e9f6ebd947f8a8848ef9171ba75f1e0066132f545935' "$STAGE/addon/evolution/native-menu.js" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cefed826a23eb65b6569811aa89df6063d9bf36b/addon/evolution/reauth.php" -o "$STAGE/addon/evolution/reauth.php"
printf '%s  %s\n' '4396c3899330032c25c47baef19b81ac231b68658df1b7829450ab04de070a16' "$STAGE/addon/evolution/reauth.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cefed826a23eb65b6569811aa89df6063d9bf36b/addon/evolution/title-photo.php" -o "$STAGE/addon/evolution/title-photo.php"
printf '%s  %s\n' '7556b6e1d9bbf25d1737db3b15cc7986dcb35e6ae23cf6d8feeba62545063d45' "$STAGE/addon/evolution/title-photo.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cefed826a23eb65b6569811aa89df6063d9bf36b/addon/evolution/title-photo.js" -o "$STAGE/addon/evolution/title-photo.js"
printf '%s  %s\n' 'd72875dc1d7f31b1553ead9906cdedcb45ecb2eca0a5db572306816280302c06' "$STAGE/addon/evolution/title-photo.js" | sha256sum -c - >/dev/null
python3 "$STAGE/evolution-install-web-addon.py"
rm -f "$STAGE/evolution-install-web-addon.py" "$STAGE/addon/evolution/index.php" "$STAGE/addon/evolution/native-menu.js" "$STAGE/addon/evolution/reauth.php"
rm -f "$STAGE/addon/evolution/title-photo.php" "$STAGE/addon/evolution/title-photo.js"
rmdir "$STAGE/addon/evolution" "$STAGE/addon" "$STAGE"
