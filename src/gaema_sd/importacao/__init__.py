"""Importação de áreas candidatas SINTÉTICAS (GeoJSON ou CSV). Só leitura de texto: sem rede, sem imagem, sem NDVI."""

from .candidatas import FORMATOS, ItemImportado, chave_geometria, ler_candidatas

__all__ = ["FORMATOS", "ItemImportado", "chave_geometria", "ler_candidatas"]
