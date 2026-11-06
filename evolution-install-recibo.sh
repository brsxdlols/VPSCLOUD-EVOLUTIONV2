#!/bin/sh
set -eu
umask 077
[ "$(id -u)" = 0 ] || exit 1
PROJECT=/opt/vpscloud-evolution-v2
[ -d "$PROJECT" ] || exit 1
STAGE=$(mktemp -d "$PROJECT/.recibo-download.XXXXXX")
# Retain staging on failure for supervised diagnosis; never remove backups.
mkdir -p "$STAGE/addon/Recibo_Evolution" "$PROJECT/monitor"
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-install-recibo.py" -o "$STAGE/evolution-install-recibo.py"
printf '%s  %s\n' 'af01a6e9097976e4054aa679c20a6c729736682094283512196028d7cf4a51bd' "$STAGE/evolution-install-recibo.py" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/setup.php" -o "$STAGE/addon/setup.php"
printf '%s  %s\n' '395a4dc728b2d29ae51e053c4bba498e4db219af6731ee615d405e782aa912b9' "$STAGE/addon/setup.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/agendar_limpeza.php" -o "$STAGE/addon/Recibo_Evolution/agendar_limpeza.php"
printf '%s  %s\n' '642f2c08dcc6ddf57e107a05e2eaf6bd77fcb1c15d7fef7df59950e07ba2f3ce' "$STAGE/addon/Recibo_Evolution/agendar_limpeza.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/api.php" -o "$STAGE/addon/Recibo_Evolution/api.php"
printf '%s  %s\n' '847a199fa6e9f9fefce990fc8b8641e119174f235516e7986e3ffc5982b06ebb' "$STAGE/addon/Recibo_Evolution/api.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/common.php" -o "$STAGE/addon/Recibo_Evolution/common.php"
printf '%s  %s\n' 'cd79feab770fbef44193abf8de79d9da9f4e41b2cbef14f6dc1a476e55dac7e9' "$STAGE/addon/Recibo_Evolution/common.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/enviozap.php" -o "$STAGE/addon/Recibo_Evolution/enviozap.php"
printf '%s  %s\n' 'd8bf2222d345feda9e7c3b6d6cf364425fe1aa8535826442e0a6afa534428052' "$STAGE/addon/Recibo_Evolution/enviozap.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/index.php" -o "$STAGE/addon/Recibo_Evolution/index.php"
printf '%s  %s\n' 'a0dce0d752b7de2cbd2214f5c713c55581958c093ab330e3309a9b06f6f632b7' "$STAGE/addon/Recibo_Evolution/index.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/limpar_log.php" -o "$STAGE/addon/Recibo_Evolution/limpar_log.php"
printf '%s  %s\n' '15cc4ad7e1ae6c5a2b403e25ed0f50a5d61644329de91276b9cc67aae18c2987' "$STAGE/addon/Recibo_Evolution/limpar_log.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/limpar_tabela.php" -o "$STAGE/addon/Recibo_Evolution/limpar_tabela.php"
printf '%s  %s\n' '71656928de7d3cf62fe1a0bad75d0d498124ddadd31a1ed764521207d714c108' "$STAGE/addon/Recibo_Evolution/limpar_tabela.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/manifest.json" -o "$STAGE/addon/Recibo_Evolution/manifest.json"
printf '%s  %s\n' 'f371891c303e2ef628f69ae79684d88bbb202cd2a25d1f20282486368bab6828' "$STAGE/addon/Recibo_Evolution/manifest.json" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/addon/Recibo_Evolution/obterLimpeza.php" -o "$STAGE/addon/Recibo_Evolution/obterLimpeza.php"
printf '%s  %s\n' '6a4a55842b0ec941aa5c8b067271063351f388846b33d86ae0fd86d1ee3cabd5' "$STAGE/addon/Recibo_Evolution/obterLimpeza.php" | sha256sum -c - >/dev/null
curl -fsSL --retry 3 "https://raw.githubusercontent.com/brsxdlols/VPSCLOUD-EVOLUTIONV2/fix/safe-evolution-v237-installer/evolution-log-policy.sh" -o "$STAGE/evolution-log-policy.sh"
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
