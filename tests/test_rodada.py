"""Rotina do aparelho: uma rodada = buscar decisões de conflito e enviar a fila. Rede simulada."""

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.sincronizacao import simulacao

from .apoio_sincronizacao import Ambiente, com


@pytest.fixture
def amb(tmp_path, atores, cenario):
    return Ambiente(tmp_path, atores, cenario)


def test_rodada_busca_a_decisao_e_envia_o_que_estava_retido_numa_unica_passada(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.rodada()
    na = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(na, valor_bruto="50", valor_normalizado=50.0), na.versao)
    local = amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    amb.disp.corrigir(com(local, valor_bruto="31", valor_normalizado=31.0), local.versao)   # fica retida pelo conflito
    r = amb.sinc.rodada()
    assert (r.envio.conflitos, r.envio.retidos) == (1, 1)
    cid = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "ACEITAR_DISPOSITIVO", "Vale o valor do aparelho.")
    r2 = amb.sinc.rodada()           # decisão chega e o retido segue, tudo na mesma passada
    assert (r2.reconciliacao.aplicadas, r2.envio.enviados, r2.envio.retidos) == (1, 1, 0)
    assert amb.na_central(E.Observacao)[0].valor_bruto == "31"
    assert amb.disp.fila.contagem()["PENDENTE"] == 0


def test_rodada_sem_nada_a_fazer_e_inofensiva(amb):
    r = amb.sinc.rodada()
    assert (r.reconciliacao.aplicadas, r.reconciliacao.aguardando, r.envio.enviados) == (0, 0, 0)


def test_rodada_com_rede_caindo_na_consulta_nao_impede_o_envio_na_proxima(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.rodada()
    na = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(na, valor_bruto="50", valor_normalizado=50.0), na.versao)
    amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    amb.sinc.rodada()
    cid = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, "MANTER_CENTRAL", "Mantida a versão central.")
    amb.canal.programar("PERDA_ANTES", "PERDA_ANTES", "PERDA_ANTES")
    r = amb.sinc.rodada()
    assert r.reconciliacao.interrompido and amb.disp.nucleo.repo.listar(E.Observacao)[0].valor_bruto == "30"
    assert amb.sinc.rodada().reconciliacao.aplicadas == 1


def test_simulacao_executavel_converge(tmp_path):
    (tmp_path / "sim").mkdir()
    r = simulacao.executar(tmp_path / "sim", verbose=False)
    assert r["convergiu"] and r["decisoes_aplicadas"] == 1 and r["valor"] == "50" and r["conflitos_abertos_antes"] == 1


def test_simulacao_recusa_pasta_com_conteudo(tmp_path, capsys):
    (tmp_path / "x").write_text("ocupada")
    assert simulacao.main(["m", "simular", str(tmp_path)]) == 2
    assert simulacao.main(["m"]) == 2
