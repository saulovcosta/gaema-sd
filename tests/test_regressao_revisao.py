"""Regressão dos 8 achados da revisão independente de 03/10/2026 (Fase 2)."""

import dataclasses
from datetime import datetime

import pytest

from gaema_sd.auditoria import TrilhaAuditoria
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, ResultadoRevisao
from gaema_sd.erros import ConflitoAtualizacao, ConflitoIdempotencia, ErroGaema, TransicaoInvalida, ValidacaoFalhou
from gaema_sd.estados import transitar
from gaema_sd.persistencia import Repositorio
from gaema_sd.sinteticos import FOTO_SINTETICA

from .test_estados import CTX_OK

S = Estado
H = "a" * 64


def acoes(nucleo):
    return [e.acao for e in nucleo.trilha.eventos]


def _diagnostico(c):
    return E.Diagnostico(demanda_id=c["Demanda"][0].id, campanha_id=c["CampanhaVistoria"][0].id,
                         versao_protocolo_id=c["VersaoProtocolo"][0].id, hash_definicao_protocolo=H,
                         hash_entradas=H, resultado_descritivo="Descrição sintética das observações.",
                         limitacoes="Dados sintéticos; protocolo descritivo.")


def _revisao(diag_id, revisor_id=""):
    return E.RevisaoTecnica(diagnostico_id=diag_id, revisor_id=revisor_id, resultado=ResultadoRevisao.APROVADO,
                            fundamentacao="Conferidas observações, medições e fotos do ponto P01.")


def levar_ate_revisao(nucleo, a, c):
    """Percorre o fluxo real pelo núcleo, com todos os registros gravados no banco."""
    t = nucleo.transitar
    for ator, chave in [("analista", "FonteDado"), ("analista", "AreaCandidata"), ("analista", "Alerta"),
                        ("analista", "AreaInteresse"), ("coord", "Equipe"), ("coord", "VersaoProtocolo"),
                        ("coord", "Demanda")]:
        nucleo.registrar(a[ator], c[chave][0])
    d = c["Demanda"][0].id
    t(a["sistema"], d, S.ALERTA)
    t(a["analista"], d, S.EM_TRIAGEM)
    t(a["membro"], d, S.DEMANDA_ABERTA, motivo="abertura para averiguação sintética")
    t(a["coord"], d, S.ATRIBUIDA)
    nucleo.registrar(a["coord"], c["CampanhaVistoria"][0])
    t(a["coord"], d, S.PLANEJADA)
    t(a["tecnico"], d, S.EM_CAMPO)
    for chave in ("PontoAmostral", "Observacao", "MedicaoPenetracao"):
        nucleo.registrar(a["tecnico"], c[chave][0])
    nucleo.registrar_evidencia(a["tecnico"], c["Evidencia"][0], FOTO_SINTETICA)
    t(a["tecnico"], d, S.AGUARDANDO_SINCRONIZACAO)
    t(a["sistema"], d, S.EM_VALIDACAO)
    diag = nucleo.computar_diagnostico(a["sistema"], d, c["CampanhaVistoria"][0].id)
    t(a["coord"], d, S.AGUARDANDO_REVISAO)
    return d, diag


# 1 ------------------------------------------------------------------------
def test_1_demanda_nao_nasce_em_estado_avancado(nucleo, atores, cenario):
    for campos in ({"estado": S.DIAGNOSTICO_EMITIDO}, {"estado_anterior": S.EM_TRIAGEM}, {"versao": 5}):
        with pytest.raises(ValidacaoFalhou):
            nucleo.registrar(atores["analista"], dataclasses.replace(cenario["Demanda"][0], **campos))
    assert nucleo.repo.listar(E.Demanda) == []
    assert "CRIACAO_RECUSADA" in acoes(nucleo)


# 2 ------------------------------------------------------------------------
def test_2_sem_diagnostico_e_revisao_no_banco_nao_emite(nucleo, atores, cenario):
    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    with pytest.raises(TransicaoInvalida, match="revisão técnica não aprovada"):
        nucleo.transitar(atores["revisor"], d, S.DIAGNOSTICO_EMITIDO)
    nucleo.registrar(atores["revisor"], _revisao(diag.id))
    assert nucleo.transitar(atores["revisor"], d, S.DIAGNOSTICO_EMITIDO).estado is S.DIAGNOSTICO_EMITIDO
    assert nucleo.verificar_auditoria(atores["auditor"]) == len(nucleo.trilha.eventos)


def test_2_revisor_que_coletou_nao_emite(nucleo, atores, cenario):
    from gaema_sd.acesso import Ator
    from gaema_sd.dominio.enums import Papel

    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    duplo = Ator.de(atores["tecnico"].id, Papel.TECNICO_CAMPO, Papel.REVISOR_TECNICO)
    nucleo.registrar(duplo, _revisao(diag.id))
    with pytest.raises(TransicaoInvalida, match="participou da coleta"):
        nucleo.transitar(duplo, d, S.DIAGNOSTICO_EMITIDO)


def test_2_revisao_de_outro_revisor_nao_vale_para_quem_emite(nucleo, atores, cenario):
    from gaema_sd.acesso import Ator
    from gaema_sd.dominio.enums import Papel

    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    nucleo.registrar(atores["revisor"], _revisao(diag.id))
    outro = Ator.de("usuario-sintetico-99", Papel.REVISOR_TECNICO)
    with pytest.raises(TransicaoInvalida):
        nucleo.transitar(outro, d, S.DIAGNOSTICO_EMITIDO)


# 3 ------------------------------------------------------------------------
def test_3_diagnostico_e_imutavel(nucleo, atores, cenario):
    _, diag = levar_ate_revisao(nucleo, atores, cenario)
    with pytest.raises(ErroGaema, match="imutável"):
        nucleo.atualizar(atores["coord"], dataclasses.replace(diag, resultado_descritivo="trocado"), 1)
    assert acoes(nucleo)[-1] == "ATUALIZACAO_RECUSADA"


def test_3_diagnostico_nao_e_gravado_a_mao(nucleo, atores, cenario):
    with pytest.raises(ErroGaema, match="motor de protocolo"):
        nucleo.registrar(atores["sistema"], _diagnostico(cenario))
    assert nucleo.repo.listar(E.Diagnostico) == []


# 4 ------------------------------------------------------------------------
def test_4_autoria_nao_pode_ser_forjada(nucleo, atores, cenario):
    with pytest.raises(ValidacaoFalhou, match="revisor_id"):
        nucleo.registrar(atores["revisor"], _revisao("diag", revisor_id="outro-revisor"))
    r, _ = nucleo.registrar(atores["revisor"], _revisao("diag"))
    assert r.revisor_id == atores["revisor"].id
    ev = dataclasses.replace(cenario["Evidencia"][0], registrado_por="outra-pessoa")
    with pytest.raises(ValidacaoFalhou, match="registrado_por"):
        nucleo.registrar_evidencia(atores["tecnico"], ev, FOTO_SINTETICA)


# 5 ------------------------------------------------------------------------
def test_5_tipo_errado_nao_e_gravado(nucleo, atores, cenario):
    a = dataclasses.replace(cenario["AreaCandidata"][0], data_deteccao=datetime(2026, 1, 1, tzinfo=E.timezone.utc))
    with pytest.raises(ValidacaoFalhou, match="TIPO|tipo datetime"):
        nucleo.registrar(atores["analista"], a)
    p = dataclasses.replace(cenario["PontoAmostral"][0], capturado_em=datetime(2026, 1, 1))
    with pytest.raises(ValidacaoFalhou, match="fuso"):
        nucleo.registrar(atores["tecnico"], p)
    q = dataclasses.replace(cenario["PontoAmostral"][0], latitude="-10.5")
    with pytest.raises(ValidacaoFalhou):
        nucleo.registrar(atores["tecnico"], q)
    assert nucleo.repo.listar(E.AreaCandidata) == [] and nucleo.repo.listar(E.PontoAmostral) == []


# 6 ------------------------------------------------------------------------
def test_6_reabertura_nao_pula_diagnostico(cenario, atores):
    t = TrilhaAuditoria()
    d = dataclasses.replace(cenario["Demanda"][0], estado=S.REABERTA)
    sem_historico = dataclasses.replace(CTX_OK, estados_percorridos=frozenset({"ALERTA", "CANCELADA_JUSTIFICADA"}))
    with pytest.raises(TransicaoInvalida, match="nunca teve diagnóstico"):
        transitar(d, S.EM_MONITORAMENTO, atores["membro"], contexto=sem_historico, trilha=t)
    with pytest.raises(TransicaoInvalida, match="nunca foi formalmente aberta"):
        transitar(d, S.ATRIBUIDA, atores["coord"], contexto=sem_historico, trilha=t)
    com = dataclasses.replace(CTX_OK, estados_percorridos=frozenset({"DEMANDA_ABERTA", "DIAGNOSTICO_EMITIDO"}))
    assert transitar(d, S.EM_MONITORAMENTO, atores["membro"], contexto=com, trilha=t).estado is S.EM_MONITORAMENTO


# 7 ------------------------------------------------------------------------
def test_7_chave_de_envio_nao_muda_nem_duplica(nucleo, atores, cenario):
    p, _ = nucleo.registrar(atores["tecnico"], cenario["PontoAmostral"][0])
    with pytest.raises(ErroGaema, match="chave de envio"):
        nucleo.atualizar(atores["tecnico"], dataclasses.replace(p, chave_idempotencia="K-NOVA"), p.versao)
    repo = Repositorio(":memory:")
    a, _ = repo.inserir(p)
    b, _ = repo.inserir(dataclasses.replace(p, id=E.novo_id(), codigo="P02", chave_idempotencia="K-B"))
    with pytest.raises(ConflitoIdempotencia):
        repo.atualizar(dataclasses.replace(b, chave_idempotencia=a.chave_idempotencia), b.versao)


# 8 ------------------------------------------------------------------------
def test_8_atualizacao_atrasada_nao_desfaz_transicao(nucleo, atores, cenario):
    nucleo.registrar(atores["analista"], cenario["FonteDado"][0])
    nucleo.registrar(atores["analista"], cenario["AreaCandidata"][0])
    lido, _ = nucleo.registrar(atores["coord"], cenario["Demanda"][0])          # A lê v1 CANDIDATA
    nucleo.transitar(atores["sistema"], lido.id, S.ALERTA)                     # B transita (v2)
    with pytest.raises(ErroGaema, match="só muda por transição"):              # A envia com versão nova
        nucleo.atualizar(atores["coord"], dataclasses.replace(lido, objetivo="x"), 2)
    with pytest.raises(ConflitoAtualizacao):                                    # A envia com versão velha
        nucleo.atualizar(atores["coord"], dataclasses.replace(lido, objetivo="x"), 1)
    assert nucleo.repo.obter(E.Demanda, lido.id).estado is S.ALERTA


# menores ------------------------------------------------------------------
def test_reenvio_com_inteiro_ou_decimal_e_o_mesmo(nucleo, atores, cenario):
    p = dataclasses.replace(cenario["PontoAmostral"][0], latitude=-10, precisao_gps_m=4)
    nucleo.registrar(atores["tecnico"], p)
    nucleo.registrar(atores["tecnico"], dataclasses.replace(p, latitude=-10.0, precisao_gps_m=4.0))
    assert acoes(nucleo) == ["CRIAR", "REENVIO_IDEMPOTENTE"]
