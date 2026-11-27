#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
[ -d "$PROJECT" ] || exit 1
STAGE=$(mktemp -d "$PROJECT/.recibo-download.XXXXXX")
# Retain staging on failure for supervised diagnosis; never remove backups.
mkdir -p "$STAGE/addon/Recibo_Evolution" "$PROJECT/monitor"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/evolution-install-recibo.py" -o "$STAGE/evolution-install-recibo.py"
printf '%s  %s\n' '76b334d9b5aefb67b1da68e1c037e4d0f54813fb285e3cac9a8e9fa021c740f6' "$STAGE/evolution-install-recibo.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/setup.php" -o "$STAGE/addon/setup.php"
printf '%s  %s\n' '3d47af688f8f1d580df0cb9033fb66b7946fd73a2040a4ee43b5da4cc08791f9' "$STAGE/addon/setup.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/agendar_limpeza.php" -o "$STAGE/addon/Recibo_Evolution/agendar_limpeza.php"
printf '%s  %s\n' '642f2c08dcc6ddf57e107a05e2eaf6bd77fcb1c15d7fef7df59950e07ba2f3ce' "$STAGE/addon/Recibo_Evolution/agendar_limpeza.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/api.php" -o "$STAGE/addon/Recibo_Evolution/api.php"
printf '%s  %s\n' 'adb4e7f660a720ab77c1747bfe83a1a1d2300343365a713a1d9828d6310e284a' "$STAGE/addon/Recibo_Evolution/api.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/common.php" -o "$STAGE/addon/Recibo_Evolution/common.php"
printf '%s  %s\n' '4bf3d34332e3353c92eea3566c1e5869bb90ed256a0f7b6ab4e6f484301d4653' "$STAGE/addon/Recibo_Evolution/common.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/enviozap.php" -o "$STAGE/addon/Recibo_Evolution/enviozap.php"
printf '%s  %s\n' 'bd19256f8e0c9a3a6075ab9c0ef4be8b3fcabd6511cb9a5d9408628561970a0a' "$STAGE/addon/Recibo_Evolution/enviozap.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/index.php" -o "$STAGE/addon/Recibo_Evolution/index.php"
printf '%s  %s\n' 'd5326e4aedd44857d1d307280b1286302cdd0bcef78ab5fdf1878b3372d19cc5' "$STAGE/addon/Recibo_Evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/limpar_log.php" -o "$STAGE/addon/Recibo_Evolution/limpar_log.php"
printf '%s  %s\n' '15cc4ad7e1ae6c5a2b403e25ed0f50a5d61644329de91276b9cc67aae18c2987' "$STAGE/addon/Recibo_Evolution/limpar_log.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/limpar_tabela.php" -o "$STAGE/addon/Recibo_Evolution/limpar_tabela.php"
printf '%s  %s\n' '71656928de7d3cf62fe1a0bad75d0d498124ddadd31a1ed764521207d714c108' "$STAGE/addon/Recibo_Evolution/limpar_tabela.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/manifest.json" -o "$STAGE/addon/Recibo_Evolution/manifest.json"
printf '%s  %s\n' 'f371891c303e2ef628f69ae79684d88bbb202cd2a25d1f20282486368bab6828' "$STAGE/addon/Recibo_Evolution/manifest.json" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/addon/Recibo_Evolution/obterLimpeza.php" -o "$STAGE/addon/Recibo_Evolution/obterLimpeza.php"
printf '%s  %s\n' '6a4a55842b0ec941aa5c8b067271063351f388846b33d86ae0fd86d1ee3cabd5' "$STAGE/addon/Recibo_Evolution/obterLimpeza.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/cf00a35e95b17c8fbc8d50ac68a6815a39c3ec1d/evolution-log-policy.sh" -o "$STAGE/evolution-log-policy.sh"
printf '%s  %s\n' '7b3888377a98bbd14a0d5b8718c78edba67c27acf9dab165ebbaf96910d8a9d1' "$STAGE/evolution-log-policy.sh" | sha256sum -c - >/dev/null
mv -f "$STAGE/evolution-log-policy.sh" "$PROJECT/monitor/evolution-log-policy.sh"
sh "$PROJECT/monitor/evolution-log-policy.sh"
python3 "$STAGE/evolution-install-recibo.py"
rm -f "$STAGE/evolution-install-recibo.py"
rm -f "$STAGE/addon/setup.php"
rm -f "$STAGE/addon/Recibo_Evolution/agendar_limpeza.php"
rm -f "$STAGE/addon/Recibo_Evolution/api.php"
rm -f "$STAGE/addon/Recibo_Evolution/common.php"
rm -f "$STAGE/addon/Recibo_Evolution/enviozap.php"
rm -f "$STAGE/addon/Recibo_Evolution/index.php"
rm -f "$STAGE/addon/Recibo_Evolution/limpar_log.php"
rm -f "$STAGE/addon/Recibo_Evolution/limpar_tabela.php"
rm -f "$STAGE/addon/Recibo_Evolution/manifest.json"
rm -f "$STAGE/addon/Recibo_Evolution/obterLimpeza.php"
rmdir "$STAGE/addon/Recibo_Evolution" "$STAGE/addon" "$STAGE"
