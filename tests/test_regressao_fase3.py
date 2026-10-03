"""Regressão dos 7 achados da revisão independente da Fase 3 (03/10/2026)."""

import copy
import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gaema_sd.acesso import Ator
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.serializacao import para_dict
from gaema_sd.dominio.enums import Estado, FormatoRelatorio, Papel, ResultadoRevisao
from gaema_sd.erros import ErroGaema, TransicaoInvalida, ValidacaoFalhou
from gaema_sd.protocolo.definicao import DefinicaoInvalida, carregar_definicao, ler_arquivo
from gaema_sd.sinteticos import FOTO_SINTETICA

from .test_regressao_revisao import levar_ate_revisao

S = Estado


def _revisao(diag_id, resultado=ResultadoRevisao.APROVADO, **kw):
    return E.RevisaoTecnica(diagnostico_id=diag_id, revisor_id="", resultado=resultado,
                            fundamentacao="Conferidas observações, medições e fotos do ponto P01.", **kw)


@pytest.fixture
def emitido(nucleo, atores, cenario):
    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    nucleo.registrar(atores["revisor"], _revisao(diag.id))
    nucleo.transitar(atores["revisor"], d, S.DIAGNOSTICO_EMITIDO)
    return d, diag


# 1 ------------------------------------------------------------------------
def test_1_relatorio_nao_e_gravado_a_mao(nucleo, atores, emitido):
    d, diag = emitido
    falso = E.Relatorio(demanda_id=d, diagnostico_id=diag.id, versao_protocolo_id=diag.versao_protocolo_id,
                        hash_conteudo="0" * 64, gerado_por="")
    with pytest.raises(ErroGaema, match="emitir_relatorio"):
        nucleo.registrar(atores["coord"], falso)
    with pytest.raises(TransicaoInvalida, match="relatório não emitido"):
        nucleo.transitar(atores["membro"], d, S.ENCERRADA, motivo="tentativa sem relatório")


# 2 ------------------------------------------------------------------------
def test_2_evidencia_nao_e_gravada_sem_arquivo(nucleo, atores, cenario):
    falsa = dataclasses.replace(cenario["Evidencia"][0], sha256="a" * 64,
                                armazenamento_ref="../../../../../../../etc/passwd")
    with pytest.raises(ErroGaema, match="registrar_evidencia"):
        nucleo.registrar(atores["tecnico"], falsa)


def test_2_verificacao_usa_so_o_hash_e_nao_sai_da_pasta(nucleo, atores, cenario):
    ev = nucleo.registrar_evidencia(atores["tecnico"], cenario["Evidencia"][0], FOTO_SINTETICA)
    passwd = Path("/etc/passwd")
    adulterada = dataclasses.replace(ev, armazenamento_ref="../../../../../../../etc/passwd",
                                     sha256=hashlib.sha256(passwd.read_bytes()).hexdigest() if passwd.exists()
                                     else "b" * 64)
    # adulteração direta no banco (fora do núcleo), como faria um invasor
    nucleo.repo.con.execute("UPDATE registros SET dados=? WHERE id=?",
                            (json.dumps(para_dict(adulterada)), ev.id))
    assert nucleo.verificar_evidencia(atores["auditor"], ev.id) is False


# 3 ------------------------------------------------------------------------
def test_3_data_futura_e_ordem_de_gravacao(nucleo, atores, cenario):
    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    with pytest.raises(ValidacaoFalhou, match="futuro"):
        nucleo.registrar(atores["revisor"], _revisao(diag.id, revisado_em=datetime(2099, 1, 1, tzinfo=timezone.utc)))
    outro = Ator.de("usuario-sintetico-77", Papel.REVISOR_TECNICO)
    nucleo.registrar(atores["revisor"], _revisao(diag.id))
    nucleo.registrar(outro, _revisao(diag.id, resultado=ResultadoRevisao.REJEITADO))  # gravada depois
    with pytest.raises(TransicaoInvalida, match="revisão técnica não aprovada"):
        nucleo.transitar(atores["revisor"], d, S.DIAGNOSTICO_EMITIDO)


def test_3_relatorio_usa_revisao_de_quem_emitiu_e_recusa_rejeicao_posterior(nucleo, atores, emitido):
    d, diag = emitido
    rel, caminho = nucleo.emitir_relatorio(atores["coord"], d)
    rev_usada = nucleo.repo.obter(E.RevisaoTecnica, rel.revisao_id)
    assert rev_usada.revisor_id == atores["revisor"].id
    coletor = Ator.de(atores["tecnico"].id, Papel.TECNICO_CAMPO, Papel.REVISOR_TECNICO)
    nucleo.registrar(coletor, _revisao(diag.id))  # aprovação posterior do próprio coletor
    rel2, _ = nucleo.emitir_relatorio(atores["coord"], d, motivo_reemissao="Teste de reemissão com nova revisão")
    assert nucleo.repo.obter(E.RevisaoTecnica, rel2.revisao_id).revisor_id == atores["revisor"].id
    nucleo.registrar(Ator.de("usuario-sintetico-78", Papel.REVISOR_TECNICO),
                     _revisao(diag.id, resultado=ResultadoRevisao.REJEITADO))
    with pytest.raises(ErroGaema, match="revisão posterior não aprovada"):
        nucleo.emitir_relatorio(atores["coord"], d, motivo_reemissao="Tentativa após rejeição posterior")


# 4 ------------------------------------------------------------------------
def test_4_falha_ao_gravar_registro_nao_deixa_arquivo(nucleo, atores, emitido, monkeypatch):
    d, _ = emitido

    def falhar(*a, **k):
        raise RuntimeError("falha simulada no banco")

    monkeypatch.setattr(nucleo, "_registrar", falhar)
    with pytest.raises(RuntimeError):
        nucleo.emitir_relatorio(atores["coord"], d)
    assert list((nucleo.saida / "relatorios").glob("*")) == []
    monkeypatch.undo()
    rel, caminho = nucleo.emitir_relatorio(atores["coord"], d)
    assert rel.numero_versao == 1 and caminho.exists()


def test_4_falha_ao_escrever_arquivo_nao_deixa_registro(nucleo, atores, emitido, monkeypatch):
    d, _ = emitido
    original = Path.write_bytes

    def disco_cheio(self, dados):
        if self.name.endswith(".parcial"):
            raise OSError("sem espaço (simulado)")
        return original(self, dados)

    monkeypatch.setattr(Path, "write_bytes", disco_cheio)
    with pytest.raises(OSError):
        nucleo.emitir_relatorio(atores["coord"], d)
    assert nucleo.repo.listar(E.Relatorio) == []


# 5 ------------------------------------------------------------------------
def test_5_evidencia_recusada_nao_deixa_arquivo(nucleo, atores, cenario):
    so_lat = dataclasses.replace(cenario["Evidencia"][0], longitude_declarada=None, latitude_declarada=-10.0)
    with pytest.raises(ValidacaoFalhou, match="latitude"):
        nucleo.registrar_evidencia(atores["tecnico"], so_lat, FOTO_SINTETICA)
    assert not (nucleo.saida / "evidencias").exists() or list((nucleo.saida / "evidencias").iterdir()) == []


# 6 ------------------------------------------------------------------------
def test_6_parametro_gravado_com_diagnostico(nucleo, atores, cenario, monkeypatch):
    from gaema_sd import config

    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    assert '"gps_precisao_maxima_m":10.0' in diag.entradas_canonicas
    original = config.parametro
    monkeypatch.setattr(config, "parametro",
                        lambda nome, *a: 20.0 if nome == "gps_precisao_maxima_m" else original(nome, *a))
    assert nucleo.reproduzir_diagnostico(atores["auditor"], diag.id)["reproduzido"] is True


# 7 ------------------------------------------------------------------------
@pytest.mark.parametrize("rotulo", ["PROTOCOLO VALIDADO CIENTIFICAMENTE - LAUDO OFICIAL", 123])
def test_7_descritivo_nao_aceita_rotulo(rotulo):
    d = copy.deepcopy(ler_arquivo("gaema-descritivo-0.1.0.json"))
    d["rotulo"] = rotulo
    with pytest.raises(DefinicaoInvalida, match="rótulo"):
        carregar_definicao(d)


def test_formato_relatorio_pdf_tambem_atomico(nucleo, atores, emitido):
    d, _ = emitido
    rel, caminho = nucleo.emitir_relatorio(atores["coord"], d, FormatoRelatorio.PDF)
    assert caminho.exists() and not list(caminho.parent.glob("*.parcial"))
