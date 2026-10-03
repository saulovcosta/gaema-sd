"""Regressão dos achados da revisão independente da Fase 6 (interface, modo estrito, âncora, backup).
Cada teste reproduz o ataque que antes passava. Só dados sintéticos."""

import io
import json
import socket
import sqlite3
import threading
import time
import uuid

import pytest

from gaema_sd.acesso import Ator
from gaema_sd.backup import __main__ as cli_backup
from gaema_sd.backup.ancora import conferir_ancora, gerar_ancora, interpretar_ancora, ler_ancora
from gaema_sd.backup.backup import criar_backup
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado, Papel
from gaema_sd.dominio.serializacao import json_canonico, para_dict, sha256_texto
from gaema_sd.erros import AcessoNegado, ErroGaema
from gaema_sd.interface import app as modulo_app
from gaema_sd.persistencia import Repositorio
from gaema_sd.sincronizacao.item import ItemSincronizacao
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import Ambiente, com
from .test_interface import Cliente, cliente, modelo, sistema  # noqa: F401 - fixtures reaproveitadas

S = Estado


def novo_id():
    return str(uuid.uuid4())


def item(tipo, op, obj, base):
    d = para_dict(obj)
    return ItemSincronizacao(tipo=tipo, entidade_id=obj.id, operacao=op, versao_base=base, dados=d,
                             hash_dados=sha256_texto(json_canonico(d)), chave_idempotencia=obj.chave_idempotencia)


@pytest.fixture
def mundo(tmp_path, atores, cenario):
    """Central com duas demandas: A (equipe do técnico A) e B (equipe só do técnico B), ambas EM_CAMPO."""
    amb = Ambiente(tmp_path, atores, cenario)
    a, c, ce = atores, cenario, amb.central
    tec_b = Ator.de("usuario-sintetico-22", Papel.TECNICO_CAMPO)
    eq = com(c["Equipe"][0], id=novo_id(), nome="Equipe B",
             membros=[E.MembroEquipe(usuario_id=tec_b.id, papel=Papel.TECNICO_CAMPO, funcao="vistoria")])
    ce.registrar(a["coord"], eq)
    dem = com(c["Demanda"][0], id=novo_id(), titulo="Demanda B", equipe_id=eq.id)
    ce.registrar(a["coord"], dem)
    ce.transitar(a["sistema"], dem.id, S.ALERTA)
    ce.transitar(a["analista"], dem.id, S.EM_TRIAGEM)
    ce.transitar(a["membro"], dem.id, S.DEMANDA_ABERTA, motivo="abertura para averiguação sintética")
    ce.transitar(a["coord"], dem.id, S.ATRIBUIDA)
    camp = com(c["CampanhaVistoria"][0], id=novo_id(), demanda_id=dem.id, equipe_id=eq.id)
    ce.registrar(a["coord"], camp)
    ce.transitar(a["coord"], dem.id, S.PLANEJADA)
    ce.transitar(tec_b, dem.id, S.EM_CAMPO)
    pA = com(c["PontoAmostral"][0], chave_idempotencia="kA")
    ce.registrar(a["tecnico"], pA)
    oA = com(c["Observacao"][0], observador_id="")
    ce.registrar(a["tecnico"], oA)
    pB = com(c["PontoAmostral"][0], id=novo_id(), campanha_id=camp.id, codigo="PB1", chave_idempotencia="kB")
    ce.registrar(tec_b, pB)
    oB = com(c["Observacao"][0], id=novo_id(), ponto_id=pB.id, chave_idempotencia="kOB", observador_id="")
    ce.registrar(tec_b, oB)
    mB = com(c["MedicaoPenetracao"][0], id=novo_id(), ponto_id=pB.id, chave_idempotencia="kMB")
    ce.registrar(tec_b, mB)
    return type("Mundo", (), dict(amb=amb, ce=ce, a=a, c=c, tec_b=tec_b, dem_b=dem, camp_b=camp,
                                  pA=pA, oA=oA, pB=pB, oB=oB, mB=mB))


def _b_em_validacao(m):
    m.ce.transitar(m.tec_b, m.dem_b.id, S.AGUARDANDO_SINCRONIZACAO)
    m.ce.transitar(m.a["sistema"], m.dem_b.id, S.EM_VALIDACAO)


# 1 (ALTA) -------------------------------------------------------------------------------------------------------------
def test_1_atualizar_nao_move_dado_de_outra_demanda(mundo):
    m = mundo
    _b_em_validacao(m)
    o = m.ce.repo.obter(E.Observacao, m.oB.id)
    with pytest.raises(ErroGaema, match="vínculo"):
        m.ce.atualizar(m.a["tecnico"], com(o, ponto_id=m.pA.id), o.versao)
    p = m.ce.repo.obter(E.PontoAmostral, m.pB.id)
    with pytest.raises(ErroGaema, match="vínculo"):
        m.ce.atualizar(m.a["tecnico"], com(p, campanha_id=m.c["CampanhaVistoria"][0].id), p.versao)
    med = m.ce.repo.obter(E.MedicaoPenetracao, m.mB.id)
    with pytest.raises(ErroGaema, match="vínculo"):
        m.ce.receber_sincronizacao(m.a["tecnico"], item("MedicaoPenetracao", "ATUALIZAR", com(med, ponto_id=m.pA.id), 1))
    assert m.ce.repo.obter(E.Observacao, m.oB.id).ponto_id == m.pB.id
    assert m.ce.repo.obter(E.MedicaoPenetracao, m.mB.id).ponto_id == m.pB.id
    assert m.ce.repo.obter(E.PontoAmostral, m.pB.id).campanha_id == m.camp_b.id


def test_1_atualizar_confere_equipe_e_estado_do_registro_gravado(mundo):
    m = mundo
    o = m.ce.repo.obter(E.Observacao, m.oB.id)
    with pytest.raises(ErroGaema, match="equipe"):      # técnico A, mesmo sem mudar o vínculo, não é da equipe B
        m.ce.atualizar(m.a["tecnico"], com(o, valor_bruto="1"), o.versao)
    _b_em_validacao(m)
    o = m.ce.repo.obter(E.Observacao, m.oB.id)
    with pytest.raises(ErroGaema, match="estado"):
        m.ce.atualizar(m.tec_b, com(o, valor_bruto="1"), o.versao)


# 2 (MÉDIA) ------------------------------------------------------------------------------------------------------------
def test_2_versao_atrasada_depois_da_coleta_e_recusada_e_nao_vira_conflito(mundo):
    m = mundo
    o = m.ce.repo.obter(E.Observacao, m.oB.id)
    m.ce.atualizar(m.tec_b, com(o, valor_bruto="10"), o.versao)
    _b_em_validacao(m)
    with pytest.raises(ErroGaema, match="estado"):
        m.ce.receber_sincronizacao(m.tec_b, item("Observacao", "ATUALIZAR", com(o, valor_bruto="99"), 1))
    assert m.ce.repo.listar_conflitos() == []
    assert m.ce.repo.obter(E.Observacao, m.oB.id).valor_bruto == "10"


def test_2_criar_com_id_de_ponto_alheio_nao_sequestra_o_ponto(mundo):
    m = mundo
    falso = com(m.pB, campanha_id=m.c["CampanhaVistoria"][0].id, codigo="PX", chave_idempotencia="kX")
    with pytest.raises(ErroGaema, match="vínculo"):
        m.ce.receber_sincronizacao(m.a["tecnico"], item("PontoAmostral", "CRIAR", falso, 0))
    assert m.ce.repo.listar_conflitos() == []
    assert m.ce.repo.obter(E.PontoAmostral, m.pB.id).campanha_id == m.camp_b.id


def test_2_aceitar_dispositivo_reconfere_vinculo_e_estado(mundo):
    m = mundo
    o = m.ce.repo.obter(E.Observacao, m.oB.id)
    m.ce.atualizar(m.tec_b, com(o, valor_bruto="10"), o.versao)
    m.ce.receber_sincronizacao(m.tec_b, item("Observacao", "ATUALIZAR", com(o, valor_bruto="99"), 1))
    k = m.ce.repo.listar_conflitos()[0]
    # o conflito nasceu em coleta; se a demanda sair dela por fora (simulação de banco adulterado), aceitar é recusado
    m.ce.repo.con.execute("UPDATE registros SET dados = json_set(dados, '$.estado', 'EM_VALIDACAO') WHERE id = ?",
                          (m.dem_b.id,))
    with pytest.raises(ErroGaema, match="estado"):
        m.ce.resolver_conflito_sincronizacao(m.a["coord"], k["id"], "ACEITAR_DISPOSITIVO", "motivo de teste longo")
    assert m.ce.repo.obter(E.Observacao, m.oB.id).valor_bruto == "10"


# 6 (MÉDIA) ------------------------------------------------------------------------------------------------------------
def test_6_tecnico_so_ve_e_move_demanda_da_propria_equipe(mundo):
    m = mundo
    with pytest.raises(AcessoNegado, match="própria equipe"):
        m.ce.transitar(m.a["tecnico"], m.dem_b.id, S.AGUARDANDO_SINCRONIZACAO)
    assert m.ce.repo.obter(E.Demanda, m.dem_b.id).estado is S.EM_CAMPO
    assert {d.id for d in m.ce.listar(m.a["tecnico"], E.Demanda)} == {m.amb.demanda_id}
    assert {d.id for d in m.ce.listar(m.tec_b, E.Demanda)} == {m.dem_b.id}
    assert len(m.ce.listar(m.a["coord"], E.Demanda)) == 2
    possiveis = m.ce.transicoes_possiveis(m.a["tecnico"], m.dem_b.id)
    assert possiveis and not any(t["disponivel"] for t in possiveis)
    assert "TRANSICAO_RECUSADA" in [e.acao for e in m.ce.trilha.eventos]


# 7 (MÉDIA) ------------------------------------------------------------------------------------------------------------
def test_7_historico_sem_permissao_de_auditoria_mostra_so_transicoes_sem_pessoas(mundo):
    m = mundo
    h = m.ce.historico_de(m.a["tecnico"], "Demanda", m.amb.demanda_id)
    assert h and all(e.acao == "TRANSICAO" and e.ator_id == "" and e.motivo == "" for e in h)
    assert m.ce.historico_de(m.a["tecnico"], "Observacao", m.oA.id) == []
    completo = m.ce.historico_de(m.a["auditor"], "Demanda", m.amb.demanda_id)
    assert any(e.ator_id for e in completo) and any(e.acao == "CRIAR" for e in completo)


def test_7_tela_da_demanda_nao_mostra_quem_nem_motivo_para_quem_nao_audita(sistema):
    from .test_interface import _demanda_id
    did = _demanda_id(sistema[1])
    t = cliente(sistema, "analista").get(f"/demanda/{did}").texto
    assert "Últimas mudanças de situação" in t and "abertura para averiguação" not in t
    assert 'data-rotulo="Quem"' not in t
    t = cliente(sistema, "auditor").get(f"/demanda/{did}").texto
    assert 'data-rotulo="Quem"' in t


# 8 (BAIXA) ------------------------------------------------------------------------------------------------------------
def test_8_evidencia_nao_aponta_observacao_de_outra_campanha(mundo):
    m = mundo
    ev = com(m.c["Evidencia"][0], id=novo_id(), observacao_id=m.oB.id, ponto_id=m.pA.id, registrado_por="",
             chave_idempotencia="e:" + novo_id())
    with pytest.raises(ErroGaema, match="outra campanha"):
        m.ce.registrar_evidencia(m.a["tecnico"], ev, FOTO_SINTETICA)


# 9 (BAIXA) ------------------------------------------------------------------------------------------------------------
def test_9_modo_do_nucleo_nao_pode_ser_trocado_depois_de_criado(mundo):
    with pytest.raises(AttributeError):
        mundo.ce.modo = "livre"
    assert mundo.ce.modo == "central"


# 10 (BAIXA) e mutantes da âncora -------------------------------------------------------------------------------------
def test_10_cli_ancora_malformada_sem_traceback_e_nao_ancora_trilha_adulterada(tmp_path, monkeypatch, capsys, nucleo,
                                                                              atores, cenario):
    banco = tmp_path / "g.db"
    from gaema_sd.nucleo import Nucleo
    n = Nucleo(Repositorio(str(banco)), tmp_path / "s", modo="livre")
    n.registrar(atores["analista"], cenario["FonteDado"][0])
    n.registrar(atores["analista"], cenario["AreaCandidata"][0])
    destino = tmp_path / "bk"
    criar_backup(n.repo, tmp_path / "s", destino)
    ruim = tmp_path / "ruim.json"
    ruim.write_text('{"formato": 1', encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["x", "verificar", str(destino), "--ancora", str(ruim)])
    assert cli_backup.main() == 2 and "âncora recusada" in capsys.readouterr().out
    n.repo.con.execute("DROP TRIGGER auditoria_sem_update")      # atacante com acesso ao arquivo do banco
    n.repo.con.execute("UPDATE auditoria SET dados = replace(dados, 'CRIAR', 'ATUALIZAR') WHERE sequencia = 1")
    n.repo.fechar()
    monkeypatch.setattr("sys.argv", ["x", "ancorar", str(banco), str(tmp_path / "fora")])
    assert cli_backup.main() == 1 and "NÃO confere" in capsys.readouterr().out
    assert not (tmp_path / "fora").exists() or not any((tmp_path / "fora").iterdir())


def test_ancora_recusa_eventos_nao_positivos_bool_e_texto_grande(nucleo, atores, cenario):
    nucleo.registrar(atores["analista"], cenario["FonteDado"][0])
    a = gerar_ancora(nucleo.trilha.eventos)
    for ruim in (0, -1, True, 1.0):
        b = dict(a, eventos=ruim)
        with pytest.raises(ErroGaema):
            interpretar_ancora(json.dumps(b))
        assert conferir_ancora(nucleo.trilha.eventos, b)            # conferência direta também recusa
    with pytest.raises(ErroGaema, match="grande"):
        interpretar_ancora(" " * 5000)
    assert interpretar_ancora(json.dumps(a)) == a


def test_ler_ancora_nao_le_dispositivo_nem_pasta(tmp_path):
    for caminho in ("/dev/zero", str(tmp_path)):
        with pytest.raises(ErroGaema, match="ilegível"):
            ler_ancora(caminho)


def test_gerar_ancora_pelo_nucleo_recusa_trilha_adulterada(tmp_path, atores, cenario):
    from gaema_sd.nucleo import Nucleo
    banco = str(tmp_path / "g.db")
    n = Nucleo(Repositorio(banco), tmp_path, modo="livre")
    n.registrar(atores["analista"], cenario["FonteDado"][0])
    n.repo.con.execute("DROP TRIGGER auditoria_sem_update")      # atacante com acesso ao arquivo do banco
    n.repo.con.execute("UPDATE auditoria SET dados = replace(dados, 'CRIAR', 'ATUALIZAR') WHERE sequencia = 1")
    n.repo.fechar()
    n = Nucleo(Repositorio(banco), tmp_path, modo="livre")
    with pytest.raises(ErroGaema):
        n.gerar_ancora(atores["auditor"])
    n.repo.fechar()


# 3 (MÉDIA) ------------------------------------------------------------------------------------------------------------
def test_3_auditoria_nao_le_caminho_do_servidor_e_checa_permissao_antes(sistema, tmp_path):
    app, nucleo, _ = sistema
    alvo = tmp_path / "segredo.json"
    alvo.write_text("{}", encoding="utf-8")
    c = cliente(sistema, "analista")
    antes = len(nucleo.trilha.eventos)
    r = c.post("/auditoria/verificar", {"ancora_texto": "{}", "ancora_arquivo": str(alvo)})
    assert r.status == 303
    t = c.get("/auditoria").texto
    assert "malformada" not in t and "ilegível" not in t                 # nada foi interpretado
    assert "ACESSO_NEGADO" in [e.acao for e in nucleo.trilha.eventos[antes:]]


# 4 (MÉDIA) ------------------------------------------------------------------------------------------------------------
def test_4_conexao_parada_nao_trava_o_servidor(modelo, tmp_path):
    import shutil
    from gaema_sd.interface import servir
    from gaema_sd.nucleo import Nucleo
    destino = tmp_path / "srv"
    shutil.copytree(modelo, destino)
    repo = Repositorio(str(destino / "gaema-demo.db"))
    srv = servir(Nucleo(repo, destino), 0)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    parados = []
    try:
        for cabecalho in ("Content-Length: -1", "Content-Length: 60000"):
            s = socket.create_connection(("127.0.0.1", porta), timeout=5)
            s.sendall(f"POST /entrar HTTP/1.1\r\nHost: 127.0.0.1:{porta}\r\n{cabecalho}\r\n"
                      "Content-Type: application/x-www-form-urlencoded\r\n\r\nusuario=coord".encode())
            parados.append(s)
        ocioso = socket.create_connection(("127.0.0.1", porta), timeout=5)   # nem manda o pedido
        parados.append(ocioso)
        inicio = time.monotonic()
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/entrar", timeout=5) as r:
            assert r.status == 200
        assert time.monotonic() - inicio < 3
    finally:
        for s in parados:
            s.close()
        srv.shutdown()
        t.join(10)
        srv.server_close()
        repo.fechar()


def test_4_content_length_negativo_e_recusado(sistema):
    c = Cliente(sistema[0])
    r = c.pedir("POST", "/entrar", corpo=b"usuario=coord", cabecalhos={"CONTENT_LENGTH": "-1"})
    assert r.status == 400


# 5 (MÉDIA) ------------------------------------------------------------------------------------------------------------
def test_5_muitas_paginas_de_entrada_nao_derrubam_quem_ja_entrou(sistema):
    app = sistema[0]
    vitima = cliente(sistema, "coord")
    for _ in range(modulo_app.MAX_SESSOES * 2):
        Cliente(app).get("/entrar")
    assert vitima.get("/painel").status == 200
    assert sum(s.usuario is None for s in app.sessoes.values()) <= modulo_app.MAX_ANONIMAS


def test_5_sessao_expira_por_tempo(sistema, monkeypatch):
    c = cliente(sistema, "coord")
    assert c.get("/painel").status == 200
    agora = time.monotonic()
    monkeypatch.setattr(modulo_app.time, "monotonic", lambda: agora + modulo_app.SESSAO_TTL + 1)
    r = c.get("/painel")
    assert r.status == 303 and r.cab["location"] == ["/entrar"]


# 11 (BAIXA) -----------------------------------------------------------------------------------------------------------
def test_11_token_nao_ascii_da_403_e_nao_500(sistema):
    c = cliente(sistema, "coord")
    r = c.pedir("POST", "/sair", {"csrf": "é"})
    assert r.status == 403


def test_campo_repetido_no_formulario_e_recusado(sistema):
    c = cliente(sistema, "coord")
    corpo = f"csrf={c.csrf}&csrf={c.csrf}".encode()
    assert c.pedir("POST", "/sair", corpo=corpo).status == 400


def test_sair_encerra_a_sessao_no_servidor(sistema):
    c = cliente(sistema, "coord")
    antigo = c.cookie
    c.post("/sair")
    outro = Cliente(sistema[0])
    outro.cookie = antigo
    assert outro.get("/painel").status == 303


def test_erro_escapa_texto(sistema):
    r = sistema[0]._erro(400, "<script>x</script>", "<b>y</b>")
    assert b"<script>x" not in r.corpo and b"&lt;script&gt;" in r.corpo


# 13 (BAIXA) -----------------------------------------------------------------------------------------------------------
def test_13_dois_backups_no_mesmo_segundo_dao_mensagem_clara(sistema, monkeypatch):
    app, nucleo, _ = sistema
    from gaema_sd import nucleo as modulo_nucleo
    fixo = modulo_nucleo.datetime(2026, 10, 3, 12, 0, 0, tzinfo=modulo_nucleo.timezone.utc)

    class Relogio(modulo_nucleo.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixo
    monkeypatch.setattr(modulo_nucleo, "datetime", Relogio)
    admin = modulo_app.USUARIOS_DE_TESTE["admin"]
    nucleo.criar_backup(admin)
    with pytest.raises(ErroGaema, match="mesmo segundo"):
        nucleo.criar_backup(admin)
    assert nucleo.verificar_backup(admin, "20261003T120000Z") == []


def test_13_backups_simultaneos_no_mesmo_destino_nao_se_apagam(tmp_path, nucleo, atores, cenario):
    nucleo.registrar(atores["analista"], cenario["FonteDado"][0])
    destino = tmp_path / "bk"
    destino.mkdir()
    (destino / ".em-criacao").touch()                 # outro processo está criando
    with pytest.raises(ErroGaema, match="outro backup|vazia"):
        criar_backup(nucleo.repo, nucleo.saida, destino)
    assert (destino / ".em-criacao").exists()          # o perdedor não apaga o trabalho do outro


# 14 (BAIXA) -----------------------------------------------------------------------------------------------------------
def test_14_banco_legado_sem_versao_recebe_a_coluna_nova(tmp_path):
    banco = tmp_path / "legado.db"
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE conflitos_sincronizacao (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entidade_id TEXT NOT NULL,"
                " demanda_id TEXT NOT NULL DEFAULT '', versao_base INTEGER NOT NULL, versao_central INTEGER NOT NULL,"
                " hash_central TEXT NOT NULL DEFAULT '', dados_dispositivo TEXT NOT NULL, hash_dispositivo TEXT NOT NULL,"
                " situacao TEXT NOT NULL DEFAULT 'ABERTO', decisao TEXT NOT NULL DEFAULT '', resolvido_por TEXT NOT NULL"
                " DEFAULT '', motivo_resolucao TEXT NOT NULL DEFAULT '', criado_em TEXT NOT NULL, resolvido_em TEXT NOT"
                " NULL DEFAULT '', UNIQUE(tipo, entidade_id, hash_dispositivo))")
    con.execute("INSERT INTO conflitos_sincronizacao (id, tipo, entidade_id, versao_base, versao_central,"
                " dados_dispositivo, hash_dispositivo, criado_em) VALUES ('c1','Observacao','e1',1,2,'{}','h','2026-01-01')")
    con.commit()
    con.close()
    repo = Repositorio(str(banco))
    assert repo.listar_conflitos()[0]["enviado_por"] == ""
    repo.fechar()


# 15 (BAIXA) -----------------------------------------------------------------------------------------------------------
def test_15_textos_nao_prometem_mais_do_que_fazem(sistema):
    c = cliente(sistema, "auditor")
    c.post("/auditoria/verificar", {"ancora_texto": ""})
    t = c.get("/auditoria").texto
    assert "íntegra" not in t and "não exclui reescrita completa" in t
    fonte = (modulo_app.__file__)
    texto = open(fonte, encoding="utf-8").read()
    assert "recebe a decisão na próxima sincronização" not in texto


# Mutantes sobreviventes da revisão --------------------------------------------------------------------------------------
def test_mutantes_leituras_e_backup_exigem_permissao_e_sao_auditados(sistema):
    app, nucleo, pasta = sistema
    U = modulo_app.USUARIOS_DE_TESTE
    for f in (lambda a: nucleo.verificar_backup(a, "20260101T000000Z"), lambda a: nucleo.listar_backups(a),
              lambda a: nucleo.criar_backup(a)):
        with pytest.raises(AcessoNegado):
            f(U["tecnico"])
    antes = len(nucleo.trilha.eventos)
    nucleo.criar_backup(U["admin"])
    assert "BACKUP_CRIADO" in [e.acao for e in nucleo.trilha.eventos[antes:]]
    (pasta / "backups" / "arquivo-solto.txt").write_text("x", encoding="utf-8")
    assert all(n != "arquivo-solto.txt" for n in nucleo.listar_backups(U["admin"]))
    antes = len(nucleo.trilha.eventos)
    nucleo.listar(U["coord"], E.Demanda)
    assert "LISTAGEM_RESTRITA" in [e.acao for e in nucleo.trilha.eventos[antes:]]


def test_mutante_verificar_backup_usa_a_ancora(sistema):
    app, nucleo, pasta = sistema
    admin, auditor = modulo_app.USUARIOS_DE_TESTE["admin"], modulo_app.USUARIOS_DE_TESTE["auditor"]
    ancora = nucleo.gerar_ancora(auditor)
    nome = nucleo.criar_backup(admin)["nome"]
    falsa = dict(ancora, eventos=ancora["eventos"] + 10_000)
    assert nucleo.verificar_backup(admin, nome, falsa)       # trilha "truncada" em relação à âncora: problema
    assert nucleo.verificar_backup(admin, nome, ancora) == []


def test_mutante_resumo_e_transicoes_exigem_leitura_restrita(sistema):
    app, nucleo, _ = sistema
    from .test_interface import _demanda_id
    sem_papel = Ator.de("usuario-sintetico-88", Papel.SISTEMA)
    did = _demanda_id(nucleo)
    for f in (nucleo.resumo_demanda, nucleo.transicoes_possiveis):
        with pytest.raises(AcessoNegado):
            f(sem_papel, did)
