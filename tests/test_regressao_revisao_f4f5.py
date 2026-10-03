"""Regressão da revisão independente das Fases 4 e 5 (03/10/2026). Cada teste reproduz um achado.

Número do achado entre colchetes. Dados 100% sintéticos; CPF/e-mail fictícios montados em tempo de execução.
"""

import dataclasses
import hashlib
import uuid

import pytest

from gaema_sd.acesso import Ator
from gaema_sd.adaptadores import traduzir_submissao
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, Papel, StatusSincronizacao
from gaema_sd.erros import AcessoNegado, ErroGaema, TransicaoInvalida, ValidacaoFalhou
from gaema_sd.sincronizacao import ItemSincronizacao, ResultadoSincronizacao
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import Ambiente, acoes, com

S = Estado
CPF = "123.456." + "789-09"
EMAIL = "pessoa.ficticia" + "@" + "example.org"


@pytest.fixture
def amb(tmp_path, atores, cenario):
    return Ambiente(tmp_path, atores, cenario)


def _item(obj, operacao="CRIAR", base=0):
    return ItemSincronizacao.de_registro(obj, operacao, base)


def _conflito(amb, valor_disp="30", valor_central="50"):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    na = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(na, valor_bruto=valor_central, valor_normalizado=float(valor_central)),
                          na.versao)
    amb.disp.corrigir(com(obs, valor_bruto=valor_disp, valor_normalizado=float(valor_disp)), obs.versao)
    amb.sinc.executar()
    return amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]


# ---- [1] integridade na entrada da sincronização -------------------------------------------------------------

def test_1_observacao_sem_ponto_na_central_e_recusada(amb):
    with pytest.raises(ErroGaema, match="ponto"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(amb.c["Observacao"][0]))
    assert amb.na_central(E.Observacao) == []


def test_1_ponto_em_campanha_inexistente_e_recusado(amb):
    ponto = com(amb.c["PontoAmostral"][0], campanha_id=str(uuid.uuid4()))
    with pytest.raises(ErroGaema, match="campanha"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(ponto))
    assert amb.na_central(E.PontoAmostral) == []


def test_1_tecnico_fora_da_equipe_da_demanda_e_recusado(amb):
    intruso = Ator.de("usuario-sintetico-77", Papel.TECNICO_CAMPO)
    with pytest.raises(ErroGaema, match="equipe"):
        amb.central.receber_sincronizacao(intruso, _item(amb.c["PontoAmostral"][0]))
    assert amb.na_central(E.PontoAmostral) == []
    assert "SINCRONIZACAO_RECUSADA" in acoes(amb.central)


def _ate_em_validacao(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    amb.central.transitar(amb.a["tecnico"], amb.demanda_id, S.AGUARDANDO_SINCRONIZACAO)
    amb.central.transitar(amb.a["sistema"], amb.demanda_id, S.EM_VALIDACAO)
    return obs


def test_1_fora_do_estado_de_coleta_nao_cria_nem_altera_dado_de_campo(amb):
    obs = _ate_em_validacao(amb)
    assert amb.central.repo.obter(E.Demanda, amb.demanda_id).estado is S.EM_VALIDACAO
    alterada = com(obs, versao=2, valor_bruto="99", valor_normalizado=99.0)
    with pytest.raises(ErroGaema, match="estado"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(alterada, "ATUALIZAR", 1))
    novo_ponto = com(amb.c["PontoAmostral"][0], id=str(uuid.uuid4()), codigo="P99", chave_idempotencia="outra")
    with pytest.raises(ErroGaema, match="estado"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(novo_ponto))
    assert amb.na_central(E.Observacao)[0].valor_bruto == "35" and len(amb.na_central(E.PontoAmostral)) == 1


def test_1_reenvio_idempotente_continua_valendo_depois_que_a_demanda_avancou(amb):
    _ate_em_validacao(amb)
    ponto = amb.disp.nucleo.repo.listar(E.PontoAmostral)[0]
    r = amb.central.receber_sincronizacao(amb.a["tecnico"], _item(ponto))   # confirmação perdida, reenvio tardio
    assert r is ResultadoSincronizacao.REENVIO_IDEMPOTENTE


# ---- [2] rejeição por falha operacional não pode ser definitiva ---------------------------------------------

def test_2_acesso_negado_e_recuperavel_e_nada_vira_rejeitado(amb):
    amb.coletar_tudo()
    ok = amb.canal.ator
    amb.canal.ator = dataclasses.replace(ok, ativo=False)
    r = amb.sinc.executar()
    assert r.interrompido and "AcessoNegado" in r.motivo_interrupcao and r.rejeitados == 0
    assert amb.disp.fila.contagem()["REJEITADO"] == 0 and amb.disp.fila.contagem()["PENDENTE"] == 4
    amb.canal.ator = ok
    r2 = amb.sinc.executar()
    assert (r2.enviados, r2.pendentes_restantes) == (4, 0)
    assert len(amb.na_central(E.PontoAmostral)) == 1


def test_2_rejeitados_podem_ser_reenfileirados_explicitamente(amb):
    _ate_em_validacao(amb)
    novo = com(amb.c["PontoAmostral"][0], id=str(uuid.uuid4()), codigo="P98", chave_idempotencia="k98")
    amb.disp.coletar(novo)
    r = amb.sinc.executar()
    assert r.rejeitados == 1 and amb.disp.fila.contagem()["REJEITADO"] == 1
    assert amb.sinc.reenfileirar_rejeitados() == 1
    assert amb.disp.fila.contagem() == {"PENDENTE": 1, "ENVIADO": 2, "CONFLITO": 0, "REJEITADO": 0}
    amb.central.transitar(amb.a["coord"], amb.demanda_id, S.DEVOLVIDA_COMPLEMENTACAO, motivo="Complementar a coleta.")
    amb.central.transitar(amb.a["tecnico"], amb.demanda_id, S.EM_CAMPO, motivo="Retomada da coleta complementar.")
    assert amb.sinc.executar().enviados == 1


# ---- [3] item envenenado não trava a fila ---------------------------------------------------------------------

def test_3_arquivo_de_evidencia_ausente_no_aparelho_nao_trava_a_fila(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    ev = amb.disp.coletar(amb.c["Evidencia"][0], FOTO_SINTETICA)
    amb.disp.coletar(amb.c["Observacao"][0])
    amb.disp.nucleo._caminho_evidencia(ev.sha256).unlink()
    r = amb.sinc.executar()
    assert (r.enviados, r.rejeitados, r.pendentes_restantes) == (2, 1, 0)
    (rej,) = amb.disp.fila.itens("REJEITADO")
    assert rej["tipo"] == "Evidencia" and "arquivo" in rej["erro"]


# ---- [4] ACEITAR_DISPOSITIVO não sobrescreve alteração posterior da central -----------------------------------

def test_4_aceitar_recusado_se_a_central_mudou_depois_do_conflito(amb):
    cid = _conflito(amb)
    atual = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(atual, valor_bruto="33", valor_normalizado=33.0), atual.versao)
    with pytest.raises(ErroGaema, match="mudou"):
        amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "ACEITAR_DISPOSITIVO", "Aceitar o aparelho.")
    assert amb.na_central(E.Observacao)[0].valor_bruto == "33"
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "MANTER_CENTRAL", "Manter a versão da central.")
    assert amb.sinc.reconciliar().aplicadas == 1
    assert amb.disp.nucleo.repo.listar(E.Observacao)[0].valor_bruto == "33"


# ---- [7] identificador de registro não pode formar caminho ------------------------------------------------------

@pytest.mark.parametrize("ruim", ["a/../../fora", "..", "x" * 40, "id com espaço", ""])
def test_7_id_fora_do_formato_uuid_e_recusado(nucleo, atores, cenario, ruim):
    with pytest.raises(ValidacaoFalhou, match="ID_INVALIDO|identificador"):
        nucleo.registrar(atores["coord"], com(cenario["Demanda"][0], id=ruim))


# ---- [9] observador_id não pode ser de outra pessoa ----------------------------------------------------------

def test_9_observador_id_forjado_e_recusado_na_central_e_no_aparelho(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    forjada = com(amb.c["Observacao"][0], observador_id="usuario-sintetico-04")
    with pytest.raises(ValidacaoFalhou):
        amb.disp.coletar(forjada)
    with pytest.raises(ErroGaema):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(forjada))
    vazio = amb.central.registrar(amb.a["tecnico"], com(amb.c["Observacao"][0], observador_id=""))[0]
    assert vazio.observador_id == amb.a["tecnico"].id          # vazio é preenchido pelo núcleo


# ---- [12] reenvio de CRIAR depois de alteração na central não é conflito -----------------------------------------

def test_12_criar_reenviado_apos_alteracao_na_central_e_idempotente(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    amb.canal.programar("PERDA_DEPOIS", "PERDA_DEPOIS", "PERDA_DEPOIS")
    r = amb.sinc.executar()
    assert r.interrompido and len(amb.na_central(E.PontoAmostral)) == 1
    ponto = amb.na_central(E.PontoAmostral)[0]
    amb.central.atualizar(amb.a["tecnico"], com(ponto, codigo="P01-central"), ponto.versao)
    r2 = amb.sinc.executar()
    assert (r2.conflitos, r2.reenvios_idempotentes, r2.pendentes_restantes) == (0, 1, 0)
    assert amb.na_central(E.PontoAmostral)[0].codigo == "P01-central"
    assert amb.central.repo.conflitos_abertos() == 0


# ---- [13] falha na transição não perde o conflito -------------------------------------------------------------

def test_13_falha_ao_transitar_nao_perde_o_conflito_e_a_demanda_acompanha_depois(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    amb.central.transitar(amb.a["tecnico"], amb.demanda_id, S.AGUARDANDO_SINCRONIZACAO)
    na = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(na, valor_bruto="50", valor_normalizado=50.0), na.versao)
    amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    original = amb.central.transitar

    def quebra(*a, **k):
        raise RuntimeError("falha injetada")
    amb.central.transitar = quebra
    with pytest.raises(RuntimeError):
        amb.sinc.executar()
    amb.central.transitar = original
    assert amb.central.repo.conflitos_abertos(amb.demanda_id) == 1           # conflito gravado e auditado
    assert "CONFLITO_SINCRONIZACAO" in acoes(amb.central)
    amb.disp.fila.marcar(3, "PENDENTE")
    amb.sinc.executar()                                                      # reenvio: a demanda agora acompanha
    assert amb.central.repo.obter(E.Demanda, amb.demanda_id).estado is S.CONFLITO_SINCRONIZACAO
    assert amb.central.repo.conflitos_abertos() == 1


# ---- [14] decisão só para quem originou o conflito -----------------------------------------------------------------

def test_14_outro_tecnico_nao_le_a_decisao_do_conflito(amb):
    cid = _conflito(amb)
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "MANTER_CENTRAL", "Mantida a versão central.")
    item = amb.disp.fila.conflitos_sem_decisao()[0]
    outro = Ator.de("usuario-sintetico-77", Papel.TECNICO_CAMPO)
    assert amb.central.consultar_decisoes_conflito(outro, [("Observacao", item["hash_dados"])]) == []
    assert len(amb.central.consultar_decisoes_conflito(amb.a["tecnico"], [("Observacao", item["hash_dados"])])) == 1


# ---- [15] aplicar a mesma decisão duas vezes não desfaz trabalho novo ----------------------------------------------

def test_15_aplicar_decisao_duas_vezes_nao_altera_nada(amb):
    cid = _conflito(amb)
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "MANTER_CENTRAL", "Mantida a versão central.")
    item = amb.disp.fila.conflitos_sem_decisao()[0]
    (d,) = amb.central.consultar_decisoes_conflito(amb.a["tecnico"], [("Observacao", item["hash_dados"])])
    amb.disp.aplicar_decisao(d)
    local = amb.disp.nucleo.repo.listar(E.Observacao)[0]
    amb.disp.corrigir(com(local, valor_bruto="77", valor_normalizado=77.0), local.versao)
    assert amb.disp.aplicar_decisao(d) == "já aplicada"
    assert amb.disp.nucleo.repo.listar(E.Observacao)[0].valor_bruto == "77"
    assert amb.disp.fila.contagem()["PENDENTE"] == 1


# ---- [18] integração só ATIVA em ambiente real ----------------------------------------------------------------------

def test_18_integracao_ativa_exige_ambiente_de_homologacao_ou_operacao(nucleo, atores):
    from gaema_sd.dominio.enums import Ambiente as Amb, SituacaoIntegracao
    base = dict(nome="Serviço sintético", sistema="ArcGIS sintético", situacao=SituacaoIntegracao.ATIVA, evidencia_teste="teste sintético",
                sintetico=True)
    campos = {f.name for f in dataclasses.fields(E.IntegracaoExterna)}
    ambiente = "ambiente" if "ambiente" in campos else None
    assert ambiente, "IntegracaoExterna deveria registrar o ambiente"
    with pytest.raises(ValidacaoFalhou, match="ATIVA"):
        nucleo.registrar(atores["admin"], E.IntegracaoExterna(**{**base, "ambiente": Amb.DESENVOLVIMENTO}))


# ---- [20] permissão também no caminho de conflito (mutante sobrevivente da revisão) ---------------------------------

def test_20_quem_nao_pode_sincronizar_nao_abre_conflito(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    na = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(na, valor_bruto="50", valor_normalizado=50.0), na.versao)
    local = amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    obsoleto = _item(local, "ATUALIZAR", 1)                      # base antiga: levaria ao caminho de conflito
    with pytest.raises(AcessoNegado):
        amb.central.receber_sincronizacao(amb.a["coord"], obsoleto)
    assert amb.central.repo.conflitos_abertos() == 0


def test_2_descartados_por_decisao_nao_voltam_com_reenfileirar(amb):
    _conflito(amb)
    obs = amb.disp.nucleo.repo.listar(E.Observacao)[0]
    # edição retida e descartada pela decisão MANTER_CENTRAL não pode ser reenfileirada como se fosse falha operacional
    amb.disp.fila.marcar(2, "PENDENTE")
    amb.disp.fila.enfileirar(_item(com(obs, versao=3, valor_bruto="31"), "ATUALIZAR", 2))
    amb.sinc.executar()
    cid = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "MANTER_CENTRAL", "Mantida a versão central.")
    amb.sinc.reconciliar()
    assert any("descartado" in i["erro"] for i in amb.disp.fila.itens("REJEITADO"))
    assert amb.sinc.reenfileirar_rejeitados() == 0
