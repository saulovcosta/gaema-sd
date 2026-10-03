"""Cenário 100% SINTÉTICO para testes e demonstração.

Nomes, identificadores, coordenadas e datas são inventados. O polígono fica num
ponto genérico do Tocantins e não corresponde a nenhum imóvel conhecido.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from .dominio import entidades as E
from .dominio.enums import (
    CategoriaEvidencia,
    ModoProtocolo,
    OrigemAlerta,
    OrigemAreaInteresse,
    Papel,
    Proveniencia,
    TipoFonte,
    VariavelCampo,
)
from .dominio.serializacao import para_dict
from .protocolo.definicao import canonizar, ler_arquivo

T0 = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
POLIGONO = "POLYGON ((-48.500 -10.500, -48.490 -10.500, -48.490 -10.490, -48.500 -10.490, -48.500 -10.500))"
FOTO_SINTETICA = b"\xff\xd8\xff\xe0" + b"IMAGEM SINTETICA GAEMA SD" + b"\x00" * 32


def _id(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def cenario() -> dict[str, list]:
    base = dict(criado_em=T0, criado_por="usuario-sintetico-01", sintetico=True)
    fonte = E.FonteDado(id=_id(1), nome="Camada sintética de cobertura", tipo=TipoFonte.CAMADA_RASTER,
                        provedor="GERADOR SINTÉTICO", data_referencia=date(2026, 1, 1), resolucao_m=30.0,
                        proveniencia=Proveniencia.AUTORAL, **base)
    candidata = E.AreaCandidata(
        id=_id(2), geometria_wkt=POLIGONO, fonte_ids=[fonte.id], data_deteccao=date(2026, 1, 10),
        sinais=[E.SinalRemoto(nome="indice_sintetico", valor=0.5, fonte_id=fonte.id,
                              data_referencia=date(2026, 1, 1), metodo="valor inventado para teste")],
        metodo_selecao="seleção manual sintética", chave_deduplicacao="sintetica-a", **base)
    alerta = E.Alerta(id=_id(3), origem=OrigemAlerta.SINAL_REMOTO, descricao="Alerta sintético de teste",
                      data_alerta=date(2026, 1, 11), area_candidata_id=candidata.id, **base)
    area = E.AreaInteresse(id=_id(4), geometria_wkt=POLIGONO, descricao="Área Sintética A",
                           origem=OrigemAreaInteresse.DE_CANDIDATA, area_candidata_id=candidata.id, **base)
    equipe = E.Equipe(id=_id(5), nome="Equipe Sintética 1", membros=[
        E.MembroEquipe(usuario_id="usuario-sintetico-02", papel=Papel.TECNICO_CAMPO, funcao="vistoria"),
        E.MembroEquipe(usuario_id="usuario-sintetico-03", papel=Papel.COORDENADOR, funcao="coordenação"),
    ], **base)
    definicao, hash_def = canonizar(ler_arquivo("gaema-descritivo-0.1.0.json"))
    protocolo = E.VersaoProtocolo(id=_id(6), codigo="GAEMA-DESCRITIVO", versao_semantica="0.1.0",
                                  modo=ModoProtocolo.DESCRITIVO, definicao_json=definicao,
                                  hash_definicao=hash_def, vigente_desde=date(2026, 1, 1), **base)
    demanda = E.Demanda(id=_id(7), titulo="Demanda sintética A", objetivo="Teste do fluxo",
                        alerta_ids=[alerta.id], area_candidata_id=candidata.id, area_interesse_id=area.id,
                        equipe_id=equipe.id, **base)
    campanha = E.CampanhaVistoria(id=_id(8), demanda_id=demanda.id, equipe_id=equipe.id,
                                  versao_protocolo_id=protocolo.id, objetivo="Vistoria sintética",
                                  data_planejada=date(2026, 2, 1), pacote_offline="pacote-sintetico", **base)
    ponto = E.PontoAmostral(id=_id(9), campanha_id=campanha.id, codigo="P01", latitude=-10.495,
                            longitude=-48.495, precisao_gps_m=4.0, capturado_em=T0,
                            dispositivo_id="dispositivo-sintetico", chave_idempotencia="disp-sint:P01", **base)
    obs = E.Observacao(id=_id(10), ponto_id=ponto.id, variavel=VariavelCampo.SOLO_EXPOSTO, valor_bruto="35",
                       unidade_bruta="%", valor_normalizado=35.0, unidade_normalizada="%", observado_em=T0,
                       observador_id="usuario-sintetico-02", chave_idempotencia="disp-sint:P01:obs1", **base)
    medicao = E.MedicaoPenetracao(id=_id(11), ponto_id=ponto.id, repeticao=1, profundidade_bruta="20",
                                  profundidade_unidade="cm", resistencia_bruta="1,5", resistencia_unidade="MPa",
                                  profundidade_cm=20.0, resistencia_kpa=1500.0, medido_em=T0,
                                  chave_idempotencia="disp-sint:P01:pen1", **base)
    evidencia = E.Evidencia(id=_id(12), campanha_id=campanha.id, ponto_id=ponto.id, observacao_id=obs.id,
                            categoria=CategoriaEvidencia.FOTO_SOLO, nome_arquivo_original="sintetica.jpg",
                            tipo_mime="image/jpeg", tamanho_bytes=len(FOTO_SINTETICA),
                            sha256=hashlib.sha256(FOTO_SINTETICA).hexdigest(),
                            registrado_por="usuario-sintetico-02", chave_idempotencia="disp-sint:P01:foto1",
                            **base)
    return {
        "FonteDado": [fonte], "AreaCandidata": [candidata], "Alerta": [alerta], "AreaInteresse": [area],
        "Equipe": [equipe], "VersaoProtocolo": [protocolo], "Demanda": [demanda],
        "CampanhaVistoria": [campanha], "PontoAmostral": [ponto], "Observacao": [obs],
        "MedicaoPenetracao": [medicao], "Evidencia": [evidencia],
    }


def cenario_json() -> str:
    dados = {"_aviso": "DADOS SINTÉTICOS. Nada aqui corresponde a pessoa, imóvel ou procedimento real.",
             **{k: [para_dict(x) for x in v] for k, v in cenario().items()}}
    return json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
