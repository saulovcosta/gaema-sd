"""R-28: a central confere origem, equipe e estado em QUALQUER entrada de dado de campo, não só na sincronização."""

import uuid

import pytest

from gaema_sd.acesso import Ator
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, Papel
from gaema_sd.erros import ErroGaema
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio
from gaema_sd.sincronizacao import Dispositivo
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import Ambiente, acoes, com


@pytest.fixture
def amb(tmp_path, atores, cenario):
    return Ambiente(tmp_path, atores, cenario)


def test_modo_padrao_e_central_e_modo_invalido_e_recusado(tmp_path):
    assert Nucleo(Repositorio(":memory:"), tmp_path).modo == "central"
    with pytest.raises(ErroGaema, match="modo"):
        Nucleo(Repositorio(":memory:"), tmp_path, modo="qualquer")


def test_registrar_direto_na_central_recusa_observacao_sem_ponto_e_ponto_sem_campanha(amb):
    with pytest.raises(ErroGaema, match="ponto"):
        amb.central.registrar(amb.a["tecnico"], amb.c["Observacao"][0])
    with pytest.raises(ErroGaema, match="campanha"):
        amb.central.registrar(amb.a["tecnico"], com(amb.c["PontoAmostral"][0], campanha_id=str(uuid.uuid4())))
    assert amb.na_central(E.Observacao) == [] and amb.na_central(E.PontoAmostral) == []
    assert acoes(amb.central).count("CRIACAO_RECUSADA") == 2


def test_registrar_direto_na_central_recusa_tecnico_fora_da_equipe(amb):
    intruso = Ator.de("usuario-sintetico-77", Papel.TECNICO_CAMPO)
    with pytest.raises(ErroGaema, match="equipe"):
        amb.central.registrar(intruso, amb.c["PontoAmostral"][0])
    amb.central.registrar(amb.a["tecnico"], amb.c["PontoAmostral"][0])
    amb.central.registrar(amb.a["tecnico"], amb.c["Observacao"][0])
    with pytest.raises(ErroGaema, match="equipe"):
        amb.central.registrar_evidencia(intruso, com(amb.c["Evidencia"][0], registrado_por=""), FOTO_SINTETICA)


def _avancar_ate_validacao(amb):
    amb.central.registrar(amb.a["tecnico"], amb.c["PontoAmostral"][0])
    amb.central.registrar(amb.a["tecnico"], amb.c["Observacao"][0])
    amb.central.transitar(amb.a["tecnico"], amb.demanda_id, Estado.AGUARDANDO_SINCRONIZACAO)
    amb.central.transitar(amb.a["sistema"], amb.demanda_id, Estado.EM_VALIDACAO)


def test_registrar_e_atualizar_direto_na_central_recusam_depois_que_a_demanda_avancou(amb):
    _avancar_ate_validacao(amb)
    novo = com(amb.c["PontoAmostral"][0], id=str(uuid.uuid4()), codigo="P99", chave_idempotencia="k99")
    with pytest.raises(ErroGaema, match="estado"):
        amb.central.registrar(amb.a["tecnico"], novo)
    obs = amb.na_central(E.Observacao)[0]
    with pytest.raises(ErroGaema, match="estado"):
        amb.central.atualizar(amb.a["tecnico"], com(obs, valor_bruto="99", valor_normalizado=99.0), obs.versao)
    assert amb.na_central(E.Observacao)[0].valor_bruto == "35"


def test_reenvio_idempotente_direto_continua_valendo_depois_que_a_demanda_avancou(amb):
    _avancar_ate_validacao(amb)
    gravado, _ = amb.central.registrar(amb.a["tecnico"], amb.c["PontoAmostral"][0])   # mesmo registro: não duplica
    assert gravado.id == amb.c["PontoAmostral"][0].id and len(amb.na_central(E.PontoAmostral)) == 1


def test_aparelho_continua_gravando_local_sem_a_campanha(amb):
    amb.disp.coletar(amb.c["PontoAmostral"][0])         # modo dispositivo: não tem campanha nem equipe
    assert amb.disp.nucleo.modo == "dispositivo"


def test_dispositivo_exige_nucleo_em_modo_dispositivo_e_so_a_central_recebe(amb, tmp_path):
    with pytest.raises(ErroGaema, match="modo='dispositivo'"):
        Dispositivo(amb.central, amb.a["tecnico"])
    from gaema_sd.sincronizacao import ItemSincronizacao
    item = ItemSincronizacao.de_registro(amb.c["PontoAmostral"][0], "CRIAR")
    with pytest.raises(ErroGaema, match="central"):
        amb.disp.nucleo.receber_sincronizacao(amb.a["tecnico"], item)


def test_modo_livre_existe_so_para_teste_e_nao_confere(tmp_path, atores, cenario):
    n = Nucleo(Repositorio(":memory:"), tmp_path, modo="livre")
    n.registrar(atores["tecnico"], cenario["PontoAmostral"][0])      # sem campanha nem equipe: só em modo livre
    assert len(n.repo.listar(E.PontoAmostral)) == 1
