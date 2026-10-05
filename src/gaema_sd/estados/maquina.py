"""Máquina de estados da Demanda.

Tabela declarativa: cada transição define quem pode fazê-la, pré-condições,
se exige motivo e (calculado) como pode ser revertida. Toda transição aceita
gera evento de auditoria. Recusas são auditadas pelo núcleo (nucleo.py).

Saídas de estados excepcionais marcadas como "retorno" só levam de volta ao
estado em que a demanda estava antes da exceção (Demanda.estado_anterior).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from ..acesso.politica import Ator
from ..auditoria.trilha import TrilhaAuditoria
from ..dominio.entidades import Demanda
from ..dominio.enums import ESTADOS_EXCEPCIONAIS, Estado, Papel
from ..erros import AcessoNegado, TransicaoInvalida
from ..validacao.entidades import validar
from ..validacao.problemas import exigir_sem_erros

MOTIVO_MINIMO = 10

S = Estado
P = Papel


@dataclass
class ContextoTransicao:
    """Fatos sobre a demanda. No Nucleo, montados a partir do banco (estados/contexto.py)."""

    geometria_valida: bool = False
    fonte_registrada: bool = False
    area_interesse_definida: bool = False
    equipe_definida: bool = False
    campanha_planejada: bool = False
    protocolo_definido: bool = False
    missao_baixada: bool = False
    nota_acesso_registrada: bool = False
    pontos_coletados: int = 0
    pendencias_sincronizacao: int = 0
    conflitos_abertos: int = 0
    diagnostico_computado: bool = False
    erros_validacao: int = 0
    revisao_aprovada: bool = False
    revisor_participou_da_coleta: bool = False
    relatorio_emitido: bool = False
    providencia_registrada: bool = False
    marcos_monitoramento: int = 0
    marcos_pendentes: int = 0
    estados_percorridos: frozenset[str] = frozenset()
    autoatribuicao_permitida: bool = True   # falso só para técnico com o parâmetro desligado ou fora da equipe


Checagem = Callable[[Demanda, ContextoTransicao, Estado], Optional[str]]


def _se(cond: Callable[[Demanda, ContextoTransicao, Estado], bool], falha: str) -> Checagem:
    return lambda d, c, destino: None if cond(d, c, destino) else falha


# nome -> (descrição para documentação, checagem)
PRECONDICOES: dict[str, tuple[str, Checagem]] = {
    "geometria_valida": ("Geometria da área sem erro de validação",
                         _se(lambda d, c, x: c.geometria_valida, "geometria inválida ou não conferida")),
    "fonte_registrada": ("Ao menos uma fonte de dado registrada",
                         _se(lambda d, c, x: c.fonte_registrada, "nenhuma fonte de dado registrada")),
    "area_interesse_definida": ("Área de interesse definida",
                                _se(lambda d, c, x: c.area_interesse_definida and bool(d.area_interesse_id),
                                    "área de interesse não definida")),
    "equipe_definida": ("Equipe atribuída",
                        _se(lambda d, c, x: c.equipe_definida and bool(d.equipe_id), "equipe não atribuída")),
    "campanha_planejada": ("Campanha de vistoria com data e objetivo",
                           _se(lambda d, c, x: c.campanha_planejada, "campanha de vistoria não planejada")),
    "protocolo_definido": ("Versão de protocolo vinculada à campanha",
                           _se(lambda d, c, x: c.protocolo_definido, "versão de protocolo não definida")),
    "missao_baixada": ("Missão e mapa baixados para uso offline",
                       _se(lambda d, c, x: c.missao_baixada, "missão não baixada para uso offline")),
    "nota_acesso_registrada": ("Motivo da falta de acesso descrito na campanha",
                               _se(lambda d, c, x: c.nota_acesso_registrada, "descrever a falta de acesso")),
    "ha_pontos_coletados": ("Ao menos um ponto amostral coletado",
                            _se(lambda d, c, x: c.pontos_coletados > 0, "nenhum ponto coletado")),
    "sem_pendencia_sincronizacao": ("Nenhum registro pendente de sincronização",
                                    _se(lambda d, c, x: c.pendencias_sincronizacao == 0,
                                        "há registros pendentes de sincronização")),
    "sem_conflito_aberto": ("Nenhum conflito de sincronização aberto",
                            _se(lambda d, c, x: c.conflitos_abertos == 0, "há conflito de sincronização aberto")),
    "diagnostico_computado": ("Diagnóstico computado com protocolo versionado",
                              _se(lambda d, c, x: c.diagnostico_computado, "diagnóstico não computado")),
    "sem_erro_validacao": ("Dados de campo sem erro de validação",
                           _se(lambda d, c, x: c.erros_validacao == 0, "há erros de validação nos dados")),
    "revisao_aprovada": ("Revisão técnica aprovada (com ou sem ressalvas)",
                         _se(lambda d, c, x: c.revisao_aprovada, "revisão técnica não aprovada")),
    "revisor_independente": ("Revisor não participou da coleta (segregação de funções, AUTORAL)",
                             _se(lambda d, c, x: not c.revisor_participou_da_coleta,
                                 "revisor participou da coleta")),
    "relatorio_emitido": ("Relatório emitido",
                          _se(lambda d, c, x: c.relatorio_emitido, "relatório não emitido")),
    "providencia_registrada": ("Providência institucional registrada por membro do MP",
                               _se(lambda d, c, x: c.providencia_registrada, "nenhuma providência registrada")),
    "ha_marcos": ("Plano com ao menos um marco de monitoramento",
                  _se(lambda d, c, x: c.marcos_monitoramento > 0, "nenhum marco de monitoramento")),
    "marcos_resolvidos": ("Nenhum marco pendente de verificação",
                          _se(lambda d, c, x: c.marcos_pendentes == 0, "há marcos pendentes")),
    "ja_foi_aberta": ("Demanda já passou por DEMANDA_ABERTA antes",
                      _se(lambda d, c, x: Estado.DEMANDA_ABERTA.value in c.estados_percorridos,
                          "a demanda nunca foi formalmente aberta")),
    "ja_teve_diagnostico_emitido": ("Demanda já passou por DIAGNOSTICO_EMITIDO antes",
                                    _se(lambda d, c, x: Estado.DIAGNOSTICO_EMITIDO.value in c.estados_percorridos,
                                        "a demanda nunca teve diagnóstico emitido")),
    "autoatribuicao_permitida": ("Técnico só atribui a si se `autoatribuicao_tecnico` estiver ligado e ele for "
                                 "da equipe definida (coordenador sempre pode)",
                                 _se(lambda d, c, x: c.autoatribuicao_permitida,
                                     "autoatribuição pelo técnico desligada ou técnico fora da equipe definida")),
    "duplicada_de_informada": ("Demanda original informada",
                               _se(lambda d, c, x: bool(d.duplicada_de) and d.duplicada_de != d.id,
                                   "informar a demanda original")),
    "destino_e_estado_anterior": ("Destino igual ao estado anterior à exceção",
                                  _se(lambda d, c, x: d.estado_anterior is x,
                                      "só é possível voltar ao estado anterior à exceção")),
}


@dataclass(frozen=True)
class Transicao:
    origem: Estado
    destino: Estado
    papeis: frozenset[Papel]
    precondicoes: tuple[str, ...] = ()
    exige_motivo: bool = False
    descricao: str = ""


def _t(origem, destino, papeis, pre=(), motivo=False, descricao=""):
    return Transicao(origem, destino, frozenset(papeis), tuple(pre), motivo, descricao)


_NORMAIS = [
    _t(S.CANDIDATA, S.ALERTA, {P.ANALISTA_TRIAGEM, P.SISTEMA}, ["geometria_valida", "fonte_registrada"],
       descricao="Sinal remoto vira alerta"),
    _t(S.ALERTA, S.EM_TRIAGEM, {P.ANALISTA_TRIAGEM, P.COORDENADOR}, descricao="Início da triagem humana"),
    _t(S.EM_TRIAGEM, S.DEMANDA_ABERTA, {P.COORDENADOR, P.MEMBRO_MP}, ["area_interesse_definida"], True,
       "Abertura formal da demanda de averiguação"),
    _t(S.DEMANDA_ABERTA, S.ATRIBUIDA, {P.COORDENADOR, P.TECNICO_CAMPO}, ["equipe_definida", "autoatribuicao_permitida"],
       descricao="Equipe atribuída"),
    _t(S.ATRIBUIDA, S.PLANEJADA, {P.COORDENADOR, P.TECNICO_CAMPO}, ["campanha_planejada", "protocolo_definido"],
       descricao="Vistoria planejada"),
    _t(S.PLANEJADA, S.EM_CAMPO, {P.TECNICO_CAMPO}, ["missao_baixada"], descricao="Início da vistoria"),
    _t(S.EM_CAMPO, S.COLETA_PARCIAL, {P.TECNICO_CAMPO}, motivo=True, descricao="Interrupção da coleta"),
    _t(S.COLETA_PARCIAL, S.EM_CAMPO, {P.TECNICO_CAMPO}, descricao="Retomada da coleta"),
    _t(S.EM_CAMPO, S.AGUARDANDO_SINCRONIZACAO, {P.TECNICO_CAMPO, P.SISTEMA}, ["ha_pontos_coletados"],
       descricao="Coleta concluída, aguardando envio"),
    _t(S.COLETA_PARCIAL, S.AGUARDANDO_SINCRONIZACAO, {P.TECNICO_CAMPO, P.SISTEMA}, ["ha_pontos_coletados"], True,
       "Envio de coleta parcial"),
    _t(S.AGUARDANDO_SINCRONIZACAO, S.EM_VALIDACAO, {P.SISTEMA, P.COORDENADOR},
       ["sem_pendencia_sincronizacao", "sem_conflito_aberto"], descricao="Dados recebidos"),
    _t(S.EM_VALIDACAO, S.AGUARDANDO_REVISAO, {P.COORDENADOR, P.SISTEMA},
       ["diagnostico_computado", "sem_erro_validacao"], descricao="Diagnóstico pronto para revisão"),
    _t(S.AGUARDANDO_REVISAO, S.DIAGNOSTICO_EMITIDO, {P.REVISOR_TECNICO},
       ["revisao_aprovada", "revisor_independente"], descricao="Revisão técnica concluída"),
    _t(S.DIAGNOSTICO_EMITIDO, S.EM_TRATATIVA, {P.MEMBRO_MP}, ["relatorio_emitido"], True,
       "Início da tratativa institucional"),
    _t(S.DIAGNOSTICO_EMITIDO, S.EM_MONITORAMENTO, {P.MEMBRO_MP, P.COORDENADOR}, ["relatorio_emitido", "ha_marcos"],
       descricao="Monitoramento direto"),
    _t(S.DIAGNOSTICO_EMITIDO, S.ENCERRADA, {P.MEMBRO_MP}, ["relatorio_emitido"], True, "Encerramento"),
    _t(S.EM_TRATATIVA, S.EM_MONITORAMENTO, {P.MEMBRO_MP, P.COORDENADOR}, ["ha_marcos"],
       descricao="Plano acordado, monitoramento"),
    _t(S.EM_TRATATIVA, S.ENCERRADA, {P.MEMBRO_MP}, ["providencia_registrada"], True, "Encerramento"),
    _t(S.EM_MONITORAMENTO, S.EM_TRATATIVA, {P.MEMBRO_MP}, motivo=True, descricao="Retorno à tratativa"),
    _t(S.EM_MONITORAMENTO, S.ENCERRADA, {P.MEMBRO_MP}, ["marcos_resolvidos"], True, "Encerramento"),
    _t(S.ENCERRADA, S.REABERTA, {P.MEMBRO_MP}, motivo=True, descricao="Reabertura"),
    _t(S.CANCELADA_JUSTIFICADA, S.REABERTA, {P.MEMBRO_MP}, motivo=True, descricao="Reabertura"),
    _t(S.REABERTA, S.EM_TRIAGEM, {P.COORDENADOR, P.MEMBRO_MP}, descricao="Nova triagem"),
    _t(S.REABERTA, S.ATRIBUIDA, {P.COORDENADOR}, ["ja_foi_aberta", "area_interesse_definida", "equipe_definida"],
       descricao="Nova vistoria"),
    _t(S.REABERTA, S.EM_MONITORAMENTO, {P.COORDENADOR, P.MEMBRO_MP}, ["ja_teve_diagnostico_emitido", "ha_marcos"],
       descricao="Retomada do monitoramento"),
]

# (estado excepcional, origens, papéis de entrada, pré-condições de entrada,
#  papéis de retorno, pré-condições de retorno)
_EXCECOES_COM_RETORNO = [
    (S.DUPLICADA, [S.CANDIDATA, S.ALERTA, S.EM_TRIAGEM, S.DEMANDA_ABERTA],
     {P.ANALISTA_TRIAGEM, P.COORDENADOR}, ["duplicada_de_informada"], {P.COORDENADOR}, []),
    (S.DADOS_INSUFICIENTES, [S.EM_TRIAGEM, S.EM_VALIDACAO, S.AGUARDANDO_REVISAO],
     {P.ANALISTA_TRIAGEM, P.COORDENADOR, P.REVISOR_TECNICO}, [], {P.ANALISTA_TRIAGEM, P.COORDENADOR}, []),
    (S.GEOMETRIA_INCONSISTENTE, [S.CANDIDATA, S.ALERTA, S.EM_TRIAGEM, S.DEMANDA_ABERTA, S.EM_VALIDACAO],
     {P.ANALISTA_TRIAGEM, P.COORDENADOR, P.SISTEMA}, [], {P.ANALISTA_TRIAGEM, P.COORDENADOR},
     ["geometria_valida"]),
]

_EXCECOES_DIRETAS = [
    _t(S.PLANEJADA, S.SEM_ACESSO, {P.TECNICO_CAMPO}, ["nota_acesso_registrada"], True, "Sem acesso à área"),
    _t(S.EM_CAMPO, S.SEM_ACESSO, {P.TECNICO_CAMPO}, ["nota_acesso_registrada"], True, "Acesso interrompido"),
    _t(S.SEM_ACESSO, S.PLANEJADA, {P.COORDENADOR}, motivo=True, descricao="Replanejamento"),
    _t(S.AGUARDANDO_SINCRONIZACAO, S.CONFLITO_SINCRONIZACAO, {P.SISTEMA, P.COORDENADOR}, motivo=True,
       descricao="Conflito detectado no envio"),
    _t(S.CONFLITO_SINCRONIZACAO, S.AGUARDANDO_SINCRONIZACAO, {P.COORDENADOR}, ["sem_conflito_aberto"], True,
       "Conflito resolvido por decisão humana registrada"),
    _t(S.EM_VALIDACAO, S.DEVOLVIDA_COMPLEMENTACAO, {P.COORDENADOR, P.REVISOR_TECNICO}, motivo=True,
       descricao="Devolução para complementar"),
    _t(S.AGUARDANDO_REVISAO, S.DEVOLVIDA_COMPLEMENTACAO, {P.REVISOR_TECNICO}, motivo=True,
       descricao="Revisor devolve para complementar"),
    _t(S.DEVOLVIDA_COMPLEMENTACAO, S.PLANEJADA, {P.COORDENADOR}, motivo=True, descricao="Nova vistoria"),
    _t(S.DEVOLVIDA_COMPLEMENTACAO, S.EM_CAMPO, {P.TECNICO_CAMPO}, ["missao_baixada"], True,
       "Complementação em campo"),
    _t(S.DEVOLVIDA_COMPLEMENTACAO, S.EM_VALIDACAO, {P.COORDENADOR}, motivo=True,
       descricao="Complementação de escritório"),
]

_NAO_CANCELAVEIS = {S.ENCERRADA, S.CANCELADA_JUSTIFICADA, S.DUPLICADA}


def _montar_tabela() -> dict[tuple[Estado, Estado], Transicao]:
    lista = list(_NORMAIS) + list(_EXCECOES_DIRETAS)
    for exc, origens, p_in, pre_in, p_out, pre_out in _EXCECOES_COM_RETORNO:
        for o in origens:
            lista.append(_t(o, exc, p_in, pre_in, True, f"Marcada como {exc.value}"))
            lista.append(_t(exc, o, p_out, ["destino_e_estado_anterior", *pre_out], True,
                            "Retorno ao estado anterior à exceção"))
    for e in Estado:
        if e not in _NAO_CANCELAVEIS:
            lista.append(_t(e, S.CANCELADA_JUSTIFICADA, {P.COORDENADOR, P.MEMBRO_MP}, motivo=True,
                            descricao="Cancelamento justificado"))
    tabela: dict[tuple[Estado, Estado], Transicao] = {}
    for t in lista:
        chave = (t.origem, t.destino)
        if chave in tabela:
            raise RuntimeError(f"transição duplicada: {chave}")
        for nome in t.precondicoes:
            if nome not in PRECONDICOES:
                raise RuntimeError(f"pré-condição desconhecida: {nome}")
        tabela[chave] = t
    return tabela


TABELA: dict[tuple[Estado, Estado], Transicao] = _montar_tabela()


def destinos_possiveis(origem: Estado) -> list[Estado]:
    return [d for (o, d) in TABELA if o is origem]


def reversao(t: Transicao) -> Optional[Transicao]:
    """Transição inversa, se existir."""
    return TABELA.get((t.destino, t.origem))


def avaliar(demanda: Demanda, destino: Estado, ator: Ator, motivo: str,
            contexto: ContextoTransicao) -> Transicao:
    """Confere tudo sem alterar nada. Levanta erro explicativo se não puder."""
    if not ator.ativo:
        raise AcessoNegado(f"usuário {ator.id} inativo")
    t = TABELA.get((demanda.estado, destino))
    if t is None:
        possiveis = ", ".join(d.value for d in destinos_possiveis(demanda.estado)) or "nenhum"
        raise TransicaoInvalida(
            f"não é possível ir de {demanda.estado.value} para {destino.value}; destinos possíveis: {possiveis}")
    if not (ator.papeis & t.papeis):
        permitidos = ", ".join(sorted(p.value for p in t.papeis))
        raise AcessoNegado(f"{demanda.estado.value} → {destino.value} só pode ser feita por: {permitidos}")
    if t.exige_motivo and len((motivo or "").strip()) < MOTIVO_MINIMO:
        raise TransicaoInvalida(f"motivo obrigatório (mínimo {MOTIVO_MINIMO} caracteres)")
    falhas = [m for nome in t.precondicoes if (m := PRECONDICOES[nome][1](demanda, contexto, destino))]
    if falhas:
        raise TransicaoInvalida("pré-condições não atendidas: " + "; ".join(falhas))
    return t


def transitar(demanda: Demanda, destino: Estado, ator: Ator, *, contexto: ContextoTransicao,
              trilha: TrilhaAuditoria, motivo: str = "") -> Demanda:
    """Aplica a transição e audita. Devolve nova Demanda (a original não muda)."""
    t = avaliar(demanda, destino, ator, motivo, contexto)
    if demanda.estado in ESTADOS_EXCEPCIONAIS and "destino_e_estado_anterior" in t.precondicoes:
        anterior = None  # saiu da exceção: não há mais estado a que voltar
    else:
        anterior = demanda.estado
    nova = dataclasses.replace(demanda, estado=destino, estado_anterior=anterior,
                               atualizado_em=datetime.now(timezone.utc))
    exigir_sem_erros(validar(nova))
    trilha.registrar(ator, "TRANSICAO", "Demanda", demanda.id,
                     estado_origem=demanda.estado.value, estado_destino=destino.value, motivo=motivo.strip())
    return nova
