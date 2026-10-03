#!/usr/bin/env bash
# Simula, no computador, o aparelho de campo e a central (dados SINTÉTICOS, rede simulada): coleta sem rede,
# conflito, decisão do coordenador e o aparelho recebendo a decisão.
# Uso: scripts/demo_sincronizacao.sh [pasta_nova]   (padrão: saida/sincronizacao-<data-hora>)
set -euo pipefail
cd "$(dirname "$0")/.."
PASTA="${1:-saida/sincronizacao-$(date +%Y%m%d-%H%M%S)}"
PYTHONPATH=src python3 -m gaema_sd.sincronizacao simular "$PASTA"
