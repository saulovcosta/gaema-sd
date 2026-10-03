"""Pacote de exportação em formato aberto e PRÓPRIO do GAEMA SD (RQ-67).

Não é o formato do Painel do art. 18 nem do Radar Ambiental (desconhecidos, LA-10): nenhuma integração
é declarada. Serve de ponto de partida para conversar com a equipe do Radar sobre o que seria trocado.
"""

from .painel import FORMATO, VERSAO_FORMATO, esquema_json, montar_pacote, serializar

__all__ = ["FORMATO", "VERSAO_FORMATO", "esquema_json", "montar_pacote", "serializar"]
