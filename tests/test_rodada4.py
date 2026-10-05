"""Rodada 4: entrada de áreas candidatas por importação (GeoJSON/CSV) e passagem a alerta/demanda só por ação humana.

Dados sintéticos. Não há processamento de imagem, NDVI nem triagem por satélite (README e LA-03).
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from gaema_sd.config import parametro
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import Estado
from gaema_sd.erros import AcessoNegado, ErroGaema
from gaema_sd.importacao import chave_geometria, ler_candidatas
from gaema_sd.interface.app import USUARIOS_DE_TESTE

from .test_interface import Cliente, cliente, modelo, sistema  # noqa: F401  (fixtures)
from .test_rodada2 import multipart

A = USUARIOS_DE_TESTE
RAIZ = Path(__file__).parents[1]
EXEMPLOS = RAIZ / "fixtures" / "sinteticos" / "importacao"
GEOJSON = (EXEMPLOS / "candidatas.geojson").read_text(encoding="utf-8")
CSV = (EXEMPLOS / "candidatas.csv").read_text(encoding="utf-8")
QUADRADO = "POLYGON ((-48.30 -10.20, -48.29 -10.20, -48.29 -10.19, -48.30 -10.19, -48.30 -10.20))"


def csv_de(*linhas):
    return "geometria_wkt,data_deteccao,origem_declarada,incerteza,fonte\n" + "\n".join(linhas) + "\n"


def linha(wkt=QUADRADO, data="2026-08-01", origem="planilha sintética", incerteza="", fonte="F"):
    return f'"{wkt}",{data},{origem},{incerteza},{fonte}'


# ================= leitura pura ======================================================================================

def test_exemplos_sinteticos_sao_lidos_sem_problema():
    for texto, formato in ((GEOJSON, "geojson"), (CSV, "csv")):
        itens = ler_candidatas(texto, formato, hoje=date(2026, 10, 5))
        assert len(itens) == 2 and all(i.aceito and i.chave.startswith("geom:") for i in itens), [i.problemas for i in itens]
        assert all(i.origem_declarada for i in itens)


def test_mesma_area_com_vertices_em_outra_ordem_tem_a_mesma_chave():
    girado = "POLYGON ((-48.29 -10.19, -48.30 -10.19, -48.30 -10.20, -48.29 -10.20, -48.29 -10.19))"
    assert chave_geometria(QUADRADO) == chave_geometria(girado)
    assert chave_geometria(QUADRADO) != chave_geometria(QUADRADO.replace("-48.29", "-48.28"))


@pytest.mark.parametrize("texto,codigo", [
    (csv_de(linha(data=(date.today() + timedelta(days=1)).isoformat())), "DATA_FUTURA"),
    (csv_de(linha(data="10/08/2026")), "DATA_INVALIDA"),
    (csv_de(linha(origem="")), "ORIGEM_AUSENTE"),
    (csv_de(linha(wkt="POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))")), "GEOM_INVALIDA"),
    (csv_de(linha(wkt="POINT (-48.3 -10.2)")), "GEOM_TIPO"),
    (csv_de(linha(wkt="não é wkt")), "GEOM_ILEGIVEL"),
    (csv_de(linha(), linha()), "DUPLICADA_NO_ARQUIVO"),
])
def test_item_ruim_e_recusado_com_motivo(texto, codigo):
    itens = ler_candidatas(texto, "csv")
    assert any(p.codigo == codigo for i in itens for p in i.problemas), [(i.numero, i.problemas) for i in itens]
    assert not itens[-1].aceito


@pytest.mark.parametrize("texto,formato,trecho", [
    ("{}", "geojson", "FeatureCollection"),
    ("{nao json", "geojson", "ilegível"),
    ("a,b\n1,2\n", "csv", "faltam colunas"),
    (csv_de(), "csv", "nenhuma área"),
    (GEOJSON, "shapefile", "formato desconhecido"),
])
def test_arquivo_mal_formado_e_recusado_inteiro(texto, formato, trecho):
    with pytest.raises(ValueError, match=trecho):
        ler_candidatas(texto, formato)


def test_feicao_que_nao_e_poligono_e_recusada():
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"data_deteccao": "2026-08-01", "origem_declarada": "x"},
         "geometry": {"type": "LineString", "coordinates": [[-48.3, -10.2], [-48.2, -10.1]]}},
        {"type": "Feature", "properties": {"data_deteccao": "2026-08-01", "origem_declarada": "x"},
         "geometry": {"type": "Polygon", "coordinates": "lixo"}}]}
    itens = ler_candidatas(json.dumps(fc), "geojson")
    assert [p.codigo for p in itens[0].problemas][:1] == ["GEOM_TIPO"] and not itens[1].aceito


def test_limite_de_itens():
    with pytest.raises(ValueError, match="máximo"):
        ler_candidatas(csv_de(*[linha(wkt=QUADRADO.replace("-48.30", f"-48.{31 + i}")) for i in range(3)]), "csv",
                       maximo_itens=2)


# ================= núcleo ============================================================================================

def test_importacao_grava_aceitos_audita_e_nao_cria_alerta_nem_demanda(sistema):
    app, n, _ = sistema
    alertas, demandas = len(n.repo.listar(E.Alerta)), len(n.repo.listar(E.Demanda))
    r = n.importar_candidatas(A["analista"], GEOJSON, "geojson")
    assert len(r["gravados"]) == 2
    for c in r["gravados"]:
        assert c.origem_declarada == "camada sintética de teste A" and c.chave_deduplicacao.startswith("geom:")
        assert "sem processamento de imagem nem NDVI" in c.metodo_selecao and c.sintetico and c.sinais == []
        assert c.criado_por == A["analista"].id
    assert len(n.repo.listar(E.Alerta)) == alertas and len(n.repo.listar(E.Demanda)) == demandas
    ev = n.trilha.eventos[-1]
    assert ev.acao == "IMPORTACAO_CANDIDATAS" and ev.detalhes["aceitos"] == 2 and len(ev.detalhes["sha256"]) == 64
    fonte = n.repo.obter(E.FonteDado, r["gravados"][0].fonte_ids[0])
    assert "declarada no arquivo importado" in fonte.nome and fonte.proveniencia.value == "PENDENTE"


def test_reimportar_a_mesma_area_e_recusado_como_duplicada(sistema):
    app, n, _ = sistema
    n.importar_candidatas(A["analista"], CSV, "csv")
    r = n.importar_candidatas(A["analista"], CSV, "csv")
    assert r["gravados"] == [] and all(any(p.codigo == "DUPLICADA_NO_BANCO" for p in i.problemas) for i in r["itens"])


def test_aceitos_e_recusados_no_mesmo_arquivo(sistema):
    app, n, _ = sistema
    texto = csv_de(linha(), linha(origem=""), linha(wkt=QUADRADO.replace("-48.30", "-48.31")))
    r = n.importar_candidatas(A["analista"], texto, "csv")
    assert len(r["gravados"]) == 2 and [i.aceito for i in r["itens"]] == [True, False, True]


@pytest.mark.parametrize("quem", ["coord", "tecnico", "membro", "revisor", "auditor", "admin"])
def test_so_o_analista_importa(sistema, quem):
    app, n, _ = sistema
    with pytest.raises(AcessoNegado):
        n.importar_candidatas(A[quem], CSV, "csv")
    assert n.trilha.eventos[-1].acao == "ACESSO_NEGADO"


def test_arquivo_grande_ou_ilegivel_e_recusado_e_auditado(sistema, monkeypatch):
    app, n, _ = sistema
    from gaema_sd import nucleo as nuc
    monkeypatch.setattr(nuc, "parametro", lambda k: 100 if k == "importacao_max_bytes" else parametro(k))
    with pytest.raises(ErroGaema, match="maior que"):
        n.importar_candidatas(A["analista"], CSV, "csv")
    assert n.trilha.eventos[-1].acao == "IMPORTACAO_RECUSADA"
    monkeypatch.undo()
    with pytest.raises(ErroGaema, match="FeatureCollection"):
        n.importar_candidatas(A["analista"], "{}", "geojson")


def test_parametros_de_importacao_tem_proveniencia():
    d = json.loads((RAIZ / "config" / "parametros.json").read_text(encoding="utf-8"))
    for k in ("importacao_max_bytes", "importacao_max_itens"):
        assert d[k]["proveniencia"] == "AUTORAL" and d[k]["valor"] > 0


# ================= interface ==========================================================================================

def importar_pela_tela(c, texto, nome="areas.csv", tipo="text/csv"):
    corpo, ct = multipart({"csrf": c.csrf, "formato": "csv", "texto": ""}, {"arquivo": (nome, tipo, texto.encode())})
    return c.pedir("POST", "/candidatas/importar", corpo=corpo, tipo=ct)


def test_tela_diz_que_nao_ha_triagem_por_satelite_e_mostra_origem_e_incerteza(sistema):
    app, n, _ = sistema
    c = cliente(sistema, "analista")
    t = c.get("/candidatas").texto
    assert "Não há triagem por satélite neste protótipo" in t and "NDVI" in t
    assert importar_pela_tela(c, CSV).status == 303
    t = c.get("/candidatas").texto
    assert "Importação concluída: 2 área(s) registrada(s) e 0 recusada(s)" in t
    assert "planilha sintética de teste B" in t and "vértices arredondados a 0.01 grau" in t and "só indicada" in t
    assert "Resultado da importação, item por item" in t
    assert "Resultado da importação" not in c.get("/candidatas").texto                 # mostrado uma vez


def test_importar_colando_o_texto_e_geojson_por_arquivo(sistema):
    app, n, _ = sistema
    c = cliente(sistema, "analista")
    c.get("/candidatas")
    corpo, ct = multipart({"csrf": c.csrf, "formato": "geojson", "texto": GEOJSON}, {})
    assert c.pedir("POST", "/candidatas/importar", corpo=corpo, tipo=ct).status == 303
    assert "2 área(s) registrada(s)" in c.get("/candidatas").texto
    importar_pela_tela(c, GEOJSON, nome="x.geojson", tipo="application/geo+json")
    t = c.get("/candidatas").texto
    assert "0 área(s) registrada(s) e 2 recusada(s)" in t and "área já registrada antes" in t


def test_recusas_aparecem_por_item(sistema):
    app, n, _ = sistema
    c = cliente(sistema, "analista")
    futura = (date.today() + timedelta(days=2)).isoformat()
    importar_pela_tela(c, csv_de(linha(data=futura), linha(origem="")))
    t = c.get("/candidatas").texto
    assert "data de detecção no futuro" in t and "informe a origem declarada" in t and "0 área(s) registrada(s)" in t


def test_candidata_so_vira_alerta_e_demanda_por_acao_humana_auditada(sistema):
    app, n, _ = sistema
    c = cliente(sistema, "analista")
    importar_pela_tela(c, csv_de(linha()))
    cand = next(x for x in n.repo.listar(E.AreaCandidata) if x.origem_declarada == "planilha sintética")
    assert not any(a.area_candidata_id == cand.id for a in n.repo.listar(E.Alerta))
    c.get("/candidatas")
    c.post(f"/candidatas/{cand.id}/demanda", {"titulo": "antes do alerta"})
    assert "gere o alerta antes" in c.get("/candidatas").texto
    c.post(f"/candidatas/{cand.id}/alerta", {"origem": "SINAL_REMOTO", "descricao": "área importada merece triagem"})
    alerta = next(a for a in n.repo.listar(E.Alerta) if a.area_candidata_id == cand.id)
    assert alerta.criado_por == A["analista"].id
    c.post(f"/candidatas/{cand.id}/alerta", {"origem": "SINAL_REMOTO", "descricao": "segunda vez, não pode"})
    assert "já tem alerta" in c.get("/candidatas").texto
    c.post(f"/candidatas/{cand.id}/demanda", {"titulo": "Demanda da área importada (sintética)", "municipio": "Município Sintético C"})
    d = next(x for x in n.repo.listar(E.Demanda) if x.area_candidata_id == cand.id)
    assert d.estado is Estado.CANDIDATA and d.alerta_ids == [alerta.id] and d.municipio == "Município Sintético C"
    n.transitar(A["analista"], d.id, Estado.ALERTA)                       # geometria e fonte conferidas pelo núcleo
    acoes = [(e.acao, e.entidade) for e in n.trilha.eventos if e.ator_id == A["analista"].id]
    assert ("CRIAR", "Alerta") in acoes and ("CRIAR", "Demanda") in acoes and ("CRIAR", "AreaInteresse") in acoes


def test_coordenador_nao_importa_mas_decide_alerta_e_tecnico_so_consulta(sistema):
    """Matriz de acesso inalterada: importar é do analista (REGISTRAR_AREA_CANDIDATA); gerar alerta e abrir demanda
    também é do coordenador (REGISTRAR_ALERTA, REGISTRAR_DEMANDA); técnico e membro só consultam."""
    app, n, _ = sistema
    n.importar_candidatas(A["analista"], CSV, "csv")
    c = cliente(sistema, "coord")
    t = c.get("/candidatas").texto
    assert 'disabled aria-describedby="razao-importar"' in t and "Gerar alerta desta área" in t
    assert importar_pela_tela(c, CSV.replace("-48.36", "-48.46")).status == 403
    cand = n.repo.listar(E.AreaCandidata)[-1]
    c.post(f"/candidatas/{cand.id}/alerta", {"origem": "SINAL_REMOTO", "descricao": "coordenador decide gerar"})
    assert next(a for a in n.repo.listar(E.Alerta) if a.area_candidata_id == cand.id).criado_por == A["coord"].id
    for quem in ("tecnico", "membro"):
        t = cliente(sistema, quem).get("/candidatas").texto
        assert 'disabled aria-describedby="razao-alerta-1"' in t or "Abrir a demanda" in t or "não registra alerta" in t
    m = cliente(sistema, "membro")
    outra = n.repo.listar(E.AreaCandidata)[-2]
    m.post(f"/candidatas/{outra.id}/alerta", {"origem": "SINAL_REMOTO", "descricao": "membro tentando gerar"})
    assert not any(a.area_candidata_id == outra.id for a in n.repo.listar(E.Alerta))


def test_multipart_de_importacao_tem_limite_proprio_e_token(sistema, monkeypatch):
    app, n, _ = sistema
    from gaema_sd.interface import app as modulo
    c = cliente(sistema, "analista")
    c.get("/candidatas")
    corpo, ct = multipart({"csrf": "0" * 32, "formato": "csv", "texto": ""}, {"arquivo": ("a.csv", "text/csv", CSV.encode())})
    assert c.pedir("POST", "/candidatas/importar", corpo=corpo, tipo=ct).status == 403
    monkeypatch.setattr(modulo, "limite_importacao", lambda: 50)
    r = importar_pela_tela(c, CSV)
    assert r.status == 413 and "Arquivo grande demais" in r.texto
    assert modulo.limite_multipart("/demanda/nova") is None


def test_readme_registra_que_nao_ha_triagem_por_satelite():
    t = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert "Não existe triagem por satélite" in t and "NDVI" in t and "LA-03" in t


def test_campo_de_arquivo_tem_alvo_de_toque(sistema):
    css = cliente(sistema, "analista").get("/candidatas").texto
    assert __import__("re").search(r"input\[type=file\] \{[^}]*min-height:44px", css)
