# Estado do projeto

Atualizado em: 03/10/2026, Fase 2.

## Feito

### Fase 1 — ESPECIFICADO
- Inventário, leitura de fontes (F1–F10), matriz fatos/inferências/lacunas/decisões (`docs/fontes.md`).
- Arquitetura (c) recomendada (`docs/decisoes.md`), requisitos com proveniência, riscos, estrutura do projeto.
- Vídeos do SIPADE (F3, F10): só título e canal confirmados. YouTube exige login anti-robô; cópias no Google Drive do usuário estão em pasta privada. Conteúdo **não visto**.

### Fase 2 — TESTADO LOCALMENTE
- 20 entidades (`src/gaema_sd/dominio/entidades.py`), documentadas em `docs/dominio.md` (gerado).
- Máquina de estados: 23 estados, 79 transições, papéis, pré-condições, motivo, reversão (`docs/estados.md`, gerado).
- Validações: geometria, coordenada, GPS (alerta de GPS ruim), unidades com bruto preservado, anexos por assinatura e SHA-256, obrigatórios, regras por entidade.
- Auditoria encadeada por hash, somente acréscimo (gatilhos SQLite), logs sem dados sensíveis.
- Política de acesso por papel no núcleo; leitura de dado restrito auditada.
- Repositório SQLite: conflito de atualização (versão), reenvio idempotente, histórico de versões.
- Fachada `Nucleo`: acesso → validação → gravação → auditoria na mesma transação; recusas auditadas.
- Contratos JSON Schema (`schemas/`) e cenário sintético (`fixtures/sinteticos/`), gerados e conferidos por teste.

## Testes executados

`python3 -m pytest` → **100 passed** (03/10/2026).

Cenários obrigatórios do §14 cobertos nesta fase: envio duplicado, conflito de atualização (inclusive 8 conexões simultâneas), anexo inválido, GPS ruim, geometria inválida, variável obrigatória ausente, acesso indevido.

**NÃO EXECUTADOS** (dependem das Fases 3–4): perda de rede, retomada após interrupção (só a transição COLETA_PARCIAL → EM_CAMPO foi testada), serviço indisponível, protocolo alterado, relatório reemitido (só a regra de validação foi testada), acessibilidade, backup e restauração.

## Falta

- Revisão independente do código da Fase 2: em andamento; correções em commit próprio.
- R-13: o contexto das transições ainda é informado pelo chamador; na Fase 3 o núcleo deve montá-lo a partir do banco.
- Fases 3 a 5.

## Próximo passo exato

Fase 3: criar `src/gaema_sd/estados/contexto.py` com `montar_contexto(repo, demanda_id)` e fazer `Nucleo.transitar` usá-lo no lugar do contexto externo; em seguida, motor de protocolo (`src/gaema_sd/protocolo/`) conforme `docs/protocolo.md`.
