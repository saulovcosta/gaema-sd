# Checklist de homologação

Nível: **ESPECIFICADO**. Proveniência: AUTORAL. Este checklist lista o que precisa ser **demonstrado** antes de qualquer uso institucional. **Nenhum item está aprovado.** A coluna "Situação" só admite `NÃO EXECUTADO`, `PENDENTE` ou `EXECUTADO LOCALMENTE`: este último significa que um teste automatizado roda no computador de desenvolvimento, com dados sintéticos e rede simulada, e **não** equivale a aprovação em ambiente real.

Quem aprova cada item, em que ambiente e em que data são decisões institucionais, a registrar quando existirem; este documento não as presume.

| ID | Categoria | Critério a demonstrar | Evidência esperada | Vínculo | Situação |
|---|---|---|---|---|---|
| H-C01 | Científica | Protocolo de campo validado (pontos, repetições, profundidade) | Documento técnico do responsável; protocolo publicado como nova versão | LA-04, RQ-32 | PENDENTE |
| H-C02 | Científica | Limiar de NDVI para o Cerrado tocantinense | Fundamentação publicada; parâmetro com proveniência | LA-03 | PENDENTE |
| H-C03 | Científica | Critério de "degradação severa" e gatilho de 40% (art. 17, III) | Critério técnico validado | LA-08, RQ-65 | PENDENTE |
| H-C04 | Científica | Regras do protocolo validadas no lugar do protótipo | Revisão científica; remoção do rótulo de protótipo só por nova versão | LA-02, R-15 | PENDENTE |
| H-C05 | Científica | Diagnóstico reproduzível a partir dos dados gravados | Teste de reprodução histórica | RQ-30 | EXECUTADO LOCALMENTE (somente com o protótipo de teste) |
| H-I01 | Institucional | Quem exerce a vistoria e com qual capacitação prévia | Ato institucional | art. 20 | PENDENTE |
| H-I02 | Institucional | Capacitação dos membros realizada | Registro de turma(s) | RQ-68, art. 18 par. único, art. 20 | NÃO EXECUTADO (existe guia de apoio) |
| H-I03 | Institucional | Base legal para compartilhar dados com terceiros | Parecer ou norma | RQ-70 | PENDENTE |
| H-I04 | Institucional | Camadas de referência autorizadas | Autorização formal | LA-07, LA-09 | PENDENTE |
| H-I05 | Institucional | Retenção documental e classificação de sigilo | Norma interna | LA-06, RQ-45 | PENDENTE |
| H-I06 | Institucional | Relação com o Painel do art. 18 e o Radar Ambiental | Resposta às perguntas de `docs/integracao-radar-painel.md` | LA-10, IN-06 | PENDENTE |
| H-I07 | Institucional | Conteúdo dos relatórios dos marcos de out./2026 e mar./2027 | Modelo aprovado pela coordenação | RQ-71 | PENDENTE (só contagens agregadas existem) |
| H-A01 | Ambiente | Organização ArcGIS, Client ID e serviços do Radar acessíveis | Credenciais em `.env` de ambiente de testes | LA-05 | PENDENTE |
| H-A02 | Ambiente | XLSForm **aberto, validado e publicado no Survey123 Connect** | Registro do teste e captura da publicação | RQ-24 | NÃO EXECUTADO. **A abertura no Survey123 Connect não foi feita**: não há organização ArcGIS nem o aplicativo. Ver H-A11 para o que foi feito |
| H-A03 | Ambiente | Formato real de exportação do Survey123 confrontado com a tradução | Amostra sintética exportada | `adaptadores/traducao.py` | NÃO EXECUTADO |
| H-A04 | Ambiente | Coleta offline e sincronização em aparelho real, com perda de rede real | Roteiro executado em campo de teste | RQ-20, RQ-26 | NÃO EXECUTADO (simulação local feita) |
| H-A05 | Ambiente | Mapa base offline em formato aceito | Pacote testado em aparelho | RQ-23 | NÃO EXECUTADO |
| H-A06 | Ambiente | Autenticação real de usuários | Integração com o provedor de identidade institucional | R-11 | PENDENTE (o ator é informado pelo chamador) |
| H-A07 | Ambiente | Backup agendado, destino e retenção definidos; restauração ensaiada no ambiente | Registro de ensaio | RQ-44, LA-06 | PENDENTE (backup e restauração locais: EXECUTADO LOCALMENTE) |
| H-A08 | Ambiente | Ancoragem externa do último hash da trilha de auditoria | Registro periódico em sistema institucional | RQ-41, R-19, RQ-88 | PENDENTE (a âncora já é gerada e conferida localmente, DEC-022; falta quem a guarda fora da máquina) |
| H-A09 | Ambiente | Carga e desempenho com volume realista | Relatório de teste | DEC-007 | NÃO EXECUTADO |
| H-A10 | Ambiente | Banco institucional decidido | Decisão registrada | DEC-002 | PENDENTE |
| H-A11 | Ambiente | XLSForm convertido pelo **pyxform** (validador ODK) sem erro | Teste `tests/test_xlsform.py::test_pyxform_converte_sem_erros` e execução de 03/10/2026 (pyxform 4.5.0): converteu, 40 linhas em `survey`, 42 em `choices`, um aviso (tamanho máximo de imagem não definido, de propósito) | RQ-24, DEC-017 | EXECUTADO LOCALMENTE (confere sintaxe XLSForm/ODK; **não** substitui H-A02) |
| H-S01 | Segurança | Dependências sem vulnerabilidade conhecida, em rotina | Saída periódica do verificador | RQ-47, R-12 | EXECUTADO LOCALMENTE (uma vez, sem rotina) |
| H-S02 | Segurança | Revisão independente **humana ou de terceiros** do código das Fases 4 e 5 | Relatório de revisão com defeitos reproduzidos | R-11, R-30 | NÃO EXECUTADO (nas Fases 2 e 3 houve revisão independente; nas Fases 4 e 5 só H-S06) |
| H-S06 | Segurança | Revisão independente das Fases 4 e 5 por agente separado, como advogado do diabo, com falhas reproduzidas, corrigidas e testes de regressão | `tests/test_regressao_revisao_f4f5.py`, `tests/test_regressao_revisao_f4f5_b.py`, DEC-020 | R-30 | EXECUTADO LOCALMENTE (revisor foi um agente de IA; 20 achados, 20 mutações nas correções mortas pelos testes) |
| H-S07 | Segurança | Toda entrada de dado de campo na central confere origem, equipe, estado e vínculo, inclusive do registro gravado | `tests/test_modo_central.py`, `tests/test_regressao_fase6.py` | R-28, RQ-86 | EXECUTADO LOCALMENTE (modo central; sem ambiente real) |
| H-S03 | Segurança | Teste de segurança por terceiros | Relatório | RQ-40 | NÃO EXECUTADO |
| H-S04 | Segurança | Gestão de segredos em ambiente real | Inventário de variáveis e rotação | RQ-42 | NÃO EXECUTADO |
| H-S05 | Segurança | Logs e trilha sem dados sensíveis | Testes automatizados | RQ-46 | EXECUTADO LOCALMENTE (não detecta nome em texto livre, R-21) |
| H-F01 | Campo | Piloto com equipe de vistoria, em área de teste | Relato e registros sintéticos ou de área de teste autorizada | RQ-20 | NÃO EXECUTADO |
| H-F02 | Campo | Conflito de sincronização resolvido e devolvido ao aparelho | Teste automatizado com dois bancos | RQ-27, RQ-76 | EXECUTADO LOCALMENTE (rede simulada) |
| H-F03 | Acessibilidade | Relatório HTML com verificações automáticas | Testes automatizados | RQ-73 | EXECUTADO LOCALMENTE |
| H-F04 | Acessibilidade | Teste com leitor de tela e pessoas usuárias | Relato do teste | RQ-74 | NÃO EXECUTADO |
| H-F05 | Campo | Tela de operação para quem não programa | Protótipo avaliado por usuárias e usuários | README, RQ-91 | NÃO EXECUTADO (a interface local existe e foi verificada por testes e navegador automatizado; nenhuma pessoa usuária a avaliou) |
| H-F06 | Acessibilidade | Interface local com verificação automática (axe-core WCAG 2.0/2.1/2.2 A e AA, 360 e 1280 px, claro e escuro, zoom 200%, ordem de Tab e foco visível) | `scripts/verificar_interface.js`, execução de 03/10/2026: 83 telas, 0 violações, 12 itens de contraste indecidíveis pela ferramenta (rótulos do mapa) conferidos por cálculo em `tests/test_interface.py` | RQ-92, RQ-93 | EXECUTADO LOCALMENTE (cobre só o automático; não é conformidade) |
| H-F07 | Acessibilidade | Interface local com leitor de tela (NVDA, Orca ou TalkBack) e com pessoas usuárias em campo e no escritório | Relato do teste | RQ-96 | NÃO EXECUTADO |
| H-S08 | Segurança | Revisão independente da Fase 6 por agente separado, com falhas reproduzidas, corrigidas e testes de regressão | `tests/test_regressao_fase6.py`, DEC-026 | R-30 | EXECUTADO LOCALMENTE (revisor foi um agente de IA; 15 achados) |

## Como usar

1. Item só muda de situação com evidência anexada ou citada (arquivo, teste, registro).
2. `EXECUTADO LOCALMENTE` nunca é convertido em aprovação por este documento.
3. Mudou o código ou a fonte? Reavalie os itens ligados (coluna "Vínculo").
4. O teste `tests/test_documentos.py` impede que uma linha seja marcada como aprovada neste arquivo e confere que todo LA tem pendência registrada.
