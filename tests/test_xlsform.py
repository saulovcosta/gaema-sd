"""Fase 5 (ii): XLSForm do formulário de vistoria — estrutura e sintaxe.

Isto NÃO prova que o formulário abre ou funciona no Survey123 Connect nem em aparelho: essa verificação
segue NÃO EXECUTADA (sem organização ArcGIS, LA-05). pyxform confere sintaxe XLSForm/ODK.
"""

import csv
import dataclasses
import io
import json
from pathlib import Path

import pytest

from gaema_sd.adaptadores import xlsform as X
from gaema_sd.dominio.enums import CategoriaEvidencia, CondicaoAcesso, VariavelCampo
from gaema_sd.validacao.unidades import PARA_CM, PARA_KPA

RAIZ = Path(__file__).resolve().parents[1]


def _blocos():
    pilha, repeticoes = [], []
    for l in X.survey():
        t = l["type"]
        if t.startswith("begin_"):
            pilha.append((t[6:], l["name"]))
            if t == "begin_repeat":
                assert not any(k == "repeat" for k, _ in pilha[:-1]), "repetição aninhada não é usada"
                repeticoes.append(l["name"])
        elif t.startswith("end_"):
            assert pilha and pilha[-1] == (t[4:], l["name"]), f"fechamento fora de ordem em {l['name']}"
            pilha.pop()
    assert pilha == []
    return repeticoes


def test_csv_gerados_conferem_com_o_codigo():
    for nome, esperado in X.arquivos_csv().items():
        arq = RAIZ / "adapters" / "arcgis" / "xlsform" / nome
        assert arq.read_text(encoding="utf-8") == esperado, f"{nome} desatualizado: rode scripts/gerar_contratos.py"


def test_blocos_balanceados_e_sem_repeticao_aninhada():
    assert _blocos() == ["outras_observacoes", "penetrometria", "fotos"]


def test_nomes_unicos_e_listas_existentes():
    nomes = [l["name"] for l in X.survey() if not l["type"].startswith(("begin_", "end_"))]
    assert len(nomes) == len(set(nomes))
    listas = {c["list_name"] for c in X.choices()}
    usadas = {l["type"].split()[1] for l in X.survey() if l["type"].startswith("select_one")}
    assert usadas <= listas
    pares = [(c["list_name"], c["name"]) for c in X.choices()]
    assert len(pares) == len(set(pares))
    assert all(l["label"] for l in X.survey() if not l["type"].startswith("end_"))
    assert all(c["label"] for c in X.choices())


def test_listas_cobrem_exatamente_os_enums_do_dominio():
    def lista(n):
        return [c["name"] for c in X.choices() if c["list_name"] == n]
    assert lista("variavel_campo") == [v.value for v in VariavelCampo]
    assert lista("condicao_acesso") == [v.value for v in CondicaoAcesso]
    assert lista("categoria_evidencia") == [v.value for v in CategoriaEvidencia]
    assert set(lista("unidade_profundidade")) == set(PARA_CM)
    assert set(lista("unidade_resistencia")) <= set(PARA_KPA)
    assert lista("sim_nao") == ["sim", "nao"]


def test_variaveis_de_presenca_sao_as_que_o_protocolo_de_teste_avalia():
    proto = json.loads((RAIZ / "config" / "protocolos" / "gaema-prototipo-teste-0.1.0.json").read_text("utf-8"))
    usadas = set()
    for r in proto["regras"]:
        for c in r["condicoes"]:
            usadas |= {c["variavel"]} if "variavel" in c else set(c["variaveis"])
    assert usadas == {v.value for v in X.VARIAVEIS_PRESENCA}


def test_todo_campo_do_formulario_esta_mapeado_para_um_campo_real_do_dominio():
    classes = X.classes_do_dominio()
    mapeados = {m["campo_formulario"] for m in X.mapeamento()}
    for m in X.mapeamento():
        campos = {f.name for f in dataclasses.fields(classes[m["entidade"]])}
        assert m["campo_dominio"] in campos, m
    campos_form = {l["name"] for l in X.survey() if not l["type"].startswith(("begin_", "end_"))}
    assert campos_form == mapeados


def test_nada_de_limiar_profundidade_padrao_ou_numero_de_repeticoes():
    for l in X.survey():
        assert l["default"] in ("", "now()")
        for campo in ("constraint", "relevant"):
            numeros = [t for t in l[campo].replace("(", " ").replace(")", " ").split() if t.replace(".", "").isdigit()]
            assert set(numeros) <= {"0", "1"}, f"número suspeito em {l['name']}: {l[campo]}"
    assert not any(l["type"] == "begin_repeat" and "repeat_count" in l for l in X.survey())
    assert "gps" not in " ".join(l["constraint"] for l in X.survey()).lower()


def test_nota_de_acesso_obrigatoria_so_quando_sem_acesso():
    (l,) = [l for l in X.survey() if l["name"] == "nota_acesso"]
    assert "SEM_ACESSO" in l["relevant"] and "SEM_ACESSO" in l["required"]


def test_versao_do_formulario_acompanha_o_conteudo():
    antes = X.settings()[0]["version"]
    assert len(antes) == 12 and antes == X.settings()[0]["version"]
    original = X.survey
    try:
        X.survey = lambda: original() + [X._linha(type="text", name="campo_novo", label="Novo")]
        assert X.settings()[0]["version"] != antes
    finally:
        X.survey = original


def test_xlsx_gravado_confere_com_os_csv(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    arq = X.escrever_xlsx(tmp_path / "vistoria.xlsx")
    wb = openpyxl.load_workbook(arq)
    assert wb.sheetnames == ["survey", "choices", "settings"]
    for nome, csv_nome in (("survey", "survey.csv"), ("choices", "choices.csv"), ("settings", "settings.csv")):
        linhas = [["" if c is None else str(c) for c in r] for r in wb[nome].iter_rows(values_only=True)]
        esperado = list(csv.reader(io.StringIO(X.arquivos_csv()[csv_nome])))
        assert linhas == esperado, nome


def test_pyxform_converte_sem_erros(tmp_path):
    pytest.importorskip("openpyxl")
    pyxform = pytest.importorskip("pyxform.xls2xform")
    arq = X.escrever_xlsx(tmp_path / "vistoria.xlsx")
    resultado = pyxform.convert(xlsform=str(arq))
    assert "<h:html" in resultado.xform and "gaema_sd_vistoria" in resultado.xform
    # único aviso conhecido: tamanho máximo de imagem não definido (valor seria invenção nossa)
    assert all("max-pixels" in w for w in resultado.warnings), resultado.warnings
    for nome in ("codigo_ponto", "localizacao", "presenca_plantas_invasoras", "pen_resistencia", "foto_arquivo"):
        assert nome in resultado.xform
