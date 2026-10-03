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
from ..dominio.serializacao import de_dict
from ..erros import ErroGaema
from ..dominio.enums import StatusSincronizacao
if TYPE_CHECKING:
    from ..nucleo import Nucleo

from .fila import FilaLocal
from .item import DecisaoConflito, ItemSincronizacao

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
        tipo = type(obj).__name__
        if (tipo, obj.id) in self.fila.entidades_retidas():
            raise ErroGaema("registro em conflito de sincronização aguardando decisão do coordenador; "
                            "consulte as decisões antes de corrigir")
        obj = dataclasses.replace(obj, status_sincronizacao=StatusSincronizacao.PENDENTE)
        gravado, _ = self.nucleo.atualizar(self.ator, obj, versao_lida)
        # a versão local pode diferir da central depois de uma decisão: base = versão local + deslocamento
        base = versao_lida + self.fila.deslocamento(tipo, obj.id)
        self.fila.enfileirar(ItemSincronizacao.de_registro(gravado, "ATUALIZAR", versao_base=base))
        return gravado

    def aplicar_decisao(self, d: DecisaoConflito) -> str:
        """Traz para o dispositivo o desfecho de um conflito. Devolve um texto curto do que foi feito."""
        item = self.fila.item_por_hash(d.hash_dados)
        if item is None:
            self.fila.registrar_decisao(d, aplicada=False, observacao="item não está mais na fila local")
            return "item desconhecido"
        cls = next(c for c in TIPOS_COLETA if c.__name__ == d.tipo)
        mesmo_registro = d.entidade_id == item["entidade_id"]
        antigo = self.fila.deslocamento(d.tipo, item["entidade_id"])
        with self.nucleo.repo.transacao():
            if d.decisao == "MANTER_CENTRAL":
                descartados = self.fila.rejeitar_pendentes(
                    d.tipo, item["entidade_id"], "descartado: decisão do coordenador manteve a versão da central")
                if cls is E.Evidencia or not mesmo_registro or d.dados_central is None:
                    self.fila.registrar_decisao(d, aplicada=False, observacao=(
                        "decisão registrada; registro local não substituído (evidência imutável ou outro identificador)"))
                    return "registrada"
                local = self.nucleo.repo.obter(cls, item["entidade_id"])
                novo = dataclasses.replace(de_dict(cls, d.dados_central), id=local.id,
                                           status_sincronizacao=StatusSincronizacao.SINCRONIZADO)
                try:
                    gravado, _ = self.nucleo.atualizar(self.ator, novo, local.versao)
                except ErroGaema as e:
                    self.fila.registrar_decisao(d, aplicada=False, observacao=f"{type(e).__name__}: {e}")
                    return "não aplicada"
                self.fila.definir_deslocamento(d.tipo, local.id, d.versao_central - gravado.versao)
                self.fila.registrar_decisao(d, aplicada=True, observacao=f"{descartados} envio(s) pendente(s) descartado(s)")
                return "versão da central adotada"
            # ACEITAR_DISPOSITIVO: a central passou a ter o conteúdo do dispositivo; o dispositivo só realinha versões
            if not mesmo_registro:
                self.fila.registrar_decisao(d, aplicada=False, observacao="outro identificador; nada a realinhar")
                return "registrada"
            novo_deslocamento = d.versao_resultante - item["dados"]["versao"]
            self.fila.reajustar_base_pendentes(d.tipo, local_id := item["entidade_id"], novo_deslocamento - antigo)
            self.fila.definir_deslocamento(d.tipo, local_id, novo_deslocamento)
            self.fila.registrar_decisao(d, aplicada=True)
            return "versões realinhadas"

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
