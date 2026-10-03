"""Trilha de auditoria append-only, encadeada por hash.

Cada evento guarda o hash do anterior; alterar ou remover um evento quebra a cadeia.
Limitação: protege contra adulteração não detectada dentro da trilha, mas quem
controla o banco inteiro pode recalcular a cadeia. Ancoragem externa do último
hash (ex.: registro periódico em sistema institucional) fica PENDENTE.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from ..acesso.politica import Ator
from ..dominio.entidades import EventoAuditoria
from ..dominio.serializacao import json_canonico, para_dict, sha256_texto
from ..erros import AuditoriaCorrompida

GENESE = "0" * 64
# casa a palavra (ou o prefixo/sufixo separado por _ ou -), não pedaço de palavra: "margem" não é "rg"
_CHAVES_SENSIVEIS = re.compile(r"(?<![a-z0-9])(cpf|cnpj|rg|nome|email|e-mail|telefone|endereco|senha|token|chave_api|"
                               r"segredo)(?![a-z0-9])", re.IGNORECASE)
_TAMANHO_MAX_TEXTO = 200
_CPF = re.compile(r"(?<![\w])(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-/.\s]?\d{2})(?![\w])")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_SEGREDO = re.compile(r"(?i)\b(senha|token|chave_api|segredo|cpf|cnpj)\b(\s*[=:]\s*)\S+")


def sanear_texto(texto: str) -> str:
    """Mascara alguns formatos de CPF (com ou sem pontuação), e-mail e 'senha=...'. Higiene de log, não garantia:
    não cobre CNPJ nem telefone com máscara, e nome de pessoa em texto livre não é detectável por padrão; por isso o
    log não carrega texto livre de usuário."""
    texto = _SEGREDO.sub(lambda m: f"{m.group(1)}{m.group(2)}[REMOVIDO]", texto)
    texto = _CPF.sub("[REMOVIDO]", texto)
    return _EMAIL.sub("[REMOVIDO]", texto)


def sanear_detalhes(detalhes: Optional[dict]) -> dict:
    """Remove chaves sensíveis e encurta textos longos (logs sem excesso de dados)."""
    limpo = {}
    for k, v in (detalhes or {}).items():
        if _CHAVES_SENSIVEIS.search(str(k)):
            limpo[k] = "[REMOVIDO]"
        elif isinstance(v, str):
            v = sanear_texto(v)
            limpo[k] = v[:_TAMANHO_MAX_TEXTO] + "…" if len(v) > _TAMANHO_MAX_TEXTO else v
        elif isinstance(v, (int, float, bool)) or v is None:
            limpo[k] = v
        else:
            limpo[k] = sanear_texto(str(v))[:_TAMANHO_MAX_TEXTO]
    return limpo


def calcular_hash(ev: EventoAuditoria) -> str:
    dados = {k: v for k, v in para_dict(ev).items() if k != "hash_evento"}
    return sha256_texto(json_canonico(dados))


class ArmazenamentoMemoria:
    """Guarda eventos em lista. O repositório SQLite oferece a mesma interface."""

    def __init__(self, eventos: Iterable[EventoAuditoria] = ()):
        self._eventos = list(eventos)

    def ultimo(self) -> Optional[EventoAuditoria]:
        return self._eventos[-1] if self._eventos else None

    def anexar(self, ev: EventoAuditoria) -> None:
        self._eventos.append(ev)

    def todos(self) -> list[EventoAuditoria]:
        return list(self._eventos)


class TrilhaAuditoria:
    """Registra e verifica eventos. Só acrescenta; não há operação de alterar ou apagar."""

    def __init__(self, armazenamento=None):
        self._arm = armazenamento if armazenamento is not None else ArmazenamentoMemoria()

    @property
    def eventos(self) -> tuple[EventoAuditoria, ...]:
        return tuple(self._arm.todos())

    def ultimo_evento(self) -> Optional[EventoAuditoria]:
        return self._arm.ultimo()

    def registrar(self, ator: Ator, acao: str, entidade: str, entidade_id: str, *,
                  estado_origem: str | None = None, estado_destino: str | None = None,
                  motivo: str = "", detalhes: dict | None = None,
                  ocorrido_em: datetime | None = None) -> EventoAuditoria:
        anterior = self._arm.ultimo()
        provisorio = EventoAuditoria(
            sequencia=(anterior.sequencia + 1) if anterior else 1,
            ocorrido_em=ocorrido_em or datetime.now(timezone.utc),
            ator_id=ator.id,
            papeis=tuple(sorted(p.value for p in ator.papeis)),
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            estado_origem=estado_origem,
            estado_destino=estado_destino,
            motivo=sanear_texto(motivo),
            detalhes=sanear_detalhes(detalhes),
            hash_anterior=anterior.hash_evento if anterior else GENESE,
            hash_evento="",
        )
        ev = dataclasses.replace(provisorio, hash_evento=calcular_hash(provisorio))
        self._arm.anexar(ev)
        return ev

    def verificar(self) -> int:
        """Confere a cadeia inteira. Devolve o nº de eventos ou levanta AuditoriaCorrompida."""
        return verificar_cadeia(self._arm.todos())


def verificar_cadeia(eventos: Iterable[EventoAuditoria]) -> int:
    anterior_hash, esperado_seq, n = GENESE, 1, 0
    for ev in eventos:
        if ev.sequencia != esperado_seq:
            raise AuditoriaCorrompida(f"sequência {ev.sequencia} fora de ordem (esperado {esperado_seq})")
        if ev.hash_anterior != anterior_hash:
            raise AuditoriaCorrompida(f"evento {ev.sequencia}: elo com o anterior rompido")
        if calcular_hash(ev) != ev.hash_evento:
            raise AuditoriaCorrompida(f"evento {ev.sequencia}: conteúdo alterado")
        anterior_hash, esperado_seq, n = ev.hash_evento, esperado_seq + 1, n + 1
    return n
