"""Fase 4: fila local, perda de rede, reenvio idempotente, retomada e conflito de sincronização.

Simulação local com dois SQLite (dispositivo e central). Não há rede nem servidor reais.
"""

import dataclasses
import hashlib

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, StatusSincronizacao
from gaema_sd.dominio.serializacao import json_canonico
from gaema_sd.erros import AcessoNegado, ErroGaema, TransicaoInvalida
from gaema_sd.sincronizacao import InterrupcaoSimulada, ItemSincronizacao, ResultadoSincronizacao
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import Ambiente, acoes, com

S = Estado


@pytest.fixture
def amb(tmp_path, atores, cenario):
    return Ambiente(tmp_path, atores, cenario)


def test_coleta_offline_fica_na_fila_e_envia_tudo(amb):
    amb.coletar_tudo()
    assert amb.disp.fila.contagem()["PENDENTE"] == 4
    assert amb.na_central(E.PontoAmostral) == []  # nada chegou à central ainda
    assert all(r.status_sincronizacao is StatusSincronizacao.PENDENTE
               for r in amb.disp.nucleo.repo.listar(E.PontoAmostral))
    r = amb.sinc.executar()
    assert (r.enviados, r.pendentes_restantes, r.interrompido) == (4, 0, False)
    for cls in (E.PontoAmostral, E.Observacao, E.MedicaoPenetracao, E.Evidencia):
        (reg,) = amb.na_central(cls)
        assert reg.status_sincronizacao is StatusSincronizacao.SINCRONIZADO
    ev = amb.na_central(E.Evidencia)[0]
    assert amb.central.verificar_evidencia(amb.a["coord"], ev.id)
    assert amb.central.verificar_auditoria(amb.a["auditor"]) > 0


def test_perda_de_rede_nao_perde_nem_descarta_e_a_proxima_rodada_conclui(amb):
    amb.coletar_tudo()
    amb.canal.programar("PERDA_ANTES", "PERDA_ANTES", "PERDA_ANTES")
    r = amb.sinc.executar()
    assert r.interrompido and r.pendentes_restantes == 4 and "ErroRede" in r.motivo_interrupcao
    assert amb.esperas == [2.0, 4.0]  # espera dobra a cada tentativa
    assert amb.na_central(E.PontoAmostral) == [] and amb.canal.entregues == 0
    r2 = amb.sinc.executar()
    assert (r2.enviados, r2.pendentes_restantes) == (4, 0)


def test_servico_indisponivel_interrompe_e_retoma_do_ponto_certo(amb):
    amb.coletar_tudo()
    amb.canal.programar(None, "INDISPONIVEL", "INDISPONIVEL", "INDISPONIVEL")
    r = amb.sinc.executar()
    assert r.enviados == 1 and r.interrompido and "ServicoIndisponivel" in r.motivo_interrupcao
    assert len(amb.na_central(E.PontoAmostral)) == 1 and amb.na_central(E.Observacao) == []  # ordem preservada
    r2 = amb.sinc.executar()
    assert (r2.enviados, r2.pendentes_restantes) == (3, 0)


def test_confirmacao_perdida_gera_reenvio_idempotente_sem_duplicar(amb):
    amb.coletar_tudo()
    amb.canal.programar("PERDA_DEPOIS")  # a central aplica o 1º item, mas o dispositivo não fica sabendo
    r = amb.sinc.executar()
    assert (r.enviados, r.reenvios_idempotentes, r.pendentes_restantes) == (3, 1, 0)
    assert len(amb.na_central(E.PontoAmostral)) == 1
    assert acoes(amb.central).count("REENVIO_IDEMPOTENTE") == 1
    assert amb.canal.entregues == 5  # 4 itens + 1 reenvio


def test_confirmacao_perdida_em_todas_as_tentativas_nao_duplica_na_proxima_rodada(amb):
    amb.coletar_tudo()
    amb.canal.programar("PERDA_DEPOIS", "PERDA_DEPOIS", "PERDA_DEPOIS")
    r = amb.sinc.executar()
    assert r.interrompido and len(amb.na_central(E.PontoAmostral)) == 1  # a central aplicou uma vez só
    r2 = amb.sinc.executar()
    assert r2.pendentes_restantes == 0 and r2.reenvios_idempotentes == 1
    assert len(amb.na_central(E.PontoAmostral)) == 1 and len(amb.na_central(E.Evidencia)) == 1


def test_retomada_apos_interrupcao_do_processo(tmp_path, atores, cenario):
    banco = str(tmp_path / "dispositivo.db")
    amb = Ambiente(tmp_path, atores, cenario, banco_dispositivo=banco)
    amb.coletar_tudo()
    amb.canal.programar(None, "INTERROMPER_DEPOIS")  # morre depois de a central aplicar o 2º item
    with pytest.raises(InterrupcaoSimulada):
        amb.sinc.executar()
    amb.reiniciar_dispositivo()  # aplicativo reaberto sobre o mesmo arquivo
    assert amb.disp.fila.contagem() == {"PENDENTE": 3, "ENVIADO": 1, "CONFLITO": 0, "REJEITADO": 0}
    r = amb.sinc.executar()
    assert (r.enviados, r.reenvios_idempotentes, r.pendentes_restantes) == (2, 1, 0)
    assert [len(amb.na_central(c)) for c in (E.PontoAmostral, E.Observacao, E.MedicaoPenetracao, E.Evidencia)] \
        == [1, 1, 1, 1]


def test_interrupcao_antes_de_enfileirar_nao_perde_o_registro(tmp_path, atores, cenario):
    banco = str(tmp_path / "dispositivo.db")
    amb = Ambiente(tmp_path, atores, cenario, banco_dispositivo=banco)
    # gravou no dispositivo, mas o processo morreu antes de enfileirar
    amb.disp.nucleo.registrar(amb.a["tecnico"], com(amb.c["PontoAmostral"][0],
                                                    status_sincronizacao=StatusSincronizacao.PENDENTE))
    assert amb.disp.fila.contagem()["PENDENTE"] == 0
    amb.reiniciar_dispositivo()
    r = amb.sinc.executar()
    assert r.enviados == 1 and len(amb.na_central(E.PontoAmostral)) == 1


def test_enfileirar_duas_vezes_nao_duplica_item(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    assert amb.disp.recuperar_nao_enfileirados() == 0
    assert amb.disp.fila.contagem()["PENDENTE"] == 1


def test_correcao_offline_aplica_quando_central_nao_mudou_e_e_idempotente(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    amb.disp.corrigir(com(obs, valor_bruto="40", valor_normalizado=40.0), obs.versao)
    amb.canal.programar("PERDA_DEPOIS")
    r = amb.sinc.executar()
    assert (r.enviados, r.reenvios_idempotentes) == (0, 1) and r.pendentes_restantes == 0
    central = amb.na_central(E.Observacao)[0]
    assert central.valor_bruto == "40" and central.versao == 2


def test_versoes_divergentes_viram_conflito_e_nada_e_sobrescrito(amb):
    a = amb.a
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    amb.central.transitar(a["tecnico"], amb.demanda_id, S.AGUARDANDO_SINCRONIZACAO)
    # central e dispositivo alteram a mesma observação a partir da mesma versão
    na_central = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(a["tecnico"], com(na_central, valor_bruto="50", valor_normalizado=50.0), na_central.versao)
    amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)

    r = amb.sinc.executar()
    assert (r.conflitos, r.enviados, r.pendentes_restantes) == (1, 0, 0)
    assert amb.na_central(E.Observacao)[0].valor_bruto == "50"  # versão da central intacta
    assert amb.central.repo.conflitos_abertos(amb.demanda_id) == 1
    assert amb.central.repo.obter(E.Demanda, amb.demanda_id).estado is S.CONFLITO_SINCRONIZACAO
    assert amb.disp.fila.contagem()["CONFLITO"] == 1
    assert "CONFLITO_SINCRONIZACAO" in acoes(amb.central)

    # a versão do dispositivo ficou guardada, e o mesmo reenvio não abre segundo conflito
    amb.disp.fila.marcar(1, "PENDENTE")  # simula reenvio do mesmo item (ex.: restauração da fila)
    amb.disp.fila.marcar(3, "PENDENTE")
    amb.sinc.executar()
    assert amb.central.repo.conflitos_abertos() == 1

    # a demanda não volta sozinha: precisa de decisão do coordenador
    with pytest.raises(TransicaoInvalida):
        amb.central.transitar(a["coord"], amb.demanda_id, S.AGUARDANDO_SINCRONIZACAO, motivo="tentativa sem resolver")
    conflito_id = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]
    with pytest.raises(AcessoNegado):
        amb.central.resolver_conflito_sincronizacao(a["tecnico"], conflito_id, "ACEITAR_DISPOSITIVO",
                                                    "técnico não decide o conflito")
    with pytest.raises(ErroGaema, match="motivo"):
        amb.central.resolver_conflito_sincronizacao(a["coord"], conflito_id, "ACEITAR_DISPOSITIVO", "curto")
    amb.central.resolver_conflito_sincronizacao(a["coord"], conflito_id, "ACEITAR_DISPOSITIVO",
                                                "Conferido em campo: vale o valor do dispositivo.")
    atual = amb.na_central(E.Observacao)[0]
    assert atual.valor_bruto == "30" and atual.versao == 3  # nova versão, histórico preservado
    assert [h.valor_bruto for h in amb.central.repo.historico(E.Observacao, atual.id)] == ["35", "50", "30"]
    with pytest.raises(ErroGaema, match="já resolvido"):
        amb.central.resolver_conflito_sincronizacao(a["coord"], conflito_id, "MANTER_CENTRAL",
                                                    "segunda decisão não vale")
    d = amb.central.transitar(a["coord"], amb.demanda_id, S.AGUARDANDO_SINCRONIZACAO,
                              motivo="Conflito resolvido pelo coordenador.")
    assert d.estado is S.AGUARDANDO_SINCRONIZACAO
    assert amb.central.verificar_auditoria(a["auditor"]) > 0


def test_manter_central_descarta_efeito_mas_guarda_a_versao_do_dispositivo(amb):
    a = amb.a
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    na_central = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(a["tecnico"], com(na_central, valor_bruto="50", valor_normalizado=50.0), na_central.versao)
    amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    amb.sinc.executar()
    # demanda ainda EM_CAMPO: o conflito fica aberto e bloqueia a validação, sem mexer no estado
    assert amb.central.repo.obter(E.Demanda, amb.demanda_id).estado is S.EM_CAMPO
    assert amb.central.repo.conflitos_abertos(amb.demanda_id) == 1
    cid = amb.central.repo.con.execute("SELECT id FROM conflitos_sincronizacao").fetchone()[0]
    amb.central.resolver_conflito_sincronizacao(a["coord"], cid, "MANTER_CENTRAL", "Valor da central foi conferido.")
    assert amb.na_central(E.Observacao)[0].valor_bruto == "50"
    linha = amb.central.repo.obter_conflito(cid)
    assert linha["situacao"] == "RESOLVIDO" and '"valor_bruto":"30"' in linha["dados_dispositivo"]


def test_conflito_na_criacao_com_mesmo_id_e_conteudo_diferente(amb):
    a = amb.a
    amb.central.registrar(a["tecnico"], amb.c["PontoAmostral"][0])
    outro = com(amb.c["PontoAmostral"][0], latitude=-10.4999)
    amb.disp.coletar(outro)
    r = amb.sinc.executar()
    assert r.conflitos == 1
    assert amb.na_central(E.PontoAmostral)[0].latitude == amb.c["PontoAmostral"][0].latitude


def test_central_nao_aceita_resolver_com_decisao_inventada(amb):
    with pytest.raises(ErroGaema, match="decisão"):
        amb.central.resolver_conflito_sincronizacao(amb.a["coord"], "x", "APAGAR", "motivo suficiente aqui")


# ---- recusas e segurança na entrada da central ---------------------------------------------------------

def _item(obj, operacao="CRIAR", base=0):
    return ItemSincronizacao.de_registro(obj, operacao, base)


def test_acesso_indevido_na_sincronizacao_e_auditado_e_nao_grava(amb):
    item = _item(amb.c["PontoAmostral"][0])
    for papel in ("coord", "auditor", "analista", "revisor", "membro", "admin", "sistema"):
        with pytest.raises(AcessoNegado):
            amb.central.receber_sincronizacao(amb.a[papel], item)
    assert amb.na_central(E.PontoAmostral) == []
    assert acoes(amb.central).count("ACESSO_NEGADO") == 7


def test_item_adulterado_em_transito_e_recusado(amb):
    item = _item(amb.c["PontoAmostral"][0])
    adulterado = dataclasses.replace(item, dados={**item.dados, "latitude": -10.0})
    with pytest.raises(ErroGaema, match="trânsito"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], adulterado)
    assert amb.na_central(E.PontoAmostral) == [] and "SINCRONIZACAO_RECUSADA" in acoes(amb.central)


def test_tipo_nao_sincronizavel_e_operacao_invalida(amb):
    d = amb.c["Demanda"][0]
    with pytest.raises(ErroGaema, match="não é sincronizável"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(d))
    with pytest.raises(ErroGaema, match="desconhecida"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], dataclasses.replace(_item(amb.c["PontoAmostral"][0]),
                                                                              operacao="APAGAR"))


def test_campo_desconhecido_no_item_e_recusado(amb):
    item = _item(amb.c["PontoAmostral"][0])
    dados = {**item.dados, "campo_inventado": 1}
    forjado = dataclasses.replace(item, dados=dados, hash_dados=hashlib.sha256(json_canonico(dados).encode()).hexdigest())
    with pytest.raises(ErroGaema, match="malformado"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], forjado)


def test_anexo_invalido_na_sincronizacao_nao_grava_registro_nem_arquivo(amb):
    ev = amb.c["Evidencia"][0]
    for conteudo, extra in ((b"MZ\x90\x00 nao e imagem", {}),                         # assinatura inválida
                            (FOTO_SINTETICA + b"x", {}),                                # hash não confere
                            (FOTO_SINTETICA, {"nome_arquivo_original": "../fora.jpg"}), # nome inseguro
                            (b"", {})):                                                 # vazio
        item = _item(com(ev, **extra))
        with pytest.raises(ErroGaema):
            amb.central.receber_sincronizacao(amb.a["tecnico"], item, conteudo)
    assert amb.na_central(E.Evidencia) == []
    pasta = amb.tmp / "central" / "evidencias"
    assert not pasta.exists() or list(pasta.iterdir()) == []
    with pytest.raises(ErroGaema, match="sem o arquivo"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(ev), None)



def test_evidencia_nao_e_atualizada_por_sincronizacao(amb):
    ev = amb.c["Evidencia"][0]
    with pytest.raises(ErroGaema, match="imutável"):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(ev, "ATUALIZAR", 1), FOTO_SINTETICA)


def test_atualizacao_de_registro_inexistente_e_recusada(amb):
    with pytest.raises(ErroGaema):
        amb.central.receber_sincronizacao(amb.a["tecnico"], _item(amb.c["Observacao"][0], "ATUALIZAR", 1))


def test_item_rejeitado_nao_trava_a_fila(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    # evidência cujo arquivo no dispositivo foi trocado depois do registro: a central recusa o hash
    ev = amb.disp.coletar(amb.c["Evidencia"][0], FOTO_SINTETICA)
    amb.disp.coletar(amb.c["Observacao"][0])
    caminho = amb.disp.nucleo._caminho_evidencia(ev.sha256)
    caminho.write_bytes(FOTO_SINTETICA + b"corrompido")
    r = amb.sinc.executar()
    assert (r.enviados, r.rejeitados, r.pendentes_restantes) == (2, 1, 0)
    assert amb.disp.fila.contagem()["REJEITADO"] == 1
    assert amb.na_central(E.Evidencia) == []


def test_rejeicao_usa_a_chave_certa_do_hash(amb):
    # sanidade do apoio: o hash do arquivo sintético é o do cenário
    assert amb.c["Evidencia"][0].sha256 == hashlib.sha256(FOTO_SINTETICA).hexdigest()
    assert ResultadoSincronizacao.CONFLITO.value == "CONFLITO"
