# Contrastes "a revisar" do axe-core: revisão manual (Rodada 2)

O axe-core não calcula sozinho o contraste de alguns textos e os marca como "a revisar" (resultado *incomplete*). Este documento mostra a conta feita à mão para cada um.

## Quais são

Na Rodada 1, a verificação automática listou 12 itens "a revisar". Nesta rodada, com a coleta em 5 etapas, ela passou por 91 telas (360 e 1280 px, tema claro e escuro, zoom de 200%) e listou 48 nós. Todos são textos do esquema SVG do mapa da demanda; nenhum é texto de página.

| Nó (seletor do axe) | O que é | Motivo dado pelo axe | Ocorrências |
|---|---|---|---|
| `text[x=…]` ao lado de cada ponto (P01, P02, P03) | código do ponto no mapa | `bgOverlap`: o fundo está coberto por outro elemento (a área de interesse ou o alvo de toque transparente) | 36 |
| `text[x=…]` ao lado da barra de escala | "N m (aprox.)" | `imgNode`: o elemento está dentro de uma imagem (SVG) | 12 |

O mesmo mapa aparece em várias capturas: 3 demandas, telas de coordenador e de analista, ponto selecionado, 2 larguras e 2 temas. Por isso são 4 nós por mapa, repetidos.

## Conta à mão

Fórmula do WCAG 2.x (luminância relativa, `(L1 + 0,05) / (L2 + 0,05)`). É a mesma função `razao_contraste` de `tests/test_acessibilidade.py`, conferida contra os valores de referência do WCAG.

O texto do mapa usa `fill: var(--texto)` com contorno ("halo") de 3 px na cor `var(--superficie)`, que é `paint-order: stroke`. O fundo imediato de cada letra é, portanto, a superfície. Também conferimos o pior caso, sem halo, com o texto direto sobre a área de interesse.

| Par | Tema claro | Tema escuro | Mínimo exigido | Atende? |
|---|---|---|---|---|
| texto do mapa / superfície (halo) | 16,53 | 13,57 | 4,5 (texto) | sim |
| texto do mapa / área de interesse (sem halo) | 12,29 | 9,34 | 4,5 (texto) | sim |
| ponto (círculo) / superfície | 8,56 | 9,42 | 3 (gráfico) | sim |
| ponto (círculo) / área de interesse | 6,36 | 6,48 | 3 (gráfico) | sim |
| ponto selecionado (losango) / superfície | 7,51 | 8,48 | 3 (gráfico) | sim |
| ponto selecionado (losango) / área de interesse | 5,58 | 5,83 | 3 (gráfico) | sim |
| borda da área / superfície | 7,86 | 7,96 | 3 (gráfico) | sim |

**Conclusão:** nenhum dos itens "a revisar" fica abaixo do mínimo. Não houve correção de cor nesta rodada.

## Como se mantém

- `tests/test_rodada2.py::test_contrastes_do_mapa_revisados_a_mao` lê os tokens de cor em `interface/modelos/base.html.j2` e recalcula os pares desta tabela. Se alguém trocar uma cor e o par cair abaixo do mínimo, o teste falha. Classificação: **UNITÁRIO**.
- O mesmo teste confere que o texto do mapa continua com o halo na cor da superfície.
- Os números de "a revisar" e de violações saem de `scripts/verificar_interface.js`. Classificação: **NAVEGADOR AUTOMATIZADO**.

## Limites

- Esta revisão é só de contraste de cor. Não declara conformidade com o WCAG.
- Leitor de tela e testes com pessoas usuárias seguem **NÃO EXECUTADOS**.
- A cor do mapa não é o único meio de informação. O ponto selecionado muda de forma (círculo → losango), e a lista de pontos é a alternativa textual ao mapa.
