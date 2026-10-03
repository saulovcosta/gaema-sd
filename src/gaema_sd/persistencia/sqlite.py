"""Repositório SQLite.

- Controle otimista: atualizar exige a versão lida; versão desatualizada gera
  ConflitoAtualizacao (nunca "última edição vence").
- Idempotência: reenvio com a mesma chave e o mesmo conteúdo devolve o registro
  existente; mesma chave com conteúdo diferente gera ConflitoIdempotencia.
- Histórico: toda versão gravada fica em `historico` (somente acréscimo).
- Auditoria: tabela somente acréscimo, protegida por gatilhos.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional, TypeVar

from ..dominio.entidades import EventoAuditoria
from ..dominio.serializacao import de_dict, json_canonico, para_dict, sha256_texto
from ..erros import ConflitoAtualizacao, ConflitoIdempotencia, RegistroNaoEncontrado

T = TypeVar("T")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS registros (
    tipo TEXT NOT NULL,
    id TEXT NOT NULL,
    versao INTEGER NOT NULL CHECK (versao >= 1),
    dados TEXT NOT NULL,
    hash_dados TEXT NOT NULL,
    chave_idempotencia TEXT NOT NULL DEFAULT '',
    gravado_em TEXT NOT NULL,
    PRIMARY KEY (tipo, id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_idempotencia
    ON registros (tipo, chave_idempotencia) WHERE chave_idempotencia <> '';

CREATE TABLE IF NOT EXISTS historico (
    tipo TEXT NOT NULL,
    id TEXT NOT NULL,
    versao INTEGER NOT NULL,
    dados TEXT NOT NULL,
    gravado_em TEXT NOT NULL,
    PRIMARY KEY (tipo, id, versao)
);

CREATE TABLE IF NOT EXISTS auditoria (
    sequencia INTEGER PRIMARY KEY,
    dados TEXT NOT NULL,
    hash_evento TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS fila_envio (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    entidade_id TEXT NOT NULL,
    operacao TEXT NOT NULL CHECK (operacao IN ('CRIAR', 'ATUALIZAR')),
    versao_base INTEGER NOT NULL,
    dados TEXT NOT NULL,
    hash_dados TEXT NOT NULL,
    chave_idempotencia TEXT NOT NULL DEFAULT '',
    situacao TEXT NOT NULL DEFAULT 'PENDENTE'
        CHECK (situacao IN ('PENDENTE', 'ENVIADO', 'CONFLITO', 'REJEITADO')),
    tentativas INTEGER NOT NULL DEFAULT 0,
    resultado TEXT NOT NULL DEFAULT '',
    erro TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    UNIQUE (tipo, entidade_id, operacao, hash_dados)
);

CREATE TABLE IF NOT EXISTS conflitos_sincronizacao (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    entidade_id TEXT NOT NULL,
    demanda_id TEXT NOT NULL DEFAULT '',
    versao_base INTEGER NOT NULL,
    versao_central INTEGER NOT NULL,
    hash_central TEXT NOT NULL,
    dados_dispositivo TEXT NOT NULL,
    hash_dispositivo TEXT NOT NULL,
    situacao TEXT NOT NULL DEFAULT 'ABERTO' CHECK (situacao IN ('ABERTO', 'RESOLVIDO')),
    decisao TEXT NOT NULL DEFAULT '',
    resolvido_por TEXT NOT NULL DEFAULT '',
    motivo_resolucao TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL,
    resolvido_em TEXT NOT NULL DEFAULT '',
    UNIQUE (tipo, entidade_id, hash_dispositivo)
);
CREATE TRIGGER IF NOT EXISTS conflitos_sem_delete BEFORE DELETE ON conflitos_sincronizacao
BEGIN SELECT RAISE(ABORT, 'conflito de sincronização não é apagado'); END;

CREATE TRIGGER IF NOT EXISTS auditoria_sem_update BEFORE UPDATE ON auditoria
BEGIN SELECT RAISE(ABORT, 'auditoria é somente acréscimo'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_sem_delete BEFORE DELETE ON auditoria
BEGIN SELECT RAISE(ABORT, 'auditoria é somente acréscimo'); END;
CREATE TRIGGER IF NOT EXISTS historico_sem_update BEFORE UPDATE ON historico
BEGIN SELECT RAISE(ABORT, 'histórico é somente acréscimo'); END;
CREATE TRIGGER IF NOT EXISTS historico_sem_delete BEFORE DELETE ON historico
BEGIN SELECT RAISE(ABORT, 'histórico é somente acréscimo'); END;
"""


VERSAO_ESQUEMA = 1  # PRAGMA user_version; base para recusar backup de esquema mais novo que o código


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conteudo(obj) -> tuple[str, str]:
    dados = json_canonico(obj)
    return dados, sha256_texto(dados)


class Repositorio:
    def __init__(self, caminho: str = ":memory:"):
        self.caminho = caminho
        self.con = sqlite3.connect(caminho, isolation_level=None, timeout=10)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA busy_timeout = 10000")
        if caminho != ":memory:":
            self.con.execute("PRAGMA journal_mode = WAL")  # leitores não bloqueiam o escritor
        self.con.executescript(ESQUEMA)
        if self.con.execute("PRAGMA user_version").fetchone()[0] == 0:
            self.con.execute(f"PRAGMA user_version = {VERSAO_ESQUEMA}")
        self._profundidade = 0

    def fechar(self) -> None:
        self.con.close()

    @contextmanager
    def transacao(self) -> Iterator[None]:
        """Transação de escrita. Aninhamento reaproveita a transação externa."""
        if self._profundidade:
            self._profundidade += 1
            try:
                yield
            finally:
                self._profundidade -= 1
            return
        self.con.execute("BEGIN IMMEDIATE")
        self._profundidade = 1
        try:
            yield
        except BaseException:
            self.con.execute("ROLLBACK")
            raise
        else:
            self.con.execute("COMMIT")
        finally:
            self._profundidade = 0

    # ------------------------------------------------------------ registros

    def inserir(self, obj: T) -> tuple[T, bool]:
        """Grava registro novo. Devolve (registro, criado). criado=False em reenvio idêntico."""
        tipo = type(obj).__name__
        obj = de_dict(type(obj), para_dict(obj))  # forma canônica (ex.: 10 e 10.0 viram o mesmo valor)
        chave = getattr(obj, "chave_idempotencia", "") or ""
        dados, hash_dados = _conteudo(obj)
        with self.transacao():
            existente = None
            if chave:
                existente = self.con.execute(
                    "SELECT id, hash_dados, dados FROM registros WHERE tipo=? AND chave_idempotencia=?",
                    (tipo, chave)).fetchone()
            if existente is None:
                existente = self.con.execute(
                    "SELECT id, hash_dados, dados FROM registros WHERE tipo=? AND id=?",
                    (tipo, obj.id)).fetchone()
            if existente is not None:
                if existente[1] == hash_dados:
                    return de_dict(type(obj), json.loads(existente[2])), False
                raise ConflitoIdempotencia(
                    f"{tipo}: já existe registro com a mesma chave/identificador e conteúdo diferente "
                    f"(id {existente[0]}); nada foi sobrescrito")
            agora = _agora()
            self.con.execute(
                "INSERT INTO registros (tipo, id, versao, dados, hash_dados, chave_idempotencia, gravado_em)"
                " VALUES (?,?,?,?,?,?,?)", (tipo, obj.id, obj.versao, dados, hash_dados, chave, agora))
            self.con.execute("INSERT INTO historico VALUES (?,?,?,?,?)", (tipo, obj.id, obj.versao, dados, agora))
        return obj, True

    def obter(self, cls: type[T], id: str) -> T:
        linha = self.con.execute("SELECT dados FROM registros WHERE tipo=? AND id=?",
                                 (cls.__name__, id)).fetchone()
        if linha is None:
            raise RegistroNaoEncontrado(f"{cls.__name__} {id} não encontrado")
        return de_dict(cls, json.loads(linha[0]))

    def listar(self, cls: type[T]) -> list[T]:
        linhas = self.con.execute("SELECT dados FROM registros WHERE tipo=? ORDER BY rowid",
                                  (cls.__name__,)).fetchall()
        return [de_dict(cls, json.loads(x[0])) for x in linhas]

    def atualizar(self, obj: T, versao_lida: int) -> T:
        """Grava nova versão se ninguém alterou o registro depois da leitura."""
        tipo = type(obj).__name__
        nova = dataclasses.replace(obj, versao=versao_lida + 1,
                                   atualizado_em=datetime.now(timezone.utc))
        dados, hash_dados = _conteudo(nova)
        chave = getattr(nova, "chave_idempotencia", "") or ""
        with self.transacao():
            try:
                cur = self.con.execute(
                    "UPDATE registros SET versao=?, dados=?, hash_dados=?, chave_idempotencia=?, gravado_em=?"
                    " WHERE tipo=? AND id=? AND versao=?",
                    (nova.versao, dados, hash_dados, chave, _agora(), tipo, obj.id, versao_lida))
            except sqlite3.IntegrityError as e:
                raise ConflitoIdempotencia(f"{tipo} {obj.id}: chave de envio já usada por outro registro") from e
            if cur.rowcount == 0:
                atual = self.con.execute("SELECT versao FROM registros WHERE tipo=? AND id=?",
                                         (tipo, obj.id)).fetchone()
                if atual is None:
                    raise RegistroNaoEncontrado(f"{tipo} {obj.id} não encontrado")
                raise ConflitoAtualizacao(
                    f"{tipo} {obj.id}: alterado por outra pessoa (versão lida {versao_lida}, "
                    f"atual {atual[0]}). Recarregue e refaça a alteração.")
            self.con.execute("INSERT INTO historico VALUES (?,?,?,?,?)",
                             (tipo, obj.id, nova.versao, dados, _agora()))
        return nova

    def historico(self, cls: type[T], id: str) -> list[T]:
        linhas = self.con.execute("SELECT dados FROM historico WHERE tipo=? AND id=? ORDER BY versao",
                                  (cls.__name__, id)).fetchall()
        return [de_dict(cls, json.loads(x[0])) for x in linhas]


    # ------------------------------------------------------------ conflitos de sincronização

    def registrar_conflito(self, *, tipo: str, entidade_id: str, demanda_id: str, versao_base: int,
                           versao_central: int, hash_central: str, dados_dispositivo: str,
                           hash_dispositivo: str) -> tuple[str, bool]:
        """Guarda a versão do dispositivo ao lado da central. Reenvio do mesmo conflito não duplica."""
        with self.transacao():
            existente = self.con.execute(
                "SELECT id FROM conflitos_sincronizacao WHERE tipo=? AND entidade_id=? AND hash_dispositivo=?",
                (tipo, entidade_id, hash_dispositivo)).fetchone()
            if existente:
                return existente[0], False
            id_ = str(uuid.uuid4())
            self.con.execute(
                "INSERT INTO conflitos_sincronizacao (id, tipo, entidade_id, demanda_id, versao_base,"
                " versao_central, hash_central, dados_dispositivo, hash_dispositivo, criado_em)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (id_, tipo, entidade_id, demanda_id, versao_base, versao_central, hash_central,
                 dados_dispositivo, hash_dispositivo, _agora()))
        return id_, True

    def obter_conflito(self, id_: str) -> dict:
        self.con.row_factory = sqlite3.Row
        try:
            linha = self.con.execute("SELECT * FROM conflitos_sincronizacao WHERE id=?", (id_,)).fetchone()
        finally:
            self.con.row_factory = None
        if linha is None:
            raise RegistroNaoEncontrado(f"conflito de sincronização {id_} não encontrado")
        return dict(linha)

    def conflitos_abertos(self, demanda_id: str | None = None) -> int:
        if demanda_id is None:
            return self.con.execute(
                "SELECT COUNT(*) FROM conflitos_sincronizacao WHERE situacao='ABERTO'").fetchone()[0]
        return self.con.execute(
            "SELECT COUNT(*) FROM conflitos_sincronizacao WHERE situacao='ABERTO' AND demanda_id=?",
            (demanda_id,)).fetchone()[0]

    def resolver_conflito(self, id_: str, *, decisao: str, resolvido_por: str, motivo: str) -> None:
        with self.transacao():
            cur = self.con.execute(
                "UPDATE conflitos_sincronizacao SET situacao='RESOLVIDO', decisao=?, resolvido_por=?,"
                " motivo_resolucao=?, resolvido_em=? WHERE id=? AND situacao='ABERTO'",
                (decisao, resolvido_por, motivo, _agora(), id_))
            if cur.rowcount == 0:
                raise RegistroNaoEncontrado(f"conflito {id_} inexistente ou já resolvido")


class ArmazenamentoAuditoriaSQLite:
    """Interface de armazenamento da TrilhaAuditoria, no mesmo banco do repositório.

    Registrar eventos sempre dentro de Repositorio.transacao(), para que a leitura
    do último evento e a gravação do novo sejam atômicas.
    """

    def __init__(self, repo: Repositorio):
        self.repo = repo

    def ultimo(self) -> Optional[EventoAuditoria]:
        linha = self.repo.con.execute(
            "SELECT dados FROM auditoria ORDER BY sequencia DESC LIMIT 1").fetchone()
        return de_dict(EventoAuditoria, json.loads(linha[0])) if linha else None

    def anexar(self, ev: EventoAuditoria) -> None:
        with self.repo.transacao():
            self.repo.con.execute("INSERT INTO auditoria VALUES (?,?,?)",
                                  (ev.sequencia, json.dumps(para_dict(ev), ensure_ascii=False), ev.hash_evento))

    def todos(self) -> list[EventoAuditoria]:
        linhas = self.repo.con.execute("SELECT dados FROM auditoria ORDER BY sequencia").fetchall()
        return [de_dict(EventoAuditoria, json.loads(x[0])) for x in linhas]
