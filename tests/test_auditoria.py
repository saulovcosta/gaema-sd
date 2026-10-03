import dataclasses
import sqlite3

import pytest

from gaema_sd.auditoria import ArmazenamentoMemoria, TrilhaAuditoria, sanear_detalhes, verificar_cadeia
from gaema_sd.erros import AuditoriaCorrompida
from gaema_sd.persistencia import ArmazenamentoAuditoriaSQLite, Repositorio


def _trilha(atores, n=4):
    t = TrilhaAuditoria()
    for i in range(n):
        t.registrar(atores["coord"], "ACAO", "Demanda", f"d{i}", motivo=f"m{i}")
    return t


def test_cadeia_integra(atores):
    assert _trilha(atores).verificar() == 4


def test_conteudo_adulterado_detectado(atores):
    ev = list(_trilha(atores).eventos)
    ev[1] = dataclasses.replace(ev[1], motivo="alterado depois")
    with pytest.raises(AuditoriaCorrompida, match="conteúdo alterado"):
        verificar_cadeia(ev)


def test_evento_removido_detectado(atores):
    ev = list(_trilha(atores).eventos)
    del ev[1]
    with pytest.raises(AuditoriaCorrompida):
        verificar_cadeia(ev)


def test_evento_reordenado_ou_hash_recalculado_detectado(atores):
    from gaema_sd.auditoria import calcular_hash

    ev = list(_trilha(atores).eventos)
    falso = dataclasses.replace(ev[2], ator_id="outra-pessoa")
    falso = dataclasses.replace(falso, hash_evento=calcular_hash(falso))
    ev[2] = falso
    with pytest.raises(AuditoriaCorrompida, match="elo"):
        verificar_cadeia(ev)


def test_logs_sem_dados_sensiveis():
    d = sanear_detalhes({"cpf": "x", "nome_ocupante": "y", "Email": "z", "token": "t", "texto": "a" * 500, "n": 1})
    assert d["cpf"] == d["nome_ocupante"] == d["Email"] == d["token"] == "[REMOVIDO]"
    assert len(d["texto"]) <= 201 and d["n"] == 1


def test_sqlite_impede_alterar_ou_apagar_auditoria(atores):
    repo = Repositorio(":memory:")
    t = TrilhaAuditoria(ArmazenamentoAuditoriaSQLite(repo))
    with repo.transacao():
        t.registrar(atores["coord"], "ACAO", "Demanda", "d1")
    with pytest.raises(sqlite3.DatabaseError, match="somente acréscimo"):
        repo.con.execute("UPDATE auditoria SET dados='{}'")
    with pytest.raises(sqlite3.DatabaseError, match="somente acréscimo"):
        repo.con.execute("DELETE FROM auditoria")
    assert t.verificar() == 1


def test_armazenamento_memoria_padrao(atores):
    arm = ArmazenamentoMemoria()
    TrilhaAuditoria(arm).registrar(atores["auditor"], "LER", "X", "1")
    assert len(arm.todos()) == 1
