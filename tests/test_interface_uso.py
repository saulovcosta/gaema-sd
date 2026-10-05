"""Usabilidade da interface: linguagem comum, próxima ação, permissões visíveis, mensagens, temas, mapa e Campo.

Só apresentação: as regras continuam no núcleo. Dados sintéticos; aparelho e rede simulados.
"""

import re
from html.parser import HTMLParser

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, Papel
from gaema_sd.interface import Aplicacao
from gaema_sd.interface import linguagem as L
from gaema_sd.interface.campo import Campo

from .apoio_sincronizacao import Ambiente
from .test_interface import HOST, Cliente, _demanda_id, cliente, sistema, modelo  # noqa: F401  (fixtures)


class SoTexto(HTMLParser):
    """Texto visível (sem atributos, sem <title>/<style>): o que a pessoa lê."""
    def __init__(self):
        super().__init__(); self.partes, self._pula = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "title", "script"):
            self._pula += 1

    def handle_endtag(self, tag):
        if tag in ("style", "title", "script"):
            self._pula -= 1

    def handle_data(self, d):
        if not self._pula:
            self.partes.append(d)


def visivel(html):
    p = SoTexto(); p.feed(html)
    return " ".join(p.partes)


# ================= linguagem comum ==================================================================================

def test_todas_as_situacoes_tem_nome_comum_acao_no_imperativo_e_tom():
    assert set(L.SITUACAO) == set(Estado)
    for e, s in L.SITUACAO.items():
        assert s.nome and s.acao.endswith(".") and s.tom in L.TOM
        assert "_" not in s.nome and e.value not in s.nome
    assert L.situacao(Estado.CONFLITO_SINCRONIZACAO).nome == "Conflito: aguardando decisão do coordenador"


def test_quem_age_vem_da_tabela_real_de_transicoes():
    from gaema_sd.estados.maquina import TABELA
    assert L.quem_age("AGUARDANDO_REVISAO") == L.papeis(
        {p for (o, d), t in TABELA.items() if o is Estado.AGUARDANDO_REVISAO and d is not Estado.CANCELADA_JUSTIFICADA
         for p in t.papeis})
    assert L.quem_age("ENCERRADA") == "Membro do Ministério Público"


def test_mensagens_tecnicas_viram_o_que_houve_e_como_resolver():
    m = L.explicar("motivo obrigatório (mínimo 10 caracteres)")
    assert "curto" in m.o_que_houve and "10 letras" in m.como_resolver
    m = L.explicar("EM_MONITORAMENTO → ENCERRADA só pode ser feita por: MEMBRO_MP")
    assert "papel" in m.o_que_house if False else "papel" in m.o_que_houve
    assert "Membro do Ministério Público" in m.detalhe and "MEMBRO_MP" not in m.detalhe and "EM_MONITORAMENTO" not in m.detalhe
    assert L.explicar("algo inesperado").como_resolver


@pytest.mark.parametrize("usuario", ["coord", "membro", "tecnico", "revisor"])
def test_paginas_nao_mostram_nome_tecnico_de_situacao_nem_de_papel(sistema, usuario):
    c = cliente(sistema, usuario)
    did = _demanda_id(sistema[1])
    for caminho in ("/painel", f"/demanda/{did}"):
        texto = visivel(c.get(caminho).texto)
        for e in Estado:
            assert not re.search(rf"\b{e.value}\b", texto), (usuario, caminho, e.value)
        for p in Papel:
            assert not re.search(rf"\b{p.value}\b", texto), (usuario, caminho, p.value)


def test_toda_pagina_diz_o_que_fazer_agora(sistema):
    c = cliente(sistema, "coord")
    did = _demanda_id(sistema[1])
    for caminho in ("/painel", f"/demanda/{did}", "/conflitos", "/exportar", "/campo"):
        t = visivel(c.get(caminho).texto)
        assert "O que fazer agora" in t or "Próxima ação" in t, caminho
    assert "Próxima ação" in visivel(c.get(f"/demanda/{did}").texto) and "Quem age agora" in visivel(c.get(f"/demanda/{did}").texto)


def test_faixa_de_prototipo_e_aviso_de_fronteira_juridica_em_toda_pagina(sistema):
    c = cliente(sistema, "coord")
    for caminho in ("/painel", "/ajuda", "/exportar", "/campo"):
        t = c.get(caminho).texto
        assert "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" in t
        assert "Não conclui autoria, ilicitude, dano jurídico, responsabilidade nem nexo causal" in t
    assert "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" in Cliente(sistema[0]).get("/entrar").texto


def test_linguagem_vedada_ausente_das_telas(sistema):
    c = cliente(sistema, "coord")
    for caminho in ("/painel", "/ajuda", "/exportar", "/campo", f"/demanda/{_demanda_id(sistema[1])}"):
        t = visivel(c.get(caminho).texto).lower()
        assert not re.search(r"homologad[oa]|\bperfeit[oa]|em produção|pronto para produção", t), caminho
        for linha in t.split("."):
            if "integrad" in linha and "mpto" in linha:
                assert re.search(r"\bnão\b|\bsem\b|\bnenhum", linha), linha


# ================= permissões visíveis ===============================================================================

def test_menu_mostra_tudo_e_marca_o_que_o_papel_nao_acessa(sistema):
    t = cliente(sistema, "tecnico").get("/painel").texto
    for item in ("Início", "Campo", "Conflitos", "Auditoria", "Exportar", "Backup", "Acessos de teste", "Ajuda e limites"):
        assert item in t
    assert t.count('class="bloqueada"') == 5 and "indisponível: seu papel (Técnico de campo)" in t


def test_botoes_sem_permissao_aparecem_desativados_com_a_razao(sistema):
    c = cliente(sistema, "tecnico")
    t = c.get(f"/demanda/{_demanda_id(sistema[1])}").texto
    assert re.search(r'<button type="button" disabled aria-describedby="razao-emitir">', t)
    assert 'id="razao-emitir"' in t and "Por que não: seu papel (Técnico de campo) não emite relatório" in t
    assert re.search(r'disabled aria-describedby="razao-exportar"', c.get("/exportar").texto)


def test_painel_mostra_o_que_o_papel_pode_e_nao_pode(sistema):
    t = visivel(cliente(sistema, "auditor").get("/painel").texto)
    assert "Pode" in t and "conferir a trilha de auditoria" in t and "Não pode" in t and "emitir relatórios" in t


def test_erro_mostra_o_que_houve_como_resolver_e_e_anunciado(sistema):
    c = cliente(sistema, "membro")
    did = _demanda_id(sistema[1])
    c.post(f"/demanda/{did}/transitar", {"destino": "ENCERRADA", "motivo": "curto"})
    t = c.get(f"/demanda/{did}").texto
    assert 'role="alert"' in t and "O que houve:" in t and "Como resolver:" in t and "10 letras" in t
    assert 'aria-live="polite"' in t


def test_pagina_de_erro_tambem_explica(sistema):
    r = cliente(sistema, "membro").get("/demanda/00000000-0000-4000-8000-00000000dead")
    assert r.status == 404 and "O que houve:" in r.texto and "Como resolver:" in r.texto


# ================= tema, toque, movimento ============================================================================

def test_tema_claro_escuro_e_do_sistema(sistema):
    c = cliente(sistema, "coord")
    assert "data-tema" not in c.get("/painel").texto.split("<head>")[0]
    c.post("/tema", {"tema": "escuro"})
    assert '<html lang="pt-BR" data-tema="escuro">' in c.get("/painel").texto
    c.post("/tema", {"tema": "<script>"})
    assert '<html lang="pt-BR" data-tema="escuro">' in c.get("/painel").texto       # valor inválido é ignorado
    anon = Cliente(sistema[0]); anon.get("/entrar"); anon.post("/tema", {"tema": "claro"})
    assert 'data-tema="claro"' in anon.get("/entrar").texto


def test_css_garante_alvo_de_toque_movimento_reduzido_e_sem_largura_fixa(sistema):
    t = cliente(sistema, "coord").get("/painel").texto
    css = re.search(r"<style>(.*?)</style>", t, re.S).group(1)
    for seletor in (r"button, \.botao \{[^}]*min-height:44px", r"input\[type=text\][^{]*\{[^}]*min-height:44px",
                    r"nav\.abas a, nav\.abas span \{[^}]*min-height:44px"):
        assert re.search(seletor, css), seletor
    assert "prefers-reduced-motion" in css and "prefers-color-scheme: dark" in css
    assert not re.search(r"width:\s*\d{3,}px", css)          # nada de largura fixa grande que force rolagem em 360 px


# ================= mapa ============================================================================================

def test_mapa_tem_legenda_escala_aviso_e_destaca_o_ponto_na_lista_e_no_mapa(sistema):
    c = cliente(sistema, "coord")
    did = _demanda_id(sistema[1])
    t = c.get(f"/demanda/{did}").texto
    assert '<svg class="mapa"' in t and "Ponto amostral (círculo)" in t and "Ponto selecionado (losango)" in t
    assert "(aprox.)" in t and "Esquema sem base cartográfica" in t and 'id="mapa-desc"' in t
    assert t.count('href="?ponto=P0') >= 6                    # links no mapa e na lista
    t2 = c.get(f"/demanda/{did}", ).texto
    sel = c.pedir("GET", f"/demanda/{did}", host=HOST, cabecalhos={"QUERY_STRING": "ponto=P02"}).texto
    assert 'class="ponto-sel"' in sel and '<tr id="ponto-P02" class="selecionado">' in sel and "(selecionado)" in sel
    assert 'class="ponto-sel"' not in t2
    xss = c.pedir("GET", f"/demanda/{did}", host=HOST, cabecalhos={"QUERY_STRING": "ponto=%3Cscript%3E"}).texto
    assert "<script>" not in xss and 'class="ponto-sel"' not in xss


def test_escala_aproximada_bate_com_a_distancia_entre_dois_pontos():
    from gaema_sd.interface.mapa import mapa_svg
    pts = [{"codigo": "A", "latitude": -10.0, "longitude": -48.0}, {"codigo": "B", "latitude": -10.0, "longitude": -47.99}]
    svg, info = mapa_svg("", pts, None, "teste")
    # 0,01° de longitude a 10°S ≈ 1,096 km; a barra deve ser um valor "redondo" menor que isso
    assert info["metros"] in (100, 200, 500) and "(aprox.)" in svg


# ================= Campo: aparelho simulado ==========================================================================

@pytest.fixture
def com_campo(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario)                 # central com demanda EM_CAMPO e técnico na equipe
    campo = Campo.criar(tmp_path / "aparelho-ui", amb.central, atores["tecnico"])
    app = Aplicacao(amb.central, hosts_permitidos={HOST}, campo=campo,
                    usuarios={"tecnico": atores["tecnico"], "coord": atores["coord"]})
    yield amb, app, campo
    campo.fechar()


def _etapa1(c, amb, **mud):
    dados = {"missao": amb.c["CampanhaVistoria"][0].id, "codigo": "P09", "latitude": "-10,4951", "longitude": "-48,4952",
             "precisao": "4", "capturado_em": "2026-10-03T09:30"}
    dados.update(mud)
    return c.post("/campo/coleta/ponto", dados)


def test_barra_de_campo_permanente_para_o_tecnico(com_campo):
    amb, app, campo = com_campo
    t = Cliente(app).entrar("tecnico").get("/painel").texto
    assert "Rede (simulada):" in t and "Na fila do aparelho:" in t and "Última sincronização:" in t
    assert "Rede (simulada):" not in Cliente(app).entrar("coord").get("/painel").texto


def test_coleta_completa_em_etapas_salva_no_aparelho_e_sincroniza(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    assert "Etapa 1 de 5" in c.get("/campo/coleta").texto and 'aria-current="step"' in c.get("/campo/coleta").texto
    _etapa1(c, amb, latitude="abc")
    t = c.get("/campo/coleta").texto
    assert "Alguns campos da etapa 1 precisam de ajuste" in t and "latitude precisa ser um número" in t
    assert 'value="abc"' in t                                    # nada se perde: o que foi digitado fica
    _etapa1(c, amb)
    assert "Etapa 2 de 5" in c.get("/campo/coleta").texto
    c.post("/campo/coleta/visto", {"PLANTAS_INVASORAS": "sim", "SULCOS": "nao", "hipotese": "pisoteio (sintético)"})
    assert "Etapa 3 de 5" in c.get("/campo/coleta").texto
    c.post("/campo/coleta/ambiente", {})                         # ambiente é opcional: em branco não gera registro
    assert "Etapa 4 de 5" in c.get("/campo/coleta").texto
    c.post("/campo/coleta/medicao", {"profundidade": "dez", "unidade_p": "cm", "resistencia": "1,5", "unidade_r": "mpa"})
    assert "A repetição não foi anotada" in c.get("/campo/coleta").texto
    for prof, res in (("20", "1,5"), ("20", "1,7"), ("20", "9")):
        c.post("/campo/coleta/medicao", {"profundidade": prof, "unidade_p": "cm", "resistencia": res, "unidade_r": "mpa"})
    c.post("/campo/coleta/desfazer")
    t = c.get("/campo/coleta").texto
    assert "Última repetição desfeita" in t and "Anotar repetição 3" in t and "MPa" in t      # unidade sempre visível
    c.post("/campo/coleta/conferir")
    conf = c.get("/campo/coleta").texto
    assert "Conferir antes de salvar" in conf and "Sim, presente" in conf and "Não observado" in conf and "1,7" in conf
    c.post("/campo/coleta/salvar")
    t = c.get("/campo").texto
    assert "Ponto P09 salvo no aparelho: 3 observação(ões), 2 medição(ões) e 0 foto(s)" in t and campo.rascunho() is None
    assert campo.status()["pendentes"] == 6
    c.post("/campo/sincronizar")
    t = c.get("/campo").texto
    assert "Sincronização concluída: 6 enviado(s), 0 conflito(s), 0 recusado(s)" in t
    assert any(p.codigo == "P09" for p in amb.na_central(E.PontoAmostral))
    obs = [o for o in amb.na_central(E.Observacao)]
    assert {o.valor_bruto for o in obs} >= {"sim", "não"} and len(amb.na_central(E.MedicaoPenetracao)) == 2


def test_sem_rede_nada_se_perde_e_a_barra_mostra(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    c.post("/campo/rede")
    _etapa1(c, amb); c.post("/campo/coleta/visto", {}); c.post("/campo/coleta/ambiente", {}); c.post("/campo/coleta/conferir")
    c.post("/campo/coleta/salvar")
    c.post("/campo/sincronizar")
    t = c.get("/campo").texto
    assert "sem rede" in t and "nada se perdeu" in t and "Rede (simulada):</strong> sem rede" in t
    assert campo.status()["pendentes"] == 1 and amb.na_central(E.PontoAmostral) == []
    assert "Aparelho sem rede (simulação)" in c.get("/painel").texto
    c.post("/campo/rede"); c.post("/campo/sincronizar")
    assert campo.status()["pendentes"] == 0 and len(amb.na_central(E.PontoAmostral)) == 1


def test_rascunho_sobrevive_ao_reinicio_do_aparelho(com_campo, tmp_path):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    _etapa1(c, amb)
    outro = Campo.criar(campo.pasta, amb.central, amb.a["tecnico"])     # "fechou e abriu" o aparelho
    try:
        r = outro.rascunho()
        assert r["codigo"] == "P09" and r["etapa"] == 2
    finally:
        outro.fechar()


def test_nao_pula_etapa_nem_salva_antes_da_conferencia(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    assert "Etapa 1 de 5" in c.pedir("GET", "/campo/coleta", cabecalhos={"QUERY_STRING": "etapa=5"}).texto
    _etapa1(c, amb)
    c.post("/campo/coleta/conferir")
    assert "complete as etapas anteriores" in c.get("/campo/coleta").texto.lower() or "Etapa 2 de 5" in c.get("/campo/coleta").texto
    c.post("/campo/coleta/salvar")
    assert "ainda não passou por todas as etapas" in c.get("/campo/coleta").texto
    assert campo.status()["pendentes"] == 0


def test_quem_nao_e_tecnico_ve_o_campo_mas_nao_coleta(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("coord")
    t = c.get("/campo").texto
    assert 'disabled aria-describedby="razao-coletar"' in t and "só o técnico de campo coleta" in t
    r = c.get("/campo/coleta")
    assert r.status == 303
    c.post("/campo/sincronizar")
    assert "O que houve:" in c.get("/campo").texto and campo.status()["pendentes"] == 0


def test_descartar_rascunho(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    _etapa1(c, amb)
    c.post("/campo/coleta/descartar")
    assert campo.rascunho() is None and "Rascunho descartado" in c.get("/campo").texto


def test_campo_desligado_explica_como_ligar(sistema):
    t = cliente(sistema, "tecnico").get("/campo").texto
    assert "O Campo não está ligado nesta execução" in t and "scripts/interface.sh" in t


def test_entrada_em_um_toque_faixa_curta_e_papel_em_teste(sistema):
    from gaema_sd.interface import USUARIOS_DE_TESTE
    t = Cliente(sistema[0]).get("/entrar").texto
    assert t.count('<button type="submit">Entrar como ') == len(USUARIOS_DE_TESTE)
    assert t.count('name="usuario"') == len(USUARIOS_DE_TESTE) and 'type="radio"' not in t
    assert "autenticação real" in t and "Linha de Atuação em Solos Degradados" in t
    assert ("PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA</strong> · DADOS SINTÉTICOS · "
            "SEM INTEGRAÇÃO COM ARCGIS, RADAR, PAINEL OU SISTEMAS DO MPTO") in t
    painel = cliente(sistema, "coord").get("/painel").texto
    assert "Papel em teste: Coordenador" in painel and "sem autenticação real" in painel
    assert "autenticação real" in cliente(sistema, "coord").get("/ajuda").texto
