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
| 2 | Núcleo: entidades, fluxo de estados, validações, auditoria | Próxima |
| 3 | Protótipo local ponta a ponta e relatório | Não iniciada |
| 4 | Robustez: offline, sincronização, segurança | Não iniciada |
| 5 | Preparação institucional: ArcGIS, formulário XLSForm, homologação | Não iniciada |

Detalhes do andamento: `docs/ESTADO.md`.

## Documentos principais

- `docs/fontes.md` — fontes consultadas, fatos, inferências, lacunas e decisões
- `docs/decisoes.md` — escolhas de arquitetura com justificativa
- `docs/requisitos.md` — requisitos com origem e nível de pronto
- `docs/riscos.md` — riscos e mitigação
- `docs/prompt-gaema-sd.md` — especificação original

## Para quem programa

```bash
scripts/testar.sh
```

Requer Python 3.11+. Dependências fixadas em `requirements-dev.txt`.
