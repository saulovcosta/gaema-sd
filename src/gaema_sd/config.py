"""Leitura de config/parametros.json. Parâmetros sem valor ficam None (sem invenção)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "parametros.json"


@lru_cache(maxsize=4)
def carregar(caminho: str | None = None) -> dict[str, Any]:
    with open(caminho or CAMINHO_PADRAO, encoding="utf-8") as f:
        return json.load(f)


def parametro(nome: str, caminho: str | None = None) -> Any:
    item = carregar(caminho).get(nome)
    if item is None:
        raise KeyError(f"Parâmetro inexistente: {nome}")
    return item["valor"]
