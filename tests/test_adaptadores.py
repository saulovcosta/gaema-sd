"""Fase 5 (ii): adaptadores ArcGIS são só interface — sem rede, sem credencial, sem integração declarada."""

import ast
import json
from pathlib import Path

import pytest

from gaema_sd.adaptadores import (
    AmbienteIndisponivel,
    CatalogoCamadas,
    ConfigArcGIS,
    ImportadorCampo,
    NaoConfiguradoCatalogo,
    NaoConfiguradoImportador,
    NaoConfiguradoPublicador,
    PublicadorCampo,
    traduzir_submissao,
)
from gaema_sd.dominio import entidades as E
from gaema_sd.erros import AcessoNegado, ErroGaema
from gaema_sd.sincronizacao import ResultadoSincronizacao

from .apoio_sincronizacao import Ambiente

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLO = RAIZ / "adapters" / "arcgis" / "exemplos" / "submissao_sintetica.json"
MODULOS_DE_REDE = {"socket", "ssl", "http", "urllib", "requests", "httpx", "ftplib", "smtplib", "aiohttp", "arcgis",
                   "websocket", "websockets", "xmlrpc", "asyncio"}


def _submissao(**mudancas):
    dados = json.loads(EXEMPLO.read_text(encoding="utf-8"))
    dados.pop("_aviso")
    dados.update(mudancas)
    return dados


def test_implementacoes_nao_configurado_recusam_e_seguem_o_protocolo():
    for impl, proto in ((NaoConfiguradoCatalogo(), CatalogoCamadas), (NaoConfiguradoImportador(), ImportadorCampo),
                        (NaoConfiguradoPublicador(), PublicadorCampo)):
        assert isinstance(impl, proto)
    with pytest.raises(AmbienteIndisponivel, match="LA-05"):
        NaoConfiguradoCatalogo().listar_camadas()
    with pytest.raises(AmbienteIndisponivel):
        NaoConfiguradoCatalogo().consultar_sobreposicao("POLYGON EMPTY", "x")
    with pytest.raises(AmbienteIndisponivel):
        list(NaoConfiguradoImportador().baixar_submissoes())
    with pytest.raises(AmbienteIndisponivel):
        NaoConfiguradoPublicador().publicar_formulario("vistoria.xlsx")
    with pytest.raises(AmbienteIndisponivel):
        NaoConfiguradoPublicador().publicar_missao("c1")
    assert issubclass(AmbienteIndisponivel, ErroGaema)


def test_codigo_dos_adaptadores_nao_importa_modulo_de_rede():
    achados = []
    for arq in (RAIZ / "src" / "gaema_sd" / "adaptadores").glob("*.py"):
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            nomes = [a.name for a in no.names] if isinstance(no, ast.Import) else \
                [no.module or ""] if isinstance(no, ast.ImportFrom) and no.level == 0 else []
            achados += [(arq.name, n) for n in nomes if n.split(".")[0] in MODULOS_DE_REDE]
    assert achados == []


def test_codigo_dos_adaptadores_nao_tem_url_nem_credencial():
    for arq in (RAIZ / "src" / "gaema_sd" / "adaptadores").glob("*.py"):
        texto = arq.read_text(encoding="utf-8")
        assert "http://" not in texto and "https://" not in texto, arq.name
    texto = (RAIZ / "adapters" / "arcgis" / "README.md").read_text(encoding="utf-8")
    assert "Nenhuma integração está declarada" in texto and "O que NÃO foi verificado" in texto


def test_config_so_informa_se_esta_definida_e_nunca_expoe_o_valor():
    segredo = "valor-que-nao-pode-aparecer"
    cfg = ConfigArcGIS.de_ambiente({"ARCGIS_PORTAL_URL": segredo, "ARCGIS_CLIENT_ID": ""})
    assert not cfg.completa and cfg.faltando() == ("ARCGIS_CLIENT_ID",)
    assert segredo not in repr(cfg) and segredo not in str(cfg.definidas)
    assert ConfigArcGIS.de_ambiente({}).faltando() == ("ARCGIS_PORTAL_URL", "ARCGIS_CLIENT_ID")
    assert ConfigArcGIS.de_ambiente({"ARCGIS_PORTAL_URL": "a", "ARCGIS_CLIENT_ID": "b"}).completa


def test_traducao_gera_ponto_observacoes_e_medicoes_em_ordem():
    itens = traduzir_submissao(_submissao())
    assert [i.tipo for i in itens] == ["PontoAmostral"] + ["Observacao"] * 9 + ["MedicaoPenetracao"]
    ponto = itens[0].dados
    assert (ponto["latitude"], ponto["longitude"], ponto["altitude_m"], ponto["precisao_gps_m"]) == \
        (-10.495, -48.495, 250.0, 4.0)
    assert ponto["sintetico"] is True and itens[0].chave_idempotencia == "dispositivo-sintetico:P01"
    presenca = {i.dados["variavel"]: i.dados["valor_bruto"] for i in itens[1:8]}
    assert presenca["PLANTAS_INVASORAS"] == "sim" and presenca["CUPINS_MONTICULO"] == "não"
    assert all(i.dados["unidade_bruta"] == "presenca" for i in itens[1:8])
    assert itens[-1].dados["resistencia_unidade"] == "mpa" and itens[-1].dados["profundidade_bruta"] == "20"


def test_traducao_e_deterministica_e_nao_inventa_valores():
    assert traduzir_submissao(_submissao()) == traduzir_submissao(_submissao())
    sem_pen = traduzir_submissao(_submissao(penetrometria=[], outras_observacoes=[], hipotese_alternativa=""))
    assert [i.tipo for i in sem_pen].count("MedicaoPenetracao") == 0
    assert all(i.dados["valor_normalizado"] is None for i in sem_pen if i.tipo == "Observacao")


@pytest.mark.parametrize("mudanca,trecho", [
    ({"codigo_ponto": ""}, "codigo_ponto"), ({"localizacao": "abc"}, "ilegível"), ({"localizacao": "-10.5"}, "incompleta"),
    ({"presenca_sulcos": "talvez"}, "inválido"), ({"outras_observacoes": [{"outra_variavel": "NAO_EXISTE",
     "outra_valor_bruto": "1", "outra_unidade_bruta": "x"}]}, "desconhecida"),
])
def test_traducao_recusa_submissao_malformada(mudanca, trecho):
    with pytest.raises(ErroGaema, match=trecho):
        traduzir_submissao(_submissao(**mudanca))


def test_submissao_entra_pelo_nucleo_e_reimportacao_nao_duplica(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario)
    itens = traduzir_submissao(_submissao())
    r1 = [amb.central.receber_sincronizacao(atores["tecnico"], i) for i in itens]
    assert set(r1) == {ResultadoSincronizacao.APLICADO}
    r2 = [amb.central.receber_sincronizacao(atores["tecnico"], i) for i in itens]
    assert set(r2) == {ResultadoSincronizacao.REENVIO_IDEMPOTENTE}
    assert len(amb.na_central(E.PontoAmostral)) == 1 and len(amb.na_central(E.Observacao)) == 9
    p = amb.na_central(E.PontoAmostral)[0]
    assert p.status_sincronizacao.value == "SINCRONIZADO" and p.criado_por == atores["tecnico"].id


def test_submissao_editada_no_campo_com_mesma_chave_vira_conflito_e_nao_sobrescreve(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario)
    for i in traduzir_submissao(_submissao()):
        amb.central.receber_sincronizacao(atores["tecnico"], i)
    outra = traduzir_submissao(_submissao(localizacao="-10.4999 -48.4999 250.0 4.0"))[0]
    assert amb.central.receber_sincronizacao(atores["tecnico"], outra) is ResultadoSincronizacao.CONFLITO
    assert amb.na_central(E.PontoAmostral)[0].latitude == -10.495


def test_importacao_exige_papel_de_campo(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario)
    with pytest.raises(AcessoNegado):
        amb.central.receber_sincronizacao(atores["analista"], traduzir_submissao(_submissao())[0])
