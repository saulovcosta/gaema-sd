"""Rodada 5: auditoria comparativa escrita e decisões do coordenador. Conferências de documento (UNITÁRIO)."""

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
AUDITORIA = (RAIZ / "docs" / "auditoria-comparativa.md").read_text(encoding="utf-8")
PENDENCIAS = (RAIZ / "docs" / "pendencias.md").read_text(encoding="utf-8")
COLUNAS = ["#", "Função pública do SIPADE", "Fonte", "O que o GAEMA SD tem", "Teste", "Lacuna", "Prioridade (sugestão)"]
VEDADAS = [r"homologad[oa]s?\b", r"\bperfeit[oa]s?\b", r"\bem produção\b", r"\bpronto para produção\b"]


def _linhas_tabela():
    return [l for l in AUDITORIA.splitlines() if re.match(r"\| \d+ \|", l)]


def test_tabela_tem_as_colunas_pedidas_e_toda_linha_completa():
    assert "| " + " | ".join(COLUNAS) + " |" in AUDITORIA
    linhas = _linhas_tabela()
    assert len(linhas) >= 20
    for l in linhas:
        celulas = [c.strip() for c in l.strip().strip("|").split("|")]
        assert len(celulas) == len(COLUNAS), l
        assert re.search(r"\bF(1|2|11|12)\b", celulas[2]), f"sem fonte pública: {l}"
        assert all(celulas), l


def test_todo_teste_citado_existe():
    citados = re.findall(r"`tests/(test_\w+\.py)::(test_\w+)`", AUDITORIA)
    assert len(citados) >= 15
    for arquivo, nome in citados:
        arvore = ast.parse((RAIZ / "tests" / arquivo).read_text(encoding="utf-8"))
        nomes = {n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)}
        assert nome in nomes, f"{arquivo}::{nome} não existe"


def test_divergencia_3_por_4_registrada_sem_conciliar_e_com_a_fonte_certa():
    secao = AUDITORIA.split("## 1.")[1].split("## 2.")[0]
    assert "**3** estados" in secao and "F11" in secao and "**4** cenários" in secao and "F1 " in secao
    assert "não escolhe nem concilia" in secao
    assert "vêm do vídeo F11, não do artigo F2" in secao


def test_abrampa_sem_pdf_nao_vira_lista():
    secao = AUDITORIA.split("## 3. ABRAMPA SOLOS")[1].split("## 4.")[0]
    assert "O PDF não está no repositório" in secao and "nenhum item da ABRAMPA SOLOS foi listado" in secao
    assert not re.search(r"^\s*(\d+\.|-|\|)", secao, re.MULTILINE), "não pode haver lista de itens da ABRAMPA"
    assert not [p for p in RAIZ.rglob("*") if "abrampa" in p.name.lower() and ".git" not in p.parts]


def test_nao_copia_texto_nem_tela_e_sem_linguagem_vedada():
    assert "Compara-se só **função**" in AUDITORIA and "Nenhuma tela, texto ou identidade visual do SIPADE foi copiada" in AUDITORIA
    for padrao in VEDADAS:
        assert not re.search(padrao, AUDITORIA, re.IGNORECASE), padrao


def test_decisoes_do_coordenador_registradas_como_nao_implementadas():
    secao = PENDENCIAS.split("## 4. Decisões do coordenador (não implementadas)")[1]
    assert "Nada nesta seção foi implementado" in secao
    for chave in ("imóvel", "DEC-006", "V-08", "H-I01", "LA-04", "LA-05", "H-I08", "autoatribuicao_tecnico", "R-31",
                  "leitor de tela", "CAOMA", "ABRAMPA"):
        assert chave in secao, chave
    assert "DEC-006 (fronteira técnica e jurídica)" in secao
