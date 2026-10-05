# CLAUDE.md — GAEMA SD

Usuário: Promotor de Justiça, não programa. Responder em português claro e curto. Uma pergunta por vez, só se bloqueado. Nunca pedir senha/token/chave. Nunca pedir que ele edite arquivo técnico.

## Comandos
- Testes: `scripts/testar.sh` (ou `python3 -m pytest`)
- Teste único: `python3 -m pytest tests/test_estados.py -k nome`
- Demonstração ponta a ponta: `scripts/demo.sh` (saída em `saida/`, fora do git)
- Interface local: `scripts/interface.sh` (http://127.0.0.1:8765/, dados sintéticos). Verificação visual/axe fora da suíte: `scripts/verificar_interface.js` (precisa de playwright-core e axe-core instalados fora do projeto)
- Backup: `python -m gaema_sd.backup criar|verificar|restaurar|rollback` (restauração e rollback só sobre caminhos fechados/novos)
- Após mudar entidades, estados ou fixtures: `python3 scripts/gerar_contratos.py` (regera `schemas/`, `docs/estados.md`, `docs/dominio.md`, `fixtures/sinteticos/`; `tests/test_contratos.py` falha se esquecer)
- Textos de `docs/dominio.md` ficam em `src/gaema_sd/dominio/documento.py`; nunca editar os arquivos gerados à mão

## Regras que não podem ser quebradas
- IMPORTANTE: não inventar fórmulas, pesos, limiares (NDVI, penetrometria etc.), protocolos validados, APIs ou textos oficiais. Parâmetro sem fonte fica sem valor padrão ou é rotulado AUTORAL/PENDENTE.
- Só dados SINTÉTICOS. Nenhum dado real de pessoa, imóvel ou procedimento.
- Segredos só em `.env` (ignorado pelo git).
- Sem campos ou saídas de autoria, ilicitude, dano jurídico, responsabilidade ou nexo causal (`tests/test_fronteira_juridica.py`).
- Sinal remoto ≠ vistoria ≠ resultado computado ≠ revisão técnica ≠ providência.
- Não declarar integração ArcGIS/MPTO sem ambiente real. Adaptadores em `adapters/` são só interface.
- Não usar "perfeito", "produção", "homologado", "integrado ao MPTO". Classificar entregas pelo nível de pronto (ver `docs/requisitos.md`).
- Não marcar teste como aprovado sem executá-lo.
- Todo requisito novo leva etiqueta de proveniência.

## Fluxo
- Ao fim de cada fase: testes, atualizar README.md, CLAUDE.md, `docs/ESTADO.md`; commit; push na branch designada.
- Decisões novas: `docs/decisoes.md`. Riscos: `docs/riscos.md`.
- Código em `src/gaema_sd/`. Toda escrita passa por `nucleo.Nucleo` (acesso → validação → gravação → auditoria na mesma transação). Não gravar direto no `Repositorio` fora de testes.
- Estado da Demanda só muda por `Nucleo.transitar`. Tabela única em `estados/maquina.py`.
- Evidencia, VersaoProtocolo, Relatorio, RevisaoTecnica e Diagnostico são imutáveis: correção = novo registro vinculado.
- Diagnóstico só por `Nucleo.computar_diagnostico` (motor em `protocolo/`); relatório só por `Nucleo.emitir_relatorio`; evidência com arquivo só por `Nucleo.registrar_evidencia`.
- Protocolos em `config/protocolos/`: versão publicada não muda; alteração = nova versão. Só operadores de presença/ausência até haver protocolo validado.
- Parâmetros operacionais em `config/parametros.json`, sempre com proveniência.
- Sincronização em `src/gaema_sd/sincronizacao/`: o dispositivo grava local e enfileira; a central só aplica por `Nucleo.receber_sincronizacao`. Divergência = conflito (nunca sobrescrever); só COORDENADOR resolve (`resolver_conflito_sincronizacao`). `CanalSimulado` é simulação, não rede real.
- Texto que vai para trilha, fila ou log passa por `auditoria.trilha.sanear_texto`; log não leva conteúdo de registro. Em testes, montar CPF/e-mail fictícios em tempo de execução (o varredor `test_sigilo_fixtures` proíbe literais).
- Esquema do banco: `VERSAO_ESQUEMA = 2` (`persistencia/sqlite.py`, migração em `Repositorio._migrar`). Tabela ou coluna nova: subir a versão, migrar o banco antigo e manter o backup coerente; esquema mais novo que o código é recusado.
- Acessibilidade do relatório: `tests/test_acessibilidade.py` é automático; leitor de tela segue NÃO EXECUTADO.
- Adaptadores ArcGIS: código só em `src/gaema_sd/adaptadores/` (interface, tradução pura, XLSForm gerado); documentação e CSV gerado em `adapters/arcgis/`. Sem módulo de rede, URL ou credencial (teste confere). Não declarar integração com ArcGIS, Radar ou Painel; formato de exportação (`Nucleo.exportar_painel`) é PRÓPRIO e sem geometria nem texto livre.
- XLSForm e esquema de exportação são gerados por `scripts/gerar_contratos.py`; não editar `adapters/arcgis/xlsform/*.csv` nem `schemas/exportacao-painel.schema.json` à mão.
- Conflito de sincronização: envios posteriores da mesma entidade ficam retidos até a decisão; o dispositivo consulta a decisão (`Sincronizador.reconciliar`) e usa `deslocamento_versao` para a base das correções.
- Documentos de homologação, pendências, integração e capacitação são conferidos por `tests/test_documentos.py`: nenhum item de `docs/homologacao.md` pode constar como aprovado; todo LA novo em `docs/fontes.md` entra em `docs/pendencias.md`.
- `Nucleo(modo="central")` (padrão) confere origem, equipe e estado de coleta em TODA entrada de dado de campo, inclusive do registro gravado; vínculo (`campanha_id`, `ponto_id`, `observacao_id`) não muda; `modo` é somente leitura. Aparelho usa `modo="dispositivo"`; `"livre"` só em testes. Técnico só lê, lista e move demanda (e campanhas, pontos, observações, medições, evidências, relatórios) da própria equipe. Correção nenhuma (atualizar ou "aceitar o aparelho") troca autoria, chave de envio ou vínculo. Identificadores são UUID; `criado_por`, `observador_id`, `registrado_por` etc. são o usuário logado e não mudam.
- Erro de acesso na sincronização é recuperável (a rodada para, nada é rejeitado); item REJEITADO volta por `reenfileirar_rejeitados` (nunca o descartado por decisão do coordenador). Item sem arquivo não pode travar a fila.
- Conflito: "aceitar o aparelho" só vale se o registro não mudou na central depois do conflito; a decisão só chega ao técnico que originou o conflito (`enviado_por`).
- Backup: `verificar_backup` confere contra o banco do próprio backup (hash de evidências e relatórios, contagens, trilha) e recusa link simbólico e arquivo fora do formato; `criar_backup` verifica o que criou. A fila do aparelho é estado local fora da trilha (descartes por decisão são auditados).
- Exportação: só papéis (nunca id de usuário); texto de categoria e rótulo só em padrão fechado; código de categoria do protocolo é restrito. Tradução de campo recusa o que não leva ao núcleo (fotos, condição e nota de acesso) em vez de descartar.
- Revisão independente feita por agente de IA não vale como revisão humana ou de terceiros: não escrever que o código foi "revisado por terceiros". Nível de pronto de cada entrega está em `docs/ESTADO.md`; o XLSForm não foi aberto no Survey123 Connect.
- Interface (`src/gaema_sd/interface/`): só apresenta; regra, acesso e auditoria ficam no `Nucleo`. Textos para leigos em `interface/linguagem.py` (sem código técnico na tela). Toda tela: faixa "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA", bloco "O que fazer agora", botão sem permissão desabilitado com motivo. Sem JavaScript, sem `style=` em atributo, sem recurso externo. Não copiar identidade visual, textos ou telas do SIPADE nem do Radar Ambiental.
- Segurança da interface: só 127.0.0.1; Host e Origin conferidos; `Referrer-Policy: same-origin` (com `no-referrer` o navegador manda `Origin: null` e o login quebra); token CSRF; campo repetido recusado; âncora é colada, nunca lida por caminho; servidor com threads e trava única em volta do núcleo (sem ela há erro 500 com usuários simultâneos; teste `test_pr4_3`). Não há autenticação real (R-31).
- Histórico de registro para quem não tem `VERIFICAR_AUDITORIA`: só mudanças de situação, sem pessoa nem motivo.
- Relatório: `relatorio/modelo.html.j2` imprime em A4; datas pelo filtro `data_br`, hashes pelo filtro `blocos` (`<data value=hash>`); manter `@page`, sem `style=`.
- Acessibilidade da interface: axe-core e navegador automatizado cobrem só o automático; não declarar conformidade WCAG; leitor de tela e pessoas usuárias seguem NÃO EXECUTADOS.
- Cabeçalho do relatório (DEC-027): logo `assets/logo-mpto-gaema.png` só no relatório (a interface mantém identidade própria); frase institucional só por `relatorio/institucional.py::linha_institucional`. Endosso só por `config/endosso.json` (vazio = sem endosso; parcial ou inválido = sem endosso); nunca escrever "endosso" sem a negativa enquanto o campo estiver vazio (`tests/test_relatorio_institucional.py`).
- Codespaces (DEC-029): `.devcontainer/devcontainer.json` (Python 3.12) roda `scripts/interface.sh`. A interface só aceita o endereço encaminhado `<CODESPACE_NAME>-<porta>.<domínio>` (origem https) quando `CODESPACES=true`. O encaminhamento real entrega Host = localhost:PORTA: a origem pública é aceita mesmo com Host local, calculada só das variáveis do GitHub, nunca de `X-Forwarded-Host` (DEC-031). Textos de "onde roda" vêm de `linguagem.onde_atende`, `como_usar_botoes` e `rodape_local`; nunca trocar o bind 127.0.0.1 nem tornar a porta pública.
- Rodada 1 (DEC-030): cookie de sessão com `Secure` só quando o pedido vem pelo https do Codespaces (`self._https`); cabeçalho `Server: GAEMA-SD` (sem versão do Python). A porta 8765 fica `"visibility": "private"`. CI em `.github/workflows/testes.yml` (pytest, demo, pip-audit; sem segredos): manter verde.
- Classificar toda verificação como UNITÁRIO, NAVEGADOR AUTOMATIZADO, CODESPACE REAL ou NÃO EXECUTADO.

