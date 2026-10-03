# CLAUDE.md — GAEMA SD

Usuário: Promotor de Justiça, não programa. Responder em português claro e curto. Uma pergunta por vez, só se bloqueado. Nunca pedir senha/token/chave. Nunca pedir que ele edite arquivo técnico.

## Comandos
- Testes: `scripts/testar.sh` (ou `python3 -m pytest`)
- Teste único: `python3 -m pytest tests/test_estados.py -k nome`
- Demonstração ponta a ponta: `scripts/demo.sh` (saída em `saida/`, fora do git)
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
- Banco novo ou tabela nova: manter `VERSAO_ESQUEMA` (`persistencia/sqlite.py`) e o backup coerentes; backup de esquema mais novo é recusado.
- Acessibilidade do relatório: `tests/test_acessibilidade.py` é automático; leitor de tela segue NÃO EXECUTADO.
- Adaptadores ArcGIS: código só em `src/gaema_sd/adaptadores/` (interface, tradução pura, XLSForm gerado); documentação e CSV gerado em `adapters/arcgis/`. Sem módulo de rede, URL ou credencial (teste confere). Não declarar integração com ArcGIS, Radar ou Painel; formato de exportação (`Nucleo.exportar_painel`) é PRÓPRIO e sem geometria nem texto livre.
- XLSForm e esquema de exportação são gerados por `scripts/gerar_contratos.py`; não editar `adapters/arcgis/xlsform/*.csv` nem `schemas/exportacao-painel.schema.json` à mão.
- Conflito de sincronização: envios posteriores da mesma entidade ficam retidos até a decisão; o dispositivo consulta a decisão (`Sincronizador.reconciliar`) e usa `deslocamento_versao` para a base das correções.
- Documentos de homologação, pendências, integração e capacitação são conferidos por `tests/test_documentos.py`: nenhum item de `docs/homologacao.md` pode constar como aprovado; todo LA novo em `docs/fontes.md` entra em `docs/pendencias.md`.
