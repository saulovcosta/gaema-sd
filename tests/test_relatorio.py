"""Relatório reproduzível (HTML e PDF), evidências guardadas e reemissão."""

import dataclasses
import hashlib
import re
import shutil
import subprocess
from datetime import datetime, timezone

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import CategoriaEvidencia, Estado, FormatoRelatorio, ResultadoRevisao
from gaema_sd.erros import AcessoNegado, ErroGaema, ValidacaoFalhou
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio
from gaema_sd.relatorio import html as rhtml
from gaema_sd.relatorio import montagem
from gaema_sd.relatorio import pdf as rpdf
from gaema_sd.sinteticos import FOTO_SINTETICA

from .test_regressao_revisao import levar_ate_revisao

FIXO = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
SECOES = ["1. Identificação da demanda", "2. Objetivo", "3. Área e mapa", "4. Fontes de dados",
          "5. Metodologia e versão do protocolo", "6. Equipe", "7. Pontos amostrados", "8. Observações de campo",
          "9. Medições de resistência à penetração", "10. Evidências", "11. Resultado computado",
          "12. Revisão técnica", "13. Limitações", "14. Recomendações", "15. Monitoramento",
          "16. Versão do relatório e histórico", "Avisos"]


@pytest.fixture
def n(tmp_path):
    repo = Repositorio(":memory:")
    yield Nucleo(repo, tmp_path)
    repo.fechar()


@pytest.fixture
def emitido(n, atores, cenario):
    demanda_id, diag = levar_ate_revisao(n, atores, cenario)
    n.registrar(atores["revisor"], E.RevisaoTecnica(
        diagnostico_id=diag.id, revisor_id="", resultado=ResultadoRevisao.APROVADO,
        fundamentacao="Conferidas observações, medições e fotos do ponto P01."))
    n.transitar(atores["revisor"], demanda_id, Estado.DIAGNOSTICO_EMITIDO)
    return demanda_id


def _texto_pdf(caminho):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext indisponível")
    return subprocess.run(["pdftotext", "-layout", str(caminho), "-"], capture_output=True, text=True,
                          check=True).stdout


def test_html_tem_todas_as_secoes_e_avisos(n, atores, emitido):
    rel, caminho = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.HTML)
    texto = caminho.read_text(encoding="utf-8")
    for secao in SECOES:
        assert secao in texto, secao
    assert "não é prova material absoluta" in texto and "declarações do dispositivo" in texto
    assert "MODO DESCRITIVO" in texto and "PROTÓTIPO DE TESTE" not in texto
    assert rel.hash_conteudo == hashlib.sha256(caminho.read_bytes()).hexdigest()
    assert (rel.numero_versao, rel.formato) == (1, FormatoRelatorio.HTML)


def test_pdf_valido_com_todas_as_secoes(n, atores, emitido):
    rel, caminho = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.PDF)
    conteudo = caminho.read_bytes()
    assert conteudo.startswith(b"%PDF") and rel.hash_conteudo == hashlib.sha256(conteudo).hexdigest()
    texto = " ".join(_texto_pdf(caminho).split())
    for secao in SECOES:
        assert " ".join(secao.split()) in texto, secao


def test_mesmos_dados_mesmo_arquivo(n, atores, emitido):
    dados = montagem.montar(n.repo, emitido, numero_versao=1, gerado_em=FIXO, gerado_por="x", eventos=n.trilha.eventos)
    assert rhtml.renderizar(dados) == rhtml.renderizar(dados)
    assert rpdf.renderizar(dados) == rpdf.renderizar(dados)


def test_reemissao_gera_nova_versao_e_preserva_anterior(n, atores, emitido):
    v1, c1 = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.HTML)
    bytes_v1 = c1.read_bytes()
    with pytest.raises(ErroGaema, match="motivo"):
        n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.HTML)
    v2, c2 = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.HTML,
                                motivo_reemissao="Correção de grafia no objetivo")
    assert (v2.numero_versao, v2.substitui_relatorio_id) == (2, v1.id)
    assert c1.read_bytes() == bytes_v1 and c1 != c2
    texto = c2.read_text(encoding="utf-8")
    assert v1.hash_conteudo in texto and "Correção de grafia no objetivo" in texto
    assert len([r for r in n.repo.listar(E.Relatorio)]) == 2


def test_emissao_exige_papel_e_diagnostico_emitido(n, atores, cenario):
    demanda_id, _ = levar_ate_revisao(n, atores, cenario)
    with pytest.raises(AcessoNegado):
        n.emitir_relatorio(atores["tecnico"], demanda_id)
    with pytest.raises(ErroGaema, match="DIAGNOSTICO_EMITIDO"):
        n.emitir_relatorio(atores["coord"], demanda_id)


def test_texto_malicioso_e_escapado(n, atores, emitido):
    d = n.repo.obter(E.Demanda, emitido)
    n.atualizar(atores["coord"], dataclasses.replace(
        d, objetivo='<script>alert(1)</script><img src="http://x/y.png"> & <b>negrito</b>'), d.versao)
    _, c = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.HTML)
    texto = c.read_text(encoding="utf-8")
    assert "<script" not in texto and "&lt;script&gt;" in texto and "<img" not in texto
    _, p = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.PDF)
    assert "<script>alert(1)</script>" in " ".join(_texto_pdf(p).split())


def test_acessibilidade_basica_do_html(n, atores, emitido):
    _, c = n.emitir_relatorio(atores["coord"], emitido, FormatoRelatorio.HTML)
    t = c.read_text(encoding="utf-8")
    assert '<html lang="pt-BR">' in t and "<title>" in t
    assert t.count("<table") == t.count("<caption")
    assert all('scope="' in th for th in re.findall(r"<th(?:\s[^>]*)?>", t))
    assert 'role="img"' in t and '<title id="mapa-titulo">' in t and '<desc id="mapa-desc">' in t
    assert not re.search(r'(src|href)="https?://', t) and "<script" not in t
    niveis = [int(x) for x in re.findall(r"<h([1-6])", t)]
    assert niveis[0] == 1 and all(b - a <= 1 for a, b in zip(niveis, niveis[1:]))


def test_relatorio_nao_tem_campos_de_conclusao_juridica(n, atores, emitido):
    from .test_fronteira_juridica import PROIBIDO

    dados = montagem.montar(n.repo, emitido, numero_versao=1, gerado_em=FIXO, gerado_por="x", eventos=n.trilha.eventos)

    def chaves(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from chaves(v)
        elif isinstance(x, list):
            for v in x:
                yield from chaves(v)

    assert [k for k in chaves(dados) if PROIBIDO.search(k)] == []


# ------------------------------------------------------------------ evidências


def _evidencia(cenario, **kw):
    base = dataclasses.replace(cenario["Evidencia"][0], id=E.novo_id(), sha256="", registrado_por="",
                               chave_idempotencia="disp-sint:P01:foto-nova")
    return dataclasses.replace(base, **kw)


def test_evidencia_guarda_original_por_hash_sem_duplicar(n, atores, cenario, tmp_path):
    ev = n.registrar_evidencia(atores["tecnico"], _evidencia(cenario), FOTO_SINTETICA)
    arquivo = tmp_path / ev.armazenamento_ref
    assert arquivo.read_bytes() == FOTO_SINTETICA and ev.sha256 == hashlib.sha256(FOTO_SINTETICA).hexdigest()
    assert ev.registrado_por == atores["tecnico"].id and ev.tamanho_bytes == len(FOTO_SINTETICA)
    again = n.registrar_evidencia(atores["tecnico"], _evidencia(cenario, id=ev.id), FOTO_SINTETICA)
    assert again.id == ev.id and len(list((tmp_path / "evidencias").iterdir())) == 1
    assert n.verificar_evidencia(atores["auditor"], ev.id) is True


def test_evidencia_invalida_ou_corrompida(n, atores, cenario, tmp_path):
    with pytest.raises(ValidacaoFalhou, match="JPEG"):
        n.registrar_evidencia(atores["tecnico"], _evidencia(cenario), b"MZ\x90executavel")
    assert n.trilha.eventos[-1].acao == "ANEXO_RECUSADO" and not (tmp_path / "evidencias").exists()
    with pytest.raises(ValidacaoFalhou, match="hash informado"):
        n.registrar_evidencia(atores["tecnico"], _evidencia(cenario, sha256="0" * 64), FOTO_SINTETICA)
    ev = n.registrar_evidencia(atores["tecnico"], _evidencia(cenario), FOTO_SINTETICA)
    (tmp_path / ev.armazenamento_ref).write_bytes(FOTO_SINTETICA + b"alterado")
    assert n.verificar_evidencia(atores["auditor"], ev.id) is False


def test_evidencia_exige_papel(n, atores, cenario):
    with pytest.raises(AcessoNegado):
        n.registrar_evidencia(atores["coord"], _evidencia(cenario), FOTO_SINTETICA)
    assert dataclasses.replace(_evidencia(cenario)).categoria is CategoriaEvidencia.FOTO_SOLO
