"""Backup lógico, verificação, restauração e rollback.

Um backup é uma pasta com: `gaema.db` (cópia consistente feita pela API de backup do SQLite),
`evidencias/` e `relatorios/` (arquivos), e `manifesto.json` (SHA-256 de cada arquivo, versão do
esquema, contagens e último hash da trilha). `manifesto.sha256` guarda o hash do manifesto.

A verificação NÃO confia só no manifesto: confere também, contra o próprio banco do backup, o hash de cada
evidência e de cada relatório registrados, as contagens, a cadeia da trilha de auditoria e a lista fechada de
arquivos (sem links simbólicos nem arquivos de fora do formato).

Limites (ver docs/riscos.md): o manifesto não é assinado. Quem controla a pasta inteira pode trocar o banco e
refazer o manifesto, e pode truncar os últimos eventos da trilha. A ancoragem externa do último hash segue
PENDENTE. Restauração e rollback são operações locais sobre arquivos; não substituem a política de backup da
infraestrutura institucional.
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
from .ancora import conferir_ancora

FORMATO = 1
BANCO = "gaema.db"
SUBPASTAS = ("evidencias", "relatorios")
FIXOS = (BANCO, "manifesto.json", "manifesto.sha256")


class BackupInvalido(ErroGaema):
    pass


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _arquivos(raiz: Path) -> dict[str, Path]:
    """Arquivos do formato (banco, evidências, relatórios). Links simbólicos nunca entram."""
    achados = {BANCO: raiz / BANCO} if (raiz / BANCO).is_file() and not (raiz / BANCO).is_symlink() else {}
    for sub in SUBPASTAS:
        base = raiz / sub
        if base.is_dir() and not base.is_symlink():
            for p in sorted(base.rglob("*")):
                if p.is_file() and not p.is_symlink() and not p.name.endswith(".parcial"):
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
        evidencias = [json.loads(l[0]) for l in con.execute("SELECT dados FROM registros WHERE tipo='Evidencia'")]
        relatorios = [json.loads(l[0]) for l in con.execute("SELECT dados FROM registros WHERE tipo='Relatorio'")]
        tem_conflitos = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='conflitos_sincronizacao'").fetchone()
        conflitos = dict(con.execute("SELECT situacao, COUNT(*) FROM conflitos_sincronizacao GROUP BY situacao")) \
            if tem_conflitos else {}
    finally:
        con.close()
    return {"versao_esquema": versao, "contagens": contagens, "eventos": eventos, "evidencias": evidencias,
            "relatorios": relatorios, "conflitos": conflitos}


def _arquivo_de_relatorio(r: dict) -> str:
    miolo = "".join(c for c in r["demanda_id"] if c in "0123456789abcdefABCDEF")[:8]
    return f"relatorios/relatorio-{miolo}-v{r['numero_versao']}.{r['formato'].lower()}"


def _conferir_arquivos_do_banco(resumo: dict, presentes: dict[str, Path]) -> list[str]:
    """Cada evidência e cada relatório registrados no BANCO precisam existir com o hash registrado."""
    problemas = []
    for ev in resumo["evidencias"]:
        rel = f"evidencias/{ev['sha256']}"
        if rel not in presentes:
            problemas.append(f"evidência {ev['id'][:8]}: arquivo ausente no backup")
        elif _sha256(presentes[rel]) != ev["sha256"]:
            problemas.append(f"evidência {ev['id'][:8]}: arquivo não confere com o hash registrado no banco")
    for r in resumo["relatorios"]:
        rel = _arquivo_de_relatorio(r)
        if rel not in presentes:
            problemas.append(f"relatório {r['id'][:8]} (v{r['numero_versao']}): arquivo ausente no backup")
        elif _sha256(presentes[rel]) != r["hash_conteudo"]:
            problemas.append(f"relatório {r['id'][:8]} (v{r['numero_versao']}): arquivo não confere com o hash "
                             "registrado no banco")
    return problemas


def _forma_do_manifesto(m) -> list[str]:
    ok = (isinstance(m, dict) and m.get("formato") == FORMATO and isinstance(m.get("versao_esquema"), int)
          and isinstance(m.get("contagens"), dict) and isinstance(m.get("auditoria"), dict)
          and isinstance(m["auditoria"].get("eventos"), int) and isinstance(m["auditoria"].get("ultimo_hash"), str)
          and isinstance(m.get("arquivos"), dict)
          and all(isinstance(v, dict) and isinstance(v.get("sha256"), str) for v in m["arquivos"].values()))
    if not ok:
        formato = m.get("formato") if isinstance(m, dict) else None
        if isinstance(m, dict) and formato not in (None, FORMATO):
            return [f"formato de backup {formato} não suportado"]
        return ["manifesto incompleto ou fora do formato"]
    return []


def criar_backup(repo: Repositorio, saida: str | Path, destino: str | Path) -> dict:
    """Cria o backup em `destino` (pasta nova ou vazia) e o verifica antes de devolver. Se não conferir (por exemplo,
    `saida` errada, sem os arquivos que o banco cita), o backup incompleto é removido e o erro é levantado."""
    saida, destino = Path(saida), Path(destino)
    if destino.exists() and any(destino.iterdir()):
        raise ErroGaema("pasta de backup precisa estar vazia; backup anterior não é sobrescrito")
    existia = destino.exists()
    destino.mkdir(parents=True, exist_ok=True)
    try:
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
                    if p.is_file() and not p.is_symlink() and not p.name.endswith(".parcial"):
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
            "sincronizacao": {"conflitos": resumo["conflitos"]},
            "auditoria": {"eventos": len(eventos), "ultimo_hash": eventos[-1].hash_evento if eventos else ""},
            "arquivos": {rel: {"sha256": _sha256(p), "bytes": p.stat().st_size}
                         for rel, p in _arquivos(destino).items()},
        }
        texto = json.dumps(manifesto, ensure_ascii=False, sort_keys=True, indent=2)
        (destino / "manifesto.json").write_text(texto, encoding="utf-8")
        (destino / "manifesto.sha256").write_text(hashlib.sha256(texto.encode("utf-8")).hexdigest(),
                                                  encoding="utf-8")
        problemas = verificar_backup(destino)
        if problemas:
            raise BackupInvalido("o backup criado não confere (a pasta de saída está certa?): " + "; ".join(problemas))
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)
        if existia:
            destino.mkdir(parents=True, exist_ok=True)
        raise
    return manifesto


def verificar_backup(pasta: str | Path, ancora: dict | None = None) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = backup confere). Nunca levanta por manifesto malformado.
    Com `ancora` (guardada fora), confronta também a trilha do backup com ela."""
    pasta = Path(pasta)
    try:
        texto = (pasta / "manifesto.json").read_text(encoding="utf-8")
        esperado = (pasta / "manifesto.sha256").read_text(encoding="utf-8").strip()
    except OSError:
        return ["manifesto ausente"]
    if hashlib.sha256(texto.encode("utf-8")).hexdigest() != esperado:
        return ["manifesto alterado (hash não confere)"]
    try:
        manifesto = json.loads(texto)
    except ValueError:
        return ["manifesto ilegível"]
    forma = _forma_do_manifesto(manifesto)
    if forma:
        return forma
    problemas: list[str] = []
    if manifesto["versao_esquema"] > VERSAO_ESQUEMA:
        problemas.append(f"esquema {manifesto['versao_esquema']} é mais novo que o do código ({VERSAO_ESQUEMA})")
    # lista fechada: nada de link simbólico nem de arquivo fora do formato (inclui -wal/-shm órfãos)
    for p in sorted(pasta.rglob("*")):
        rel = p.relative_to(pasta).as_posix()
        if p.is_symlink():
            problemas.append(f"link simbólico não permitido: {rel}")
        elif p.is_file() and rel not in FIXOS and not rel.startswith(("evidencias/", "relatorios/")):
            problemas.append(f"arquivo fora do formato de backup: {rel}")
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
            eventos = resumo["eventos"]
            verificar_cadeia(eventos)
            if ancora is not None:
                problemas += conferir_ancora(eventos, ancora)
            if len(eventos) != manifesto["auditoria"]["eventos"]:
                problemas.append("número de eventos da trilha difere do manifesto")
            if eventos and eventos[-1].hash_evento != manifesto["auditoria"]["ultimo_hash"]:
                problemas.append("último hash da trilha difere do manifesto")
            sinc = manifesto.get("sincronizacao")
            if isinstance(sinc, dict) and sinc.get("conflitos") != resumo["conflitos"]:
                problemas.append("conflitos de sincronização do banco diferem do manifesto")
            problemas += _conferir_arquivos_do_banco(resumo, presentes)
        except AuditoriaCorrompida as e:
            problemas.append(f"trilha de auditoria corrompida: {e}")
        except (BackupInvalido, sqlite3.DatabaseError, KeyError, ValueError) as e:
            problemas.append(f"banco do backup inválido: {type(e).__name__}")
    elif BANCO not in presentes:
        problemas.append("banco ausente do backup")
    return problemas


def restaurar_backup(pasta_backup: str | Path, destino_db: str | Path, destino_saida: str | Path) -> dict:
    """Restaura para caminhos que ainda não existem. Verifica antes de copiar e confere depois."""
    pasta_backup, destino_db, destino_saida = Path(pasta_backup), Path(destino_db), Path(destino_saida)
    problemas = verificar_backup(pasta_backup)
    if problemas:
        raise BackupInvalido("backup não confere; nada foi restaurado: " + "; ".join(problemas))
    if destino_db.exists() or destino_saida.exists():
        raise ErroGaema("destino já existe; restauração não sobrescreve (use rollback para trocar com cópia de segurança)")
    for sobra in (Path(str(destino_db) + "-wal"), Path(str(destino_db) + "-shm")):
        if sobra.exists():
            raise ErroGaema(f"há um arquivo {sobra.name} órfão no destino; remova-o ou escolha outro destino "
                            "(ele corromperia o banco restaurado)")
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
        if _conferir_arquivos_do_banco(resumo, _arquivos_restaurados(destino_saida)):
            raise BackupInvalido("arquivos restaurados não conferem com o banco restaurado")
    except BaseException:
        shutil.rmtree(destino_saida, ignore_errors=True)
        destino_db.unlink(missing_ok=True)
        raise
    return {"contagens": resumo["contagens"], "eventos_auditoria": len(resumo["eventos"])}


def _arquivos_restaurados(saida: Path) -> dict[str, Path]:
    return {rel: p for rel, p in _arquivos(saida).items() if rel != BANCO}


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
