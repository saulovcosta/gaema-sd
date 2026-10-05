"""Fachada do núcleo: único caminho de escrita.

Toda operação passa por: política de acesso → validação → gravação → auditoria,
na mesma transação. Recusas (acesso negado, transição inválida, conflito) são
auditadas em transação própria, depois de desfeita a operação recusada.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from .acesso.politica import Acao, Ator, exigir, pode
from .auditoria.trilha import TrilhaAuditoria, sanear_texto
from .backup.ancora import conferir_ancora, gerar_ancora
from .backup.backup import criar_backup as criar_backup_arquivos
from .backup.backup import verificar_backup as verificar_backup_arquivos
from .dominio import entidades as E
from .dominio.enums import Estado, FormatoRelatorio, Papel, Sensibilidade, SituacaoPedidoAcesso, StatusSincronizacao
from .dominio.serializacao import de_dict, json_canonico, para_dict, sha256_texto
from .erros import (
    AcessoNegado,
    AuditoriaCorrompida,
    ConflitoAtualizacao,
    ConflitoIdempotencia,
    ErroGaema,
    RegistroNaoEncontrado,
    TransicaoInvalida,
    ValidacaoFalhou,
)
from .estados import maquina
from .exportacao import painel as exportacao_painel
from .estados.contexto import montar_contexto
from .config import parametro
from .persistencia.sqlite import ArmazenamentoAuditoriaSQLite, Repositorio
from .protocolo.definicao import canonizar, carregar_definicao
from .sincronizacao.item import DecisaoConflito, ItemSincronizacao, ResultadoSincronizacao
from .protocolo.motor import avaliar, entradas_de, hash_entradas, resultado_para_json
from .relatorio import html as relatorio_html
from .relatorio import montagem
from .relatorio import pdf as relatorio_pdf
from .validacao.anexos import validar_anexo
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
    E.PedidoAcesso: Acao.PEDIR_ACESSO_TESTE,
}

# Correção gera novo registro (com vínculo ao anterior), nunca alteração.
IMUTAVEIS = (E.VersaoProtocolo, E.Evidencia, E.Relatorio, E.RevisaoTecnica, E.Diagnostico)

# Campos de autoria que devem coincidir com o usuário logado (vazio = preenchido pelo núcleo).
AUTORIA: dict[type, str] = {
    E.RevisaoTecnica: "revisor_id",
    E.Providencia: "decidido_por",
    E.Evidencia: "registrado_por",
    E.Relatorio: "gerado_por",
    E.Observacao: "observador_id",
}


# Tipos que o dispositivo de campo envia. Evidencia só nasce (imutável); os demais também podem ser corrigidos.
TIPOS_SINCRONIZAVEIS: dict[str, type] = {c.__name__: c for c in
                                         (E.PontoAmostral, E.Observacao, E.MedicaoPenetracao, E.Evidencia)}
ATOR_SINCRONIZACAO = Ator.de("processo-sincronizacao", Papel.SISTEMA)
# Quem pede usuário de teste pela página de entrada (não há login nem autenticação real, R-31).
ATOR_PEDIDO_ACESSO = Ator.de("visitante-pedido-acesso", Papel.SISTEMA)
DECISOES_CONFLITO = ("MANTER_CENTRAL", "ACEITAR_DISPOSITIVO")
_META = {"versao", "atualizado_em", "status_sincronizacao", "criado_por", "criado_em"}

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
# Dado de campo só entra enquanto a demanda está em coleta/envio; depois do diagnóstico a correção é registro novo.
ESTADOS_DE_COLETA = (Estado.EM_CAMPO, Estado.COLETA_PARCIAL, Estado.AGUARDANDO_SINCRONIZACAO,
                     Estado.CONFLITO_SINCRONIZACAO)

# Papel da instalação. "central" confere origem, equipe e estado em TODA entrada de dado de campo (R-28); "dispositivo"
# é o aparelho de campo (não tem a campanha, só grava local e enfileira); "livre" é só para testes e desenvolvimento.
MODOS = ("central", "dispositivo", "livre")
TIPOS_DE_CAMPO = tuple(TIPOS_SINCRONIZAVEIS.values())
# Campos que ligam o dado de campo à sua demanda; não mudam depois de gravados.
VINCULOS: dict[type, tuple[str, ...]] = {E.PontoAmostral: ("campanha_id",), E.Observacao: ("ponto_id",),
                                         E.MedicaoPenetracao: ("ponto_id",),
                                         E.Evidencia: ("campanha_id", "ponto_id", "observacao_id")}

ESTADOS_COM_RELATORIO = (Estado.DIAGNOSTICO_EMITIDO, Estado.EM_TRATATIVA, Estado.EM_MONITORAMENTO,
                         Estado.ENCERRADA, Estado.REABERTA)


class Nucleo:
    def __init__(self, repo: Repositorio, diretorio_saida: str | Path = "saida", *, modo: str = "central"):
        if modo not in MODOS:
            raise ErroGaema(f"modo {modo!r} desconhecido; use um de {MODOS}")
        self._modo = modo
        self.repo = repo
        self.saida = Path(diretorio_saida)
        self.trilha = TrilhaAuditoria(ArmazenamentoAuditoriaSQLite(repo))

    @property
    def modo(self) -> str:
        """Somente leitura: o modo é fixado na criação (trocar para 'livre' desligaria as conferências da central)."""
        return self._modo

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
        if not _UUID.fullmatch(obj.id or ""):
            problemas.append(erro("ID_INVALIDO", "id", "identificador deve ser um UUID (hexadecimal e hífens)"))
        if obj.versao != 1:
            problemas.append(erro("VERSAO_INICIAL", "versao", "registro novo começa na versão 1"))
        if isinstance(obj, E.Demanda) and (obj.estado is not Estado.CANDIDATA or obj.estado_anterior is not None):
            problemas.append(erro("ESTADO_INICIAL", "estado",
                                  "demanda nasce em CANDIDATA; outros estados só por transição"))
        if isinstance(obj, E.PedidoAcesso) and (obj.situacao is not SituacaoPedidoAcesso.PENDENTE or obj.decidido_por
                                                or obj.motivo_decisao or obj.decidido_em is not None):
            problemas.append(erro("ESTADO_INICIAL", "situacao",
                                  "pedido nasce PENDENTE; decisão só por Nucleo.decidir_acesso_teste"))
        campo = AUTORIA.get(type(obj))
        if campo and getattr(obj, campo) not in ("", ator.id):
            problemas.append(erro("AUTORIA_DIVERGENTE", campo, "deve ser o próprio usuário que registra"))
        if isinstance(obj, E.VersaoProtocolo):
            for v in self.repo.listar(E.VersaoProtocolo):
                if (v.codigo, v.versao_semantica) == (obj.codigo, obj.versao_semantica) and \
                        v.hash_definicao != obj.hash_definicao:
                    problemas.append(erro("VERSAO_PROTOCOLO_REPETIDA", "versao_semantica",
                                          "já existe esta versão com outro conteúdo; publique nova versão"))
        return problemas

    def registrar(self, ator: Ator, obj: T) -> tuple[T, list[Problema]]:
        """Grava registro novo. Devolve (registro, alertas). Reenvio idêntico não duplica."""
        if isinstance(obj, E.Diagnostico):
            raise ErroGaema("diagnóstico só é gravado pelo motor de protocolo (Nucleo.computar_diagnostico)")
        if isinstance(obj, E.Relatorio):
            raise ErroGaema("relatório só é gravado na emissão (Nucleo.emitir_relatorio)")
        if isinstance(obj, E.Evidencia):
            raise ErroGaema("evidência só é gravada com o arquivo (Nucleo.registrar_evidencia)")
        return self._registrar(ator, obj)

    def _registrar(self, ator: Ator, obj: T) -> tuple[T, list[Problema]]:
        tipo = type(obj).__name__
        self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], tipo, obj.id)
        campo = AUTORIA.get(type(obj))
        preencher = {campo: ator.id} if campo and getattr(obj, campo) == "" else {}
        obj = dataclasses.replace(obj, criado_por=ator.id, **preencher)  # autoria vem do login
        if isinstance(obj, E.CampanhaVistoria) and self._so_tecnico(ator):
            self._exigir_vistoria_da_equipe(ator, obj)
        try:
            if self.modo == "central" and isinstance(obj, TIPOS_DE_CAMPO):
                demanda = self._contexto_de_coleta(ator, obj)
                if self.repo.achar_por_chave_ou_id(type(obj), obj.id, getattr(obj, "chave_idempotencia", "")) is None:
                    self._exigir_estado_de_coleta(demanda)   # reenvio idempotente continua valendo depois
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
        except ErroGaema as e:
            if self.modo == "central" and isinstance(obj, TIPOS_DE_CAMPO):
                self._auditar_recusa(ator, "CRIACAO_RECUSADA", tipo, obj.id, e)
            raise
        return gravado, alertas

    def atualizar(self, ator: Ator, obj: T, versao_lida: int) -> tuple[T, list[Problema]]:
        """Grava nova versão. Leitura, conferências e gravação na mesma transação."""
        tipo = type(obj).__name__
        self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], tipo, obj.id)
        try:
            if self.modo == "central" and isinstance(obj, TIPOS_DE_CAMPO):
                gravado = self.repo.obter(type(obj), obj.id)
                self._exigir_vinculo_inalterado(gravado, obj)
                self._exigir_estado_de_coleta(self._contexto_de_coleta(ator, gravado))
            with self.repo.transacao():
                if isinstance(obj, IMUTAVEIS):
                    raise ErroGaema(f"{tipo} é imutável: registre nova versão vinculada à anterior")
                if isinstance(obj, E.PedidoAcesso):
                    raise ErroGaema("pedido de acesso só muda por decisão do administrador (Nucleo.decidir_acesso_teste)")
                original = self.repo.obter(type(obj), obj.id)
                if original.versao != versao_lida:
                    raise ConflitoAtualizacao(
                        f"{tipo} {obj.id}: alterado por outra pessoa (versão lida {versao_lida}, "
                        f"atual {original.versao}). Recarregue e refaça a alteração.")
                if isinstance(obj, E.Demanda) and (obj.estado, obj.estado_anterior) != (
                        original.estado, original.estado_anterior):
                    raise ErroGaema("estado da Demanda só muda por transição (Nucleo.transitar)")
                self._exigir_identidade_inalterada(original, obj)
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
                self._exigir_equipe_do_tecnico(ator, atual, destino)
                contexto = montar_contexto(self.repo, atual, ator, self.trilha.eventos)
                nova = maquina.transitar(atual, destino, ator, contexto=contexto,
                                         trilha=self.trilha, motivo=motivo)
                return self.repo.atualizar(nova, atual.versao)
        except (AcessoNegado, TransicaoInvalida, ConflitoAtualizacao) as e:
            self._auditar_recusa(ator, "TRANSICAO_RECUSADA", "Demanda", demanda_id, e,
                                 estado_destino=destino.value)
            raise

    def _membros_da_demanda(self, demanda: E.Demanda) -> set[str]:
        equipes = {demanda.equipe_id} | {c.equipe_id for c in self.repo.listar(E.CampanhaVistoria)
                                        if c.demanda_id == demanda.id}
        membros: set[str] = set()
        for eid in equipes - {""}:
            try:
                membros |= {m.usuario_id for m in self.repo.obter(E.Equipe, eid).membros}
            except RegistroNaoEncontrado:
                pass
        return membros

    @staticmethod
    def _so_tecnico(ator: Ator) -> bool:
        return Papel.TECNICO_CAMPO in ator.papeis and not (ator.papeis - {Papel.TECNICO_CAMPO})

    # Tipos cuja leitura pelo técnico é limitada às demandas da própria equipe.
    _TIPOS_POR_DEMANDA = (E.Demanda, E.CampanhaVistoria, E.PontoAmostral, E.Observacao, E.MedicaoPenetracao,
                          E.Evidencia, E.Relatorio)

    def _demanda_de(self, obj) -> str:
        if isinstance(obj, E.Demanda):
            return obj.id
        if isinstance(obj, (E.CampanhaVistoria, E.Relatorio)):
            return obj.demanda_id
        return self._demanda_da_coleta(obj)

    def _demandas_da_equipe(self, ator: Ator) -> set[str]:
        return {d.id for d in self.repo.listar(E.Demanda) if ator.id in self._membros_da_demanda(d)}

    def _exigir_demanda_visivel(self, ator: Ator, demanda_id: str, entidade: str, entidade_id: str) -> None:
        """Quem só é técnico de campo lê apenas demandas (e seus registros) da própria equipe."""
        if self._so_tecnico(ator) and demanda_id not in self._demandas_da_equipe(ator):
            e = AcessoNegado("técnico de campo só vê demanda da própria equipe")
            self._auditar_recusa(ator, "ACESSO_NEGADO", entidade, entidade_id, e)
            raise e

    def _exigir_equipe_do_tecnico(self, ator: Ator, demanda: E.Demanda, destino: Estado) -> None:
        """Quem só pode mover a demanda como técnico de campo precisa ser da equipe dela (ou de uma campanha dela)."""
        t = maquina.TABELA.get((demanda.estado, destino))
        if t is not None and (ator.papeis & t.papeis) == {Papel.TECNICO_CAMPO} and \
                ator.id not in self._membros_da_demanda(demanda):
            raise AcessoNegado("técnico de campo só move demanda da própria equipe")

    def _exigir_vistoria_da_equipe(self, ator: Ator, campanha: E.CampanhaVistoria) -> None:
        """Técnico de campo só agenda vistoria de demanda da própria equipe, com a equipe da demanda."""
        try:
            demanda = self.repo.obter(E.Demanda, campanha.demanda_id)
            equipe = self.repo.obter(E.Equipe, demanda.equipe_id) if demanda.equipe_id else None
        except RegistroNaoEncontrado:
            demanda = equipe = None
        if equipe is None or campanha.equipe_id != equipe.id or ator.id not in {m.usuario_id for m in equipe.membros}:
            e = AcessoNegado("técnico de campo só agenda vistoria de demanda da própria equipe")
            self._auditar_recusa(ator, "ACESSO_NEGADO", "CampanhaVistoria", campanha.id, e)
            raise e

    def registrar_em_lote(self, ator: Ator, objetos: list) -> list:
        """Grava vários registros novos numa transação só (ex.: fonte, área candidata, alerta, área de interesse e
        demanda criadas juntas pela interface). Se um falhar, nada fica gravado; cada criação é auditada."""
        for obj in objetos:
            self._exigir(ator, ACAO_DE_ESCRITA[type(obj)], type(obj).__name__, obj.id)
            if isinstance(obj, (E.Diagnostico, E.Relatorio, E.Evidencia, *TIPOS_DE_CAMPO)):
                raise ErroGaema(f"{type(obj).__name__} não entra por gravação em lote")
        try:
            with self.repo.transacao():
                return [self._registrar(ator, obj)[0] for obj in objetos]
        except ErroGaema as e:                 # a recusa de dentro voltou com a transação; registra a do lote
            self._auditar_recusa(ator, "CRIACAO_RECUSADA", "+".join(type(o).__name__ for o in objetos)[:120],
                                 objetos[-1].id if objetos else "*", e)
            raise

    ESTADOS_SEM_EQUIPE_FIXA = (Estado.CANDIDATA, Estado.ALERTA, Estado.EM_TRIAGEM, Estado.DEMANDA_ABERTA, Estado.REABERTA)

    def definir_equipe(self, ator: Ator, demanda_id: str, equipe_id: str) -> E.Demanda:
        """Coordenador escolhe a equipe da demanda antes da atribuição (a transição para ATRIBUIDA confere a equipe)."""
        self._exigir(ator, Acao.GERIR_EQUIPE, "Demanda", demanda_id)
        d = self.repo.obter(E.Demanda, demanda_id)
        self.repo.obter(E.Equipe, equipe_id)                          # equipe tem de existir
        if d.estado not in self.ESTADOS_SEM_EQUIPE_FIXA:
            e = ErroGaema("a equipe só é escolhida antes da atribuição (até a demanda aberta ou reaberta)")
            self._auditar_recusa(ator, "ATUALIZACAO_RECUSADA", "Demanda", demanda_id, e)
            raise e
        return self.atualizar(ator, dataclasses.replace(d, equipe_id=equipe_id), d.versao)[0]   # confere a versão

    # ------------------------------------------------------------ usuários de TESTE (sem autenticação real, R-31)

    def pedir_acesso_teste(self, ator: Ator, identificador: str, papel: Papel, motivo: str, *,
                           reservados: frozenset[str] = frozenset()) -> E.PedidoAcesso:
        """Registra pedido de usuário de teste (PENDENTE). `reservados`: identificadores já usados pela interface."""
        self._exigir(ator, Acao.PEDIR_ACESSO_TESTE, "PedidoAcesso", "*")
        identificador = (identificador or "").strip().lower()
        pedidos = self.repo.listar(E.PedidoAcesso)
        if identificador in reservados or any(p.identificador == identificador and p.situacao is not
                                              SituacaoPedidoAcesso.REJEITADO for p in pedidos):
            raise ErroGaema("identificador já usado ou já pedido; escolha outro")
        if sum(p.situacao is SituacaoPedidoAcesso.PENDENTE for p in pedidos) >= \
                int(parametro("interface_pedidos_acesso_pendentes_max")):
            raise ErroGaema("há pedidos demais esperando decisão; peça ao administrador que decida os pendentes")
        pedido = E.PedidoAcesso(identificador=identificador, papel=papel, motivo=sanear_texto(motivo or "").strip()[:300],
                                sintetico=True)
        return self._registrar(ator, pedido)[0]

    def decidir_acesso_teste(self, ator: Ator, pedido_id: str, aprovar: bool, motivo: str) -> E.PedidoAcesso:
        """Administrador aprova ou rejeita (com motivo). Decisão não volta atrás; auditada."""
        self._exigir(ator, Acao.DECIDIR_ACESSO_TESTE, "PedidoAcesso", pedido_id)
        motivo = sanear_texto(motivo or "").strip()[:300]
        try:
            with self.repo.transacao():
                atual = self.repo.obter(E.PedidoAcesso, pedido_id)
                if atual.situacao is not SituacaoPedidoAcesso.PENDENTE:
                    raise ErroGaema("pedido já decidido; um novo pedido é um novo registro")
                agora_ = datetime.now(timezone.utc)
                novo = dataclasses.replace(
                    atual, situacao=SituacaoPedidoAcesso.APROVADO if aprovar else SituacaoPedidoAcesso.REJEITADO,
                    decidido_por=ator.id, motivo_decisao=motivo, decidido_em=agora_, atualizado_em=agora_)
                exigir_sem_erros(validar(novo))
                gravado = self.repo.atualizar(novo, atual.versao)
                self.trilha.registrar(ator, "ACESSO_TESTE_APROVADO" if aprovar else "ACESSO_TESTE_REJEITADO",
                                      "PedidoAcesso", pedido_id, motivo=motivo,
                                      detalhes={"papel": atual.papel.value})
        except (ErroGaema, RegistroNaoEncontrado) as e:
            self._auditar_recusa(ator, "DECISAO_ACESSO_RECUSADA", "PedidoAcesso", pedido_id, e)
            raise
        return gravado

    def acessos_de_teste_aprovados(self, ator: Ator) -> list[tuple[str, Papel]]:
        """(identificador, papel) dos pedidos aprovados, para a lista de entrada da interface. Sem motivo nem decisor."""
        self._exigir(ator, Acao.PEDIR_ACESSO_TESTE, "PedidoAcesso", "*")
        return [(p.identificador, p.papel) for p in self.repo.listar(E.PedidoAcesso)
                if p.situacao is SituacaoPedidoAcesso.APROVADO]

    # ------------------------------------------------------------ protocolo e diagnóstico

    def publicar_protocolo(self, ator: Ator, dados: dict) -> E.VersaoProtocolo:
        """Grava uma definição de protocolo como VersaoProtocolo imutável (idempotente)."""
        definicao = carregar_definicao(dados)
        texto, hash_def = canonizar(dados)
        existente = next((v for v in self.repo.listar(E.VersaoProtocolo) if v.hash_definicao == hash_def), None)
        if existente:
            return existente
        vp = E.VersaoProtocolo(codigo=definicao.codigo, versao_semantica=definicao.versao, modo=definicao.modo,
                               rotulo=definicao.rotulo, definicao_json=texto, hash_definicao=hash_def,
                               proveniencia=definicao.proveniencia)
        return self._registrar(ator, vp)[0]

    def _entradas_da_campanha(self, campanha_id: str) -> dict:
        pontos = [p for p in self.repo.listar(E.PontoAmostral) if p.campanha_id == campanha_id]
        ids = {p.id for p in pontos}
        return entradas_de(pontos,
                           [o for o in self.repo.listar(E.Observacao) if o.ponto_id in ids],
                           [m for m in self.repo.listar(E.MedicaoPenetracao) if m.ponto_id in ids],
                           [e for e in self.repo.listar(E.Evidencia) if e.campanha_id == campanha_id])

    def computar_diagnostico(self, ator: Ator, demanda_id: str, campanha_id: str) -> E.Diagnostico:
        """Roda o motor sobre os dados gravados e grava o Diagnostico (imutável, com fotografia das entradas)."""
        self._exigir(ator, Acao.COMPUTAR_DIAGNOSTICO, "Diagnostico", demanda_id)
        demanda = self.repo.obter(E.Demanda, demanda_id)
        campanha = self.repo.obter(E.CampanhaVistoria, campanha_id)
        if demanda.estado is not Estado.EM_VALIDACAO:
            raise ErroGaema("diagnóstico só é computado com a demanda EM_VALIDACAO")
        if campanha.demanda_id != demanda.id:
            raise ErroGaema("campanha não pertence a esta demanda")
        vp = self.repo.obter(E.VersaoProtocolo, campanha.versao_protocolo_id)
        exigir_sem_erros(validar(vp))  # confere integridade da definição gravada
        entradas = self._entradas_da_campanha(campanha.id)
        if not entradas["pontos"]:
            raise ErroGaema("campanha sem pontos amostrais")
        resultado = avaliar(carregar_definicao(json.loads(vp.definicao_json)), vp.hash_definicao, entradas)
        anteriores = [d for d in self.repo.listar(E.Diagnostico) if d.demanda_id == demanda.id]
        substituidos = {d.substitui_diagnostico_id for d in anteriores}
        vigente = next((d for d in anteriores if d.id not in substituidos), None)
        diag = E.Diagnostico(
            demanda_id=demanda.id, campanha_id=campanha.id, versao_protocolo_id=vp.id,
            hash_definicao_protocolo=vp.hash_definicao, hash_entradas=resultado.hash_entradas,
            resultado_descritivo=resultado.texto_descritivo(), categoria_descritiva=resultado.categoria_resumo,
            regras_disparadas=resultado.regras_disparadas, limitacoes="\n".join(resultado.limitacoes),
            hipoteses_alternativas="\n".join(resultado.hipoteses_alternativas),
            rotulo_validade=vp.rotulo or "MODO DESCRITIVO: sem classificação",
            substitui_diagnostico_id=vigente.id if vigente else None,
            entradas_canonicas=json_canonico(entradas), resultado_json=resultado_para_json(resultado))
        return self._registrar(ator, diag)[0]

    def reproduzir_diagnostico(self, ator: Ator, diagnostico_id: str) -> dict:
        """Recalcula com a versão de protocolo e as entradas gravadas; compara com o resultado gravado."""
        self._exigir(ator, Acao.LER, "Diagnostico", diagnostico_id)
        d = self.repo.obter(E.Diagnostico, diagnostico_id)
        vp = self.repo.obter(E.VersaoProtocolo, d.versao_protocolo_id)
        entradas = json.loads(d.entradas_canonicas)
        r = avaliar(carregar_definicao(json.loads(vp.definicao_json)), vp.hash_definicao, entradas)
        divergencias = []
        if vp.hash_definicao != d.hash_definicao_protocolo:
            divergencias.append("hash da definição do protocolo")
        if r.hash_entradas != d.hash_entradas:
            divergencias.append("hash das entradas")
        if resultado_para_json(r) != d.resultado_json:
            divergencias.append("resultado do motor")
        if (r.texto_descritivo(), r.categoria_resumo, r.regras_disparadas) != (
                d.resultado_descritivo, d.categoria_descritiva, d.regras_disparadas):
            divergencias.append("texto, categoria ou regras gravados")
        atuais = self._entradas_da_campanha(d.campanha_id)
        saida = {"reproduzido": not divergencias, "divergencias": divergencias,
                 "entradas_atuais_iguais": hash_entradas(atuais) == d.hash_entradas}
        with self.repo.transacao():
            self.trilha.registrar(ator, "REPRODUCAO_DIAGNOSTICO", "Diagnostico", d.id,
                                  detalhes={"reproduzido": saida["reproduzido"],
                                            "entradas_atuais_iguais": saida["entradas_atuais_iguais"]})
        return saida

    # ------------------------------------------------------------ evidências

    def _caminho_evidencia(self, sha256: str) -> Path:
        return self.saida / "evidencias" / sha256

    def registrar_evidencia(self, ator: Ator, evidencia: E.Evidencia, conteudo: bytes) -> E.Evidencia:
        """Valida o arquivo, guarda o original (endereçado pelo hash, nunca sobrescrito) e registra."""
        self._exigir(ator, Acao.REGISTRAR_EVIDENCIA, "Evidencia", evidencia.id)
        r = validar_anexo(conteudo, evidencia.nome_arquivo_original, evidencia.tipo_mime)
        problemas = list(r.problemas)
        if evidencia.sha256 and evidencia.sha256 != r.sha256:
            problemas.append(erro("HASH_DIVERGENTE", "sha256", "hash informado difere do arquivo recebido"))
        if problemas:
            falha = ValidacaoFalhou(problemas)
            self._auditar_recusa(ator, "ANEXO_RECUSADO", "Evidencia", evidencia.id, falha)
            raise falha
        evidencia = dataclasses.replace(evidencia, sha256=r.sha256, tamanho_bytes=r.tamanho_bytes,
                                        armazenamento_ref=f"evidencias/{r.sha256}", criado_por=ator.id,
                                        registrado_por=evidencia.registrado_por or ator.id)
        # Valida o registro ANTES de tocar no disco: recusa não deixa arquivo órfão.
        exigir_sem_erros(self._regras_de_criacao(ator, evidencia) + validar(evidencia))
        caminho = self._caminho_evidencia(r.sha256)
        ja_existia = caminho.exists()
        if ja_existia:
            if hashlib.sha256(caminho.read_bytes()).hexdigest() != r.sha256:
                raise ErroGaema(f"arquivo guardado {caminho.name} não confere com o hash; verificar armazenamento")
        else:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = caminho.with_suffix(".parcial")
            temporario.write_bytes(conteudo)
            os.replace(temporario, caminho)
        try:
            return self._registrar(ator, evidencia)[0]
        except BaseException:
            if not ja_existia:
                caminho.unlink(missing_ok=True)
            raise

    def verificar_evidencia(self, ator: Ator, evidencia_id: str) -> bool:
        """Confere se o arquivo guardado ainda tem o hash registrado."""
        self._exigir(ator, Acao.LER_RESTRITO, "Evidencia", evidencia_id)
        ev = self.repo.obter(E.Evidencia, evidencia_id)
        caminho = self._caminho_evidencia(ev.sha256)  # caminho derivado do hash, nunca do texto gravado
        integro = (ev.armazenamento_ref == f"evidencias/{ev.sha256}" and caminho.exists()
                   and hashlib.sha256(caminho.read_bytes()).hexdigest() == ev.sha256)
        with self.repo.transacao():
            self.trilha.registrar(ator, "VERIFICACAO_EVIDENCIA", "Evidencia", ev.id, detalhes={"integro": integro})
        return integro

    # ------------------------------------------------------------ relatório

    def emitir_relatorio(self, ator: Ator, demanda_id: str, formato: FormatoRelatorio = FormatoRelatorio.HTML,
                         *, motivo_reemissao: str = "", gerado_em: datetime | None = None
                         ) -> tuple[E.Relatorio, Path]:
        """Gera o arquivo, grava hash e registro. Reemissão = nova versão vinculada, com motivo."""
        self._exigir(ator, Acao.EMITIR_RELATORIO, "Relatorio", demanda_id)
        demanda = self.repo.obter(E.Demanda, demanda_id)
        if demanda.estado not in ESTADOS_COM_RELATORIO:
            raise ErroGaema("relatório só é emitido depois de DIAGNOSTICO_EMITIDO")
        anteriores = sorted((r for r in self.repo.listar(E.Relatorio)
                             if r.demanda_id == demanda.id and r.formato is formato), key=lambda r: r.numero_versao)
        if anteriores and len(motivo_reemissao.strip()) < 10:
            raise ErroGaema("reemissão exige motivo (mínimo 10 caracteres)")
        numero = anteriores[-1].numero_versao + 1 if anteriores else 1
        gerado_em = gerado_em or datetime.now(timezone.utc)
        eventos = self.trilha.eventos
        dados = montagem.montar(self.repo, demanda.id, numero_versao=numero, gerado_em=gerado_em,
                                gerado_por=ator.id, eventos=eventos, motivo_reemissao=motivo_reemissao.strip(),
                                anteriores=anteriores)
        diag = montagem.diagnostico_vigente(self.repo, demanda.id)
        revisao = montagem.revisao_aprovada(self.repo, demanda.id, diag.id, eventos)
        conteudo = (relatorio_pdf if formato is FormatoRelatorio.PDF else relatorio_html).renderizar(dados)
        pasta_relatorios = (self.saida / "relatorios").resolve()
        caminho = pasta_relatorios / f"relatorio-{re.sub('[^0-9a-fA-F]', '', demanda.id)[:8]}-v{numero}.{formato.value.lower()}"
        if caminho.resolve().parent != pasta_relatorios:
            raise ErroGaema("caminho do relatório fora da pasta de relatórios")
        if caminho.exists():
            raise ErroGaema(f"{caminho.name} já existe; relatório emitido não é sobrescrito")
        rel = E.Relatorio(demanda_id=demanda.id, numero_versao=numero, diagnostico_id=diag.id,
                          revisao_id=revisao.id, versao_protocolo_id=diag.versao_protocolo_id, formato=formato,
                          hash_conteudo=hashlib.sha256(conteudo).hexdigest(), gerado_por=ator.id,
                          gerado_em=gerado_em, substitui_relatorio_id=anteriores[-1].id if anteriores else None,
                          motivo_reemissao=motivo_reemissao.strip())
        # Arquivo primeiro (temporário + renomeação atômica), registro depois; se o registro falhar,
        # o arquivo é removido: nunca há registro sem arquivo nem arquivo sem registro.
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(caminho.suffix + ".parcial")
        temporario.write_bytes(conteudo)
        os.replace(temporario, caminho)
        try:
            gravado = self._registrar(ator, rel)[0]
        except BaseException:
            caminho.unlink(missing_ok=True)
            raise
        return gravado, caminho

    # ------------------------------------------------------------ sincronização (lado central)

    def _demanda_da_coleta(self, obj) -> str:
        """Demanda a que um registro de coleta pertence (vazio se a cadeia não está na central)."""
        try:
            if isinstance(obj, E.Evidencia):
                return self.repo.obter(E.CampanhaVistoria, obj.campanha_id).demanda_id
            ponto_id = obj.id if isinstance(obj, E.PontoAmostral) else obj.ponto_id
            ponto = obj if isinstance(obj, E.PontoAmostral) else self.repo.obter(E.PontoAmostral, ponto_id)
            return self.repo.obter(E.CampanhaVistoria, ponto.campanha_id).demanda_id
        except RegistroNaoEncontrado:
            return ""

    def _contexto_de_coleta(self, ator: Ator, obj) -> E.Demanda:
        """Confere que os registros de origem existem na central e que o usuário é da equipe da campanha.
        Devolve a demanda. Levanta ErroGaema (nada é gravado)."""
        def achar(cls, id_, nome):
            try:
                return self.repo.obter(cls, id_)
            except RegistroNaoEncontrado:
                raise ErroGaema(f"{nome} de origem não encontrado(a) na central; envie os registros de origem antes") \
                    from None
        if isinstance(obj, E.PontoAmostral):
            campanha = achar(E.CampanhaVistoria, obj.campanha_id, "campanha")
        elif isinstance(obj, (E.Observacao, E.MedicaoPenetracao)):
            campanha = achar(E.CampanhaVistoria, achar(E.PontoAmostral, obj.ponto_id, "ponto").campanha_id, "campanha")
        else:  # Evidencia
            campanha = achar(E.CampanhaVistoria, obj.campanha_id, "campanha")
            if obj.ponto_id and achar(E.PontoAmostral, obj.ponto_id, "ponto").campanha_id != campanha.id:
                raise ErroGaema("o ponto da evidência pertence a outra campanha")
            if obj.observacao_id:
                obs = achar(E.Observacao, obj.observacao_id, "observação")
                if achar(E.PontoAmostral, obs.ponto_id, "ponto").campanha_id != campanha.id:
                    raise ErroGaema("a observação da evidência pertence a outra campanha")
        equipe = achar(E.Equipe, campanha.equipe_id, "equipe")
        if not any(m.usuario_id == ator.id for m in equipe.membros):
            raise ErroGaema("o usuário não faz parte da equipe desta campanha")
        return achar(E.Demanda, campanha.demanda_id, "demanda")

    @staticmethod
    def _exigir_identidade_inalterada(gravado, obj) -> None:
        """Autoria e chave de envio não mudam em nenhuma correção (atualizar ou "aceitar o aparelho")."""
        campo_autoria = AUTORIA.get(type(obj))
        if campo_autoria and getattr(obj, campo_autoria) != getattr(gravado, campo_autoria):
            raise ErroGaema("autoria do registro não pode ser alterada")
        if getattr(obj, "chave_idempotencia", "") != getattr(gravado, "chave_idempotencia", ""):
            raise ErroGaema("chave de envio não pode ser alterada")

    @staticmethod
    def _exigir_vinculo_inalterado(gravado, obj) -> None:
        """Correção de dado de campo não muda a que ponto/campanha ele pertence (senão sairia de uma demanda para outra)."""
        for campo in VINCULOS.get(type(obj), ()):
            if getattr(obj, campo) != getattr(gravado, campo):
                raise ErroGaema(f"o vínculo do registro ({campo}) não pode ser alterado; registre um dado novo")

    @staticmethod
    def _exigir_estado_de_coleta(demanda: E.Demanda) -> None:
        if demanda.estado not in ESTADOS_DE_COLETA:
            esperados = ", ".join(e.value for e in ESTADOS_DE_COLETA)
            raise ErroGaema(f"demanda em estado {demanda.estado.value} não aceita dado novo de campo "
                            f"(estados de coleta: {esperados})")

    def _recusar_sincronizacao(self, ator: Ator, item: ItemSincronizacao, e: Exception) -> None:
        self._auditar_recusa(ator, "SINCRONIZACAO_RECUSADA", item.tipo, item.entidade_id, e)

    def receber_sincronizacao(self, ator: Ator, item: ItemSincronizacao,
                              conteudo: bytes | None = None) -> ResultadoSincronizacao:
        """Aplica um item vindo do dispositivo. Reenvio idêntico não duplica; versões divergentes
        não são sobrescritas: viram conflito (as duas versões ficam guardadas) e a Demanda vai a
        CONFLITO_SINCRONIZACAO quando estava aguardando sincronização."""
        if self.modo != "central":
            raise ErroGaema("só a instalação central recebe sincronização")
        self._exigir(ator, Acao.SINCRONIZAR, item.tipo, item.entidade_id)
        cls = TIPOS_SINCRONIZAVEIS.get(item.tipo)
        try:
            if cls is None:
                raise ErroGaema(f"tipo {item.tipo!r} não é sincronizável")
            if item.operacao not in ("CRIAR", "ATUALIZAR"):
                raise ErroGaema(f"operação {item.operacao!r} desconhecida")
            if item.operacao == "ATUALIZAR" and cls is E.Evidencia:
                raise ErroGaema("Evidencia é imutável: correção é novo registro, não atualização")
            if sha256_texto(json_canonico(item.dados)) != item.hash_dados:
                raise ErroGaema("item alterado em trânsito (hash não confere)")
            try:
                obj = de_dict(cls, item.dados)
            except (ValueError, TypeError, KeyError) as e:
                raise ErroGaema(f"item malformado: {type(e).__name__}") from e
            if obj.id != item.entidade_id:
                raise ErroGaema("identificador do item não confere com o registro")
            obj = dataclasses.replace(obj, status_sincronizacao=StatusSincronizacao.SINCRONIZADO)
            campo_autoria = AUTORIA.get(cls)
            if campo_autoria and getattr(obj, campo_autoria) not in ("", ator.id):
                raise ErroGaema("autoria do registro deve ser o próprio usuário que envia")
            demanda = self._contexto_de_coleta(ator, obj)
        except ErroGaema as e:
            self._recusar_sincronizacao(ator, item, e)
            raise
        if item.operacao == "CRIAR":
            return self._sincronizar_criacao(ator, item, cls, obj, conteudo, demanda)
        return self._sincronizar_atualizacao(ator, item, cls, obj, demanda)

    def _sincronizar_criacao(self, ator, item, cls, obj, conteudo, demanda) -> ResultadoSincronizacao:
        existente = self._existente_por_chave_ou_id(cls, obj)
        if existente is not None:
            try:
                self._exigir_vinculo_inalterado(existente, obj)
            except ErroGaema as e:
                self._recusar_sincronizacao(ator, item, e)
                raise
        if existente is not None and existente.id == obj.id and any(
                h.versao == 1 and self._conteudo_comparavel(h) == self._conteudo_comparavel(obj)
                for h in self.repo.historico(cls, existente.id)):
            # reenvio da criação original, ainda que a central já tenha alterado o registro depois
            with self.repo.transacao():
                self.trilha.registrar(ator, "REENVIO_IDEMPOTENTE", item.tipo, obj.id,
                                      detalhes={"versao_central": existente.versao})
            return ResultadoSincronizacao.REENVIO_IDEMPOTENTE
        if existente is None:
            try:
                self._exigir_estado_de_coleta(demanda)
            except ErroGaema as e:
                self._recusar_sincronizacao(ator, item, e)
                raise
        try:
            if isinstance(obj, E.Evidencia):
                if conteudo is None:
                    raise ErroGaema("evidência sem o arquivo")
                self.registrar_evidencia(ator, obj, conteudo)
            else:
                self._registrar(ator, obj)
        except ConflitoIdempotencia:
            existente = self._existente_por_chave_ou_id(cls, obj)
            return self._registrar_conflito(ator, item, cls, obj, existente, versao_base=0)
        ultimo = self.trilha.ultimo_evento()
        return (ResultadoSincronizacao.REENVIO_IDEMPOTENTE if ultimo and ultimo.acao == "REENVIO_IDEMPOTENTE"
                else ResultadoSincronizacao.APLICADO)

    def _existente_por_chave_ou_id(self, cls, obj):
        return self.repo.achar_por_chave_ou_id(cls, obj.id, obj.chave_idempotencia)

    @staticmethod
    def _conteudo_comparavel(registro) -> str:
        return json_canonico({k: v for k, v in para_dict(registro).items() if k not in _META})

    def _sincronizar_atualizacao(self, ator, item, cls, obj, demanda) -> ResultadoSincronizacao:
        try:
            atual = self.repo.obter(cls, obj.id)
            self._exigir_vinculo_inalterado(atual, obj)
        except ErroGaema as e:
            self._recusar_sincronizacao(ator, item, e)
            raise
        if atual.versao == item.versao_base:
            try:
                self._exigir_estado_de_coleta(demanda)
            except ErroGaema as e:
                self._recusar_sincronizacao(ator, item, e)
                raise
            try:
                self.atualizar(ator, obj, item.versao_base)
                return ResultadoSincronizacao.APLICADO
            except ConflitoAtualizacao:
                atual = self.repo.obter(cls, obj.id)  # alguém gravou entre a leitura e a gravação
        alvo = self._conteudo_comparavel(obj)
        if any(self._conteudo_comparavel(h) == alvo for h in self.repo.historico(cls, obj.id)
               if h.versao > item.versao_base):
            with self.repo.transacao():
                self.trilha.registrar(ator, "REENVIO_IDEMPOTENTE", item.tipo, obj.id,
                                      detalhes={"versao_base": item.versao_base})
            return ResultadoSincronizacao.REENVIO_IDEMPOTENTE
        return self._registrar_conflito(ator, item, cls, obj, atual, versao_base=item.versao_base)

    def _registrar_conflito(self, ator, item, cls, obj, atual, *, versao_base: int) -> ResultadoSincronizacao:
        demanda_id = self._demanda_da_coleta(obj)
        if demanda_id:
            try:   # depois da coleta, versão divergente não vira conflito "aceitável": é recusada
                self._exigir_estado_de_coleta(self.repo.obter(E.Demanda, demanda_id))
            except ErroGaema as e:
                self._recusar_sincronizacao(ator, item, e)
                raise
        with self.repo.transacao():
            conflito_id, novo = self.repo.registrar_conflito(
                tipo=item.tipo, entidade_id=atual.id if atual else obj.id, demanda_id=demanda_id,
                versao_base=versao_base, versao_central=atual.versao if atual else 0,
                hash_central=sha256_texto(self._conteudo_comparavel(atual)) if atual else "",
                dados_dispositivo=json_canonico(item.dados), hash_dispositivo=item.hash_dados,
                enviado_por=ator.id)
            if novo:
                self.trilha.registrar(ator, "CONFLITO_SINCRONIZACAO", item.tipo, obj.id,
                                      detalhes={"conflito_id": conflito_id, "versao_base": versao_base,
                                                "versao_central": atual.versao if atual else 0})
        # A transição é tentada fora da transação do registro: se falhar, o conflito já está gravado e
        # auditado, e um reenvio tenta de novo (o conflito aberto bloqueia a validação de qualquer forma).
        if demanda_id and self.repo.obter(E.Demanda, demanda_id).estado is Estado.AGUARDANDO_SINCRONIZACAO:
            try:
                self.transitar(ATOR_SINCRONIZACAO, demanda_id, Estado.CONFLITO_SINCRONIZACAO,
                               motivo="Versões divergentes entre dispositivo e central.")
            except (AcessoNegado, TransicaoInvalida, ConflitoAtualizacao):
                pass  # já auditado por transitar
        return ResultadoSincronizacao.CONFLITO

    def resolver_conflito_sincronizacao(self, ator: Ator, conflito_id: str, decisao: str, motivo: str) -> None:
        """Decisão humana (COORDENADOR). MANTER_CENTRAL descarta o efeito da versão do dispositivo (que
        continua guardada no conflito); ACEITAR_DISPOSITIVO grava o conteúdo do dispositivo como nova versão."""
        self._exigir(ator, Acao.RESOLVER_CONFLITO_SINCRONIZACAO, "ConflitoSincronizacao", conflito_id)
        try:
            if decisao not in DECISOES_CONFLITO:
                raise ErroGaema(f"decisão deve ser uma de {DECISOES_CONFLITO}")
            if len(motivo.strip()) < 10:
                raise ErroGaema("resolução exige motivo (mínimo 10 caracteres)")
            with self.repo.transacao():
                c = self.repo.obter_conflito(conflito_id)
                if c["situacao"] != "ABERTO":
                    raise ErroGaema("conflito já resolvido")
                if decisao == "ACEITAR_DISPOSITIVO":
                    cls = TIPOS_SINCRONIZAVEIS[c["tipo"]]
                    if cls is E.Evidencia:
                        raise ErroGaema("Evidencia é imutável: só MANTER_CENTRAL")
                    dados = json.loads(c["dados_dispositivo"])
                    if dados["id"] != c["entidade_id"]:
                        raise ErroGaema("o registro do dispositivo tem outro identificador; só MANTER_CENTRAL")
                    atual = self.repo.obter(cls, c["entidade_id"])
                    if atual.versao != c["versao_central"]:
                        raise ErroGaema(
                            f"o registro mudou na central depois do conflito (versão {c['versao_central']} → "
                            f"{atual.versao}); aceitar o aparelho apagaria essa alteração do estado corrente. "
                            "Use MANTER_CENTRAL ou peça novo envio a partir da versão atual")
                    obj = dataclasses.replace(de_dict(cls, dados), criado_por=atual.criado_por,
                                              criado_em=atual.criado_em,
                                              status_sincronizacao=StatusSincronizacao.SINCRONIZADO)
                    self._exigir_vinculo_inalterado(atual, obj)
                    self._exigir_identidade_inalterada(atual, obj)
                    demanda_id = self._demanda_da_coleta(atual)
                    if demanda_id:
                        self._exigir_estado_de_coleta(self.repo.obter(E.Demanda, demanda_id))
                    exigir_sem_erros(validar(obj))
                    self.repo.atualizar(obj, atual.versao)
                self.repo.resolver_conflito(conflito_id, decisao=decisao, resolvido_por=ator.id,
                                            motivo=motivo.strip())
                self.trilha.registrar(ator, "CONFLITO_SINCRONIZACAO_RESOLVIDO", c["tipo"], c["entidade_id"],
                                      motivo=motivo.strip(), detalhes={
                                          "conflito_id": conflito_id, "decisao": decisao,
                                          "versao_central_no_conflito": c["versao_central"]})
        except ErroGaema as e:
            self._auditar_recusa(ator, "RESOLUCAO_CONFLITO_RECUSADA", "ConflitoSincronizacao", conflito_id, e)
            raise

    def consultar_decisoes_conflito(self, ator: Ator, consultas: list[tuple[str, str]]) -> list[DecisaoConflito]:
        """Devolve ao dispositivo o desfecho dos conflitos já RESOLVIDOS. `consultas` = (tipo, hash_dados do item
        enviado). Conflito ainda aberto, ou hash desconhecido, não aparece na resposta."""
        self._exigir(ator, Acao.SINCRONIZAR, "ConflitoSincronizacao", "*")
        if len(consultas) > 500:
            raise ErroGaema("consulta grande demais (máximo 500 itens por vez)")
        saida: list[DecisaoConflito] = []
        for tipo, hash_dados in consultas:
            linha = self.repo.conflito_por_hash(tipo, hash_dados)
            cls = TIPOS_SINCRONIZAVEIS.get(tipo)
            if not linha or linha["situacao"] != "RESOLVIDO" or cls is None:
                continue
            if linha["enviado_por"] not in ("", ator.id):   # '' = conflito anterior ao registro de origem
                continue
            try:
                atual = self.repo.obter(cls, linha["entidade_id"])
            except RegistroNaoEncontrado:
                continue
            resultante = atual.versao
            if linha["decisao"] == "ACEITAR_DISPOSITIVO":
                alvo = self._conteudo_comparavel(de_dict(cls, json.loads(linha["dados_dispositivo"])))
                resultante = next((h.versao for h in self.repo.historico(cls, atual.id)
                                   if h.versao > linha["versao_central"] and self._conteudo_comparavel(h) == alvo),
                                  atual.versao)
            saida.append(DecisaoConflito(
                conflito_id=linha["id"], tipo=tipo, entidade_id=atual.id, hash_dados=hash_dados,
                decisao=linha["decisao"], motivo=sanear_texto(linha["motivo_resolucao"]),
                versao_central=atual.versao, versao_resultante=resultante, dados_central=para_dict(atual)))
        with self.repo.transacao():
            self.trilha.registrar(ator, "CONSULTA_DECISAO_CONFLITO", "ConflitoSincronizacao", "*",
                                  detalhes={"consultados": len(consultas), "resolvidos": len(saida)})
        return saida

    # ------------------------------------------------------------ exportação

    def exportar_painel(self, ator: Ator, *, demanda_ids: list[str] | None = None,
                        gerado_em: datetime | None = None) -> dict:
        """Pacote aberto de exportação (formato próprio; ver exportacao/painel.py). Somente leitura + auditoria."""
        self._exigir(ator, Acao.EXPORTAR, "Exportacao", "painel")
        pacote = exportacao_painel.montar_pacote(self.repo, gerado_por_papeis=[p.value for p in ator.papeis],
                                                 gerado_em=gerado_em or datetime.now(timezone.utc),
                                                 demanda_ids=demanda_ids)
        with self.repo.transacao():
            self.trilha.registrar(ator, "EXPORTACAO", "Exportacao", "painel", detalhes={
                "demandas": len(pacote["demandas"]),
                "hash": hashlib.sha256(exportacao_painel.serializar(pacote)).hexdigest()})
        return pacote

    # ------------------------------------------------------------ operação (usada pela interface local)

    def listar(self, ator: Ator, cls: type[T]) -> list[T]:
        """Lista registros de um tipo. Leitura restrita é auditada uma vez por listagem (não uma por registro)."""
        restrito = cls.SENSIBILIDADE in (Sensibilidade.RESTRITA, Sensibilidade.SIGILOSA)
        self._exigir(ator, Acao.LER_RESTRITO if restrito else Acao.LER, cls.__name__, "*")
        itens = self.repo.listar(cls)
        if issubclass(cls, self._TIPOS_POR_DEMANDA) and self._so_tecnico(ator):
            visiveis = self._demandas_da_equipe(ator)
            itens = [x for x in itens if self._demanda_de(x) in visiveis]
        if restrito:
            with self.repo.transacao():
                self.trilha.registrar(ator, "LISTAGEM_RESTRITA", cls.__name__, "*", detalhes={"quantidade": len(itens)})
        return itens

    def transicoes_possiveis(self, ator: Ator, demanda_id: str) -> list[dict]:
        """Para cada destino da situação atual: se este usuário pode agora e, se não, por quê. Não altera nada."""
        self._exigir(ator, Acao.LER_RESTRITO, "Demanda", demanda_id)
        d = self.repo.obter(E.Demanda, demanda_id)
        self._exigir_demanda_visivel(ator, demanda_id, "Demanda", demanda_id)
        contexto = montar_contexto(self.repo, d, ator, self.trilha.eventos)
        saida = []
        for destino in maquina.destinos_possiveis(d.estado):
            t = maquina.TABELA[(d.estado, destino)]
            item = {"destino": destino.value, "descricao": t.descricao, "exige_motivo": t.exige_motivo,
                    "papeis": sorted(p.value for p in t.papeis), "disponivel": True, "bloqueio": ""}
            try:
                self._exigir_equipe_do_tecnico(ator, d, destino)
                maquina.avaliar(d, destino, ator, "x" * maquina.MOTIVO_MINIMO, contexto)
            except (AcessoNegado, TransicaoInvalida) as e:
                item["disponivel"], item["bloqueio"] = False, sanear_texto(str(e))[:300]
            saida.append(item)
        return saida

    def resumo_demanda(self, ator: Ator, demanda_id: str) -> dict:
        """Contagens, rótulo de validade e relatórios de uma demanda (sem geometria nem pessoas)."""
        self._exigir(ator, Acao.LER_RESTRITO, "Demanda", demanda_id)
        self._exigir_demanda_visivel(ator, demanda_id, "Demanda", demanda_id)
        pacote = exportacao_painel.montar_pacote(self.repo, gerado_por_papeis=[], gerado_em=datetime.now(timezone.utc),
                                                 demanda_ids=[demanda_id])
        if not pacote["demandas"]:
            raise RegistroNaoEncontrado(f"Demanda {demanda_id} não encontrada")
        return pacote["demandas"][0]

    def historico_de(self, ator: Ator, entidade: str, entidade_id: str, limite: int = 30) -> list[E.EventoAuditoria]:
        """Histórico de um registro. Com permissão de auditoria: todos os eventos. Sem ela: só as mudanças de
        situação, sem quem fez e sem motivo (a trilha completa é do auditor)."""
        self._exigir(ator, Acao.LER, entidade, entidade_id)
        if entidade == "Demanda":
            self._exigir_demanda_visivel(ator, entidade_id, entidade, entidade_id)
        eventos = [e for e in self.trilha.eventos if e.entidade == entidade and e.entidade_id == entidade_id]
        if not pode(ator, Acao.VERIFICAR_AUDITORIA):
            eventos = [dataclasses.replace(e, ator_id="", papeis=(), motivo="", detalhes={})
                       for e in eventos if e.acao == "TRANSICAO"]
        return eventos[-limite:]

    def eventos_recentes(self, ator: Ator, limite: int = 30) -> list[E.EventoAuditoria]:
        self._exigir(ator, Acao.VERIFICAR_AUDITORIA, "EventoAuditoria", "*")
        return list(self.trilha.eventos)[-limite:]

    def listar_conflitos(self, ator: Ator, *, apenas_abertos: bool = True) -> list[dict]:
        self._exigir(ator, Acao.RESOLVER_CONFLITO_SINCRONIZACAO, "ConflitoSincronizacao", "*")
        return self.repo.listar_conflitos(apenas_abertos=apenas_abertos)

    def comparar_conflito(self, ator: Ator, conflito_id: str) -> dict:
        """Campos que diferem entre a versão da central e a do aparelho, para o coordenador decidir."""
        self._exigir(ator, Acao.RESOLVER_CONFLITO_SINCRONIZACAO, "ConflitoSincronizacao", conflito_id)
        c = self.repo.obter_conflito(conflito_id)
        cls = TIPOS_SINCRONIZAVEIS[c["tipo"]]
        aparelho = json.loads(c["dados_dispositivo"])
        try:
            atual = self.repo.obter(cls, c["entidade_id"])
        except RegistroNaoEncontrado:
            atual = None
        central = para_dict(atual) if atual else {}
        ignorar = _META | {"id", "sintetico"}
        campos = [{"campo": k, "central": str(central.get(k, "—"))[:300], "aparelho": str(aparelho.get(k, "—"))[:300]}
                  for k in sorted(set(central) | set(aparelho)) if k not in ignorar and central.get(k) != aparelho.get(k)]
        aceitar = (atual is not None and cls is not E.Evidencia and aparelho.get("id") == c["entidade_id"]
                   and atual.versao == c["versao_central"])
        with self.repo.transacao():
            self.trilha.registrar(ator, "LEITURA_RESTRITA", "ConflitoSincronizacao", conflito_id)
        return {**{k: c[k] for k in ("id", "tipo", "entidade_id", "demanda_id", "versao_base", "versao_central",
                                     "enviado_por", "situacao", "decisao", "criado_em")},
                "versao_atual_central": atual.versao if atual else None, "campos": campos, "aceitar_possivel": aceitar}

    def abrir_relatorio(self, ator: Ator, relatorio_id: str) -> tuple[bytes, E.Relatorio]:
        """Devolve o arquivo do relatório SE ele ainda tem o hash registrado (nunca serve arquivo adulterado)."""
        rel = self.ler(ator, E.Relatorio, relatorio_id)
        pasta = (self.saida / "relatorios").resolve()
        caminho = pasta / f"relatorio-{re.sub('[^0-9a-fA-F]', '', rel.demanda_id)[:8]}-v{rel.numero_versao}.{rel.formato.value.lower()}"
        if caminho.resolve().parent != pasta or not caminho.is_file():
            raise ErroGaema("arquivo do relatório não encontrado")
        conteudo = caminho.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != rel.hash_conteudo:
            with self.repo.transacao():
                self.trilha.registrar(ator, "RELATORIO_NAO_CONFERE", "Relatorio", rel.id)
            raise ErroGaema("o arquivo do relatório não confere com o hash registrado; não será aberto")
        return conteudo, rel

    def _pasta_backups(self) -> Path:
        return self.saida / "backups"

    def listar_backups(self, ator: Ator) -> list[str]:
        self._exigir(ator, Acao.GERIR_BACKUP, "Backup", "*")
        pasta = self._pasta_backups()
        return sorted(p.name for p in pasta.iterdir() if p.is_dir()) if pasta.is_dir() else []

    def criar_backup(self, ator: Ator) -> dict:
        """Backup lógico em `saida/backups/<data-hora>` (verificado ao criar). A guarda FORA da máquina é institucional."""
        self._exigir(ator, Acao.GERIR_BACKUP, "Backup", "*")
        nome = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if (self._pasta_backups() / nome).exists():
            raise ErroGaema("já existe um backup criado neste mesmo segundo; aguarde um instante e tente de novo")
        manifesto = criar_backup_arquivos(self.repo, self.saida, self._pasta_backups() / nome)
        with self.repo.transacao():
            self.trilha.registrar(ator, "BACKUP_CRIADO", "Backup", nome,
                                  detalhes={"arquivos": len(manifesto["arquivos"]),
                                            "eventos_auditoria": manifesto["auditoria"]["eventos"]})
        return {"nome": nome, "arquivos": len(manifesto["arquivos"]), "eventos": manifesto["auditoria"]["eventos"]}

    def verificar_backup(self, ator: Ator, nome: str, ancora: dict | None = None) -> list[str]:
        self._exigir(ator, Acao.GERIR_BACKUP, "Backup", nome)
        if not re.fullmatch(r"\d{8}T\d{6}Z", nome or ""):
            raise ErroGaema("nome de backup inválido")
        problemas = verificar_backup_arquivos(self._pasta_backups() / nome, ancora)
        with self.repo.transacao():
            self.trilha.registrar(ator, "BACKUP_VERIFICADO", "Backup", nome, detalhes={"problemas": len(problemas)})
        return problemas

    # ------------------------------------------------------------ leitura

    def ler(self, ator: Ator, cls: type[T], id: str) -> T:
        restrito = cls.SENSIBILIDADE in (Sensibilidade.RESTRITA, Sensibilidade.SIGILOSA)
        self._exigir(ator, Acao.LER_RESTRITO if restrito else Acao.LER, cls.__name__, id)
        obj = self.repo.obter(cls, id)
        if isinstance(obj, self._TIPOS_POR_DEMANDA):
            self._exigir_demanda_visivel(ator, self._demanda_de(obj), cls.__name__, id)
        if restrito:
            with self.repo.transacao():
                self.trilha.registrar(ator, "LEITURA_RESTRITA", cls.__name__, id)
        return obj

    def verificar_auditoria(self, ator: Ator, ancora: dict | None = None) -> int:
        """Confere a cadeia da trilha. Com `ancora` (guardada fora do banco), confere também truncamento e reescrita."""
        self._exigir(ator, Acao.VERIFICAR_AUDITORIA, "EventoAuditoria", "*")
        n = self.trilha.verificar()
        if ancora is not None:
            problemas = conferir_ancora(self.trilha.eventos, ancora)
            if problemas:
                raise AuditoriaCorrompida("; ".join(problemas))
        return n

    def gerar_ancora(self, ator: Ator) -> dict:
        """Âncora da trilha atual, para guardar FORA do banco (ver backup/ancora.py). Não contém dados de registros."""
        self._exigir(ator, Acao.VERIFICAR_AUDITORIA, "EventoAuditoria", "*")
        self.trilha.verificar()
        return gerar_ancora(self.trilha.eventos)
