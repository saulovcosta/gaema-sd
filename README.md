# GAEMA SD

Módulo autoral do Radar Ambiental do Ministério Público do Estado do Tocantins (nome provisório) para **apoiar** a identificação e o diagnóstico de pastagens degradadas: da triagem por imagem de satélite à vistoria de campo, ao relatório e ao monitoramento.

> **Situação atual:** protótipo em desenvolvimento, com **dados sintéticos**. Não está integrado a nenhum sistema do MPTO nem ao ArcGIS. Nenhum resultado tem validade científica ou jurídica.

## Como testar no navegador (Codespaces)

Não precisa instalar nada no seu computador. Tudo roda com **dados inventados**.

1. No GitHub, abra o repositório e toque em **Code** → aba **Codespaces** → **Create codespace on main**. Se já existe um Codespace antigo, crie um novo: o antigo não tem a interface.
2. Espere a preparação, alguns minutos na primeira vez. A interface abre sozinha numa aba nova do navegador.
3. Se a aba não abrir, procure embaixo a aba **PORTAS** (PORTS), na linha **8765**, e toque no ícone do globo.
4. Toque no papel com que quer testar ("Entrar como Coordenador", por exemplo) e siga o quadro **"O que fazer agora"** de cada tela.
5. Para recomeçar do zero: no terminal do Codespace, aperte Ctrl+C e digite `scripts/interface.sh`. Cada abertura cria um cenário novo.
6. Ao terminar, pare o Codespace (menu **Codespaces** → **Stop**) para não gastar a cota.

O endereço só abre para quem é dono do Codespace, porque a porta fica privada. Não há senha nem autenticação real; não use dados reais.

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
| 3 | Protótipo local ponta a ponta e relatório | Concluída (testada localmente) |
| 4 | Robustez: offline, sincronização, segurança, backup, acessibilidade | Concluída (testada localmente, com rede simulada) |
| 5 | Preparação institucional: adaptadores, formulário XLSForm, pontos de integração, homologação, capacitação | Concluída como preparação, com revisão independente por agente de IA; testada localmente; **nada foi integrado** |
| 6 | Interface local de operação, segurança da central, âncora da trilha, relatório A4 | Concluída como protótipo local (testada localmente e com navegador automatizado); **sem autenticação real** |

Detalhes do andamento: `docs/ESTADO.md`.

## Documentos principais

- `docs/fontes.md` — fontes consultadas, fatos, inferências, lacunas e decisões
- `docs/sipade-videos.md` — o que os vídeos públicos do SIPADE mostram e o que muda no GAEMA SD
- `docs/decisoes.md` — escolhas de arquitetura com justificativa
- `docs/requisitos.md` — requisitos com origem e nível de pronto
- `docs/riscos.md` — riscos e mitigação
- `docs/dominio.md` — as 20 entidades: o que guardam, regras e retenção
- `docs/estados.md` — fluxo da demanda: 23 situações, quem pode mudar e quando
- `docs/protocolo.md` — como o diagnóstico é calculado (modo descritivo e protótipo de teste)
- `docs/guia-capacitacao.md` — guia de uso para os membros, com exercícios e gabarito (art. 20 da Portaria)
- `docs/integracao-radar-painel.md` — pontos de troca com o Radar Ambiental e o Painel do art. 18, e perguntas à equipe
- `docs/homologacao.md` — checklist do que falta demonstrar (nenhum item aprovado)
- `docs/pendencias.md` — pendências científicas, institucionais e de ambiente
- `adapters/arcgis/` — adaptadores ArcGIS (só interface), XLSForm do formulário de vistoria e exemplos sintéticos
- `docs/prompt-gaema-sd.md` — especificação original

## O que já existe (Fase 2)

- Cadastro das 20 entidades com regras de preenchimento.
- Fluxo da demanda com 23 situações e 79 mudanças possíveis, cada uma com quem pode fazer, condições e motivo.
- Controle de acesso por papel, feito no núcleo (não depende da tela).
- Registro de auditoria encadeado, que denuncia qualquer alteração ou remoção.
- Proteção contra perda silenciosa (edições simultâneas geram aviso de conflito) e contra duplicidade em reenvio.
- Conferência de geometria, GPS, unidades de medida e anexos.

## O que já existe (Fase 3)

- Motor de diagnóstico com regras versionadas: descreve o que foi visto em campo e, só no modo de teste, sugere uma categoria por ponto, sempre com a faixa "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA". Nenhum limiar numérico.
- Todo diagnóstico guarda os dados usados e pode ser refeito depois para conferência, mesmo que os dados de campo tenham sido corrigidos.
- Relatório em HTML e PDF com as 16 seções previstas, mapa esquemático, avisos de limitação e histórico de versões. Corrigir gera nova versão; a anterior é preservada.
- Fotos e documentos guardados como original, identificados pelo hash, com conferência de integridade.
- Demonstração completa com dados inventados: `scripts/demo.sh`.

A tela de operação veio na Fase 6 (abaixo).

## O que já existe (Fase 4)

Tudo testado só em computador, com dados inventados e rede **simulada**.

- **Sincronização** (`src/gaema_sd/sincronizacao/`): cada dispositivo tem uma fila local que sobrevive a reinício. Perda de rede, serviço fora do ar e confirmação perdida não perdem nem duplicam registro; o envio recomeça de onde parou. Se dispositivo e central alteraram o mesmo registro, nada é sobrescrito: a demanda vai para "conflito de sincronização", as duas versões ficam guardadas e só o coordenador decide, com motivo.
- **Concorrência:** várias conexões ao mesmo arquivo sem perda de dados (modo WAL).
- **Segurança básica:** acesso indevido recusado e auditado, anexo inválido barrado, logs e trilha sem CPF/e-mail/senha, análise das dependências sem achados (executada uma vez em 03/10/2026).
- **Backup e rollback:** `python -m gaema_sd.backup criar|verificar|restaurar|rollback`. A restauração é conferida (hashes, contagens, trilha de auditoria); backup adulterado é recusado; o estado desfeito no rollback é guardado, não apagado.
- **Relatório HTML mais acessível:** link de salto, foco visível, contraste conferido por cálculo. **Teste com leitor de tela ainda não foi feito.**

Não existe rede, aplicativo de campo, ArcGIS ou MPTO reais nesta etapa.

## O que já existe (Fase 5)

Preparação institucional. **Nada aqui está integrado a ArcGIS, ao Radar Ambiental, ao Painel do art. 18 ou a sistema do MPTO**; tudo roda só no computador, com dados inventados.

- **Decisão do coordenador volta ao aparelho:** o aparelho consulta o desfecho do conflito, adota a versão da central ou realinha as versões, e converge com a central. Foi corrigido um defeito da Fase 4: depois de um conflito, uma segunda correção já na fila podia sobrescrever a versão da central; agora fica retida até a decisão.
- **Adaptadores ArcGIS só como interface** (`src/gaema_sd/adaptadores/`): sem rede, sem URL, sem credencial; recusam por padrão.
- **Formulário de vistoria em XLSForm**, gerado do próprio modelo de dados, sem profundidade, número de repetições ou limiar inventados. Conferido por estrutura e sintaxe; **não** foi aberto no Survey123 Connect.
- **Pacote de exportação em formato próprio** (sem coordenadas, textos livres nem pessoas) como base de conversa com a equipe do Radar.
- **Checklist de homologação** (nenhum item aprovado), **lista de pendências** e **guia de capacitação** com exercícios e gabarito.
- **Revisão independente das Fases 4 e 5** (feita por um agente de IA separado, não por pessoas): 20 falhas reproduzidas e corrigidas, cada uma com teste. As mais sérias: dado de campo aceito de quem não é da equipe ou depois de a demanda avançar, e um erro de acesso que rejeitava todo o campo. Ver `docs/decisoes.md` (DEC-020).

### Nível de pronto real

Nada passou de **TESTADO LOCALMENTE** (testes automáticos no computador, dados inventados, rede simulada). Em especial: **o formulário XLSForm foi conferido por testes próprios e pelo pyxform, mas não foi aberto no Survey123 Connect**; adaptadores ArcGIS são só interface; o relatório não foi testado com leitor de tela; não houve revisão humana nem de terceiros; nenhuma turma foi capacitada. A tabela completa está em `docs/ESTADO.md`.

## O que já existe (Fase 6)

**Interface local para testar o fluxo sem programar.** Abra com `scripts/interface.sh` e acesse http://127.0.0.1:8765/ no navegador do mesmo computador. Escolhe-se um **usuário de teste** (não há senha nem autenticação real); só dados inventados.

- **Cada tela começa por "O que fazer agora".** As situações aparecem em linguagem comum (por exemplo, "Conflito: aguardando decisão do coordenador"), com ícone e texto, não só cor.
- **O papel aparece no topo**, com o que pode e o que não pode fazer. Botão sem permissão aparece desabilitado, com o motivo ao lado. Erro diz "o que houve" e "como resolver".
- **Escritório:** início com "Exige atenção", demanda com mapa esquemático (escala aproximada, lista de pontos ligada ao mapa), mudanças de situação, relatórios, conflitos lado a lado, auditoria com âncora, exportação e backup.
- **Campo (aparelho simulado):** rede, fila e última sincronização sempre visíveis; coleta em 4 etapas com rascunho salvo a cada etapa; unidade sempre visível; desfazer; conferência antes de salvar; "Sincronizar agora" mostra o resultado ("1 enviado(s), 0 conflito(s)").
- **Temas claro e escuro**, com contraste conferido; funciona em tela de celular de 360 px sem rolagem lateral.
- **Relatório para A4** com bloco de identificação, datas legíveis e hashes em grupos.
- **Segurança da central:** todo dado de campo confere origem, equipe e situação da demanda, e não pode ser "mudado de demanda" depois (fecha R-28). **Âncora da trilha** para guardar fora da máquina (R-19, em parte).
- **Revisão independente** por agente de IA separado: 15 falhas reproduzidas e corrigidas, cada uma com teste. A verificação com navegador real achou mais uma: o próprio login era recusado pelo navegador; corrigida.

- **Cabeçalho institucional do relatório:** logo e "Ministério Público do Estado do Tocantins · CAOMA · GAEMA" no topo, e a linha "Protótipo em desenvolvimento no âmbito do CAOMA. Sem endosso institucional formal." A frase só muda se `config/endosso.json` receber o número e a data de um ato formal; hoje está vazio.

**Nível de pronto real:** TESTADO LOCALMENTE. Verificação automática de acessibilidade (axe-core) sem violações em 83 telas, mas **não foi feito teste com leitor de tela nem com pessoas usuárias**, e **não há conformidade WCAG declarada**. Sem autenticação real, sem rede real, sem ArcGIS, Radar Ambiental ou sistema do MPTO.

## Para quem programa

```bash
scripts/testar.sh     # todos os testes
scripts/demo.sh       # fluxo completo com dados sintéticos; relatórios em saida/
scripts/interface.sh  # interface local em http://127.0.0.1:8765/ (dados sintéticos); no Codespaces abre sozinha
scripts/demo_sincronizacao.sh   # conflito, decisão do coordenador e aparelho convergindo
python -m gaema_sd.backup verificar PASTA_DO_BACKUP   # confere um backup
```

Requer Python 3.11+. Dependências fixadas em `requirements-dev.txt`.
