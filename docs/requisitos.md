# Requisitos

**Proveniência** (de onde vem o requisito):
INSTITUCIONAL (pedido do MPTO / prompt do projeto) · OBSERVAÇÃO PÚBLICA (visto no SIPADE público) · DOCUMENTAÇÃO OFICIAL (documentação de fornecedor) · CIENTÍFICO (literatura) · AUTORAL (decisão de projeto do GAEMA SD) · PENDENTE (depende de definição externa).

**Nível de pronto:** ESPECIFICADO · IMPLEMENTADO LOCALMENTE · TESTADO LOCALMENTE · INTEGRÁVEL · VALIDADO EM HOMOLOGAÇÃO · PRONTO PARA SUBMISSÃO INSTITUCIONAL.

Níveis atualizados ao fim de cada fase.

## Ciclo e domínio

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-01 | Cobrir o ciclo: candidata → alerta → demanda → vistoria → diagnóstico → revisão → relatório → tratativa → monitoramento | INSTITUCIONAL | ESPECIFICADO |
| RQ-02 | Identificar áreas indicativas por análise remota | OBSERVAÇÃO PÚBLICA (FC-01) | ESPECIFICADO |
| RQ-03 | Registrar em campo invasoras, cupim de montículo e erosão laminar, além de outras variáveis | OBSERVAÇÃO PÚBLICA (FC-03) + INSTITUCIONAL (§11) | ESPECIFICADO |
| RQ-04 | Categorias descritivas inspiradas nos 4 cenários públicos, só em protótipo rotulado | OBSERVAÇÃO PÚBLICA (FC-04) + AUTORAL | TESTADO LOCALMENTE (protótipo rotulado, por ponto) |
| RQ-05 | Resultado orientar recuperação ou renovação, por decisão humana | OBSERVAÇÃO PÚBLICA (FC-05) + INSTITUCIONAL | ESPECIFICADO |
| RQ-06 | Modelo com as 20 entidades do §7 | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-07 | Nunca confundir área de interesse, imóvel, cadastro, ocupante, autor, responsável e conclusão jurídica | INSTITUCIONAL | TESTADO LOCALMENTE (`test_fronteira_juridica.py`) |
| RQ-08 | Máquina de estados com 16 estados normais e 7 excepcionais, papéis, pré-condições, motivo, auditoria e reversão | INSTITUCIONAL | TESTADO LOCALMENTE (`test_estados.py`) |

## Triagem remota

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-10 | Pipeline configurável: ingestão, proveniência, data, resolução, qualidade, harmonização, seleção, deduplicação, priorização, cruzamentos, revisão humana | INSTITUCIONAL | ESPECIFICADO |
| RQ-11 | NDVI como sinal configurável, sem limiar padrão | CIENTÍFICO (Valle Júnior et al., 2019, citado em F2) + PENDENTE (limiar) | ESPECIFICADO |
| RQ-12 | Fontes MapBiomas, INPE/TerraBrasilis, PRODES, DETER, SICAR apenas avaliáveis, sem integração presumida | INSTITUCIONAL + PENDENTE (autorização) | ESPECIFICADO |
| RQ-13 | Sinal remoto nunca é conclusão técnica final | INSTITUCIONAL | TESTADO LOCALMENTE (sem revisão aprovada não há DIAGNOSTICO_EMITIDO) |

## Campo e sincronização

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-20 | Vistoria offline-first com retomada | INSTITUCIONAL + DOCUMENTAÇÃO OFICIAL (FC-09) | ESPECIFICADO |
| RQ-21 | GPS com precisão registrada; alerta de GPS ruim por limite configurável | INSTITUCIONAL + AUTORAL (limite) | TESTADO LOCALMENTE |
| RQ-22 | Sem perda silenciosa nem duplicidade ao sincronizar | INSTITUCIONAL + DOCUMENTAÇÃO OFICIAL (FC-12) | TESTADO LOCALMENTE no núcleo (conflito e idempotência); sincronização de campo na Fase 4 |
| RQ-23 | Mapa base offline em formatos aceitos pelo Survey123 quando usado o adaptador | DOCUMENTAÇÃO OFICIAL (FC-11) | ESPECIFICADO |
| RQ-24 | Formulário de vistoria exportável em XLSForm | DOCUMENTAÇÃO OFICIAL (FC-10) | ESPECIFICADO |

## Protocolo, relatório e evidências

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-30 | Motor de protocolo versionado, com entradas brutas, unidades, explicação de regras e reprodução histórica | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-31 | Protótipo rotulado "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-32 | Parâmetros de penetrometria (profundidade, repetições) | PENDENTE (LA-04) | ESPECIFICADO |
| RQ-33 | Não automatizar autoria, ilicitude, dano jurídico, responsabilidade, nexo causal | INSTITUCIONAL | TESTADO LOCALMENTE (ausência de campos) |
| RQ-34 | Relatório reproduzível e versionado em HTML e PDF | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-35 | Evidência com original, hash, data, autoria, vínculo a observação e ponto | INSTITUCIONAL | TESTADO LOCALMENTE |

## Segurança

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-40 | Controle de acesso no núcleo, por papel, com menor privilégio | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-41 | Trilha de auditoria íntegra e verificável | INSTITUCIONAL + AUTORAL (encadeamento por hash) | TESTADO LOCALMENTE |
| RQ-42 | Segredos fora do código | INSTITUCIONAL | TESTADO LOCALMENTE (varredura e .gitignore) |
| RQ-43 | Validação de anexos (tipo real, tamanho, hash) | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-44 | Backup lógico com restauração testada | INSTITUCIONAL | ESPECIFICADO |
| RQ-45 | Retenção documental por entidade | PENDENTE (LA-06) | ESPECIFICADO |

## Integração ArcGIS

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-50 | Adaptadores como interface e documentação, sem execução, até haver organização ArcGIS | INSTITUCIONAL + PENDENTE (LA-05) | ESPECIFICADO |
| RQ-51 | Experience Builder Dev Edition exige conta ArcGIS Online/Enterprise e Client ID | DOCUMENTAÇÃO OFICIAL (FC-08) | ESPECIFICADO |

## Portaria GAEMA nº 001/2026 — Linha de Atuação em Solos Degradados (arts. 16 a 20)

Fonte F13. Regra geral: os critérios e instrumentos da Portaria orientam **decisões humanas**; o sistema organiza indícios, indicadores e registros, sem deflagrar intervenção, sem modelar imóvel ou proprietário e sem produzir conclusão jurídica (DEC-006, DE-07).

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-60 | Escopo do módulo alinhado à Linha de Atuação em Solos Degradados, vigência 2026/2028 (art. 16) | INSTITUCIONAL | ESPECIFICADO |
| RQ-61 | Registrar a Peça de Informação Técnica do CAOMA/NIMA como origem de alerta ou demanda, com referência ao documento (art. 17, caput) | INSTITUCIONAL | TESTADO LOCALMENTE |
| RQ-62 | Registrar a prioridade atribuída por pessoa, indicando o critério do art. 17 (I a IV) invocado e o motivo; o sistema não atribui prioridade sozinho | INSTITUCIONAL + AUTORAL | TESTADO LOCALMENTE (registro humano do critério) |
| RQ-63 | Critério I (erosão ativa de grande porte, especialmente voçorocas, nas regiões indicadas, com risco a curso d'água perene ou rodovia pública): o sistema registra voçorocas observadas e cruzamentos com camadas autorizadas (regiões, hidrografia, rodovias) como indícios; o "risco comprovado" é juízo técnico humano | INSTITUCIONAL + PENDENTE (camadas e critério de risco, LA-09) | ESPECIFICADO |
| RQ-64 | Critério II (pastagem degradada atestada pelo CAOMA/NIMA com impacto supramunicipal): cruzamento com camadas de municípios e bacias como indício; a atestação é registro de origem externa | INSTITUCIONAL + PENDENTE (camadas autorizadas, LA-09) | ESPECIFICADO |
| RQ-65 | Critério III (acima de 1.000 ha e mais de 40% em degradação severa): **não implementado**; depende de protocolo científico validado para "degradação severa" (LA-08). A área de referência, quando houver, vem de área de interesse ou cruzamento informado por pessoa, nunca de cadastro de imóvel | INSTITUCIONAL + **PENDENTE** | ESPECIFICADO |
| RQ-66 | Critério IV (casos encaminhados por Promotorias, com anuência do Promotor Natural, ligados a mineração de grande escala): registrar o encaminhamento como origem e a anuência como providência humana | INSTITUCIONAL | IMPLEMENTADO LOCALMENTE (origem do alerta; anuência como providência) |
| RQ-67 | Dados do GAEMA SD exportáveis em formato aberto para eventual uso no Painel do art. 18; nenhuma integração declarada sem ambiente real | INSTITUCIONAL + PENDENTE (LA-10) | ESPECIFICADO |
| RQ-68 | Apoio à capacitação (art. 18, parágrafo único): guia de uso e cenário sintético de treinamento | INSTITUCIONAL + AUTORAL | IMPLEMENTADO LOCALMENTE (cenário de demonstração `scripts/demo.sh`; guia de uso pendente) |
| RQ-69 | Diagnóstico de solo auditável e indicadores de avanço de PRAD aferidos semestralmente (art. 19, I): relatório reproduzível com trilha de auditoria e marcos de monitoramento com periodicidade configurável | INSTITUCIONAL | IMPLEMENTADO LOCALMENTE (relatório auditável e marcos; aferição semestral é decisão humana) |
| RQ-70 | Recomendações, comunicações a instituições financeiras e ações judiciais (art. 19, II a IV) são providências humanas registradas como `Providencia`; o sistema não gera minuta nem conclusão. Compartilhar dados com terceiros exige base legal e exportação controlada | INSTITUCIONAL + PENDENTE (base legal do compartilhamento) | ESPECIFICADO |
| RQ-71 | Relatórios agregados de atividade para os marcos de out./2026 (relatório prévio à PGJ) e mar./2027 (relatório consolidado ao CPJ), e acompanhamento dos marcos do art. 20 | INSTITUCIONAL | ESPECIFICADO |
