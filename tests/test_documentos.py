"""Fase 5 (iv, v): documentos institucionais coerentes com o código e sem linguagem vedada."""

import re
from pathlib import Path

import pytest

from gaema_sd import demo
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado

RAIZ = Path(__file__).resolve().parents[1]
DOCS_FASE5 = ["docs/homologacao.md", "docs/pendencias.md", "docs/guia-capacitacao.md",
              "docs/integracao-radar-painel.md", "adapters/arcgis/README.md", "README.md"]
SITUACOES_VALIDAS = ("NÃO EXECUTADO", "PENDENTE", "EXECUTADO LOCALMENTE")
VEDADAS = [r"homologad[oa]s?\b", r"\bperfeit[oa]s?\b", r"\bem produção\b", r"\bpronto para produção\b"]


def _texto(rel):
    return (RAIZ / rel).read_text(encoding="utf-8")


def _linhas_checklist():
    return [l for l in _texto("docs/homologacao.md").splitlines() if re.match(r"\| H-[A-Z]\d+ ", l)]


def test_linguagem_vedada_ausente_nos_documentos_da_fase_5():
    achados = []
    for rel in DOCS_FASE5:
        for n, linha in enumerate(_texto(rel).splitlines(), 1):
            for padrao in VEDADAS:
                if re.search(padrao, linha, re.IGNORECASE):
                    achados.append((rel, n, padrao))
            if re.search(r"integrad[oa] ao MPTO", linha, re.IGNORECASE) and not re.search(
                    r"\b(n[ãa]o|nenhum[a]?|sem)\b", linha, re.IGNORECASE):
                achados.append((rel, n, "integrado ao MPTO sem negação"))
    assert achados == []


def test_checklist_nenhum_item_aprovado_e_situacao_valida():
    linhas = _linhas_checklist()
    assert len(linhas) >= 30
    ids = []
    for l in linhas:
        celulas = [c.strip() for c in l.strip().strip("|").split("|")]
        assert len(celulas) == 6, l
        ids.append(celulas[0])
        assert celulas[5].startswith(SITUACOES_VALIDAS), f"situação inválida: {l}"
        assert not re.search(r"\b(aprovad|conclu[ií]d|ok\b|passou)", celulas[5], re.IGNORECASE), l
    assert len(ids) == len(set(ids))
    categorias = {i.split("-")[1][0] for i in ids}
    assert categorias == {"C", "I", "A", "S", "F"}


def test_todo_la_de_fontes_tem_pendencia_registrada():
    fontes = {m.group(1) for m in re.finditer(r"^\| (LA-\d+) \|", _texto("docs/fontes.md"), re.MULTILINE)}
    pend = {m.group(1) for m in re.finditer(r"^\| (LA-\d+) \|", _texto("docs/pendencias.md"), re.MULTILINE)}
    assert fontes and fontes == pend


def test_la_citados_no_checklist_existem():
    fontes = _texto("docs/fontes.md")
    for la in set(re.findall(r"LA-\d+", _texto("docs/homologacao.md"))):
        assert f"| {la} |" in fontes, la


def test_arquivos_e_comandos_citados_nos_documentos_existem():
    for rel in DOCS_FASE5:
        for caminho in set(re.findall(r"`((?:docs|scripts|adapters|schemas|config)/[\w./-]+\.[a-z]+)`", _texto(rel))):
            assert (RAIZ / caminho).exists(), f"{rel} cita {caminho}, que não existe"
        for caminho in set(re.findall(r"\]\(((?:docs|scripts|adapters)/[^)#\s]+)\)", _texto(rel))):
            assert (RAIZ / caminho).exists(), f"{rel} tem link para {caminho}, que não existe"


def test_guia_traz_avisos_obrigatorios_e_todos_os_estados_normais():
    guia = _texto("docs/guia-capacitacao.md")
    for exigido in ("protótipo", "dados sintéticos", "validade científica", "não está integrado", "nenhuma turma"):
        assert exigido.lower() in guia.lower(), exigido
    estados_normais = [e for e in Estado if e.name in (
        "ALERTA", "EM_TRIAGEM", "DEMANDA_ABERTA", "ATRIBUIDA", "PLANEJADA", "EM_CAMPO", "COLETA_PARCIAL",
        "AGUARDANDO_SINCRONIZACAO", "EM_VALIDACAO", "AGUARDANDO_REVISAO", "DIAGNOSTICO_EMITIDO", "EM_TRATATIVA",
        "EM_MONITORAMENTO", "ENCERRADA", "REABERTA")]
    for e in estados_normais:
        assert e.value in guia, e.value
    assert "CONFLITO_SINCRONIZACAO".replace("_", " ").lower().split()[0] in guia.lower()


def test_guia_cita_todos_os_papeis():
    from gaema_sd.dominio.enums import Papel
    guia = _texto("docs/guia-capacitacao.md").lower()
    nomes = {"ANALISTA_TRIAGEM": "analista de triagem", "COORDENADOR": "coordenador", "TECNICO_CAMPO": "técnico de campo",
             "REVISOR_TECNICO": "revisor técnico", "MEMBRO_MP": "membro do ministério público", "AUDITOR": "auditor",
             "ADMINISTRADOR": "administrador", "SISTEMA": "sistema"}
    assert set(nomes) == {p.name for p in Papel}
    assert all(t in guia for t in nomes.values())


@pytest.fixture(scope="module")
def resultado_demo(tmp_path_factory):
    return demo.executar(tmp_path_factory.mktemp("guia"), verbose=False)


def test_gabarito_do_guia_confere_com_a_demonstracao(resultado_demo):
    r = resultado_demo
    assert r["estado_final"] == "EM_MONITORAMENTO"                                   # exercício 1
    assert sorted(demo.PONTOS) == ["P01", "P02", "P03"]                              # exercício 2
    assert {c: v[2] for c, v in demo.PONTOS.items()}["P03"] == 18.0
    from gaema_sd.config import parametro
    assert parametro("gps_precisao_maxima_m") == 10.0
    assert [Path(p).suffix for p in r["relatorios"]] == [".html", ".pdf", ".html"]   # exercício 4
    assert r["relatorio_v2"].numero_versao == 2 and r["relatorio_pdf"].numero_versao == 1
    html = Path(r["relatorios"][0]).read_text(encoding="utf-8")
    assert "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" in html                     # exercício 5
    assert "motivo da reemissão" in Path(r["relatorios"][2]).read_text(encoding="utf-8")
