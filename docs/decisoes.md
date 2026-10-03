# Registro de decisões

Formato: cada decisão traz hipótese, motivo, impacto, risco e teste. Uma decisão só muda por nova entrada que a substitua.

## DEC-001 — Arquitetura do núcleo (03/10/2026)

### Opções comparadas

| Critério | (a) Máximo nativo ArcGIS | (b) ArcGIS com extensão mínima | (c) Núcleo independente com adaptadores |
|---|---|---|---|
| Descrição | Feature Services, Survey123, Field Maps, Experience Builder e regras em Arcade/Python Notebooks | ArcGIS para dados, campo e mapas; pequeno serviço próprio só para protocolo e relatório | Núcleo próprio (domínio, estados, protocolo, auditoria, relatório); ArcGIS conectado por adaptadores |
| Pode ser testado hoje? | Não. Exige organização ArcGIS e Client ID (FC-08) | Parcialmente; a maior parte depende de ArcGIS | Sim, integralmente, sem rede externa |
| Offline em campo | Bom, nativo (FC-09, FC-11) | Bom, nativo | Precisa de app próprio **ou** do adaptador Survey123/Field Maps |
| Conflito de edição | "Última edição sincronizada vence" em camada hospedada (FC-12) | Igual a (a) | Controle próprio: versão + chave idempotente; conflito vira estado explícito |
| Reprodutibilidade do diagnóstico | Difícil: regras espalhadas em formulários e expressões | Média | Alta: protocolo versionado, entradas brutas preservadas |
| Auditoria | Rastreamento de edição nativo, sem encadeamento | Mista | Trilha encadeada por hash no núcleo |
| Dependência de fornecedor | Total | Alta | Baixa; ArcGIS continua como canal preferencial |
| Custo de integração posterior | Nenhum | Baixo | Médio (adaptadores, mapeamento de campos) |

### Recomendação: opção (c)

- **Hipótese:** um núcleo independente, com contratos explícitos (JSON Schema) e adaptadores, permite desenvolver e testar todo o ciclo agora e ligar ArcGIS depois sem reescrever regras.
- **Motivo:** não há organização ArcGIS acessível (LA-05); as regras de protocolo, estados e auditoria precisam ser reproduzíveis e testáveis; a regra "última edição vence" (FC-12) não atende a exigência de nenhum dado perdido em silêncio.
- **Impacto:** todo o desenvolvimento das Fases 2 a 4 ocorre sem ArcGIS; a Fase 5 escreve adaptadores (XLSForm, Feature Services, Field Maps, Experience Builder, ArcGIS API for Python) como interface e documentação, sem execução.
- **Risco:** divergência entre o modelo do núcleo e os campos que a organização ArcGIS do MPTO venha a usar; duplicidade de esforço se o MPTO preferir solução 100% nativa. Mitigação: contratos em `schemas/`, mapeamento de campos documentado, XLSForm gerado a partir do mesmo esquema.
- **Teste:** (1) o núcleo instala e passa nos testes sem nenhuma biblioteca ArcGIS (verificado pela lista de dependências e pela suíte); (2) na Fase 5, um XLSForm gerado do esquema é validado pelo Survey123 Connect assim que houver ambiente — até lá, o item fica PENDENTE.
- **Nível:** ESPECIFICADO.

## DEC-002 — Pilha tecnológica (03/10/2026)

- **Hipótese:** Python 3.11 + SQLite + pytest + shapely bastam para o núcleo e rodam em qualquer computador do MPTO.
- **Motivo:** poucas dependências, sem servidor, arquivo único de banco, fácil backup; shapely é a referência para validade de geometria.
- **Impacto:** sem servidor web nesta fase; interface virá na Fase 3.
- **Risco:** SQLite tem concorrência limitada de escrita; aceitável para protótipo local. Migração para PostgreSQL/PostGIS fica como opção da Fase 5.
- **Teste:** suíte pytest roda limpa em ambiente novo com `scripts/testar.sh`.

## DEC-003 — Somente dados sintéticos (03/10/2026)

- **Hipótese:** nenhum dado real é necessário para construir e testar o núcleo.
- **Motivo:** sigilo (prompt §5).
- **Impacto:** fixtures com nomes fictícios, coordenadas genéricas e rótulo SINTÉTICO.
- **Risco:** dado real entrar por descuido. Mitigação: `.gitignore` bloqueia bancos e pastas de dados; teste automático varre fixtures por padrões de CPF, CNPJ, e-mail e número de procedimento.
- **Teste:** `tests/test_sigilo_fixtures.py`.

## DEC-004 — Protocolo em modo descritivo (03/10/2026)

- **Hipótese:** sem protocolo científico validado, o sistema só descreve e organiza observações; qualquer classificação usa protótipo rotulado.
- **Motivo:** lacunas LA-02, LA-03, LA-04; proibição de inventar limiares.
- **Impacto:** o protótipo de teste (Fase 3) carrega o rótulo "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA" em toda saída.
- **Risco:** leitor tomar resultado de protótipo como conclusão técnica. Mitigação: rótulo obrigatório, revisão técnica humana obrigatória antes de DIAGNOSTICO_EMITIDO.
- **Teste:** Fase 3 — teste que falha se um relatório de protótipo for gerado sem o rótulo.

## DEC-005 — Concorrência e sincronização (03/10/2026)

- **Hipótese:** controle otimista por número de versão e chave idempotente gerada no dispositivo evitam perda silenciosa e duplicidade.
- **Motivo:** FC-12 e prompt §10.
- **Impacto:** toda gravação informa a versão lida; versão desatualizada gera erro de conflito, nunca sobrescrita; reenvio com a mesma chave devolve o registro existente.
- **Risco:** mais conflitos visíveis para o usuário. É desejado.
- **Teste:** `tests/test_persistencia.py` (conflito e envio duplicado).

## DEC-006 — Fronteira entre técnica e conclusão jurídica (03/10/2026)

- **Hipótese:** o sistema não deve conter campos que sugiram autoria, ilicitude, dano jurídico, responsabilidade ou nexo causal.
- **Motivo:** prompt §7 e §11.
- **Impacto:** `Providencia` registra decisão humana em texto livre, com autor humano; `AreaInteresse` não é imóvel nem cadastro; pessoas vinculadas não existem no modelo desta fase.
- **Teste:** `tests/test_fronteira_juridica.py` varre os campos das entidades.
