# Guia de uso para capacitação dos membros

Nível: **IMPLEMENTADO LOCALMENTE** (documento escrito; **nenhuma turma foi atendida**). Proveniência: INSTITUCIONAL (Portaria GAEMA nº 001/2026, arts. 18 e 20, conforme `docs/fontes.md`) e AUTORAL (texto e exercícios).

> **Aviso.** O GAEMA SD é um **protótipo**, com **dados sintéticos**. Nenhum resultado tem validade científica ou jurídica. Não está integrado ao ArcGIS, ao Radar Ambiental, ao Painel do art. 18 nem a sistema algum do MPTO. Este guia é material de apoio e **não substitui** a capacitação coordenada com o CAOMA (art. 18, parágrafo único).

## 1. Para que serve o sistema

Ele **organiza**: áreas suspeitas, alertas, demandas, vistorias de campo, medições, fotos, o diagnóstico descritivo, a revisão técnica, o relatório e o acompanhamento de marcos.

Ele **não conclui** autoria, ilicitude, dano jurídico, responsabilidade ou nexo causal. Essas conclusões são sempre humanas. Também **não decide** a prioridade de uma demanda nem aplica o critério de "degradação severa" do art. 17, III (o critério técnico ainda não é conhecido).

## 2. Cinco coisas que não se confundem

| Coisa | O que é | O que **não** é |
|---|---|---|
| Sinal remoto | Indício vindo de imagem de satélite ou de alerta | Constatação. Não prova nada sozinho |
| Vistoria | O que a equipe viu e mediu em campo, com data, local e fotos | Conclusão técnica |
| Resultado computado | Descrição calculada pelo protocolo, com os dados usados guardados | Laudo. No protótipo, vem com a faixa "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" |
| Revisão técnica | Análise de uma pessoa habilitada sobre o resultado | Providência |
| Providência | Decisão institucional humana (reunião, TAC, ação etc.) | Efeito automático do sistema |

## 3. Quem faz o quê

| Papel | Em linguagem comum |
|---|---|
| Analista de triagem | Registra fontes, áreas candidatas e alertas; faz a triagem |
| Coordenador | Forma a equipe, publica o protocolo, planeja campanhas (o técnico de campo também pode planejar), decide conflitos de sincronização, pode emitir relatório e também pode abrir a averiguação |
| Técnico de campo | Coleta no campo (pontos, observações, medições, fotos) e envia os dados |
| Revisor técnico | Revisa o diagnóstico e libera a emissão. Quem participou da coleta não pode revisar |
| Membro do Ministério Público | Abre a averiguação (o coordenador também pode), registra providências, conduz tratativa e monitoramento |
| Auditor | Confere a trilha de auditoria. Não move o fluxo |
| Administrador | Cuida do ambiente. Não move o fluxo |
| Sistema | Executa passos automáticos (por exemplo, computar o diagnóstico) |

Cada ação é conferida pelo **papel**, no núcleo do sistema, e fica registrada na trilha de auditoria.

## 4. O caminho de uma demanda

| Situação | O que significa para você |
|---|---|
| CANDIDATA / ALERTA | Há um indício. Nenhuma conclusão |
| EM_TRIAGEM | Uma pessoa analisa o alerta |
| DEMANDA_ABERTA | A averiguação foi formalmente aberta (decisão do membro ou do coordenador, com motivo) |
| ATRIBUIDA / PLANEJADA | Há equipe, protocolo e campanha de vistoria (a passagem para PLANEJADA é do coordenador; o técnico de campo também pode fazê-la) |
| EM_CAMPO / COLETA_PARCIAL | Vistoria em andamento; pode ser interrompida e retomada |
| AGUARDANDO_SINCRONIZACAO | Dados coletados esperando envio ao sistema central |
| EM_VALIDACAO | Conferência dos dados recebidos |
| AGUARDANDO_REVISAO | Diagnóstico computado, à espera do revisor |
| DIAGNOSTICO_EMITIDO | Revisado; o relatório pode ser emitido |
| EM_TRATATIVA / EM_MONITORAMENTO | Providências humanas e acompanhamento de marcos |
| ENCERRADA / REABERTA | Fim ou retomada, sempre com motivo |

Situações **excepcionais** (o fluxo para até alguém decidir): duplicada, dados insuficientes, sem acesso à área, geometria inconsistente, **conflito de sincronização**, cancelada com justificativa, devolvida para complementação. O diagrama completo está em `docs/estados.md`.

Regras do fluxo: toda mudança fica registrada com quem fez, quando e por quê; nada é apagado; reverter é uma nova mudança registrada.

## 5. A priorização do art. 17

O sistema permite **registrar** qual critério (I a IV) uma pessoa invocou e por quê. Ele não calcula nem sugere. Os critérios I e II dependem de camadas oficiais ainda não autorizadas; o critério III depende de um critério técnico ainda desconhecido; o IV é o encaminhamento de Promotoria.

## 6. Como ler o relatório

O relatório tem 16 seções e uma lista de avisos. Leia nesta ordem:

1. **As faixas do topo.** "DADOS SINTÉTICOS" e "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" dizem o que o documento é.
2. **Metodologia e versão do protocolo (seção 5).** Mostra qual protocolo e quais dados geraram o resultado (por meio de códigos de conferência, os "hashes").
3. **Pontos, observações e medições (seções 7 a 9).** São os valores brutos, como foram registrados. Atenção à precisão do GPS: acima do limite operacional há um aviso.
4. **Evidências (seção 10).** Fotos e documentos guardados como original, cada um com seu código de conferência.
5. **Resultado computado e revisão técnica (seções 11 e 12).** O resultado é descritivo; quem o valida é o revisor.
6. **Limitações (seção 13).** Leia sempre. Dizem o que o resultado não permite concluir.
7. **Versão (seção 16).** Corrigir um relatório gera uma versão nova com motivo; as anteriores continuam guardadas.

## 7. O que é um conflito de sincronização

Acontece quando o aparelho de campo e o sistema central alteraram o **mesmo registro** a partir da mesma versão. O sistema **não escolhe**: guarda as duas versões e espera o coordenador. Enquanto o conflito estiver aberto, a validação dos dados fica bloqueada, e novos envios daquele registro ficam retidos no aparelho.

A demanda passa para "conflito de sincronização" só quando a demanda está em AGUARDANDO_SINCRONIZACAO. Nas outras situações (por exemplo, EM_CAMPO) a situação não muda, mas o conflito continua aberto e visível.

O coordenador decide, com motivo escrito:
- **Manter a versão do sistema central**: o aparelho passa a ter a versão central e as correções que ficaram na fila para aquele registro são descartadas (com registro).
- **Aceitar a versão do aparelho**: ela vira a versão corrente do sistema central, o histórico preserva a anterior. Só é possível se o registro não mudou na central depois do conflito; se mudou, só se pode manter a central.

Depois de decidir, o coordenador precisa mover a demanda de volta para "aguardando sincronização": o sistema não faz isso sozinho.

A decisão chega ao aparelho quando ele consulta o sistema central. Hoje essa consulta existe como função testada com rede simulada, mas ainda não há comando nem rotina automática para executá-la. Evidências (fotos e documentos) não são alteradas: só se mantém a versão central.

## 8. Exercícios com o cenário sintético

Peça à equipe técnica para executar a demonstração (`scripts/demo.sh`) e abrir os arquivos da pasta `relatorios` da saída. Tudo ali é inventado.

1. Em que situação a demanda terminou?
2. Quantos pontos amostrais foram coletados e qual deles ficou com precisão de GPS acima do limite operacional?
3. A coleta foi interrompida em algum momento? O que a equipe fez?
4. Quantas versões do relatório existem, em quais formatos?
5. Qual é o rótulo de validade do resultado computado?
6. Quem pode registrar uma providência? E quem pode revisar o diagnóstico?
7. Por que o sistema não diz se houve infração?

### Gabarito

1. Em **monitoramento** (EM_MONITORAMENTO).
2. **Três** pontos (P01, P02, P03). O **P03** tem precisão de 18 m, acima do limite operacional de 10 m (valor provisório, sem fundamento científico).
3. Sim: depois de coletar o P02 e antes do P03, por chuva forte (registro sintético). A demanda foi para COLETA_PARCIAL e voltou a EM_CAMPO.
4. **Três arquivos**: HTML versão 1 e versão 2 (esta com o plano de recuperação e os marcos, e o motivo da reemissão) e PDF versão 1.
5. "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA".
6. Providência: o **membro do Ministério Público**. Revisão: o **revisor técnico**, que não pode ter participado da coleta.
7. Porque essa conclusão é sempre humana; o sistema só organiza indícios e registros.

## 9. Boas práticas

- Registre o **motivo** com clareza: ele fica na trilha de auditoria. Não escreva dado pessoal sensível no campo de motivo; o sistema mascara alguns formatos de CPF e de e-mail, mas não reconhece nome de pessoa, CNPJ nem telefone com máscara.
- Não trate o resultado do protótipo como laudo.
- Em dúvida sobre prioridade, critério ou providência, a decisão é humana e deve ser registrada como tal.
- Trabalhe só com dados sintéticos enquanto a instituição não concluir a homologação do sistema (ver `docs/homologacao.md`).

## 10. Glossário

- **Hash (código de conferência):** sequência que muda se o arquivo ou o dado mudar. Serve para provar que nada foi alterado.
- **Trilha de auditoria:** registro de tudo o que foi feito, por quem e quando, que denuncia adulteração.
- **Sincronização:** envio dos dados do aparelho de campo ao sistema central.
- **Protocolo:** conjunto de regras que descreve o que foi observado. No protótipo, só presença e ausência.
- **Evidência:** foto ou documento guardado como original.

## 11. Limites desta etapa

Não há tela: a operação é por linha de comando. Não há rede real, aplicativo de campo, ArcGIS, Radar ou Painel. As pendências estão em `docs/pendencias.md`; o que falta demonstrar, em `docs/homologacao.md`; os pontos de troca previstos, em `docs/integracao-radar-painel.md`.
