"""Fase 5 (iii): pacote de exportação em formato PRÓPRIO (RQ-67). Não é o formato do Painel (LA-10)."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from gaema_sd import demo
from gaema_sd.erros import AcessoNegado
from gaema_sd.exportacao import FORMATO, esquema_json, montar_pacote, serializar
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio

RAIZ = Path(__file__).resolve().parents[1]
QUANDO = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
# mesma regex do teste de fronteira jurídica: nenhuma chave do pacote pode sugerir conclusão jurídica ou identificar imóvel/pessoa
PROIBIDO = re.compile(r"(^|_)(ilicit|culpa|dolo|nexo|responsabil|infrator|infracao|autor(ia)?(_|$)|dano|sancao|multa|"
                      r"proprietari|possuidor|ocupante|imovel|matricula|cpf|cnpj|nome|condena|crime|"
                      r"latitude|longitude|geometria|coordenada|titulo|objetivo|descricao|referencia)")


@pytest.fixture(scope="module")
def demo_pronta(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("exp")
    demo.executar(pasta, verbose=False)
    return pasta


@pytest.fixture
def nucleo_demo(demo_pronta):
    repo = Repositorio(str(demo_pronta / "gaema-demo.db"))
    yield Nucleo(repo, demo_pronta)
    repo.fechar()


def _chaves(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from _chaves(v)
    elif isinstance(x, list):
        for i in x:
            yield from _chaves(i)


def test_pacote_obedece_ao_esquema_gerado_e_ao_arquivo_versionado(nucleo_demo):
    pacote = nucleo_demo.exportar_painel(demo.ATORES["coord"], gerado_em=QUANDO)
    jsonschema.Draft202012Validator(esquema_json()).validate(pacote)
    em_disco = json.loads((RAIZ / "schemas" / "exportacao-painel.schema.json").read_text("utf-8"))
    assert em_disco == esquema_json()
    assert pacote["formato"] == FORMATO and pacote["todos_sinteticos"] is True


def test_conteudo_confere_com_o_banco_da_demonstracao(nucleo_demo):
    p = nucleo_demo.exportar_painel(demo.ATORES["membro"], gerado_em=QUANDO)
    (d,) = p["demandas"]
    assert d["estado"] == "EM_MONITORAMENTO" and d["criterio_priorizacao"] == "ART17_II"
    assert d["origens_alerta"] == ["PECA_INFORMACAO_TECNICA"]
    assert (d["campanhas"], d["pontos"], d["evidencias"], d["medicoes_penetracao"]) == (1, 3, 1, 3)
    assert d["observacoes"] == 22
    assert d["diagnostico"]["rotulo_validade"].startswith("PROTÓTIPO DE TESTE")
    assert [(r["formato"], r["numero_versao"]) for r in d["relatorios"]] == [("HTML", 2), ("PDF", 1)]
    assert len(d["marcos"]) == 2 and p["agregados"]["marcos_por_situacao"] == {"PREVISTO": 2}
    assert p["agregados"]["por_estado"] == {"EM_MONITORAMENTO": 1}
    assert p["agregados"]["com_relatorio_emitido"] == 1


def test_pacote_sem_campos_vedados_nem_dados_de_localizacao_ou_texto_livre(nucleo_demo):
    pacote = nucleo_demo.exportar_painel(demo.ATORES["coord"], gerado_em=QUANDO)
    ruins = [k for k in _chaves(pacote) if PROIBIDO.search(k)]
    assert ruins == []
    texto = serializar(pacote).decode("utf-8")
    assert "POLYGON" not in texto and "-10.49" not in texto and "Demanda sintética" not in texto
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", texto)


def test_exportacao_e_deterministica_e_auditada(nucleo_demo):
    antes = sum(e.acao == "EXPORTACAO" for e in nucleo_demo.trilha.eventos)
    a = serializar(nucleo_demo.exportar_painel(demo.ATORES["coord"], gerado_em=QUANDO))
    b = serializar(nucleo_demo.exportar_painel(demo.ATORES["coord"], gerado_em=QUANDO))
    assert a == b
    eventos = [e for e in nucleo_demo.trilha.eventos if e.acao == "EXPORTACAO"]
    assert len(eventos) == antes + 2 and eventos[-1].detalhes["demandas"] == 1
    assert eventos[-1].detalhes["hash"] == hashlib.sha256(a).hexdigest()
    assert nucleo_demo.verificar_auditoria(demo.ATORES["auditor"]) > 0


def test_filtro_por_demanda(nucleo_demo):
    assert nucleo_demo.exportar_painel(demo.ATORES["coord"], demanda_ids=["inexistente"])["demandas"] == []


@pytest.mark.parametrize("papel", ["analista", "tecnico", "revisor", "auditor", "sistema"])
def test_acesso_indevido_a_exportacao(nucleo_demo, papel):
    with pytest.raises(AcessoNegado):
        nucleo_demo.exportar_painel(demo.ATORES[papel])
    assert nucleo_demo.trilha.eventos[-1].acao == "ACESSO_NEGADO"


def test_exportacao_vazia_e_valida(tmp_path):
    n = Nucleo(Repositorio(":memory:"), tmp_path)
    from gaema_sd.acesso import Ator
    from gaema_sd.dominio.enums import Papel
    p = n.exportar_painel(Ator.de("usuario-sintetico-03", Papel.COORDENADOR), gerado_em=QUANDO)
    jsonschema.Draft202012Validator(esquema_json()).validate(p)
    assert p["demandas"] == [] and p["agregados"]["demandas"] == 0 and p["todos_sinteticos"] is True


def test_montar_pacote_so_le(nucleo_demo):
    antes = nucleo_demo.repo.con.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
    montar_pacote(nucleo_demo.repo, gerado_por_papeis=["COORDENADOR"], gerado_em=QUANDO)
    assert nucleo_demo.repo.con.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == antes
