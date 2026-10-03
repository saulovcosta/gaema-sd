"""Fachada do núcleo: único caminho de escrita.

Toda operação passa por: política de acesso → validação → gravação → auditoria,
na mesma transação. Recusas (acesso negado, transição inválida, conflito) são
auditadas em transação própria, depois de desfeita a operação recusada.
"""

from __future__ import annotations

import dataclasses
from typing import TypeVar

from .acesso.politica import Acao, Ator, exigir
from .auditoria.trilha import TrilhaAuditoria
from .dominio import entidades as E
from .dominio.enums import Estado, Sensibilidade
from .erros import AcessoNegado, ConflitoAtualizacao, ConflitoIdempotencia, ErroGaema, TransicaoInvalida
from .estados import maquina
from .persistencia.sqlite import ArmazenamentoAuditoriaSQLite, Repositorio
from .validacao.entidades import validar
from .validacao.problemas import Problema, exigir_sem_erros

T = TypeVar("T")

ACAO_DE_ESCRITA: dict[type, Acao] = {
    E.FonteDado: Acao.REGISTRAR_FONTE,
    E.IntegracaoExterna: Acao.REGISTRAR_INTEGRACAO,
    E.AreaCandidata: Acao.REGISTRAR_AREA_CANDIDATA,
    E.Alerta: Acao.REGISTRAR_ALERTA,
    E.Demanda: Acao.REGISTRAR_DEMANDA,
    E.AreaInteresse: Acao.DEFINIR_AREA_INTERESSE,
    E.Equipe: Acao.GERIR_EQUIPE,
    E.CampanhaVistoria: Acao.PLANEJAR_CAMPANHA,
    E.PontoAmostral: Acao.COLETAR_CAMPO,
    E.Observacao: Acao.COLETAR_CAMPO,
    E.MedicaoPenetracao: Acao.COLETAR_CAMPO,
    E.Evidencia: Acao.REGISTRAR_EVIDENCIA,
    E.VersaoProtocolo: Acao.PUBLICAR_PROTOCOLO,
    E.Diagnostico: Acao.COMPUTAR_DIAGNOSTICO,
    E.RevisaoTecnica: Acao.REVISAR_DIAGNOSTICO,
    E.Providencia: Acao.REGISTRAR_PROVIDENCIA,
    E.PlanoRecuperacao: Acao.GERIR_PLANO_MONITORAMENTO,
    E.MarcoMonitoramento: Acao.GERIR_PLANO_MONITORAMENTO,
    E.Relatorio: Acao.EMITIR_RELATORIO,
}

# Correção gera novo registro (com vínculo ao anterior), nunca alteração.
IMUTAVEIS = (E.VersaoProtocolo, E.Evidencia, E.Relatorio, E.RevisaoTecnica)


class Nucleo:
    def __init__(self, repo: Repositorio):
        self.repo = repo
        self.trilha = TrilhaAuditoria(ArmazenamentoAuditoriaSQLite(repo))

    # ------------------------------------------------------------ apoio

    def _auditar_recusa(self, ator: Ator, acao: str, entidade: str, entidade_id: str,
                        erro: Exception, **extra) -> None:
        with self.repo.transacao():
            self.trilha.registrar(ator, acao, entidade, entidade_id,
                                  detalhes={"erro": type(erro).__name__, "mensagem": str(erro)}, **extra)

    def _exigir(self, ator: Ator, acao: Acao, entidade: str, entidade_id: str) -> None:
        try:
            exigir(ator, acao)
        except AcessoNegado as e:
            self._auditar_recusa(ator, "ACESSO_NEGADO", entidade, entidade_id, e)
            raise

    # ------------------------------------------------------------ escrita

    def registrar(self, ator: Ator, obj: T) -> tuple[T, list[Problema]]:
        """Grava registro novo. Devolve (registro, alertas). Reenvio idêntico não duplica."""
        tipo = type(obj).__name__
        self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], tipo, obj.id)
        obj = dataclasses.replace(obj, criado_por=ator.id)  # autoria do registro vem do login
        alertas = exigir_sem_erros(validar(obj))
        try:
            with self.repo.transacao():
                gravado, criado = self.repo.inserir(obj)
                self.trilha.registrar(
                    ator, "CRIAR" if criado else "REENVIO_IDEMPOTENTE", tipo, gravado.id,
                    detalhes={"alertas": ",".join(p.codigo for p in alertas)} if alertas else None)
        except ConflitoIdempotencia as e:
            self._auditar_recusa(ator, "CONFLITO_IDEMPOTENCIA", tipo, obj.id, e)
            raise
        return gravado, alertas

    def atualizar(self, ator: Ator, obj: T, versao_lida: int) -> tuple[T, list[Problema]]:
        tipo = type(obj).__name__
        if isinstance(obj, IMUTAVEIS):
            raise ErroGaema(f"{tipo} é imutável: registre nova versão vinculada à anterior")
        self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], tipo, obj.id)
        original = self.repo.obter(type(obj), obj.id)
        if isinstance(obj, E.Demanda) and (obj.estado, obj.estado_anterior) != (
                original.estado, original.estado_anterior):
            raise ErroGaema("estado da Demanda só muda por transição (Nucleo.transitar)")
        obj = dataclasses.replace(obj, criado_por=original.criado_por, criado_em=original.criado_em)
        alertas = exigir_sem_erros(validar(obj))
        try:
            with self.repo.transacao():
                novo = self.repo.atualizar(obj, versao_lida)
                self.trilha.registrar(ator, "ATUALIZAR", tipo, obj.id, detalhes={"versao": novo.versao})
        except ConflitoAtualizacao as e:
            self._auditar_recusa(ator, "CONFLITO_ATUALIZACAO", tipo, obj.id, e)
            raise
        return novo, alertas

    def transitar(self, ator: Ator, demanda_id: str, destino: Estado, *,
                  contexto: maquina.ContextoTransicao, motivo: str = "") -> E.Demanda:
        try:
            with self.repo.transacao():
                atual = self.repo.obter(E.Demanda, demanda_id)
                nova = maquina.transitar(atual, destino, ator, contexto=contexto,
                                         trilha=self.trilha, motivo=motivo)
                return self.repo.atualizar(nova, atual.versao)
        except (AcessoNegado, TransicaoInvalida, ConflitoAtualizacao) as e:
            self._auditar_recusa(ator, "TRANSICAO_RECUSADA", "Demanda", demanda_id, e,
                                 estado_destino=destino.value)
            raise

    # ------------------------------------------------------------ leitura

    def ler(self, ator: Ator, cls: type[T], id: str) -> T:
        restrito = cls.SENSIBILIDADE in (Sensibilidade.RESTRITA, Sensibilidade.SIGILOSA)
        self._exigir(ator, Acao.LER_RESTRITO if restrito else Acao.LER, cls.__name__, id)
        obj = self.repo.obter(cls, id)
        if restrito:
            with self.repo.transacao():
                self.trilha.registrar(ator, "LEITURA_RESTRITA", cls.__name__, id)
        return obj

    def verificar_auditoria(self, ator: Ator) -> int:
        self._exigir(ator, Acao.VERIFICAR_AUDITORIA, "EventoAuditoria", "*")
        return self.trilha.verificar()
