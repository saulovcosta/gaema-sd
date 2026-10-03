"""Cabeçalho institucional do relatório (HTML e PDF) e endosso configurável.
Regra: sem endosso válido em config/endosso.json, a palavra "endosso" só aparece na negativa."""

import hashlib
import json
import re
from datetime import date, timedelta

import pytest

from gaema_sd import config
from gaema_sd.dominio.enums import FormatoRelatorio
from gaema_sd.relatorio import institucional, pdf

from .test_relatorio import _texto_pdf, emitido, n  # noqa: F401 - fixtures reaproveitadas

NEGATIVA = "Sem endosso institucional formal"
HASH_LOGO = "30077f41ddd7b858ffe4bdc6d1be0230e4b8ee1ebc6b51c20ce49188a63a6af3"


def _escrever(tmp_path, ato, data):
    arq = tmp_path / "endosso.json"
    arq.write_text(json.dumps({"ato_numero": {"valor": ato}, "ato_data": {"valor": data}}), encoding="utf-8")
    return arq


def _so_negativa(texto: str) -> None:
    """Toda ocorrência de "endoss" está dentro da frase negativa; nunca "Endossado"."""
    plano = " ".join(texto.split())
    assert "ndossad" not in plano.lower()
    ocorrencias = [m.start() for m in re.finditer("endoss", plano, re.IGNORECASE)]
    negativas = [m.start() + len("Sem ") for m in re.finditer(NEGATIVA, plano)]
    assert ocorrencias and set(ocorrencias) <= set(negativas), plano[:300]


def _emitir(n, atores, demanda, formato):
    _, caminho = n.emitir_relatorio(atores["coord"], demanda, formato,
                                    motivo_reemissao="Nova emissão para conferir o cabeçalho (teste).")
    return caminho


# ---------------------------------------------------------------- configuração

def test_configuracao_do_repositorio_esta_vazia_por_padrao():
    dados = json.loads(config.CAMINHO_ENDOSSO.read_text(encoding="utf-8"))
    assert dados["ato_numero"]["valor"] == "" and dados["ato_data"]["valor"] == ""
    assert config.endosso() is None


@pytest.mark.parametrize("ato,data", [
    ("", ""), ("12/2026", ""), ("", "01/02/2026"), ("12/2026", "31/02/2026"), ("12/2026", "2026-02-01"),
    ("12/2026", "1/2/2026"), ("<script>", "01/02/2026"), ("x" * 41, "01/02/2026"),
])
def test_endosso_incompleto_ou_invalido_vale_como_sem_endosso(tmp_path, ato, data):
    assert config.endosso(_escrever(tmp_path, ato, data)) is None


def test_endosso_com_data_futura_ou_arquivo_ruim_vale_como_sem_endosso(tmp_path):
    amanha = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")
    assert config.endosso(_escrever(tmp_path, "12/2026", amanha), ate=date.today()) is None
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{ não é json", encoding="utf-8")
    assert config.endosso(ruim) is None and config.endosso(tmp_path / "nao-existe.json") is None


def test_linha_institucional():
    assert institucional.linha_institucional(None) == \
        "Protótipo em desenvolvimento no âmbito do CAOMA. Sem endosso institucional formal."
    assert institucional.linha_institucional({"ato": "12/2026", "data": "01/02/2026"}) == \
        "Endossado pelo CAOMA, ato nº 12/2026, de 01/02/2026"


# ---------------------------------------------------------------- relatório sem endosso

def test_relatorio_sem_endosso_nunca_afirma_endosso_html_e_pdf(n, atores, emitido):
    html = _emitir(n, atores, emitido, FormatoRelatorio.HTML).read_text(encoding="utf-8")
    _so_negativa(re.sub(r"<[^>]+>", " ", html))
    _so_negativa(_texto_pdf(_emitir(n, atores, emitido, FormatoRelatorio.PDF)))


def test_relatorio_com_endosso_parcial_continua_sem_endosso(n, atores, emitido, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CAMINHO_ENDOSSO", _escrever(tmp_path, "12/2026", ""))
    html = _emitir(n, atores, emitido, FormatoRelatorio.HTML).read_text(encoding="utf-8")
    _so_negativa(re.sub(r"<[^>]+>", " ", html))


def test_relatorio_com_endosso_valido_troca_a_linha(n, atores, emitido, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CAMINHO_ENDOSSO", _escrever(tmp_path, "12/2026", "01/02/2026"))
    html = _emitir(n, atores, emitido, FormatoRelatorio.HTML).read_text(encoding="utf-8")
    assert "Endossado pelo CAOMA, ato nº 12/2026, de 01/02/2026" in html and NEGATIVA not in html
    texto = " ".join(_texto_pdf(_emitir(n, atores, emitido, FormatoRelatorio.PDF)).split())
    assert "Endossado pelo CAOMA, ato nº 12/2026, de 01/02/2026" in texto and NEGATIVA not in texto


# ---------------------------------------------------------------- cabeçalho

def test_logo_guardado_em_assets_sem_alteracao():
    assert hashlib.sha256(institucional.LOGO.read_bytes()).hexdigest() == HASH_LOGO


def test_cabecalho_html_logo_texto_faixa_linha_e_titulo_em_ordem(n, atores, emitido):
    t = _emitir(n, atores, emitido, FormatoRelatorio.HTML).read_text(encoding="utf-8")
    img = re.search(r'<img src="data:image/png;base64,[A-Za-z0-9+/=]+" alt="([^"]+)" width="\d+" height="\d+">', t)
    assert img and "Ministério Público do Estado do Tocantins" in img.group(1)
    posicoes = [t.index(x) for x in ('<img src="data:', "Ministério Público do Estado do Tocantins · CAOMA · GAEMA",
                                    '<p class="faixa"', NEGATIVA, "<h1>")]
    assert posicoes == sorted(posicoes)
    assert "style=" not in t and not re.search(r'(src|href)="https?:', t)       # nenhum recurso externo


def test_cabecalho_sem_logo_sai_so_com_texto(n, atores, emitido, monkeypatch):
    monkeypatch.setattr(institucional, "logo_bytes", lambda: None)
    t = _emitir(n, atores, emitido, FormatoRelatorio.HTML).read_text(encoding="utf-8")
    assert "<img" not in t and "Ministério Público do Estado do Tocantins · CAOMA · GAEMA" in t
    monkeypatch.setattr(pdf, "logo_bytes", lambda: None)
    assert "CAOMA" in _texto_pdf(_emitir(n, atores, emitido, FormatoRelatorio.PDF))


def test_pdf_tem_o_logo(n, atores, emitido):
    """O determinismo (mesmos dados → mesmo arquivo) segue em test_relatorio.py::test_mesmos_dados_mesmo_arquivo."""
    assert b"/Subtype /Image" in _emitir(n, atores, emitido, FormatoRelatorio.PDF).read_bytes()


# ---------------------------------------------------------------- tabela de pontos

def test_coordenadas_em_uma_linha(n, atores, emitido):
    t = _emitir(n, atores, emitido, FormatoRelatorio.HTML).read_text(encoding="utf-8")
    assert '<th scope="col" class="num coord">Longitude</th>' in t and '<th scope="col">Alerta de GPS</th>' in t
    assert ".coord { white-space: nowrap; }" in t
    assert re.search(r'<td class="num coord">-?\d+\.\d{6}</td><td class="num coord">-?\d+\.\d{6}</td>', t)
    assert sum(pdf.LARGURAS_PONTOS) <= pdf.LARGURA_UTIL
    texto = _texto_pdf(_emitir(n, atores, emitido, FormatoRelatorio.PDF))
    linha = next(l for l in texto.splitlines() if "Longitude" in l)
    assert "Latitude" in linha and "Capturado em" in linha            # cabeçalho inteiro numa linha só
