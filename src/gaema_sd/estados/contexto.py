"""Monta o ContextoTransicao a partir do banco e da trilha de auditoria.

O chamador não informa fatos: o núcleo os apura. Isso impede, por exemplo,
declarar "revisão aprovada" sem existir RevisaoTecnica gravada.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..acesso.politica import Ator
from ..dominio import entidades as E
from ..dominio.enums import (
    CondicaoAcesso,
    ResultadoRevisao,
    SituacaoDiagnostico,
    SituacaoMarco,
    StatusSincronizacao,
)
from ..erros import RegistroNaoEncontrado
from ..validacao.entidades import validar
from ..validacao.geometria import validar_poligono_wkt
from ..validacao.problemas import tem_erro
from .maquina import ContextoTransicao

APROVACOES = (ResultadoRevisao.APROVADO, ResultadoRevisao.APROVADO_COM_RESSALVAS)
MARCOS_ABERTOS = (SituacaoMarco.PREVISTO, SituacaoMarco.VERIFICACAO_PENDENTE)


def _obter(repo, cls, id_: Optional[str]):
    if not id_:
        return None
    try:
        return repo.obter(cls, id_)
    except RegistroNaoEncontrado:
        return None


def montar_contexto(repo, demanda: E.Demanda, ator: Ator,
                    eventos: Iterable[E.EventoAuditoria]) -> ContextoTransicao:
    candidata = _obter(repo, E.AreaCandidata, demanda.area_candidata_id)
    area = _obter(repo, E.AreaInteresse, demanda.area_interesse_id)
    equipe = _obter(repo, E.Equipe, demanda.equipe_id)

    geometrias = [g.geometria_wkt for g in (candidata, area) if g is not None]
    geometria_valida = bool(geometrias) and not any(tem_erro(validar_poligono_wkt(g)) for g in geometrias)
    fonte_registrada = bool(candidata and candidata.fonte_ids) and all(
        _obter(repo, E.FonteDado, f) is not None for f in candidata.fonte_ids)

    campanhas = [c for c in repo.listar(E.CampanhaVistoria) if c.demanda_id == demanda.id]
    ids_campanha = {c.id for c in campanhas}
    pontos = [p for p in repo.listar(E.PontoAmostral) if p.campanha_id in ids_campanha]
    ids_ponto = {p.id for p in pontos}
    observacoes = [o for o in repo.listar(E.Observacao) if o.ponto_id in ids_ponto]
    medicoes = [m for m in repo.listar(E.MedicaoPenetracao) if m.ponto_id in ids_ponto]
    evidencias = [e for e in repo.listar(E.Evidencia) if e.campanha_id in ids_campanha]
    coleta = [*pontos, *observacoes, *medicoes, *evidencias]

    coletores = {r.criado_por for r in coleta}
    coletores |= {o.observador_id for o in observacoes} | {e.registrado_por for e in evidencias}

    diagnosticos = [d for d in repo.listar(E.Diagnostico)
                    if d.demanda_id == demanda.id and d.situacao is not SituacaoDiagnostico.SUBSTITUIDO]
    ids_diag = {d.id for d in diagnosticos}
    revisoes = sorted((r for r in repo.listar(E.RevisaoTecnica) if r.diagnostico_id in ids_diag),
                      key=lambda r: r.revisado_em)
    ultima = revisoes[-1] if revisoes else None

    planos = [p for p in repo.listar(E.PlanoRecuperacao) if p.demanda_id == demanda.id]
    ids_plano = {p.id for p in planos}
    marcos = [m for m in repo.listar(E.MarcoMonitoramento) if m.plano_id in ids_plano]

    percorridos = frozenset(
        ev.estado_destino for ev in eventos
        if ev.acao == "TRANSICAO" and ev.entidade == "Demanda" and ev.entidade_id == demanda.id)

    return ContextoTransicao(
        geometria_valida=geometria_valida,
        fonte_registrada=fonte_registrada,
        area_interesse_definida=area is not None,
        equipe_definida=equipe is not None,
        campanha_planejada=any(c.equipe_id == demanda.equipe_id for c in campanhas),
        protocolo_definido=any(_obter(repo, E.VersaoProtocolo, c.versao_protocolo_id) for c in campanhas),
        missao_baixada=any(c.pacote_offline.strip() for c in campanhas),
        nota_acesso_registrada=any(c.condicao_acesso is CondicaoAcesso.SEM_ACESSO and c.nota_acesso.strip()
                                   for c in campanhas),
        pontos_coletados=len(pontos),
        pendencias_sincronizacao=sum(r.status_sincronizacao is StatusSincronizacao.PENDENTE for r in coleta),
        conflitos_abertos=sum(r.status_sincronizacao is StatusSincronizacao.CONFLITO for r in coleta),
        diagnostico_computado=bool(diagnosticos),
        erros_validacao=sum(tem_erro(validar(r)) for r in coleta),
        revisao_aprovada=bool(ultima and ultima.resultado in APROVACOES and ultima.revisor_id == ator.id),
        revisor_participou_da_coleta=ator.id in coletores,
        relatorio_emitido=any(r.demanda_id == demanda.id for r in repo.listar(E.Relatorio)),
        providencia_registrada=any(p.demanda_id == demanda.id for p in repo.listar(E.Providencia)),
        marcos_monitoramento=len(marcos),
        marcos_pendentes=sum(m.situacao in MARCOS_ABERTOS for m in marcos),
        estados_percorridos=percorridos,
    )
