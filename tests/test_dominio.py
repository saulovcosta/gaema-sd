import dataclasses

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.serializacao import de_dict, para_dict

EXIGIDAS = """AreaCandidata Alerta Demanda AreaInteresse Equipe CampanhaVistoria PontoAmostral Observacao
MedicaoPenetracao Evidencia VersaoProtocolo Diagnostico RevisaoTecnica Providencia PlanoRecuperacao
MarcoMonitoramento Relatorio EventoAuditoria FonteDado IntegracaoExterna""".split()
NOVAS = ["PedidoAcesso"]   # Rodada 3: usuário de teste pedido pela interface (DEC-034)


def test_as_20_entidades_exigidas_existem_mais_as_novas():
    assert sorted(EXIGIDAS + NOVAS) == sorted(E.POR_NOME)
    assert len(E.ENTIDADES) == 21


def test_ida_e_volta_preserva_tudo(cenario):
    for lista in cenario.values():
        for obj in lista:
            assert de_dict(type(obj), para_dict(obj)) == obj


def test_campo_desconhecido_recusado():
    import pytest

    with pytest.raises(ValueError, match="desconhecidos"):
        de_dict(E.Alerta, {"campo_inventado": 1})


def test_ids_unicos_e_registros_sinteticos(cenario):
    ids = [o.id for lista in cenario.values() for o in lista]
    assert len(ids) == len(set(ids))
    assert all(o.sintetico for lista in cenario.values() for o in lista)


def test_registros_tem_versao_para_concorrencia():
    for cls in E.ENTIDADES:
        if cls is E.EventoAuditoria:
            assert cls.__dataclass_params__.frozen
            continue
        assert "versao" in {f.name for f in dataclasses.fields(cls)}, cls
