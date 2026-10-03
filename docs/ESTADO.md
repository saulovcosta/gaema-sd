# Estado do projeto

Atualizado em: 03/10/2026, fim da Fase 5.

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

### Fase 5 — TESTADO LOCALMENTE (preparação; nada integrado)
- **Mescla:** o PR 2 (Fase 4) foi mesclado na `main` por squash antes de começar a Fase 5, com 221 testes verdes.
- **Decisão do coordenador volta ao aparelho** (fecha R-18): `Nucleo.consultar_decisoes_conflito`, `Sincronizador.reconciliar`, `Dispositivo.aplicar_decisao`, tabelas `decisoes_conflito` e `deslocamento_versao` (sem mudar `VERSAO_ESQUEMA`). **Defeito da Fase 4 reproduzido e corrigido:** depois de um conflito, correção posterior do mesmo registro, já na fila, sobrescrevia a versão da central; agora fica retida até a decisão (DEC-016, RQ-75, RQ-76).
- **Adaptadores ArcGIS só como interface** (`src/gaema_sd/adaptadores/`): `Protocol`s, `NaoConfigurado*`, `ConfigArcGIS` (só informa se as variáveis existem), tradução pura de submissão de campo. Teste confere que não há módulo de rede, URL nem credencial (DEC-017, RQ-77, RQ-78).
- **XLSForm do formulário de vistoria**, gerado do domínio (`adapters/arcgis/xlsform/*.csv`, `.xlsx` sob demanda): 7 variáveis de presença do protótipo, outras observações, penetrometria sem profundidade nem repetições padrão (LA-04), fotos, condição de acesso. Estrutura conferida por testes próprios e sintaxe XLSForm/ODK por `pyxform` (RQ-24).
- **Pacote de exportação em formato próprio** (`Nucleo.exportar_painel`, `schemas/exportacao-painel.schema.json`): sem geometria, coordenadas, textos livres nem pessoas; auditado (DEC-018, RQ-79). `docs/integracao-radar-painel.md` lista os pontos de troca e as perguntas à equipe.
- **Documentos:** `docs/homologacao.md` (32 itens, nenhum aprovado), `docs/pendencias.md` (LA-01 a LA-10 e pendências de ambiente), `docs/guia-capacitacao.md` (com exercícios e gabarito conferido pela demonstração), todos conferidos por `tests/test_documentos.py` (DEC-019, RQ-80, RQ-81).
- **Dependências de desenvolvimento novas:** `openpyxl`, `pyxform` e as que ele exige, versões fixadas; `pip-audit` sem achados em 03/10/2026.

## Testes executados

`python3 -m pytest` → **281 passed** (03/10/2026): 221 anteriores + 60 da Fase 5 (`test_reconciliacao`, `test_xlsform`, `test_adaptadores`, `test_exportacao`, `test_documentos`). `python3 scripts/gerar_contratos.py` regenera os arquivos novos (XLSForm em CSV, esquema de exportação) e `tests/test_contratos.py` passa. `scripts/demo.sh` → "Resultado: OK". `pip-audit -r requirements-dev.txt` → "No known vulnerabilities found". Duas mutações no código da reconciliação (desligar a retenção; ignorar o deslocamento de versão) foram pegas pelos testes e revertidas.

Cenários já executados (todos com rede e dispositivo simulados): os da Fase 4 e, agora, conflito → decisão → convergência dos dois bancos nos dois sentidos, envio retido, consulta com falha de rede e com interrupção do processo, importação de submissão de campo sintética (reimportação e edição divergente), exportação com acesso indevido.

**NÃO EXECUTADOS:** Survey123 Connect (abrir, validar e publicar o XLSForm); formato real de exportação do Survey123; qualquer acesso a ArcGIS, Radar Ambiental ou Painel do art. 18; sincronização em rede ou aparelho reais; mapa base offline; autenticação real; teste do relatório com leitor de tela e com pessoas usuárias; carga e desempenho; backup agendado, retenção e ancoragem externa do último hash; revisão independente de código das Fases 4 e 5; capacitação de turma; tela de operação; varredura de dependências em rotina automática.

## Falta

- Os itens NÃO EXECUTADOS acima e o checklist de `docs/homologacao.md` (nenhum item aprovado).
- Capacitação de turma (existe guia, `docs/guia-capacitacao.md`); tela de operação (hoje só linha de comando).
- Pendências científicas: protocolo validado, limiares, "degradação severa" (LA-02 a LA-04, LA-08).
- Pendências institucionais: quem exerce a vistoria, capacitação prévia, base legal para compartilhar dados (RQ-70), camadas autorizadas (LA-09), relação com o Painel do art. 18 (LA-10).

## Próximo passo exato

Fase 5 concluída como preparação; **nenhuma fase seguinte está definida**. Decisões da equipe que destravam o resto (ver `docs/pendencias.md`): organização ArcGIS e Client ID (LA-05), formato de troca com o Painel (LA-10), protocolo de campo validado (LA-04), retenção e sigilo (LA-06), quem exerce a vistoria e a capacitação coordenada com o CAOMA.
