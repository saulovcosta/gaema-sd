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

## DEC-007 — Condições das transições apuradas pelo núcleo (03/10/2026)

- **Hipótese:** se quem pede a transição informa as condições (ex.: "revisão aprovada"), a revisão humana pode ser pulada.
- **Motivo:** revisão independente do código reproduziu uma demanda chegando a DIAGNOSTICO_EMITIDO sem diagnóstico nem revisão gravados.
- **Impacto:** `Nucleo.transitar` não recebe contexto; `estados/contexto.py` apura no banco e na trilha. A revisão que libera a emissão deve ser do próprio revisor que emite, e ele não pode ter participado da coleta (segregação de funções, AUTORAL). Reabertura só volta ao monitoramento se a demanda já teve diagnóstico emitido.
- **Risco:** consulta ao banco a cada transição (lista e filtra registros); aceitável no protótipo, otimizar com índices na Fase 4.
- **Teste:** `tests/test_regressao_revisao.py` (fluxo real pelo banco até DIAGNOSTICO_EMITIDO).

## DEC-008 — Relatório em HTML (Jinja2) e PDF (reportlab), mapa em SVG próprio (03/10/2026)

- **Hipótese:** HTML acessível e PDF idêntico a cada emissão atendem ao relatório reproduzível sem serviço externo.
- **Motivo:** Jinja2 já estava no ambiente e escapa texto automaticamente; reportlab gera PDF determinístico (`invariant=1`); weasyprint não estava disponível. Mapa em SVG gerado da geometria evita depender de serviço de mapas.
- **Impacto:** dependências novas fixadas (reportlab 4.2.5, pillow, chardet, Jinja2, MarkupSafe). Mapa é esquemático, sem escala cartográfica (dito no relatório).
- **Risco:** visual simples; mapa sem base cartográfica. Aceitável no protótipo; mapa base fica para a Fase 5 (ArcGIS ou camada autorizada).
- **Teste:** `tests/test_relatorio.py` (mesmos dados → mesmos bytes; seções; escape; acessibilidade básica).

## DEC-009 — Diagnóstico só pelo motor, com fotografia das entradas (03/10/2026)

- **Hipótese:** guardar no diagnóstico a fotografia canônica das entradas e o resultado completo do motor permite reprodução histórica mesmo após correções nos dados de campo.
- **Motivo:** §11 do prompt (reproduzir resultados históricos) e impedir diagnóstico "digitado".
- **Impacto:** `Nucleo.registrar` recusa `Diagnostico`; só `Nucleo.computar_diagnostico` grava. Novo cálculo substitui o anterior por vínculo (`substitui_diagnostico_id`), sem apagar.
- **Teste:** `tests/test_protocolo.py` e `tests/test_regressao_revisao.py`.

## DEC-010 — Fechamento de brechas apontadas na revisão da Fase 3 (03/10/2026)

- **Hipótese:** todo artefato com arquivo (relatório, evidência) só deve existir no banco junto com o arquivo correspondente, e vice-versa.
- **Motivo:** revisão independente reproduziu relatório e evidência gravados sem arquivo, e arquivo sem registro.
- **Impacto:** `Nucleo.registrar` recusa `Relatorio`, `Evidencia` e `Diagnostico`; cada um tem método próprio. Arquivo gravado em temporário e renomeado de forma atômica; se o registro falha, o arquivo é removido. Revisões ordenadas pela gravação no banco, não pela data declarada; data de revisão no futuro é recusada. Parâmetros operacionais usados entram na fotografia do diagnóstico.
- **Teste:** `tests/test_regressao_fase3.py`.

## DEC-011 — Sincronização: fila no dispositivo, aplicação só pelo núcleo da central (03/10/2026)

- **Hipótese:** o dispositivo grava no SQLite local e enfileira; a central aplica cada item por `Nucleo.receber_sincronizacao`, que mantém a regra única de escrita (acesso → validação → gravação → auditoria na mesma transação).
- **Motivo:** DEC-005 já previa versão otimista e chave de idempotência; faltava o caminho entre dois bancos. Duas versões divergentes não podem ser decididas por máquina.
- **Impacto:**
  - Envia-se como o técnico dono do dispositivo (nova ação `SINCRONIZAR`, só TECNICO_CAMPO); a autoria do registro na central é sempre quem enviou.
  - Item novo igual ao já gravado = reenvio idempotente. Item com mesmo id/chave e conteúdo diferente, ou correção a partir de versão que a central já ultrapassou com conteúdo diferente = **conflito**: a versão do dispositivo fica guardada em `conflitos_sincronizacao`, a da central não muda e, se a demanda estava em AGUARDANDO_SINCRONIZACAO, vai a CONFLITO_SINCRONIZACAO (por `Nucleo.transitar`, ator interno SISTEMA).
  - Resolução só por COORDENADOR (`resolver_conflito_sincronizacao`, nova ação), com motivo: MANTER_CENTRAL ou ACEITAR_DISPOSITIVO (nova versão; histórico preservado). Evidência é imutável: só MANTER_CENTRAL. A demanda não volta sozinha; o coordenador transita depois.
  - Conflito aberto conta em `conflitos_abertos` e bloqueia a validação mesmo que a demanda não esteja em CONFLITO_SINCRONIZACAO.
  - Tentativas máximas e espera inicial (dobra a cada tentativa) ficam em `config/parametros.json`, rotulados AUTORAL; não têm fundamento externo.
- **Risco:** o canal é simulado (`CanalSimulado`); nada foi testado em rede real, aplicativo de campo ou Survey123. O dispositivo não recebe de volta a versão resolvida pela central (reconciliação do lado do dispositivo fica para a Fase 5). Itens dependentes de um registro em conflito seguem o envio normal.
- **Teste:** `tests/test_sincronizacao.py`.

## DEC-012 — Concorrência: SQLite em WAL e versão de esquema (03/10/2026)

- **Hipótese:** WAL, `busy_timeout` e `BEGIN IMMEDIATE` bastam para várias conexões ao mesmo arquivo neste protótipo.
- **Motivo:** o `Repositorio` só era exercitado com uma conexão em memória.
- **Impacto:** arquivo em modo WAL; `PRAGMA user_version` = 1 (base para recusar backup de esquema mais novo). Banco em memória não muda.
- **Risco:** testes usam threads em uma máquina; não são prova de carga nem de sistema de arquivos em rede.
- **Teste:** `tests/test_concorrencia.py`.

## DEC-013 — Backup lógico, restauração e rollback por arquivos (03/10/2026)

- **Hipótese:** pasta com cópia consistente do banco (API de backup do SQLite), arquivos de evidência e relatório e manifesto com SHA-256 atende a RQ-44.
- **Motivo:** restauração só vale se for conferida: o backup é verificado antes de restaurar e o resultado é conferido depois (trilha de auditoria, contagens, hash dos arquivos).
- **Impacto:** `python -m gaema_sd.backup criar|verificar|restaurar|rollback`. Rollback move o estado atual para `<saida>.descartado-<hora>` (nunca apaga) e desfaz a troca se a restauração falhar. Backup anterior não é sobrescrito.
- **Risco:** manifesto não é assinado; quem controla a pasta pode refazê-lo (a cadeia da trilha ainda denuncia alteração de eventos). Ancoragem externa do último hash segue PENDENTE. Retenção (RQ-45, LA-06) segue PENDENTE. Não há agendamento nem armazenamento institucional.
- **Teste:** `tests/test_backup.py`.

## DEC-014 — Logs sem dado sensível por construção, filtro como segunda barreira (03/10/2026)

- **Hipótese:** o mais seguro é não logar conteúdo; o filtro mascara padrões óbvios (CPF, e-mail, `senha=`) e remove traceback.
- **Motivo:** mensagens de erro e o campo `motivo` da trilha podiam repetir texto digitado.
- **Impacto:** `auditoria.trilha.sanear_texto` aplicado a `motivo` e aos detalhes da trilha, ao erro guardado na fila e ao log (`observabilidade.py`). O log da sincronização leva só contagens e nomes de erro.
- **Risco:** nome de pessoa em texto livre não é detectável por padrão. Mascaramento por padrão pode, em tese, ocultar um número de 11 dígitos legítimo no motivo.
- **Teste:** `tests/test_seguranca.py`.

## DEC-015 — Acessibilidade do relatório: o que foi verificado (03/10/2026)

- **Hipótese:** verificações automáticas pegam as falhas estruturais mais comuns; não substituem leitor de tela.
- **Impacto:** link de salto, foco visível, estilo só na folha (sem atributo `style`), contraste calculado pela fórmula pública do WCAG 2.x (critério AA como referência, AUTORAL).
- **Risco:** leitor de tela e pessoas usuárias NÃO foram testados (RQ-74).
- **Teste:** `tests/test_acessibilidade.py`.

