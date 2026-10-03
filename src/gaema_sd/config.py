"""Leitura de config/parametros.json e config/endosso.json. Parâmetros sem valor ficam None (sem invenção)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
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


CAMINHO_ENDOSSO = Path(__file__).resolve().parents[2] / "config" / "endosso.json"
_ATO = re.compile(r"[0-9A-Za-zÀ-ÿº./\- ]{1,40}")


def endosso(caminho: str | Path | None = None, *, ate: date | None = None) -> dict | None:
    """Endosso institucional lido de config/endosso.json. Só vale com número E data do ato preenchidos, número em
    formato simples e data DD/MM/AAAA real, não posterior a `ate`. Qualquer falta ou erro = None (sem endosso): na
    dúvida, o relatório nunca afirma endosso."""
    try:
        with open(caminho or CAMINHO_ENDOSSO, encoding="utf-8") as f:
            dados = json.load(f)
        ato = str(dados["ato_numero"]["valor"] or "").strip()
        texto_data = str(dados["ato_data"]["valor"] or "").strip()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not ato or not texto_data or not _ATO.fullmatch(ato):
        return None
    try:
        quando = datetime.strptime(texto_data, "%d/%m/%Y").date()
    except ValueError:
        return None
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto_data) or (ate is not None and quando > ate):
        return None
    return {"ato": ato, "data": quando.strftime("%d/%m/%Y")}
