"""Cenário SINTÉTICO extra para a interface: uma segunda demanda já em campo, para o aparelho simulado ter missão.

Usa só o caminho normal do núcleo (registrar, transitar). Nada aqui corresponde a área, pessoa ou procedimento real.
"""

from __future__ import annotations

from datetime import date

from ..demo import ATORES
from ..dominio import entidades as E
from ..dominio.enums import Estado, OrigemAlerta, OrigemAreaInteresse, Papel, Proveniencia, TipoFonte
from ..nucleo import Nucleo

# polígono inventado, deslocado da área da demonstração
POLIGONO_CAMPO = "POLYGON ((-48.470 -10.470, -48.458 -10.470, -48.458 -10.459, -48.470 -10.459, -48.470 -10.470))"


def preparar_vistoria_em_campo(n: Nucleo) -> str:
    a = ATORES
    sint = {"sintetico": True}
    fonte, _ = n.registrar(a["analista"], E.FonteDado(nome="Mosaico sintético 2", tipo=TipoFonte.CAMADA_RASTER,
                                                      provedor="GERADOR SINTÉTICO", data_referencia=date(2026, 1, 1),
                                                      resolucao_m=10.0, proveniencia=Proveniencia.AUTORAL, **sint))
    cand, _ = n.registrar(a["analista"], E.AreaCandidata(geometria_wkt=POLIGONO_CAMPO, fonte_ids=[fonte.id],
                                                         data_deteccao=date(2026, 9, 1), metodo_selecao="seleção manual sintética",
                                                         **sint))
    alerta, _ = n.registrar(a["analista"], E.Alerta(origem=OrigemAlerta.PECA_INFORMACAO_TECNICA,
                                                    descricao="Indício remoto sintético (treino de campo)",
                                                    data_alerta=date(2026, 9, 2), area_candidata_id=cand.id,
                                                    referencia_documento="Peça de Informação Técnica SINTÉTICA nº 0002/2026", **sint))
    area, _ = n.registrar(a["analista"], E.AreaInteresse(geometria_wkt=POLIGONO_CAMPO, descricao="Área Sintética de Treino",
                                                         origem=OrigemAreaInteresse.DE_CANDIDATA, area_candidata_id=cand.id, **sint))
    equipe, _ = n.registrar(a["coord"], E.Equipe(nome="Equipe Sintética de Treino", membros=[
        E.MembroEquipe(usuario_id=a["tecnico"].id, papel=Papel.TECNICO_CAMPO, funcao="vistoria"),
        E.MembroEquipe(usuario_id=a["coord"].id, papel=Papel.COORDENADOR, funcao="coordenação")], **sint))
    protocolo = n.repo.listar(E.VersaoProtocolo)[0]
    demanda, _ = n.registrar(a["coord"], E.Demanda(titulo="Demanda sintética de treino em campo",
                                                   objetivo="Treinar a coleta no aparelho simulado.", alerta_ids=[alerta.id],
                                                   area_candidata_id=cand.id, area_interesse_id=area.id, equipe_id=equipe.id, **sint))
    d = demanda.id
    n.transitar(a["sistema"], d, Estado.ALERTA)
    n.transitar(a["analista"], d, Estado.EM_TRIAGEM)
    n.transitar(a["membro"], d, Estado.DEMANDA_ABERTA, motivo="Abertura para treino de campo (sintético).")
    n.transitar(a["coord"], d, Estado.ATRIBUIDA)
    n.registrar(a["coord"], E.CampanhaVistoria(demanda_id=d, equipe_id=equipe.id, versao_protocolo_id=protocolo.id,
                                               objetivo="Vistoria de treino", data_planejada=date(2026, 10, 5),
                                               pacote_offline="missão sintética de treino", **sint))
    n.transitar(a["coord"], d, Estado.PLANEJADA)
    n.transitar(a["tecnico"], d, Estado.EM_CAMPO)
    return d
