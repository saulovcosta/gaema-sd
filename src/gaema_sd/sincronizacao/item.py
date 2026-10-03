"""Item de envio do dispositivo para a central e erros de transporte."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..dominio.serializacao import json_canonico, para_dict, sha256_texto


class ResultadoSincronizacao(str, Enum):
    APLICADO = "APLICADO"
    REENVIO_IDEMPOTENTE = "REENVIO_IDEMPOTENTE"
    CONFLITO = "CONFLITO"


class ErroTransporte(Exception):
    """Falha de rede ou de serviço: o item NÃO foi confirmado e pode ser reenviado."""


class ErroRede(ErroTransporte):
    pass


class ServicoIndisponivel(ErroTransporte):
    pass


class InterrupcaoSimulada(BaseException):
    """Simula o processo do dispositivo morrendo no meio do envio (não é capturada pelo sincronizador)."""


@dataclass(frozen=True)
class ItemSincronizacao:
    tipo: str
    entidade_id: str
    operacao: str           # CRIAR | ATUALIZAR
    versao_base: int        # versão que o dispositivo conhecia da central (0 em CRIAR)
    dados: dict
    hash_dados: str
    chave_idempotencia: str = ""

    @staticmethod
    def de_registro(obj, operacao: str, versao_base: int = 0) -> "ItemSincronizacao":
        dados = para_dict(obj)
        return ItemSincronizacao(tipo=type(obj).__name__, entidade_id=obj.id, operacao=operacao,
                                 versao_base=versao_base, dados=dados,
                                 hash_dados=sha256_texto(json_canonico(dados)),
                                 chave_idempotencia=getattr(obj, "chave_idempotencia", "") or "")
