# Motor de protocolo — especificação

Nível: **TESTADO LOCALMENTE** (Fase 3). Proveniência: INSTITUCIONAL (requisitos), AUTORAL (desenho).

Código: `src/gaema_sd/protocolo/` (`definicao.py`, `motor.py`). Definições: `config/protocolos/` (`gaema-descritivo-0.1.0.json`, `gaema-prototipo-teste-0.1.0.json`). Testes: `tests/test_protocolo.py`.

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
| CAT-D | Solo exposto e processo erosivo observados | solo exposto registrado como presente (sim/não) e erosão (laminar, sulcos, ravinas ou voçorocas) presente |

Situações fora da tabela resultam em "NÃO CLASSIFICADO", nunca em categoria forçada. Quando mais de uma categoria se aplica ao mesmo ponto, o ponto também fica "NÃO CLASSIFICADO (categorias concorrentes)": não há regra de precedência. Não existe categoria da área inteira; o resultado é por ponto, com a contagem de pontos por categoria.

## Como o motor funciona (implementado)

1. **Entradas**: o núcleo tira uma "fotografia" canônica dos pontos, observações (valor bruto e unidade), medições (brutas) e hashes das evidências da campanha. A fotografia e seu hash (`hash_entradas`) ficam gravados no `Diagnostico`.
2. **Presença**: observações com unidade `presenca` aceitam só "sim" ou "não". Variável registrada em outra unidade (por exemplo, solo exposto em %) **não** é convertida em presença, porque isso exigiria um limiar; a regra fica "não avaliável", com o motivo.
3. **Regras**: cada regra é avaliada por ponto como disparada, não disparada ou não avaliável (dado ausente, unidade diferente ou observações conflitantes). Operadores aceitos: `presente`, `ausente`, `qualquer_presente`. Operadores numéricos são recusados ao carregar a definição.
4. **Penetrometria**: estatística descritiva por ponto e profundidade (repetições, mínimo, máximo, média aritmética), após conversão de unidades; nenhum limiar.
5. **Limitações automáticas**: resultado só vale após revisão humana; ausência de conclusão jurídica; pontos com GPS acima do limite operacional; regras não avaliáveis; falta de medições ou evidências; alcance do hash.
6. **Reprodução**: `Nucleo.reproduzir_diagnostico` recalcula com a versão de protocolo e a fotografia gravadas e compara hashes, resultado completo, texto, categorias e regras. Também informa se os dados atuais da campanha ainda são iguais aos usados.
7. **Protocolo alterado**: versão de protocolo é imutável; a mesma versão com conteúdo diferente é recusada; mudança exige nova versão; diagnósticos antigos continuam reproduzíveis com a versão que usaram.
8. **Diagnóstico só pelo motor**: o núcleo recusa gravar `Diagnostico` por outro caminho.

## Variáveis (já modeladas em `VariavelCampo`)

Cobertura e vigor da forrageira, solo exposto, plantas invasoras, cupins de montículo, erosão laminar, sulcos, ravinas, voçorocas, resistência à penetração (com profundidade e repetições em `MedicaoPenetracao`), umidade do solo, animais e pastejo, contexto seco ou chuvoso, drenagem, declividade, manejo informado, hipótese alternativa e outras.

## Pendências científicas

- Protocolo de amostragem (número de pontos por área, repetições, profundidades): PENDENTE.
- Limiares e pesos: PENDENTE; só entram com referência documental e registro em `docs/decisoes.md`.
- Validação do protocolo para o Cerrado tocantinense: PENDENTE.
