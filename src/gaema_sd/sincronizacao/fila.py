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

    # ---- conflitos, retenção e deslocamento de versão (reconciliação)

    def conflitos_sem_decisao(self) -> list[dict]:
        linhas = self.repo.con.execute(
            "SELECT seq, tipo, entidade_id, hash_dados, dados FROM fila_envio f WHERE situacao='CONFLITO'"
            " AND NOT EXISTS (SELECT 1 FROM decisoes_conflito d WHERE d.hash_dados = f.hash_dados) ORDER BY seq"
        ).fetchall()
        return [{"seq": l[0], "tipo": l[1], "entidade_id": l[2], "hash_dados": l[3], "dados": json.loads(l[4])}
                for l in linhas]

    def entidades_retidas(self) -> set[tuple[str, str]]:
        """Registros com conflito ainda sem decisão: novos envios deles ficam retidos."""
        return {(c["tipo"], c["entidade_id"]) for c in self.conflitos_sem_decisao()}

    def item_por_hash(self, hash_dados: str) -> dict | None:
        l = self.repo.con.execute(
            "SELECT seq, tipo, entidade_id, dados FROM fila_envio WHERE hash_dados=? ORDER BY seq LIMIT 1",
            (hash_dados,)).fetchone()
        return {"seq": l[0], "tipo": l[1], "entidade_id": l[2], "dados": json.loads(l[3])} if l else None

    def deslocamento(self, tipo: str, entidade_id: str) -> int:
        l = self.repo.con.execute("SELECT deslocamento FROM deslocamento_versao WHERE tipo=? AND entidade_id=?",
                                  (tipo, entidade_id)).fetchone()
        return l[0] if l else 0

    def definir_deslocamento(self, tipo: str, entidade_id: str, valor: int) -> None:
        with self.repo.transacao():
            self.repo.con.execute(
                "INSERT INTO deslocamento_versao (tipo, entidade_id, deslocamento) VALUES (?,?,?)"
                " ON CONFLICT(tipo, entidade_id) DO UPDATE SET deslocamento=excluded.deslocamento",
                (tipo, entidade_id, valor))

    def reajustar_base_pendentes(self, tipo: str, entidade_id: str, delta: int) -> int:
        with self.repo.transacao():
            return self.repo.con.execute(
                "UPDATE fila_envio SET versao_base = versao_base + ?, atualizado_em=? WHERE tipo=? AND entidade_id=?"
                " AND situacao='PENDENTE'", (delta, _agora(), tipo, entidade_id)).rowcount

    def rejeitar_pendentes(self, tipo: str, entidade_id: str, motivo: str) -> int:
        with self.repo.transacao():
            return self.repo.con.execute(
                "UPDATE fila_envio SET situacao='REJEITADO', erro=?, atualizado_em=? WHERE tipo=? AND entidade_id=?"
                " AND situacao='PENDENTE'", (motivo[:_LIMITE_ERRO], _agora(), tipo, entidade_id)).rowcount

    def reenfileirar_rejeitados(self) -> int:
        """Devolve a PENDENTE os itens REJEITADOS por falha operacional. Não reenfileira os descartados por decisão
        do coordenador (conteúdo que a decisão rejeitou)."""
        with self.repo.transacao():
            return self.repo.con.execute(
                "UPDATE fila_envio SET situacao='PENDENTE', tentativas=0, erro='', atualizado_em=?"
                " WHERE situacao='REJEITADO' AND erro NOT LIKE 'descartado:%'", (_agora(),)).rowcount

    def decisao_registrada(self, hash_dados: str) -> bool:
        return self.repo.con.execute("SELECT 1 FROM decisoes_conflito WHERE hash_dados=?",
                                     (hash_dados,)).fetchone() is not None

    def registrar_decisao(self, d, *, aplicada: bool, observacao: str = "") -> None:
        with self.repo.transacao():
            self.repo.con.execute(
                "INSERT OR REPLACE INTO decisoes_conflito (hash_dados, tipo, entidade_id, decisao, motivo,"
                " versao_central, aplicada, observacao, recebida_em) VALUES (?,?,?,?,?,?,?,?,?)",
                (d.hash_dados, d.tipo, d.entidade_id, d.decisao, sanear_texto(d.motivo), d.versao_central,
                 int(aplicada), sanear_texto(observacao)[:_LIMITE_ERRO], _agora()))

    def decisoes(self) -> list[dict]:
        linhas = self.repo.con.execute(
            "SELECT tipo, entidade_id, decisao, versao_central, aplicada, observacao FROM decisoes_conflito"
            " ORDER BY recebida_em, hash_dados").fetchall()
        return [dict(zip(("tipo", "entidade_id", "decisao", "versao_central", "aplicada", "observacao"), l))
                for l in linhas]

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
