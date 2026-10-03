#!/usr/bin/env bash
# Instala dependências fixadas e roda a suíte de testes.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q -r requirements-dev.txt
python3 -m pytest "$@"
