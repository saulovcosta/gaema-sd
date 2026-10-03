"""Qualidade do GPS. Precisão é obrigatória; acima do limite configurado gera ALERTA."""

from __future__ import annotations

import math

from .. import config
from .problemas import Problema, alerta, erro


def validar_precisao(precisao_m, campo: str = "precisao_gps_m") -> list[Problema]:
    if precisao_m is None:
        return [erro("GPS_PRECISAO_AUSENTE", campo, "registrar a precisão informada pelo GPS")]
    try:
        p = float(precisao_m)
    except (TypeError, ValueError):
        return [erro("GPS_PRECISAO_INVALIDA", campo, "precisão não numérica")]
    if not math.isfinite(p) or p <= 0:
        return [erro("GPS_PRECISAO_INVALIDA", campo, "precisão deve ser número positivo")]
    limite = config.parametro("gps_precisao_maxima_m")
    if limite is not None and p > float(limite):
        return [alerta("GPS_RUIM", campo,
                       f"precisão {p:g} m acima do limite operacional de {float(limite):g} m")]
    return []
