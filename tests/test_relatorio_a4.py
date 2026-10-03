"""Relatório para impressão: A4, bloco de identificação, datas legíveis e hashes em grupos (copiáveis inteiros)."""

import re

from gaema_sd.relatorio.html import blocos, data_br

from .test_interface import modelo  # noqa: F401 - demonstração gerada uma vez por módulo


def _html_v2(pasta):
    return next((pasta / "relatorios").glob("*-v2.html")).read_text(encoding="utf-8")


def test_impressao_em_a4_sem_corte_de_linha_de_tabela(modelo):
    t = _html_v2(modelo)
    assert "@page { size: A4;" in t
    assert re.search(r"tr, figure, \.aviso, \.ficha, table\.inteira \{ break-inside: avoid; \}", t)
    assert "thead { display: table-header-group; }" in t


def test_cabecalho_tem_faixa_e_bloco_de_identificacao_antes_das_secoes(modelo):
    t = _html_v2(modelo)
    faixa, ficha, s1 = (t.index("PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"),
                        t.index("<caption>Identificação deste documento</caption>"), t.index('id="s1"'))
    assert faixa < ficha < s1
    cabecalho = t[ficha:s1]
    for rotulo in ("Versão do relatório", "Emitido em / por", "Protocolo", "Hash da definição do protocolo",
                   "Hash das entradas de campo"):
        assert f'<th scope="row">{rotulo}' in cabecalho


def test_secoes_em_ordem_fixa(modelo):
    t = _html_v2(modelo)
    posicoes = [t.index(f'<h2 id="s{i}">') for i in range(1, 18)]
    assert posicoes == sorted(posicoes)


def test_datas_sem_microssegundos_e_hash_inteiro_no_valor(modelo):
    t = _html_v2(modelo)
    assert not re.search(r"\d{2}:\d{2}:\d{2}\.\d{6}", t)          # nada de ISO com microssegundos
    assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2} UTC", t)
    for valor in re.findall(r'<data class="hash" value="([0-9a-f]+)">', t):
        assert len(valor) == 64


def test_filtros():
    assert data_br("2026-10-03T15:12:09.492000+00:00") == "03/10/2026 15:12 UTC"
    assert data_br("2026-02-03") == "03/02/2026" and data_br("—") == "—" and data_br(None) == "—"
    h = "ab" * 32
    saida = str(blocos(h))
    assert f'value="{h}"' in saida and saida.count('class="bloco"') == 8
    assert re.sub(r"<[^>]+>", "", saida) == h                       # copiar o texto devolve o hash sem espaços
    assert "<x>" not in str(blocos("<x>"))                          # escapado no texto e no atributo
