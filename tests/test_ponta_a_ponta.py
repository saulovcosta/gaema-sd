"""Protótipo local completo (src/gaema_sd/demo.py), só com dados sintéticos."""

from gaema_sd import demo
from gaema_sd.dominio.entidades import ROTULO_PROTOTIPO


def test_fluxo_completo(tmp_path):
    r = demo.executar(tmp_path, verbose=False)
    assert r["estado_final"] == "EM_MONITORAMENTO"
    assert r["categorias"] == "CAT-B: 1 ponto(s); CAT-C: 1 ponto(s); CAT-D: 1 ponto(s)"
    assert r["reproducao"] == {"reproduzido": True, "divergencias": [], "entradas_atuais_iguais": True}
    assert r["evidencia_integra"] is True and r["eventos_auditoria"] > 50
    html1, pdf1, html2 = r["relatorios"]
    assert all(p.exists() for p in (html1, pdf1, html2))
    assert ROTULO_PROTOTIPO in html1.read_text(encoding="utf-8")
    assert r["relatorio_v2"].substitui_relatorio_id == r["relatorio_v1"].id
    assert "Verificação semestral 2" in html2.read_text(encoding="utf-8")


def test_demo_recusa_pasta_com_conteudo(tmp_path, capsys):
    (tmp_path / "qualquer.txt").write_text("x")
    assert demo.main(["demo", str(tmp_path)]) == 2
