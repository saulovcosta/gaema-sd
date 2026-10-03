"""Motor de protocolo: definição, avaliação, hash, reprodução e protocolo alterado."""

import copy
import dataclasses

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import ModoProtocolo
from gaema_sd.erros import ErroGaema, ValidacaoFalhou
from gaema_sd.protocolo.definicao import DefinicaoInvalida, canonizar, carregar_definicao, ler_arquivo
from gaema_sd.protocolo.motor import NAO_CLASSIFICADO, avaliar, hash_entradas, resultado_para_json

PROTO = ler_arquivo("gaema-prototipo-teste-0.1.0.json")
DESCR = ler_arquivo("gaema-descritivo-0.1.0.json")


def _entradas(pontos: dict[str, dict[str, str]], medicoes=(), precisao=4.0, hipotese=None):
    """pontos = {"P01": {"PLANTAS_INVASORAS": "sim", ...}} — valores de presença."""
    ent = {"parametros": {"gps_precisao_maxima_m": 10.0}, "pontos": [], "observacoes": [], "medicoes": [],
           "evidencias": []}
    for i, (cod, obs) in enumerate(sorted(pontos.items())):
        pid = f"p{i}"
        ent["pontos"].append({"id": pid, "codigo": cod, "latitude": -10.5, "longitude": -48.5,
                              "precisao_gps_m": precisao, "capturado_em": "2026-01-15T12:00:00+00:00"})
        for j, (var, val) in enumerate(sorted(obs.items())):
            unidade = "presenca" if val in ("sim", "não") else "%"
            ent["observacoes"].append({"id": f"o{i}-{j}", "ponto_id": pid, "variavel": var, "valor_bruto": val,
                                       "unidade_bruta": unidade, "nota": ""})
    for k, (rep, prof, uprof, res, ures) in enumerate(medicoes):
        ent["medicoes"].append({"id": f"m{k}", "ponto_id": "p0", "repeticao": rep, "profundidade_bruta": prof,
                                "profundidade_unidade": uprof, "resistencia_bruta": res,
                                "resistencia_unidade": ures, "contexto_umidade": ""})
    if hipotese:
        ent["observacoes"].append({"id": "oh", "ponto_id": "p0", "variavel": "HIPOTESE_ALTERNATIVA",
                                   "valor_bruto": hipotese, "unidade_bruta": "texto", "nota": ""})
    return ent


def _rodar(dados, entradas):
    return avaliar(carregar_definicao(dados), canonizar(dados)[1], entradas)


NADA = {"PLANTAS_INVASORAS": "não", "CUPINS_MONTICULO": "não", "EROSAO_LAMINAR": "não", "SULCOS": "não",
        "RAVINAS": "não", "VOCOROCAS": "não", "SOLO_EXPOSTO": "não"}


# ------------------------------------------------------------------ definição


@pytest.mark.parametrize("alteracao,mensagem", [
    (lambda d: d["regras"][0]["condicoes"].append({"operador": "maior_que", "variavel": "SOLO_EXPOSTO"}),
     "limiar numérico"),
    (lambda d: d.update(rotulo="protótipo"), "rótulo exato"),
    (lambda d: d["regras"][0]["condicoes"].append({"operador": "presente", "variavel": "NDVI"}),
     "variável desconhecida"),
    (lambda d: d.update(modo="VALIDADO_CIENTIFICAMENTE"), "validado"),
    (lambda d: d.update(limiar_ndvi=0.5), "campos não aceitos"),
    (lambda d: d["regras"].append(dict(d["regras"][0])), "repetido"),
    (lambda d: d["regras"][0].update(categoria="CAT-Z"), "categoria não declarada"),
])
def test_definicao_invalida_recusada(alteracao, mensagem):
    d = copy.deepcopy(PROTO)
    alteracao(d)
    with pytest.raises(DefinicaoInvalida, match=mensagem):
        carregar_definicao(d)


def test_descritivo_nao_aceita_regras():
    d = copy.deepcopy(DESCR)
    d["regras"] = PROTO["regras"]
    with pytest.raises(DefinicaoInvalida, match="DESCRITIVO"):
        carregar_definicao(d)


# ------------------------------------------------------------------ avaliação


@pytest.mark.parametrize("obs,categoria,regra", [
    (NADA, "CAT-A", "R-A1"),
    ({**NADA, "PLANTAS_INVASORAS": "sim"}, "CAT-B", "R-B1"),
    ({**NADA, "PLANTAS_INVASORAS": "sim", "CUPINS_MONTICULO": "sim"}, "CAT-C", "R-C1"),
    ({**NADA, "SOLO_EXPOSTO": "sim", "VOCOROCAS": "sim"}, "CAT-D", "R-D1"),
])
def test_prototipo_classifica_por_ponto(obs, categoria, regra):
    r = _rodar(PROTO, _entradas({"P01": obs}))
    p = r.por_ponto[0]
    assert (p.categoria, p.disparadas) == (categoria, [regra])
    assert r.rotulo == E.ROTULO_PROTOTIPO and r.regras_disparadas == [f"P01:{regra}"]


def test_categorias_concorrentes_nao_classificam():
    obs = {**NADA, "PLANTAS_INVASORAS": "sim", "SOLO_EXPOSTO": "sim", "SULCOS": "sim"}
    p = _rodar(PROTO, _entradas({"P01": obs})).por_ponto[0]
    assert p.categoria.startswith(NAO_CLASSIFICADO) and "CAT-B" in p.categoria and "CAT-D" in p.categoria


def test_dado_ausente_torna_regra_nao_avaliavel_com_motivo():
    r = _rodar(PROTO, _entradas({"P01": {"PLANTAS_INVASORAS": "sim"}}))
    p = r.por_ponto[0]
    assert p.categoria == NAO_CLASSIFICADO and p.disparadas == []
    motivos = dict(p.nao_avaliaveis)
    assert "CUPINS_MONTICULO: sem observação registrada" in motivos["R-B1"]
    assert any("não avaliáveis" in x for x in r.limitacoes)


def test_percentual_nao_vira_presenca_por_limiar():
    """Solo exposto em % não é convertido em presença: isso exigiria limiar."""
    obs = {**NADA, "SOLO_EXPOSTO": "60", "EROSAO_LAMINAR": "sim"}
    p = _rodar(PROTO, _entradas({"P01": obs})).por_ponto[0]
    assert "R-D1" in dict(p.nao_avaliaveis)
    assert "unidade diferente" in dict(p.nao_avaliaveis)["R-D1"]


def test_observacoes_conflitantes_no_mesmo_ponto():
    ent = _entradas({"P01": NADA})
    extra = dict(ent["observacoes"][0], id="ox", valor_bruto="sim")
    ent["observacoes"].append(extra)
    p = _rodar(PROTO, ent).por_ponto[0]
    assert any("conflitantes" in m for _, m in p.nao_avaliaveis)


def test_contagem_por_categoria_sem_agregar_a_area():
    ent = _entradas({"P01": NADA, "P02": {**NADA, "PLANTAS_INVASORAS": "sim"},
                     "P03": {**NADA, "PLANTAS_INVASORAS": "sim"}})
    r = _rodar(PROTO, ent)
    assert r.contagem_categorias == {"CAT-A": 1, "CAT-B": 2}
    assert r.categoria_resumo == "CAT-A: 1 ponto(s); CAT-B: 2 ponto(s)"


def test_modo_descritivo_nao_classifica():
    r = _rodar(DESCR, _entradas({"P01": {**NADA, "PLANTAS_INVASORAS": "sim"}}))
    assert r.modo is ModoProtocolo.DESCRITIVO and r.por_ponto[0].categoria == ""
    assert r.categoria_resumo == "" and r.regras_disparadas == []
    assert r.resumo_variaveis["PLANTAS_INVASORAS"] == {"presente": 1}


def test_penetrometria_descritiva_com_unidades_mistas():
    med = [(1, "20", "cm", "1,5", "MPa"), (2, "0.2", "m", "1700", "kPa"), (3, "200", "mm", "1.6", "MPa"),
           (1, "40", "cm", "2", "MPa")]
    r = _rodar(DESCR, _entradas({"P01": NADA}, medicoes=med))
    a20, a40 = r.penetrometria
    assert (a20["profundidade_cm"], a20["n"], a20["min_kpa"], a20["max_kpa"], a20["media_kpa"]) == \
        (20.0, 3, 1500.0, 1700.0, 1600.0)
    assert (a40["n"], a40["media_kpa"]) == (1, 2000.0)
    assert "Nenhum limiar" in a20["metodo"]


def test_limitacoes_gps_ruim_e_hipotese_alternativa():
    r = _rodar(PROTO, _entradas({"P01": NADA}, precisao=30.0, hipotese="pisoteio recente por manejo"))
    assert any("GPS" in x and "P01" in x for x in r.limitacoes)
    assert r.hipoteses_alternativas == ["P01: pisoteio recente por manejo"]
    assert any("não conclui autoria" in x for x in r.limitacoes)


# ------------------------------------------------------------------ hash e determinismo


def test_hash_independe_da_ordem_e_muda_com_valor_bruto():
    ent = _entradas({"P01": NADA, "P02": {**NADA, "CUPINS_MONTICULO": "sim"}})
    invertida = {k: list(reversed(v)) if isinstance(v, list) else v for k, v in ent.items()}
    assert hash_entradas(ent) == hash_entradas(invertida)
    alterada = copy.deepcopy(ent)
    alterada["observacoes"][0]["valor_bruto"] = "sim"
    assert hash_entradas(alterada) != hash_entradas(ent)


def test_resultado_identico_em_execucoes_repetidas():
    ent = _entradas({"P01": NADA, "P02": {**NADA, "PLANTAS_INVASORAS": "sim"}})
    assert resultado_para_json(_rodar(PROTO, ent)) == resultado_para_json(_rodar(PROTO, copy.deepcopy(ent)))


# ------------------------------------------------------------------ núcleo: reprodução e protocolo alterado


@pytest.fixture
def fluxo(nucleo, atores, cenario):
    from .test_regressao_revisao import levar_ate_revisao

    d, diag = levar_ate_revisao(nucleo, atores, cenario)
    return d, diag


def test_diagnostico_guarda_fotografia_e_reproduz(nucleo, atores, fluxo):
    _, diag = fluxo
    assert diag.entradas_canonicas and diag.resultado_json and diag.limitacoes
    saida = nucleo.reproduzir_diagnostico(atores["auditor"], diag.id)
    assert saida == {"reproduzido": True, "divergencias": [], "entradas_atuais_iguais": True}
    assert nucleo.trilha.eventos[-1].acao == "REPRODUCAO_DIAGNOSTICO"


def test_dado_corrigido_depois_nao_altera_diagnostico_antigo(nucleo, atores, cenario, fluxo):
    _, diag = fluxo
    obs = nucleo.repo.obter(E.Observacao, cenario["Observacao"][0].id)
    nucleo.atualizar(atores["tecnico"], dataclasses.replace(obs, valor_bruto="40"), obs.versao)
    saida = nucleo.reproduzir_diagnostico(atores["auditor"], diag.id)
    assert saida["reproduzido"] is True and saida["entradas_atuais_iguais"] is False


def test_protocolo_alterado_gera_nova_versao_e_preserva_historico(nucleo, atores, fluxo):
    _, diag = fluxo
    v1 = nucleo.repo.obter(E.VersaoProtocolo, diag.versao_protocolo_id)
    novo = copy.deepcopy(ler_arquivo("gaema-descritivo-0.1.0.json"))
    novo["limitacoes"].append("Texto acrescentado na versão 0.2.0.")
    with pytest.raises(ValidacaoFalhou, match="já existe esta versão"):  # mesma versão, conteúdo diferente
        nucleo.publicar_protocolo(atores["coord"], novo)
    novo["versao"] = "0.2.0"
    v2 = nucleo.publicar_protocolo(atores["coord"], novo)
    assert v2.hash_definicao != v1.hash_definicao
    assert nucleo.publicar_protocolo(atores["coord"], novo).id == v2.id  # idempotente
    assert nucleo.reproduzir_diagnostico(atores["auditor"], diag.id)["reproduzido"] is True
    with pytest.raises(ErroGaema, match="imutável"):
        nucleo.atualizar(atores["coord"], dataclasses.replace(v1, rotulo="x"), v1.versao)


def test_reprodução_detecta_resultado_adulterado_no_banco(nucleo, atores, fluxo):
    import json as _json

    _, diag = fluxo
    dados = _json.loads(nucleo.repo.con.execute("SELECT dados FROM registros WHERE id=?", (diag.id,)).fetchone()[0])
    dados["resultado_descritivo"] = dados["resultado_descritivo"].replace("avaliados: 1", "avaliados: 9")
    resultado = _json.loads(dados["resultado_json"])
    resultado["contagem_categorias"] = {"CAT-D": 1}
    dados["resultado_json"] = _json.dumps(resultado)
    nucleo.repo.con.execute("UPDATE registros SET dados=? WHERE id=?", (_json.dumps(dados), diag.id))
    assert nucleo.reproduzir_diagnostico(atores["auditor"], diag.id)["divergencias"] == [
        "resultado do motor", "texto, categoria ou regras gravados"]


def test_computar_exige_papel_e_estado(nucleo, atores, cenario, fluxo):
    d, _ = fluxo
    from gaema_sd.erros import AcessoNegado

    with pytest.raises(AcessoNegado):
        nucleo.computar_diagnostico(atores["tecnico"], d, cenario["CampanhaVistoria"][0].id)
    with pytest.raises(ErroGaema, match="EM_VALIDACAO"):
        nucleo.computar_diagnostico(atores["sistema"], d, cenario["CampanhaVistoria"][0].id)
