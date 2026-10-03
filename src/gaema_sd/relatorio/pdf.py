"""Relatório em PDF (reportlab). `invariant=1`: mesmos dados → mesmo arquivo, byte a byte."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .mapa import ALTURA, LARGURA, projecao

_EST = getSampleStyleSheet()
_P = ParagraphStyle("p", parent=_EST["BodyText"], fontSize=9, leading=11.5)
_PEQ = ParagraphStyle("peq", parent=_P, fontSize=7.5, leading=9)
_H1 = ParagraphStyle("h1", parent=_EST["Heading1"], fontSize=15)
_H2 = ParagraphStyle("h2", parent=_EST["Heading2"], fontSize=11.5, spaceBefore=10)
_FAIXA = ParagraphStyle("faixa", parent=_P, fontSize=11, textColor=colors.HexColor("#8a1c1c"),
                        borderColor=colors.HexColor("#8a1c1c"), borderWidth=1.5, borderPadding=6,
                        alignment=1, spaceBefore=6, spaceAfter=10)


def _t(valor) -> str:
    return escape("—" if valor is None or valor == "" else str(valor))


def _par(texto, estilo=_P) -> Paragraph:
    return Paragraph(_t(texto), estilo)


def _tabela(cabecalho: list[str], linhas: list[list], larguras=None) -> Table:
    dados = [[Paragraph(f"<b>{_t(c)}</b>", _PEQ) for c in cabecalho]]
    dados += [[Paragraph(_t(v), _PEQ) for v in linha] for linha in linhas] or \
        [[Paragraph("Nenhum registro.", _PEQ)] + [""] * (len(cabecalho) - 1)]
    t = Table(dados, colWidths=larguras, repeatRows=1, spaceBefore=4, spaceAfter=8)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _mapa(dados: dict) -> Drawing:
    projetar, aneis = projecao(dados["area"]["geometria_wkt"], dados["pontos"])
    fator = 0.75
    d = Drawing(LARGURA * fator, ALTURA * fator)
    d.add(Rect(0, 0, LARGURA * fator, ALTURA * fator, fillColor=colors.white, strokeColor=colors.grey))
    if projetar:
        for anel in aneis:
            pts = []
            for c in anel:
                x, y = projetar(*c[:2])
                pts += [x * fator, (ALTURA - y) * fator]
            d.add(Polygon(pts, fillColor=colors.HexColor("#e8f0e0"), strokeColor=colors.HexColor("#2f5d1e")))
        for p in dados["pontos"]:
            x, y = projetar(p["longitude"], p["latitude"])
            d.add(Circle(x * fator, (ALTURA - y) * fator, 3.5, fillColor=colors.HexColor("#8a1c1c")))
            d.add(String(x * fator + 6, (ALTURA - y) * fator + 4, p["codigo"], fontSize=8, fontName="Helvetica"))
    d.add(String(6, 4, "Esquema sem escala; norte para cima", fontSize=7, fontName="Helvetica"))
    return d


def renderizar(dados: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title=f"{dados['titulo']} (versão {dados['versao']['numero']})",
                            author="GAEMA SD (protótipo local)", subject="Relatório de diagnóstico",
                            lang="pt-BR", invariant=1)
    s = [Paragraph(_t(dados["titulo"]), _H1)]
    if dados["rotulo_prototipo"]:
        s.append(Paragraph(f"<b>{_t(dados['rotulo_prototipo'])}</b>", _FAIXA))
    if dados["sintetico"]:
        s.append(Paragraph("<b>DADOS SINTÉTICOS — documento de desenvolvimento</b>", _FAIXA))
    v = dados["versao"]
    s.append(_par(f"Versão do relatório: {v['numero']} · emitido em {v['gerado_em']} por {v['gerado_por']}"
                  + (f" · motivo da reemissão: {v['motivo_reemissao']}" if v["motivo_reemissao"] else "")))

    dm = dados["demanda"]
    s += [Paragraph("1. Identificação da demanda", _H2),
          _tabela(["Campo", "Valor"], [["Identificador", dm["id"]], ["Título", dm["titulo"]],
                                       ["Situação no fluxo", dm["estado"]],
                                       ["Referência interna", dm["referencia_interna"]],
                                       ["Critério de priorização (escolhido por pessoa)",
                                        f"{dm['criterio_priorizacao']} {dm['motivo_priorizacao']}".strip()]],
                  [5 * cm, 12.6 * cm]),
          _tabela(["Origem", "Data", "Descrição", "Documento de referência"],
                  [[a["origem"], a["data"], a["descricao"], a["referencia_documento"]] for a in dados["alertas"]]),
          Paragraph("2. Objetivo", _H2), _par(dm["objetivo"]),
          _par(f"Objetivo da vistoria: {dados['campanha']['objetivo']} (planejada para "
               f"{dados['campanha']['data_planejada']}; acesso: {dados['campanha']['condicao_acesso']})."),
          Paragraph("3. Área e mapa", _H2),
          _par(f"Área de interesse: {dados['area']['descricao']}. Recorte geográfico de análise; não identifica "
               "imóvel, cadastro, ocupante ou responsável."), _mapa(dados),
          Paragraph("4. Fontes de dados", _H2),
          _tabela(["Nome", "Tipo", "Provedor", "Data", "Autorização", "Proveniência"],
                  [[f["nome"], f["tipo"], f["provedor"], f["data_referencia"], f["autorizacao_uso"],
                    f["proveniencia"]] for f in dados["fontes"]]),
          Paragraph("5. Metodologia e versão do protocolo", _H2)]
    m = dados["metodologia"]
    s += [_par(f"Protocolo {m['protocolo']}, versão {m['versao']}, modo {m['modo']}. {m['descricao']}"),
          _par(f"Hash da definição do protocolo: {m['hash_definicao']}", _PEQ),
          _par(f"Hash das entradas de campo usadas: {m['hash_entradas']}", _PEQ)]
    if m["regras"]:
        s.append(_tabela(["Regra", "Categoria", "Descrição"],
                         [[r["id"], f"{r['categoria']} — {m['categorias'][r['categoria']]}", r["descricao"]]
                          for r in m["regras"]]))
    if m["metodo_penetrometria"]:
        s.append(_par(f"Penetrometria: {m['metodo_penetrometria']}"))
    s += [Paragraph("6. Equipe", _H2),
          _tabela(["Usuário", "Papel", "Função"],
                  [[x["usuario"], x["papel"], x["funcao"]] for x in dados["equipe"]["membros"]]),
          Paragraph("7. Pontos amostrados", _H2),
          _tabela(["Ponto", "Latitude", "Longitude", "Precisão GPS (m)", "Capturado em"],
                  [[p["codigo"], f"{p['latitude']:.6f}", f"{p['longitude']:.6f}",
                    f"{p['precisao_gps_m']}" + (" (acima do limite operacional)" if p["gps_ruim"] else ""),
                    p["capturado_em"]] for p in dados["pontos"]]),
          Paragraph("8. Observações de campo", _H2),
          _tabela(["Ponto", "Variável", "Valor", "Unidade", "Nota"],
                  [[o["ponto"], o["variavel"], o["valor_bruto"], o["unidade_bruta"], o["nota"]]
                   for o in dados["observacoes"]]),
          Paragraph("9. Medições de resistência à penetração", _H2),
          _tabela(["Ponto", "Repetição", "Profundidade", "Resistência", "Umidade"],
                  [[x["ponto"], x["repeticao"], f"{x['profundidade_bruta']} {x['profundidade_unidade']}",
                    f"{x['resistencia_bruta']} {x['resistencia_unidade']}", x["contexto_umidade"]]
                   for x in dados["medicoes"]])]
    if dados["resultado"]["penetrometria"]:
        s.append(_tabela(["Ponto", "Prof. (cm)", "Repetições", "Mín. (kPa)", "Máx. (kPa)", "Média (kPa)"],
                         [[x["ponto"], x["profundidade_cm"], x["n"], x["min_kpa"], x["max_kpa"], x["media_kpa"]]
                          for x in dados["resultado"]["penetrometria"]]))
    s += [Paragraph("10. Evidências", _H2),
          _tabela(["Categoria", "Arquivo", "Ponto", "Data declarada", "Coord. declarada", "SHA-256"],
                  [[e["categoria"], f"{e['nome']} ({e['tipo']}, {e['tamanho_bytes']} bytes)", e["ponto"],
                    e["data_declarada"], e["coordenada_declarada"], e["sha256"]] for e in dados["evidencias"]],
                  [2.4 * cm, 3.4 * cm, 1.2 * cm, 2.6 * cm, 2.6 * cm, 5.4 * cm]),
          Paragraph("11. Resultado computado", _H2), _par(dados["resultado"]["rotulo_validade"])]
    r = dados["resultado"]
    if r["categoria_resumo"]:
        s.append(_par(f"Categorias por ponto: {r['categoria_resumo']}."))
    if dados["rotulo_prototipo"]:
        s.append(_tabela(["Ponto", "Categoria descritiva", "Regras disparadas", "Não avaliáveis (motivo)"],
                         [[p["codigo"], p["categoria"], ", ".join(p["disparadas"]) or "nenhuma",
                           "; ".join(f"{a}: {b}" for a, b in p["nao_avaliaveis"]) or "—"] for p in r["por_ponto"]]))
    s += [_par(linha) for linha in r["texto"].splitlines()]
    rv = dados["revisao"]
    s += [Paragraph("12. Revisão técnica", _H2),
          _par(f"Resultado: {rv['resultado']}, por {rv['revisor']} em {rv['revisado_em']}."),
          _par(f"Fundamentação: {rv['fundamentacao']}")]
    if rv["ressalvas"]:
        s.append(_par(f"Ressalvas: {rv['ressalvas']}"))
    s.append(Paragraph("13. Limitações", _H2))
    s += [_par(f"• {x}") for x in dados["limitacoes"]]
    s += [_par(f"Hipótese alternativa: {x}") for x in dados["hipoteses_alternativas"]]
    s.append(Paragraph("14. Recomendações (plano de recuperação ou renovação)", _H2))
    if not dados["recomendacoes"]:
        s.append(_par("Nenhum plano registrado até a emissão desta versão."))
    for rec in dados["recomendacoes"]:
        s.append(_par(f"{rec['tipo']}: {rec['objetivos']}"))
        s += [_par(f"• {a}") for a in rec["acoes"]]
    if dados["providencias"]:
        s.append(_tabela(["Tipo", "Descrição", "Decidido por", "Em"],
                         [[p["tipo"], p["descricao"], p["decidido_por"], p["decidido_em"]]
                          for p in dados["providencias"]]))
    s += [Paragraph("15. Monitoramento", _H2),
          _tabela(["Marco", "Indicador", "Previsto", "Verificado", "Situação"],
                  [[x["descricao"], x["indicador"], x["data_prevista"], x["data_verificada"], x["situacao"]]
                   for x in dados["monitoramento"]]),
          Paragraph("16. Versão do relatório e histórico", _H2),
          _par(f"Esta é a versão {v['numero']}. Toda correção gera nova versão; as anteriores são preservadas.")]
    if v["historico"]:
        s.append(_tabela(["Versão", "Formato", "Emitida em", "Motivo", "Hash"],
                         [[h["numero"], h["formato"], h["gerado_em"], h["motivo"], h["hash"]]
                          for h in v["historico"]]))
    s += [Paragraph("Avisos", _H2)] + [_par(f"• {a}") for a in dados["avisos"]]
    s += [Spacer(1, 8), _par("GAEMA SD — protótipo local. Não integrado a sistemas institucionais.", _PEQ)]
    doc.build(s)
    return buf.getvalue()
