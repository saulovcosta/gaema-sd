"""Backup lógico, restauração testável e rollback (Fase 4). Só dados sintéticos, só arquivos locais."""

import json
import shutil
import sqlite3

import pytest

from gaema_sd.backup import BackupInvalido, criar_backup, restaurar_backup, rollback, verificar_backup
from gaema_sd.dominio import entidades as E
from gaema_sd.erros import ErroGaema
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio
from gaema_sd.persistencia.sqlite import VERSAO_ESQUEMA
from gaema_sd.sinteticos import FOTO_SINTETICA

from .apoio_sincronizacao import preparar_central


@pytest.fixture
def sistema(tmp_path, atores, cenario):
    """Núcleo em arquivo, com fluxo até EM_CAMPO, ponto, observação e uma foto guardada."""
    banco, saida = tmp_path / "vivo" / "gaema.db", tmp_path / "vivo" / "saida"
    banco.parent.mkdir()
    n = Nucleo(Repositorio(str(banco)), saida)
    preparar_central(n, atores, cenario)
    n.registrar(atores["tecnico"], cenario["PontoAmostral"][0])
    n.registrar(atores["tecnico"], cenario["Observacao"][0])
    n.registrar_evidencia(atores["tecnico"], cenario["Evidencia"][0], FOTO_SINTETICA)
    yield n, banco, saida, tmp_path
    try:
        n.repo.fechar()
    except sqlite3.ProgrammingError:
        pass


def test_backup_confere_e_restaura_estado_identico(sistema, atores):
    n, banco, saida, tmp = sistema
    manifesto = criar_backup(n.repo, saida, tmp / "bk1")
    assert verificar_backup(tmp / "bk1") == []
    assert manifesto["auditoria"]["eventos"] == len(n.trilha.eventos)
    assert manifesto["versao_esquema"] == VERSAO_ESQUEMA
    n.repo.fechar()

    relatorio = restaurar_backup(tmp / "bk1", tmp / "novo" / "gaema.db", tmp / "novo" / "saida")
    assert relatorio["contagens"]["Evidencia"] == 1
    n2 = Nucleo(Repositorio(str(tmp / "novo" / "gaema.db")), tmp / "novo" / "saida")
    assert n2.verificar_auditoria(atores["auditor"]) == manifesto["auditoria"]["eventos"]
    (ev,) = n2.repo.listar(E.Evidencia)
    assert n2.verificar_evidencia(atores["tecnico"], ev.id)  # arquivo restaurado confere com o hash
    n2.repo.fechar()


def test_backup_nao_sobrescreve_backup_anterior(sistema):
    n, _, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    with pytest.raises(ErroGaema, match="vazia"):
        criar_backup(n.repo, saida, tmp / "bk")


def test_backup_adulterado_e_recusado_em_cada_ponto(sistema):
    n, _, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()

    # 1) arquivo de evidência trocado
    ruim = tmp / "bk-ev"; shutil.copytree(tmp / "bk", ruim)
    foto = next((ruim / "evidencias").iterdir()); foto.write_bytes(b"outra coisa")
    assert any("arquivo alterado" in p for p in verificar_backup(ruim))
    # 2) arquivo apagado
    ruim = tmp / "bk-apagado"; shutil.copytree(tmp / "bk", ruim)
    next((ruim / "evidencias").iterdir()).unlink()
    assert any("arquivo ausente" in p for p in verificar_backup(ruim))
    # 3) arquivo extra
    ruim = tmp / "bk-extra"; shutil.copytree(tmp / "bk", ruim)
    (ruim / "relatorios").mkdir(); (ruim / "relatorios" / "intruso.html").write_text("x")
    assert any("fora do manifesto" in p for p in verificar_backup(ruim))
    # 4) manifesto reescrito sem refazer o hash
    ruim = tmp / "bk-manifesto"; shutil.copytree(tmp / "bk", ruim)
    m = json.loads((ruim / "manifesto.json").read_text()); m["contagens"]["Evidencia"] = 9
    (ruim / "manifesto.json").write_text(json.dumps(m))
    assert verificar_backup(ruim) == ["manifesto alterado (hash não confere)"]
    # 5) manifesto ausente
    ruim = tmp / "bk-sem"; shutil.copytree(tmp / "bk", ruim); (ruim / "manifesto.json").unlink()
    assert verificar_backup(ruim) == ["manifesto ausente"]


def test_trilha_adulterada_dentro_do_banco_do_backup_e_detectada(sistema):
    n, _, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    ruim = tmp / "bk-trilha"; shutil.copytree(tmp / "bk", ruim)
    con = sqlite3.connect(ruim / "gaema.db")
    con.execute("DROP TRIGGER auditoria_sem_update")
    con.execute("UPDATE auditoria SET dados = replace(dados, 'CRIAR', 'ATUALIZAR') WHERE sequencia = 1")
    con.commit(); con.close()
    problemas = verificar_backup(ruim)  # o hash do arquivo do banco muda: pego antes mesmo da cadeia
    assert any("arquivo alterado: gaema.db" in p for p in problemas)
    # refazendo o manifesto (atacante com acesso à pasta), a cadeia da trilha ainda denuncia
    import hashlib
    m = json.loads((ruim / "manifesto.json").read_text())
    m["arquivos"]["gaema.db"]["sha256"] = hashlib.sha256((ruim / "gaema.db").read_bytes()).hexdigest()
    texto = json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2)
    (ruim / "manifesto.json").write_text(texto)
    (ruim / "manifesto.sha256").write_text(hashlib.sha256(texto.encode()).hexdigest())
    assert any("trilha de auditoria corrompida" in p for p in verificar_backup(ruim))


def test_restauracao_recusa_backup_invalido_e_destino_existente(sistema):
    n, _, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    ruim = tmp / "bk-ruim"; shutil.copytree(tmp / "bk", ruim)
    next((ruim / "evidencias").iterdir()).write_bytes(b"x")
    with pytest.raises(BackupInvalido):
        restaurar_backup(ruim, tmp / "r1.db", tmp / "r1")
    assert not (tmp / "r1.db").exists() and not (tmp / "r1").exists()  # nada restaurado pela metade
    (tmp / "r2").mkdir()
    with pytest.raises(ErroGaema, match="não sobrescreve"):
        restaurar_backup(tmp / "bk", tmp / "r2.db", tmp / "r2")


def test_backup_de_esquema_mais_novo_que_o_codigo_e_recusado(sistema):
    import hashlib
    n, _, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    m = json.loads((tmp / "bk" / "manifesto.json").read_text()); m["versao_esquema"] = VERSAO_ESQUEMA + 1
    texto = json.dumps(m, ensure_ascii=False, sort_keys=True, indent=2)
    (tmp / "bk" / "manifesto.json").write_text(texto)
    (tmp / "bk" / "manifesto.sha256").write_text(hashlib.sha256(texto.encode()).hexdigest())
    assert any("mais novo" in p for p in verificar_backup(tmp / "bk"))


def test_rollback_volta_ao_backup_e_guarda_o_estado_descartado(sistema, atores, cenario):
    n, banco, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    # operação posterior ao backup que se quer desfazer
    n.registrar(atores["tecnico"], cenario["MedicaoPenetracao"][0])
    assert len(n.repo.listar(E.MedicaoPenetracao)) == 1
    n.repo.fechar()

    guarda = rollback(tmp / "bk", banco, saida)
    n2 = Nucleo(Repositorio(str(banco)), saida)
    assert n2.repo.listar(E.MedicaoPenetracao) == []          # voltou ao estado do backup
    assert len(n2.repo.listar(E.Evidencia)) == 1
    assert n2.verificar_auditoria(atores["auditor"]) > 0
    # o estado "desfeito" não foi apagado
    descartado = Repositorio(str(guarda / "gaema.db"))
    assert len(descartado.listar(E.MedicaoPenetracao)) == 1
    descartado.fechar(); n2.repo.fechar()


def test_rollback_com_backup_invalido_nao_mexe_no_estado_atual(sistema):
    n, banco, saida, tmp = sistema
    criar_backup(n.repo, saida, tmp / "bk")
    n.repo.fechar()
    (tmp / "bk" / "manifesto.json").write_text("{}")
    antes = banco.read_bytes()
    with pytest.raises(BackupInvalido):
        rollback(tmp / "bk", banco, saida)
    assert banco.read_bytes() == antes and saida.exists()


def test_backup_consistente_com_escrita_concorrente(sistema, atores, cenario):
    """Outra conexão grava enquanto o backup é feito: o backup continua verificável."""
    import threading
    n, banco, saida, tmp = sistema
    parar = threading.Event()

    def escrever():
        outro = Nucleo(Repositorio(str(banco)), saida)
        i = 0
        while not parar.is_set() and i < 200:
            i += 1
            outro.registrar(atores["tecnico"], E.MedicaoPenetracao(
                id=f"00000000-0000-4000-8000-{900000 + i:012d}", ponto_id=cenario["PontoAmostral"][0].id,
                repeticao=i, profundidade_bruta="20", profundidade_unidade="cm", resistencia_bruta="1,5",
                resistencia_unidade="MPa", profundidade_cm=20.0, resistencia_kpa=1500.0,
                medido_em=cenario["PontoAmostral"][0].capturado_em, chave_idempotencia=f"c:{i}", sintetico=True,
                criado_em=cenario["PontoAmostral"][0].criado_em, criado_por="x"))
        outro.repo.fechar()

    t = threading.Thread(target=escrever); t.start()
    try:
        for k in range(3):
            criar_backup(n.repo, saida, tmp / f"bk{k}")
    finally:
        parar.set(); t.join()
    assert all(verificar_backup(tmp / f"bk{k}") == [] for k in range(3))
