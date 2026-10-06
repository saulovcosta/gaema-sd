"""Rodada 6: demonstração com áreas candidatas, pendência do GPS e menu sem quebra de linha."""

import json
import re
from pathlib import Path

from gaema_sd.dominio import entidades as E
from gaema_sd.interface.__main__ import criar_cenario_demo
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio

RAIZ = Path(__file__).resolve().parents[1]


def test_demo_da_interface_traz_areas_candidatas_declaradas_e_sem_alerta(tmp_path):
    criar_cenario_demo(tmp_path)
    repo = Repositorio(str(tmp_path / "gaema-demo.db"))
    try:
        cands = [c for c in repo.listar(E.AreaCandidata) if c.metodo_selecao == Nucleo.METODO_IMPORTACAO]
        assert len(cands) == 3
        assert all(c.sintetico and "sintética" in c.origem_declarada and c.incerteza for c in cands)
        com_alerta = {a.area_candidata_id for a in repo.listar(E.Alerta)}
        assert not com_alerta & {c.id for c in cands}                 # alerta e demanda só por decisão humana
        eventos = [e for e in Nucleo(repo, tmp_path).trilha.eventos if e.acao == "IMPORTACAO_CANDIDATAS"]
        assert len(eventos) == 1 and eventos[0].detalhes["aceitos"] == 3
        assert any(d.titulo == "Demanda sintética de treino em campo" for d in repo.listar(E.Demanda))
    finally:
        repo.fechar()


def test_pendencias_lista_o_limite_do_gps_como_provisorio_sem_fonte():
    valor = json.loads((RAIZ / "config" / "parametros.json").read_text(encoding="utf-8"))["gps_precisao_maxima_m"]
    secao = (RAIZ / "docs" / "pendencias.md").read_text(encoding="utf-8").split("## 5. Valores provisórios sem fonte")[1]
    linha = next(l for l in secao.splitlines() if "gps_precisao_maxima_m" in l)
    assert f"{valor['valor']:g} m" in linha and "sem fonte" in linha and valor["proveniencia"] in linha
    assert "não bloqueia" in linha


def test_itens_do_menu_nao_quebram_linha():
    css = (RAIZ / "src" / "gaema_sd" / "interface" / "modelos" / "base.html.j2").read_text(encoding="utf-8")
    regra = re.search(r"nav\.abas a, nav\.abas span \{([^}]*)\}", css).group(1)
    assert "white-space:nowrap" in regra
    assert re.search(r"nav\.abas ul \{[^}]*flex-wrap:wrap", css)              # quebra entre itens, nunca dentro


def test_nenhuma_situacao_diz_que_a_area_veio_de_satelite():
    """Regressão (captura a 360 px da Rodada 6): a situação inicial dizia "Área indicada por satélite", mas não existe
    triagem por satélite (DEC-035, LA-03)."""
    from gaema_sd.interface import linguagem as L
    for s in L.SITUACAO.values():
        assert "satélite" not in (s.nome + s.acao).lower()
