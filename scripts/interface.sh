#!/usr/bin/env bash
# Abre a interface local de operação com o cenário sintético de demonstração (só neste computador, 127.0.0.1).
# Uso: scripts/interface.sh [porta]    Depois abra http://127.0.0.1:8765/ no navegador. Ctrl+C encerra.
# No GitHub Codespaces o próprio Codespace encaminha a porta e abre o navegador (ver README).
set -euo pipefail
cd "$(dirname "$0")/.."
PORTA="${1:-8765}"
if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) == 0 else 1)" "$PORTA"; then
  echo "A interface já está aberta na porta $PORTA (http://127.0.0.1:$PORTA/). Nada a fazer."
  exit 0
fi
PASTA="saida/interface-$(date +%Y%m%d-%H%M%S)"
PYTHONPATH=src python3 -m gaema_sd.interface "$PASTA" --demo --porta "$PORTA"
