# Pontos de integração com o Radar Ambiental e o Painel do art. 18

Nível: **ESPECIFICADO**, com um ponto **IMPLEMENTADO LOCALMENTE** (pacote de exportação em formato próprio). Proveniência: INSTITUCIONAL (Portaria GAEMA nº 001/2026, arts. 17 a 20, conforme `docs/fontes.md`, FC-15 a FC-19) e AUTORAL (desenho).

> **Nenhuma integração está declarada.** Não se conhece a arquitetura, o acesso nem os dados do Painel de Monitoramento de Pastagens Degradadas do Radar Ambiental (lacuna LA-10), nem há organização ArcGIS acessível (LA-05). Este documento lista **onde** uma troca seria possível e **o que precisa ser respondido** antes. O GAEMA SD continua sendo implementação independente (IN-06); se vai complementar o Painel ou alimentá-lo é decisão institucional.

## 0. O que a página pública do Radar mostra (consultada em 03/10/2026; fonte F14, OBSERVAÇÃO PÚBLICA)

- O Radar Ambiental é apresentado como ferramenta de livre acesso a estatísticas em tempo real sobre queimadas, desmatamentos e resíduos sólidos no Tocantins; proprietários rurais também podem consultar as apurações ambientais do MPTO. Acessa-se pelo Portal do MPTO e pelo aplicativo MPTO Cidadão.
- Lista quatro painéis (Queimadas, Gestão dos Resíduos Sólidos, Desmatamento, Bacia do Rio Formoso), embora o texto fale em três. Os links são **ArcGIS StoryMaps**.
- **Não aparece** o Painel de Monitoramento de Pastagens Degradadas do art. 18, e a página **não informa** API, exportação, documentação técnica, quem opera, quais camadas usa nem se há organização ArcGIS acessível.
- Consequências: (a) é provável que o MPTO use ArcGIS Online, mas isso não é acesso (LA-05); (b) como parte do Radar é pública, **dado enviado a um painel pode ficar visível a terceiros** (IN-09): mais um motivo para o pacote de exportação não levar geometria, texto livre nem pessoas; (c) não sabemos se o painel de pastagens ainda não foi publicado ou tem acesso restrito (IN-10).

## 1. Pontos de troca

| # | Ponto | Direção | O que trocaria | Como está hoje | Depende de |
|---|---|---|---|---|---|
| P1 | Peça de Informação Técnica (CAOMA/NIMA) | Entrada | Referência do documento e indício que originou a demanda (art. 17, caput) | Registro manual como `Alerta` de origem `PECA_INFORMACAO_TECNICA`, com campo de referência do documento | Formato e canal de entrega da Peça (desconhecidos) |
| P2 | Radar Ambiental / SIPADE-ABRAMPA | Entrada | Áreas candidatas e alertas | Cadastro manual (`AreaCandidata`, `Alerta`); nenhuma leitura automática | LA-05, LA-10, LA-07 |
| P3 | Painel do art. 18 | Saída | Situação das demandas, contagens, rótulo de validade, hashes de relatório | **Pacote de exportação em formato próprio** (`Nucleo.exportar_painel`; esquema em `schemas/exportacao-painel.schema.json`) | LA-10; base legal para compartilhar dados (RQ-70); classificação de sigilo (LA-06) |
| P4 | Camadas de referência (limites, uso do solo, SICAR, MapBiomas, PRODES, DETER) | Entrada | Cruzamentos territoriais como **indício** | Interface `CatalogoCamadas` (somente leitura); implementação `NaoConfigurado` | LA-07, LA-09, LA-05 |
| P5 | Campo (Survey123 / Field Maps) | Entrada | Pontos, observações, medições e fotos | XLSForm gerado em `adapters/arcgis/xlsform/`; tradução neutra; entrada pelo núcleo com controle de versão | LA-05; teste no Survey123 Connect e em aparelho (NÃO EXECUTADO) |
| P6 | Relatórios dos marcos do art. 20 (prévio à PGJ em out./2026; consolidado ao CPJ em mar./2027) | Saída | Atividade agregada | **Parcial:** o pacote traz contagens por estado, critério, origem e marcos; não há texto de relatório agregado | Definição do conteúdo pelo CAOMA/coordenação |

## 2. O que o pacote de exportação leva e o que não leva

Leva (por demanda): identificador técnico, situação no fluxo, critério de priorização **registrado por pessoa**, origens dos alertas, contagens (campanhas, pontos, observações, medições, evidências), categoria descritiva e **rótulo de validade** do diagnóstico, hashes do protocolo e das entradas, versão e hash dos relatórios, situação dos marcos e contagem de providências por tipo. Mais agregados.

Não leva, de propósito: geometria, coordenadas, títulos e textos livres, referência interna (pode ser número de procedimento), nomes e identificadores de pessoas, imóvel ou proprietário. A inclusão de qualquer um depende de LA-06 (classificação de sigilo) e RQ-70 (base legal). Um teste varre as chaves do pacote contra a mesma lista de termos vedados do teste de fronteira jurídica.

O critério III do art. 17 (mais de 40% de área em "degradação severa") **não é calculado** (LA-08); o pacote só repete o que uma pessoa registrou.

## 3. Perguntas objetivas para a equipe do Radar Ambiental / Painel

1. O Painel de Pastagens (art. 18) já foi publicado? Onde? Por que não consta da página pública do Radar? Recebe dados de sistemas externos, e por qual meio (arquivo, serviço, camada hospedada)?
2. Qual é o formato esperado de uma área, de um alerta e de uma Peça de Informação Técnica?
3. Quem autoriza o compartilhamento de dados de vistoria e relatórios com o Painel, e com base em quê?
4. O Painel guarda geometria e dados de vistoria? Com que classificação de sigilo e retenção?
5. Existe organização ArcGIS do MPTO, com Client ID, e quais serviços do Radar já existem?
6. Como se identifica a mesma área nos dois sistemas (identificador comum)?
7. O Painel quer apenas indicadores, ou também os relatórios? Em qual versão?
8. Há ambiente de testes separado, com dados sintéticos?

## 4. Regras que valem para qualquer troca futura

- Dados entram sempre por `Nucleo.receber_sincronizacao` (ou outro método do núcleo): acesso, validação, gravação e auditoria na mesma transação.
- Conflito nunca se resolve por "a última edição vence" (FC-12).
- Sinal remoto não vira conclusão; priorização e providência continuam sendo decisões humanas.
- Credenciais só em `.env`, nunca em código, exemplo ou log.
