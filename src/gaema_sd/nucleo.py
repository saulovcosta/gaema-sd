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
from .erros import (
    AcessoNegado,
    ConflitoAtualizacao,
    ConflitoIdempotencia,
    ErroGaema,
    TransicaoInvalida,
    ValidacaoFalhou,
)
from .estados import maquina
from .estados.contexto import montar_contexto
from .persistencia.sqlite import ArmazenamentoAuditoriaSQLite, Repositorio
from .validacao.entidades import validar
from .validacao.problemas import Problema, erro, exigir_sem_erros

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
IMUTAVEIS = (E.VersaoProtocolo, E.Evidencia, E.Relatorio, E.RevisaoTecnica, E.Diagnostico)

# Campos de autoria que devem coincidir com o usuário logado (vazio = preenchido pelo núcleo).
AUTORIA: dict[type, str] = {
    E.RevisaoTecnica: "revisor_id",
    E.Providencia: "decidido_por",
    E.Evidencia: "registrado_por",
    E.Relatorio: "gerado_por",
}


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

    def _regras_de_criacao(self, ator: Ator, obj) -> list[Problema]:
        problemas = []
        if obj.versao != 1:
            problemas.append(erro("VERSAO_INICIAL", "versao", "registro novo começa na versão 1"))
        if isinstance(obj, E.Demanda) and (obj.estado is not Estado.CANDIDATA or obj.estado_anterior is not None):
            problemas.append(erro("ESTADO_INICIAL", "estado",
                                  "demanda nasce em CANDIDATA; outros estados só por transição"))
        campo = AUTORIA.get(type(obj))
        if campo and getattr(obj, campo) not in ("", ator.id):
            problemas.append(erro("AUTORIA_DIVERGENTE", campo, "deve ser o próprio usuário que registra"))
        return problemas

    def registrar(self, ator: Ator, obj: T) -> tuple[T, list[Problema]]:
        """Grava registro novo. Devolve (registro, alertas). Reenvio idêntico não duplica."""
        tipo = type(obj).__name__
        self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], tipo, obj.id)
        campo = AUTORIA.get(type(obj))
        preencher = {campo: ator.id} if campo and getattr(obj, campo) == "" else {}
        obj = dataclasses.replace(obj, criado_por=ator.id, **preencher)  # autoria vem do login
        try:
            alertas = exigir_sem_erros(self._regras_de_criacao(ator, obj) + validar(obj))
            with self.repo.transacao():
                gravado, criado = self.repo.inserir(obj)
                self.trilha.registrar(
                    ator, "CRIAR" if criado else "REENVIO_IDEMPOTENTE", tipo, gravado.id,
                    detalhes={"alertas": ",".join(p.codigo for p in alertas)} if alertas else None)
        except ConflitoIdempotencia as e:
            self._auditar_recusa(ator, "CONFLITO_IDEMPOTENCIA", tipo, obj.id, e)
            raise
        except ValidacaoFalhou as e:
            if any(p.codigo in ("ESTADO_INICIAL", "AUTORIA_DIVERGENTE") for p in e.problemas):
                self._auditar_recusa(ator, "CRIACAO_RECUSADA", tipo, obj.id, e)
            raise
        return gravado, alertas

    def atualizar(self, ator: Ator, obj: T, versao_lida: int) -> tuple[T, list[Problema]]:
        """Grava nova versão. Leitura, conferências e gravação na mesma transação."""
        tipo = type(obj).__name__
        self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], tipo, obj.id)
        try:
            with self.repo.transacao():
                if isinstance(obj, IMUTAVEIS):
                    raise ErroGaema(f"{tipo} é imutável: registre nova versão vinculada à anterior")
                original = self.repo.obter(type(obj), obj.id)
                if original.versao != versao_lida:
                    raise ConflitoAtualizacao(
                        f"{tipo} {obj.id}: alterado por outra pessoa (versão lida {versao_lida}, "
                        f"atual {original.versao}). Recarregue e refaça a alteração.")
                if isinstance(obj, E.Demanda) and (obj.estado, obj.estado_anterior) != (
                        original.estado, original.estado_anterior):
                    raise ErroGaema("estado da Demanda só muda por transição (Nucleo.transitar)")
                if getattr(obj, "chave_idempotencia", "") != getattr(original, "chave_idempotencia", ""):
                    raise ErroGaema("chave de envio não pode ser alterada")
                obj = dataclasses.replace(obj, criado_por=original.criado_por, criado_em=original.criado_em)
                alertas = exigir_sem_erros(validar(obj))
                novo = self.repo.atualizar(obj, versao_lida)
                self.trilha.registrar(ator, "ATUALIZAR", tipo, obj.id, detalhes={"versao": novo.versao})
        except ConflitoAtualizacao as e:
            self._auditar_recusa(ator, "CONFLITO_ATUALIZACAO", tipo, obj.id, e)
            raise
        except ValidacaoFalhou:
            raise
        except ErroGaema as e:
            self._auditar_recusa(ator, "ATUALIZACAO_RECUSADA", tipo, obj.id, e)
            raise
        return novo, alertas

    def transitar(self, ator: Ator, demanda_id: str, destino: Estado, *, motivo: str = "") -> E.Demanda:
        """Muda o estado. As pré-condições são apuradas no banco, nunca informadas pelo chamador."""
        try:
            with self.repo.transacao():
                atual = self.repo.obter(E.Demanda, demanda_id)
                contexto = montar_contexto(self.repo, atual, ator, self.trilha.eventos)
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
