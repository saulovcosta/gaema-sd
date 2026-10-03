# GAEMA SD

Módulo autoral do Radar Ambiental do Ministério Público do Estado do Tocantins (nome provisório) para **apoiar** a identificação e o diagnóstico de pastagens degradadas: da triagem por imagem de satélite à vistoria de campo, ao relatório e ao monitoramento.

> **Situação atual:** protótipo em desenvolvimento, com **dados sintéticos**. Não está integrado a nenhum sistema do MPTO nem ao ArcGIS. Nenhum resultado tem validade científica ou jurídica.

## O que o sistema faz (e o que não faz)

- **Faz:** organiza áreas suspeitas, alertas, demandas, vistorias, medições, fotos, diagnóstico descritivo, revisão técnica, relatório e acompanhamento.
- **Não faz:** não conclui autoria, ilicitude, dano jurídico, responsabilidade ou nexo causal. Essas conclusões são sempre humanas.
- Imagem de satélite gera só **sinal**; quem confirma é a vistoria, e quem conclui é o revisor técnico.

## Referência

Inspira-se funcionalmente no SIPADE (IFTM e MPMG), sem copiar código, textos ou telas. O que se sabe publicamente do SIPADE está em `docs/fontes.md`.

## Fases

| Fase | Conteúdo | Situação |
|---|---|---|
| 1 | Descoberta, fontes, arquitetura, estrutura | Concluída |
| 2 | Núcleo: entidades, fluxo de estados, validações, auditoria | Concluída (testada localmente) |
| 3 | Protótipo local ponta a ponta e relatório | Próxima |
| 4 | Robustez: offline, sincronização, segurança | Não iniciada |
| 5 | Preparação institucional: ArcGIS, formulário XLSForm, homologação | Não iniciada |

Detalhes do andamento: `docs/ESTADO.md`.

## Documentos principais

- `docs/fontes.md` — fontes consultadas, fatos, inferências, lacunas e decisões
- `docs/sipade-videos.md` — o que os vídeos públicos do SIPADE mostram e o que muda no GAEMA SD
- `docs/decisoes.md` — escolhas de arquitetura com justificativa
- `docs/requisitos.md` — requisitos com origem e nível de pronto
- `docs/riscos.md` — riscos e mitigação
- `docs/dominio.md` — as 20 entidades: o que guardam, regras e retenção
- `docs/estados.md` — fluxo da demanda: 23 situações, quem pode mudar e quando
- `docs/protocolo.md` — como o diagnóstico será calculado (ainda não implementado)
- `docs/prompt-gaema-sd.md` — especificação original

## O que já existe (Fase 2)

- Cadastro das 20 entidades com regras de preenchimento.
- Fluxo da demanda com 23 situações e 79 mudanças possíveis, cada uma com quem pode fazer, condições e motivo.
- Controle de acesso por papel, feito no núcleo (não depende da tela).
- Registro de auditoria encadeado, que denuncia qualquer alteração ou remoção.
- Proteção contra perda silenciosa (edições simultâneas geram aviso de conflito) e contra duplicidade em reenvio.
- Conferência de geometria, GPS, unidades de medida e anexos.

Ainda não há tela nem relatório.

## Para quem programa

```bash
scripts/testar.sh
```

Requer Python 3.11+. Dependências fixadas em `requirements-dev.txt`.
