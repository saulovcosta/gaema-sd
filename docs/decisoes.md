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
- **Risco:** o canal é simulado (`CanalSimulado`); nada foi testado em rede real, aplicativo de campo ou Survey123. O dispositivo não recebia de volta a versão resolvida pela central (resolvido na Fase 5; ver DEC-016). Itens dependentes de um registro em conflito seguem o envio normal.
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

## DEC-016 — Reconciliação no dispositivo e retenção de envios em conflito (03/10/2026)

- **Hipótese:** a decisão do coordenador volta ao aparelho por consulta (o dispositivo pergunta pelos itens que enviou e ficaram em conflito), e a numeração de versões do aparelho pode diferir da central por um deslocamento fixo por registro.
- **Motivo:** (1) fechar a lacuna R-18 da Fase 4; (2) **defeito da Fase 4 reproduzido**: depois de um conflito, uma segunda correção do mesmo registro, já na fila, tinha base igual à versão atual da central e era aplicada por cima dela, sobrescrevendo a edição da central sem aviso.
- **Impacto:**
  - Envios posteriores da mesma entidade ficam **retidos** enquanto houver conflito sem decisão; o aparelho não corrige o registro nesse intervalo.
  - `Nucleo.consultar_decisoes_conflito` (ação `SINCRONIZAR`, auditada) devolve só conflitos RESOLVIDOS, com o motivo saneado, a versão atual e a versão resultante.
  - MANTER_CENTRAL: o aparelho grava a versão da central (uma gravação local), descarta os envios retidos (com registro) e guarda o deslocamento. ACEITAR_DISPOSITIVO: o aparelho só realinha versões (deslocamento) e reajusta a base dos retidos, que então são enviados. `Evidencia` (imutável) só registra a decisão.
  - Tabelas novas no aparelho (`decisoes_conflito`, `deslocamento_versao`), criadas sem mudar `VERSAO_ESQUEMA`.
  - A central não guarda de quem veio o conflito: a consulta é pelo hash do item, e qualquer técnico que o conheça pode vê-lo (RESTRITA, auditado).
- **Risco:** rede simulada; sem teste em aparelho. Decisão tomada enquanto o aparelho tem edições novas só em registros diferentes é tratada; edição local nova no mesmo registro é bloqueada até a decisão.
- **Teste:** `tests/test_reconciliacao.py` (inclui a reprodução do defeito; duas mutações no código foram pegas pelos testes).

## DEC-017 — Adaptadores ArcGIS só como interface; XLSForm gerado do domínio (03/10/2026)

- **Hipótese:** é possível preparar a integração sem declará-la: interfaces (`Protocol`), implementações que recusam, tradução pura e um XLSForm gerado dos mesmos enums e unidades do núcleo.
- **Motivo:** DEC-001 e LA-05 (nenhuma organização ArcGIS acessível); R-06 (modelo divergir do ArcGIS).
- **Impacto:**
  - Código em `src/gaema_sd/adaptadores/`; documentação, XLSForm em CSV e exemplo sintético em `adapters/arcgis/`. O CSV é gerado por `scripts/gerar_contratos.py` e conferido por teste; o `.xlsx` sai sob demanda.
  - Uma submissão = um ponto; só repetições de um nível. O formulário não define profundidade, repetições nem limiar; GPS ruim é alerta do núcleo, não bloqueio.
  - Formato de entrada da tradução **neutro** (definido aqui), porque o formato real de exportação do Survey123 não foi verificado.
  - Dependências de desenvolvimento novas, fixadas: `openpyxl` e `pyxform` (e as que ele exige). `pip-audit` sem achados em 03/10/2026.
- **Risco:** pyxform confere sintaxe XLSForm/ODK, não o comportamento no Survey123 Connect (R-23, R-24, R-27). O único aviso conhecido do pyxform (tamanho máximo de imagem) fica registrado, porque um valor seria invenção.
- **Teste:** `tests/test_xlsform.py`, `tests/test_adaptadores.py`.

## DEC-018 — Pacote de exportação em formato próprio, sem dados sensíveis (03/10/2026)

- **Hipótese:** um pacote JSON aberto com identificadores técnicos, estados, contagens, rótulos de validade e hashes serve de base de conversa com a equipe do Radar sem expor geometria ou texto livre.
- **Motivo:** RQ-67; o formato do Painel é desconhecido (LA-10); classificação de sigilo e base legal pendentes (LA-06, RQ-70).
- **Impacto:** `Nucleo.exportar_painel` (ação `EXPORTAR`, COORDENADOR e MEMBRO_MP; auditada com o hash do pacote); esquema em `schemas/exportacao-painel.schema.json`, gerado e conferido. Sem geometria, coordenadas, títulos, objetivos, referência interna nem pessoas. O critério de priorização é repetido como registrado por pessoa.
- **Risco:** pode ser lido como integração ou formato oficial (R-25); o pacote leva o campo `aviso`. Conteúdo dos relatórios dos marcos do art. 20 não está coberto (RQ-71 parcial).
- **Teste:** `tests/test_exportacao.py`.

## DEC-019 — Checklist de homologação sem aprovação; documentos conferidos por teste (03/10/2026)

- **Hipótese:** documentos institucionais só são confiáveis se algo os impede de ficar defasados ou otimistas.
- **Impacto:** `docs/homologacao.md`, `docs/pendencias.md`, `docs/integracao-radar-painel.md` e `docs/guia-capacitacao.md`. Teste exige: nenhuma linha do checklist aprovada, situação só `NÃO EXECUTADO`/`PENDENTE`/`EXECUTADO LOCALMENTE`, todo LA de `fontes.md` em `pendencias.md`, arquivos citados existentes, avisos obrigatórios no guia, gabarito do guia igual ao resultado da demonstração, e ausência das expressões vedadas.
- **Risco:** o teste de linguagem cobre só estes documentos; a regra continua valendo para os demais.
- **Teste:** `tests/test_documentos.py`.

## DEC-020 — Revisão independente das Fases 4 e 5: achados e correções (03/10/2026)

- **Hipótese:** um revisor separado, instruído a quebrar o que foi feito, acha o que os testes do autor não acharam.
- **Método:** um agente separado (de IA, não humano) rodou mais de mil cenários de falha e 35 mutações em cópia do repositório, sem editar nada. Cada achado foi reproduzido por um teste novo que **falhou no código anterior** e passa agora; 20 mutações nas correções novas foram todas pegas pelos testes.
- **Corrigidos (número do achado do relatório):**
  1. (alta) dado de campo aceito sem ponto/campanha, de usuário fora da equipe e com a demanda já adiante (alterava o que sustenta o diagnóstico) → origem, equipe e estado conferidos em `receber_sincronizacao`; reenvio idempotente segue valendo.
  2. (alta) erro de acesso transformava todo o campo em REJEITADO definitivo → `AcessoNegado` interrompe a rodada sem rejeitar; `reenfileirar_rejeitados` (não reenfileira o que a decisão do coordenador descartou).
  3. item sem arquivo de evidência travava a fila → vira REJEITADO e a fila segue.
  4. ACEITAR_DISPOSITIVO apagava alteração posterior da central do estado corrente → recusado se a versão mudou depois do conflito.
  5. e 16. backup "conferia" sem arquivos e confiava no manifesto → confere hashes contra o banco, contagens, eventos, conflitos, lista fechada, sem link simbólico, `-wal` órfão no destino, manifesto malformado e CLI com banco inexistente; `criar_backup` verifica o que criou.
  6. e 11. tradução descartava fotos e nota de acesso em silêncio, e repetição de penetrometria duplicada colidia → erro explícito (`ignorar_nao_traduzidos`, `campos_de_campanha`).
  7. id de registro formava caminho do relatório → UUID obrigatório e conferência do caminho.
  8. pacote de exportação levava id de usuário e texto livre do protocolo → só papéis; categoria e rótulo só em padrão fechado; código de categoria do protocolo restrito; id opaco.
  9. `observador_id` forjável (alimentava a regra de independência do revisor) → autoria imutável e igual ao usuário.
  10. XLSForm obrigava sim/não e usava `now()` → presença não obrigatória ("não observado" = em branco); sem valor padrão.
  12. CRIAR reenviado após alteração da central virava conflito falso → compara com a versão 1 do histórico.
  13. falha ao mover a demanda perdia o conflito → conflito gravado e auditado antes; a transição é tentada depois e a cada reenvio.
  14. técnico B lia decisão de A → coluna `enviado_por`; **esquema 2** com migração do 1 (17).
  15. aplicar a mesma decisão duas vezes desfazia trabalho novo → idempotente; descartes passam a ser auditados.
  18. integração ATIVA em ambiente de desenvolvimento → recusada.
  19. e 20. guia e gabarito imprecisos (ponto da interrupção; conflito só muda a demanda em AGUARDANDO_SINCRONIZACAO; papéis; mascaramento) → corrigidos e conferidos por teste; mascaramento de CPF cobre mais formatos e a chave sensível não casa pedaço de palavra; testes novos para contagens e último hash do manifesto e para a permissão no caminho de conflito.
- **Não corrigidos (limites aceitos e registrados):** `Nucleo.registrar` direto na central não aplica as regras de origem/equipe/estado, porque o aparelho usa o mesmo método sem ter a campanha (R-28, H-S07); a fila do aparelho é estado local e grava fora da trilha (os descartes por decisão agora são auditados); trilha truncada e banco trocado com manifesto refeito seguem possíveis para quem controla a pasta (R-19, ancoragem externa PENDENTE); conflitos antigos (esquema 1) ficam visíveis a qualquer técnico (`enviado_por` vazio).
- **Risco:** o revisor foi um agente de IA; não substitui revisão humana ou de terceiros (H-S02, R-30).
- **Teste:** `tests/test_regressao_revisao_f4f5.py`, `tests/test_regressao_revisao_f4f5_b.py`.

## DEC-021 — Modo da instalação: a central confere toda entrada de campo (03/10/2026)

- **Contexto:** R-28: `Nucleo.registrar` direto não conferia origem, equipe e estado, porque o aparelho usa o mesmo método sem ter a campanha.
- **Decisão:** `Nucleo(..., modo="central" | "dispositivo" | "livre")`. Em "central" (padrão) toda escrita de dado de campo confere origem, equipe e estado de coleta; "dispositivo" grava local e enfileira; "livre" só em testes. O modo é somente leitura depois de criado. Na revisão da Fase 6 (DEC-026) a regra passou a valer também para o registro **gravado** e o vínculo (ponto/campanha) ficou imutável.
- **Risco:** quem cria o `Nucleo` escolhe o modo; a interface recusa qualquer modo que não seja "central".
- **Teste:** `tests/test_modo_central.py`, `tests/test_regressao_fase6.py`.

## DEC-022 — Âncora externa da trilha (03/10/2026)

- **Contexto:** R-19: quem controla a pasta pode truncar a trilha ou refazê-la inteira com o manifesto do backup.
- **Decisão:** âncora = número de eventos + último hash + data, com selo de forma; gerada pelo sistema (`Nucleo.gerar_ancora`, CLI `backup ancorar`, botão na tela de auditoria) só se a cadeia confere; conferida em `verificar_auditoria` e `verificar_backup`. Na interface a âncora é **colada** (até 4 KiB), nunca lida por caminho do servidor.
- **Limite:** a âncora só protege se for guardada por quem não controla o banco; o selo é recalculável por quem tem o arquivo. Quem guarda e onde é decisão institucional (PENDENTE).
- **Teste:** `tests/test_ancora.py`, `tests/test_regressao_fase6.py`.

## DEC-023 — Rodada do aparelho (03/10/2026)

- **Decisão:** `Sincronizador.rodada()` = consulta as decisões de conflito e depois envia a fila; resume em `ResumoRodada`. Comando de simulação: `python -m gaema_sd.sincronizacao simular PASTA` (`scripts/demo_sincronizacao.sh`). Na interface, o botão "Sincronizar agora" chama a rodada.
- **Limite:** canal e aparelho simulados (R-17).
- **Teste:** `tests/test_rodada.py`.

## DEC-024 — Interface local de operação (03/10/2026)

- **Decisão:** WSGI da biblioteca padrão, só em 127.0.0.1; Jinja2 com escape; sem JavaScript; CSP `default-src 'none'`; conferência de Host (contra DNS rebinding) e de Origin; token CSRF; cookie HttpOnly e SameSite=Strict; `Referrer-Policy: same-origin`; uma thread por conexão com **uma trava única** em volta do núcleo (o corpo é lido antes da trava, com limite de 64 KiB e tempo máximo de conexão); sessões anônimas com teto próprio e expiração por tempo (8 h, AUTORAL). Toda regra, acesso e auditoria seguem no `Nucleo`.
- **Login:** escolhe-se um usuário SINTÉTICO de teste. **Não há autenticação real** (R-31).
- **Alternativa descartada:** framework web completo (mais dependências, sem ganho para um protótipo local).
- **Teste:** `tests/test_interface.py`, `tests/test_interface_uso.py`, `tests/test_regressao_fase6.py`.

## DEC-025 — Redesenho para quem não programa (03/10/2026)

- **Decisão:** linguagem comum (`interface/linguagem.py`: 23 situações com nome, tom e próxima ação; papéis; mensagens "o que houve / como resolver"); identidade visual própria (verde sóbrio, temas claro e escuro, contraste AA calculado; nada copiado do SIPADE nem do Radar Ambiental); situação por ícone + texto; escala tipográfica fixa; botões sem permissão desabilitados com motivo; Campo com barra de rede/fila/última sincronização e coleta em 4 etapas com rascunho local; mapa SVG com escala aproximada e lista sincronizada; relatório em A4.
- **Verificação:** navegador real automatizado (`scripts/verificar_interface.js`: 83 telas em 360 e 1280 px, claro e escuro, zoom 200%, axe-core 4.13). Só verificações automáticas; leitor de tela e pessoas usuárias NÃO EXECUTADOS.

## DEC-026 — Revisão independente da Fase 6 e verificação com navegador (03/10/2026)

- **Método:** agente de IA separado revisou o commit 542dd82 (interface, modo central, âncora, rodada, backup), com scripts próprios e 74 mutações (47 mortas). 15 achados (1 alto, 6 médios, 8 baixos), todos reproduzidos de novo contra a árvore corrigida.
- **Corrigidos:** (1, alto) atualização movia dado de campo de outra demanda e não conferia o registro gravado → vínculo imutável e conferência do gravado; (2) conflito aceito depois da coleta e "sequestro" de ponto por CRIAR com id alheio → recusados; (3) campo da âncora lia caminho do servidor antes da permissão → âncora colada, permissão primeiro, limite de tamanho; (4) `Content-Length` negativo e conexão parada travavam o servidor → recusa, threads com trava única, tempo máximo; (5) GETs anônimos derrubavam sessões → teto para anônimas e prazo; (6) técnico movia e listava demanda de outra equipe → recusado e filtrado; (7) histórico expunha trilha a quem não audita → só mudanças de situação, sem pessoas nem motivo; (8) evidência com observação de outra campanha → recusada; (9) modo do núcleo mutável → somente leitura; (10) CLI da âncora com traceback e ancorando trilha adulterada → mensagens e recusa; (11) token não ASCII dava 500 → 403; (13) backups no mesmo segundo e simultâneos → mensagem clara e reserva atômica; (14) banco legado sem versão → migração da coluna; (15) textos que prometiam demais → "cadeia conferida; sem âncora não exclui reescrita" e "o aparelho só sabe quando consultar". Também: campo repetido no formulário recusado; `/sair` encerra a sessão no servidor; mutantes sobreviventes de permissão e auditoria cobertos por teste.
- **Achado da verificação com navegador (não da revisão):** com `Referrer-Policy: no-referrer` o Chromium manda `Origin: null` em todo formulário, e a interface recusava o próprio login. Os testes sem navegador não pegavam. Corrigido para `same-origin`, com teste.
- **Não corrigido (registrado):** a trilha é lida inteira a cada página (12; R-34); pontos do mapa com ~32 px a 360 px (R-35).
- **Risco:** o revisor é um agente de IA (R-30).
- **Teste:** `tests/test_regressao_fase6.py` (mutações nas correções: 5 de 6 mortas; a sobrevivente é equivalente).

## DEC-027 — Cabeçalho institucional e endosso configurável (03/10/2026)

- **Contexto:** pedido do usuário: o relatório deve trazer a identificação do MPTO, do CAOMA e do GAEMA, sem sugerir chancela que não existe.
- **Decisão:**
  - O logo fornecido pelo usuário fica em `assets/logo-mpto-gaema.png`, com o hash conferido por teste. No HTML ele vai embutido (`data:`), porque o relatório não tem recurso externo; no PDF, como imagem.
  - O logo aparece **só no cabeçalho do relatório**; a interface mantém a identidade própria (DEC-025).
  - A frase institucional vem de uma única função, `relatorio/institucional.py::linha_institucional`.
  - O endosso vem só de `config/endosso.json`, vazio por padrão, e só vale com número e data do ato válidos e não futuros em relação à emissão. **Na dúvida (campo vazio, parcial ou malformado, arquivo ausente), o relatório sai como não endossado.**
  - O estado do endosso fica nos dados do relatório.
- **Também:** tabela de pontos com coordenadas em uma linha; mapa do relatório maior e centralizado (640×420 no HTML, largura útil no PDF); títulos do PDF presos ao conteúdo seguinte; tabelas curtas do HTML não se partem.
- **Risco:** R-36.
- **Teste:** `tests/test_relatorio_institucional.py`.
