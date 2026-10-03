#!/usr/bin/env bash
# Abre a interface local de operação com o cenário sintético de demonstração (só neste computador, 127.0.0.1).
# Uso: scripts/interface.sh [porta]    Depois abra http://127.0.0.1:8765/ no navegador. Ctrl+C encerra.
set -euo pipefail
cd "$(dirname "$0")/.."
PORTA="${1:-8765}"
PASTA="saida/interface-$(date +%Y%m%d-%H%M%S)"
PYTHONPATH=src python3 -m gaema_sd.interface "$PASTA" --demo --porta "$PORTA"
