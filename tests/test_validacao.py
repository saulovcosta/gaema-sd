import dataclasses

import pytest

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import ModoProtocolo, SituacaoIntegracao, VariavelCampo
from gaema_sd.erros import ValidacaoFalhou
from gaema_sd.validacao import Gravidade, exigir_sem_erros
from gaema_sd.validacao import geometria, gps, unidades
from gaema_sd.validacao.entidades import validar


def codigos(problemas):
    return {p.codigo for p in problemas}


# ---------------------------------------------------------------- geometria inválida

@pytest.mark.parametrize("wkt,codigo", [
    ("", "GEOM_AUSENTE"),
    ("POLYGON ((isto não é wkt", "GEOM_ILEGIVEL"),
    ("POINT (-48.5 -10.5)", "GEOM_TIPO"),
    # gravata-borboleta: auto-interseção
    ("POLYGON ((-48.50 -10.50, -48.49 -10.49, -48.49 -10.50, -48.50 -10.49, -48.50 -10.50))", "GEOM_INVALIDA"),
    ("POLYGON ((-48.5 -10.5, -48.4 -10.5, -48.3 -10.5, -48.5 -10.5))", "GEOM_INVALIDA"),
    ("POLYGON ((-10.5 -48.5, 200 -48.5, 200 -48.4, -10.5 -48.5))", "GEOM_FORA_WGS84"),
    ("POLYGON Z ((-48.5 -10.5 1, -48.4 -10.5 1, -48.4 -10.4 1, -48.5 -10.5 1))", "GEOM_3D"),
])
def test_geometria_invalida(wkt, codigo):
    assert codigo in codigos(geometria.validar_poligono_wkt(wkt))


def test_geometria_valida_sem_problemas():
    from gaema_sd.sinteticos import POLIGONO

    assert geometria.validar_poligono_wkt(POLIGONO) == []


def test_geometria_fora_do_tocantins_e_alerta_nao_erro():
    p = geometria.validar_poligono_wkt("POLYGON ((-43 -20, -42.9 -20, -42.9 -19.9, -43 -19.9, -43 -20))")
    assert [x.gravidade for x in p] == [Gravidade.ALERTA]


def test_coordenada_lat_lon_trocadas_e_zero():
    assert "COORD_FORA_WGS84" in codigos(geometria.validar_coordenada(-148.5, -10.5))
    assert "COORD_ZERO" in codigos(geometria.validar_coordenada(0, 0))
    assert "COORD_NAO_FINITA" in codigos(geometria.validar_coordenada(float("nan"), -48))


# ---------------------------------------------------------------- GPS ruim

def test_gps_ruim_gera_alerta_e_nao_bloqueia():
    p = gps.validar_precisao(35.0)
    assert codigos(p) == {"GPS_RUIM"} and p[0].gravidade is Gravidade.ALERTA


def test_gps_sem_precisao_e_erro(cenario):
    ponto = dataclasses.replace(cenario["PontoAmostral"][0], precisao_gps_m=None)
    assert "GPS_PRECISAO_AUSENTE" in codigos(validar(ponto))
    assert "GPS_PRECISAO_INVALIDA" in codigos(gps.validar_precisao(-1))


def test_ponto_com_gps_ruim_ainda_e_gravavel(cenario):
    ponto = dataclasses.replace(cenario["PontoAmostral"][0], precisao_gps_m=50.0)
    alertas = exigir_sem_erros(validar(ponto))
    assert codigos(alertas) == {"GPS_RUIM"}


# ---------------------------------------------------------------- unidades

def test_conversao_de_unidades_preserva_bruto():
    assert unidades.para_kpa("1,5", "MPa") == (1500.0, [])
    assert unidades.para_kpa("2", "kgf/cm2")[0] == pytest.approx(196.133)
    assert unidades.para_cm("0.2", "m") == (20.0, [])
    assert unidades.para_cm("150", "mm") == (15.0, [])


@pytest.mark.parametrize("bruto,unidade,codigo", [
    ("10", "psi", "UNIDADE_INVALIDA"),
    ("abc", "kPa", "VALOR_NAO_NUMERICO"),
    ("-3", "kPa", "VALOR_NEGATIVO"),
    ("inf", "kPa", "VALOR_NAO_NUMERICO"),
])
def test_unidade_ou_valor_invalido(bruto, unidade, codigo):
    v, p = unidades.para_kpa(bruto, unidade)
    assert v is None and codigo in codigos(p)


def test_medicao_com_unidade_invalida(cenario):
    m = dataclasses.replace(cenario["MedicaoPenetracao"][0], resistencia_unidade="bar", repeticao=0)
    assert {"UNIDADE_INVALIDA", "REPETICAO_INVALIDA"} <= codigos(validar(m))


def test_percentual_fora_da_faixa(cenario):
    o = dataclasses.replace(cenario["Observacao"][0], valor_bruto="130")
    assert "PERCENTUAL_FORA_FAIXA" in codigos(validar(o))


def test_variavel_outra_exige_descricao(cenario):
    o = dataclasses.replace(cenario["Observacao"][0], variavel=VariavelCampo.OUTRA, unidade_bruta="texto")
    assert "OUTRA_SEM_NOTA" in codigos(validar(o))


# ---------------------------------------------------------------- variável obrigatória ausente

def test_variavel_obrigatoria_ausente(cenario):
    o = dataclasses.replace(cenario["Observacao"][0], valor_bruto="  ", observador_id="")
    p = validar(o)
    assert {("OBRIGATORIO", "valor_bruto"), ("OBRIGATORIO", "observador_id")} <= {(x.codigo, x.campo) for x in p}
    with pytest.raises(ValidacaoFalhou, match="valor_bruto"):
        exigir_sem_erros(p)


def test_construir_sem_campo_obrigatorio_falha():
    with pytest.raises(TypeError):
        E.Observacao(ponto_id="x")  # faltam variável, valor, unidade...


# ---------------------------------------------------------------- regras de entidade

def test_area_candidata_sem_fonte_e_sinal_orfao(cenario):
    a = dataclasses.replace(cenario["AreaCandidata"][0], fonte_ids=[])
    assert {"SEM_FONTE", "SINAL_SEM_FONTE"} <= codigos(validar(a))


def test_alerta_sem_local():
    a = E.Alerta(origem=E.OrigemAlerta.NOTICIA_EXTERNA, descricao="x", data_alerta=E.date(2026, 1, 1),
                 criado_por="u")
    assert "ALERTA_SEM_LOCAL" in codigos(validar(a))


def test_prototipo_exige_rotulo_exato(cenario):
    p = dataclasses.replace(cenario["VersaoProtocolo"][0], modo=ModoProtocolo.PROTOTIPO_TESTE, rotulo="teste")
    assert "ROTULO_PROTOTIPO" in codigos(validar(p))
    ok = dataclasses.replace(p, rotulo=E.ROTULO_PROTOTIPO)
    assert validar(ok) == []


def test_modo_validado_exige_referencia(cenario):
    p = dataclasses.replace(cenario["VersaoProtocolo"][0], modo=ModoProtocolo.VALIDADO_CIENTIFICAMENTE)
    assert "SEM_REFERENCIA_VALIDACAO" in codigos(validar(p))


def test_integracao_nao_pode_ser_ativa_sem_evidencia_nem_guardar_segredo():
    i = E.IntegracaoExterna(nome="Survey123", sistema="ArcGIS", situacao=SituacaoIntegracao.ATIVA,
                            variavel_configuracao="abc123-segredo", criado_por="u")
    assert {"ATIVA_SEM_EVIDENCIA", "VARIAVEL_INVALIDA"} <= codigos(validar(i))


def test_diagnostico_exige_limitacoes_e_rotulo_para_categoria():
    d = E.Diagnostico(demanda_id="d", campanha_id="c", versao_protocolo_id="p", hash_definicao_protocolo="0" * 64,
                      hash_entradas="1" * 64, resultado_descritivo="texto", categoria_descritiva="X",
                      criado_por="u")
    assert {"SEM_LIMITACOES", "CATEGORIA_SEM_ROTULO"} <= codigos(validar(d))


def test_relatorio_reemitido_exige_motivo_e_vinculo():
    r = E.Relatorio(demanda_id="d", numero_versao=2, diagnostico_id="g", versao_protocolo_id="p",
                    hash_conteudo="a" * 64, gerado_por="u", criado_por="u")
    assert "REEMISSAO_SEM_MOTIVO" in codigos(validar(r))
    ok = dataclasses.replace(r, substitui_relatorio_id="r1", motivo_reemissao="correção de grafia")
    assert validar(ok) == []


def test_revisao_exige_fundamentacao():
    r = E.RevisaoTecnica(diagnostico_id="d", revisor_id="u", resultado=E.ResultadoRevisao.APROVADO,
                         fundamentacao="ok", criado_por="u")
    assert "FUNDAMENTACAO_CURTA" in codigos(validar(r))


def test_equipe_vazia_ou_com_papel_inadequado():
    e = E.Equipe(nome="x", criado_por="u", membros=[E.MembroEquipe(usuario_id="a", papel=E.Papel.SISTEMA)])
    assert "PAPEL_INADEQUADO" in codigos(validar(e))
    assert "EQUIPE_VAZIA" in codigos(validar(E.Equipe(nome="x", criado_por="u")))


def test_evidencia_hash_invalido_e_coordenada_incompleta(cenario):
    ev = dataclasses.replace(cenario["Evidencia"][0], sha256="xyz", latitude_declarada=-10.0)
    assert {"HASH_INVALIDO", "COORD_INCOMPLETA"} <= codigos(validar(ev))
