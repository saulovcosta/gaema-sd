import dataclasses

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado
from gaema_sd.erros import AcessoNegado, ConflitoAtualizacao, ErroGaema, TransicaoInvalida, ValidacaoFalhou
from .test_estados import CTX_OK


def acoes(nucleo):
    return [e.acao for e in nucleo.trilha.eventos]


def test_registrar_audita_e_fixa_quem_registrou(nucleo, atores, cenario):
    ponto = dataclasses.replace(cenario["PontoAmostral"][0], criado_por="tentando-se-passar-por-outro")
    gravado, alertas = nucleo.registrar(atores["tecnico"], ponto)
    assert gravado.criado_por == atores["tecnico"].id and alertas == []
    assert acoes(nucleo) == ["CRIAR"]


def test_acesso_indevido_e_auditado(nucleo, atores, cenario):
    with pytest.raises(AcessoNegado):
        nucleo.registrar(atores["auditor"], cenario["PontoAmostral"][0])
    with pytest.raises(AcessoNegado):
        nucleo.registrar(atores["tecnico"], cenario["VersaoProtocolo"][0])
    assert acoes(nucleo) == ["ACESSO_NEGADO", "ACESSO_NEGADO"]
    assert nucleo.repo.listar(E.PontoAmostral) == []


def test_reenvio_duplicado_auditado_sem_duplicar(nucleo, atores, cenario):
    p = cenario["PontoAmostral"][0]
    nucleo.registrar(atores["tecnico"], p)
    nucleo.registrar(atores["tecnico"], p)
    assert acoes(nucleo) == ["CRIAR", "REENVIO_IDEMPOTENTE"]
    assert len(nucleo.repo.listar(E.PontoAmostral)) == 1


def test_gps_ruim_grava_com_alerta(nucleo, atores, cenario):
    p = dataclasses.replace(cenario["PontoAmostral"][0], precisao_gps_m=80.0)
    _, alertas = nucleo.registrar(atores["tecnico"], p)
    assert [a.codigo for a in alertas] == ["GPS_RUIM"]
    assert nucleo.trilha.eventos[-1].detalhes == {"alertas": "GPS_RUIM"}


def test_erro_de_validacao_nao_grava(nucleo, atores, cenario):
    a = dataclasses.replace(cenario["AreaCandidata"][0], geometria_wkt="POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))")
    with pytest.raises(ValidacaoFalhou, match="geometria inválida"):
        nucleo.registrar(atores["analista"], a)
    assert nucleo.repo.listar(E.AreaCandidata) == []


def test_imutaveis_e_estado_so_por_transicao(nucleo, atores, cenario):
    ev, _ = nucleo.registrar(atores["tecnico"], cenario["Evidencia"][0])
    with pytest.raises(ErroGaema, match="imutável"):
        nucleo.atualizar(atores["tecnico"], ev, ev.versao)
    d, _ = nucleo.registrar(atores["coord"], cenario["Demanda"][0])
    with pytest.raises(ErroGaema, match="só muda por transição"):
        nucleo.atualizar(atores["coord"], dataclasses.replace(d, estado=Estado.ENCERRADA), d.versao)


def test_conflito_de_atualizacao_auditado(nucleo, atores, cenario):
    d, _ = nucleo.registrar(atores["coord"], cenario["Demanda"][0])
    nucleo.atualizar(atores["coord"], dataclasses.replace(d, objetivo="primeira edição"), d.versao)
    with pytest.raises(ConflitoAtualizacao):
        nucleo.atualizar(atores["coord"], dataclasses.replace(d, objetivo="edição atrasada"), d.versao)
    assert acoes(nucleo)[-1] == "CONFLITO_ATUALIZACAO"


def test_transicao_persistida_e_recusa_auditada(nucleo, atores, cenario):
    d, _ = nucleo.registrar(atores["coord"], cenario["Demanda"][0])
    d2 = nucleo.transitar(atores["sistema"], d.id, Estado.ALERTA, contexto=CTX_OK)
    assert d2.estado is Estado.ALERTA and d2.versao == 2
    with pytest.raises(TransicaoInvalida):
        nucleo.transitar(atores["analista"], d.id, Estado.ENCERRADA, contexto=CTX_OK)
    assert nucleo.repo.obter(E.Demanda, d.id).estado is Estado.ALERTA
    assert acoes(nucleo) == ["CRIAR", "TRANSICAO", "TRANSICAO_RECUSADA"]
    assert nucleo.verificar_auditoria(atores["auditor"]) == 3


def test_leitura_restrita_exige_papel_e_e_auditada(nucleo, atores, cenario):
    d, _ = nucleo.registrar(atores["coord"], cenario["Demanda"][0])
    with pytest.raises(AcessoNegado):
        nucleo.ler(atores["admin"], E.Demanda, d.id)
    assert nucleo.ler(atores["membro"], E.Demanda, d.id).id == d.id
    assert acoes(nucleo)[-2:] == ["ACESSO_NEGADO", "LEITURA_RESTRITA"]
    f, _ = nucleo.registrar(atores["analista"], cenario["FonteDado"][0])
    nucleo.ler(atores["admin"], E.FonteDado, f.id)  # interna: leitura comum, sem evento
    assert acoes(nucleo)[-1] == "CRIAR"


def test_so_auditor_e_admin_verificam_auditoria(nucleo, atores):
    with pytest.raises(AcessoNegado):
        nucleo.verificar_auditoria(atores["tecnico"])
    assert nucleo.verificar_auditoria(atores["admin"]) == 1  # o próprio ACESSO_NEGADO
