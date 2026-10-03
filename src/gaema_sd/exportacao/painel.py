"""Montagem do pacote de exportação (somente leitura sobre o repositório).

O que NÃO entra, de propósito (sensibilidade e retenção pendentes, LA-06; RQ-70 base legal): geometria,
coordenadas, títulos e textos livres, referência interna (pode ser número de procedimento), nomes e
identificadores de pessoas, imóvel ou proprietário. Entram identificadores técnicos, estados, contagens,
rótulos de validade e hashes. Critério de priorização é registro humano; nada aqui o calcula.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

from ..dominio import entidades as E
from ..dominio.serializacao import json_canonico

FORMATO = "gaema-sd-exportacao"
VERSAO_FORMATO = "0.1"
AVISO = ("Formato PRÓPRIO do GAEMA SD, não é o do Painel do art. 18 nem o do Radar Ambiental. Protótipo; sem validade "
         "científica ou jurídica. Sem geometria, coordenadas, nomes ou textos livres. Nenhuma integração declarada.")


def _contagem(itens) -> dict[str, int]:
    return dict(sorted(Counter(itens).items()))


def _demanda(repo, d: E.Demanda, alertas, campanhas, pontos, obs, med, evid, diag, rels, planos, marcos, provs) -> dict:
    ids_campanha = {c.id for c in campanhas if c.demanda_id == d.id}
    ids_ponto = {p.id for p in pontos if p.campanha_id in ids_campanha}
    substituidos = {x.substitui_diagnostico_id for x in diag if x.demanda_id == d.id and x.substitui_diagnostico_id}
    vigente = next((x for x in diag if x.demanda_id == d.id and x.id not in substituidos), None)
    ultimos: dict[str, E.Relatorio] = {}
    for r in sorted((r for r in rels if r.demanda_id == d.id), key=lambda r: r.numero_versao):
        ultimos[r.formato.value] = r
    ids_plano = {p.id for p in planos if p.demanda_id == d.id}
    return {
        "demanda_id": d.id,
        "sintetico": d.sintetico,
        "estado": d.estado.value,
        "criterio_priorizacao": d.criterio_priorizacao.value if d.criterio_priorizacao else None,
        "origens_alerta": sorted({a.origem.value for a in alertas if a.id in d.alerta_ids}),
        "campanhas": len(ids_campanha),
        "pontos": len(ids_ponto),
        "observacoes": sum(o.ponto_id in ids_ponto for o in obs),
        "medicoes_penetracao": sum(m.ponto_id in ids_ponto for m in med),
        "evidencias": sum(e.campanha_id in ids_campanha for e in evid),
        "diagnostico": None if vigente is None else {
            "categoria_descritiva": vigente.categoria_descritiva,
            "rotulo_validade": vigente.rotulo_validade,
            "hash_definicao_protocolo": vigente.hash_definicao_protocolo,
            "hash_entradas": vigente.hash_entradas},
        "relatorios": [{"formato": f, "numero_versao": r.numero_versao, "hash_conteudo": r.hash_conteudo,
                        "gerado_em": r.gerado_em.isoformat()} for f, r in sorted(ultimos.items())],
        "providencias_por_tipo": _contagem(p.tipo.value for p in provs if p.demanda_id == d.id),
        "marcos": [{"situacao": m.situacao.value, "data_prevista": m.data_prevista.isoformat(),
                    "data_verificada": m.data_verificada.isoformat() if m.data_verificada else None}
                   for m in marcos if m.plano_id in ids_plano],
    }


def montar_pacote(repo, *, gerado_por: str, gerado_em: datetime, demanda_ids: list[str] | None = None) -> dict:
    todas = repo.listar(E.Demanda)
    if demanda_ids is not None:
        pedidas = set(demanda_ids)
        todas = [d for d in todas if d.id in pedidas]
    dados = dict(
        alertas=repo.listar(E.Alerta), campanhas=repo.listar(E.CampanhaVistoria), pontos=repo.listar(E.PontoAmostral),
        obs=repo.listar(E.Observacao), med=repo.listar(E.MedicaoPenetracao), evid=repo.listar(E.Evidencia),
        diag=repo.listar(E.Diagnostico), rels=repo.listar(E.Relatorio), planos=repo.listar(E.PlanoRecuperacao),
        marcos=repo.listar(E.MarcoMonitoramento), provs=repo.listar(E.Providencia))
    demandas = [_demanda(repo, d, **dados) for d in todas]
    marcos = [m for d in demandas for m in d["marcos"]]
    return {
        "formato": FORMATO, "versao_formato": VERSAO_FORMATO, "aviso": AVISO,
        "gerado_em": gerado_em.isoformat(), "gerado_por": gerado_por,
        "todos_sinteticos": all(d["sintetico"] for d in demandas),
        "demandas": demandas,
        "agregados": {
            "demandas": len(demandas),
            "por_estado": _contagem(d["estado"] for d in demandas),
            "por_criterio_priorizacao": _contagem(d["criterio_priorizacao"] or "NAO_REGISTRADO" for d in demandas),
            "por_origem_alerta": _contagem(o for d in demandas for o in d["origens_alerta"]),
            "marcos_por_situacao": _contagem(m["situacao"] for m in marcos),
            "com_relatorio_emitido": sum(bool(d["relatorios"]) for d in demandas),
        },
    }


def serializar(pacote: dict) -> bytes:
    """JSON canônico (mesmo pacote → mesmos bytes)."""
    return (json_canonico(pacote) + "\n").encode("utf-8")


def esquema_json() -> dict:
    texto = {"type": "string"}
    inteiro = {"type": "integer", "minimum": 0}
    contagem = {"type": "object", "additionalProperties": inteiro}
    demanda = {
        "type": "object", "additionalProperties": False,
        "required": ["demanda_id", "sintetico", "estado", "criterio_priorizacao", "origens_alerta", "campanhas",
                     "pontos", "observacoes", "medicoes_penetracao", "evidencias", "diagnostico", "relatorios",
                     "providencias_por_tipo", "marcos"],
        "properties": {
            "demanda_id": texto, "sintetico": {"type": "boolean"}, "estado": texto,
            "criterio_priorizacao": {"type": ["string", "null"]},
            "origens_alerta": {"type": "array", "items": texto},
            "campanhas": inteiro, "pontos": inteiro, "observacoes": inteiro, "medicoes_penetracao": inteiro,
            "evidencias": inteiro,
            "diagnostico": {"type": ["object", "null"], "additionalProperties": False,
                            "required": ["categoria_descritiva", "rotulo_validade", "hash_definicao_protocolo",
                                         "hash_entradas"],
                            "properties": {k: texto for k in ("categoria_descritiva", "rotulo_validade",
                                                              "hash_definicao_protocolo", "hash_entradas")}},
            "relatorios": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["formato", "numero_versao", "hash_conteudo", "gerado_em"],
                "properties": {"formato": texto, "numero_versao": inteiro, "hash_conteudo": texto,
                               "gerado_em": texto}}},
            "providencias_por_tipo": contagem,
            "marcos": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["situacao", "data_prevista", "data_verificada"],
                "properties": {"situacao": texto, "data_prevista": texto,
                               "data_verificada": {"type": ["string", "null"]}}}},
        }}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Pacote de exportação GAEMA SD (formato próprio)",
        "description": AVISO,
        "type": "object", "additionalProperties": False,
        "required": ["formato", "versao_formato", "aviso", "gerado_em", "gerado_por", "todos_sinteticos",
                     "demandas", "agregados"],
        "properties": {
            "formato": {"const": FORMATO}, "versao_formato": {"const": VERSAO_FORMATO}, "aviso": texto,
            "gerado_em": texto, "gerado_por": texto, "todos_sinteticos": {"type": "boolean"},
            "demandas": {"type": "array", "items": demanda},
            "agregados": {"type": "object", "additionalProperties": False,
                          "required": ["demandas", "por_estado", "por_criterio_priorizacao", "por_origem_alerta",
                                       "marcos_por_situacao", "com_relatorio_emitido"],
                          "properties": {"demandas": inteiro, "por_estado": contagem,
                                         "por_criterio_priorizacao": contagem, "por_origem_alerta": contagem,
                                         "marcos_por_situacao": contagem, "com_relatorio_emitido": inteiro}},
        }}
