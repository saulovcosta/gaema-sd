# Fontes consultadas

Data de acesso de todas as fontes: **03/10/2026**, a partir do ambiente de nuvem do Claude Code (acesso por proxy HTTPS).
Regra: fonte que não abriu é LACUNA. Lacuna não é preenchida com suposição.

## 1. Resultado da leitura

| # | Fonte | URL | Situação | O que foi possível confirmar |
|---|---|---|---|---|
| F1 | SIPADE, página estática | https://www.sipade.com.br/assets/static/home/index.html | ABRIU | "solução completa para auxiliar os órgãos públicos na identificação e diagnóstico de pastagens degradadas"; web identifica "áreas indicativas"; mobile identifica "o grau de degradação"; usuário informa "presença de plantas invasoras, presença de cupim de montículo, presença de erosão laminar entre outras"; relatório em 4 cenários; IFTM em parceria com MPMG; orienta "a necessidade da recuperação ou renovação das pastagens" |
| F2 | Artigo SBSI 2023 | https://sol.sbc.org.br/index.php/sbsi_estendido/article/view/24595 | ABRIU | Título "SIPADE: Uma Solução do Brasil para Apoio ao Diagnóstico de Pastagens Degradadas"; autores Tomaz, França, Maciel, Orbolato, Ponciano, Faria, Valera; DOI 10.5753/sbsi_estendido.2023.229360; "em implantação na região da Bacia do Rio Uberaba"; referência a Valle Júnior et al. (2019), "Diagnosis of degraded pastures using an improved ndvi-based remote sensing approach" |
| F3 / F11 | Vídeo "Apresentação SIPADE" | https://www.youtube.com/watch?v=7FpfZxlR380 | **ABRIU (via cópia do usuário)** | YouTube bloqueia acesso automático (exige login anti-robô). Analisado em 03/10/2026 a partir de cópia MP4 compartilhada pelo usuário no Google Drive: quadros e transcrição automática. Achados em `docs/sipade-videos.md` |
| F4 | Claude Code, boas práticas | https://code.claude.com/docs/en/best-practices | ABRIU | Dar ao agente uma verificação executável (testes); explorar, planejar, implementar, commitar; CLAUDE.md curto e operacional |
| F5 | Claude Code, nuvem | https://code.claude.com/docs/en/claude-code-on-the-web | ABRIU | Sessão roda em máquina isolada e efêmera; trabalho precisa de commit e push; rede e variáveis configuradas no ambiente |
| F6 | Experience Builder Developer Edition | https://developers.arcgis.com/experience-builder/guide/install-guide/ | ABRIU | Usa Node.js; compatível com ArcGIS Online e ArcGIS Enterprise 10.6+; "requires a Client ID"; roda localmente em `https://localhost:3001/`; contas ArcGIS Location Platform não dão acesso |
| F7 | Survey123, perguntas gerais | https://doc.arcgis.com/en/survey123/get-started/faqgeneral.htm | ABRIU | "Surveys continue to work … while disconnected"; geocodificação de endereço e funções que buscam dados remotos falham sem rede; formulários em XLSForm |
| F8 | Survey123, mapas base offline | https://doc.arcgis.com/en/survey123/create/connect/preparebasemaps.htm | ABRIU | Formatos TPKX/TPK, VTPK, MMPK, todos em Web Mercator Auxiliary Sphere; vínculo recomendado por "Linked Content" no Survey123 Connect |
| F9 | Field Maps, sincronização | https://doc.arcgis.com/en/field-maps/android/use-maps/sync.htm | ABRIU | Camada hospedada: "the last edit synced is preserved"; dados versionados: conflito resolvido por reconcile/post do administrador |
| F10 / F12 | Vídeo "Video Tutorial Projeto SIPADE" | https://www.youtube.com/watch?v=NtxHv9Dzgzk | **ABRIU (via cópia do usuário)** | Canal "Mauro Borges França" (homônimo de coautor de F2; identidade não confirmada). Analisado em 03/10/2026 a partir de cópia MP4 compartilhada pelo usuário: telas e diagramas de processo. Achados em `docs/sipade-videos.md` |
| F13 | Portaria GAEMA nº 001/2026 (Coordenação do CAOMA/GAEMA, 15/09/2026) | Documento fornecido pelo usuário (PDF, 13 p.); **não** copiado para o repositório | ABRIU | Cap. V, arts. 16 a 20: institui a Linha de Atuação em Solos Degradados e o Plano de Trabalho do GAEMA SD 2026/2028 (gatilhos de intervenção, Painel de Monitoramento, instrumentos, cronograma). Os demais capítulos tratam de outras frentes e não foram incorporados. Registro sem nomes, números de procedimento ou dados pessoais |
| F14 | Página pública do Radar Ambiental (CAOMA/MPTO) | https://www.mpto.mp.br/caop-do-meio-ambiente/radar-ambiental/ | ABRIU (03/10/2026, por `curl` pelo proxy do ambiente; o leitor de páginas do assistente recebeu 403 do site) | OBSERVAÇÃO PÚBLICA: ver FC-20 a FC-24 |

## 2. Matriz da Fase 1

### 2.1 FATOS CONFIRMADOS (com fonte)

| ID | Fato | Fonte |
|---|---|---|
| FC-01 | SIPADE identifica áreas indicativas de pastagem degradada por sistema web | F1 |
| FC-02 | SIPADE identifica grau de degradação em campo por sistema mobile | F1 |
| FC-03 | Usuário informa invasoras, cupim de montículo, erosão laminar "entre outras" variáveis | F1 |
| FC-04 | Relatório em quatro cenários: produtiva; invasoras (início); invasoras e cupins (médio); solo desnudo e erosão intensa (degradada) | F1 |
| FC-05 | Resultado orienta recuperação ou renovação | F1 |
| FC-06 | Desenvolvido por IFTM e MPMG | F1 |
| FC-07a | Vídeos públicos mostram: fluxo registro de pontos → averiguação → tratativa; formulário de campo com cupim, invasora, solo exposto, erosão, gado, altura do pasto, tipo de solo, formação geológica e resistência à penetração com contexto seco/chuvoso/chuva em 48 h; relatório em PDF com tabela de parâmetros e fotos | F11, F12 (detalhes em `docs/sipade-videos.md`) |
| FC-07b | Vídeo F11 mostra 3 estados (degradada, em degradação, não degradada), enquanto o site F1 descreve 4 cenários | F1, F11 |
| FC-07 | Implantação na Bacia do Rio Uberaba (MG); cita NDVI de Valle Júnior et al. (2019) | F2 |
| FC-08 | Experience Builder Dev Edition exige conta ArcGIS Online/Enterprise e Client ID e roda no computador do desenvolvedor | F6 |
| FC-09 | Survey123 funciona offline; perguntas que dependem de serviço hospedado falham sem rede | F7 |
| FC-10 | Survey123 aceita XLSForm | F7 |
| FC-11 | Survey123 aceita mapa base offline TPKX/TPK/VTPK/MMPK em Web Mercator | F8 |
| FC-12 | Field Maps com camada hospedada: vale a última edição sincronizada | F9 |
| FC-13 | Ambiente de nuvem é efêmero; persistência só por commit e push | F5 |
| FC-14 | Fica instituída a Linha de Atuação em Solos Degradados (GAEMA SD), Plano de Trabalho 2026/2028, a partir da publicação da Portaria (art. 16) | F13 |
| FC-15 | A intervenção é deflagrada a partir de Peças de Informação Técnica do CAOMA/NIMA com base na plataforma SIPADE/Radar Ambiental, com quatro critérios de priorização (art. 17, I a IV) | F13 |
| FC-16 | Critério do art. 17, III: empreendimentos rurais acima de 1.000 ha com mais de 40% da área rural consolidada em "estágio de degradação severa do solo, conforme classificação da plataforma SIPADE" | F13 |
| FC-17 | Painel de Monitoramento de Pastagens Degradadas, no Radar Ambiental do aplicativo MPTO Cidadão, desenvolvido a partir da customização da plataforma SIPADE/ABRAMPA, é o instrumento primário de identificação de alvos, geração de evidências e subsídio probatório (art. 18); capacitação coordenada com o CAOMA (art. 18, parágrafo único) | F13 |
| FC-18 | Instrumentos: IC e TAC com PRAD, diagnóstico de solo auditável e indicadores de avanço aferidos semestralmente pelo CAOMA; recomendações ao órgão ambiental estadual; articulação com instituições financeiras do crédito rural; ACP; demais da Resolução CPJ nº 009/2022 (art. 19) | F13 |
| FC-19 | Cronograma (art. 20): capacitação na plataforma até o 2º sem./2026; primeiras Peças de Informação Técnica, notificações administrativas nos casos prioritários até o 1º sem./2027; primeiros TACs com PRAD até o 2º sem./2027; relatório prévio à PGJ em out./2026; relatório consolidado ao CPJ em mar./2027 | F13 |
| FC-20 | A página descreve o Radar Ambiental como ferramenta de livre acesso, a todos os cidadãos, a estatísticas atualizadas em tempo real sobre queimadas, desmatamentos e destinação de resíduos sólidos no Tocantins | F14 (OBSERVAÇÃO PÚBLICA) |
| FC-21 | A página diz que proprietários rurais também podem consultar, na plataforma, as apurações ambientais realizadas pelo MPTO | F14 |
| FC-22 | A página diz que o Radar "é composto por três paineis" e pode ser acessado no Portal do MPTO e no aplicativo MPTO Cidadão; ela lista quatro painéis (Queimadas, Gestão dos Resíduos Sólidos, Desmatamento, Bacia do Rio Formoso), além do título "Contra Fogo" | F14 |
| FC-23 | Os links dos painéis listados apontam para ArcGIS StoryMaps (`storymaps.arcgis.com`) | F14 |
| FC-24 | **Ausências:** o Painel de Monitoramento de Pastagens Degradadas não aparece na página em 03/10/2026; a página não informa API, exportação, documentação técnica, quem opera o Radar, quais camadas usa nem se há organização ArcGIS própria | F14 |

### 2.2 INFERÊNCIAS (raciocínio próprio, não fato)

| ID | Inferência | Base |
|---|---|---|
| IN-01 | As variáveis do SIPADE alimentam uma regra que leva aos 4 cenários, mas **a regra, pesos e limiares não são públicos** | FC-03, FC-04 |
| IN-02 | "Last edit wins" do Field Maps pode apagar silenciosamente edição concorrente; o GAEMA SD precisa de controle de versão próprio para detectar conflito | FC-12 |
| IN-03 | Sem organização ArcGIS acessível, nenhuma integração ArcGIS pode ser testada nesta fase | FC-08, inventário |
| IN-05 | "GAEMA SD" tem dois sentidos: na Portaria, é a frente de atuação de Promotores de Justiça; neste repositório, é o nome provisório do módulo de software | F13 |
| IN-06 | O Painel do art. 18 nasce da customização da plataforma SIPADE/ABRAMPA; este repositório continua sendo implementação independente, e a relação entre ambos depende de decisão institucional | F13, DEC-001 |
| IN-07 | Os critérios do art. 17 orientam a priorização humana a partir de Peças de Informação Técnica; o software pode organizar indícios e indicadores, mas não deflagra intervenção | F13, DEC-006 |
| IN-08 | Os painéis públicos do Radar são publicados como ArcGIS StoryMaps; é provável que o MPTO use ArcGIS Online, mas isso não dá acesso, nem prova Client ID, serviços ou camadas utilizáveis (LA-05 continua aberta) | FC-23 |
| IN-09 | Como o Radar é público e proprietários rurais consultam apurações, dado enviado a um painel pode ficar visível a terceiros; reforça LA-06 e RQ-70 e a decisão de exportar sem geometria, texto livre nem pessoas | FC-20, FC-21 |
| IN-10 | Que o painel de pastagens do art. 18 não conste da página pública pode significar que ainda não foi publicado ou que tem acesso restrito; não há como saber pela página | FC-24 |
| IN-04 | O cenário 4 do SIPADE menciona "dano ambiental"; no GAEMA SD essa expressão não pode ser saída automática, porque dano jurídico é conclusão humana | FC-04, prompt §11 |

### 2.3 LACUNAS

| ID | Lacuna | Consequência |
|---|---|---|
| LA-01 | Faixas numéricas vistas nas telas do SIPADE (altura do pasto, <50%, >10 mm) não têm fundamentação pública | Não adotadas como limiar (V-04) |
| LA-02 | Fórmulas, pesos e limiares do SIPADE | Protótipo próprio rotulado "SEM VALIDADE CIENTÍFICA" |
| LA-03 | Limiar de NDVI aplicável ao Cerrado tocantinense | NDVI só como sinal configurável, sem valor padrão |
| LA-04 | Protocolo de campo validado (nº de pontos, repetições, profundidade de penetrometria) | Parâmetros configuráveis, marcados PENDENTE |
| LA-05 | Organização ArcGIS do MPTO, Client ID, serviços existentes do Radar Ambiental | Adaptadores só como interface e documentação |
| LA-06 | Normas internas de retenção documental e de classificação de sigilo do MPTO | Retenção marcada PENDENTE em `docs/dominio.md` |
| LA-08 | Critério técnico de "degradação severa" da plataforma SIPADE (art. 17, III) não é público | Gatilho de 40% fica PENDENTE de protocolo científico validado; o sistema não o calcula nem o sinaliza |
| LA-09 | Operacionalização de "risco comprovado de assoreamento", "impacto supramunicipal" e dos recortes Serras Gerais, Jalapão e MATOPIBA (art. 17, I e II) | Dependem de camadas oficiais autorizadas e de juízo técnico humano |
| LA-10 | Arquitetura, acesso e dados do Painel do art. 18 (a página pública do Radar não o lista: FC-24) | Nenhuma integração declarada |
| LA-07 | Autorização formal de uso de SICAR, MapBiomas, PRODES, DETER | Nenhuma ingestão real; só desenho do pipeline |

### 2.4 DECISÕES (detalhes em `docs/decisoes.md`)

| ID | Decisão |
|---|---|
| DE-01 | Arquitetura opção (c): núcleo independente de ArcGIS, com adaptadores |
| DE-02 | Núcleo em Python 3.11 + SQLite + pytest + shapely |
| DE-03 | Somente dados sintéticos |
| DE-04 | Protocolo em modo descritivo; protótipo rotulado "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" |
| DE-05 | Controle de concorrência otimista (número de versão) e idempotência por chave de cliente, em vez de "última edição vence" |
| DE-06 | Nenhum campo do modelo representa autoria, ilicitude, nexo causal ou responsabilidade |
| DE-07 | Portaria GAEMA nº 001/2026 (arts. 16 a 20) incorporada como fonte INSTITUCIONAL de requisitos de priorização, instrumentos e cronograma, mantidas DEC-001 (implementação independente) e DEC-006 (sem imóvel, proprietário ou conclusão jurídica). Teses jurídicas da Portaria não viram saída do sistema |

## 3. Inventário do ambiente (03/10/2026)

| Item | Situação |
|---|---|
| Repositório | `saulovcosta/gaema-sd`, só `README.md` e 1 commit inicial |
| Branch de trabalho | `claude/intelligent-faraday-q1h4nb` |
| Python | 3.11.15 |
| SQLite | nativo do Python |
| Bibliotecas | pytest 9.1.1 e shapely 2.1.2 instaladas pelo PyPI; Jinja2 3.1.6 e jsonschema 4.26.0 já presentes |
| ArcGIS | nenhuma conta, Client ID ou serviço acessível |
| Rede | saída HTTPS por proxy; PyPI acessível |
