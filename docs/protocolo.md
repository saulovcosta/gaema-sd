# Motor de protocolo — especificação

Nível: **ESPECIFICADO** (implementação na Fase 3). Proveniência: INSTITUCIONAL (requisitos), AUTORAL (desenho).

## Princípios

1. **Modo descritivo por padrão.** Sem protocolo científico validado, o sistema descreve e organiza as observações. Não classifica.
2. **Protótipo rotulado.** Para desenvolvimento, existe o modo `PROTOTIPO_TESTE`, com o rótulo obrigatório **"PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"** em toda saída (validação já implementada em `VersaoProtocolo`).
3. **Nenhum limiar inventado.** Regras do protótipo usam condições explícitas e configuráveis; valores numéricos (NDVI, penetrometria, percentuais) ficam vazios até haver fonte (lacunas LA-02 a LA-04).
4. **Reprodutibilidade.** Diagnóstico guarda hash da definição do protocolo e hash das entradas; recomputar com a mesma versão e as mesmas entradas dá o mesmo resultado.
5. **Explicação.** Todo resultado lista as regras disparadas e as que não puderam ser avaliadas (dado ausente).
6. **Fronteira.** O motor nunca produz autoria, ilicitude, dano jurídico, responsabilidade ou nexo causal.

## Categorias descritivas do protótipo

Inspiradas nos quatro cenários públicos do SIPADE (FC-04, OBSERVAÇÃO PÚBLICA), com redação própria e **sem** a expressão "dano ambiental" como saída automática:

| Código | Descrição | Condição no protótipo (presença/ausência, sem limiar numérico) |
|---|---|---|
| CAT-A | Sem indícios das variáveis de degradação observadas | invasoras ausentes, cupins ausentes, erosão ausente |
| CAT-B | Presença de plantas invasoras | invasoras presentes, cupins ausentes |
| CAT-C | Presença de invasoras e cupins de montículo | invasoras presentes, cupins presentes |
| CAT-D | Solo exposto e processo erosivo observados | solo exposto informado como relevante pelo técnico e erosão (laminar, sulcos, ravinas ou voçorocas) presente |

Situações fora da tabela resultam em "não classificado; ver descrição", nunca em categoria forçada.

## Variáveis (já modeladas em `VariavelCampo`)

Cobertura e vigor da forrageira, solo exposto, plantas invasoras, cupins de montículo, erosão laminar, sulcos, ravinas, voçorocas, resistência à penetração (com profundidade e repetições em `MedicaoPenetracao`), umidade do solo, animais e pastejo, contexto seco ou chuvoso, drenagem, declividade, manejo informado, hipótese alternativa e outras.

## Pendências científicas

- Protocolo de amostragem (número de pontos por área, repetições, profundidades): PENDENTE.
- Limiares e pesos: PENDENTE; só entram com referência documental e registro em `docs/decisoes.md`.
- Validação do protocolo para o Cerrado tocantinense: PENDENTE.
