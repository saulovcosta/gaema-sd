# SIPADE — observações dos vídeos públicos

Fontes: F11 = "Apresentação SIPADE" (YouTube `7FpfZxlR380`, canal SIPADE, 2 min 42 s); F12 = "Video Tutorial Projeto SIPADE" (YouTube `NtxHv9Dzgzk`, canal Mauro Borges França, 13 min 36 s).
Acesso em 03/10/2026, por cópias MP4 fornecidas pelo usuário no Google Drive (o YouTube bloqueou o acesso automático). Análise feita por quadros extraídos (ffmpeg) e transcrição automática do áudio (faster-whisper, modelo "small"). A transcrição tem erros de reconhecimento (ex.: "SIPAD" por "SIPADE"); trechos duvidosos estão marcados.

Proveniência de tudo o que está aqui: **OBSERVAÇÃO PÚBLICA**. Nada disso é protocolo validado. Faixas numéricas vistas nas telas são escolhas de interface do SIPADE, **não** limiares científicos adotados pelo GAEMA SD. Nenhum texto, tela ou identidade visual foi copiado para o projeto.

## 1. O que os vídeos mostram

### 1.1 Fluxo geral (F11, narração e tela "SIPADE visão geral")
Três pilares: **Registro de Pontos** (o sistema registra uma coordenada e a relaciona à propriedade/proprietário; o registro vira uma demanda; a narração diz que áreas possivelmente degradadas são identificadas "de forma automática … por meio de satélites"), **Averiguação** (a demanda passa a uma instituição competente, que averigua in loco pelo app; na narração, policiais ambientais) e **Tratativa** (dados da visita viram relatórios técnicos e gerenciais; orientação aos proprietários sobre renovação e recuperação).

### 1.2 Categorias (F11)
A animação mostra **três** estados: degradada, em degradação, não degradada. O site oficial (F1) descreve **quatro** cenários. As fontes públicas divergem; o GAEMA SD mantém categorias configuráveis no protocolo.

### 1.3 Macroprocesso e papéis (F12)
"Macroprocesso do sistema SIPADE": 1) cadastrar usuários → 2) cadastrar demanda → 3) registrar diagnósticos, com cadastro de propriedades ligado às etapas 2 e 3.
Raias dos diagramas: **Policial** (app mobile: solicita cadastro, faz agendamento de visitas a partir da lista, preenche o diagnóstico em campo, sincroniza) e **Procuradores** (aplicação web: liberam cadastro, cadastram demanda, pré-cadastram propriedade, gerenciam diagnósticos fechados). Um "superusuário" aprova os acessos.

### 1.4 Offline e sincronização (F12)
Notas dos diagramas: o agendamento deve ser feito em local com internet estável; em campo "a aplicação estará off line"; depois o policial sincroniza e pode encaminhar o relatório em PDF por e-mail ou outro canal.

### 1.5 Telas do app (F12, apresentadas como especificação: "o sistema será…")
- Login com e-mail e senha; solicitação de acesso aprovada por superusuário.
- Menu: minhas demandas, listar demandas (o usuário se atribui uma demanda), relatórios, sobre.
- Atualizar propriedade (em campo).
- **Diagnosticar área**: nome da área; coordenadas pelo GPS do aparelho; até três fotos por área; chaves de presença de **cupim**, **invasora**, **solo exposto**, **erosão** e **gado**; **altura do pasto** em três faixas (menos de 0,10 m; de 0,1 a 0,2 m; mais de 0,2 m).
- **Diagnosticar área (continuação)**: **tipo de solo** (consulta a mapa de solos da UFV, 2014); **formação geológica** (Mapa Geológico do Brasil); "valor máximo médio" da resistência à penetração, com contexto **chuvoso**, **seco** e **precipitação nas últimas 48 h > 10 mm**; ajuda sobre como calcular a média.
- Relatório da área; um diagnóstico pode ter várias áreas na mesma propriedade.

### 1.6 Telas da web (F12)
Menus Dashboard, Usuários, Propriedades e Demanda. A lista de propriedades mostra nome da propriedade, nome do proprietário, CPF do proprietário, endereço, município e geolocalização. A lista de usuários mostra nome, CPF, instituição, cargo e e-mail.

### 1.7 Relatório (F11)
PDF de 9 páginas, "Relatório do Diagnóstico #N", logomarca do MPMG. A tabela "Dados do Diagnóstico" traz: hábito de crescimento (<0,2), resistência à penetração (Alto), solo exposto (Baixo: <50%), amostras 1 a 3 (Baixo: <50%), erosão laminar (Não), nível de infestação por cupim (Baixo), presença de invasora (Alto). As páginas seguintes trazem fotos por amostra.
No app: campo "Resistência a penetração (KPaF)", "Formação geológica: Grupo Bauru, Formação Uberaba", botões "Interromper visita" e "Próximo".

### 1.8 Contexto (F11)
Mapa da Bacia do Rio Uberaba (ano 2019), com classes "pasto degradado" e "pasto sadio". Parceria com o "Projeto TERAMA" ("Tecnologia para altas produtividades"), que apoia produtores na recuperação. A instituição do TERAMA na narração está ininteligível. A narração cita números nacionais de área de pastagem e degradação; esses números **não** foram conferidos e não são usados.

## 2. Consequências para o GAEMA SD

| # | Observação | Decisão no GAEMA SD | Situação |
|---|---|---|---|
| V-01 | Fluxo registro → averiguação → tratativa | Confirma o ciclo já modelado (candidata/alerta → demanda/vistoria → tratativa) | Já atendido |
| V-02 | Variáveis de campo: altura do pasto, tipo de solo, formação geológica, chuva nas últimas 48 h | Incluídas em `VariavelCampo` (ALTURA_PASTO, TIPO_SOLO, FORMACAO_GEOLOGICA, PRECIPITACAO_RECENTE) | TESTADO LOCALMENTE |
| V-03 | Cupim, invasora, solo exposto, erosão, gado | Já existiam (CUPINS_MONTICULO, PLANTAS_INVASORAS, SOLO_EXPOSTO, EROSAO_*, ANIMAIS_PASTEJO) | Já atendido |
| V-04 | Faixas fixas (<0,10 m; 0,1–0,2 m; >0,2 m; <50%; >10 mm) | **Não adotadas** como limiar. Podem entrar no protótipo como categorias configuráveis rotuladas "OBSERVAÇÃO PÚBLICA, não validado" | PENDENTE (Fase 3) |
| V-05 | 3 categorias no vídeo × 4 no site | Categorias do protocolo configuráveis por versão | Já previsto em `docs/protocolo.md` |
| V-06 | Média de repetições da penetrometria e contexto seco/chuvoso | O GAEMA SD guarda cada repetição bruta (`MedicaoPenetracao`) e calcula agregados no motor, registrando o método | Fase 3 |
| V-07 | Até três fotos por área | Não adotado como limite; o número mínimo ou máximo de fotos depende do protocolo | PENDENTE |
| V-08 | Demanda ligada a propriedade e proprietário, com CPF e endereço | **Divergência intencional**: o GAEMA SD não modela imóvel nem pessoa (DEC-006). Vínculo com cadastro só como indício espacial | Mantido |
| V-09 | Agendamento online, campo offline, sincronização posterior, PDF enviado depois | Confirma o desenho offline-first; agendamento entra como campo da campanha na Fase 3 | Fase 3/4 |
| V-10 | Policiais ambientais fazem a vistoria; Procuradores operam a web; superusuário aprova acessos | Papéis do GAEMA SD são genéricos; quem exerce TECNICO_CAMPO no Tocantins é decisão institucional | PENDENTE (INSTITUCIONAL) |
| V-11 | Relatório com tabela de parâmetros e fotos por amostra | Modelo de relatório da Fase 3 inclui tabela de parâmetros com valor bruto, unidade e evidências vinculadas | Fase 3 |
| V-12 | Tipo de solo e formação geológica vindos de mapas oficiais | `FonteDado` registra o mapa usado; preenchimento automático só com camada autorizada | Fase 3/5 |
