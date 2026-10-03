"""Gera docs/estados.md a partir da tabela de transições (fonte única de verdade)."""

from __future__ import annotations

from ..dominio.enums import ESTADOS_EXCEPCIONAIS, ESTADOS_NORMAIS, Estado
from .maquina import MOTIVO_MINIMO, PRECONDICOES, TABELA, reversao

DESCRICAO_ESTADO = {
    Estado.CANDIDATA: "Área indicada por sinal remoto; nenhuma conclusão",
    Estado.ALERTA: "Sinal registrado como alerta para triagem",
    Estado.EM_TRIAGEM: "Análise humana do alerta",
    Estado.DEMANDA_ABERTA: "Averiguação formalmente aberta",
    Estado.ATRIBUIDA: "Equipe técnica designada",
    Estado.PLANEJADA: "Vistoria planejada, protocolo definido",
    Estado.EM_CAMPO: "Vistoria em andamento (pode estar offline)",
    Estado.COLETA_PARCIAL: "Coleta interrompida; pode ser retomada",
    Estado.AGUARDANDO_SINCRONIZACAO: "Dados coletados aguardando envio",
    Estado.EM_VALIDACAO: "Conferência dos dados recebidos",
    Estado.AGUARDANDO_REVISAO: "Diagnóstico computado aguardando revisão técnica",
    Estado.DIAGNOSTICO_EMITIDO: "Diagnóstico revisado e emitido",
    Estado.EM_TRATATIVA: "Tratativa institucional em curso",
    Estado.EM_MONITORAMENTO: "Acompanhamento de marcos",
    Estado.ENCERRADA: "Encerrada com motivo",
    Estado.REABERTA: "Reaberta com motivo",
    Estado.DUPLICADA: "Mesma área/objeto de outra demanda",
    Estado.DADOS_INSUFICIENTES: "Faltam dados para prosseguir",
    Estado.SEM_ACESSO: "Equipe não conseguiu acessar a área",
    Estado.GEOMETRIA_INCONSISTENTE: "Geometria com erro a corrigir",
    Estado.CONFLITO_SINCRONIZACAO: "Envio com versões divergentes; decisão humana",
    Estado.CANCELADA_JUSTIFICADA: "Cancelada com justificativa",
    Estado.DEVOLVIDA_COMPLEMENTACAO: "Devolvida para complementar coleta ou análise",
}


def _mermaid() -> str:
    linhas = ["```mermaid", "stateDiagram-v2", "    [*] --> CANDIDATA"]
    for (o, d), t in TABELA.items():
        if d is Estado.CANCELADA_JUSTIFICADA and o is not Estado.DADOS_INSUFICIENTES:
            continue  # omitidas no diagrama para legibilidade; constam na tabela
        if o in ESTADOS_EXCEPCIONAIS and "destino_e_estado_anterior" in t.precondicoes:
            continue
        linhas.append(f"    {o.value} --> {d.value}")
    linhas.append("    ENCERRADA --> [*]")
    linhas.append("```")
    return "\n".join(linhas)


def gerar_markdown() -> str:
    out = [
        "# Fluxo de estados da Demanda",
        "",
        "> Arquivo GERADO por `scripts/gerar_contratos.py` a partir de `src/gaema_sd/estados/maquina.py`.",
        "> Não editar à mão: o teste `tests/test_contratos.py` falha se divergir do código.",
        "",
        "Nível: TESTADO LOCALMENTE (Fase 2). Proveniência: INSTITUCIONAL (lista de estados) e AUTORAL",
        "(papéis, pré-condições e transições).",
        "",
        "## Regras gerais",
        "",
        "- Toda transição aceita gera evento de auditoria com ator, papéis, origem, destino, motivo e data.",
        "- Toda recusa (papel indevido, transição inexistente, pré-condição falha, conflito) também é auditada.",
        f"- Quando a coluna Motivo indica \"sim\", o motivo tem no mínimo {MOTIVO_MINIMO} caracteres.",
        "- Estados excepcionais com \"retorno\" só voltam ao estado anterior à exceção.",
        "- Cancelamento justificado é possível a partir de qualquer estado, exceto ENCERRADA, DUPLICADA e"
        " a própria CANCELADA_JUSTIFICADA; sai por REABERTA (só MEMBRO_MP).",
        "- ADMINISTRADOR e AUDITOR nunca movem o fluxo (separação de funções).",
        "- Reversão: indica a transição inversa existente, quando houver. Nada é apagado; reverter é nova",
        "  transição auditada.",
        "",
        "## Diagrama (sem cancelamentos e sem retornos de exceção)",
        "",
        _mermaid(),
        "",
        "## Estados",
        "",
        "| Estado | Tipo | Significado |",
        "|---|---|---|",
    ]
    for e in Estado:
        tipo = "normal" if e in ESTADOS_NORMAIS else "excepcional"
        out.append(f"| {e.value} | {tipo} | {DESCRICAO_ESTADO[e]} |")
    out += ["", "## Pré-condições", "", "| Código | Significado |", "|---|---|"]
    for nome, (desc, _) in PRECONDICOES.items():
        out.append(f"| `{nome}` | {desc} |")
    out += ["", "## Transições", "",
            "| # | Origem | Destino | Quem pode | Pré-condições | Motivo | Reversão | Descrição |",
            "|---|---|---|---|---|---|---|---|"]
    ordem = list(Estado)
    ordenadas = sorted(TABELA.items(), key=lambda kv: (ordem.index(kv[0][0]), ordem.index(kv[0][1])))
    for i, ((o, d), t) in enumerate(ordenadas, 1):
        papeis = ", ".join(sorted(p.value for p in t.papeis))
        pre = ", ".join(f"`{p}`" for p in t.precondicoes) or "—"
        rev = reversao(t)
        rev_txt = f"{d.value} → {o.value}" if rev else "não"
        out.append(f"| {i} | {o.value} | {d.value} | {papeis} | {pre} | "
                   f"{'sim' if t.exige_motivo else 'não'} | {rev_txt} | {t.descricao} |")
    out.append("")
    return "\n".join(out)
