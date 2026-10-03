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
| RQ-04 | Categorias descritivas inspiradas nos 4 cenários públicos, só em protótipo rotulado | OBSERVAÇÃO PÚBLICA (FC-04) + AUTORAL | ESPECIFICADO |
| RQ-05 | Resultado orientar recuperação ou renovação, por decisão humana | OBSERVAÇÃO PÚBLICA (FC-05) + INSTITUCIONAL | ESPECIFICADO |
| RQ-06 | Modelo com as 20 entidades do §7 | INSTITUCIONAL | ver ESTADO.md |
| RQ-07 | Nunca confundir área de interesse, imóvel, cadastro, ocupante, autor, responsável e conclusão jurídica | INSTITUCIONAL | ver ESTADO.md |
| RQ-08 | Máquina de estados com 16 estados normais e 7 excepcionais, papéis, pré-condições, motivo, auditoria e reversão | INSTITUCIONAL | ver ESTADO.md |

## Triagem remota

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-10 | Pipeline configurável: ingestão, proveniência, data, resolução, qualidade, harmonização, seleção, deduplicação, priorização, cruzamentos, revisão humana | INSTITUCIONAL | ESPECIFICADO |
| RQ-11 | NDVI como sinal configurável, sem limiar padrão | CIENTÍFICO (Valle Júnior et al., 2019, citado em F2) + PENDENTE (limiar) | ESPECIFICADO |
| RQ-12 | Fontes MapBiomas, INPE/TerraBrasilis, PRODES, DETER, SICAR apenas avaliáveis, sem integração presumida | INSTITUCIONAL + PENDENTE (autorização) | ESPECIFICADO |
| RQ-13 | Sinal remoto nunca é conclusão técnica final | INSTITUCIONAL | ver ESTADO.md |

## Campo e sincronização

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-20 | Vistoria offline-first com retomada | INSTITUCIONAL + DOCUMENTAÇÃO OFICIAL (FC-09) | ESPECIFICADO |
| RQ-21 | GPS com precisão registrada; alerta de GPS ruim por limite configurável | INSTITUCIONAL + AUTORAL (limite) | ver ESTADO.md |
| RQ-22 | Sem perda silenciosa nem duplicidade ao sincronizar | INSTITUCIONAL + DOCUMENTAÇÃO OFICIAL (FC-12) | ver ESTADO.md |
| RQ-23 | Mapa base offline em formatos aceitos pelo Survey123 quando usado o adaptador | DOCUMENTAÇÃO OFICIAL (FC-11) | ESPECIFICADO |
| RQ-24 | Formulário de vistoria exportável em XLSForm | DOCUMENTAÇÃO OFICIAL (FC-10) | ESPECIFICADO |

## Protocolo, relatório e evidências

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-30 | Motor de protocolo versionado, com entradas brutas, unidades, explicação de regras e reprodução histórica | INSTITUCIONAL | ESPECIFICADO |
| RQ-31 | Protótipo rotulado "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" | INSTITUCIONAL | ESPECIFICADO |
| RQ-32 | Parâmetros de penetrometria (profundidade, repetições) | PENDENTE (LA-04) | ESPECIFICADO |
| RQ-33 | Não automatizar autoria, ilicitude, dano jurídico, responsabilidade, nexo causal | INSTITUCIONAL | ver ESTADO.md |
| RQ-34 | Relatório reproduzível e versionado em HTML e PDF | INSTITUCIONAL | ESPECIFICADO |
| RQ-35 | Evidência com original, hash, data, autoria, vínculo a observação e ponto | INSTITUCIONAL | ver ESTADO.md |

## Segurança

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-40 | Controle de acesso no núcleo, por papel, com menor privilégio | INSTITUCIONAL | ver ESTADO.md |
| RQ-41 | Trilha de auditoria íntegra e verificável | INSTITUCIONAL + AUTORAL (encadeamento por hash) | ver ESTADO.md |
| RQ-42 | Segredos fora do código | INSTITUCIONAL | ver ESTADO.md |
| RQ-43 | Validação de anexos (tipo real, tamanho, hash) | INSTITUCIONAL | ver ESTADO.md |
| RQ-44 | Backup lógico com restauração testada | INSTITUCIONAL | ESPECIFICADO |
| RQ-45 | Retenção documental por entidade | PENDENTE (LA-06) | ESPECIFICADO |

## Integração ArcGIS

| ID | Requisito | Proveniência | Nível |
|---|---|---|---|
| RQ-50 | Adaptadores como interface e documentação, sem execução, até haver organização ArcGIS | INSTITUCIONAL + PENDENTE (LA-05) | ESPECIFICADO |
| RQ-51 | Experience Builder Dev Edition exige conta ArcGIS Online/Enterprise e Client ID | DOCUMENTAÇÃO OFICIAL (FC-08) | ESPECIFICADO |
