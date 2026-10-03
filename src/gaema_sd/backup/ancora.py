"""Âncora externa da trilha de auditoria (mitiga R-19; a GUARDA fora da máquina continua institucional).

Uma âncora é um arquivo pequeno com o número de eventos da trilha e o hash do último. Guardada FORA de onde o banco
e o backup ficam (outro computador, mídia removível, sistema institucional), ela permite descobrir, depois:
- trilha truncada (menos eventos do que a âncora registrou);
- trilha reescrita (o hash no mesmo ponto da cadeia não é o ancorado), mesmo que o atacante recalcule a cadeia
  inteira e refaça o manifesto do backup.

Limite: a âncora não é assinada. Quem controlar também o lugar onde ela está guardada pode trocá-la. Por isso o
valor da âncora depende de a guarda ser feita por quem não controla o banco (PENDENTE: decisão institucional).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ..dominio.entidades import EventoAuditoria
from ..erros import ErroGaema

FORMATO = "gaema-ancora"
VERSAO = 1


def _selo(eventos: int, ultimo_hash: str, criada_em: str) -> str:
    return hashlib.sha256(f"{FORMATO}|{VERSAO}|{eventos}|{ultimo_hash}|{criada_em}".encode("utf-8")).hexdigest()


def gerar_ancora(eventos: Sequence[EventoAuditoria], *, criada_em: datetime | None = None) -> dict:
    if not eventos:
        raise ErroGaema("não há eventos na trilha para ancorar")
    criada = (criada_em or datetime.now(timezone.utc)).isoformat()
    ultimo = eventos[-1]
    return {"formato": FORMATO, "versao": VERSAO, "criada_em": criada, "eventos": len(eventos),
            "ultimo_hash": ultimo.hash_evento, "selo": _selo(len(eventos), ultimo.hash_evento, criada),
            "aviso": "Guarde este arquivo FORA do computador do banco de dados. Não contém dados de registros."}


def escrever_ancora(eventos: Sequence[EventoAuditoria], pasta_destino: str | Path) -> Path:
    """Grava `ancora-<n eventos>.json` na pasta (que deve ficar fora do banco). Não sobrescreve."""
    a = gerar_ancora(eventos)
    pasta = Path(pasta_destino)
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"ancora-{a['eventos']:08d}.json"
    if arq.exists():
        raise ErroGaema(f"{arq.name} já existe; âncora anterior não é sobrescrita")
    arq.write_text(json.dumps(a, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return arq


TAMANHO_MAXIMO = 4096   # bytes; uma âncora tem poucas centenas


def interpretar_ancora(texto: str) -> dict:
    """Confere a forma e o selo de uma âncora recebida como texto (por exemplo, colada na interface)."""
    if len(texto.encode("utf-8")) > TAMANHO_MAXIMO:
        raise ErroGaema("âncora grande demais: não parece uma âncora do GAEMA SD")
    try:
        a = json.loads(texto)
    except ValueError as e:
        raise ErroGaema(f"âncora ilegível: {type(e).__name__}") from e
    eventos = a.get("eventos") if isinstance(a, dict) else None
    ok = (isinstance(a, dict) and a.get("formato") == FORMATO and a.get("versao") == VERSAO
          and isinstance(eventos, int) and not isinstance(eventos, bool) and eventos > 0
          and isinstance(a.get("ultimo_hash"), str) and isinstance(a.get("criada_em"), str)
          and a.get("selo") == _selo(eventos, a["ultimo_hash"], a["criada_em"]))
    if not ok:
        raise ErroGaema("âncora malformada ou com o selo alterado")
    return a


def ler_ancora(arquivo: str | Path) -> dict:
    caminho = Path(arquivo)
    try:
        if not caminho.is_file():
            raise ErroGaema("âncora ilegível: não é um arquivo comum")
        with caminho.open("rb") as f:
            dados = f.read(TAMANHO_MAXIMO + 1)
        texto = dados.decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ErroGaema(f"âncora ilegível: {type(e).__name__}") from e
    return interpretar_ancora(texto)


def conferir_ancora(eventos: Sequence[EventoAuditoria], ancora: dict) -> list[str]:
    """Problemas encontrados ao confrontar a trilha com a âncora (lista vazia = confere)."""
    n = ancora.get("eventos")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        return ["âncora inválida: número de eventos ausente ou menor que 1"]
    if len(eventos) < n:
        return [f"trilha truncada: tem {len(eventos)} eventos e a âncora registrou {n}"]
    no_ponto = eventos[n - 1]
    if no_ponto.sequencia != n or no_ponto.hash_evento != ancora["ultimo_hash"]:
        return [f"trilha reescrita: o evento {n} não tem o hash ancorado"]
    return []
