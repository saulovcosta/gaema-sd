# Estado do projeto

Atualizado em: 03/10/2026, fim da Fase 5, depois da revisão independente das Fases 4 e 5.

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

## Nível de pronto real de cada entrega

| Entrega | Nível de pronto real | O que limita |
|---|---|---|
| Núcleo, estados, auditoria, acesso (Fase 2) | TESTADO LOCALMENTE | Sem autenticação real: o usuário é informado pelo chamador |
| Motor de protocolo, diagnóstico, relatório HTML/PDF (Fase 3) | TESTADO LOCALMENTE | Só o protótipo "sem validade científica"; protocolo validado PENDENTE |
| Sincronização: fila, reenvio, conflito, decisão de volta ao aparelho (Fases 4 e 5) | TESTADO LOCALMENTE | Rede e aparelho simulados; ainda não há comando nem rotina para o aparelho consultar decisões |
| Entrada de dado de campo na central (origem, equipe, estado) | TESTADO LOCALMENTE | Só pelo caminho de sincronização; o registro direto não confere (R-28) |
| Concorrência, segurança básica, logs | TESTADO LOCALMENTE | Threads em uma máquina; mascaramento parcial (alguns formatos de CPF e e-mail; não pega nome nem CNPJ/telefone com máscara) |
| Backup, restauração e rollback | TESTADO LOCALMENTE | Manifesto sem assinatura; sem rotina agendada, destino ou retenção; ancoragem do último hash PENDENTE |
| Relatório HTML acessível | TESTADO LOCALMENTE (verificações automáticas) | Leitor de tela e pessoas usuárias: NÃO EXECUTADO |
| Adaptadores ArcGIS | IMPLEMENTADO LOCALMENTE (interface; recusam por padrão) | Nada integrado; sem organização ArcGIS (LA-05) |
| XLSForm da vistoria | TESTADO LOCALMENTE (estrutura + sintaxe pelo pyxform) | **Não foi aberto no Survey123 Connect**; formato real de exportação não verificado |
| Tradução de submissão de campo | TESTADO LOCALMENTE | Formato de entrada neutro, não o do Survey123 |
| Pacote de exportação | TESTADO LOCALMENTE | Formato próprio; formato do Painel desconhecido (LA-10); nenhuma integração |
| Checklist, pendências, integração (documentos) | IMPLEMENTADO LOCALMENTE | Dependem de decisões institucionais; nenhum item aprovado |
| Guia de capacitação | IMPLEMENTADO LOCALMENTE | Nenhuma turma atendida; gabarito conferido por teste contra a demonstração |
| Revisão independente das Fases 4 e 5 | EXECUTADA por agente de IA separado | Revisão humana ou de terceiros: NÃO EXECUTADA |

Nenhuma entrega passou de TESTADO LOCALMENTE: nada está INTEGRÁVEL, VALIDADO EM HOMOLOGAÇÃO nem PRONTO PARA SUBMISSÃO INSTITUCIONAL.

## Testes executados

`python3 -m pytest` → **329 passed** (03/10/2026): 281 do fim da implementação da Fase 5 + 48 de regressão da revisão independente (`test_regressao_revisao_f4f5.py` e `test_regressao_revisao_f4f5_b.py`). `python3 scripts/gerar_contratos.py` regenera os arquivos gerados; `tests/test_contratos.py` passa. `scripts/demo.sh` → "Resultado: OK". `pip-audit -r requirements-dev.txt` → "No known vulnerabilities found" (executado depois da inclusão de openpyxl e pyxform). **pyxform 4.5.0 converte o XLSForm sem erro** (40 linhas em `survey`, 42 em `choices`; um aviso, de propósito: tamanho máximo de imagem não definido).

Cenários já executados (todos com rede e dispositivo simulados): os da Fase 4; conflito → decisão → convergência dos dois bancos nos dois sentidos; envio retido; consulta com falha de rede e com interrupção do processo; importação de submissão sintética; exportação com acesso indevido; e, vindos da revisão, dado de campo órfão, de fora da equipe e fora do estado, erro de acesso recuperável, item sem arquivo, "aceitar" depois de a central mudar, backup com saída errada, evidência/relatório trocados ou ausentes com manifesto refeito, link simbólico, `-wal` órfão, manifesto malformado, exportação com texto sujo no diagnóstico, id fora do formato.

**NÃO EXECUTADOS:** **abertura, validação e publicação do XLSForm no Survey123 Connect**; formato real de exportação do Survey123; qualquer acesso a ArcGIS, Radar Ambiental ou Painel do art. 18; sincronização em rede ou aparelho reais; comando ou rotina para o aparelho consultar decisões de conflito; mapa base offline; autenticação real; separação da API de entrada de campo na implantação (R-28); teste do relatório com leitor de tela e com pessoas usuárias; carga e desempenho; backup agendado, retenção e ancoragem externa do último hash; **revisão independente humana ou de terceiros** das Fases 4 e 5; capacitação de turma; tela de operação; varredura de dependências em rotina automática.

## Falta

- Os itens NÃO EXECUTADOS acima e o checklist de `docs/homologacao.md` (nenhum item aprovado).
- Capacitação de turma (existe guia, `docs/guia-capacitacao.md`); tela de operação (hoje só linha de comando).
- Pendências científicas: protocolo validado, limiares, "degradação severa" (LA-02 a LA-04, LA-08).
- Pendências institucionais: quem exerce a vistoria, capacitação prévia, base legal para compartilhar dados (RQ-70), camadas autorizadas (LA-09), relação com o Painel do art. 18 (LA-10).

## Próximo passo exato

Fase 5 concluída como preparação; **nenhuma fase seguinte está definida**. Decisões da equipe que destravam o resto (ver `docs/pendencias.md`): organização ArcGIS e Client ID (LA-05), formato de troca com o Painel (LA-10), protocolo de campo validado (LA-04), retenção e sigilo (LA-06), quem exerce a vistoria e a capacitação coordenada com o CAOMA.
