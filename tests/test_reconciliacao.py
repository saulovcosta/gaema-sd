"""Fase 5 (i): o dispositivo recebe de volta a decisão do coordenador sobre um conflito (fecha R-18).

Simulação local com dois SQLite; a rede é simulada.
"""

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import StatusSincronizacao
from gaema_sd.erros import AcessoNegado, ErroGaema
from gaema_sd.sincronizacao import InterrupcaoSimulada
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import Ambiente, acoes, com

EMAIL = "pessoa.ficticia" + "@" + "example.org"


@pytest.fixture
def amb(tmp_path, atores, cenario):
    return Ambiente(tmp_path, atores, cenario)


def _conflito_de_observacao(amb, *, valor_dispositivo="30", valor_central="50"):
    """Ponto e observação sincronizados; central e dispositivo editam a mesma versão: gera 1 conflito."""
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    na_central = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(na_central, valor_bruto=valor_central,
                                                valor_normalizado=float(valor_central)), na_central.versao)
    local = amb.disp.corrigir(com(obs, valor_bruto=valor_dispositivo, valor_normalizado=float(valor_dispositivo)),
                              obs.versao)
    return local


def _decidir(amb, decisao, motivo="Conferido em campo pelo coordenador."):
    cid = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao WHERE situacao='ABERTO'").fetchone()[0]
    amb.central.resolver_conflito_sincronizacao(amb.a["coord"], cid, decisao, motivo)
    return cid


def _local(amb):
    return amb.disp.nucleo.repo.listar(E.Observacao)[0]


def _central(amb):
    return amb.na_central(E.Observacao)[0]


def test_falha_da_fase_4_item_posterior_nao_passa_por_cima_da_central(amb):
    """Reprodução do defeito: 2ª correção do dispositivo tinha base igual à versão da central e a sobrescrevia."""
    local = _conflito_de_observacao(amb)
    amb.disp.corrigir(com(local, valor_bruto="31", valor_normalizado=31.0), local.versao)
    r = amb.sinc.executar()
    assert (r.conflitos, r.retidos, r.pendentes_restantes) == (1, 1, 1)
    assert _central(amb).valor_bruto == "50" and _central(amb).versao == 2   # nada foi sobrescrito


def test_aceitar_dispositivo_realinha_versoes_e_correcao_seguinte_e_aceita(amb):
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    assert amb.sinc.reconciliar().aguardando == 1            # coordenador ainda não decidiu
    assert amb.disp.fila.decisoes() == []
    _decidir(amb, "ACEITAR_DISPOSITIVO")
    rec = amb.sinc.reconciliar()
    assert (rec.aplicadas, rec.aguardando) == (1, 0)
    assert _central(amb).valor_bruto == "30" and _central(amb).versao == 3
    (d,) = amb.disp.fila.decisoes()
    assert d["decisao"] == "ACEITAR_DISPOSITIVO" and d["aplicada"] == 1
    # nova correção no dispositivo parte da versão certa da central e é aplicada
    nova = amb.disp.corrigir(com(_local(amb), valor_bruto="33", valor_normalizado=33.0), _local(amb).versao)
    r = amb.sinc.executar()
    assert (r.enviados, r.conflitos) == (1, 0)
    assert _central(amb).valor_bruto == nova.valor_bruto == "33" and _central(amb).versao == 4


def test_manter_central_dispositivo_adota_a_versao_da_central(amb):
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    _decidir(amb, "MANTER_CENTRAL")
    rec = amb.sinc.reconciliar()
    assert rec.aplicadas == 1
    assert _local(amb).valor_bruto == "50" == _central(amb).valor_bruto            # os dois bancos convergem
    assert _local(amb).status_sincronizacao is StatusSincronizacao.SINCRONIZADO
    assert _local(amb).versao != _central(amb).versao                              # numeração local difere...
    assert amb.disp.fila.deslocamento("Observacao", _local(amb).id) == _central(amb).versao - _local(amb).versao
    # ...e a próxima correção usa a versão da central como base
    amb.disp.corrigir(com(_local(amb), valor_bruto="55", valor_normalizado=55.0), _local(amb).versao)
    r = amb.sinc.executar()
    assert (r.enviados, r.conflitos) == (1, 0)
    assert _central(amb).valor_bruto == "55" == _local(amb).valor_bruto


def test_retidos_com_aceitar_sao_reajustados_e_aplicados(amb):
    local = _conflito_de_observacao(amb)
    amb.disp.corrigir(com(local, valor_bruto="31", valor_normalizado=31.0), local.versao)
    amb.sinc.executar()                                                           # conflito + 1 retido
    _decidir(amb, "ACEITAR_DISPOSITIVO")
    amb.sinc.reconciliar()
    r = amb.sinc.executar()
    assert (r.enviados, r.retidos, r.pendentes_restantes) == (1, 0, 0)
    assert _central(amb).valor_bruto == "31" == _local(amb).valor_bruto
    assert [h.valor_bruto for h in amb.central.repo.historico(E.Observacao, _central(amb).id)] == ["35", "50", "30", "31"]


def test_retidos_com_manter_central_sao_descartados_com_registro(amb):
    local = _conflito_de_observacao(amb)
    amb.disp.corrigir(com(local, valor_bruto="31", valor_normalizado=31.0), local.versao)
    amb.sinc.executar()
    _decidir(amb, "MANTER_CENTRAL")
    amb.sinc.reconciliar()
    descartados = amb.disp.fila.itens("REJEITADO")
    assert len(descartados) == 1 and "decisão do coordenador" in descartados[0]["erro"]
    r = amb.sinc.executar()
    assert r.enviados == 0 and _central(amb).valor_bruto == "50" == _local(amb).valor_bruto


def test_registro_em_conflito_nao_pode_ser_corrigido_ate_a_decisao(amb):
    local = _conflito_de_observacao(amb)
    amb.sinc.executar()
    with pytest.raises(ErroGaema, match="aguardando decisão"):
        amb.disp.corrigir(com(local, valor_bruto="99", valor_normalizado=99.0), local.versao)
    _decidir(amb, "ACEITAR_DISPOSITIVO")
    amb.sinc.reconciliar()
    amb.disp.corrigir(com(_local(amb), valor_bruto="99", valor_normalizado=99.0), _local(amb).versao)  # agora pode


def test_reconciliar_duas_vezes_nao_aplica_de_novo(amb):
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    _decidir(amb, "MANTER_CENTRAL")
    amb.sinc.reconciliar()
    versao = _local(amb).versao
    assert amb.sinc.reconciliar().aplicadas == 0 and _local(amb).versao == versao


def test_falha_de_rede_na_consulta_nao_perde_a_decisao(amb):
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    _decidir(amb, "MANTER_CENTRAL")
    amb.canal.programar("PERDA_ANTES", "INDISPONIVEL", "PERDA_ANTES")
    rec = amb.sinc.reconciliar()
    assert rec.interrompido and rec.aplicadas == 0 and _local(amb).valor_bruto == "30"
    assert amb.esperas[-2:] == [2.0, 4.0]
    assert amb.sinc.reconciliar().aplicadas == 1 and _local(amb).valor_bruto == "50"


def test_interrupcao_do_processo_na_consulta_e_retomada(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario, banco_dispositivo=str(tmp_path / "disp.db"))
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    _decidir(amb, "MANTER_CENTRAL")
    amb.canal.programar("INTERROMPER_DEPOIS")           # a central respondeu, mas o processo morreu antes de aplicar
    with pytest.raises(InterrupcaoSimulada):
        amb.sinc.reconciliar()
    amb.reiniciar_dispositivo()
    assert amb.disp.fila.decisoes() == [] and _local(amb).valor_bruto == "30"
    assert amb.sinc.reconciliar().aplicadas == 1
    assert _local(amb).valor_bruto == "50" == _central(amb).valor_bruto


def test_conflito_de_evidencia_registra_a_decisao_sem_mexer_no_arquivo(amb):
    a, c = amb.a, amb.c
    amb.central.registrar(a["tecnico"], c["PontoAmostral"][0])      # origem da evidência precisa existir na central
    amb.central.registrar(a["tecnico"], c["Observacao"][0])
    amb.central.registrar_evidencia(a["tecnico"], c["Evidencia"][0], FOTO_SINTETICA)
    outra = com(c["Evidencia"][0], categoria=c["Evidencia"][0].categoria.__class__("FOTO_PANORAMICA"),
                chave_idempotencia="outra-chave")
    amb.disp.coletar(outra, FOTO_SINTETICA)
    r = amb.sinc.executar()
    assert r.conflitos == 1
    cid = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]
    with pytest.raises(ErroGaema, match="imutável"):
        amb.central.resolver_conflito_sincronizacao(a["coord"], cid, "ACEITAR_DISPOSITIVO", "tentativa não permitida")
    amb.central.resolver_conflito_sincronizacao(a["coord"], cid, "MANTER_CENTRAL", "Mantida a evidência da central.")
    assert amb.sinc.reconciliar().aplicadas == 1
    (d,) = amb.disp.fila.decisoes()
    assert d["aplicada"] == 0 and "imutável" in d["observacao"]
    assert amb.na_central(E.Evidencia)[0].categoria == c["Evidencia"][0].categoria


def test_consulta_nao_vaza_conflito_aberto_nem_hash_desconhecido(amb):
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    item = amb.disp.fila.conflitos_sem_decisao()[0]
    assert amb.central.consultar_decisoes_conflito(amb.a["tecnico"], [("Observacao", item["hash_dados"])]) == []
    assert amb.central.consultar_decisoes_conflito(amb.a["tecnico"], [("Observacao", "0" * 64)]) == []
    assert amb.central.consultar_decisoes_conflito(amb.a["tecnico"], [("Demanda", item["hash_dados"])]) == []


def test_acesso_indevido_e_limite_na_consulta(amb):
    for papel in ("coord", "auditor", "analista", "revisor", "membro", "admin", "sistema"):
        with pytest.raises(AcessoNegado):
            amb.central.consultar_decisoes_conflito(amb.a[papel], [("Observacao", "x")])
    with pytest.raises(ErroGaema, match="grande demais"):
        amb.central.consultar_decisoes_conflito(amb.a["tecnico"], [("Observacao", str(i)) for i in range(501)])
    assert acoes(amb.central).count("ACESSO_NEGADO") == 7


def test_motivo_da_decisao_chega_mascarado_ao_dispositivo(amb):
    _conflito_de_observacao(amb)
    amb.sinc.executar()
    _decidir(amb, "MANTER_CENTRAL", motivo=f"Falei com {EMAIL} e conferi no local.")
    amb.sinc.reconciliar()
    texto = str(amb.disp.fila.decisoes()) + " ".join(str(e.detalhes) + e.motivo for e in amb.central.trilha.eventos)
    assert EMAIL not in texto


def test_demanda_volta_a_aguardar_sincronizacao_e_auditoria_fecha(amb):
    from gaema_sd.dominio.enums import Estado
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    amb.central.transitar(amb.a["tecnico"], amb.demanda_id, Estado.AGUARDANDO_SINCRONIZACAO)
    na_central = _central(amb)
    amb.central.atualizar(amb.a["tecnico"], com(na_central, valor_bruto="50", valor_normalizado=50.0), na_central.versao)
    amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    amb.sinc.executar()
    assert amb.central.repo.obter(E.Demanda, amb.demanda_id).estado is Estado.CONFLITO_SINCRONIZACAO
    _decidir(amb, "ACEITAR_DISPOSITIVO")
    amb.sinc.reconciliar()
    d = amb.central.transitar(amb.a["coord"], amb.demanda_id, Estado.AGUARDANDO_SINCRONIZACAO,
                              motivo="Conflito resolvido e dispositivo atualizado.")
    assert d.estado is Estado.AGUARDANDO_SINCRONIZACAO
    assert amb.central.verificar_auditoria(amb.a["auditor"]) > 0
    assert "CONSULTA_DECISAO_CONFLITO" in acoes(amb.central)


def test_banco_da_fase_4_sem_as_tabelas_novas_abre_e_ganha_as_tabelas(tmp_path):
    from gaema_sd.persistencia import Repositorio
    caminho = str(tmp_path / "antigo.db")
    repo = Repositorio(caminho)
    for t in ("decisoes_conflito", "deslocamento_versao"):
        repo.con.execute(f"DROP TABLE {t}")
    repo.con.execute("ALTER TABLE conflitos_sincronizacao DROP COLUMN enviado_por")
    repo.con.execute("PRAGMA user_version = 1")
    repo.fechar()
    novo = Repositorio(caminho)
    tabelas = {l[0] for l in novo.con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"decisoes_conflito", "deslocamento_versao", "fila_envio", "conflitos_sincronizacao"} <= tabelas
    assert novo.con.execute("PRAGMA user_version").fetchone()[0] == 2   # banco da Fase 4 (versão 1) migrou para 2
    novo.fechar()
