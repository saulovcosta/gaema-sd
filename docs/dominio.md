# Modelo de domínio

> Arquivo GERADO por `scripts/gerar_contratos.py`. Campos e tipos vêm de `src/gaema_sd/dominio/entidades.py`; textos de `src/gaema_sd/dominio/documento.py`.

Nível: TESTADO LOCALMENTE (Fase 2). Proveniência: INSTITUCIONAL (lista de entidades) e AUTORAL (campos).

## Distinções que o modelo garante

| Conceito | Como aparece no GAEMA SD |
|---|---|
| Área de interesse | `AreaInteresse`: recorte geográfico de análise |
| Imóvel | **Não modelado.** Nenhum campo identifica imóvel |
| Cadastro territorial | Só como `CruzamentoTerritorial` (indício espacial, não titularidade) |
| Ocupante, autor, responsável | **Não modelados.** Teste `test_fronteira_juridica.py` impede |
| Conclusão jurídica | **Não modelada.** `Providencia` registra decisão humana |
| Sinal remoto / vistoria / resultado computado / revisão / providência | `AreaCandidata`+`SinalRemoto` / `CampanhaVistoria`+`Observacao` / `Diagnostico` / `RevisaoTecnica` / `Providencia` — entidades separadas |

## Campos comuns (todas as entidades, exceto EventoAuditoria)

`id` (UUID), `versao` (controle de concorrência: atualizar exige a versão lida), `criado_em` (UTC), `criado_por` (preenchido pelo núcleo a partir do login, nunca pelo cliente), `atualizado_em`, `sintetico` (marca dados de teste).

## Sensibilidade

INTERNA: leitura por qualquer papel humano. RESTRITA: leitura só por papéis do fluxo e AUDITOR, e cada leitura gera evento de auditoria. Classificação de sigilo oficial: PENDENTE (LA-06).

## AreaCandidata

**Finalidade.** Polígono indicado por sinal remoto como possível pastagem degradada. É só **sinal**, não conclusão.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `geometria_wkt` | str | sim |
| `fonte_ids` | lista de str | não |
| `sinais` | lista de SinalRemoto | não |
| `data_deteccao` | date | sim |
| `metodo_selecao` | str | não |
| `prioridade` | int (opcional) | não |
| `chave_deduplicacao` | str | não |

**Relações.** Usa 1..n FonteDado; origina 0..n Alerta, AreaInteresse e Demanda.

**Validações.** Obrigatórios da tabela acima, mais: Polígono WGS84 válido (sem auto-interseção, com área); ao menos uma fonte; todo sinal aponta fonte listada; fora do recorte aproximado do Tocantins gera ALERTA.

**Atualização.** Editável enquanto a Demanda estiver em CANDIDATA/ALERTA/EM_TRIAGEM; cada edição gera versão.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000002",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "geometria_wkt": "POLYGON ((-48.500 -10.500, -48.490 -10.500, -48.490 -10.490, -48.500 -10.490, -48.500 -10.500))",
  "fonte_ids": [
    "00000000-0000-4000-8000-000000000001"
  ],
  "sinais": [
    {
      "nome": "indice_sintetico",
      "valor": 0.5,
      "unidade": "",
      "fonte_id": "00000000-0000-4000-8000-000000000001",
      "data_referencia": "2026-01-01",
      "metodo": "valor inventado para teste"
    }
  ],
  "data_deteccao": "2026-01-10",
  "metodo_selecao": "seleção manual sintética",
  "prioridade": null,
  "chave_deduplicacao": "sintetica-a"
}
```

## Alerta

**Finalidade.** Registro de que um sinal ou notícia merece triagem.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `origem` | OrigemAlerta (lista fixa) | sim |
| `descricao` | str | sim |
| `data_alerta` | date | sim |
| `area_candidata_id` | str (opcional) | não |
| `geometria_wkt` | str | não |

**Relações.** 0..1 AreaCandidata; listado em Demanda.alerta_ids.

**Validações.** Obrigatórios da tabela acima, mais: Exige área candidata ou geometria própria; geometria, se houver, válida.

**Atualização.** Edição versionada; não muda a origem.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000003",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "origem": "SINAL_REMOTO",
  "descricao": "Alerta sintético de teste",
  "data_alerta": "2026-01-11",
  "area_candidata_id": "00000000-0000-4000-8000-000000000002",
  "geometria_wkt": ""
}
```

## Demanda

**Finalidade.** Unidade de acompanhamento que percorre o fluxo de estados (docs/estados.md).

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `titulo` | str | sim |
| `objetivo` | str | não |
| `estado` | Estado (lista fixa) | não |
| `estado_anterior` | Estado (lista fixa) (opcional) | não |
| `alerta_ids` | lista de str | não |
| `area_candidata_id` | str (opcional) | não |
| `area_interesse_id` | str (opcional) | não |
| `equipe_id` | str (opcional) | não |
| `duplicada_de` | str (opcional) | não |
| `referencia_interna` | str | não |

**Relações.** 0..n Alerta; 0..1 AreaCandidata, AreaInteresse, Equipe; 0..n CampanhaVistoria, Diagnostico, Providencia, PlanoRecuperacao, Relatorio.

**Validações.** Obrigatórios da tabela acima, mais: DUPLICADA exige `duplicada_de` diferente do próprio id.

**Atualização.** Estado muda **só** por transição auditada; demais campos por edição versionada.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000007",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "titulo": "Demanda sintética A",
  "objetivo": "Teste do fluxo",
  "estado": "CANDIDATA",
  "estado_anterior": null,
  "alerta_ids": [
    "00000000-0000-4000-8000-000000000003"
  ],
  "area_candidata_id": "00000000-0000-4000-8000-000000000002",
  "area_interesse_id": "00000000-0000-4000-8000-000000000004",
  "equipe_id": "00000000-0000-4000-8000-000000000005",
  "duplicada_de": null,
  "referencia_interna": ""
}
```

## AreaInteresse

**Finalidade.** Recorte geográfico de análise. **Não é imóvel, não é cadastro territorial e não identifica ocupante, possuidor, proprietário, autor ou responsável.**

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `geometria_wkt` | str | sim |
| `descricao` | str | sim |
| `origem` | OrigemAreaInteresse (lista fixa) | sim |
| `area_candidata_id` | str (opcional) | não |
| `cruzamentos` | lista de CruzamentoTerritorial | não |

**Relações.** 0..1 AreaCandidata; 0..n CruzamentoTerritorial (indício espacial com camadas como SICAR, se autorizado — não prova titularidade).

**Validações.** Obrigatórios da tabela acima, mais: Polígono válido; sobreposição entre 0 e 100%.

**Atualização.** Edição versionada; a geometria anterior fica no histórico.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000004",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "geometria_wkt": "POLYGON ((-48.500 -10.500, -48.490 -10.500, -48.490 -10.490, -48.500 -10.490, -48.500 -10.500))",
  "descricao": "Área Sintética A",
  "origem": "DE_CANDIDATA",
  "area_candidata_id": "00000000-0000-4000-8000-000000000002",
  "cruzamentos": []
}
```

## Equipe

**Finalidade.** Conjunto de usuários designados para a vistoria.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `nome` | str | sim |
| `membros` | lista de MembroEquipe | não |

**Relações.** Referenciada por Demanda e CampanhaVistoria. Membros são ids de usuário, sem dados pessoais.

**Validações.** Obrigatórios da tabela acima, mais: Ao menos um membro; sem repetição; SISTEMA e ADMINISTRADOR não compõem equipe.

**Atualização.** Edição versionada por COORDENADOR.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000005",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "nome": "Equipe Sintética 1",
  "membros": [
    {
      "usuario_id": "usuario-sintetico-02",
      "papel": "TECNICO_CAMPO",
      "funcao": "vistoria"
    },
    {
      "usuario_id": "usuario-sintetico-03",
      "papel": "COORDENADOR",
      "funcao": "coordenação"
    }
  ]
}
```

## CampanhaVistoria

**Finalidade.** Planejamento e execução de uma ida a campo (missão offline).

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `demanda_id` | str | sim |
| `equipe_id` | str | sim |
| `versao_protocolo_id` | str | sim |
| `objetivo` | str | sim |
| `data_planejada` | date | sim |
| `inicio_em` | datetime (opcional) | não |
| `fim_em` | datetime (opcional) | não |
| `pacote_offline` | str | não |
| `condicao_acesso` | CondicaoAcesso (lista fixa) | não |
| `nota_acesso` | str | não |

**Relações.** 1 Demanda, 1 Equipe, 1 VersaoProtocolo; 0..n PontoAmostral e Evidencia.

**Validações.** Obrigatórios da tabela acima, mais: Fim não anterior ao início; SEM_ACESSO exige descrição.

**Atualização.** Edição versionada; protocolo vinculado não muda depois do início (regra da Fase 3).

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000008",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "demanda_id": "00000000-0000-4000-8000-000000000007",
  "equipe_id": "00000000-0000-4000-8000-000000000005",
  "versao_protocolo_id": "00000000-0000-4000-8000-000000000006",
  "objetivo": "Vistoria sintética",
  "data_planejada": "2026-02-01",
  "inicio_em": null,
  "fim_em": null,
  "pacote_offline": "pacote-sintetico",
  "condicao_acesso": "NAO_INFORMADA",
  "nota_acesso": ""
}
```

## PontoAmostral

**Finalidade.** Local de amostragem em campo, com GPS e precisão registrada.

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `campanha_id` | str | sim |
| `codigo` | str | sim |
| `latitude` | float | sim |
| `longitude` | float | sim |
| `precisao_gps_m` | float (opcional) | sim |
| `altitude_m` | float (opcional) | não |
| `capturado_em` | datetime | sim |
| `dispositivo_id` | str | não |
| `geometria_wkt` | str | não |
| `chave_idempotencia` | str | não |
| `status_sincronizacao` | StatusSincronizacao (lista fixa) | não |

**Relações.** 1 CampanhaVistoria; 0..n Observacao, MedicaoPenetracao, Evidencia.

**Validações.** Obrigatórios da tabela acima, mais: Coordenada WGS84 válida e diferente de 0,0; precisão obrigatória; precisão acima do limite operacional gera ALERTA (GPS ruim), sem bloquear; chave de envio recomendada.

**Atualização.** Coleta é imutável na prática: correção gera nova versão com histórico. Reenvio com a mesma chave não duplica.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000009",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "campanha_id": "00000000-0000-4000-8000-000000000008",
  "codigo": "P01",
  "latitude": -10.495,
  "longitude": -48.495,
  "precisao_gps_m": 4.0,
  "altitude_m": null,
  "capturado_em": "2026-01-15T12:00:00+00:00",
  "dispositivo_id": "dispositivo-sintetico",
  "geometria_wkt": "",
  "chave_idempotencia": "disp-sint:P01",
  "status_sincronizacao": "LOCAL"
}
```

## Observacao

**Finalidade.** Valor observado de uma variável de campo (invasoras, cupins, erosão, cobertura etc.).

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `ponto_id` | str | sim |
| `variavel` | VariavelCampo (lista fixa) | sim |
| `valor_bruto` | str | sim |
| `unidade_bruta` | str | sim |
| `valor_normalizado` | float (opcional) | não |
| `unidade_normalizada` | str | não |
| `observado_em` | datetime | sim |
| `observador_id` | str | sim |
| `nota` | str | não |
| `chave_idempotencia` | str | não |
| `status_sincronizacao` | StatusSincronizacao (lista fixa) | não |

**Relações.** 1 PontoAmostral; 0..n Evidencia.

**Validações.** Obrigatórios da tabela acima, mais: Valor bruto e unidade obrigatórios; percentuais entre 0 e 100; OUTRA exige descrição.

**Atualização.** Valor bruto preservado; normalização explícita; correção gera versão.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000010",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "ponto_id": "00000000-0000-4000-8000-000000000009",
  "variavel": "SOLO_EXPOSTO",
  "valor_bruto": "35",
  "unidade_bruta": "%",
  "valor_normalizado": 35.0,
  "unidade_normalizada": "%",
  "observado_em": "2026-01-15T12:00:00+00:00",
  "observador_id": "usuario-sintetico-02",
  "nota": "",
  "chave_idempotencia": "disp-sint:P01:obs1",
  "status_sincronizacao": "LOCAL"
}
```

## MedicaoPenetracao

**Finalidade.** Uma repetição de medição de resistência à penetração em uma profundidade.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `ponto_id` | str | sim |
| `repeticao` | int | sim |
| `profundidade_bruta` | str | sim |
| `profundidade_unidade` | str | sim |
| `resistencia_bruta` | str | sim |
| `resistencia_unidade` | str | sim |
| `profundidade_cm` | float (opcional) | não |
| `resistencia_kpa` | float (opcional) | não |
| `contexto_umidade` | str | não |
| `equipamento` | str | não |
| `medido_em` | datetime | sim |
| `chave_idempotencia` | str | não |
| `status_sincronizacao` | StatusSincronizacao (lista fixa) | não |

**Relações.** 1 PontoAmostral (n repetições).

**Validações.** Obrigatórios da tabela acima, mais: Repetição ≥ 1; unidades aceitas (cm/mm/m; kPa/MPa/kgf/cm²); valores numéricos não negativos. Nº mínimo de repetições e profundidade-padrão: PENDENTE (LA-04).

**Atualização.** Bruto preservado; correção gera versão.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000011",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "ponto_id": "00000000-0000-4000-8000-000000000009",
  "repeticao": 1,
  "profundidade_bruta": "20",
  "profundidade_unidade": "cm",
  "resistencia_bruta": "1,5",
  "resistencia_unidade": "MPa",
  "profundidade_cm": 20.0,
  "resistencia_kpa": 1500.0,
  "contexto_umidade": "",
  "equipamento": "",
  "medido_em": "2026-01-15T12:00:00+00:00",
  "chave_idempotencia": "disp-sint:P01:pen1",
  "status_sincronizacao": "LOCAL"
}
```

## Evidencia

**Finalidade.** Arquivo (foto, documento) com hash, autoria do registro e vínculo a ponto/observação.

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `campanha_id` | str | sim |
| `ponto_id` | str (opcional) | não |
| `observacao_id` | str (opcional) | não |
| `categoria` | CategoriaEvidencia (lista fixa) | sim |
| `nome_arquivo_original` | str | sim |
| `tipo_mime` | str | sim |
| `tamanho_bytes` | int | sim |
| `sha256` | str | sim |
| `registrado_por` | str | sim |
| `capturado_em_declarado` | datetime (opcional) | não |
| `latitude_declarada` | float (opcional) | não |
| `longitude_declarada` | float (opcional) | não |
| `armazenamento_ref` | str | não |
| `substitui_evidencia_id` | str (opcional) | não |
| `chave_idempotencia` | str | não |
| `status_sincronizacao` | StatusSincronizacao (lista fixa) | não |

**Relações.** 1 CampanhaVistoria; 0..1 PontoAmostral; 0..1 Observacao; 0..1 Evidencia substituída.

**Validações.** Obrigatórios da tabela acima, mais: Tipo real pela assinatura (JPEG/PNG/PDF), tamanho, SHA-256; coordenada declarada completa. Hash não é prova material absoluta; EXIF/GPS são declarações do dispositivo.

**Atualização.** **Imutável.** Correção gera nova Evidencia com `substitui_evidencia_id`.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000012",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "campanha_id": "00000000-0000-4000-8000-000000000008",
  "ponto_id": "00000000-0000-4000-8000-000000000009",
  "observacao_id": "00000000-0000-4000-8000-000000000010",
  "categoria": "FOTO_SOLO",
  "nome_arquivo_original": "sintetica.jpg",
  "tipo_mime": "image/jpeg",
  "tamanho_bytes": 61,
  "sha256": "d076c6e289cc2a8a81f48bc1a2ce6f94a5e2f96e440bc3d296a081a72d94b3eb",
  "registrado_por": "usuario-sintetico-02",
  "capturado_em_declarado": null,
  "latitude_declarada": null,
  "longitude_declarada": null,
  "armazenamento_ref": "",
  "substitui_evidencia_id": null,
  "chave_idempotencia": "disp-sint:P01:foto1",
  "status_sincronizacao": "LOCAL"
}
```

## VersaoProtocolo

**Finalidade.** Definição versionada das regras de diagnóstico.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `codigo` | str | sim |
| `versao_semantica` | str | sim |
| `modo` | ModoProtocolo (lista fixa) | não |
| `rotulo` | str | não |
| `definicao_json` | str | não |
| `hash_definicao` | str | não |
| `vigente_desde` | date (opcional) | não |
| `referencia_validacao` | str | não |
| `proveniencia` | Proveniencia (lista fixa) | não |

**Relações.** Usada por CampanhaVistoria, Diagnostico e Relatorio.

**Validações.** Obrigatórios da tabela acima, mais: Versão semântica; hash da definição; protótipo exige o rótulo exato "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"; modo validado exige referência documental.

**Atualização.** **Imutável.** Mudança gera nova versão; diagnósticos antigos continuam reproduzíveis.

**Retenção.** Permanente enquanto houver diagnóstico que a referencie.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000006",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "codigo": "GAEMA-DESCRITIVO",
  "versao_semantica": "0.1.0",
  "modo": "DESCRITIVO",
  "rotulo": "",
  "definicao_json": "{\"modo\":\"DESCRITIVO\",\"regras\":[],\"variaveis\":[\"COBERTURA_FORRAGEIRA\",\"VIGOR_FORRAGEIRA\",\"SOLO_EXPOSTO\",\"PLANTAS_INVASORAS\",\"CUPINS_MONTICULO\",\"EROSAO_LAMINAR\",\"SULCOS\",\"RAVINAS\",\"VOCOROCAS\",\"UMIDADE_SOLO\",\"ANIMAIS_PASTEJO\",\"CONTEXTO_SAZONAL\",\"DRENAGEM\",\"DECLIVIDADE\",\"MANEJO_INFORMADO\",\"HIPOTESE_ALTERNATIVA\",\"OUTRA\"]}",
  "hash_definicao": "b23f1ece849c192ddc02fc29a48b39a686255fd1c9ea66a03f3dfccddb985a31",
  "vigente_desde": "2026-01-01",
  "referencia_validacao": "",
  "proveniencia": "AUTORAL"
}
```

## Diagnostico

**Finalidade.** Resultado **computado** e descritivo. Só vale depois da RevisaoTecnica.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `demanda_id` | str | sim |
| `campanha_id` | str | sim |
| `versao_protocolo_id` | str | sim |
| `hash_definicao_protocolo` | str | sim |
| `hash_entradas` | str | sim |
| `resultado_descritivo` | str | sim |
| `categoria_descritiva` | str | não |
| `regras_disparadas` | lista de str | não |
| `limitacoes` | str | não |
| `hipoteses_alternativas` | str | não |
| `rotulo_validade` | str | não |
| `situacao` | SituacaoDiagnostico (lista fixa) | não |
| `substitui_diagnostico_id` | str (opcional) | não |

**Relações.** 1 Demanda, 1 CampanhaVistoria, 1 VersaoProtocolo; 0..n RevisaoTecnica.

**Validações.** Obrigatórios da tabela acima, mais: Hashes de protocolo e entradas; limitações obrigatórias; categoria exige rótulo de validade.

**Atualização.** Recomputação gera novo Diagnostico (`substitui_diagnostico_id`).

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## RevisaoTecnica

**Finalidade.** Juízo técnico humano sobre o diagnóstico.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `diagnostico_id` | str | sim |
| `revisor_id` | str | sim |
| `resultado` | ResultadoRevisao (lista fixa) | sim |
| `fundamentacao` | str | sim |
| `ressalvas` | str | não |
| `revisado_em` | datetime | não |

**Relações.** 1 Diagnostico.

**Validações.** Obrigatórios da tabela acima, mais: Fundamentação mínima; revisor independente da coleta (pré-condição de transição).

**Atualização.** **Imutável.** Nova revisão gera novo registro.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## Providencia

**Finalidade.** Registro de decisão institucional tomada por membro do MP. O sistema não sugere nem infere.

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `demanda_id` | str | sim |
| `tipo` | TipoProvidencia (lista fixa) | sim |
| `descricao` | str | sim |
| `decidido_por` | str | sim |
| `decidido_em` | datetime | não |
| `base_tecnica_ids` | lista de str | não |

**Relações.** 1 Demanda; referências a Diagnostico/RevisaoTecnica como base técnica.

**Validações.** Obrigatórios da tabela acima, mais: Tipo da lista de ações; descrição obrigatória; só MEMBRO_MP registra.

**Atualização.** Edição versionada.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## PlanoRecuperacao

**Finalidade.** Plano de recuperação ou renovação acordado ou apresentado.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `demanda_id` | str | sim |
| `tipo` | TipoPlano (lista fixa) | não |
| `objetivos` | str | sim |
| `acoes` | lista de str | não |
| `origem_documento` | str | não |
| `elaborado_por` | str | não |
| `prazo_meses` | int (opcional) | não |

**Relações.** 1 Demanda; 0..n MarcoMonitoramento.

**Validações.** Obrigatórios da tabela acima, mais: Prazo positivo quando informado.

**Atualização.** Edição versionada.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## MarcoMonitoramento

**Finalidade.** Ponto de verificação do plano.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `plano_id` | str | sim |
| `descricao` | str | sim |
| `indicador` | str | não |
| `data_prevista` | date | sim |
| `data_verificada` | date (opcional) | não |
| `situacao` | SituacaoMarco (lista fixa) | não |
| `campanha_verificacao_id` | str (opcional) | não |

**Relações.** 1 PlanoRecuperacao; 0..1 CampanhaVistoria de verificação.

**Validações.** Obrigatórios da tabela acima, mais: Cumprido/não cumprido exige data de verificação.

**Atualização.** Edição versionada.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## Relatorio

**Finalidade.** Documento reproduzível emitido (HTML/PDF na Fase 3).

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `demanda_id` | str | sim |
| `numero_versao` | int | não |
| `diagnostico_id` | str | sim |
| `revisao_id` | str (opcional) | não |
| `versao_protocolo_id` | str | sim |
| `formato` | FormatoRelatorio (lista fixa) | não |
| `hash_conteudo` | str | sim |
| `gerado_por` | str | sim |
| `gerado_em` | datetime | não |
| `substitui_relatorio_id` | str (opcional) | não |
| `motivo_reemissao` | str | não |

**Relações.** 1 Demanda, 1 Diagnostico, 0..1 RevisaoTecnica, 1 VersaoProtocolo; 0..1 Relatorio substituído.

**Validações.** Obrigatórios da tabela acima, mais: Hash do conteúdo; reemissão (versão > 1) exige relatório substituído e motivo.

**Atualização.** **Imutável.** Toda correção gera nova versão.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## EventoAuditoria

**Finalidade.** Trilha de quem fez o quê, quando, e por quê.

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `sequencia` | int | sim |
| `ocorrido_em` | datetime | sim |
| `ator_id` | str | sim |
| `papeis` | lista de str | sim |
| `acao` | str | sim |
| `entidade` | str | sim |
| `entidade_id` | str | sim |
| `estado_origem` | str (opcional) | não |
| `estado_destino` | str (opcional) | não |
| `motivo` | str | não |
| `detalhes` | dict | não |
| `hash_anterior` | str | sim |
| `hash_evento` | str | sim |

**Relações.** Aponta qualquer entidade por tipo e id.

**Validações.** Obrigatórios da tabela acima, mais: Encadeamento por hash; sequência contínua; detalhes sem dados sensíveis.

**Atualização.** **Somente acréscimo** (gatilhos no banco impedem alterar ou apagar).

**Retenção.** Permanente (proposta AUTORAL; confirmar com norma interna).

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).

## FonteDado

**Finalidade.** Proveniência de camada ou tabela usada na triagem (data, resolução, autorização).

**Sensibilidade.** INTERNA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `nome` | str | sim |
| `tipo` | TipoFonte (lista fixa) | sim |
| `provedor` | str | sim |
| `data_referencia` | date (opcional) | não |
| `resolucao_m` | float (opcional) | não |
| `autorizacao_uso` | str | não |
| `url_referencia` | str | não |
| `nota_qualidade` | str | não |
| `proveniencia` | Proveniencia (lista fixa) | não |

**Relações.** Referenciada por AreaCandidata, SinalRemoto e CruzamentoTerritorial.

**Validações.** Obrigatórios da tabela acima, mais: Resolução positiva; autorização de uso inicia como PENDENTE.

**Atualização.** Edição versionada.

**Retenção.** Permanente enquanto referenciada.

**Exemplo sintético.**

```json
{
  "id": "00000000-0000-4000-8000-000000000001",
  "versao": 1,
  "criado_em": "2026-01-15T12:00:00+00:00",
  "criado_por": "usuario-sintetico-01",
  "atualizado_em": null,
  "sintetico": true,
  "nome": "Camada sintética de cobertura",
  "tipo": "CAMADA_RASTER",
  "provedor": "GERADOR SINTÉTICO",
  "data_referencia": "2026-01-01",
  "resolucao_m": 30.0,
  "autorizacao_uso": "PENDENTE",
  "url_referencia": "",
  "nota_qualidade": "",
  "proveniencia": "AUTORAL"
}
```

## IntegracaoExterna

**Finalidade.** Registro de integração prevista ou testada (ArcGIS etc.).

**Sensibilidade.** RESTRITA

| Campo | Tipo | Obrigatório |
|---|---|---|
| `id` | str | não |
| `versao` | int | não |
| `criado_em` | datetime | não |
| `criado_por` | str | não |
| `atualizado_em` | datetime (opcional) | não |
| `sintetico` | bool | não |
| `nome` | str | sim |
| `sistema` | str | sim |
| `situacao` | SituacaoIntegracao (lista fixa) | não |
| `ambiente` | Ambiente (lista fixa) | não |
| `variavel_configuracao` | str | não |
| `evidencia_teste` | str | não |
| `observacoes` | str | não |

**Relações.** Independente.

**Validações.** Obrigatórios da tabela acima, mais: ATIVA só com evidência de teste em ambiente real; guarda o NOME da variável de ambiente, nunca o segredo.

**Atualização.** Edição versionada; só ADMINISTRADOR.

**Retenção.** PENDENTE (LA-06): depende de norma interna do MPTO. Proposta AUTORAL provisória: não excluir; inativar com motivo auditado.

**Exemplo sintético.** Gerado na Fase 3 (fluxo de diagnóstico e relatório).
