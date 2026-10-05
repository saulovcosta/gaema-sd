# Pendências: científicas, institucionais e de ambiente

Nível: **ESPECIFICADO**. Proveniência: AUTORAL (consolidação) sobre as lacunas de `docs/fontes.md`. Este documento diz **o que falta e o que cada resposta destrava**; não atribui responsáveis nem prazos, porque isso é decisão institucional. Atualizado em 03/10/2026, fim da Fase 5.

## 1. Lacunas de `docs/fontes.md`

| ID | Natureza | Pendência | Como o sistema se comporta hoje | O que a resposta destrava |
|---|---|---|---|---|
| LA-01 | Científica | Faixas numéricas vistas nas telas do SIPADE (altura do pasto, <50%, >10 mm) sem fundamentação pública | Não adotadas como limiar | Nada, enquanto não houver fundamentação |
| LA-02 | Científica | Fórmulas, pesos e limiares do SIPADE | Protótipo próprio, só presença/ausência, rotulado "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" | Protocolo validado no lugar do protótipo (nova versão publicada) |
| LA-03 | Científica | Limiar de NDVI para o Cerrado tocantinense | NDVI é sinal configurável, sem valor padrão. **Não existe triagem por satélite** (Rodada 4): nenhuma imagem é processada nem índice calculado; áreas candidatas só entram informadas ou importadas por pessoa, com origem e incerteza declaradas | Uso de NDVI na triagem |
| LA-04 | Científica | Protocolo de campo validado: número de pontos, repetições, profundidade da penetrometria | Parâmetros PENDENTES; o XLSForm não define profundidade nem repetições | Formulário e regras de penetrometria completos |
| LA-05 | Ambiente | Organização ArcGIS do MPTO, Client ID, serviços existentes do Radar Ambiental | Adaptadores só interface; nada contra ArcGIS | Teste do XLSForm, publicação, camadas, qualquer adaptador real |
| LA-06 | Institucional | Normas de retenção documental e classificação de sigilo | Retenção PENDENTE; exportação sem geometria nem texto livre; backup sem rotina | Política de backup, retenção e conteúdo permitido na exportação |
| LA-07 | Institucional | Autorização formal de uso de SICAR, MapBiomas, PRODES, DETER | Nenhuma ingestão | Camadas de cruzamento (`CatalogoCamadas`) |
| LA-08 | Científica | Critério técnico de "degradação severa" (art. 17, III); gatilho de 40% | Não calculado nem sinalizado | Apoio ao critério III |
| LA-09 | Institucional | Como operacionalizar "risco comprovado de assoreamento", "impacto supramunicipal" e os recortes Serras Gerais, Jalapão e MATOPIBA (art. 17, I e II) | Priorização é registro humano | Apoio aos critérios I e II com camadas autorizadas |
| LA-10 | Institucional | Arquitetura, acesso e dados do Painel do art. 18 (a página pública do Radar, consultada em 03/10/2026, não o lista e não traz API, exportação nem documentação técnica; FC-24) | Pacote de exportação em formato próprio; nenhuma integração declarada | Formato de troca real e decisão entre complementar ou alimentar o Painel |

## 2. Outras pendências institucionais

| Item | Pendência | Efeito hoje |
|---|---|---|
| Quem exerce a vistoria | Definição institucional | O sistema só tem o papel TECNICO_CAMPO |
| Capacitação prévia (art. 20) | Capacitação coordenada com o CAOMA não realizada; há guia de apoio (`docs/guia-capacitacao.md`) | Nenhuma turma atendida |
| Base legal para compartilhar dados (RQ-70) | Não definida | Nenhum dado sai do sistema, exceto o pacote de exportação sem dados sensíveis, gerado a pedido |
| Conteúdo dos relatórios dos marcos (RQ-71) | O CAOMA/coordenação precisa definir | Só contagens agregadas |

## 3. Pendências de ambiente e de engenharia (NÃO EXECUTADAS)

| Item | Situação |
|---|---|
| Autenticação real de usuários | Não existe: na interface local escolhe-se um usuário SINTÉTICO de teste; no código, o ator é informado pelo chamador |
| Endosso do CAOMA e autorização de uso da marca | PENDENTE: o relatório imprime "Sem endosso institucional formal" até haver ato (`config/endosso.json`) |
| Tela de operação | Existe uma interface local de teste (`scripts/interface.sh`, só em 127.0.0.1, dados sintéticos); avaliação com pessoas usuárias NÃO EXECUTADA |
| Survey123 Connect: abrir, validar e publicar o XLSForm | NÃO EXECUTADO (só estrutura e sintaxe XLSForm/ODK com pyxform) |
| Formato real de exportação do Survey123 | NÃO verificado |
| Sincronização em rede e aparelho reais | NÃO EXECUTADA (rede simulada) |
| Mapa base offline (TPKX/VTPK/MMPK) | NÃO EXECUTADO |
| Backup agendado, destino e retenção; guarda da âncora da trilha fora da máquina | PENDENTES (a âncora já é gerada e conferida; quem a guarda, e onde, é decisão institucional) |
| Carga e desempenho (índices citados na DEC-007) | NÃO EXECUTADOS |
| Teste com leitor de tela e pessoas usuárias (relatório e interface) | NÃO EXECUTADO (só verificações automáticas, incluindo axe-core na interface) |
| Revisão independente **humana ou de terceiros** das Fases 4 e 5 | NÃO EXECUTADA (nas Fases 2 e 3 houve revisão independente; nas Fases 4 e 5 houve só a revisão por agente separado, DEC-020) |
| Separar a API de entrada de campo da API administrativa na implantação (R-28) | PENDENTE |
| Comando ou rotina para o aparelho consultar as decisões de conflito (`Sincronizador.reconciliar` só existe como função) | PENDENTE |
| Varredura de dependências em rotina automática | NÃO existe (executada manualmente) |
| Banco institucional (opção PostgreSQL/PostGIS da DEC-002) | Decisão pendente |

## 4. Decisões do coordenador (não implementadas)

Nada nesta seção foi implementado. Cada item espera decisão da coordenação do CAOMA/GAEMA. Até lá, o sistema fica como descrito na coluna "Como está hoje". A prioridade sugerida de cada função está em `docs/auditoria-comparativa.md`.

| Decisão | Como está hoje | Referência |
|---|---|---|
| Permitir vínculo **opcional** da demanda com imóvel ou com procedimento | Vedado: a área de interesse é recorte de análise, sem imóvel, proprietário ou número de procedimento | DEC-006 (fronteira técnica e jurídica), DE-07, V-08 |
| Quem faz a vistoria no Tocantins e com qual capacitação prévia; se o pedido de acesso registra o curso feito | Papel genérico "Técnico de campo"; o curso não é registrado | H-I01, V-10, V-13, art. 20 |
| Protocolo científico: variáveis, repetições, profundidade, fotos e regra de classificação | Modo descritivo como padrão; protótipo "SEM VALIDADE CIENTÍFICA"; divergência 3 × 4 categorias mantida | LA-02, LA-04, V-05 |
| ArcGIS: organização, Client ID, Survey123 e relação com o Painel do art. 18 | Adaptadores só como interface; nenhuma integração | LA-05, LA-10, H-A01 |
| Uso da marca do MPTO e endosso do CAOMA no relatório | "Sem endosso institucional formal" (`config/endosso.json` vazio) | H-I08, DEC-027 |
| Ligar a autoatribuição da demanda pelo técnico | `autoatribuicao_tecnico` = false | V-14, DEC-034 |
| Autenticação institucional real | Usuários de teste; aprovação de pedido só libera papel de teste | R-31, H-A06 |
| Revisão humana ou de terceiros do código | Só revisões por agente de IA separado | H-S02, H-S03 |
| Teste com leitor de tela | NÃO EXECUTADO (só verificações automáticas) | `docs/acessibilidade-contraste.md` |
| Teste com pessoas usuárias do CAOMA (escritório e campo) | NÃO EXECUTADO | `docs/guia-capacitacao.md` |
| Itens da ABRAMPA SOLOS | Não listados: o PDF não está no repositório | `docs/auditoria-comparativa.md`, seção 3 |
