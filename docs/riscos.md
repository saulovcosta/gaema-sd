# Registro de riscos

Escala: Probabilidade e Impacto em Baixo / Médio / Alto.

| ID | Risco | Prob. | Impacto | Mitigação | Situação |
|---|---|---|---|---|---|
| R-01 | Resultado de protótipo lido como conclusão técnica ou jurídica | Média | Alto | Rótulo obrigatório; revisão humana obrigatória; sem campos jurídicos (DEC-006) | Mitigação parcial na Fase 2 |
| R-02 | Dado real (pessoa, imóvel, procedimento) entrar no repositório | Média | Alto | Só dados sintéticos; `.gitignore`; teste de varredura | Mitigado na Fase 2 |
| R-03 | Perda silenciosa por "última edição vence" ao sincronizar | Alta (se usar ArcGIS sem controle) | Alto | Versão otimista e estado CONFLITO_SINCRONIZACAO | Núcleo pronto; sincronização na Fase 4 |
| R-04 | Duplicidade de registro em reenvio | Média | Médio | Chave idempotente | Núcleo pronto |
| R-05 | Limiares inventados (NDVI, penetrometria) | Média | Alto | Proibição em CLAUDE.md; configuração sem valor padrão | Ativo |
| R-06 | Modelo do núcleo divergir da organização ArcGIS do MPTO | Média | Médio | Contratos em `schemas/`; mapeamento na Fase 5 | Aberto |
| R-07 | GPS ou EXIF tomados como verdade | Média | Médio | Precisão registrada; alerta de GPS ruim; documentação de limitação | Parcial |
| R-08 | Hash tomado como prova material absoluta | Baixa | Médio | Texto de limitação no relatório (Fase 3) | Aberto |
| R-09 | Segredo (Client ID, token) commitado | Baixa | Alto | `.env` ignorado; `.env.example` sem valores; varredura | Mitigado |
| R-10 | Ambiente de nuvem efêmero apagar trabalho | Média | Médio | Commit e push ao fim de cada fase | Ativo |
| R-11 | Controle de acesso só na interface | Média | Alto | Política de acesso no núcleo (`acesso/politica.py`) | Mitigado na Fase 2 |
| R-12 | Dependência vulnerável | Baixa | Médio | Poucas dependências e versões fixadas; análise na Fase 4 | Aberto |
| R-13 | Contexto das transições (fatos como "revisão aprovada") é informado pelo chamador e poderia ser falseado | Média | Alto | Fase 3: montar o contexto a partir do repositório dentro do núcleo, sem aceitar valores externos | Aberto |
| R-14 | Vídeos do SIPADE (F3, F10) não analisados | Alta | Baixo | Nada do conteúdo usado; análise se o usuário disponibilizar os arquivos por link | Aberto |
