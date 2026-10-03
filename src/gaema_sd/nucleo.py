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
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from .acesso.politica import Acao, Ator, exigir
from .auditoria.trilha import TrilhaAuditoria
from .dominio import entidades as E
from .dominio.enums import Estado, FormatoRelatorio, Sensibilidade
from .dominio.serializacao import json_canonico
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
from .protocolo.definicao import canonizar, carregar_definicao
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


ESTADOS_COM_RELATORIO = (Estado.DIAGNOSTICO_EMITIDO, Estado.EM_TRATATIVA, Estado.EM_MONITORAMENTO,
                         Estado.ENCERRADA, Estado.REABERTA)


class Nucleo:
    def __init__(self, repo: Repositorio, diretorio_saida: str | Path = "saida"):
        self.repo = repo
        self.saida = Path(diretorio_saida)
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
        return self._registrar(ator, obj)

    def _registrar(self, ator: Ator, obj: T) -> tuple[T, list[Problema]]:
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
        caminho = self._caminho_evidencia(r.sha256)
        if caminho.exists():
            if hashlib.sha256(caminho.read_bytes()).hexdigest() != r.sha256:
                raise ErroGaema(f"arquivo guardado {caminho.name} não confere com o hash; verificar armazenamento")
        else:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = caminho.with_suffix(".parcial")
            temporario.write_bytes(conteudo)
            os.replace(temporario, caminho)
        evidencia = dataclasses.replace(evidencia, sha256=r.sha256, tamanho_bytes=r.tamanho_bytes,
                                        armazenamento_ref=f"evidencias/{r.sha256}")
        return self._registrar(ator, evidencia)[0]

    def verificar_evidencia(self, ator: Ator, evidencia_id: str) -> bool:
        """Confere se o arquivo guardado ainda tem o hash registrado."""
        self._exigir(ator, Acao.LER_RESTRITO, "Evidencia", evidencia_id)
        ev = self.repo.obter(E.Evidencia, evidencia_id)
        caminho = self.saida / ev.armazenamento_ref if ev.armazenamento_ref else None
        integro = bool(caminho and caminho.exists()
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
        dados = montagem.montar(self.repo, demanda.id, numero_versao=numero, gerado_em=gerado_em,
                                gerado_por=ator.id, motivo_reemissao=motivo_reemissao.strip(),
                                anteriores=anteriores)
        diag = montagem.diagnostico_vigente(self.repo, demanda.id)
        revisao = montagem.revisao_aprovada(self.repo, diag.id)
        conteudo = (relatorio_pdf if formato is FormatoRelatorio.PDF else relatorio_html).renderizar(dados)
        caminho = self.saida / "relatorios" / f"relatorio-{demanda.id[:8]}-v{numero}.{formato.value.lower()}"
        if caminho.exists():
            raise ErroGaema(f"{caminho.name} já existe; relatório emitido não é sobrescrito")
        rel = E.Relatorio(demanda_id=demanda.id, numero_versao=numero, diagnostico_id=diag.id,
                          revisao_id=revisao.id, versao_protocolo_id=diag.versao_protocolo_id, formato=formato,
                          hash_conteudo=hashlib.sha256(conteudo).hexdigest(), gerado_por=ator.id,
                          gerado_em=gerado_em, substitui_relatorio_id=anteriores[-1].id if anteriores else None,
                          motivo_reemissao=motivo_reemissao.strip())
        gravado = self._registrar(ator, rel)[0]
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        return gravado, caminho

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
