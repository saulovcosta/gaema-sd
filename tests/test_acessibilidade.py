"""Acessibilidade do relatório HTML — verificações AUTOMÁTICAS (Fase 4).

Isto NÃO substitui teste com leitor de tela (NVDA/VoiceOver/TalkBack) nem com pessoas usuárias:
esse teste manual segue NÃO EXECUTADO. A razão de contraste usa a fórmula pública do WCAG 2.x
(luminância relativa); o mínimo 4,5:1 é o critério AA para texto normal.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from gaema_sd import demo


@pytest.fixture(scope="module")
def html(tmp_path_factory):
    r = demo.executar(tmp_path_factory.mktemp("demo-acess"), verbose=False)
    return Path(r["relatorios"][0]).read_text(encoding="utf-8")


class Estrutura(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.titulos, self.tabelas, self.ids = [], [], [], set()
        self.lang = None
        self.th_sem_scope = 0
        self.tabela_atual = None
        self._titulo_aberto = None
        self.links_ancora, self.svg = [], None
        self.externos = []
        self.rotulos_secao = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag in ("h1", "h2", "h3", "h4"):
            self._titulo_aberto = tag
        if tag == "table":
            self.tabela_atual = {"caption": False, "th": 0}
            self.tabelas.append(self.tabela_atual)
        if tag == "caption" and self.tabela_atual is not None:
            self.tabela_atual["caption"] = True
        if tag == "th":
            self.tabela_atual["th"] += 1
            if a.get("scope") not in ("col", "row"):
                self.th_sem_scope += 1
        if tag == "a" and a.get("href", "").startswith("#"):
            self.links_ancora.append(a["href"][1:])
        if tag == "svg":
            self.svg = a
        if tag == "section" and "aria-labelledby" in a:
            self.rotulos_secao.append(a["aria-labelledby"])
        for atributo in ("src", "href", "action"):
            if a.get(atributo, "").startswith(("http:", "https:", "//")):
                self.externos.append((tag, a[atributo]))
        if tag in ("script", "iframe", "object", "embed", "form", "link"):
            self.externos.append((tag, "proibido"))

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4"):
            self._titulo_aberto = None
        if tag == "table":
            self.tabela_atual = None

    def handle_data(self, data):
        if self._titulo_aberto and data.strip():
            self.titulos.append((int(self._titulo_aberto[1]), data.strip()))


@pytest.fixture(scope="module")
def e(html):
    p = Estrutura()
    p.feed(html)
    return p


def test_idioma_titulo_e_metadados(html, e):
    assert e.lang == "pt-BR"
    assert re.search(r"<title>[^<]{5,}</title>", html)
    assert 'name="viewport"' in html


def test_um_h1_e_hierarquia_de_titulos_sem_saltos(e):
    niveis = [n for n, _ in e.titulos]
    assert niveis.count(1) == 1 and niveis[0] == 1
    for anterior, atual in zip(niveis, niveis[1:]):
        assert atual - anterior <= 1, f"salto de título de h{anterior} para h{atual}"
    assert all(texto for _, texto in e.titulos)


def test_marcos_de_pagina_e_secoes_rotuladas(e):
    for tag in ("header", "main", "footer"):
        assert e.tags.count(tag) == 1
    assert e.rotulos_secao and all(r in e.ids for r in e.rotulos_secao)  # aria-labelledby aponta para id real


def test_tabelas_tem_legenda_e_cabecalhos_com_escopo(e):
    assert e.tabelas and all(t["caption"] and t["th"] >= 1 for t in e.tabelas)
    assert e.th_sem_scope == 0


def test_mapa_svg_tem_papel_nome_e_descricao(html, e):
    assert e.svg["role"] == "img"
    for ref in e.svg["aria-labelledby"].split():
        assert ref in e.ids, f"aria-labelledby aponta para {ref}, que não existe"
    assert "<figcaption>" in html


def test_link_de_salto_aponta_para_o_conteudo_e_foco_visivel(html, e):
    assert e.links_ancora and all(destino in e.ids for destino in e.links_ancora)
    assert ":focus-visible" in html and "outline" in html


def test_sem_script_recurso_externo_nem_estilo_inline_em_elementos(html, e):
    assert e.externos == []
    assert not re.search(r"<[a-z]+[^>]*\sstyle=", html)  # estilo só na folha <style>, não em atributos
    assert "default-src 'none'" in html


# ---- contraste (WCAG 2.x) -------------------------------------------------------------------------------

def _rgb(hexa):
    h = hexa.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _luminancia(hexa):
    def canal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in _rgb(hexa))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razao_contraste(a, b):
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_formula_de_contraste_confere_com_valores_conhecidos_do_wcag():
    assert razao_contraste("#000000", "#ffffff") == pytest.approx(21.0)
    assert razao_contraste("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)  # valor de referência conhecido


def test_contraste_dos_pares_texto_fundo_do_relatorio(html):
    cores = dict(re.findall(r"--([a-z]+)\s*:\s*(#[0-9a-fA-F]{3,6})", html))
    assert {"texto", "fundo", "destaque", "suave", "borda"} <= cores.keys()
    pares = {
        "texto/fundo (corpo)": ("texto", "fundo"),
        "texto/suave (cabeçalho de tabela, aviso)": ("texto", "suave"),
        "destaque/fundo (faixas de aviso)": ("destaque", "fundo"),
    }
    for nome, (frente, fundo) in pares.items():
        assert razao_contraste(cores[frente], cores[fundo]) >= 4.5, nome
    # componentes de interface/bordas: mínimo 3:1 (WCAG 1.4.11)
    assert razao_contraste(cores["borda"], cores["fundo"]) >= 3.0
