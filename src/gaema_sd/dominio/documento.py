"""Gera docs/dominio.md: campos e tipos vêm do código; textos descritivos vêm daqui."""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from enum import Enum

from . import entidades as E
from .serializacao import _dicas, para_dict

RETENCAO_PENDENTE = ("PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: "
                     "não excluir; inativar com motivo auditado.")

# finalidade, relações, validações específicas, regras de atualização, retenção
TEXTOS: dict[str, dict[str, str]] = {
    "AreaCandidata": dict(
        finalidade="Polígono indicado por sinal remoto como possível pastagem degradada. É só **sinal**, não conclusão.",
        relacoes="Usa 1..n FonteDado; origina 0..n Alerta, AreaInteresse e Demanda.",
        validacoes="Polígono WGS84 válido (sem auto-interseção, com área); ao menos uma fonte; todo sinal aponta "
                   "fonte listada; fora do recorte aproximado do Tocantins gera ALERTA.",
        atualizacao="Editável enquanto a Demanda estiver em CANDIDATA/ALERTA/EM_TRIAGEM; cada edição gera versão.",
        retencao=RETENCAO_PENDENTE),
    "Alerta": dict(
        finalidade="Registro de que um sinal ou notícia merece triagem.",
        relacoes="0..1 AreaCandidata; listado em Demanda.alerta_ids.",
        validacoes="Exige área candidata ou geometria própria; geometria, se houver, válida.",
        atualizacao="Edição versionada; não muda a origem.",
        retencao=RETENCAO_PENDENTE),
    "Demanda": dict(
        finalidade="Unidade de acompanhamento que percorre o fluxo de estados (docs/estados.md).",
        relacoes="0..n Alerta; 0..1 AreaCandidata, AreaInteresse, Equipe; 0..n CampanhaVistoria, Diagnostico, "
                 "Providencia, PlanoRecuperacao, Relatorio.",
        validacoes="DUPLICADA exige `duplicada_de` diferente do próprio id. `municipio` é texto como informado "
                   "(sem cadastro de municípios); não identifica imóvel.",
        atualizacao="Estado muda **só** por transição auditada; demais campos por edição versionada.",
        retencao=RETENCAO_PENDENTE),
    "AreaInteresse": dict(
        finalidade="Recorte geográfico de análise. **Não é imóvel, não é cadastro territorial e não identifica "
                   "ocupante, possuidor, proprietário, autor ou responsável.**",
        relacoes="0..1 AreaCandidata; 0..n CruzamentoTerritorial (indício espacial com camadas como SICAR, se "
                 "autorizado — não prova titularidade).",
        validacoes="Polígono válido; sobreposição entre 0 e 100%.",
        atualizacao="Edição versionada; a geometria anterior fica no histórico.",
        retencao=RETENCAO_PENDENTE),
    "Equipe": dict(
        finalidade="Conjunto de usuários designados para a vistoria.",
        relacoes="Referenciada por Demanda e CampanhaVistoria. Membros são ids de usuário, sem dados pessoais.",
        validacoes="Ao menos um membro; sem repetição; SISTEMA e ADMINISTRADOR não compõem equipe.",
        atualizacao="Edição versionada por COORDENADOR.",
        retencao=RETENCAO_PENDENTE),
    "CampanhaVistoria": dict(
        finalidade="Planejamento e execução de uma ida a campo (missão offline).",
        relacoes="1 Demanda, 1 Equipe, 1 VersaoProtocolo; 0..n PontoAmostral e Evidencia.",
        validacoes="Fim não anterior ao início; SEM_ACESSO exige descrição.",
        atualizacao="Edição versionada; protocolo vinculado não muda depois do início (regra da Fase 3).",
        retencao=RETENCAO_PENDENTE),
    "PontoAmostral": dict(
        finalidade="Local de amostragem em campo, com GPS e precisão registrada.",
        relacoes="1 CampanhaVistoria; 0..n Observacao, MedicaoPenetracao, Evidencia.",
        validacoes="Coordenada WGS84 válida e diferente de 0,0; precisão obrigatória; precisão acima do limite "
                   "operacional gera ALERTA (GPS ruim), sem bloquear; chave de envio recomendada.",
        atualizacao="Coleta é imutável na prática: correção gera nova versão com histórico. Reenvio com a mesma "
                    "chave não duplica.",
        retencao=RETENCAO_PENDENTE),
    "Observacao": dict(
        finalidade="Valor observado de uma variável de campo (invasoras, cupins, erosão, cobertura etc.).",
        relacoes="1 PontoAmostral; 0..n Evidencia.",
        validacoes="Valor bruto e unidade obrigatórios; percentuais entre 0 e 100; OUTRA exige descrição.",
        atualizacao="Valor bruto preservado; normalização explícita; correção gera versão.",
        retencao=RETENCAO_PENDENTE),
    "MedicaoPenetracao": dict(
        finalidade="Uma repetição de medição de resistência à penetração em uma profundidade.",
        relacoes="1 PontoAmostral (n repetições).",
        validacoes="Repetição ≥ 1; unidades aceitas (cm/mm/m; kPa/MPa/kgf/cm²); valores numéricos não "
                   "negativos. Nº mínimo de repetições e profundidade-padrão: PENDENTE (LA-04).",
        atualizacao="Bruto preservado; correção gera versão.",
        retencao=RETENCAO_PENDENTE),
    "Evidencia": dict(
        finalidade="Arquivo (foto, documento) com hash, autoria do registro e vínculo a ponto/observação.",
        relacoes="1 CampanhaVistoria; 0..1 PontoAmostral; 0..1 Observacao; 0..1 Evidencia substituída.",
        validacoes="Tipo real pela assinatura (JPEG/PNG/PDF), tamanho, SHA-256; coordenada declarada completa. "
                   "Hash não é prova material absoluta; EXIF/GPS são declarações do dispositivo.",
        atualizacao="**Imutável.** Arquivo original guardado por `Nucleo.registrar_evidencia`, endereçado pelo "
                    "hash e nunca sobrescrito; integridade conferível. Correção gera nova Evidencia com "
                    "`substitui_evidencia_id`.",
        retencao=RETENCAO_PENDENTE),
    "VersaoProtocolo": dict(
        finalidade="Definição versionada das regras de diagnóstico.",
        relacoes="Usada por CampanhaVistoria, Diagnostico e Relatorio.",
        validacoes="Versão semântica; hash confere com a definição; definição válida (só presença/ausência); "
                   "protótipo exige o rótulo exato "
                   "\"PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA\"; modo validado exige referência documental.",
        atualizacao="**Imutável.** Mudança gera nova versão; diagnósticos antigos continuam reproduzíveis.",
        retencao="Permanente enquanto houver diagnóstico que a referencie."),
    "Diagnostico": dict(
        finalidade="Resultado **computado** e descritivo. Só vale depois da RevisaoTecnica.",
        relacoes="1 Demanda, 1 CampanhaVistoria, 1 VersaoProtocolo; 0..n RevisaoTecnica.",
        validacoes="Hashes de protocolo e entradas; o hash confere com a fotografia gravada das entradas; "
                   "limitações obrigatórias; categoria exige rótulo de validade.",
        atualizacao="**Imutável e gravado só pelo motor** (`Nucleo.computar_diagnostico`). Guarda a fotografia "
                    "das entradas e o resultado completo, para reprodução. Recomputação gera novo Diagnostico "
                    "(`substitui_diagnostico_id`).",
        retencao=RETENCAO_PENDENTE),
    "RevisaoTecnica": dict(
        finalidade="Juízo técnico humano sobre o diagnóstico.",
        relacoes="1 Diagnostico.",
        validacoes="Fundamentação mínima; revisor independente da coleta (pré-condição de transição).",
        atualizacao="**Imutável.** Nova revisão gera novo registro.",
        retencao=RETENCAO_PENDENTE),
    "Providencia": dict(
        finalidade="Registro de decisão institucional tomada por membro do MP. O sistema não sugere nem infere.",
        relacoes="1 Demanda; referências a Diagnostico/RevisaoTecnica como base técnica.",
        validacoes="Tipo da lista de ações; descrição obrigatória; só MEMBRO_MP registra.",
        atualizacao="Edição versionada.",
        retencao=RETENCAO_PENDENTE),
    "PlanoRecuperacao": dict(
        finalidade="Plano de recuperação ou renovação acordado ou apresentado.",
        relacoes="1 Demanda; 0..n MarcoMonitoramento.",
        validacoes="Prazo positivo quando informado.",
        atualizacao="Edição versionada.",
        retencao=RETENCAO_PENDENTE),
    "MarcoMonitoramento": dict(
        finalidade="Ponto de verificação do plano.",
        relacoes="1 PlanoRecuperacao; 0..1 CampanhaVistoria de verificação.",
        validacoes="Cumprido/não cumprido exige data de verificação.",
        atualizacao="Edição versionada.",
        retencao=RETENCAO_PENDENTE),
    "Relatorio": dict(
        finalidade="Documento reproduzível emitido em HTML ou PDF por `Nucleo.emitir_relatorio`, só após "
                   "revisão técnica aprovada.",
        relacoes="1 Demanda, 1 Diagnostico, 0..1 RevisaoTecnica, 1 VersaoProtocolo; 0..1 Relatorio substituído.",
        validacoes="Hash do conteúdo; reemissão (versão > 1) exige relatório substituído e motivo.",
        atualizacao="**Imutável.** Toda correção gera nova versão.",
        retencao=RETENCAO_PENDENTE),
    "EventoAuditoria": dict(
        finalidade="Trilha de quem fez o quê, quando, e por quê.",
        relacoes="Aponta qualquer entidade por tipo e id.",
        validacoes="Encadeamento por hash; sequência contínua; detalhes sem dados sensíveis.",
        atualizacao="**Somente acréscimo** (gatilhos no banco impedem alterar ou apagar).",
        retencao="Permanente (proposta AUTORAL; confirmar com norma interna)."),
    "FonteDado": dict(
        finalidade="Proveniência de camada ou tabela usada na triagem (data, resolução, autorização).",
        relacoes="Referenciada por AreaCandidata, SinalRemoto e CruzamentoTerritorial.",
        validacoes="Resolução positiva; autorização de uso inicia como PENDENTE.",
        atualizacao="Edição versionada.",
        retencao="Permanente enquanto referenciada."),
    "IntegracaoExterna": dict(
        finalidade="Registro de integração prevista ou testada (ArcGIS etc.).",
        relacoes="Independente.",
        validacoes="ATIVA só com evidência de teste em ambiente real; guarda o NOME da variável de ambiente, "
                   "nunca o segredo.",
        atualizacao="Edição versionada; só ADMINISTRADOR.",
        retencao=RETENCAO_PENDENTE),
    "PedidoAcesso": dict(
        finalidade="Pedido de **usuário de teste** para a interface local. **Não há autenticação real (R-31)**: "
                   "aprovar só libera um papel de teste com identificador sintético.",
        relacoes="Independente. Decidido por ADMINISTRADOR; aprovado, aparece na lista de entrada da interface.",
        validacoes="Identificador `usuario-sintetico-…` (nunca nome, e-mail ou documento); papel diferente de "
                   "SISTEMA e ADMINISTRADOR; motivo com 10+ caracteres; decisão com quem, quando e motivo.",
        atualizacao="Só por `Nucleo.decidir_acesso_teste` (PENDENTE → APROVADO ou REJEITADO), auditado; "
                    "decisão não volta atrás (novo pedido = novo registro).",
        retencao=RETENCAO_PENDENTE),
}


def _nome_tipo(t) -> str:
    origem, args = typing.get_origin(t), typing.get_args(t)
    if origem in (typing.Union, types.UnionType):
        return " ou ".join(_nome_tipo(a) for a in args if a is not type(None)) + " (opcional)"
    if origem in (list, tuple):
        return f"lista de {_nome_tipo(args[0])}" if args else "lista"
    if isinstance(t, type) and issubclass(t, Enum):
        return f"{t.__name__} (lista fixa)"
    return getattr(t, "__name__", str(t))


def _tabela_campos(cls) -> list[str]:
    dicas = _dicas(cls)
    linhas = ["| Campo | Tipo | Obrigatório |", "|---|---|---|"]
    for f in dataclasses.fields(cls):
        obrig = f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
        linhas.append(f"| `{f.name}` | {_nome_tipo(dicas[f.name])} | {'sim' if obrig else 'não'} |")
    return linhas


def gerar_markdown(exemplos: dict[str, list]) -> str:
    out = [
        "# Modelo de domínio",
        "",
        "> Arquivo GERADO por `scripts/gerar_contratos.py`. Campos e tipos vêm de "
        "`src/gaema_sd/dominio/entidades.py`; textos de `src/gaema_sd/dominio/documento.py`.",
        "",
        "Nível: TESTADO LOCALMENTE (Fase 2). Proveniência: INSTITUCIONAL (lista de entidades) e AUTORAL (campos).",
        "",
        "## Distinções que o modelo garante",
        "",
        "| Conceito | Como aparece no GAEMA SD |",
        "|---|---|",
        "| Área de interesse | `AreaInteresse`: recorte geográfico de análise |",
        "| Imóvel | **Não modelado.** Nenhum campo identifica imóvel |",
        "| Cadastro territorial | Só como `CruzamentoTerritorial` (indício espacial, não titularidade) |",
        "| Ocupante, autor, responsável | **Não modelados.** Teste `test_fronteira_juridica.py` impede |",
        "| Conclusão jurídica | **Não modelada.** `Providencia` registra decisão humana |",
        "| Sinal remoto / vistoria / resultado computado / revisão / providência | "
        "`AreaCandidata`+`SinalRemoto` / `CampanhaVistoria`+`Observacao` / `Diagnostico` / `RevisaoTecnica` / "
        "`Providencia` — entidades separadas |",
        "",
        "## Campos comuns (todas as entidades, exceto EventoAuditoria)",
        "",
        "`id` (UUID), `versao` (controle de concorrência: atualizar exige a versão lida), `criado_em` (UTC), "
        "`criado_por` (preenchido pelo núcleo a partir do login, nunca pelo cliente), `atualizado_em`, "
        "`sintetico` (marca dados de teste).",
        "",
        "## Sensibilidade",
        "",
        "INTERNA: leitura por qualquer papel humano. RESTRITA: leitura só por papéis do fluxo e AUDITOR, e cada "
        "leitura gera evento de auditoria. Classificação de sigilo oficial: PENDENTE (LA-06).",
        "",
    ]
    for cls in E.ENTIDADES:
        nome = cls.__name__
        t = TEXTOS[nome]
        sens = getattr(cls, "SENSIBILIDADE", E.Sensibilidade.INTERNA).value
        out += [f"## {nome}", "", f"**Finalidade.** {t['finalidade']}", "",
                f"**Sensibilidade.** {sens}", "", *_tabela_campos(cls), "",
                f"**Relações.** {t['relacoes']}", "",
                f"**Validações.** Obrigatórios da tabela acima, mais: {t['validacoes']}", "",
                f"**Atualização.** {t['atualizacao']}", "",
                f"**Retenção.** {t['retencao']}", ""]
        if nome in exemplos:
            exemplo = json.dumps(para_dict(exemplos[nome][0]), ensure_ascii=False, indent=2)
            out += ["**Exemplo sintético.**", "", "```json", exemplo, "```", ""]
        else:
            out += ["**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).", ""]
    return "\n".join(out)
