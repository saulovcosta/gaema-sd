"""Backup lógico, verificação, restauração e rollback.

Um backup é uma pasta com: `gaema.db` (cópia consistente feita pela API de backup do SQLite),
`evidencias/` e `relatorios/` (arquivos), e `manifesto.json` (SHA-256 de cada arquivo, versão do
esquema, contagens e último hash da trilha). `manifesto.sha256` guarda o hash do manifesto.

Limites (ver docs/riscos.md): o manifesto não é assinado; quem controla a pasta inteira pode refazê-lo.
A ancoragem externa do último hash da trilha continua PENDENTE. Restauração e rollback aqui são
operações locais sobre arquivos; não substituem a política de backup da infraestrutura institucional.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..auditoria.trilha import verificar_cadeia
from ..dominio.entidades import EventoAuditoria
from ..dominio.serializacao import de_dict
from ..erros import AuditoriaCorrompida, ErroGaema
from ..persistencia.sqlite import VERSAO_ESQUEMA, Repositorio

FORMATO = 1
BANCO = "gaema.db"
SUBPASTAS = ("evidencias", "relatorios")


class BackupInvalido(ErroGaema):
    pass


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _arquivos(raiz: Path) -> dict[str, Path]:
    achados = {BANCO: raiz / BANCO} if (raiz / BANCO).exists() else {}
    for sub in SUBPASTAS:
        base = raiz / sub
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and not p.name.endswith(".parcial"):
                    achados[p.relative_to(raiz).as_posix()] = p
    return achados


def _resumo_banco(caminho: Path) -> dict:
    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BackupInvalido("banco do backup não passou na checagem de integridade")
        versao = con.execute("PRAGMA user_version").fetchone()[0]
        contagens = dict(con.execute("SELECT tipo, COUNT(*) FROM registros GROUP BY tipo"))
        eventos = [de_dict(EventoAuditoria, json.loads(l[0]))
                   for l in con.execute("SELECT dados FROM auditoria ORDER BY sequencia")]
    finally:
        con.close()
    return {"versao_esquema": versao, "contagens": contagens, "eventos": eventos}


def criar_backup(repo: Repositorio, saida: str | Path, destino: str | Path) -> dict:
    """Cria o backup em `destino` (pasta nova ou vazia). Devolve o manifesto."""
    saida, destino = Path(saida), Path(destino)
    if destino.exists() and any(destino.iterdir()):
        raise ErroGaema("pasta de backup precisa estar vazia; backup anterior não é sobrescrito")
    destino.mkdir(parents=True, exist_ok=True)
    alvo = sqlite3.connect(destino / BANCO)
    try:
        repo.con.backup(alvo)  # cópia consistente, mesmo com outras conexões escrevendo
        alvo.execute("PRAGMA journal_mode = DELETE")  # backup é um arquivo único, sem -wal/-shm
    finally:
        alvo.close()
    # banco primeiro, arquivos depois: todo arquivo citado no banco já existe (o arquivo é gravado antes do registro)
    for sub in SUBPASTAS:
        origem = saida / sub
        if origem.is_dir():
            for p in origem.rglob("*"):
                if p.is_file() and not p.name.endswith(".parcial"):
                    alvo_p = destino / p.relative_to(saida)
                    alvo_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, alvo_p)
    resumo = _resumo_banco(destino / BANCO)
    eventos = resumo["eventos"]
    manifesto = {
        "formato": FORMATO,
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "versao_esquema": resumo["versao_esquema"],
        "contagens": resumo["contagens"],
        "auditoria": {"eventos": len(eventos), "ultimo_hash": eventos[-1].hash_evento if eventos else ""},
        "arquivos": {rel: {"sha256": _sha256(p), "bytes": p.stat().st_size}
                     for rel, p in _arquivos(destino).items()},
    }
    texto = json.dumps(manifesto, ensure_ascii=False, sort_keys=True, indent=2)
    (destino / "manifesto.json").write_text(texto, encoding="utf-8")
    (destino / "manifesto.sha256").write_text(hashlib.sha256(texto.encode("utf-8")).hexdigest(), encoding="utf-8")
    return manifesto


def verificar_backup(pasta: str | Path) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = backup confere)."""
    pasta = Path(pasta)
    problemas: list[str] = []
    try:
        texto = (pasta / "manifesto.json").read_text(encoding="utf-8")
        esperado = (pasta / "manifesto.sha256").read_text(encoding="utf-8").strip()
    except OSError:
        return ["manifesto ausente"]
    if hashlib.sha256(texto.encode("utf-8")).hexdigest() != esperado:
        return ["manifesto alterado (hash não confere)"]
    manifesto = json.loads(texto)
    if manifesto.get("formato") != FORMATO:
        return [f"formato de backup {manifesto.get('formato')} não suportado"]
    if manifesto["versao_esquema"] > VERSAO_ESQUEMA:
        problemas.append(f"esquema {manifesto['versao_esquema']} é mais novo que o do código ({VERSAO_ESQUEMA})")
    presentes = _arquivos(pasta)
    for rel, info in manifesto["arquivos"].items():
        if rel not in presentes:
            problemas.append(f"arquivo ausente: {rel}")
        elif _sha256(presentes[rel]) != info["sha256"]:
            problemas.append(f"arquivo alterado: {rel}")
    for rel in presentes.keys() - manifesto["arquivos"].keys():
        problemas.append(f"arquivo fora do manifesto: {rel}")
    if BANCO in presentes and not any(p.startswith("arquivo alterado: " + BANCO) for p in problemas):
        try:
            resumo = _resumo_banco(pasta / BANCO)
            if resumo["contagens"] != manifesto["contagens"]:
                problemas.append("contagens do banco diferem do manifesto")
            verificar_cadeia(resumo["eventos"])
            if resumo["eventos"] and resumo["eventos"][-1].hash_evento != manifesto["auditoria"]["ultimo_hash"]:
                problemas.append("último hash da trilha difere do manifesto")
        except AuditoriaCorrompida as e:
            problemas.append(f"trilha de auditoria corrompida: {e}")
        except (BackupInvalido, sqlite3.DatabaseError) as e:
            problemas.append(f"banco do backup inválido: {e}")
    return problemas


def restaurar_backup(pasta_backup: str | Path, destino_db: str | Path, destino_saida: str | Path) -> dict:
    """Restaura para caminhos que ainda não existem. Verifica antes de copiar e confere depois."""
    pasta_backup, destino_db, destino_saida = Path(pasta_backup), Path(destino_db), Path(destino_saida)
    problemas = verificar_backup(pasta_backup)
    if problemas:
        raise BackupInvalido("backup não confere; nada foi restaurado: " + "; ".join(problemas))
    if destino_db.exists() or destino_saida.exists():
        raise ErroGaema("destino já existe; restauração não sobrescreve (use rollback para trocar com cópia de segurança)")
    destino_saida.mkdir(parents=True)
    destino_db.parent.mkdir(parents=True, exist_ok=True)
    try:
        for rel in _arquivos(pasta_backup):
            if rel == BANCO:
                shutil.copy2(pasta_backup / rel, destino_db)
            else:
                alvo = destino_saida / rel
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pasta_backup / rel, alvo)
        resumo = _resumo_banco(destino_db)
        verificar_cadeia(resumo["eventos"])
    except BaseException:
        shutil.rmtree(destino_saida, ignore_errors=True)
        destino_db.unlink(missing_ok=True)
        raise
    return {"contagens": resumo["contagens"], "eventos_auditoria": len(resumo["eventos"])}


def rollback(pasta_backup: str | Path, db_atual: str | Path, saida_atual: str | Path) -> Path:
    """Volta ao estado do backup. O estado atual NÃO é apagado: vai para `<saida>.descartado-<hora>`.
    Feche o Repositorio antes (o arquivo não pode estar em uso)."""
    pasta_backup, db_atual, saida_atual = Path(pasta_backup), Path(db_atual), Path(saida_atual)
    problemas = verificar_backup(pasta_backup)
    if problemas:
        raise BackupInvalido("backup não confere; rollback não executado: " + "; ".join(problemas))
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    guarda = saida_atual.with_name(f"{saida_atual.name}.descartado-{carimbo}")
    guarda.mkdir(parents=True)
    movidos: list[tuple[Path, Path]] = []
    try:
        for origem in (db_atual, Path(str(db_atual) + "-wal"), Path(str(db_atual) + "-shm")):
            if origem.exists():
                shutil.move(str(origem), guarda / origem.name)
                movidos.append((guarda / origem.name, origem))
        if saida_atual.exists():
            shutil.move(str(saida_atual), guarda / "saida")
            movidos.append((guarda / "saida", saida_atual))
        restaurar_backup(pasta_backup, db_atual, saida_atual)
    except BaseException:
        for de, para in reversed(movidos):  # desfaz: o estado anterior volta ao lugar
            if para.exists():
                shutil.rmtree(para, ignore_errors=True) if para.is_dir() else para.unlink()
            shutil.move(str(de), str(para))
        raise
    return guarda
