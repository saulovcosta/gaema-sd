# CLAUDE.md — GAEMA SD

Usuário: Promotor de Justiça, não programa. Responder em português claro e curto. Uma pergunta por vez, só se bloqueado. Nunca pedir senha/token/chave. Nunca pedir que ele edite arquivo técnico.

## Comandos
- Testes: `scripts/testar.sh` (ou `python3 -m pytest`)
- Teste único: `python3 -m pytest tests/test_estados.py -k nome`
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
- Evidencia, VersaoProtocolo, Relatorio e RevisaoTecnica são imutáveis: correção = novo registro vinculado.
- Parâmetros operacionais em `config/parametros.json`, sempre com proveniência.
