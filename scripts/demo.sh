#!/usr/bin/env bash
# Roda o protótipo local de ponta a ponta com dados SINTÉTICOS.
# Uso: scripts/demo.sh [pasta_nova_de_saida]   (padrão: saida/demo-<data-hora>)
set -euo pipefail
cd "$(dirname "$0")/.."
PASTA="${1:-saida/demo-$(date +%Y%m%d-%H%M%S)}"
PYTHONPATH=src python3 -m gaema_sd.demo "$PASTA"
