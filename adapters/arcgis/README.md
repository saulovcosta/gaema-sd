# Adaptadores ArcGIS — somente interface, exemplos e documentação

**Situação: IMPLEMENTADO LOCALMENTE (interface, tradução e XLSForm) e TESTADO LOCALMENTE (estrutura e sintaxe). Nada aqui executa contra ArcGIS.** Não existe organização ArcGIS, Client ID nem serviço acessível (lacuna LA-05 em `docs/fontes.md`). **Nenhuma integração está declarada**: nem com ArcGIS, nem com o Radar Ambiental, nem com o Painel do art. 18, nem com sistemas do MPTO.

## O que existe

| Item | Onde | O que é |
|---|---|---|
| Interfaces | `src/gaema_sd/adaptadores/interfaces.py` | `CatalogoCamadas` (somente leitura), `ImportadorCampo`, `PublicadorCampo` e as versões `NaoConfigurado*`, que recusam com `AmbienteIndisponivel` |
| Configuração | `src/gaema_sd/adaptadores/config.py` | Só informa se `ARCGIS_PORTAL_URL` e `ARCGIS_CLIENT_ID` estão definidas. O valor nunca é devolvido nem registrado |
| Tradução | `src/gaema_sd/adaptadores/traducao.py` | Submissão de campo (formato neutro) → itens de sincronização. Sem rede. Quem grava é `Nucleo.receber_sincronizacao` |
| XLSForm | `adapters/arcgis/xlsform/` | `survey.csv`, `choices.csv`, `settings.csv` e `mapeamento.csv`, **gerados** por `scripts/gerar_contratos.py` |
| Exemplo | `adapters/arcgis/exemplos/submissao_sintetica.json` | Submissão sintética no formato neutro |

Para gerar o `.xlsx` (não fica no git): `python -m gaema_sd.adaptadores.xlsform escrever vistoria.xlsx`.

## Como o formulário foi montado

- Uma submissão = um ponto amostral. Repetições só de um nível (outras observações, penetrometria, fotos).
- As 7 variáveis de presença/ausência são as que o protótipo de teste avalia; unidade `presenca`, respostas `sim`/`nao`.
- Penetrometria: **sem profundidade padrão e sem número mínimo de repetições** (LA-04). Unidades: as aceitas por `validacao/unidades.py`.
- Condição de acesso: a nota passa a ser obrigatória quando for "sem acesso".
- GPS: o núcleo registra a precisão e emite alerta se for ruim; o formulário não bloqueia.
- Todo campo está mapeado para um campo real do domínio (`mapeamento.csv`, conferido por teste).

## O que NÃO foi verificado

- Abertura, publicação e uso do formulário no **Survey123 Connect**, offline e em aparelho real.
- O **formato real de exportação** do Survey123 (o formato de entrada da tradução é neutro, definido aqui).
- Repetições aninhadas (por isso não são usadas), mapa base offline (FC-11), Field Maps, Experience Builder.
- Camadas de referência: só entram se autorizadas (LA-07, LA-09). `CamadaExterna.autorizada` nasce falso.
- O que foi conferido: estrutura do XLSForm por testes próprios e sintaxe XLSForm/ODK com **pyxform** (não é o Survey123).

## Fatos técnicos a respeitar (fontes em `docs/fontes.md`)

| Adaptador previsto | Fato |
|---|---|
| Feature Services / Field Maps | "Última edição sincronizada vence" (FC-12): por isso a entrada passa por `Nucleo.receber_sincronizacao`, que compara versões e abre conflito em vez de sobrescrever |
| Survey123 (XLSForm) | Funciona offline; geocodificação e consultas remotas falham sem rede (FC-09); formulário em XLSForm (FC-10) |
| Mapa base offline | TPKX/TPK, VTPK ou MMPK em Web Mercator (FC-11) |
| Experience Builder (Developer Edition) | Exige conta ArcGIS Online/Enterprise e Client ID (FC-08) |

## Regras para quem implementar o adaptador real

1. O adaptador traduz; a regra de negócio fica no núcleo (`src/gaema_sd`).
2. Toda escrita no núcleo passa pela política de acesso e gera evento de auditoria.
3. Credenciais só por variável de ambiente (`.env`, fora do git). Nunca em código, exemplo ou log.
4. Nenhum módulo de rede entra em `src/gaema_sd/adaptadores/` sem decisão registrada em `docs/decisoes.md` (um teste hoje exige o contrário).
