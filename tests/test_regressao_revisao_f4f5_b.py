"""Regressão da revisão independente das Fases 4 e 5 (parte 2): backup, tradução, exportação, XLSForm, texto, guia.

Número do achado entre colchetes. Dados 100% sintéticos; CPF/e-mail fictícios montados em tempo de execução.
"""

import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gaema_sd import demo
from gaema_sd.adaptadores import traduzir_submissao
from gaema_sd.adaptadores import xlsform as X
from gaema_sd.auditoria.trilha import sanear_detalhes, sanear_texto
from gaema_sd.backup import BackupInvalido, criar_backup, restaurar_backup, verificar_backup
from gaema_sd.dominio import entidades as E
from gaema_sd.erros import ErroGaema
from gaema_sd.exportacao import montar_pacote, serializar
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio
from gaema_sd.protocolo.definicao import DefinicaoInvalida, ler_arquivo

from .test_backup import sistema  # noqa: F401  (fixture)

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLO = RAIZ / "adapters" / "arcgis" / "exemplos" / "submissao_sintetica.json"
CPF = "123.456." + "789-09"
EMAIL = "pessoa.ficticia" + "@" + "example.org"
QUANDO = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def _sub(**mudancas):
    dados = json.loads(EXEMPLO.read_text(encoding="utf-8"))
    dados.pop("_aviso")
    dados.update(mudancas)
    return dados


# ================= backup [5] [16] [20] ==============================================================================

def _refazer(pasta, mutar=None):
    """Atacante (ou erro) que conhece o formato: recalcula o manifesto a partir do que há na pasta."""
    m = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    arquivos = {}
    for p in sorted(pasta.rglob("*")):
        rel = p.relative_to(pasta).as_posix()
        if p.is_file() and not p.is_symlink() and rel not in ("manifesto.json", "manifesto.sha256") \
                and (rel == "gaema.db" or rel.startswith(("evidencias/", "relatorios/"))):
            arquivos[rel] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    m["arquivos"] = arquivos
    if mutar:
        mutar(m)
    texto = json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2)
    (pasta / "manifesto.json").write_text(texto, encoding="utf-8")
    (pasta / "manifesto.sha256").write_text(hashlib.sha256(texto.encode("utf-8")).hexdigest(), encoding="utf-8")


def _bk(sistema_):
    n, _, saida, tmp = sistema_
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    ruim = tmp / "ruim"
    shutil.copytree(tmp / "bk", ruim)
    return ruim, tmp


def test_5_backup_com_pasta_de_saida_errada_nao_e_criado(sistema):
    n, _, _, tmp = sistema
    with pytest.raises(BackupInvalido, match="evidência"):
        criar_backup(n.repo, tmp / "pasta_que_nao_e_a_saida", tmp / "bk")
    assert not (tmp / "bk").exists() or not any((tmp / "bk").iterdir())    # nada de backup "verde" sem arquivos


def test_5_evidencia_trocada_com_manifesto_refeito_e_detectada(sistema):
    ruim, _ = _bk(sistema)
    next((ruim / "evidencias").iterdir()).write_bytes(b"outro conteudo qualquer")
    _refazer(ruim)
    assert any("evidência" in p and "hash" in p for p in verificar_backup(ruim))


def test_5_evidencia_do_banco_ausente_no_backup_com_manifesto_refeito_e_detectada(sistema):
    ruim, tmp = _bk(sistema)
    next((ruim / "evidencias").iterdir()).unlink()
    _refazer(ruim)
    assert any("evidência" in p and "ausente" in p for p in verificar_backup(ruim))
    with pytest.raises(BackupInvalido):
        restaurar_backup(ruim, tmp / "r.db", tmp / "r")


def test_5_relatorio_trocado_ou_ausente_e_detectado(tmp_path):
    pasta = tmp_path / "demo"
    pasta.mkdir()
    demo.executar(pasta, verbose=False)
    repo = Repositorio(str(pasta / "gaema-demo.db"))
    criar_backup(repo, pasta, tmp_path / "bk")
    repo.fechar()
    assert verificar_backup(tmp_path / "bk") == []                     # controle positivo
    ruim = tmp_path / "ruim"
    shutil.copytree(tmp_path / "bk", ruim)
    alvo = next((ruim / "relatorios").glob("*.html"))
    alvo.write_text("<html>outro relatório</html>", encoding="utf-8")
    _refazer(ruim)
    assert any("relatório" in p and "hash" in p for p in verificar_backup(ruim))
    alvo.unlink()
    _refazer(ruim)
    assert any("relatório" in p and "ausente" in p for p in verificar_backup(ruim))


def test_20_manifesto_com_contagens_ou_ultimo_hash_alterados_e_detectado(sistema):
    ruim, _ = _bk(sistema)
    _refazer(ruim, lambda m: m["contagens"].update({"Evidencia": 9}))
    assert any("contagens" in p for p in verificar_backup(ruim))
    _refazer(ruim, lambda m: (m["contagens"].update({"Evidencia": 1}), m["auditoria"].update({"ultimo_hash": "0" * 64})))
    assert any("último hash" in p for p in verificar_backup(ruim))
    _refazer(ruim, lambda m: m["auditoria"].update({"ultimo_hash": m["auditoria"]["ultimo_hash"], "eventos": 1}))
    assert any("eventos" in p for p in verificar_backup(ruim))


def test_16_manifesto_ilegivel_ou_incompleto_devolve_problema_em_vez_de_excecao(sistema):
    ruim, tmp = _bk(sistema)

    def refazer_texto(texto):
        (ruim / "manifesto.json").write_text(texto, encoding="utf-8")
        (ruim / "manifesto.sha256").write_text(hashlib.sha256(texto.encode()).hexdigest(), encoding="utf-8")
    refazer_texto("{isto não é json")
    assert verificar_backup(ruim) == ["manifesto ilegível"]
    refazer_texto(json.dumps({"formato": 1}))
    (p,) = verificar_backup(ruim)
    assert "incompleto" in p
    with pytest.raises(BackupInvalido):
        restaurar_backup(ruim, tmp / "r.db", tmp / "r")


def test_16_link_simbolico_e_arquivo_fora_do_formato_sao_recusados(sistema):
    ruim, tmp = _bk(sistema)
    externo = tmp / "externo.txt"
    externo.write_text("conteudo fora do backup")
    (ruim / "evidencias" / "atalho").symlink_to(externo)
    problemas = verificar_backup(ruim)
    assert any("link simbólico" in p for p in problemas)
    (ruim / "evidencias" / "atalho").unlink()
    (ruim / "lixo").mkdir()
    (ruim / "lixo" / "x.txt").write_text("x")
    (ruim / "gaema.db-wal").write_bytes(b"sobra")
    problemas = verificar_backup(ruim)
    assert any("fora do formato" in p and "lixo/x.txt" in p for p in problemas)
    assert any("fora do formato" in p and "gaema.db-wal" in p for p in problemas)


def test_16_wal_orfao_no_destino_da_restauracao_e_recusado_com_mensagem_clara(sistema):
    ruim, tmp = _bk(sistema)
    destino = tmp / "novo" / "gaema.db"
    destino.parent.mkdir()
    Path(str(destino) + "-wal").write_bytes(b"resto de outro banco")
    with pytest.raises(ErroGaema, match="-wal|-shm"):
        restaurar_backup(tmp / "bk", destino, tmp / "novo" / "saida")
    assert not destino.exists()


def test_16_cli_nao_cria_backup_de_banco_inexistente(tmp_path, monkeypatch, capsys):
    from gaema_sd.backup.__main__ import main
    monkeypatch.setattr(sys, "argv", ["x", "criar", str(tmp_path / "nao_existe.db"), str(tmp_path), str(tmp_path / "bk")])
    assert main() == 2
    assert not (tmp_path / "nao_existe.db").exists() and not (tmp_path / "bk").exists()
    assert "não existe" in capsys.readouterr().out


# ================= tradução [6] [11] =================================================================================

def test_6_campos_coletados_sem_destino_na_traducao_nao_sao_descartados_em_silencio():
    with pytest.raises(ErroGaema, match="fotos"):
        traduzir_submissao(_sub(fotos=[{"foto_categoria": "FOTO_SOLO", "foto_arquivo": "a.jpg"}]))
    with pytest.raises(ErroGaema, match="nota_acesso"):
        traduzir_submissao(_sub(condicao_acesso="SEM_ACESSO", nota_acesso="Porteira trancada."))
    with pytest.raises(ErroGaema, match="condicao_acesso"):
        traduzir_submissao(_sub())          # o exemplo traz condicao_acesso: quem chama precisa decidir
    itens = traduzir_submissao(_sub(), ignorar_nao_traduzidos=True)
    assert itens[0].tipo == "PontoAmostral"


def test_11_repeticao_de_penetrometria_duplicada_e_recusada():
    dupla = [{"pen_repeticao": 1, "pen_profundidade": 20, "pen_profundidade_unidade": "cm", "pen_resistencia": 1.4,
              "pen_resistencia_unidade": "mpa"},
             {"pen_repeticao": 1, "pen_profundidade": 20, "pen_profundidade_unidade": "cm", "pen_resistencia": 9.9,
              "pen_resistencia_unidade": "mpa"}]
    with pytest.raises(ErroGaema, match="repetição.*duplicada|duplicada"):
        traduzir_submissao(_sub(penetrometria=dupla), ignorar_nao_traduzidos=True)


# ================= exportação [8] ====================================================================================

@pytest.fixture
def demo_copia(tmp_path_factory):
    modelo = tmp_path_factory.getbasetemp() / "modelo_demo_f4f5"
    if not modelo.exists():
        modelo.mkdir(parents=True)
        demo.executar(modelo, verbose=False)
    copia = tmp_path_factory.mktemp("copia")
    shutil.copytree(modelo, copia / "d")
    repo = Repositorio(str(copia / "d" / "gaema-demo.db"))
    yield Nucleo(repo, copia / "d"), repo, copia / "d"
    repo.fechar()


def test_8_pacote_nao_leva_identificador_de_pessoa_nem_o_id_do_usuario(demo_copia):
    n, _, _ = demo_copia
    p = n.exportar_painel(demo.ATORES["coord"], gerado_em=QUANDO)
    assert "gerado_por" not in p and p["gerado_por_papeis"] == ["COORDENADOR"]
    assert demo.ATORES["coord"].id not in serializar(p).decode()


def test_8_texto_fora_do_padrao_no_diagnostico_nao_sai_no_pacote(demo_copia):
    n, repo, _ = demo_copia
    sujo = f"Fulano de Tal {CPF} {EMAIL} -10.495123 -48.495456"
    repo.con.execute("UPDATE registros SET dados = json_set(dados, '$.categoria_descritiva', ?, "
                     "'$.rotulo_validade', ?) WHERE tipo='Diagnostico'", (sujo, sujo))
    texto = serializar(n.exportar_painel(demo.ATORES["coord"], gerado_em=QUANDO)).decode()
    for proibido in ("Fulano", CPF, EMAIL, "-10.495123", "-48.495456"):
        assert proibido not in texto


def test_8_demanda_id_fora_do_formato_sai_opaco(demo_copia):
    n, repo, _ = demo_copia
    repo.con.execute("UPDATE registros SET dados = json_set(dados, '$.id', 'Fulano de Tal ' || id) "
                     "WHERE tipo='Demanda'")
    texto = serializar(montar_pacote(repo, gerado_por_papeis=["COORDENADOR"], gerado_em=QUANDO)).decode()
    assert "Fulano" not in texto and "id-opaco-" in texto


def test_8_codigo_de_categoria_com_texto_livre_e_recusado_na_publicacao():
    dados = ler_arquivo("gaema-prototipo-teste-0.1.0.json")
    antigo = next(iter(dados["categorias"]))
    dados["categorias"] = {f"Fulano de Tal {CPF}" if k == antigo else k: v for k, v in dados["categorias"].items()}
    dados["regras"] = [{**r, "categoria": f"Fulano de Tal {CPF}" if r["categoria"] == antigo else r["categoria"]}
                       for r in dados["regras"]]
    from gaema_sd.protocolo.definicao import carregar_definicao
    with pytest.raises(DefinicaoInvalida, match="código de categoria"):
        carregar_definicao(dados)


# ================= XLSForm [10] ======================================================================================

def test_10_xlsform_nao_obriga_resposta_de_presenca_nem_usa_hora_de_abertura_como_padrao():
    linhas = {l["name"]: l for l in X.survey()}
    for v in X.VARIAVEIS_PRESENCA:
        l = linhas[X.nome_presenca(v)]
        assert l["required"] != "yes" and "branco" in l["hint"].lower()
    assert linhas["capturado_em"]["default"] == ""
    assert all(l["default"] == "" for l in X.survey())


# ================= texto sensível [19] ===============================================================================

@pytest.mark.parametrize("formato", ["123 456 789 09", "123.456789-09", "123456789-09", "123.456.789/09",
                                     "123.456." + "789-09", "12345678909"])
def test_19_formatos_comuns_de_cpf_sao_mascarados(formato):
    assert "[REMOVIDO]" in sanear_texto(f"documento {formato} informado")


def test_19_chave_sensivel_nao_casa_por_pedaco_de_palavra():
    limpo = sanear_detalhes({"margem": 1, "energia": 2, "nome_pessoa": "x", "senha_atual": "y", "cpf": "z", "RG": "w"})
    assert limpo["margem"] == 1 and limpo["energia"] == 2
    assert limpo["nome_pessoa"] == limpo["senha_atual"] == limpo["cpf"] == limpo["RG"] == "[REMOVIDO]"


# ================= guia e gabarito [19] ==============================================================================

def test_19_gabarito_do_ponto_da_interrupcao_confere_com_a_trilha_da_demonstracao(tmp_path):
    (tmp_path / "d").mkdir()
    demo.executar(tmp_path / "d", verbose=False)
    repo = Repositorio(str(tmp_path / "d" / "gaema-demo.db"))
    try:
        codigo = {p.id: p.codigo for p in repo.listar(E.PontoAmostral)}
        eventos = list(Nucleo(repo, tmp_path / "d").trilha.eventos)
    finally:
        repo.fechar()
    interrupcao = next(i for i, e in enumerate(eventos) if e.estado_destino == "COLETA_PARCIAL")
    criados = [codigo[e.entidade_id] for e in eventos[:interrupcao] if e.entidade == "PontoAmostral" and e.acao == "CRIAR"]
    depois = [codigo[e.entidade_id] for e in eventos[interrupcao:] if e.entidade == "PontoAmostral" and e.acao == "CRIAR"]
    assert criados == ["P01", "P02"] and depois == ["P03"]
    guia = (RAIZ / "docs" / "guia-capacitacao.md").read_text(encoding="utf-8")
    assert "depois de coletar o P02 e antes do P03" in guia and "durante o ponto P02" not in guia


def test_19_guia_descreve_o_conflito_como_o_sistema_se_comporta():
    guia = (RAIZ / "docs" / "guia-capacitacao.md").read_text(encoding="utf-8")
    assert "só quando a demanda está em AGUARDANDO_SINCRONIZACAO" in guia
    assert "o coordenador precisa mover a demanda de volta" in guia
    assert "ainda não há comando nem rotina automática" in guia
    assert "mascara alguns formatos" in guia and "não reconhece nome" in guia


def test_19_quem_abre_a_averiguacao_e_quem_planeja_batem_com_a_maquina_de_estados():
    from gaema_sd.dominio.enums import Estado, Papel
    from gaema_sd.estados.maquina import TABELA
    abre = TABELA[(Estado.EM_TRIAGEM, Estado.DEMANDA_ABERTA)].papeis
    planeja = TABELA[(Estado.ATRIBUIDA, Estado.PLANEJADA)].papeis
    assert abre == {Papel.COORDENADOR, Papel.MEMBRO_MP} and planeja == {Papel.COORDENADOR, Papel.TECNICO_CAMPO}
    guia = (RAIZ / "docs" / "guia-capacitacao.md").read_text(encoding="utf-8")
    assert "decisão do membro ou do coordenador, com motivo" in guia
    assert "ATRIBUIDA / PLANEJADA" in guia and "técnico de campo também pode" in guia
