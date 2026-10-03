"""Fila local de envio do dispositivo (tabela `fila_envio` no SQLite do próprio dispositivo).

Sobrevive a reinício. A ordem de envio é a ordem de enfileiramento. Item confirmado sai de
PENDENTE; item em conflito ou rejeitado fica guardado, nunca é descartado em silêncio.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..auditoria.trilha import sanear_texto
from ..persistencia.sqlite import Repositorio
from .item import ItemSincronizacao

_LIMITE_ERRO = 200


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class FilaLocal:
    def __init__(self, repo: Repositorio):
        self.repo = repo

    def enfileirar(self, item: ItemSincronizacao) -> bool:
        """Devolve False se o mesmo item já está na fila (enfileirar duas vezes não duplica)."""
        with self.repo.transacao():
            cur = self.repo.con.execute(
                "INSERT OR IGNORE INTO fila_envio (tipo, entidade_id, operacao, versao_base, dados, hash_dados,"
                " chave_idempotencia, criado_em, atualizado_em) VALUES (?,?,?,?,?,?,?,?,?)",
                (item.tipo, item.entidade_id, item.operacao, item.versao_base,
                 json.dumps(item.dados, ensure_ascii=False, sort_keys=True), item.hash_dados,
                 item.chave_idempotencia, _agora(), _agora()))
            return cur.rowcount == 1

    def pendentes(self) -> list[tuple[int, ItemSincronizacao, int]]:
        linhas = self.repo.con.execute(
            "SELECT seq, tipo, entidade_id, operacao, versao_base, dados, hash_dados, chave_idempotencia,"
            " tentativas FROM fila_envio WHERE situacao='PENDENTE' ORDER BY seq").fetchall()
        return [(l[0], ItemSincronizacao(tipo=l[1], entidade_id=l[2], operacao=l[3], versao_base=l[4],
                                         dados=json.loads(l[5]), hash_dados=l[6], chave_idempotencia=l[7]), l[8])
                for l in linhas]

    def registrar_tentativa(self, seq: int) -> None:
        with self.repo.transacao():
            self.repo.con.execute("UPDATE fila_envio SET tentativas=tentativas+1, atualizado_em=? WHERE seq=?",
                                  (_agora(), seq))

    def marcar(self, seq: int, situacao: str, *, resultado: str = "", erro: str = "") -> None:
        with self.repo.transacao():
            self.repo.con.execute(
                "UPDATE fila_envio SET situacao=?, resultado=?, erro=?, atualizado_em=? WHERE seq=?",
                (situacao, resultado, sanear_texto(erro)[:_LIMITE_ERRO], _agora(), seq))

    def contagem(self) -> dict[str, int]:
        base = {"PENDENTE": 0, "ENVIADO": 0, "CONFLITO": 0, "REJEITADO": 0}
        for situacao, n in self.repo.con.execute("SELECT situacao, COUNT(*) FROM fila_envio GROUP BY situacao"):
            base[situacao] = n
        return base

    def itens(self, situacao: str) -> list[dict]:
        linhas = self.repo.con.execute(
            "SELECT seq, tipo, entidade_id, operacao, tentativas, resultado, erro FROM fila_envio"
            " WHERE situacao=? ORDER BY seq", (situacao,)).fetchall()
        return [dict(zip(("seq", "tipo", "entidade_id", "operacao", "tentativas", "resultado", "erro"), l))
                for l in linhas]
