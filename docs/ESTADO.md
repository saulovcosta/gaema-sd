# Estado do projeto

Atualizado em: 03/10/2026, fim da Fase 4.

## Feito

### Fase 1 — ESPECIFICADO
- Inventário, fontes F1–F13, matriz fatos/inferências/lacunas/decisões (`docs/fontes.md`), arquitetura (c) (`docs/decisoes.md`), requisitos com proveniência, riscos, estrutura.
- Vídeos do SIPADE (F11, F12) analisados a partir de cópias do usuário (`docs/sipade-videos.md`).
- Passo 0: Portaria GAEMA nº 001/2026, arts. 16 a 20, incorporada como fonte INSTITUCIONAL (F13, RQ-60 a RQ-71), sem cópia do documento e sem dados pessoais. Gatilho de 40% em "degradação severa" PENDENTE.

### Fase 2 — TESTADO LOCALMENTE
- 20 entidades, máquina de estados (23 estados, 79 transições), validações, auditoria encadeada, política de acesso, repositório SQLite com conflito e idempotência, fachada `Nucleo`. Revisão independente: 8 falhas corrigidas.

### Fase 3 — TESTADO LOCALMENTE
- **Motor de protocolo** (`src/gaema_sd/protocolo/`): definições versionadas em `config/protocolos/` (descritivo e "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"); só presença/ausência, operador numérico recusado; resultado por ponto com regras disparadas, não disparadas e não avaliáveis (com motivo); penetrometria descritiva; limitações automáticas; `hash_entradas` independente da ordem.
- **Diagnóstico só pelo motor**, com fotografia das entradas e dos parâmetros usados; reprodução histórica (`Nucleo.reproduzir_diagnostico`); protocolo alterado exige nova versão.
- **Relatório** (`src/gaema_sd/relatorio/`): HTML acessível (Jinja2, escape automático, sem script nem recurso externo) e PDF determinístico (reportlab); 16 seções do §12; mapa esquemático em SVG; avisos de limitação; reemissão versionada, versão anterior preservada; só emitido após revisão aprovada, usando a revisão de quem autorizou a emissão.
- **Evidências**: arquivo original guardado pelo hash, nunca sobrescrito; validação antes de gravar; conferência de integridade com caminho derivado do hash.
- **Portaria (Passo 0) no modelo**: origem "Peça de Informação Técnica" e "encaminhamento de Promotoria"; critério de priorização do art. 17 registrado por pessoa, com motivo.
- **Protótipo local ponta a ponta**: `scripts/demo.sh` (área candidata → … → monitoramento → reemissão), só dados sintéticos; operação por linha de comando.
- **Revisão independente da Fase 3**: 7 defeitos reproduzidos e corrigidos, cada um com teste (`tests/test_regressao_fase3.py`): relatório e evidência gravados sem arquivo; caminho de arquivo manipulável na verificação; ordem de revisões pela data declarada; registro sem arquivo em falha de disco; arquivo órfão após recusa; parâmetro de GPS fora da fotografia; rótulo livre no modo descritivo.

### Fase 4 — TESTADO LOCALMENTE (rede simulada)
- **Sincronização** (`src/gaema_sd/sincronizacao/`): fila local por dispositivo (SQLite próprio, sobrevive a reinício), `CanalSimulado` com perda antes/depois do envio, serviço indisponível e interrupção do processo; reenvio idempotente; espera crescente (parâmetros AUTORAIS); retomada do ponto em que parou; registro gravado e não enfileirado é recuperado. Central aplica só por `Nucleo.receber_sincronizacao` (ação `SINCRONIZAR`, só TECNICO_CAMPO).
- **Conflito:** versões divergentes não sobrescrevem; as duas ficam guardadas (`conflitos_sincronizacao`), a demanda vai a CONFLITO_SINCRONIZACAO, só o COORDENADOR resolve com motivo (`resolver_conflito_sincronizacao`). DEC-011.
- **Concorrência:** SQLite em WAL com `busy_timeout`; testes com várias conexões ao mesmo arquivo (escritas distintas, mesmo envio, mesma versão, mesma chave). `PRAGMA user_version` = 1. DEC-012.
- **Segurança básica:** acesso indevido na sincronização (7 papéis, todos auditados), item adulterado em trânsito, tipo/operação inválidos, anexo inválido (assinatura, hash, nome inseguro, vazio) sem registro nem arquivo, autoria não forjável; `sanear_texto` em motivo, detalhes, fila e log; filtro de log. DEC-014.
- **Backup e rollback** (`src/gaema_sd/backup/`): cópia consistente, manifesto com SHA-256, verificação (adulteração, ausência, arquivo extra, trilha corrompida, esquema mais novo), restauração só para caminhos novos e conferida, rollback que guarda o estado desfeito. DEC-013.
- **Acessibilidade do relatório HTML:** link de salto, foco visível, sem estilo em atributo; testes automáticos de estrutura e de contraste (fórmula WCAG 2.x). DEC-015.
- **Dependências:** `pip-audit -r requirements-dev.txt` executado em 03/10/2026: "No known vulnerabilities found". Foi uma execução única, sem rotina automática.

## Testes executados

`python3 -m pytest` → **221 passed** (03/10/2026): 166 anteriores + 55 da Fase 4 (`test_sincronizacao`, `test_concorrencia`, `test_backup`, `test_seguranca`, `test_acessibilidade`). `python3 scripts/gerar_contratos.py` sem diferença nos arquivos gerados. `scripts/demo.sh` → "Resultado: OK" (EM_MONITORAMENTO, diagnóstico reproduzido, evidência e auditoria íntegras, 62 eventos).

Cenários obrigatórios do §14 já executados: envio duplicado, conflito de atualização (inclusive concorrente), anexo inválido, GPS ruim, geometria inválida, variável obrigatória ausente, acesso indevido, protocolo alterado, relatório reemitido, interrupção e retomada da coleta, **perda de rede, serviço indisponível, confirmação perdida, interrupção do processo e retomada da fila, conflito de sincronização, restauração de backup e rollback** (todos com rede e dispositivo simulados).

**NÃO EXECUTADOS:** sincronização em rede, aparelho ou aplicativo de campo reais (nem Survey123/ArcGIS); teste do relatório com leitor de tela e com pessoas usuárias (RQ-74); carga e desempenho (os índices citados na DEC-007 não foram feitos); rotina agendada de backup, retenção (LA-06) e ancoragem externa do último hash da trilha; reconciliação do dispositivo com a decisão do coordenador (R-18); observabilidade além de log filtrado (sem métricas nem alertas); varredura de dependências em rotina automática.

## Falta

- Fase 5 (preparação institucional: ArcGIS, XLSForm, homologação) e os itens NÃO EXECUTADOS acima.
- Guia de uso para capacitação (RQ-68); tela de operação (hoje só linha de comando).
- Pendências científicas: protocolo validado, limiares, "degradação severa" (LA-02 a LA-04, LA-08).
- Pendências institucionais: quem exerce a vistoria, capacitação prévia, base legal para compartilhar dados (RQ-70), camadas autorizadas (LA-09), relação com o Painel do art. 18 (LA-10).

## Próximo passo exato

Fase 5 (não iniciada; aguardar instrução): preparação institucional. Antes, decidir com a equipe: quem exerce a vistoria, o destino e a retenção dos backups (LA-06) e se a sincronização será testada em aparelho real.
