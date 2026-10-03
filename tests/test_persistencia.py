import dataclasses
import threading

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.erros import ConflitoAtualizacao, ConflitoIdempotencia, RegistroNaoEncontrado
from gaema_sd.persistencia import Repositorio


@pytest.fixture
def repo():
    r = Repositorio(":memory:")
    yield r
    r.fechar()


def test_gravar_e_ler_todas_as_entidades_do_cenario(repo, cenario):
    for lista in cenario.values():
        for obj in lista:
            gravado, criado = repo.inserir(obj)
            assert criado and repo.obter(type(obj), obj.id) == obj


def test_envio_duplicado_nao_duplica(repo, cenario):
    ponto = cenario["PontoAmostral"][0]
    assert repo.inserir(ponto)[1] is True
    for _ in range(3):  # reenvio após perda de confirmação
        assert repo.inserir(ponto)[1] is False
    assert len(repo.listar(E.PontoAmostral)) == 1


def test_mesma_chave_conteudo_diferente_nao_sobrescreve(repo, cenario):
    ponto = cenario["PontoAmostral"][0]
    repo.inserir(ponto)
    outro = dataclasses.replace(ponto, id=E.novo_id(), latitude=-10.4)
    with pytest.raises(ConflitoIdempotencia, match="nada foi sobrescrito"):
        repo.inserir(outro)
    assert repo.obter(E.PontoAmostral, ponto.id).latitude == ponto.latitude


def test_conflito_de_atualizacao(repo, cenario):
    d = cenario["Demanda"][0]
    repo.inserir(d)
    lido_a = repo.obter(E.Demanda, d.id)
    lido_b = repo.obter(E.Demanda, d.id)
    repo.atualizar(dataclasses.replace(lido_a, objetivo="versão A"), lido_a.versao)
    with pytest.raises(ConflitoAtualizacao, match="outra pessoa"):
        repo.atualizar(dataclasses.replace(lido_b, objetivo="versão B"), lido_b.versao)
    atual = repo.obter(E.Demanda, d.id)
    assert (atual.objetivo, atual.versao) == ("versão A", 2)


def test_historico_preserva_todas_as_versoes(repo, cenario):
    d = cenario["Demanda"][0]
    repo.inserir(d)
    repo.atualizar(dataclasses.replace(d, objetivo="v2"), 1)
    repo.atualizar(dataclasses.replace(d, objetivo="v3"), 2)
    assert [x.objetivo for x in repo.historico(E.Demanda, d.id)] == ["Teste do fluxo", "v2", "v3"]


def test_inexistente(repo):
    with pytest.raises(RegistroNaoEncontrado):
        repo.obter(E.Demanda, "nao-existe")


def test_rollback_nao_deixa_rastro(repo, cenario):
    d = cenario["Demanda"][0]
    with pytest.raises(RuntimeError):
        with repo.transacao():
            repo.inserir(d)
            raise RuntimeError("falha simulada no meio da gravação")
    assert repo.listar(E.Demanda) == []


def test_concorrencia_real_duas_conexoes(tmp_path, cenario):
    """Duas pessoas editam a mesma demanda ao mesmo tempo: só uma vence, a outra recebe conflito."""
    caminho = str(tmp_path / "gaema_teste.db")
    d = cenario["Demanda"][0]
    Repositorio(caminho).inserir(d)
    barreira = threading.Barrier(8)
    resultados = []

    def editar(i):
        r = Repositorio(caminho)
        lido = r.obter(E.Demanda, d.id)
        barreira.wait()
        try:
            r.atualizar(dataclasses.replace(lido, objetivo=f"edição {i}"), lido.versao)
            resultados.append("ok")
        except ConflitoAtualizacao:
            resultados.append("conflito")
        finally:
            r.fechar()

    threads = [threading.Thread(target=editar, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(resultados) == ["conflito"] * 7 + ["ok"]
    r = Repositorio(caminho)
    assert r.obter(E.Demanda, d.id).versao == 2
    assert len(r.historico(E.Demanda, d.id)) == 2
