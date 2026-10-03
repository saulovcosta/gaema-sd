"""Reúne, a partir do banco, todos os dados de um relatório (seções do §12 do prompt).

Função determinística: mesmos registros + mesmos parâmetros → mesmos dados.
Não lê imóvel, proprietário nem conclusão jurídica (não existem no modelo).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from ..dominio import entidades as E
from ..dominio.enums import ModoProtocolo, ResultadoRevisao
from ..dominio.serializacao import para_dict
from ..erros import ErroGaema, RegistroNaoEncontrado

AVISOS_FIXOS = [
    "Este relatório organiza dados técnicos. Não conclui autoria, ilicitude, dano jurídico, responsabilidade "
    "nem nexo causal; essas conclusões são sempre humanas.",
    "Sinal remoto, vistoria, resultado computado, revisão técnica e providência institucional são etapas distintas.",
    "Hash (SHA-256) comprova que um arquivo não mudou desde o registro; não é prova material absoluta.",
    "Data, hora e coordenadas de fotos (EXIF/GPS) são declarações do dispositivo, não verdade inquestionável.",
    "Dados SINTÉTICOS de desenvolvimento quando assim marcados.",
]

APROVACOES = (ResultadoRevisao.APROVADO, ResultadoRevisao.APROVADO_COM_RESSALVAS)


def _obter(repo, cls, id_):
    if not id_:
        return None
    try:
        return repo.obter(cls, id_)
    except RegistroNaoEncontrado:
        return None


def diagnostico_vigente(repo, demanda_id: str) -> Optional[E.Diagnostico]:
    diags = [d for d in repo.listar(E.Diagnostico) if d.demanda_id == demanda_id]
    substituidos = {d.substitui_diagnostico_id for d in diags if d.substitui_diagnostico_id}
    vigentes = [d for d in diags if d.id not in substituidos]
    return vigentes[-1] if vigentes else None


def revisao_aprovada(repo, demanda_id: str, diagnostico_id: str, eventos) -> Optional[E.RevisaoTecnica]:
    """Revisão que autorizou DIAGNOSTICO_EMITIDO: do revisor que fez a transição, aprovada.

    Usa a ordem de gravação (não a data declarada). Se a revisão mais recente do diagnóstico
    não for aprovação, não há revisão válida para o relatório.
    """
    transicoes = [e for e in eventos if e.acao == "TRANSICAO" and e.entidade_id == demanda_id
                  and e.estado_destino == "DIAGNOSTICO_EMITIDO"]
    revs = [r for r in repo.listar(E.RevisaoTecnica) if r.diagnostico_id == diagnostico_id]
    if not transicoes or not revs or revs[-1].resultado not in APROVACOES:
        return None
    autor = transicoes[-1].ator_id
    candidatas = [r for r in revs if r.revisor_id == autor and r.resultado in APROVACOES]
    return candidatas[-1] if candidatas else None


def montar(repo, demanda_id: str, *, numero_versao: int, gerado_em: datetime, gerado_por: str, eventos,
           motivo_reemissao: str = "", anteriores: list[E.Relatorio] = ()) -> dict:
    demanda = repo.obter(E.Demanda, demanda_id)
    diag = diagnostico_vigente(repo, demanda_id)
    if diag is None:
        raise ErroGaema("demanda sem diagnóstico")
    revisao = revisao_aprovada(repo, demanda_id, diag.id, eventos)
    if revisao is None:
        raise ErroGaema("diagnóstico sem revisão técnica aprovada válida (ou com revisão posterior não aprovada)")
    vp = repo.obter(E.VersaoProtocolo, diag.versao_protocolo_id)
    definicao = json.loads(vp.definicao_json)
    resultado = json.loads(diag.resultado_json)
    campanha = repo.obter(E.CampanhaVistoria, diag.campanha_id)
    equipe = _obter(repo, E.Equipe, campanha.equipe_id)
    area = _obter(repo, E.AreaInteresse, demanda.area_interesse_id)
    candidata = _obter(repo, E.AreaCandidata, demanda.area_candidata_id)
    alertas = [a for a in (_obter(repo, E.Alerta, i) for i in demanda.alerta_ids) if a]
    fontes = [f for f in (_obter(repo, E.FonteDado, i) for i in (candidata.fonte_ids if candidata else [])) if f]

    entradas = json.loads(diag.entradas_canonicas)
    codigos = {p["id"]: p["codigo"] for p in entradas["pontos"]}
    limite_gps = entradas["parametros"]["gps_precisao_maxima_m"]  # valor gravado com o diagnóstico
    pontos = [dict(p, gps_ruim=limite_gps is not None and (p["precisao_gps_m"] is None
                                                              or p["precisao_gps_m"] > float(limite_gps)))
              for p in sorted(entradas["pontos"], key=lambda x: x["codigo"])]
    observacoes = sorted((dict(o, ponto=codigos.get(o["ponto_id"], "?")) for o in entradas["observacoes"]),
                         key=lambda o: (o["ponto"], o["variavel"], o["id"]))
    medicoes = sorted((dict(m, ponto=codigos.get(m["ponto_id"], "?")) for m in entradas["medicoes"]),
                      key=lambda m: (m["ponto"], m["repeticao"], m["id"]))
    ev_ids = {e["id"] for e in entradas["evidencias"]}
    evidencias = []
    for e in sorted((x for x in repo.listar(E.Evidencia) if x.id in ev_ids), key=lambda x: x.id):
        evidencias.append({
            "categoria": e.categoria.value, "nome": e.nome_arquivo_original, "tipo": e.tipo_mime,
            "tamanho_bytes": e.tamanho_bytes, "sha256": e.sha256, "ponto": codigos.get(e.ponto_id, "—"),
            "observacao_id": e.observacao_id or "—", "registrado_por": e.registrado_por,
            "data_declarada": e.capturado_em_declarado.isoformat() if e.capturado_em_declarado else "—",
            "coordenada_declarada": (f"{e.latitude_declarada:.6f}, {e.longitude_declarada:.6f}"
                                     if e.latitude_declarada is not None else "—"),
            "substitui": e.substitui_evidencia_id or "—"})

    planos = [p for p in repo.listar(E.PlanoRecuperacao) if p.demanda_id == demanda.id]
    ids_plano = {p.id for p in planos}
    marcos = sorted((m for m in repo.listar(E.MarcoMonitoramento) if m.plano_id in ids_plano),
                    key=lambda m: (m.data_prevista, m.id))
    providencias = sorted((p for p in repo.listar(E.Providencia) if p.demanda_id == demanda.id),
                          key=lambda p: (p.decidido_em, p.id))

    prototipo = vp.modo is ModoProtocolo.PROTOTIPO_TESTE
    return {
        "titulo": f"Relatório de diagnóstico — {demanda.titulo}",
        "rotulo_prototipo": vp.rotulo if prototipo else "",
        "sintetico": bool(demanda.sintetico),
        "versao": {"numero": numero_versao, "gerado_em": gerado_em.isoformat(), "gerado_por": gerado_por,
                   "motivo_reemissao": motivo_reemissao,
                   "historico": [{"numero": r.numero_versao, "gerado_em": r.gerado_em.isoformat(),
                                  "hash": r.hash_conteudo, "formato": r.formato.value,
                                  "motivo": r.motivo_reemissao or "emissão inicial"} for r in anteriores]},
        "demanda": {"id": demanda.id, "titulo": demanda.titulo, "objetivo": demanda.objetivo,
                    "estado": demanda.estado.value, "referencia_interna": demanda.referencia_interna,
                    "criterio_priorizacao": demanda.criterio_priorizacao.value if demanda.criterio_priorizacao
                    else "não informado", "motivo_priorizacao": demanda.motivo_priorizacao},
        "alertas": [{"origem": a.origem.value, "descricao": a.descricao, "data": a.data_alerta.isoformat(),
                     "referencia_documento": a.referencia_documento} for a in alertas],
        "area": {"descricao": area.descricao if area else "—",
                 "geometria_wkt": (area or candidata).geometria_wkt if (area or candidata) else "",
                 "cruzamentos": [para_dict(c) for c in (area.cruzamentos if area else [])]},
        "fontes": [{"nome": f.nome, "tipo": f.tipo.value, "provedor": f.provedor,
                    "data_referencia": f.data_referencia.isoformat() if f.data_referencia else "—",
                    "resolucao_m": f.resolucao_m, "autorizacao_uso": f.autorizacao_uso,
                    "proveniencia": f.proveniencia.value} for f in fontes],
        "sinais": [para_dict(s) for s in (candidata.sinais if candidata else [])],
        "metodologia": {"protocolo": vp.codigo, "versao": vp.versao_semantica, "modo": vp.modo.value,
                        "descricao": definicao.get("descricao", ""), "hash_definicao": vp.hash_definicao,
                        "categorias": definicao.get("categorias", {}),
                        "regras": [{"id": r["id"], "categoria": r["categoria"], "descricao": r["descricao"]}
                                   for r in definicao.get("regras", [])],
                        "hash_entradas": diag.hash_entradas,
                        "metodo_penetrometria": (resultado["penetrometria"][0]["metodo"]
                                                 if resultado["penetrometria"] else "")},
        "equipe": {"nome": equipe.nome if equipe else "—",
                   "membros": [{"usuario": m.usuario_id, "papel": m.papel.value, "funcao": m.funcao}
                               for m in (equipe.membros if equipe else [])]},
        "campanha": {"objetivo": campanha.objetivo, "data_planejada": campanha.data_planejada.isoformat(),
                     "condicao_acesso": campanha.condicao_acesso.value, "nota_acesso": campanha.nota_acesso},
        "pontos": pontos, "observacoes": observacoes, "medicoes": medicoes, "evidencias": evidencias,
        "resultado": {"texto": diag.resultado_descritivo, "categoria_resumo": diag.categoria_descritiva,
                      "por_ponto": resultado["por_ponto"], "contagem": resultado["contagem_categorias"],
                      "penetrometria": resultado["penetrometria"], "rotulo_validade": diag.rotulo_validade,
                      "computado_em": diag.criado_em.isoformat()},
        "revisao": {"resultado": revisao.resultado.value, "fundamentacao": revisao.fundamentacao,
                    "ressalvas": revisao.ressalvas, "revisor": revisao.revisor_id,
                    "revisado_em": revisao.revisado_em.isoformat()},
        "limitacoes": [x for x in diag.limitacoes.splitlines() if x.strip()],
        "hipoteses_alternativas": [x for x in diag.hipoteses_alternativas.splitlines() if x.strip()],
        "recomendacoes": [{"tipo": p.tipo.value, "objetivos": p.objetivos, "acoes": list(p.acoes),
                           "prazo_meses": p.prazo_meses} for p in planos],
        "monitoramento": [{"descricao": m.descricao, "indicador": m.indicador,
                           "data_prevista": m.data_prevista.isoformat(),
                           "data_verificada": m.data_verificada.isoformat() if m.data_verificada else "—",
                           "situacao": m.situacao.value} for m in marcos],
        "providencias": [{"tipo": p.tipo.value, "descricao": p.descricao, "decidido_por": p.decidido_por,
                          "decidido_em": p.decidido_em.isoformat()} for p in providencias],
        "avisos": AVISOS_FIXOS,
    }
