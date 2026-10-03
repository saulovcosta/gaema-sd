"""Dispositivo de campo: núcleo local (SQLite próprio) + fila de envio.

Grava localmente primeiro (offline-first) e enfileira. Se o processo morrer entre gravar e
enfileirar, `recuperar_nao_enfileirados` reenfileira os registros PENDENTE que ficaram de fora.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import dataclasses
from pathlib import Path

from ..acesso.politica import Ator
from ..dominio import entidades as E
from ..dominio.enums import StatusSincronizacao
if TYPE_CHECKING:
    from ..nucleo import Nucleo

from .fila import FilaLocal
from .item import ItemSincronizacao

TIPOS_COLETA = (E.PontoAmostral, E.Observacao, E.MedicaoPenetracao, E.Evidencia)


class Dispositivo:
    def __init__(self, nucleo: Nucleo, ator: Ator):
        self.nucleo = nucleo
        self.ator = ator
        self.fila = FilaLocal(nucleo.repo)

    def coletar(self, obj, conteudo: bytes | None = None):
        """Grava no dispositivo (status PENDENTE) e enfileira a criação."""
        obj = dataclasses.replace(obj, status_sincronizacao=StatusSincronizacao.PENDENTE)
        if isinstance(obj, E.Evidencia):
            if conteudo is None:
                raise ValueError("evidência exige o conteúdo do arquivo")
            gravado = self.nucleo.registrar_evidencia(self.ator, obj, conteudo)
        else:
            gravado, _ = self.nucleo.registrar(self.ator, obj)
        self.fila.enfileirar(ItemSincronizacao.de_registro(gravado, "CRIAR"))
        return gravado

    def corrigir(self, obj, versao_lida: int):
        """Altera registro já gravado (não vale para Evidencia, que é imutável) e enfileira a atualização."""
        obj = dataclasses.replace(obj, status_sincronizacao=StatusSincronizacao.PENDENTE)
        gravado, _ = self.nucleo.atualizar(self.ator, obj, versao_lida)
        self.fila.enfileirar(ItemSincronizacao.de_registro(gravado, "ATUALIZAR", versao_base=versao_lida))
        return gravado

    def recuperar_nao_enfileirados(self) -> int:
        """Reenfileira criações PENDENTE sem item na fila (queda entre gravar e enfileirar)."""
        n = 0
        for cls in TIPOS_COLETA:
            for obj in self.nucleo.repo.listar(cls):
                if obj.status_sincronizacao is StatusSincronizacao.PENDENTE and obj.versao == 1:
                    n += self.fila.enfileirar(ItemSincronizacao.de_registro(obj, "CRIAR"))
        return n

    def conteudo_evidencia(self, sha256: str) -> bytes:
        return Path(self.nucleo._caminho_evidencia(sha256)).read_bytes()
