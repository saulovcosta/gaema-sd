"""Configuração ArcGIS lida do ambiente (variáveis do `.env`, fora do git).

Só informa SE está definida. O valor nunca é devolvido, impresso nem registrado em log: nenhum código
desta fase o usa. Quando existir organização ArcGIS, o adaptador real terá de ler o valor por outro caminho.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

VARIAVEIS = ("ARCGIS_PORTAL_URL", "ARCGIS_CLIENT_ID")


@dataclass(frozen=True)
class ConfigArcGIS:
    definidas: tuple[str, ...]

    @staticmethod
    def de_ambiente(env: Mapping[str, str] | None = None) -> "ConfigArcGIS":
        env = os.environ if env is None else env
        return ConfigArcGIS(tuple(v for v in VARIAVEIS if (env.get(v) or "").strip()))

    @property
    def completa(self) -> bool:
        return set(self.definidas) == set(VARIAVEIS)

    def faltando(self) -> tuple[str, ...]:
        return tuple(v for v in VARIAVEIS if v not in self.definidas)
