"""Rodada 3: telas do escritório (criar demanda, usuários de teste, equipe e vistoria, filtros, autoatribuição).

Dados sintéticos. Sem autenticação real (R-31): "aprovar" só libera um papel de teste na página de entrada.
"""

import dataclasses
import json
import re
from datetime import date, timedelta

import pytest

from gaema_sd.acesso.politica import Ator
from gaema_sd.config import CAMINHO_PADRAO, parametro
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, Papel, SituacaoPedidoAcesso
from gaema_sd.erros import AcessoNegado, ErroGaema, TransicaoInvalida, ValidacaoFalhou
from gaema_sd.estados import contexto as ctx_mod
from gaema_sd.interface.app import USUARIOS_DE_TESTE
from gaema_sd.nucleo import ATOR_PEDIDO_ACESSO

from .test_interface import Cliente, cliente, modelo, sistema  # noqa: F401  (fixtures)

A = USUARIOS_DE_TESTE
HOJE = date.today()


def dados_demanda(**mud):
    d = {"titulo": "Pastagem com solo exposto (sintético)", "objetivo": "averiguar o informado",
         "origem": "NOTICIA_EXTERNA", "descricao": "comunicação sintética de solo exposto",
         "data_alerta": HOJE.isoformat(), "municipio": "Município Sintético A", "lat_min": "-10,52", "lat_max": "-10,50",
         "lon_min": "-48,52", "lon_max": "-48,50", "criterio": "", "motivo_priorizacao": ""}
    d.update(mud)
    return d


def criar_pela_tela(c, **mud):
    r = c.post("/demanda/nova", dados_demanda(**mud))
    return r


def contagens(n):
    return {cls.__name__: len(n.repo.listar(cls)) for cls in (E.FonteDado, E.AreaCandidata, E.Alerta, E.AreaInteresse, E.Demanda)}


# ================= criar demanda ======================================================================================

def test_analista_cria_demanda_pela_tela_com_os_cinco_registros_auditados(sistema):
    app, n, _ = sistema
    antes = contagens(n)
    c = cliente(sistema, "analista")
    r = criar_pela_tela(c)
    assert r.status == 303 and r.cab["location"][0].startswith("/demanda/")
    depois = contagens(n)
    assert all(depois[k] == antes[k] + 1 for k in antes)
    did = r.cab["location"][0].rsplit("/", 1)[-1]
    d = n.repo.obter(E.Demanda, did)
    assert d.estado is Estado.CANDIDATA and d.municipio == "Município Sintético A" and d.criado_por == A["analista"].id
    cand = n.repo.obter(E.AreaCandidata, d.area_candidata_id)
    fonte = n.repo.obter(E.FonteDado, cand.fonte_ids[0])
    assert fonte.tipo.value == "REGISTRO_MANUAL" and "satélite" in cand.metodo_selecao
    criados = [e for e in n.trilha.eventos if e.acao == "CRIAR" and e.ator_id == A["analista"].id]
    assert {e.entidade for e in criados[-5:]} == {"FonteDado", "AreaCandidata", "Alerta", "AreaInteresse", "Demanda"}
    t = c.get(f"/demanda/{did}").texto
    assert "Demanda criada" in t and "Município Sintético A" in t
    n.transitar(A["analista"], did, Estado.ALERTA)               # geometria e fonte conferidas pelo núcleo
    assert n.repo.obter(E.Demanda, did).estado is Estado.ALERTA


@pytest.mark.parametrize("mud,trecho", [
    ({"data_alerta": (HOJE + timedelta(days=1)).isoformat()}, "não pode estar no futuro"),
    ({"lat_min": "-10,40"}, "o sul precisa ser menor que o norte"),
    ({"lon_max": "abc"}, "longitude leste precisa ser um número"),
    ({"lat_max": "95"}, "entre -90 e 90"),
    ({"titulo": ""}, "preencha: título"),
    ({"origem": "INVENTADA"}, "origem da informação"),
    ({"criterio": "ART17_I", "motivo_priorizacao": "curto"}, "Nada foi gravado"),
])
def test_dado_ruim_nao_cria_nada_e_mantem_o_que_foi_digitado(sistema, mud, trecho):
    app, n, _ = sistema
    antes = contagens(n)
    c = cliente(sistema, "analista")
    r = criar_pela_tela(c, **mud)
    assert r.status == 422 and trecho in r.texto and "A demanda não foi criada" in r.texto
    assert 'value="Município Sintético A"' in r.texto
    assert contagens(n) == antes


def test_coordenador_ve_o_botao_desabilitado_com_motivo_e_nao_cria(sistema):
    app, n, _ = sistema
    c = cliente(sistema, "coord")
    t = c.get("/painel").texto
    assert 'disabled aria-describedby="razao-nova"' in t and "quem cria demanda pela tela é o analista" in t
    antes = contagens(n)
    assert criar_pela_tela(c).status == 403 and contagens(n) == antes
    assert 'href="/demanda/nova"' in cliente(sistema, "analista").get("/painel").texto


def test_gravacao_em_lote_desfaz_tudo_se_um_falhar(sistema):
    app, n, _ = sistema
    antes = contagens(n)
    fonte = E.FonteDado(nome="f", tipo="REGISTRO_MANUAL", provedor="p", sintetico=True)
    from gaema_sd.dominio.enums import TipoFonte
    fonte = dataclasses.replace(fonte, tipo=TipoFonte.REGISTRO_MANUAL)
    ruim = E.Demanda(titulo="", sintetico=True)                       # título obrigatório: falha no fim
    with pytest.raises(ValidacaoFalhou):
        n.registrar_em_lote(A["analista"], [fonte, ruim])
    assert contagens(n) == antes
    assert n.trilha.eventos[-1].acao == "CRIACAO_RECUSADA"
    with pytest.raises(AcessoNegado):
        n.registrar_em_lote(A["coord"], [dataclasses.replace(fonte, id=E.novo_id()),
                                         E.AreaCandidata(geometria_wkt="POLYGON((0 0,1 0,1 1,0 0))", fonte_ids=["x"],
                                                         data_deteccao=HOJE)])
    assert contagens(n) == antes


# ================= usuários de teste ==================================================================================

def pedir(sistema, ident="usuario-sintetico-campo-2", papel="TECNICO_CAMPO", motivo="testar a coleta no celular"):
    c = Cliente(sistema[0])
    c.get("/entrar")
    c.post("/acesso/pedir", {"identificador": ident, "papel": papel, "motivo": motivo})
    return c


def test_pagina_de_entrada_diz_que_nao_ha_autenticacao_real(sistema):
    t = Cliente(sistema[0]).get("/entrar").texto
    assert "Sem autenticação real (R-31)" in t and "Pedir um usuário de teste" in t
    opcoes = re.findall(r'<option value="([A-Z_]+)"', t)
    assert "ADMINISTRADOR" not in opcoes and "SISTEMA" not in opcoes and "TECNICO_CAMPO" in opcoes


def test_pedido_aprovado_aparece_na_entrada_e_entra_com_o_papel(sistema):
    app, n, _ = sistema
    c = pedir(sistema)
    assert "Pedido registrado" in c.get("/entrar").texto
    p = n.repo.listar(E.PedidoAcesso)[-1]
    assert p.situacao is SituacaoPedidoAcesso.PENDENTE and p.criado_por == ATOR_PEDIDO_ACESSO.id
    assert "usuario-sintetico-campo-2" not in c.get("/entrar").texto.split("Pedir um usuário de teste")[0]
    adm = cliente(sistema, "admin")
    t = adm.get("/acessos").texto
    assert "Sem autenticação real (R-31)" in t and "Aprovar usuario-sintetico-campo-2" in t
    adm.post(f"/acessos/{p.id}/decidir", {"decisao": "aprovar", "motivo": "teste de coleta autorizado"})
    assert "Pedido aprovado" in adm.get("/acessos").texto
    novo = Cliente(app)
    assert "usuario-sintetico-campo-2" in novo.get("/entrar").texto
    novo.entrar("usuario-sintetico-campo-2")
    assert "Técnico de campo" in novo.get("/painel").texto
    ev = [e for e in n.trilha.eventos if e.entidade == "PedidoAcesso"]
    assert [e.acao for e in ev][-2:] == ["CRIAR", "ACESSO_TESTE_APROVADO"] and ev[-1].ator_id == A["admin"].id


def test_pedido_rejeitado_nao_entra_e_decisao_nao_volta(sistema):
    app, n, _ = sistema
    pedir(sistema, ident="usuario-sintetico-x1")
    p = n.repo.listar(E.PedidoAcesso)[-1]
    n.decidir_acesso_teste(A["admin"], p.id, False, "não há necessidade agora")
    assert "usuario-sintetico-x1" not in Cliente(app).get("/entrar").texto.split("Pedir um usuário de teste")[0]
    with pytest.raises(ErroGaema, match="já decidido"):
        n.decidir_acesso_teste(A["admin"], p.id, True, "mudei de ideia agora")
    assert n.trilha.eventos[-1].acao == "DECISAO_ACESSO_RECUSADA"
    r = Cliente(app)
    r.get("/entrar")
    assert r.post("/entrar", {"usuario": "usuario-sintetico-x1"}).status == 400


@pytest.mark.parametrize("ident,papel,motivo,trecho", [
    ("joao.silva", "TECNICO_CAMPO", "testar a coleta no celular", "identificador sintético"),
    ("usuario-sintetico-Maiusc", "TECNICO_CAMPO", "testar a coleta no celular", None),   # vira minúsculo: aceito
    ("usuario-sintetico-a", "ADMINISTRADOR", "quero ser administrador", "não podem ser pedidos"),
    ("usuario-sintetico-a", "SISTEMA", "quero ser sistema agora", "não podem ser pedidos"),
    ("usuario-sintetico-a", "TECNICO_CAMPO", "curto", "mínimo 10"),
    ("tecnico", "TECNICO_CAMPO", "testar a coleta no celular", "identificador"),
    ("tecnico-sintetico", "TECNICO_CAMPO", "testar a coleta no celular", "identificador"),
])
def test_pedido_invalido_e_recusado(sistema, ident, papel, motivo, trecho):
    app, n, _ = sistema
    c = pedir(sistema, ident, papel, motivo)
    t = c.get("/entrar").texto
    if trecho is None:
        assert n.repo.listar(E.PedidoAcesso)[-1].identificador == "usuario-sintetico-maiusc"
    else:
        assert n.repo.listar(E.PedidoAcesso) == [] and "Pedido registrado" not in t


def test_identificador_repetido_e_limite_de_pendentes(sistema, monkeypatch):
    app, n, _ = sistema
    n.pedir_acesso_teste(ATOR_PEDIDO_ACESSO, "usuario-sintetico-r", Papel.AUDITOR, "conferir a trilha de teste")
    with pytest.raises(ErroGaema, match="já usado"):
        n.pedir_acesso_teste(ATOR_PEDIDO_ACESSO, "usuario-sintetico-r", Papel.AUDITOR, "conferir a trilha de teste")
    from gaema_sd import nucleo as nuc
    monkeypatch.setattr(nuc, "parametro", lambda k: 1 if k == "interface_pedidos_acesso_pendentes_max" else parametro(k))
    with pytest.raises(ErroGaema, match="pedidos demais"):
        n.pedir_acesso_teste(ATOR_PEDIDO_ACESSO, "usuario-sintetico-s", Papel.AUDITOR, "conferir a trilha de teste")


def test_so_o_administrador_decide_e_ninguem_altera_por_fora(sistema):
    app, n, _ = sistema
    p = n.pedir_acesso_teste(ATOR_PEDIDO_ACESSO, "usuario-sintetico-q", Papel.REVISOR_TECNICO, "revisar um diagnóstico")
    for quem in ("coord", "membro", "auditor", "tecnico"):
        with pytest.raises(AcessoNegado):
            n.decidir_acesso_teste(A[quem], p.id, True, "aprovado por quem não pode")
        assert cliente(sistema, quem).get("/acessos").status == 403
    with pytest.raises(AcessoNegado):
        n.pedir_acesso_teste(A["admin"], "usuario-sintetico-z", Papel.AUDITOR, "admin não pede por aqui")
    aprovado = dataclasses.replace(p, situacao=SituacaoPedidoAcesso.APROVADO, decidido_por="x", motivo_decisao="x" * 10,
                                   decidido_em=p.criado_em)
    with pytest.raises(ErroGaema):
        n.atualizar(ATOR_PEDIDO_ACESSO, aprovado, p.versao)
    with pytest.raises(ValidacaoFalhou):
        n.registrar(ATOR_PEDIDO_ACESSO, dataclasses.replace(aprovado, id=E.novo_id(), identificador="usuario-sintetico-w"))
    with pytest.raises(ValidacaoFalhou):
        n.decidir_acesso_teste(A["admin"], p.id, True, "curto")
    assert n.repo.obter(E.PedidoAcesso, p.id).situacao is SituacaoPedidoAcesso.PENDENTE


def test_pedido_de_acesso_exige_token(sistema):
    c = Cliente(sistema[0])
    c.get("/entrar")
    r = c.pedir("POST", "/acesso/pedir", {"csrf": "0" * 32, "identificador": "usuario-sintetico-t", "papel": "AUDITOR",
                                         "motivo": "conferir a trilha de teste"})
    assert r.status == 403 and sistema[1].repo.listar(E.PedidoAcesso) == []


# ================= equipe, vistoria e autoatribuição =================================================================

def aberta_com_equipe(sistema, equipe_id=None):
    """Cria pela tela e leva a demanda até DEMANDA_ABERTA, com a equipe da demonstração (técnico e coordenador)."""
    app, n, _ = sistema
    r = criar_pela_tela(cliente(sistema, "analista"))
    did = r.cab["location"][0].rsplit("/", 1)[-1]
    n.transitar(A["analista"], did, Estado.ALERTA)
    n.transitar(A["analista"], did, Estado.EM_TRIAGEM)
    n.transitar(A["coord"], did, Estado.DEMANDA_ABERTA, motivo="abertura para teste da rodada 3")
    equipe = equipe_id or n.repo.listar(E.Equipe)[0].id
    c = cliente(sistema, "coord")
    c.post(f"/demanda/{did}/equipe", {"equipe": equipe})
    assert n.repo.obter(E.Demanda, did).equipe_id == equipe
    return did


def test_coordenador_define_equipe_e_tecnico_nao(sistema):
    app, n, _ = sistema
    did = aberta_com_equipe(sistema)
    t = cliente(sistema, "tecnico").get(f"/demanda/{did}").texto
    assert 'disabled aria-describedby="razao-equipe"' in t and "quem escolhe é o coordenador" in t
    with pytest.raises(AcessoNegado):
        n.definir_equipe(A["tecnico"], did, n.repo.listar(E.Equipe)[0].id)


def test_parametro_de_autoatribuicao_desligado_com_proveniencia():
    p = json.loads(CAMINHO_PADRAO.read_text(encoding="utf-8"))["autoatribuicao_tecnico"]
    assert p["valor"] is False and p["proveniencia"] == "AUTORAL" and "V-14" in p["observacao"]


def test_tecnico_nao_se_atribui_com_parametro_desligado(sistema):
    app, n, _ = sistema
    did = aberta_com_equipe(sistema)
    with pytest.raises(TransicaoInvalida, match="autoatribuição"):
        n.transitar(A["tecnico"], did, Estado.ATRIBUIDA)
    item = next(t for t in n.transicoes_possiveis(A["tecnico"], did) if t["destino"] == "ATRIBUIDA")
    assert not item["disponivel"]


def test_tecnico_da_equipe_se_atribui_com_parametro_ligado(sistema, monkeypatch):
    app, n, _ = sistema
    monkeypatch.setattr(ctx_mod, "parametro", lambda k: True if k == "autoatribuicao_tecnico" else parametro(k))
    did = aberta_com_equipe(sistema)
    n.transitar(A["tecnico"], did, Estado.ATRIBUIDA)
    assert n.repo.obter(E.Demanda, did).estado is Estado.ATRIBUIDA
    assert n.trilha.eventos[-1].ator_id == A["tecnico"].id and n.trilha.eventos[-1].estado_destino == "ATRIBUIDA"


def test_tecnico_fora_da_equipe_nao_se_atribui_mesmo_ligado(sistema, monkeypatch):
    app, n, _ = sistema
    monkeypatch.setattr(ctx_mod, "parametro", lambda k: True if k == "autoatribuicao_tecnico" else parametro(k))
    outra, _ = n.registrar(A["coord"], E.Equipe(nome="Equipe Sintética B", membros=[
        E.MembroEquipe(usuario_id="tecnico-sintetico-b", papel=Papel.TECNICO_CAMPO)], sintetico=True))
    did = aberta_com_equipe(sistema, outra.id)
    with pytest.raises((TransicaoInvalida, AcessoNegado)):
        n.transitar(A["tecnico"], did, Estado.ATRIBUIDA)
    n.transitar(A["coord"], did, Estado.ATRIBUIDA)                    # o coordenador continua podendo


def test_vistoria_agendada_pela_tela_libera_o_planejamento(sistema):
    app, n, _ = sistema
    from gaema_sd.protocolo.definicao import ler_arquivo
    n.publicar_protocolo(A["coord"], ler_arquivo("gaema-descritivo-0.1.0.json"))    # a interface publica (cenario.py)
    did = aberta_com_equipe(sistema)
    c = cliente(sistema, "coord")
    assert 'disabled aria-describedby="razao-vistoria"' in c.get(f"/demanda/{did}").texto      # ainda não atribuída
    n.transitar(A["coord"], did, Estado.ATRIBUIDA)
    t = c.get(f"/demanda/{did}").texto
    protocolo = re.search(r'<select id="protocolo" name="protocolo"[^>]*><option value="([^"]+)">[^<]*descritivo', t)
    assert protocolo, "o primeiro protocolo oferecido é o descritivo"
    amanha = (HOJE + timedelta(days=1)).isoformat()
    c.post(f"/demanda/{did}/vistoria", {"data_planejada": (HOJE - timedelta(days=1)).isoformat(),
                                         "objetivo": "vistoria sintética do recorte", "protocolo": protocolo.group(1)})
    assert "não pode estar no passado" in c.get(f"/demanda/{did}").texto
    c.post(f"/demanda/{did}/vistoria", {"data_planejada": amanha, "objetivo": "vistoria sintética do recorte",
                                         "protocolo": protocolo.group(1), "missao_baixada": "nao"})
    assert "Vistoria agendada" in c.get(f"/demanda/{did}").texto
    camp = [x for x in n.repo.listar(E.CampanhaVistoria) if x.demanda_id == did]
    assert len(camp) == 1 and camp[0].pacote_offline == "" and camp[0].equipe_id == n.repo.obter(E.Demanda, did).equipe_id
    n.transitar(A["coord"], did, Estado.PLANEJADA)
    with pytest.raises(TransicaoInvalida, match="missão"):                # missão não baixada: declarado na tela
        n.transitar(A["tecnico"], did, Estado.EM_CAMPO)


def test_tecnico_so_agenda_vistoria_da_propria_equipe(sistema):
    app, n, _ = sistema
    outra, _ = n.registrar(A["coord"], E.Equipe(nome="Equipe Sintética C", membros=[
        E.MembroEquipe(usuario_id="tecnico-sintetico-c", papel=Papel.TECNICO_CAMPO)], sintetico=True))
    did = aberta_com_equipe(sistema, outra.id)
    n.transitar(A["coord"], did, Estado.ATRIBUIDA)
    prot = n.repo.listar(E.VersaoProtocolo)[0].id
    camp = E.CampanhaVistoria(demanda_id=did, equipe_id=outra.id, versao_protocolo_id=prot, objetivo="vistoria sintética",
                              data_planejada=HOJE, sintetico=True)
    with pytest.raises(AcessoNegado, match="própria equipe"):
        n.registrar(A["tecnico"], camp)
    assert n.trilha.eventos[-1].acao == "ACESSO_NEGADO"


# ================= filtros do painel =================================================================================

def test_filtros_por_situacao_equipe_municipio_e_data(sistema):
    app, n, _ = sistema
    criar_pela_tela(cliente(sistema, "analista"), municipio="Município Sintético B", titulo="Demanda B (sintética)")
    c = cliente(sistema, "coord")
    total = len(n.repo.listar(E.Demanda))

    def titulos(qs):
        t = c.pedir("GET", "/painel", cabecalhos={"QUERY_STRING": qs}).texto
        return t, re.findall(r'<h3><a href="/demanda/[^"]+">([^<]+)</a>', t)
    t, ts = titulos("")
    assert f"Mostrando {total} de {total}" in t
    t, ts = titulos("municipio=sint%C3%A9tico+b")
    assert ts == ["Demanda B (sintética)"] and "Limpar filtros" in t
    t, ts = titulos("situacao=CANDIDATA")
    assert "Demanda B (sintética)" in ts and all(n.repo.listar(E.Demanda))
    t, ts = titulos("equipe=sem")
    assert "Demanda B (sintética)" in ts
    t, ts = titulos(f"de={(HOJE + timedelta(days=1)).isoformat()}")
    assert ts == [] and "Nenhuma demanda com estes filtros" in t
    t, ts = titulos(f"ate={(HOJE - timedelta(days=3650)).isoformat()}")
    assert ts == []
    t, ts = titulos("situacao=INVENTADA&de=31-02-2026")
    assert "Filtro ignorado" in t and f"Mostrando {total} de {total}" in t


def test_filtro_nao_amplia_o_que_o_tecnico_ve(sistema):
    app, n, _ = sistema
    criar_pela_tela(cliente(sistema, "analista"), titulo="Fora da equipe (sintética)")
    c = cliente(sistema, "tecnico")
    for qs in ("", "situacao=CANDIDATA", "equipe=sem", "municipio=Sint"):
        assert "Fora da equipe (sintética)" not in c.pedir("GET", "/painel", cabecalhos={"QUERY_STRING": qs}).texto


def test_campos_de_data_tem_o_mesmo_tamanho_dos_outros(sistema):
    css = cliente(sistema, "coord").get("/painel").texto
    assert re.search(r"input\[type=datetime-local\], input\[type=date\], select, textarea \{", css)
