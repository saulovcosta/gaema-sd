"""Unidades de medida. O valor bruto é sempre preservado; a conversão é explícita.

Fatores de conversão são definições metrológicas (não parâmetros técnicos):
1 MPa = 1000 kPa; 1 kgf/cm² = 98,0665 kPa; 1 m = 100 cm; 1 mm = 0,1 cm.
"""

from __future__ import annotations

import math

from .problemas import Problema, erro

PARA_KPA = {"kpa": 1.0, "mpa": 1000.0, "kgf/cm2": 98.0665, "kgf/cm²": 98.0665}
PARA_CM = {"cm": 1.0, "mm": 0.1, "m": 100.0}
PERCENTUAL = {"%", "percentual"}


def ler_numero(bruto) -> float:
    """Aceita vírgula decimal. Levanta ValueError se não for número finito."""
    if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
        v = float(bruto)
    else:
        v = float(str(bruto).strip().replace(",", "."))
    if not math.isfinite(v):
        raise ValueError("número não finito")
    return v


def _converter(bruto, unidade: str, tabela: dict, campo: str, grandeza: str):
    u = (unidade or "").strip().lower()
    if u not in tabela:
        return None, [erro("UNIDADE_INVALIDA", campo,
                           f"unidade '{unidade}' não aceita para {grandeza}; use {sorted(tabela)}")]
    try:
        v = ler_numero(bruto)
    except (TypeError, ValueError):
        return None, [erro("VALOR_NAO_NUMERICO", campo, f"valor '{bruto}' não é número")]
    if v < 0:
        return None, [erro("VALOR_NEGATIVO", campo, f"{grandeza} não pode ser negativa")]
    return v * tabela[u], []


def para_kpa(bruto, unidade: str, campo: str = "resistencia"):
    return _converter(bruto, unidade, PARA_KPA, campo, "resistência à penetração")


def para_cm(bruto, unidade: str, campo: str = "profundidade"):
    return _converter(bruto, unidade, PARA_CM, campo, "profundidade")


def validar_percentual(bruto, campo: str = "valor") -> list[Problema]:
    try:
        v = ler_numero(bruto)
    except (TypeError, ValueError):
        return [erro("VALOR_NAO_NUMERICO", campo, f"valor '{bruto}' não é número")]
    if not 0 <= v <= 100:
        return [erro("PERCENTUAL_FORA_FAIXA", campo, "percentual deve estar entre 0 e 100")]
    return []
