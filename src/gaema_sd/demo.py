"""Protótipo local de ponta a ponta, só com dados SINTÉTICOS.

Percorre: área candidata → alerta (Peça de Informação Técnica sintética) → triagem → demanda →
atribuição → vistoria (com interrupção e retomada) → fim da coleta e validação (só transições de estado; a fila e a
sincronização do aparelho não entram nesta demonstração) → validação → diagnóstico
(protótipo rotulado) → revisão → relatório HTML e PDF → tratativa → plano e marcos → monitoramento →
reemissão do relatório → reprodução do diagnóstico e conferência da auditoria.

Uso: python -m gaema_sd.demo [pasta_de_saida]
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .acesso.politica import Ator
from .dominio import entidades as E
from .dominio.enums import (
    CategoriaEvidencia,
    CriterioPriorizacao,
    Estado,
    FormatoRelatorio,
    OrigemAlerta,
    OrigemAreaInteresse,
    Papel,
    Proveniencia,
    ResultadoRevisao,
    TipoFonte,
    TipoPlano,
    TipoProvidencia,
    VariavelCampo,
)
from .nucleo import Nucleo
from .persistencia.sqlite import Repositorio
from .protocolo.definicao import ler_arquivo
from .sinteticos import FOTO_SINTETICA, POLIGONO

S = Estado
V = VariavelCampo

ATORES = {
    "analista": Ator.de("analista-sintetico", Papel.ANALISTA_TRIAGEM),
    "coord": Ator.de("coordenador-sintetico", Papel.COORDENADOR),
    "tecnico": Ator.de("tecnico-sintetico", Papel.TECNICO_CAMPO),
    "revisor": Ator.de("revisor-sintetico", Papel.REVISOR_TECNICO),
    "membro": Ator.de("membro-mp-sintetico", Papel.MEMBRO_MP),
    "auditor": Ator.de("auditor-sintetico", Papel.AUDITOR),
    "sistema": Ator.de("processo-sintetico", Papel.SISTEMA),
}

# Ponto → (lat, lon, precisão GPS, observações de presença). Valores inventados.
PONTOS = {
    "P01": (-10.4950, -48.4950, 4.0, {V.PLANTAS_INVASORAS: "sim", V.CUPINS_MONTICULO: "não",
                                      V.EROSAO_LAMINAR: "não", V.SULCOS: "não", V.RAVINAS: "não",
                                      V.VOCOROCAS: "não", V.SOLO_EXPOSTO: "não"}),
    "P02": (-10.4930, -48.4925, 5.0, {V.PLANTAS_INVASORAS: "sim", V.CUPINS_MONTICULO: "sim",
                                      V.EROSAO_LAMINAR: "não", V.SULCOS: "não", V.RAVINAS: "não",
                                      V.VOCOROCAS: "não", V.SOLO_EXPOSTO: "não"}),
    "P03": (-10.4915, -48.4980, 18.0, {V.PLANTAS_INVASORAS: "não", V.CUPINS_MONTICULO: "não",
                                       V.EROSAO_LAMINAR: "sim", V.SULCOS: "sim", V.RAVINAS: "não",
                                       V.VOCOROCAS: "não", V.SOLO_EXPOSTO: "sim"}),
}


def executar(pasta: Path, *, verbose: bool = True) -> dict:
    a = ATORES
    repo = Repositorio(str(pasta / "gaema-demo.db"))
    n = Nucleo(repo, pasta)
    log = print if verbose else (lambda *x: None)
    t0 = datetime(2026, 2, 3, 13, 0, tzinfo=timezone.utc)
    sint = {"sintetico": True}

    def passo(texto):
        log(f"  • {texto}")

    log("GAEMA SD — protótipo local (DADOS SINTÉTICOS)")
    fonte, _ = n.registrar(a["analista"], E.FonteDado(
        nome="Mosaico sintético de cobertura", tipo=TipoFonte.CAMADA_RASTER, provedor="GERADOR SINTÉTICO",
        data_referencia=date(2026, 1, 1), resolucao_m=10.0, proveniencia=Proveniencia.AUTORAL, **sint))
    cand, _ = n.registrar(a["analista"], E.AreaCandidata(
        geometria_wkt=POLIGONO, fonte_ids=[fonte.id], data_deteccao=date(2026, 1, 10),
        sinais=[E.SinalRemoto(nome="indice_sintetico", valor=0.31, fonte_id=fonte.id,
                              data_referencia=date(2026, 1, 1), metodo="valor inventado; sem limiar")],
        metodo_selecao="seleção manual sintética", **sint))
    alerta, _ = n.registrar(a["analista"], E.Alerta(
        origem=OrigemAlerta.PECA_INFORMACAO_TECNICA, descricao="Indício remoto de pastagem degradada (sintético)",
        data_alerta=date(2026, 1, 12), area_candidata_id=cand.id,
        referencia_documento="Peça de Informação Técnica SINTÉTICA nº 0001/2026", **sint))
    area, _ = n.registrar(a["analista"], E.AreaInteresse(
        geometria_wkt=POLIGONO, descricao="Área Sintética Demo", origem=OrigemAreaInteresse.DE_CANDIDATA,
        area_candidata_id=cand.id, **sint))
    equipe, _ = n.registrar(a["coord"], E.Equipe(nome="Equipe Sintética Demo", membros=[
        E.MembroEquipe(usuario_id=a["tecnico"].id, papel=Papel.TECNICO_CAMPO, funcao="vistoria"),
        E.MembroEquipe(usuario_id=a["coord"].id, papel=Papel.COORDENADOR, funcao="coordenação")], **sint))
    protocolo = n.publicar_protocolo(a["coord"], ler_arquivo("gaema-prototipo-teste-0.1.0.json"))
    demanda, _ = n.registrar(a["coord"], E.Demanda(
        titulo="Demanda sintética de demonstração", objetivo="Averiguar indício remoto de degradação (teste).",
        alerta_ids=[alerta.id], area_candidata_id=cand.id, area_interesse_id=area.id, equipe_id=equipe.id,
        criterio_priorizacao=CriterioPriorizacao.ART17_II,
        motivo_priorizacao="Priorização sintética para demonstrar o registro do critério.", **sint))
    d = demanda.id
    passo("área candidata, alerta, área de interesse, equipe, protocolo e demanda registrados")

    t = n.transitar
    t(a["sistema"], d, S.ALERTA)
    t(a["analista"], d, S.EM_TRIAGEM)
    t(a["membro"], d, S.DEMANDA_ABERTA, motivo="Abertura de averiguação (demonstração sintética)")
    t(a["coord"], d, S.ATRIBUIDA)
    campanha, _ = n.registrar(a["coord"], E.CampanhaVistoria(
        demanda_id=d, equipe_id=equipe.id, versao_protocolo_id=protocolo.id, objetivo="Vistoria sintética",
        data_planejada=date(2026, 2, 3), pacote_offline="missão sintética baixada", **sint))
    t(a["coord"], d, S.PLANEJADA)
    t(a["tecnico"], d, S.EM_CAMPO)
    passo("demanda aberta, atribuída e vistoria iniciada")

    for i, (cod, (lat, lon, prec, obs)) in enumerate(PONTOS.items()):
        ponto, _ = n.registrar(a["tecnico"], E.PontoAmostral(
            campanha_id=campanha.id, codigo=cod, latitude=lat, longitude=lon, precisao_gps_m=prec,
            capturado_em=t0 + timedelta(minutes=20 * i), dispositivo_id="dispositivo-sintetico",
            chave_idempotencia=f"demo:{cod}", **sint))
        for var, val in obs.items():
            n.registrar(a["tecnico"], E.Observacao(
                ponto_id=ponto.id, variavel=var, valor_bruto=val, unidade_bruta="presenca",
                observado_em=ponto.capturado_em, observador_id=a["tecnico"].id,
                chave_idempotencia=f"demo:{cod}:{var.value}", **sint))
        if cod == "P01":
            for rep, valor in enumerate(("1,4", "1,6", "1500"), 1):
                n.registrar(a["tecnico"], E.MedicaoPenetracao(
                    ponto_id=ponto.id, repeticao=rep, profundidade_bruta="20", profundidade_unidade="cm",
                    resistencia_bruta=valor, resistencia_unidade="kPa" if valor == "1500" else "MPa",
                    contexto_umidade="período seco (sintético)", medido_em=ponto.capturado_em,
                    chave_idempotencia=f"demo:{cod}:pen{rep}", **sint))
            n.registrar_evidencia(a["tecnico"], E.Evidencia(
                campanha_id=campanha.id, ponto_id=ponto.id, categoria=CategoriaEvidencia.FOTO_SOLO,
                nome_arquivo_original="foto-sintetica-p01.jpg", tipo_mime="image/jpeg", tamanho_bytes=1,
                sha256="", registrado_por="", capturado_em_declarado=ponto.capturado_em,
                latitude_declarada=lat, longitude_declarada=lon, chave_idempotencia="demo:P01:foto1", **sint),
                FOTO_SINTETICA)
            n.registrar(a["tecnico"], E.Observacao(
                ponto_id=ponto.id, variavel=V.HIPOTESE_ALTERNATIVA, valor_bruto="pisoteio concentrado perto do bebedouro",
                unidade_bruta="texto", observado_em=ponto.capturado_em, observador_id=a["tecnico"].id,
                chave_idempotencia="demo:P01:hip", **sint))
        if cod == "P02":
            t(a["tecnico"], d, S.COLETA_PARCIAL, motivo="Chuva forte interrompeu a coleta (sintético)")
            t(a["tecnico"], d, S.EM_CAMPO)
            passo("coleta interrompida e retomada")
    t(a["tecnico"], d, S.AGUARDANDO_SINCRONIZACAO)
    t(a["sistema"], d, S.EM_VALIDACAO)
    passo(f"{len(PONTOS)} pontos, observações, 3 repetições de penetrometria e 1 foto registrados")

    diag = n.computar_diagnostico(a["sistema"], d, campanha.id)
    t(a["coord"], d, S.AGUARDANDO_REVISAO)
    n.registrar(a["revisor"], E.RevisaoTecnica(
        diagnostico_id=diag.id, revisor_id="", resultado=ResultadoRevisao.APROVADO_COM_RESSALVAS,
        fundamentacao="Conferidas observações, medições e foto; categorias coerentes com o registrado em campo.",
        ressalvas="Ponto P03 com precisão de GPS acima do limite operacional."))
    t(a["revisor"], d, S.DIAGNOSTICO_EMITIDO)
    passo(f"diagnóstico computado ({diag.categoria_descritiva}) e revisado")

    rel_html, html1 = n.emitir_relatorio(a["revisor"], d, FormatoRelatorio.HTML)
    rel_pdf, pdf1 = n.emitir_relatorio(a["revisor"], d, FormatoRelatorio.PDF)
    passo("relatório versão 1 emitido em HTML e PDF")

    n.registrar(a["membro"], E.Providencia(
        demanda_id=d, tipo=TipoProvidencia.REUNIAO_TRATATIVA, decidido_por="",
        descricao="Designada reunião de tratativa (registro sintético).", base_tecnica_ids=[diag.id]))
    t(a["membro"], d, S.EM_TRATATIVA, motivo="Início da tratativa institucional (sintético)")
    plano, _ = n.registrar(a["coord"], E.PlanoRecuperacao(
        demanda_id=d, tipo=TipoPlano.RECUPERACAO, objetivos="Recuperação da pastagem (sintético).",
        acoes=["Controle de invasoras (sintético)", "Contenção de erosão no ponto P03 (sintético)"],
        origem_documento="plano sintético", prazo_meses=12))
    for k, prevista in enumerate((date(2026, 8, 3), date(2027, 2, 3)), 1):
        n.registrar(a["coord"], E.MarcoMonitoramento(
            plano_id=plano.id, descricao=f"Verificação semestral {k}", indicador="avanço das ações do plano",
            data_prevista=prevista))
    t(a["membro"], d, S.EM_MONITORAMENTO)
    passo("tratativa registrada, plano com 2 marcos semestrais, demanda em monitoramento")

    rel2, html2 = n.emitir_relatorio(a["coord"], d, FormatoRelatorio.HTML,
                                     motivo_reemissao="Inclusão do plano de recuperação e dos marcos de monitoramento")
    passo("relatório reemitido (versão 2), versão 1 preservada")

    reproducao = n.reproduzir_diagnostico(a["auditor"], diag.id)
    ev = next(x for x in repo.listar(E.Evidencia))
    evidencia_ok = n.verificar_evidencia(a["auditor"], ev.id)
    eventos = n.verificar_auditoria(a["auditor"])
    estado_final = repo.obter(E.Demanda, d).estado.value
    passo(f"diagnóstico reproduzido: {'sim' if reproducao['reproduzido'] else 'NÃO'}; "
          f"evidência íntegra: {'sim' if evidencia_ok else 'NÃO'}; auditoria íntegra com {eventos} eventos")
    log(f"Situação final da demanda: {estado_final}")
    log(f"Relatórios: {html1}, {pdf1}, {html2}")
    repo.fechar()
    return {"demanda_id": d, "estado_final": estado_final, "categorias": diag.categoria_descritiva,
            "relatorios": [html1, pdf1, html2], "relatorio_v2": rel2, "relatorio_v1": rel_html,
            "relatorio_pdf": rel_pdf, "reproducao": reproducao, "evidencia_integra": evidencia_ok,
            "eventos_auditoria": eventos}


def main(argv: list[str]) -> int:
    pasta = Path(argv[1]) if len(argv) > 1 else Path(tempfile.mkdtemp(prefix="gaema-demo-"))
    pasta.mkdir(parents=True, exist_ok=True)
    if any(pasta.iterdir()):
        print(f"A pasta {pasta} não está vazia; use uma pasta nova para não misturar execuções.")
        return 2
    r = executar(pasta)
    ok = r["reproducao"]["reproduzido"] and r["evidencia_integra"] and r["estado_final"] == "EM_MONITORAMENTO"
    print("Resultado: OK" if ok else "Resultado: FALHOU")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
