# Estado do projeto

Atualizado em: 03/10/2026, fim da Fase 6 (interface local e segurança da central), depois da revisão independente da Fase 6.

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
- **Segurança básica:** acesso indevido na sincronização (7 papéis, todos auditados), item adulterado em trânsito, tipo/operação inválidos, anexo inválido (assinatura, hash, nome inseguro, vazio) sem registro nem arquivo, autoria (`criado_por`) não forjável; `sanear_texto` em motivo, detalhes, fila e log; filtro de log. DEC-014.
- **Backup e rollback** (`src/gaema_sd/backup/`): cópia consistente, manifesto com SHA-256, verificação (adulteração, ausência, arquivo extra, trilha corrompida, esquema mais novo), restauração só para caminhos novos e conferida, rollback que guarda o estado desfeito. DEC-013.
- **Acessibilidade do relatório HTML:** link de salto, foco visível, sem estilo em atributo; testes automáticos de estrutura e de contraste (fórmula WCAG 2.x). DEC-015.
- **Dependências:** `pip-audit -r requirements-dev.txt` executado em 03/10/2026: "No known vulnerabilities found". Foi uma execução única, sem rotina automática.

### Fase 5 — TESTADO LOCALMENTE (preparação; nada integrado)
- **Mescla:** o PR 2 (Fase 4) foi mesclado na `main` por squash antes de começar a Fase 5, com 221 testes verdes.
- **Decisão do coordenador volta ao aparelho** (fecha R-18): `Nucleo.consultar_decisoes_conflito`, `Sincronizador.reconciliar`, `Dispositivo.aplicar_decisao`, tabelas `decisoes_conflito` e `deslocamento_versao` (sem mudar `VERSAO_ESQUEMA`). **Defeito da Fase 4 reproduzido e corrigido:** depois de um conflito, correção posterior do mesmo registro, já na fila, sobrescrevia a versão da central; agora fica retida até a decisão (DEC-016, RQ-75, RQ-76).
- **Adaptadores ArcGIS só como interface** (`src/gaema_sd/adaptadores/`): `Protocol`s, `NaoConfigurado*`, `ConfigArcGIS` (só informa se as variáveis existem), tradução pura de submissão de campo. Teste confere que não há módulo de rede, URL nem credencial (DEC-017, RQ-77, RQ-78).
- **XLSForm do formulário de vistoria**, gerado do domínio (`adapters/arcgis/xlsform/*.csv`, `.xlsx` sob demanda): 7 variáveis de presença do protótipo, outras observações, penetrometria sem profundidade nem repetições padrão (LA-04), fotos, condição de acesso. Estrutura conferida por testes próprios e sintaxe XLSForm/ODK por `pyxform` (RQ-24).
- **Pacote de exportação em formato próprio** (`Nucleo.exportar_painel`, `schemas/exportacao-painel.schema.json`): sem geometria, coordenadas, textos livres nem pessoas; auditado (DEC-018, RQ-79). `docs/integracao-radar-painel.md` lista os pontos de troca e as perguntas à equipe.
- **Documentos:** `docs/homologacao.md` (35 itens, nenhum aprovado), `docs/pendencias.md` (LA-01 a LA-10 e pendências de ambiente), `docs/guia-capacitacao.md` (com exercícios e gabarito conferido pela demonstração), todos conferidos por `tests/test_documentos.py` (DEC-019, RQ-80, RQ-81).
- **Dependências de desenvolvimento novas:** `openpyxl`, `pyxform` e as que ele exige, versões fixadas; `pip-audit` sem achados em 03/10/2026.

### Revisão independente das Fases 4 e 5 — EXECUTADA por agente separado (DEC-020)
- Um agente separado, de IA, instruído a quebrar o que foi feito, reproduziu **20 achados** (2 de gravidade alta) em scripts próprios, sem editar o repositório. Cada achado virou teste de regressão que **falhou no código anterior**; as correções estão nos mesmos commits da fase.
- **Altos:** (1) dado de campo aceito sem ponto/campanha, de usuário fora da equipe e com a demanda já adiante, alterando o que sustenta o diagnóstico; (2) um erro de acesso rejeitava em definitivo todo o campo. **Médios:** item sem arquivo travava a fila; "aceitar o aparelho" apagava alteração posterior da central; backup "conferia" sem os arquivos e confiando só no manifesto; tradução descartava fotos e nota de acesso em silêncio; id de registro formava caminho do relatório; exportação levava id de usuário e texto livre do protocolo; `observador_id` forjável; XLSForm obrigava sim/não e usava `now()`. **Baixos:** conflito falso em reenvio, conflito perdido se a transição falhasse, decisão visível a outro técnico, decisão aplicada duas vezes, integração ATIVA em desenvolvimento, esquema sem versão nova, guia e gabarito imprecisos, mutantes sobreviventes.
- **Esquema do banco passou a 2** (`conflitos_sincronizacao.enviado_por`), com migração do 1 sem perda.
- 20 mutações nas correções novas foram todas pegas pelos testes.
- **Não corrigidos (registrados):** `Nucleo.registrar` direto na central não confere origem/equipe/estado (R-28, H-S07); a fila do aparelho é estado local fora da trilha (os descartes por decisão agora são auditados); trilha truncada e banco trocado com manifesto refeito seguem possíveis para quem controla a pasta (R-19); conflitos do esquema 1 ficam visíveis a qualquer técnico (R-29).
- **O revisor não é humano nem terceiro** (R-30, H-S02).

### Fase 6 — TESTADO LOCALMENTE (interface local; dados sintéticos; sem autenticação real)
- **Mescla:** o PR 3 (Fase 5) foi mesclado na `main` por squash a pedido do usuário.
- **R-28 fechado localmente** (DEC-021): `Nucleo` em modo "central" confere origem, equipe e estado em toda entrada de dado de campo, inclusive do registro gravado; vínculo ponto/campanha imutável; modo somente leitura.
- **R-19 mitigado em parte** (DEC-022): âncora externa da trilha (gerar, conferir, conferir backup com âncora). Guardar a âncora fora da máquina é decisão institucional (PENDENTE).
- **Rotina do aparelho** (DEC-023): `Sincronizador.rodada()` consulta decisões e envia a fila; `scripts/demo_sincronizacao.sh`.
- **Interface local** (DEC-024, DEC-025): `scripts/interface.sh` abre em http://127.0.0.1:8765/. Início com "O que fazer agora" e "Exige atenção"; demanda com situação em linguagem comum, mudanças possíveis (desabilitadas com motivo quando o papel não pode), mapa esquemático com escala aproximada e lista sincronizada, histórico, relatórios; conflitos com comparação campo a campo; auditoria com âncora; exportação; backup; Campo (aparelho simulado) com barra de rede/fila/última sincronização, coleta em 4 etapas com rascunho salvo, desfazer e conferência; ajuda e limites; temas claro e escuro.
- **Relatório A4** (RQ-95): bloco de identificação, datas legíveis, hashes em grupos (copiáveis inteiros), tabelas sem corte; 6 páginas A4 no cenário de demonstração (antes: 8 páginas Carta).
- **Revisão independente da Fase 6 por agente separado** (DEC-026): 15 achados (1 alto: técnico movia dado de campo de outra demanda), todos corrigidos com teste de regressão e reproduzidos de novo contra a árvore corrigida.
- **Teste por Codespaces** (DEC-027): `.devcontainer/devcontainer.json` (Python 3.12, porta 8765 privada, início por `scripts/interface.sh`); aceita só o host encaminhado exato quando `CODESPACES=true`. Testado só por simulação dos cabeçalhos; **NÃO EXECUTADO num Codespaces real**.
- **Verificação com navegador real automatizado** (Chromium + axe-core 4.13, `scripts/verificar_interface.js`): achou um defeito que os testes não pegavam — o navegador mandava `Origin: null` e a interface recusava o próprio login (corrigido, DEC-026). Depois das correções: 83 telas (360 e 1280 px, claro e escuro, tema escolhido na tela, zoom 200%), **0 violações** do axe-core, nenhuma rolagem horizontal, próxima ação e faixa de protótipo em todas, títulos sem salto, foco visível em todas as paradas de Tab.

## Nível de pronto real de cada entrega

| Entrega | Nível de pronto real | O que limita |
|---|---|---|
| Núcleo, estados, auditoria, acesso (Fase 2) | TESTADO LOCALMENTE | Sem autenticação real: o usuário é informado pelo chamador |
| Motor de protocolo, diagnóstico, relatório HTML/PDF (Fase 3) | TESTADO LOCALMENTE | Só o protótipo "sem validade científica"; protocolo validado PENDENTE |
| Sincronização: fila, reenvio, conflito, decisão de volta ao aparelho, rodada (Fases 4 a 6) | TESTADO LOCALMENTE | Rede e aparelho simulados |
| Entrada de dado de campo na central (origem, equipe, estado, vínculo) | TESTADO LOCALMENTE | Em todos os caminhos (modo central); sem ambiente real |
| Concorrência, segurança básica, logs | TESTADO LOCALMENTE | Threads em uma máquina; mascaramento parcial (alguns formatos de CPF e e-mail; não pega nome nem CNPJ/telefone com máscara) |
| Backup, restauração, rollback e âncora da trilha | TESTADO LOCALMENTE | Manifesto sem assinatura; sem rotina agendada, destino ou retenção; quem guarda a âncora fora da máquina: PENDENTE |
| Relatório HTML acessível, impressão em A4 | TESTADO LOCALMENTE (verificações automáticas; PDF A4 renderizado e conferido visualmente) | Leitor de tela e pessoas usuárias: NÃO EXECUTADO |
| Interface local de operação (escritório e campo simulado) | TESTADO LOCALMENTE (testes automáticos + navegador automatizado + axe-core) | Sem autenticação real (R-31); só 127.0.0.1; aparelho e rede simulados; leitor de tela e pessoas usuárias NÃO EXECUTADOS; não há conformidade WCAG declarada |
| Adaptadores ArcGIS | IMPLEMENTADO LOCALMENTE (interface; recusam por padrão) | Nada integrado; sem organização ArcGIS (LA-05) |
| XLSForm da vistoria | TESTADO LOCALMENTE (estrutura + sintaxe pelo pyxform) | **Não foi aberto no Survey123 Connect**; formato real de exportação não verificado |
| Tradução de submissão de campo | TESTADO LOCALMENTE | Formato de entrada neutro, não o do Survey123 |
| Pacote de exportação | TESTADO LOCALMENTE | Formato próprio; formato do Painel desconhecido (LA-10); nenhuma integração |
| Checklist, pendências, integração (documentos) | IMPLEMENTADO LOCALMENTE | Dependem de decisões institucionais; nenhum item aprovado |
| Guia de capacitação | IMPLEMENTADO LOCALMENTE | Nenhuma turma atendida; gabarito conferido por teste contra a demonstração |
| Revisões independentes das Fases 4, 5 e 6 | EXECUTADAS por agente de IA separado | Revisão humana ou de terceiros: NÃO EXECUTADA |

Nenhuma entrega passou de TESTADO LOCALMENTE: nada está INTEGRÁVEL, VALIDADO EM HOMOLOGAÇÃO nem PRONTO PARA SUBMISSÃO INSTITUCIONAL.

## Testes executados

Fase 6, em 03/10/2026:
- `scripts/testar.sh` → **443 passed** (329 do fim da Fase 5 + testes de modo central, âncora, rodada, interface, uso da interface, relatório A4 e 31 de regressão da revisão da Fase 6).
- `scripts/demo.sh` → "Resultado: OK". `scripts/demo_sincronizacao.sh` → "Resultado: OK" (conflito, decisão, aparelho converge).
- `python3 scripts/gerar_contratos.py` → nenhum arquivo gerado mudou. `pip-audit -r requirements-dev.txt` → "No known vulnerabilities found".
- `scripts/interface.sh` → a interface abriu em http://127.0.0.1:8765/ (resposta 200 em `/entrar`); login, navegação e coleta em etapas feitos por Chromium automatizado.
- `scripts/verificar_interface.js` (Chromium + axe-core 4.13, fora da suíte): 83 telas, 0 violações; 12 itens de contraste que a ferramenta não decide (rótulos do mapa sobre a área) conferidos por cálculo em teste; sem rolagem horizontal a 360 px; alvos de toque ≥ 44 px, exceto os pontos do mapa (~32 px, R-35); foco visível; zoom 200% sem rolagem lateral.
- O relatório HTML foi impresso em PDF A4 pelo Chromium e conferido visualmente (6 páginas, sem linha de tabela cortada).

**NÃO EXECUTADOS:** teste da interface e do relatório com **leitor de tela** e com **pessoas usuárias** (campo e escritório); **autenticação real**; uso fora de 127.0.0.1; **abertura, validação e publicação do XLSForm no Survey123 Connect**; formato real de exportação do Survey123; qualquer acesso a ArcGIS, Radar Ambiental ou Painel do art. 18; sincronização em rede ou aparelho reais (GPS real); mapa base offline; carga e desempenho; backup agendado, retenção e guarda institucional da âncora; **revisão independente humana ou de terceiros**; capacitação de turma; varredura de dependências em rotina automática; teste em navegadores além do Chromium e em celular físico.

## Falta

- Os itens NÃO EXECUTADOS acima e o checklist de `docs/homologacao.md` (nenhum item aprovado).
- Capacitação de turma (existe guia, `docs/guia-capacitacao.md`); avaliação da interface local com pessoas usuárias e leitor de tela.
- Pendências científicas: protocolo validado, limiares, "degradação severa" (LA-02 a LA-04, LA-08).
- Pendências institucionais: quem exerce a vistoria, capacitação prévia, base legal para compartilhar dados (RQ-70), camadas autorizadas (LA-09), relação com o Painel do art. 18 (LA-10).

## Próximo passo exato

Fase 6 concluída como protótipo local; **nenhuma fase seguinte está definida**. O que destrava o resto (ver `docs/pendencias.md`): teste da interface com pessoas usuárias e leitor de tela; autenticação institucional; quem guarda a âncora da trilha; organização ArcGIS e Client ID (LA-05); formato de troca com o Painel (LA-10); protocolo de campo validado (LA-04); retenção e sigilo (LA-06).
