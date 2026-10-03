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

### 2.2 INFERÊNCIAS (raciocínio próprio, não fato)

| ID | Inferência | Base |
|---|---|---|
| IN-01 | As variáveis do SIPADE alimentam uma regra que leva aos 4 cenários, mas **a regra, pesos e limiares não são públicos** | FC-03, FC-04 |
| IN-02 | "Last edit wins" do Field Maps pode apagar silenciosamente edição concorrente; o GAEMA SD precisa de controle de versão próprio para detectar conflito | FC-12 |
| IN-03 | Sem organização ArcGIS acessível, nenhuma integração ArcGIS pode ser testada nesta fase | FC-08, inventário |
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
