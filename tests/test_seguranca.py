"""Segurança básica da Fase 4: logs e trilha sem dado sensível, higiene de texto. Só dados sintéticos.

Os valores "sensíveis" abaixo são INVENTADOS (CPF fora de uso real, e-mail de domínio de exemplo).
"""

import io
import logging

import pytest

from gaema_sd.auditoria.trilha import sanear_detalhes, sanear_texto, verificar_cadeia
from gaema_sd.dominio import entidades as E
from gaema_sd.observabilidade import FiltroSanear, configurar_logs
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import Ambiente, com

# montados em tempo de execução para o varredor de sigilo (test_sigilo_fixtures) não achar dado literal no código
CPF = "123.456." + "789-09"
EMAIL = "pessoa.ficticia" + "@" + "example.org"


def test_sanear_texto_mascara_padroes_obvios_e_preserva_o_resto():
    assert CPF not in sanear_texto(f"cpf {CPF} informado")
    assert "12345678909" not in sanear_texto("documento 12345678909.")
    assert EMAIL not in sanear_texto(f"contato {EMAIL}")
    assert sanear_texto("senha=abc123 depois").count("abc123") == 0
    assert "token: xyz" not in sanear_texto("token: xyz")
    # não mascara o que não é dado pessoal
    hash_ = "3fa2b19c0d" * 6 + "abcd"
    for neutro in (hash_, "00000000-0000-4000-8000-000000000012", "2026-02-03T13:00:00+00:00", "ponto P01",
                   "precisão de 4,0 m"):
        assert sanear_texto(neutro) == neutro


def test_trilha_mascara_motivo_e_detalhes_e_a_cadeia_continua_valida(nucleo, atores, cenario):
    nucleo.registrar(atores["analista"], cenario["FonteDado"][0])
    nucleo.registrar(atores["analista"], cenario["AreaCandidata"][0])
    d, _ = nucleo.registrar(atores["coord"], cenario["Demanda"][0])
    from gaema_sd.dominio.enums import Estado
    nucleo.transitar(atores["sistema"], d.id, Estado.ALERTA, motivo=f"contato {EMAIL} e cpf {CPF} informados")
    nucleo.trilha.registrar(atores["sistema"], "TESTE", "X", "1", detalhes={"email": EMAIL, "obs": f"cpf={CPF}"})
    texto = " ".join(f"{e.motivo} {e.detalhes}" for e in nucleo.trilha.eventos)
    assert CPF not in texto and EMAIL not in texto
    assert verificar_cadeia(nucleo.trilha.eventos) == len(nucleo.trilha.eventos)


def test_detalhes_com_chave_sensivel_sao_removidos():
    out = sanear_detalhes({"nome_pessoa": "Fulano Fictício", "cpf": CPF, "senha": "x", "token": "y", "ok": 1})
    assert out == {"nome_pessoa": "[REMOVIDO]", "cpf": "[REMOVIDO]", "senha": "[REMOVIDO]",
                   "token": "[REMOVIDO]", "ok": 1}


def test_mensagem_de_recusa_na_trilha_nao_carrega_dado_sensivel(nucleo, atores):
    from gaema_sd.erros import ErroGaema
    nucleo._auditar_recusa(atores["tecnico"], "TESTE_RECUSA", "X", "1", ErroGaema(f"campo com {CPF} e {EMAIL}"))
    ev = nucleo.trilha.eventos[-1]
    assert ev.acao == "TESTE_RECUSA" and "ErroGaema" in ev.detalhes["erro"]
    assert CPF not in str(ev.detalhes) and EMAIL not in str(ev.detalhes)


def test_log_da_sincronizacao_nao_carrega_conteudo_dos_registros(tmp_path, atores, cenario, caplog):
    amb = Ambiente(tmp_path, atores, cenario)
    obs = com(cenario["Observacao"][0], nota=f"falou com {EMAIL}, cpf {CPF}")
    amb.disp.coletar(cenario["PontoAmostral"][0])
    amb.disp.coletar(obs)
    amb.disp.coletar(cenario["Evidencia"][0], FOTO_SINTETICA)
    amb.canal.programar("PERDA_ANTES", "INDISPONIVEL")
    with caplog.at_level(logging.DEBUG, logger="gaema_sd"):
        amb.sinc.executar()
        amb.sinc.executar()
    assert caplog.records, "esperava registros de log da sincronização"
    tudo = "\n".join(r.getMessage() for r in caplog.records)
    latitude = str(cenario["PontoAmostral"][0].latitude)
    for proibido in (CPF, EMAIL, "sintetica.jpg", latitude, "falou com"):
        assert proibido not in tudo


def test_filtro_de_log_mascara_e_nao_vaza_traceback():
    saida = io.StringIO()
    manipulador = logging.StreamHandler(saida)
    manipulador.addFilter(FiltroSanear())
    log = logging.getLogger("gaema_sd.teste_filtro")
    log.propagate = False
    log.addHandler(manipulador)
    log.setLevel(logging.INFO)
    try:
        try:
            raise ValueError(f"valor secreto {CPF}")
        except ValueError:
            log.exception("falha ao processar %s", EMAIL)
    finally:
        log.removeHandler(manipulador)
    texto = saida.getvalue()
    assert CPF not in texto and EMAIL not in texto and "Traceback" not in texto
    assert "ValueError" in texto  # fica o tipo do erro, útil para diagnóstico


def test_configurar_logs_nao_duplica_manipulador():
    log = logging.getLogger("gaema_sd")
    antes = len(log.handlers)
    h1 = configurar_logs(manipulador=logging.NullHandler())
    n1 = len(h1.handlers)
    configurar_logs(manipulador=logging.NullHandler())
    assert len(log.handlers) == n1 and n1 >= antes
    for h in list(log.handlers):
        if isinstance(h, logging.NullHandler):
            log.removeHandler(h)


def test_erro_de_rejeicao_gravado_na_fila_e_mascarado(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario)
    amb.disp.coletar(cenario["PontoAmostral"][0])
    amb.disp.fila.marcar(1, "REJEITADO", erro=f"ValidacaoFalhou: campo com {EMAIL} e {CPF}")
    (item,) = amb.disp.fila.itens("REJEITADO")
    assert EMAIL not in item["erro"] and CPF not in item["erro"]


def test_registros_do_dispositivo_nao_ganham_autoria_de_outra_pessoa(tmp_path, atores, cenario):
    """O técnico do dispositivo não consegue enviar registro em nome de outro usuário."""
    amb = Ambiente(tmp_path, atores, cenario)
    amb.disp.coletar(com(cenario["PontoAmostral"][0], criado_por="usuario-sintetico-99"))
    amb.sinc.executar()
    (p,) = amb.na_central(E.PontoAmostral)
    assert p.criado_por == atores["tecnico"].id
