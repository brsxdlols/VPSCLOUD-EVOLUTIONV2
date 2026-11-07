#!/bin/sh
# Deprecated: the original update path bypassed current session/entrypoint protections.
set -eu
printf '%s\n' 'ERRO: este atalho de atualizacao foi desativado.' 'Use o instalador revisado install-7070-replace-v1.sh publicado na main.' 'Leia README.md e execute primeiro EVOLUTION_MODE=diagnose. Nenhuma alteracao foi executada.' >&2
exit 1
