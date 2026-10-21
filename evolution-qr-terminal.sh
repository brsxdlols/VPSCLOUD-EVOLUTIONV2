#!/bin/sh
# Mostra o QR Code da instancia existente pelo endpoint local da Evolution.
# Nao altera sessoes, containers ou banco de dados.
set -eu
CONTAINER="${EVOLUTION_API_CONTAINER:-evolution_v2_api}"
INSTANCE="${1:-}"
if [ -z "$INSTANCE" ]; then
  printf 'Uso: %s NOME_DA_INSTANCIA\nExemplo: %s MKAUTH\n' "$0" "$0" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker nao encontrado." >&2
  exit 1
fi
docker exec -i -e "QR_INSTANCE=$INSTANCE" "$CONTAINER" node <<'NODE'
const axios = require("axios");
const QR = require("qrcode-terminal");
const name = process.env.QR_INSTANCE;
const apikey = process.env.AUTHENTICATION_API_KEY;
if (!apikey) {
  console.error("ERRO: AUTHENTICATION_API_KEY ausente.");
  process.exit(1);
}
(async () => {
  try {
    const url = "http://127.0.0.1:8080/instance/connect/" + encodeURIComponent(name);
    const response = await axios.get(url, {
      headers: { apikey },
      timeout: 15000
    });
    const data = response.data || {};
    const code = data.code || (data.qrcode && data.qrcode.code);
    if (!code || typeof code !== "string") {
      console.error("QR textual nao disponivel. A instancia pode estar conectada.");
      console.error("Campos recebidos:", Object.keys(data).join(", "));
      process.exitCode = 1;
      return;
    }
    console.log("===== QR CODE: " + name + " =====");
    QR.generate(code, { small: true });
    console.log("Escaneie imediatamente. Nao compartilhe este QR Code.");
  } catch (err) {
    console.error("Falha ao obter QR Code. HTTP:", err.response && err.response.status || "sem resposta");
    console.error("Detalhe:", err.message);
    process.exitCode = 1;
  }
})();
NODE
