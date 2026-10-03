# Adaptadores ArcGIS — somente interface e documentação

**Situação: ESPECIFICADO. Nada aqui executa contra ArcGIS.** Não existe, nesta fase, organização ArcGIS, Client ID ou serviço acessível (lacuna LA-05 em `docs/fontes.md`). Nenhuma integração com o MPTO está declarada.

Adaptadores previstos para a Fase 5:

| Adaptador | Papel | Fato técnico a respeitar |
|---|---|---|
| Feature Services | Publicar e ler camadas (áreas, pontos, observações) | Camada hospedada: "última edição sincronizada vence" (FC-12) — o adaptador deve comparar versão antes de aplicar |
| Survey123 (XLSForm) | Formulário de vistoria em campo | Funciona offline; geocodificação e consultas remotas não funcionam sem rede (FC-09); formulário em XLSForm (FC-10) |
| Mapa base offline | Uso em campo | TPKX/TPK, VTPK ou MMPK em Web Mercator (FC-11) |
| Field Maps | Navegação e coleta em mapa | Mesma regra de sincronização de FC-12 |
| Experience Builder (Developer Edition) | Painel web | Exige conta ArcGIS Online/Enterprise e Client ID; roda no computador do desenvolvedor (FC-08) |
| ArcGIS API for Python | Automação de carga e leitura | Depende de credencial institucional; credencial nunca no código |

Regras para quem implementar:
1. O adaptador traduz; a regra de negócio fica no núcleo (`src/gaema_sd`).
2. Toda escrita no núcleo passa pela política de acesso e gera evento de auditoria.
3. Credenciais só por variável de ambiente (`.env`, fora do git).
