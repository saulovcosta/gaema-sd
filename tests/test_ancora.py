"""R-19: âncora externa da trilha. Detecta o que o manifesto sozinho não detecta. A GUARDA da âncora é institucional."""

import dataclasses
import hashlib
import json
import shutil
import sqlite3
import sys

import pytest

from gaema_sd.auditoria.trilha import calcular_hash
from gaema_sd.backup import (BackupInvalido, conferir_ancora, criar_backup, escrever_ancora, gerar_ancora, ler_ancora,
                             verificar_backup)
from gaema_sd.dominio.entidades import EventoAuditoria
from gaema_sd.dominio.serializacao import de_dict, para_dict
from gaema_sd.erros import AcessoNegado, AuditoriaCorrompida, ErroGaema

from .test_backup import sistema  # noqa: F401  (fixture)
from .test_regressao_revisao_f4f5_b import _refazer


@pytest.fixture
def auditor():
    from gaema_sd.acesso import Ator
    from gaema_sd.dominio.enums import Papel
    return Ator.de("usuario-sintetico-06", Papel.AUDITOR)


def test_ancora_nao_leva_dados_de_registros_e_tem_selo(sistema, auditor):
    n, _, _, tmp = sistema
    a = n.gerar_ancora(auditor)
    assert set(a) == {"formato", "versao", "criada_em", "eventos", "ultimo_hash", "selo", "aviso"}
    assert a["eventos"] == len(n.trilha.eventos) and a["ultimo_hash"] == n.trilha.eventos[-1].hash_evento
    arq = escrever_ancora(n.trilha.eventos, tmp / "externo")
    assert ler_ancora(arq)["ultimo_hash"] == a["ultimo_hash"]
    with pytest.raises(ErroGaema, match="não é sobrescrita"):
        escrever_ancora(n.trilha.eventos, tmp / "externo")


def test_so_auditor_ou_administrador_gera_ancora(sistema):
    from gaema_sd.acesso import Ator
    from gaema_sd.dominio.enums import Papel
    n, *_ = sistema
    with pytest.raises(AcessoNegado):
        n.gerar_ancora(Ator.de("usuario-sintetico-02", Papel.TECNICO_CAMPO))


def test_ancora_alterada_ou_malformada_e_recusada(sistema, tmp_path, auditor):
    n, *_ = sistema
    a = n.gerar_ancora(auditor)
    f = tmp_path / "a.json"
    for ruim in ({**a, "ultimo_hash": "0" * 64}, {**a, "eventos": a["eventos"] + 1}, {"formato": "outro"}):
        f.write_text(json.dumps(ruim), encoding="utf-8")
        with pytest.raises(ErroGaema, match="malformada|selo"):
            ler_ancora(f)
    f.write_text("isto não é json", encoding="utf-8")
    with pytest.raises(ErroGaema, match="ilegível"):
        ler_ancora(f)


def test_trilha_que_so_cresceu_confere_com_a_ancora_antiga(sistema, auditor, atores, cenario):
    n, _, saida, tmp = sistema
    a = n.gerar_ancora(auditor)
    n.registrar(atores["tecnico"], cenario["MedicaoPenetracao"][0])           # a trilha cresce depois da âncora
    assert n.verificar_auditoria(auditor, a) == len(n.trilha.eventos)
    criar_backup(n.repo, saida, tmp / "bk")
    assert verificar_backup(tmp / "bk", a) == []


def _reescrever_trilha(banco, a_partir_de, novo_motivo="trilha reescrita pelo atacante"):
    """Atacante com acesso ao banco: altera um evento e RECALCULA a cadeia inteira dali em diante."""
    con = sqlite3.connect(banco)
    con.execute("DROP TRIGGER auditoria_sem_update")
    eventos = [de_dict(EventoAuditoria, json.loads(l[0])) for l in con.execute("SELECT dados FROM auditoria ORDER BY sequencia")]
    anterior = eventos[a_partir_de - 2].hash_evento if a_partir_de > 1 else "0" * 64
    for i in range(a_partir_de - 1, len(eventos)):
        ev = dataclasses.replace(eventos[i], hash_anterior=anterior, motivo=novo_motivo if i == a_partir_de - 1 else eventos[i].motivo)
        ev = dataclasses.replace(ev, hash_evento=calcular_hash(ev))
        anterior = ev.hash_evento
        con.execute("UPDATE auditoria SET dados=?, hash_evento=? WHERE sequencia=?",
                    (json.dumps(para_dict(ev), ensure_ascii=False), ev.hash_evento, ev.sequencia))
    con.commit(); con.close()


def test_trilha_reescrita_com_cadeia_recalculada_e_manifesto_refeito_so_a_ancora_denuncia(sistema, auditor):
    n, _, saida, tmp = sistema
    a = n.gerar_ancora(auditor)
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    ruim = tmp / "ruim"
    shutil.copytree(tmp / "bk", ruim)
    _reescrever_trilha(ruim / "gaema.db", a_partir_de=3)
    _refazer(ruim, lambda m: m["auditoria"].update(
        {"ultimo_hash": json.loads(sqlite3.connect(ruim / "gaema.db").execute(
            "SELECT dados FROM auditoria ORDER BY sequencia DESC LIMIT 1").fetchone()[0])["hash_evento"]}))
    assert verificar_backup(ruim) == []          # sem âncora, o ataque passa (é o limite do manifesto)
    assert any("reescrita" in p for p in verificar_backup(ruim, a))


def test_trilha_truncada_com_manifesto_refeito_so_a_ancora_denuncia(sistema, auditor):
    n, _, saida, tmp = sistema
    a = n.gerar_ancora(auditor)
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    ruim = tmp / "ruim"
    shutil.copytree(tmp / "bk", ruim)
    con = sqlite3.connect(ruim / "gaema.db")
    con.execute("DROP TRIGGER auditoria_sem_delete")
    con.execute("DELETE FROM auditoria WHERE sequencia > ?", (a["eventos"] - 3,))
    con.commit()
    ultimo = json.loads(con.execute("SELECT dados FROM auditoria ORDER BY sequencia DESC LIMIT 1").fetchone()[0])
    con.close()
    _refazer(ruim, lambda m: m["auditoria"].update({"eventos": a["eventos"] - 3, "ultimo_hash": ultimo["hash_evento"]}))
    assert verificar_backup(ruim) == []          # sem âncora, a truncagem passa
    assert any("truncada" in p for p in verificar_backup(ruim, a))


def test_verificar_auditoria_com_ancora_levanta_quando_nao_confere(sistema, auditor):
    n, *_ = sistema
    a = n.gerar_ancora(auditor)
    falsa = {**a, "ultimo_hash": "f" * 64}
    with pytest.raises(AuditoriaCorrompida, match="reescrita"):
        n.verificar_auditoria(auditor, falsa)


def test_cli_ancorar_e_verificar_com_ancora(sistema, monkeypatch, capsys, auditor):
    from gaema_sd.backup.__main__ import main
    n, banco, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    monkeypatch.setattr(sys, "argv", ["x", "ancorar", str(banco), str(tmp / "pen_drive")])
    assert main() == 0
    (arq,) = (tmp / "pen_drive").glob("ancora-*.json")
    monkeypatch.setattr(sys, "argv", ["x", "verificar", str(tmp / "bk"), "--ancora", str(arq)])
    assert main() == 0 and "backup confere" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["x", "ancorar", str(tmp / "nao_existe.db"), str(tmp / "outro")])
    assert main() == 2
