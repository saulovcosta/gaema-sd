"""Cabeçalho institucional do relatório (HTML e PDF usam as mesmas frases)."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

INSTITUICAO = "Ministério Público do Estado do Tocantins · CAOMA · GAEMA"
SEM_ENDOSSO = "Protótipo em desenvolvimento no âmbito do CAOMA. Sem endosso institucional formal."
LOGO = Path(__file__).resolve().parents[3] / "assets" / "logo-mpto-gaema.png"
LOGO_ALT = "Logotipos do Gaema e do Ministério Público do Estado do Tocantins"
LOGO_PIXELS = (462, 141)


def linha_institucional(endosso: dict | None) -> str:
    """Única fonte da frase. Sem endosso válido (ver config.endosso), só a negativa."""
    if endosso and endosso.get("ato") and endosso.get("data"):
        return f"Endossado pelo CAOMA, ato nº {endosso['ato']}, de {endosso['data']}"
    return SEM_ENDOSSO


@lru_cache(maxsize=1)
def logo_bytes() -> bytes | None:
    """Logo de assets/ (fora do pacote). Sem o arquivo, o cabeçalho sai só com o texto."""
    try:
        return LOGO.read_bytes()
    except OSError:
        return None


def logo_data_uri() -> str:
    b = logo_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode("ascii") if b else ""
