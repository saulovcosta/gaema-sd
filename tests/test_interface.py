"""Interface local de operação: segurança, permissões, fluxos e acessibilidade. Só dados sintéticos; sem navegador real
(o servidor real em 127.0.0.1 tem um teste de fumaça)."""

import hashlib
import io
import json
import re
import shutil
import threading
import urllib.request
from urllib.parse import quote
from html.parser import HTMLParser
from pathlib import Path

import jsonschema
import pytest

from gaema_sd import demo
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, FormatoRelatorio
from gaema_sd.exportacao import esquema_json
from gaema_sd.interface import USUARIOS_DE_TESTE, Aplicacao, servir
from gaema_sd.interface import app as modulo_app
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio

from .apoio_sincronizacao import Ambiente, com
from .test_acessibilidade import razao_contraste

HOST = "127.0.0.1:8765"


class Cliente:
    """Navegador mínimo: guarda o cookie, lê o token CSRF das páginas e chama a aplicação WSGI direto."""

    def __init__(self, app, host=HOST):
        self.app, self.host, self.cookie, self.csrf = app, host, "", ""

    def pedir(self, metodo, caminho, dados=None, *, host="__padrao__", cabecalhos=None, corpo=None, tipo="application/x-www-form-urlencoded"):
        if corpo is None:
            corpo = "&".join(f"{k}={quote(str(v))}" for k, v in (dados or {}).items()).encode()
        env = {"REQUEST_METHOD": metodo, "PATH_INFO": caminho, "HTTP_HOST": self.host if host == "__padrao__" else host, "wsgi.input": io.BytesIO(corpo),
               "CONTENT_LENGTH": str(len(corpo)), "CONTENT_TYPE": tipo, "HTTP_COOKIE": self.cookie}
        env.update(cabecalhos or {})
        saida = {}

        def sr(status, h):
            saida["status"], saida["h"] = int(status.split()[0]), h
        corpo_resp = b"".join(self.app(env, sr))
        cab = {}
        for k, v in saida["h"]:
            cab.setdefault(k.lower(), []).append(v)
        if "set-cookie" in cab:
            self.cookie = cab["set-cookie"][-1].split(";")[0]
        r = type("R", (), {})()
        r.status, r.cab, r.bytes = saida["status"], cab, corpo_resp
        r.texto = corpo_resp.decode("utf-8", errors="replace")
        m = re.search(r'name="csrf" value="([0-9a-f]+)"', r.texto)
        if m:
            self.csrf = m.group(1)
        return r

    def get(self, caminho, **k):
        return self.pedir("GET", caminho, **k)

    def post(self, caminho, dados=None, **k):
        return self.pedir("POST", caminho, {"csrf": self.csrf, **(dados or {})}, **k)

    def entrar(self, usuario):
        self.get("/entrar")
        r = self.post("/entrar", {"usuario": usuario})
        assert r.status == 303, r.texto
        self.get("/painel")
        return self


@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("interface") / "modelo"
    pasta.mkdir()
    demo.executar(pasta, verbose=False)
    return pasta


@pytest.fixture
def sistema(modelo, tmp_path):
    destino = tmp_path / "d"
    shutil.copytree(modelo, destino)
    repo = Repositorio(str(destino / "gaema-demo.db"))
    nucleo = Nucleo(repo, destino)
    yield Aplicacao(nucleo, hosts_permitidos={HOST}), nucleo, destino
    repo.fechar()


def cliente(sistema, usuario):
    return Cliente(sistema[0]).entrar(usuario)


def _demanda_id(nucleo):
    return nucleo.repo.listar(E.Demanda)[0].id


# ================= segurança =============================================================================================

def test_host_diferente_e_recusado_contra_dns_rebinding(sistema):
    c = Cliente(sistema[0])
    for host in ("evil.example.com", "127.0.0.1:9999", "127.0.0.1", ""):
        assert c.get("/entrar", host=host).status == 400


def test_so_atende_a_central_e_so_com_usuarios_sinteticos(tmp_path):
    with pytest.raises(Exception, match="central"):
        Aplicacao(Nucleo(Repositorio(":memory:"), tmp_path, modo="livre"), hosts_permitidos={HOST})
    assert all(a.id.endswith("-sintetico") for a in USUARIOS_DE_TESTE.values())


def test_cabecalhos_de_seguranca_e_cookie_restrito(sistema):
    c = Cliente(sistema[0])
    r = c.get("/entrar")
    csp = r.cab["content-security-policy"][0]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp and "form-action 'self'" in csp
    assert r.cab["x-content-type-options"] == ["nosniff"] and r.cab["x-frame-options"] == ["DENY"]
    assert r.cab["cache-control"] == ["no-store"] and r.cab["referrer-policy"] == ["no-referrer"]
    cookie = r.cab["set-cookie"][0]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/" in cookie


def test_sem_sessao_redireciona_para_entrar(sistema):
    c = Cliente(sistema[0])
    for caminho in ("/painel", "/conflitos", "/auditoria", "/exportar", "/backup", "/ajuda"):
        r = c.get(caminho)
        assert r.status == 303 and r.cab["location"] == ["/entrar"], caminho
    assert c.post("/sair").status == 303


def test_post_sem_token_ou_com_token_errado_e_recusado(sistema):
    c = cliente(sistema, "membro")
    did = _demanda_id(sistema[1])
    destino = [t for t in sistema[1].transicoes_possiveis(USUARIOS_DE_TESTE["membro"], did) if t["disponivel"]][0]["destino"]
    for dados in ({"destino": destino}, {"csrf": "0" * 32, "destino": destino}):
        r = c.pedir("POST", f"/demanda/{did}/transitar", dados)
        assert r.status == 403
    assert sistema[1].repo.obter(E.Demanda, did).estado is Estado.EM_MONITORAMENTO


def test_origem_diferente_e_recusada_mesmo_com_token_certo(sistema):
    c = cliente(sistema, "membro")
    r = c.post("/sair", cabecalhos={"HTTP_ORIGIN": "http://evil.example.com"})
    assert r.status == 403
    assert c.get("/painel").status == 200          # a sessão continua valendo
    assert c.post("/sair", cabecalhos={"HTTP_ORIGIN": f"http://{HOST}"}).status == 303


def test_sessao_e_trocada_no_login_e_encerrada_no_logout(sistema):
    c = Cliente(sistema[0])
    c.get("/entrar")
    anonima = c.cookie
    c.post("/entrar", {"usuario": "membro"})
    assert c.cookie != anonima and c.cookie.startswith("sid=")
    velho = Cliente(sistema[0]); velho.cookie = anonima
    assert velho.get("/painel").status == 303                       # sessão anônima não vira autenticada
    c.get("/painel")
    assert c.post("/sair").status == 303
    c.cookie = c.cookie
    assert c.get("/painel").status == 303


def test_login_com_usuario_inexistente_ou_sem_sessao_e_recusado(sistema):
    c = Cliente(sistema[0])
    c.get("/entrar")
    assert c.post("/entrar", {"usuario": "root"}).status == 400
    assert Cliente(sistema[0]).pedir("POST", "/entrar", {"usuario": "membro", "csrf": "x"}).status == 403


def test_limites_de_corpo_tipo_metodo_e_caminho(sistema):
    c = cliente(sistema, "membro")
    assert c.pedir("POST", "/sair", corpo=b"x" * 70000, cabecalhos={"HTTP_ORIGIN": f"http://{HOST}"}).status == 413
    assert c.pedir("POST", "/sair", corpo=b"{}", tipo="application/json").status == 400
    assert c.pedir("DELETE", "/painel").status == 405
    assert c.get("/nao-existe").status == 404
    assert c.get("/relatorio/../../etc/passwd").status == 404
    assert c.get("/demanda/nao-e-uuid").status == 404


def test_texto_de_usuario_e_escapado_nas_paginas(sistema):
    app, nucleo, _ = sistema
    nucleo.repo.con.execute("UPDATE registros SET dados = json_set(dados, '$.titulo', ?, '$.motivo_priorizacao', ?) "
                            "WHERE tipo='Demanda'", ("<script>alert(1)</script>", "<img src=x onerror=alert(2)>"))
    c = cliente(sistema, "membro")
    for caminho in ("/painel", f"/demanda/{_demanda_id(nucleo)}"):
        t = c.get(caminho).texto
        assert "<script>alert" not in t and "<img src=x" not in t and "&lt;script&gt;" in t


def test_erro_interno_nao_vaza_detalhe(sistema, monkeypatch):
    c = cliente(sistema, "membro")
    monkeypatch.setattr(sistema[1], "listar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("segredo-interno /tmp/x")))
    r = c.get("/painel")
    assert r.status == 500 and "segredo-interno" not in r.texto and "Traceback" not in r.texto and "/tmp" not in r.texto


def test_sessoes_tem_limite(sistema):
    app = sistema[0]
    for _ in range(modulo_app.MAX_SESSOES + 20):
        Cliente(app).get("/entrar")
    assert len(app.sessoes) <= modulo_app.MAX_SESSOES


def test_aviso_aparece_uma_vez_so(sistema):
    c = cliente(sistema, "membro")
    did = _demanda_id(sistema[1])
    c.post(f"/demanda/{did}/transitar", {"destino": "ENCERRADA", "motivo": "curto"})
    assert 'role="alert"' in c.get(f"/demanda/{did}").texto
    assert 'role="alert"' not in c.get(f"/demanda/{did}").texto


# ================= permissões por papel ============================================================================

def test_cada_papel_so_ve_e_faz_o_que_pode(sistema):
    tec = cliente(sistema, "tecnico")
    assert tec.get("/conflitos").status == 403 and tec.get("/auditoria").status == 403 and tec.get("/backup").status == 403
    painel_tec = tec.get("/painel").texto
    assert "Exportar" in painel_tec and 'class="bloqueada"' in painel_tec        # aparece, desativado, com razão
    aud = cliente(sistema, "auditor")
    assert aud.get("/auditoria").status == 200 and aud.get("/conflitos").status == 403
    adm = cliente(sistema, "admin")
    assert adm.get("/backup").status == 200 and "Seu papel não vê demandas" in adm.get("/painel").texto
    ana = cliente(sistema, "analista")
    r = ana.post("/exportar")
    assert r.status == 303
    assert "Sem permissão" in ana.get("/exportar").texto


def test_painel_lista_a_demanda_com_situacao_e_prioridade(sistema):
    t = cliente(sistema, "membro").get("/painel").texto
    assert "Em acompanhamento" in t and "Art. 17, II" in t and _demanda_id(sistema[1]) in t


# ================= fluxos =====================================================================================

def test_transicao_pela_tela_muda_o_estado_e_fica_no_historico(sistema):
    app, nucleo, _ = sistema
    c = cliente(sistema, "membro")
    did = _demanda_id(nucleo)
    pagina = c.get(f"/demanda/{did}").texto
    disponiveis = [t for t in nucleo.transicoes_possiveis(USUARIOS_DE_TESTE["membro"], did) if t["disponivel"]]
    from gaema_sd.interface import linguagem as L
    assert disponiveis and f"Mover para: {L.situacao(disponiveis[0]['destino']).nome}" in pagina
    alvo = disponiveis[0]
    r = c.post(f"/demanda/{did}/transitar", {"destino": alvo["destino"], "motivo": "Decisão registrada pela tela de operação."})
    assert r.status == 303
    depois = c.get(f"/demanda/{did}").texto
    assert nucleo.repo.obter(E.Demanda, did).estado.value == alvo["destino"]
    assert f"Demanda movida para: {L.situacao(alvo['destino']).nome}" in depois and "Mudança de situação" in depois


def test_transicao_recusada_mostra_motivo_e_nao_muda_nada(sistema):
    app, nucleo, _ = sistema
    c = cliente(sistema, "membro")
    did = _demanda_id(nucleo)
    c.post(f"/demanda/{did}/transitar", {"destino": "ENCERRADA", "motivo": "curto"})
    assert "motivo obrigatório" in c.get(f"/demanda/{did}").texto
    c.post(f"/demanda/{did}/transitar", {"destino": "CANDIDATA", "motivo": "Tentativa de voltar sem caminho."})
    assert "não é possível ir" in c.get(f"/demanda/{did}").texto
    assert c.post(f"/demanda/{did}/transitar", {"destino": "INVENTADO"}).status == 400
    assert nucleo.repo.obter(E.Demanda, did).estado is Estado.EM_MONITORAMENTO


def test_pagina_explica_por_que_uma_transicao_nao_esta_disponivel(sistema):
    t = cliente(sistema, "tecnico").get(f"/demanda/{_demanda_id(sistema[1])}").texto
    assert "Por que não:" in t and "disabled" in t


def test_relatorio_abre_com_conferencia_de_hash_e_recusa_arquivo_adulterado(sistema):
    app, nucleo, pasta = sistema
    c = cliente(sistema, "coord")
    rels = nucleo.repo.listar(E.Relatorio)
    html = next(r for r in rels if r.formato is FormatoRelatorio.HTML and r.numero_versao == 1)
    pdf = next(r for r in rels if r.formato is FormatoRelatorio.PDF)
    r = c.get(f"/relatorio/{html.id}")
    assert r.status == 200 and hashlib.sha256(r.bytes).hexdigest() == html.hash_conteudo and r.cab["content-type"][0].startswith("text/html")
    rp = c.get(f"/relatorio/{pdf.id}")
    assert rp.cab["content-type"] == ["application/pdf"] and "attachment" in rp.cab["content-disposition"][0] and rp.bytes[:4] == b"%PDF"
    arq = next((pasta / "relatorios").glob(f"*-v1.html"))
    arq.write_text("<html>adulterado</html>", encoding="utf-8")
    r2 = c.get(f"/relatorio/{html.id}")
    assert r2.status == 409 and "não confere" in r2.texto and "adulterado" not in r2.texto
    assert "RELATORIO_NAO_CONFERE" in [e.acao for e in nucleo.trilha.eventos]
    assert c.get("/relatorio/00000000-0000-4000-8000-00000000dead").status == 404


def test_emitir_relatorio_pela_tela_exige_motivo_na_reemissao(sistema):
    app, nucleo, _ = sistema
    c = cliente(sistema, "revisor")
    did = _demanda_id(nucleo)
    c.post(f"/demanda/{did}/relatorio", {"formato": "HTML", "motivo": ""})
    assert "reemissão exige motivo" in c.get(f"/demanda/{did}").texto
    c.post(f"/demanda/{did}/relatorio", {"formato": "HTML", "motivo": "Reemissão pedida na tela de operação."})
    assert "Relatório emitido (versão 3)" in c.get(f"/demanda/{did}").texto
    assert c.post(f"/demanda/{did}/relatorio", {"formato": "XML"}).status == 400


def test_exportar_baixa_json_valido_e_audita(sistema):
    app, nucleo, _ = sistema
    c = cliente(sistema, "coord")
    r = c.post("/exportar")
    assert r.status == 200 and r.cab["content-type"] == ["application/json"] and "attachment" in r.cab["content-disposition"][0]
    pacote = json.loads(r.bytes)
    jsonschema.Draft202012Validator(esquema_json()).validate(pacote)
    assert pacote["gerado_por_papeis"] == ["COORDENADOR"] and "coordenador-sintetico" not in r.texto
    assert "EXPORTACAO" in [e.acao for e in nucleo.trilha.eventos]


def test_auditoria_verifica_gera_ancora_e_confere_com_ela(sistema, tmp_path):
    app, nucleo, _ = sistema
    c = cliente(sistema, "auditor")
    c.post("/auditoria/verificar", {"ancora_texto": ""})
    t = c.get("/auditoria").texto
    assert "Cadeia da trilha conferida" in t and "não exclui reescrita completa" in t
    r = c.post("/auditoria/ancora")
    assert r.status == 200 and "attachment" in r.cab["content-disposition"][0]
    c.post("/auditoria/verificar", {"ancora_texto": r.bytes.decode("utf-8")})
    assert "Trilha conferida com a âncora colada" in c.get("/auditoria").texto
    c.post("/auditoria/verificar", {"ancora_texto": "isto não é âncora"})
    assert "ilegível" in c.get("/auditoria").texto


def test_backup_pela_tela_cria_verifica_e_recusa_nome_invalido(sistema):
    app, nucleo, pasta = sistema
    c = cliente(sistema, "admin")
    c.post("/backup/criar")
    t = c.get("/backup").texto
    nome = re.search(r"Backup (\d{8}T\d{6}Z) criado e verificado", t).group(1)
    assert (pasta / "backups" / nome / "manifesto.json").is_file()
    c.post("/backup/verificar", {"nome": nome})
    assert f"Backup {nome} confere" in c.get("/backup").texto
    c.post("/backup/verificar", {"nome": "../../etc"})
    assert "nome de backup inválido" in c.get("/backup").texto
    (pasta / "backups" / nome / "evidencias").mkdir(exist_ok=True)
    next((pasta / "backups" / nome / "evidencias").iterdir()).write_bytes(b"adulterado")
    c.post("/backup/verificar", {"nome": nome})
    assert "NÃO confere" in c.get("/backup").texto
    assert cliente(sistema, "tecnico").post("/backup/criar").status == 303
    tec = cliente(sistema, "tecnico")
    assert tec.post("/backup/criar").status == 303 and "Sem permissão" in tec.get("/painel").texto


# ================= conflitos (banco com sincronização simulada) =====================================================

@pytest.fixture
def com_conflito(tmp_path, atores, cenario):
    amb = Ambiente(tmp_path, atores, cenario)
    amb.disp.coletar(amb.c["PontoAmostral"][0])
    obs = amb.disp.coletar(amb.c["Observacao"][0])
    amb.sinc.executar()
    na = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(atores["tecnico"], com(na, valor_bruto="50", valor_normalizado=50.0), na.versao)
    amb.disp.corrigir(com(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    amb.sinc.executar()
    usuarios = {"coord": atores["coord"], "tecnico": atores["tecnico"]}
    app = Aplicacao(amb.central, hosts_permitidos={HOST}, usuarios=usuarios)
    return amb, app


def test_coordenador_ve_compara_e_resolve_o_conflito_pela_tela(com_conflito):
    amb, app = com_conflito
    c = Cliente(app).entrar("coord")
    assert "1 conflito(s) de sincronização aguardando sua decisão" in c.get("/painel").texto
    cid = amb.central.repo.listar_conflitos()[0]["id"]
    t = c.get(f"/conflitos/{cid}").texto
    assert "Valor anotado" in t and ">50<" in t and ">30<" in t and 'value="ACEITAR_DISPOSITIVO"' in t
    c.post(f"/conflitos/{cid}/resolver", {"decisao": "MANTER_CENTRAL", "motivo": "curto"})
    assert "motivo" in c.get(f"/conflitos/{cid}").texto and amb.central.repo.conflitos_abertos() == 1
    c.post(f"/conflitos/{cid}/resolver", {"decisao": "APAGAR", "motivo": "Decisão inválida de propósito."})
    assert amb.central.repo.conflitos_abertos() == 1
    c.post(f"/conflitos/{cid}/resolver", {"decisao": "MANTER_CENTRAL", "motivo": "Valor da central foi conferido."})
    assert "Decisão registrada" in c.get(f"/conflitos/{cid}").texto and amb.central.repo.conflitos_abertos() == 0
    assert amb.sinc.rodada().reconciliacao.aplicadas == 1            # o aparelho recebe a decisão
    assert amb.disp.nucleo.repo.listar(E.Observacao)[0].valor_bruto == "50"


def test_aceitar_o_aparelho_nao_e_oferecido_se_a_central_mudou_depois(com_conflito):
    amb, app = com_conflito
    atual = amb.na_central(E.Observacao)[0]
    amb.central.atualizar(amb.a["tecnico"], com(atual, valor_bruto="33", valor_normalizado=33.0), atual.versao)
    c = Cliente(app).entrar("coord")
    cid = amb.central.repo.listar_conflitos()[0]["id"]
    t = c.get(f"/conflitos/{cid}").texto
    assert 'value="ACEITAR_DISPOSITIVO"' not in t and "não está disponível" in t
    c.post(f"/conflitos/{cid}/resolver", {"decisao": "ACEITAR_DISPOSITIVO", "motivo": "Tentativa de aceitar mesmo assim."})
    assert "mudou na central" in c.get(f"/conflitos/{cid}").texto


def test_tecnico_nao_acessa_conflitos(com_conflito):
    amb, app = com_conflito
    c = Cliente(app).entrar("tecnico")
    cid = amb.central.repo.listar_conflitos()[0]["id"]
    assert c.get("/conflitos").status == 403 and c.get(f"/conflitos/{cid}").status == 403
    c.post(f"/conflitos/{cid}/resolver", {"decisao": "MANTER_CENTRAL", "motivo": "Técnico tentando decidir."})
    assert amb.central.repo.conflitos_abertos() == 1


# ================= servidor real em 127.0.0.1 ===========================================================================

def test_servidor_real_escuta_so_em_loopback_e_responde(modelo, tmp_path):
    destino = tmp_path / "srv"
    shutil.copytree(modelo, destino)
    pronto, info = threading.Event(), {}

    def rodar():
        repo = Repositorio(str(destino / "gaema-demo.db"))            # a conexão SQLite nasce na thread que a usa
        srv = servir(Nucleo(repo, destino), 0)
        info["srv"], info["porta"] = srv, srv.server_address[1]
        pronto.set()
        srv.serve_forever()
        srv.server_close(); repo.fechar()
    t = threading.Thread(target=rodar, daemon=True)
    t.start()
    assert pronto.wait(10)
    try:
        assert info["srv"].server_address[0] == "127.0.0.1"
        with urllib.request.urlopen(f"http://127.0.0.1:{info['porta']}/entrar", timeout=10) as r:
            corpo = r.read().decode()
            assert r.status == 200 and "Entrar (usuário de teste)" in corpo
            assert r.headers["Content-Security-Policy"].startswith("default-src 'none'")
    finally:
        info["srv"].shutdown()
        t.join(10)


# ================= sem JavaScript, sem recurso externo, acessibilidade ============================================

class Estrutura(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.niveis, self.rotulos_for, self.ids, self.controles = [], [], set(), set(), []
        self.lang = None; self.tabelas = []; self.th_sem_escopo = 0; self.botoes = []; self.atual_btn = None
        self.links_internos = []; self.externos = []; self.tabela = None; self.forms = 0; self.forms_com_submit = 0
        self._form_tem = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); self.tags.append(tag)
        if "id" in a: self.ids.add(a["id"])
        if tag == "html": self.lang = a.get("lang")
        if tag in ("h1", "h2", "h3"): self.niveis.append(int(tag[1]))
        if tag == "label" and "for" in a: self.rotulos_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden": self.controles.append(a.get("id"))
        if tag == "form": self.forms += 1; self._form_tem = False
        if tag == "button": self.atual_btn = ""; self._form_tem = True
        if tag == "table": self.tabela = {"caption": False}; self.tabelas.append(self.tabela)
        if tag == "caption" and self.tabela is not None: self.tabela["caption"] = True
        if tag == "th" and a.get("scope") not in ("col", "row"): self.th_sem_escopo += 1
        if tag == "a" and a.get("href", "").startswith("#"): self.links_internos.append(a["href"][1:])
        for atr in ("src", "href", "action"):
            if a.get(atr, "").startswith(("http:", "https:", "//")): self.externos.append((tag, a[atr]))
        if tag in ("script", "iframe", "object", "embed", "link"): self.externos.append((tag, "proibido"))
        if "style" in a: self.externos.append((tag, "estilo em atributo"))

    def handle_endtag(self, tag):
        if tag == "button": self.botoes.append(self.atual_btn.strip()); self.atual_btn = None
        if tag == "form" and self._form_tem: self.forms_com_submit += 1
        if tag == "table": self.tabela = None

    def handle_data(self, d):
        if self.atual_btn is not None: self.atual_btn += d


@pytest.fixture
def todas_as_paginas(sistema):
    app, nucleo, _ = sistema
    did = _demanda_id(nucleo)
    admin = cliente(sistema, "admin"); admin.post("/backup/criar")
    coord = cliente(sistema, "coord"); aud = cliente(sistema, "auditor"); anon = Cliente(app)
    return {"entrar": anon.get("/entrar").texto, "painel": coord.get("/painel").texto, "demanda": coord.get(f"/demanda/{did}").texto,
            "conflitos": coord.get("/conflitos").texto, "auditoria": aud.get("/auditoria").texto,
            "exportar": coord.get("/exportar").texto, "backup": admin.get("/backup").texto, "ajuda": coord.get("/ajuda").texto}


def test_paginas_sem_javascript_nem_recurso_externo(todas_as_paginas):
    for nome, html in todas_as_paginas.items():
        p = Estrutura(); p.feed(html)
        assert p.externos == [], (nome, p.externos)


def test_acessibilidade_estrutural_de_todas_as_paginas(todas_as_paginas):
    for nome, html in todas_as_paginas.items():
        p = Estrutura(); p.feed(html)
        assert p.lang == "pt-BR", nome
        assert p.niveis.count(1) == 1 and p.niveis[0] == 1, nome
        assert all(b - a <= 1 for a, b in zip(p.niveis, p.niveis[1:])), (nome, p.niveis)
        for tag in ("header", "main", "footer", "nav") if nome != "entrar" else ("header", "main", "footer"):
            assert p.tags.count(tag) == 1, (nome, tag)
        assert all(d in p.ids for d in p.links_internos), nome                     # link de salto aponta para algo real
        assert all(c and c in p.rotulos_for for c in p.controles), (nome, p.controles)  # todo campo tem rótulo associado
        assert p.forms == p.forms_com_submit and all(b for b in p.botoes), nome     # todo formulário tem botão com texto
        assert all(t["caption"] for t in p.tabelas) and p.th_sem_escopo == 0, nome
        assert ":focus-visible" in html and "pular" in html


def _tokens(html, seletor):
    bloco = re.search(re.escape(seletor) + r"\s*\{(.*?)\}", html, re.S).group(1)
    return dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", bloco))


def test_contraste_aa_nos_temas_claro_e_escuro(todas_as_paginas):
    html = todas_as_paginas["painel"]
    claro, escuro = _tokens(html, ":root"), _tokens(html, ':root[data-tema="escuro"]')
    pares_texto = [("texto", "fundo"), ("texto", "superficie"), ("texto", "superficie-2"), ("texto-2", "superficie"),
                   ("texto-2", "superficie-2"), ("link", "superficie"), ("link", "fundo"), ("marca", "superficie"),
                   ("marca-texto", "marca"), ("ok", "ok-fundo"), ("atencao", "atencao-fundo"), ("critico", "critico-fundo"),
                   ("info", "info-fundo"), ("ok", "superficie"), ("atencao", "superficie"), ("critico", "superficie"),
                   ("info", "superficie")]
    for nome, cores in (("claro", claro), ("escuro", escuro)):
        for a, b in pares_texto:
            assert razao_contraste(cores[a], cores[b]) >= 4.5, (nome, a, b, razao_contraste(cores[a], cores[b]))
        for a, b in (("borda-campo", "superficie"), ("foco", "superficie"), ("foco", "fundo")):
            assert razao_contraste(cores[a], cores[b]) >= 3.0, (nome, a, b)        # componentes de interface (1.4.11)
