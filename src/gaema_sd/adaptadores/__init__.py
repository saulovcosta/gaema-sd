"""Adaptadores ArcGIS: SOMENTE interface, tradução e documentação.

Nada aqui fala com rede, ArcGIS Online/Enterprise, Survey123, Field Maps, Radar Ambiental ou Painel.
Não existe organização ArcGIS, Client ID nem serviço acessível (lacuna LA-05). Ver adapters/arcgis/README.md.
"""

from .config import ConfigArcGIS
from .interfaces import (
    AmbienteIndisponivel,
    CamadaExterna,
    CatalogoCamadas,
    ImportadorCampo,
    NaoConfiguradoCatalogo,
    NaoConfiguradoImportador,
    NaoConfiguradoPublicador,
    PublicadorCampo,
)
from .traducao import campos_de_campanha, nao_traduzidos, traduzir_submissao

__all__ = ["AmbienteIndisponivel", "CamadaExterna", "CatalogoCamadas", "ConfigArcGIS", "ImportadorCampo",
           "NaoConfiguradoCatalogo", "NaoConfiguradoImportador", "NaoConfiguradoPublicador", "PublicadorCampo",
           "campos_de_campanha", "nao_traduzidos", "traduzir_submissao"]
