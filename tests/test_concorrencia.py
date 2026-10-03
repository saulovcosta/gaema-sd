"""Concorrência com várias conexões ao MESMO arquivo SQLite (Fase 4). Só dados sintéticos."""

import dataclasses
import threading

from gaema_sd.dominio import entidades as E
from gaema_sd.erros import ConflitoAtualizacao, ConflitoIdempotencia
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio

from .apoio_sincronizacao import preparar_central


def _rodar(n, alvo):
    erros, ts = [], []

    def envolver(i):
        try:
            alvo(i)
        except BaseException as e:  # noqa: BLE001 - o teste precisa ver qualquer falha de thread
            erros.append(e)

    for i in range(n):
        ts.append(threading.Thread(target=envolver, args=(i,)))
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return erros


def _central_em_arquivo(tmp_path, atores, cenario):
    n = Nucleo(Repositorio(str(tmp_path / "central.db")), tmp_path / "saida")
    preparar_central(n, atores, cenario)
    return n


def test_modo_wal_em_arquivo(tmp_path):
    repo = Repositorio(str(tmp_path / "x.db"))
    assert repo.con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert repo.con.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
    assert repo.con.execute("PRAGMA user_version").fetchone()[0] >= 1
    repo.fechar()


def test_escritas_simultaneas_de_registros_distintos_nao_perdem_nada_e_a_trilha_fecha(tmp_path, atores, cenario):
    n = _central_em_arquivo(tmp_path, atores, cenario)
    base = cenario["PontoAmostral"][0]
    antes = len(n.trilha.eventos)

    def gravar(i):
        outro = Nucleo(Repositorio(str(tmp_path / "central.db")), tmp_path / "saida")
        try:
            for k in range(5):
                outro.registrar(atores["tecnico"], dataclasses.replace(
                    base, id=f"00000000-0000-4000-8000-{100000 + i * 10 + k:012d}", codigo=f"T{i}-{k}",
                    chave_idempotencia=f"t{i}:{k}"))
        finally:
            outro.repo.fechar()

    assert _rodar(6, gravar) == []
    assert len(n.repo.listar(E.PontoAmostral)) == 30
    assert len(n.trilha.eventos) == antes + 30
    assert n.verificar_auditoria(atores["auditor"]) == antes + 30  # sequência e elos sem buraco
    n.repo.fechar()


def test_mesmo_envio_simultaneo_grava_uma_vez_so(tmp_path, atores, cenario):
    n = _central_em_arquivo(tmp_path, atores, cenario)
    ponto = cenario["PontoAmostral"][0]

    def reenviar(i):
        outro = Nucleo(Repositorio(str(tmp_path / "central.db")), tmp_path / "saida")
        try:
            outro.registrar(atores["tecnico"], ponto)
        finally:
            outro.repo.fechar()

    assert _rodar(8, reenviar) == []
    assert len(n.repo.listar(E.PontoAmostral)) == 1
    acoes = [e.acao for e in n.trilha.eventos]
    assert acoes.count("CRIAR") >= 1 and acoes.count("REENVIO_IDEMPOTENTE") == 7
    n.repo.fechar()


def test_atualizacoes_simultaneas_da_mesma_versao_so_uma_vence(tmp_path, atores, cenario):
    n = _central_em_arquivo(tmp_path, atores, cenario)
    ponto, _ = n.registrar(atores["tecnico"], cenario["PontoAmostral"][0])
    obs, _ = n.registrar(atores["tecnico"], cenario["Observacao"][0])
    vencedores, conflitos = [], []

    def editar(i):
        outro = Nucleo(Repositorio(str(tmp_path / "central.db")), tmp_path / "saida")
        try:
            try:
                outro.atualizar(atores["tecnico"], dataclasses.replace(obs, valor_bruto=str(40 + i),
                                                                       valor_normalizado=float(40 + i)),
                                obs.versao)
                vencedores.append(i)
            except ConflitoAtualizacao:
                conflitos.append(i)
        finally:
            outro.repo.fechar()

    assert _rodar(6, editar) == []
    assert len(vencedores) == 1 and len(conflitos) == 5   # ninguém sobrescreveu ninguém em silêncio
    atual = n.repo.obter(E.Observacao, obs.id)
    assert atual.versao == obs.versao + 1 and atual.valor_bruto == str(40 + vencedores[0])
    assert [e.acao for e in n.trilha.eventos].count("CONFLITO_ATUALIZACAO") == 5
    n.repo.fechar()


def test_mesma_chave_com_conteudo_diferente_em_paralelo_recusa_o_segundo(tmp_path, atores, cenario):
    n = _central_em_arquivo(tmp_path, atores, cenario)
    base = cenario["PontoAmostral"][0]
    resultados = []

    def gravar(i):
        outro = Nucleo(Repositorio(str(tmp_path / "central.db")), tmp_path / "saida")
        try:
            try:
                outro.registrar(atores["tecnico"], dataclasses.replace(base, codigo=f"V{i}"))
                resultados.append("ok")
            except ConflitoIdempotencia:
                resultados.append("conflito")
        finally:
            outro.repo.fechar()

    assert _rodar(5, gravar) == []
    assert resultados.count("ok") == 1 and resultados.count("conflito") == 4
    assert len(n.repo.listar(E.PontoAmostral)) == 1
    n.repo.fechar()


def test_leitura_nao_e_bloqueada_enquanto_outra_conexao_escreve(tmp_path, atores, cenario):
    n = _central_em_arquivo(tmp_path, atores, cenario)
    n.registrar(atores["tecnico"], cenario["PontoAmostral"][0])
    leitor = Repositorio(str(tmp_path / "central.db"))
    with n.repo.transacao():  # escritor com transação aberta
        n.repo.con.execute("UPDATE registros SET gravado_em = gravado_em WHERE tipo = 'Nada'")
        assert len(leitor.listar(E.PontoAmostral)) == 1  # WAL: leitor vê o último estado confirmado
    leitor.fechar(); n.repo.fechar()
