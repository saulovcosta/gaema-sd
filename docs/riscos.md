# Registro de riscos

Escala: Probabilidade e Impacto em Baixo / Médio / Alto.

| ID | Risco | Prob. | Impacto | Mitigação | Situação |
|---|---|---|---|---|---|
| R-01 | Resultado de protótipo lido como conclusão técnica ou jurídica | Média | Alto | Rótulo obrigatório; revisão humana obrigatória; sem campos jurídicos (DEC-006) | Mitigação parcial na Fase 2 |
| R-02 | Dado real (pessoa, imóvel, procedimento) entrar no repositório | Média | Alto | Só dados sintéticos; `.gitignore`; teste de varredura | Mitigado na Fase 2 |
| R-03 | Perda silenciosa por "última edição vence" ao sincronizar | Alta (se usar ArcGIS sem controle) | Alto | Versão otimista e estado CONFLITO_SINCRONIZACAO | Testado com canal simulado na Fase 4 (R-17 segue ativo) |
| R-04 | Duplicidade de registro em reenvio | Média | Médio | Chave idempotente; reenvio e confirmação perdida testados na Fase 4 | Testado com canal simulado |
| R-05 | Limiares inventados (NDVI, penetrometria) | Média | Alto | Proibição em CLAUDE.md; configuração sem valor padrão | Ativo |
| R-06 | Modelo do núcleo divergir da organização ArcGIS do MPTO | Média | Médio | Contratos em `schemas/`; XLSForm e tradução gerados do mesmo domínio e conferidos por teste (Fase 5); falta confronto com o ambiente ArcGIS real | Parcialmente mitigado |
| R-07 | GPS ou EXIF tomados como verdade | Média | Médio | Precisão registrada; alerta de GPS ruim; documentação de limitação | Parcial |
| R-08 | Hash tomado como prova material absoluta | Baixa | Médio | Aviso fixo em todo relatório e nas limitações do diagnóstico | Mitigado na Fase 3 |
| R-09 | Segredo (Client ID, token) commitado | Baixa | Alto | `.env` ignorado; `.env.example` sem valores; varredura | Mitigado |
| R-10 | Ambiente de nuvem efêmero apagar trabalho | Média | Médio | Commit e push ao fim de cada fase | Ativo |
| R-11 | Controle de acesso só na interface | Média | Alto | Política de acesso no núcleo (`acesso/politica.py`) | Mitigado na Fase 2 |
| R-12 | Dependência vulnerável | Baixa | Médio | Poucas dependências e versões fixadas; `pip-audit` rodado uma vez em 03/10/2026 sem achados; repetir a cada atualização | Parcialmente mitigado (sem rotina automática)
| R-13 | Contexto das transições (fatos como "revisão aprovada") é informado pelo chamador e poderia ser falseado | Média | Alto | `Nucleo.transitar` monta o contexto a partir do banco e da trilha (`estados/contexto.py`); chamador não informa fatos | Mitigado na Fase 2 (após revisão independente) |
| R-14 | Faixas vistas nos vídeos do SIPADE virarem limiar sem validação | Média | Alto | Registradas só como OBSERVAÇÃO PÚBLICA (`docs/sipade-videos.md`, V-04) | Ativo |
| R-15 | Relatório de protótipo circular como laudo | Média | Alto | Faixa "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" e "DADOS SINTÉTICOS" no topo do HTML e do PDF; teste obrigatório | Mitigado na Fase 3 |
| R-16 | Mapa esquemático lido como mapa oficial | Baixa | Médio | Legenda "sem escala cartográfica"; mapa base só na Fase 5 | Ativo |
| R-17 | Sincronização só validada com canal simulado; comportamento em rede e aparelho reais desconhecido | Alta | Alto | `CanalSimulado` com cinco tipos de falha; teste em campo na Fase 5 antes de qualquer uso | Ativo |
| R-18 | Conflito resolvido na central não volta ao dispositivo | Média | Médio | Versão do dispositivo fica guardada no conflito; decisão devolvida ao dispositivo e versões realinhadas (Fase 5, RQ-75 e RQ-76) | Mitigado em simulação local; não testado em aparelho real (R-17) |
| R-19 | Manifesto do backup sem assinatura; quem controla a pasta pode refazê-lo | Média | Médio | Cadeia da trilha denuncia alteração de eventos; ancoragem externa do último hash (PENDENTE) | Ativo |
| R-20 | Backup sem rotina nem retenção definida (LA-06) | Média | Alto | Comando disponível e testado; agendamento e destino dependem da infraestrutura institucional | Ativo |
| R-21 | Mascaramento de log não pega nome em texto livre | Média | Médio | Log sem conteúdo de registro; revisão de novos pontos de log | Ativo |
| R-22 | Relatório não testado com leitor de tela | Média | Médio | Verificações automáticas feitas; teste manual especificado (RQ-74) | Ativo |
| R-23 | Formato de entrada da tradução de campo é neutro; o formato real de exportação do Survey123 pode ser diferente | Alta | Médio | Tradução isolada em `adaptadores/traducao.py`; confronto com amostra real é o item H-A03 do checklist | Ativo |
| R-24 | XLSForm conferido só por pyxform; pode não abrir ou comportar-se diferente no Survey123 Connect (por exemplo, repetições, geopoint, imagem sem tamanho máximo) | Média | Médio | Só repetições de um nível; avisos do pyxform registrados; teste no Survey123 Connect é o item H-A02 | Ativo |
| R-25 | Pacote de exportação ser lido como integração com o Painel ou como formato oficial | Média | Médio | Campo `aviso` no pacote, nome "formato próprio", documento de integração com perguntas à equipe do Radar | Ativo |
| R-26 | Item retido por conflito ficar parado se o coordenador não decidir | Média | Baixo | O resumo da rodada mostra `retidos`; decisão humana é intencional | Ativo |
| R-27 | Dependências de desenvolvimento novas (openpyxl, pyxform e suas dependências) ampliarem a superfície de vulnerabilidade | Baixa | Baixo | Só em desenvolvimento e testes; versões fixadas; `pip-audit` sem achados em 03/10/2026 | Mitigado, sem rotina |
