# Estado do projeto

Atualizado em: 03/10/2026, fim da Fase 3.

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

## Testes executados

`python3 -m pytest` → **166 passed** (03/10/2026). `scripts/demo.sh` → "Resultado: OK" (demanda em EM_MONITORAMENTO, diagnóstico reproduzido, evidência íntegra, auditoria íntegra).

Cenários obrigatórios do §14 já executados: envio duplicado, conflito de atualização (inclusive concorrente), anexo inválido, GPS ruim, geometria inválida, variável obrigatória ausente, acesso indevido, **protocolo alterado**, **relatório reemitido**, interrupção e retomada da coleta (no fluxo de estados e no demo).

**NÃO EXECUTADOS** (Fase 4): perda de rede e sincronização real de dispositivo, serviço indisponível, acessibilidade com leitor de tela (só checagens automáticas básicas foram feitas), backup e restauração, análise de dependências, observabilidade, rollback.

## Falta

- Fase 4 (robustez), Fase 5 (preparação institucional: ArcGIS, XLSForm, homologação).
- Guia de uso para capacitação (RQ-68); tela de operação (hoje só linha de comando).
- Pendências científicas: protocolo validado, limiares, "degradação severa" (LA-02 a LA-04, LA-08).
- Pendências institucionais: quem exerce a vistoria, capacitação prévia, base legal para compartilhar dados (RQ-70), camadas autorizadas (LA-09), relação com o Painel do art. 18 (LA-10).

## Próximo passo exato

Fase 4: criar `src/gaema_sd/sincronizacao/` com fila local de envio por dispositivo (simulação de perda de rede, reenvio idempotente e estado CONFLITO_SINCRONIZACAO a partir de versões divergentes), começando pelos testes de "perda de rede" e "retomada após interrupção" com dois repositórios SQLite (dispositivo e central).
