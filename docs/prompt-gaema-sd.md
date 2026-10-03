# Prompt de origem do projeto GAEMA SD

> Registro integral do prompt que iniciou o projeto (sessão de 03/10/2026). Serve como especificação de referência. Alterações de escopo devem ser registradas em `docs/decisoes.md`, não aqui.

---

PROJETO GAEMA SD MÓDULO DE DIAGNÓSTICO DE PASTAGENS DEGRADADAS DO RADAR AMBIENTAL DO MPTO

## 1. MISSÃO

Você atua como equipe sênior de engenharia de software, geotecnologia, confiabilidade, QA e documentação. Construa um módulo autoral do Radar Ambiental do Ministério Público do Estado do Tocantins, com nome provisório GAEMA SD, para apoiar a identificação e o diagnóstico de pastagens degradadas, da triagem remota ao relatório e ao monitoramento.
O ciclo a cobrir: a) identificar áreas candidatas à degradação; b) registrar alertas e abrir demandas de averiguação; c) planejar e executar vistoria georreferenciada em campo, inclusive offline; d) registrar parâmetros, medições repetidas e evidências; e) gerar diagnóstico descritivo e explicável, sujeito a revisão técnica humana; f) emitir relatório reproduzível; g) apoiar a tratativa institucional e o plano de recuperação ou renovação; h) acompanhar marcos de monitoramento.

## 2. USUÁRIO E FORMA DE TRABALHO

O usuário é Promotor de Justiça e não programa. Faça o trabalho técnico. Explique em português claro e curto, sem jargão. Corrija os erros sozinho. Faça no máximo uma pergunta por vez, e só se estiver bloqueado. Antes de qualquer ação destrutiva, mostre o impacto e peça confirmação. Nunca peça senha, token ou chave no chat. Nunca peça que o usuário edite arquivos técnicos.

## 3. FATOS CONFIRMADOS SOBRE O SIPADE

O GAEMA SD tem como referência funcional pública o SIPADE (Sistema de Apoio ao Diagnóstico de Pastagens Degradadas), desenvolvido pelo IFTM e pelo MPMG. Fatos confirmados em 03/10/2026 no site oficial e no artigo: a) o sistema web identifica áreas indicativas de pastagens degradadas; b) o sistema mobile identifica o grau de degradação em campo; c) o usuário informa presença de plantas invasoras, de cupim de montículo e de erosão laminar, entre outras; d) o relatório classifica a pastagem em quatro cenários: pastagem produtiva; plantas invasoras indicando início de degradação; plantas invasoras e cupins, indicando estágio médio; solo desnudo e processo erosivo intenso, indicando pasto degradado e dano ambiental; e) o resultado orienta a recuperação ou a renovação da pastagem; f) o artigo de Tomaz et al. (SBSI 2023, DOI 10.5753/sbsi_estendido.2023.229360) descreve a implantação na Bacia do Rio Uberaba (MG) e cita a abordagem de sensoriamento remoto por NDVI de Valle Júnior et al. (2019).
Nada além disso é fato. Não invente fórmulas, pesos, limiares, protocolos validados, APIs, telas internas, modelos de banco ou textos oficiais. O GAEMA SD é uma implementação independente: não copie identidade visual, textos, código ou layouts de terceiros. Crie nomenclatura, fluxos, componentes e documentação próprios.
Etiquete a proveniência de cada requisito com uma destas marcas: INSTITUCIONAL, OBSERVAÇÃO PÚBLICA, DOCUMENTAÇÃO OFICIAL, CIENTÍFICO, AUTORAL ou PENDENTE.

## 4. FONTES

Consulte as fontes abaixo e registre o resultado em docs/fontes.md: SIPADE (leia esta URL, porque a página inicial carrega por JavaScript): https://www.sipade.com.br/assets/static/home/index.html Artigo: https://sol.sbc.org.br/index.php/sbsi_estendido/article/view/24595 Vídeo de apresentação (não conferido, pode estar bloqueado): https://www.youtube.com/watch?v=7FpfZxlR380 Claude Code, boas práticas: https://code.claude.com/docs/en/best-practices Claude Code, nuvem: https://code.claude.com/docs/en/claude-code-on-the-web Experience Builder Developer Edition, instalação: https://developers.arcgis.com/experience-builder/guide/install-guide/ Survey123, perguntas gerais e uso offline: https://doc.arcgis.com/en/survey123/get-started/faqgeneral.htm Survey123, mapas base offline: https://doc.arcgis.com/en/survey123/create/connect/preparebasemaps.htm Field Maps, sincronização: https://doc.arcgis.com/en/field-maps/android/use-maps/sync.htm
Se uma fonte não abrir, registre como LACUNA e siga em frente. Não preencha lacuna com suposição.
Fatos técnicos já conferidos, que o projeto deve respeitar: a) o Experience Builder Developer Edition exige conta ArcGIS Online ou ArcGIS Enterprise e um Client ID, e roda no computador do desenvolvedor; b) o Survey123 funciona offline, mas perguntas que dependem de serviço hospedado, como geocodificação de endereço, não funcionam sem rede; c) o Survey123 aceita formulários no padrão XLSForm; d) no Field Maps, com feature layer hospedada, vale a última edição sincronizada, o que exige estratégia própria de conflito.

## 5. DADOS E SIGILO

Use somente dados sintéticos. Nenhum dado real do MPTO, de procedimento, de pessoa ou de imóvel entra no repositório. Segredos ficam fora do código. Trate o repositório como privado.

## 6. ARQUITETURA INICIAL

Compare três opções e recomende uma em docs/decisoes.md, com hipótese, motivo, impacto, risco e teste: a) máximo nativo ArcGIS; b) ArcGIS com extensão mínima; c) núcleo independente de ArcGIS, com adaptadores.
Recomendação inicial a confirmar: opção (c). Núcleo em Python 3 com SQLite e pytest, validação geoespacial, motor de protocolo versionado e gerador de relatório em HTML e PDF. Os adaptadores ArcGIS (Feature Services, Survey123 por XLSForm, Field Maps, Experience Builder e ArcGIS API for Python) ficam como interfaces, exemplos e documentação, sem execução, até existir organização ArcGIS acessível. Não declare integração institucional sem ambiente real.

## 7. MODELO DE DOMÍNIO

Projete e implemente, no mínimo: AreaCandidata, Alerta, Demanda, AreaInteresse, Equipe, CampanhaVistoria, PontoAmostral, Observacao, MedicaoPenetracao, Evidencia, VersaoProtocolo, Diagnostico, RevisaoTecnica, Providencia, PlanoRecuperacao, MarcoMonitoramento, Relatorio, EventoAuditoria, FonteDado, IntegracaoExterna.
Para cada entidade, documente em docs/dominio.md: finalidade, campos, tipos, obrigatoriedade, relações, sensibilidade, validações, exemplo sintético, regras de atualização e retenção. Nunca confunda área de interesse, imóvel, cadastro territorial, ocupante, autor, responsável e conclusão jurídica.

## 8. FLUXO DE ESTADOS

Implemente a máquina de estados: CANDIDATA, ALERTA, EM_TRIAGEM, DEMANDA_ABERTA, ATRIBUIDA, PLANEJADA, EM_CAMPO, COLETA_PARCIAL, AGUARDANDO_SINCRONIZACAO, EM_VALIDACAO, AGUARDANDO_REVISAO, DIAGNOSTICO_EMITIDO, EM_TRATATIVA, EM_MONITORAMENTO, ENCERRADA, REABERTA.
Estados excepcionais: DUPLICADA, DADOS_INSUFICIENTES, SEM_ACESSO, GEOMETRIA_INCONSISTENTE, CONFLITO_SINCRONIZACAO, CANCELADA_JUSTIFICADA, DEVOLVIDA_COMPLEMENTACAO.
Para cada transição, defina quem pode fazê-la, pré-condições, validações, motivo, trilha de auditoria e possibilidade de reversão.

## 9. TRIAGEM GEOESPACIAL

Projete um pipeline configurável: ingestão de camadas autorizadas, proveniência, data, resolução, qualidade, harmonização espacial, seleção de candidatas, deduplicação, priorização, cruzamentos territoriais e revisão humana. Fontes que podem ser avaliadas, sem presumir integração pronta: MapBiomas, INPE e TerraBrasilis, PRODES, DETER, camadas oficiais e SICAR, se aplicável e autorizado. A abordagem por NDVI pode entrar como um sinal configurável, sem limiares inventados.
Nunca transforme detecção remota em conclusão técnica final. Separe sempre: sinal remoto, vistoria, resultado computado, revisão técnica e providência institucional.

## 10. CAMPO E OFFLINE

A vistoria de campo é offline-first: missão baixada antes, mapa offline quando aplicável, formulário progressivo, GPS com precisão registrada, pontos e geometrias, medições repetidas, fotos categorizadas, notas, salvamento local, retomada e sincronização posterior com indicação clara de pendência e conflito. Nenhum dado se perde em silêncio. Nenhum registro se duplica ao sincronizar de novo.

## 11. PROTOCOLO TÉCNICO

Implemente um motor configurável e versionado que preserve entradas brutas, valide unidades, registre contexto e versão, explique as regras disparadas, permita revisão humana e reproduza resultados históricos.
Enquanto não houver protocolo científico homologado, opere em modo descritivo. Para desenvolvimento e testes, crie um protocolo rotulado "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA". Os quatro cenários do SIPADE podem servir de categorias descritivas desse protótipo, com regras explícitas e configuráveis.
Variáveis a modelar: cobertura e vigor da forrageira, solo exposto, plantas invasoras, cupins, erosão laminar, sulcos, ravinas, voçorocas, resistência à penetração, profundidade, repetições, umidade do solo, animais e pastejo, contexto seco ou chuvoso, drenagem e declividade, manejo informado, evidências e hipótese alternativa.
Não automatize autoria, ilicitude, dano jurídico, responsabilidade nem nexo causal.

## 12. RELATÓRIO E EVIDÊNCIAS

O relatório reproduzível traz: identificação da demanda, objetivo, área, mapa, fontes, metodologia, versão do protocolo, equipe, pontos amostrados, observações, medições, evidências, resultado descritivo ou classificado, revisão técnica, limitações, recomendações, monitoramento e versão do relatório. Preserve original, hash, data, autoria, vínculo com observação e ponto, e histórico de revisão. Toda correção gera nova versão. Hash não é prova material absoluta, e EXIF ou GPS não são verdade inquestionável.

## 13. SEGURANÇA E CONFIABILIDADE

Implemente ou documente, conforme a fase: separação de ambientes, menor privilégio, validação de acesso (filtro de interface não é controle de acesso), segredos fora do código, trilha de auditoria, exportação controlada, logs sem excesso de dados sensíveis, backup lógico com restauração testável, validação de anexos, análise de dependências, registro de riscos e rollback.

## 14. TESTES

Crie e execute testes unitários, de integração, de contrato, geoespaciais, de offline e sincronização, de concorrência, de acessibilidade, de segurança básica, de regressão, de relatório e de auditoria. Cenários obrigatórios: perda de rede; retomada após interrupção; envio duplicado; conflito de atualização; anexo inválido; GPS ruim; geometria inválida; variável obrigatória ausente; protocolo alterado; relatório reemitido; acesso indevido; serviço indisponível. Não marque como aprovado o que não foi executado.

## 15. FASES

Fase 1, descoberta: inventário do ambiente e do repositório, leitura das fontes, matriz FATOS CONFIRMADOS / INFERÊNCIAS / LACUNAS / DECISÕES em docs/fontes.md, comparação das três arquiteturas, recomendação e estrutura do projeto (README.md, CLAUDE.md curto e operacional, docs/, src/, tests/, fixtures/, schemas/, scripts/, adapters/, config/). Grave este prompt em docs/prompt-gaema-sd.md. Fase 2, núcleo: modelo de domínio, máquina de estados, validações e auditoria, com testes unitários. Fase 3, protótipo funcional local: área candidata, alerta, demanda, vistoria, evidências, revisão e relatório. Fase 4, robustez: testes de integração, simulação de offline e sincronização, concorrência, acessibilidade, segurança, observabilidade e rollback. Fase 5, preparação institucional: adaptadores ArcGIS (inclusive XLSForm do formulário de vistoria), pontos de integração, checklist de homologação e pendências científicas e de ambiente.

## 16. ESCOPO DESTA SESSÃO

Execute somente as Fases 1 e 2. Comece em modo de plano e mostre o plano antes de editar arquivos. Ao fim de cada fase: rode os testes, atualize README.md, CLAUDE.md e docs/ESTADO.md (o que foi feito, o que falta e o próximo passo exato), faça commit e resuma em até cinco linhas. Se uma tarefa exigir mais de uma sessão, divida e proponha a divisão. Pare ao fim da Fase 2.

## 17. DEFINIÇÃO DE PRONTO

Classifique cada entrega em um destes níveis: ESPECIFICADO, IMPLEMENTADO LOCALMENTE, TESTADO LOCALMENTE, INTEGRÁVEL, VALIDADO EM HOMOLOGAÇÃO, PRONTO PARA SUBMISSÃO INSTITUCIONAL. Sem evidência real, não use as palavras "perfeito", "produção", "homologado" nem "integrado ao MPTO".

## 18. COMECE AGORA

Verifique as fontes, faça o inventário do ambiente, produza a matriz da Fase 1, recomende a arquitetura e mostre o plano. Aja, verifique, corrija, registre e continue.
