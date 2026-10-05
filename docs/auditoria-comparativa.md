# Auditoria comparativa: funções públicas do SIPADE × GAEMA SD (Rodada 5)

Nível: **ESPECIFICADO** (documento). Proveniência: OBSERVAÇÃO PÚBLICA (o que o SIPADE mostra publicamente) e AUTORAL (o que o GAEMA SD tem, a lacuna e a prioridade sugerida). Data: 05/10/2026.

**Regras deste documento:**
- Compara-se só **função**. Nenhuma tela, texto ou identidade visual do SIPADE foi copiada.
- As fontes são as de `docs/fontes.md` (F1 site, F2 artigo SBSI 2023, F11 e F12 vídeos) e as observações V-01 a V-16 de `docs/sipade-videos.md`. Nada além do que essas fontes mostram.
- "Teste" aponta o teste automatizado que cobre a função no GAEMA SD. "—" quando não há.
- A **prioridade** é sugestão AUTORAL para a coordenação decidir. Não é decisão institucional (ver `docs/pendencias.md`, seção 4).
- Nenhuma função listada como existente foi validada em ambiente real. O nível de pronto de cada entrega está em `docs/ESTADO.md`.

## 1. Divergência mantida sem conciliar: 3 categorias × 4 cenários

| Fonte | O que mostra |
|---|---|
| F11 (vídeo "Apresentação SIPADE") | **3** estados: degradada, em degradação, não degradada (`docs/sipade-videos.md`, 1.2) |
| F1 (site estático do SIPADE) | **4** cenários de relatório (FC-04) |

As duas fontes públicas divergem. Este documento **não escolhe nem concilia**. No GAEMA SD, as categorias ficam no protocolo versionado (`config/protocolos/`) e o modo descritivo continua o padrão.

**Nota de fonte:** o pedido mencionou "artigo". No repositório, as **3 categorias vêm do vídeo F11, não do artigo F2**. O artigo F2 confirma título, autoria, implantação na Bacia do Rio Uberaba e a referência ao NDVI de Valle Júnior et al. (2019). Ele não foi registrado como fonte das categorias.

## 2. Tabela comparativa

| # | Função pública do SIPADE | Fonte | O que o GAEMA SD tem | Teste | Lacuna | Prioridade (sugestão) |
|---|---|---|---|---|---|---|
| 1 | Identificar áreas indicativas de degradação pela web, com satélite | F1 (FC-01), F2 (FC-07), F11 (V-01) | Área candidata só **informada** (criar demanda pela tela) ou **importada** de GeoJSON/CSV, com origem e incerteza declaradas | `tests/test_rodada4.py::test_importacao_grava_aceitos_audita_e_nao_cria_alerta_nem_demanda` | **Não existe triagem por satélite**, processamento de imagem nem NDVI (LA-03, LA-07) | Alta, depende de LA-03 e LA-07 |
| 2 | Registrar a área como demanda | F11 (V-01), F12 (1.3) | Área candidata vira alerta e demanda só por ação humana auditada | `tests/test_rodada4.py::test_candidata_so_vira_alerta_e_demanda_por_acao_humana_auditada` | — | — |
| 3 | Procurador cadastra demanda na web | F12 (1.3, 1.9) | Analista cria demanda pela tela; coordenador e membro do MP movem a demanda pelos estados | `tests/test_rodada3.py::test_analista_cria_demanda_pela_tela_com_os_cinco_registros_auditados` | Papel diferente (analista, não procurador): quem cadastra é decisão institucional | Baixa |
| 4 | Cadastro de propriedade e proprietário (nome, CPF, endereço) | F12 (1.6, V-08) | **Não modelado** por decisão (DEC-006): área de interesse é recorte de análise, não imóvel | `tests/test_fronteira_juridica.py::test_area_de_interesse_declara_que_nao_e_imovel` | Divergência intencional; vínculo opcional com imóvel ou procedimento depende de decisão do coordenador | Decisão do coordenador |
| 5 | Diagnóstico em campo pelo aplicativo, offline | F1 (FC-02), F12 (1.4, V-09) | Coleta em 5 etapas num aparelho **simulado**, com rascunho salvo a cada etapa e fila offline | `tests/test_interface_uso.py::test_coleta_completa_em_etapas_salva_no_aparelho_e_sincroniza` | Aplicativo e aparelho reais; GPS real; mapa base offline | Alta |
| 6 | Presença de cupim, invasora, solo exposto, erosão e gado | F1 (FC-03), F12 (1.5, V-03) | Sim / não / não observado, em botões de 44 px | `tests/test_rodada2.py::test_sim_nao_e_nao_observado_sao_caixas_de_44px_com_foco_e_marca` | Peso dessas variáveis no resultado não é público (LA-02) | Média |
| 7 | Altura do pasto em três faixas | F12 (1.5, V-04) | Número + unidade, **sem faixa** | `tests/test_rodada2.py::test_ambiente_do_ponto_chega_a_central_sem_faixa_nem_lista` | Divergência intencional: faixas sem fundamentação pública (LA-01) | Baixa |
| 8 | Tipo de solo e formação geológica a partir de mapas | F12 (1.5, V-12) | Texto livre "como consta no mapa consultado", com a fonte na nota | `tests/test_rodada2.py::test_ambiente_do_ponto_chega_a_central_sem_faixa_nem_lista` | Sem camada autorizada para preencher sozinho (LA-07) | Média |
| 9 | Resistência à penetração com contexto seco, chuvoso e chuva > 10 mm em 48 h | F12 (1.5, V-06), F11 (1.7) | Cada repetição bruta com unidade; chuva em 48 h como sim/não/não sei, **sem o limite de 10 mm** | `tests/test_rodada2.py::test_chuva_aceita_so_sim_nao_ou_nao_observado` | Protocolo de penetrometria validado (LA-04) | Alta, depende de LA-04 |
| 10 | Fotos por área (tela: até três) | F12 (1.5, V-07) | Até 5 fotos por ponto (AUTORAL), conferidas pelo conteúdo e guardadas com hash | `tests/test_rodada2.py::test_foto_valida_vira_evidencia_na_central_depois_de_sincronizar` | Quantas fotos e de quê é protocolo (LA-04) | Média |
| 11 | Várias áreas por diagnóstico | F12 (1.9, V-15) | Vários pontos amostrais por vistoria | `tests/test_interface_uso.py::test_coleta_completa_em_etapas_salva_no_aparelho_e_sincroniza` | — | — |
| 12 | Sincronizar depois da visita | F12 (1.4) | Fila com reenvio idempotente; divergência vira conflito, decidido pelo coordenador | `tests/test_sincronizacao.py::test_coleta_offline_fica_na_fila_e_envia_tudo`, `tests/test_interface.py::test_coordenador_ve_compara_e_resolve_o_conflito_pela_tela` | Rede real | Alta |
| 13 | Classificação do resultado (3 estados no F11; 4 cenários no F1) | F1 (FC-04), F11 (1.2, V-05) | Modo descritivo como padrão; protótipo de presença/ausência rotulado "SEM VALIDADE CIENTÍFICA" | `tests/test_protocolo.py::test_prototipo_classifica_por_ponto` | Regra, pesos e limiares não públicos (LA-02); divergência 3 × 4 mantida (seção 1) | Alta, depende de LA-02 |
| 14 | Relatório em PDF com tabela de parâmetros e fotos por amostra | F11 (1.7, V-11) | Relatório HTML/PDF A4 com valores brutos, unidades e lista de evidências com hash | `tests/test_relatorio.py::test_pdf_valido_com_todas_as_secoes` | O relatório lista as fotos, mas **não imprime as imagens** | Média |
| 15 | Orientação sobre recuperação ou renovação da pastagem | F1 (FC-05) | Providência, plano e marcos registrados por pessoa; nada automático | `tests/test_fronteira_juridica.py::test_providencias_sao_acoes_e_nao_conclusoes` | Divergência intencional: o sistema não recomenda sozinho | — |
| 16 | Pedido de acesso aprovado por superusuário | F12 (1.5, 1.9) | Pedido de **usuário de teste** aprovado ou rejeitado pelo administrador, com motivo | `tests/test_rodada3.py::test_pedido_aprovado_aparece_na_entrada_e_entra_com_o_papel` | **Sem autenticação real** (R-31) | Alta |
| 17 | Login com e-mail e senha | F12 (1.5) | Não há: entra-se escolhendo um usuário de teste | `tests/test_interface.py::test_login_com_usuario_inexistente_ou_sem_sessao_e_recusado` | Autenticação institucional (R-31) | Alta |
| 18 | Pedido de acesso informa se a pessoa fez o curso | F12 (1.9, V-13) | Não há | — | Capacitação como requisito do técnico (H-I01, V-13) | Média, decisão do coordenador |
| 19 | Policial atribui a demanda a si e agenda a visita | F12 (1.9, V-14) | Autoatribuição opcional (parâmetro desligado); coordenador ou técnico da equipe agenda a vistoria | `tests/test_rodada3.py::test_tecnico_da_equipe_se_atribui_com_parametro_ligado`, `tests/test_rodada3.py::test_vistoria_agendada_pela_tela_libera_o_planejamento` | Ligar a autoatribuição é decisão institucional | Média |
| 20 | Quem faz a vistoria: policiais ambientais | F11 (1.1), F12 (V-10) | Papel genérico "Técnico de campo" | — | Quem exerce a vistoria no Tocantins (H-I01) | Decisão do coordenador |
| 21 | "Minhas demandas" (atendidas e pendentes) | F12 (1.9) | O técnico vê só as demandas da própria equipe; a situação aparece com ícone e texto, não só cor | `tests/test_rodada3.py::test_filtro_nao_amplia_o_que_o_tecnico_ve` | — | — |
| 22 | Painel do procurador por demanda: responsável, data agendada, data da visita, relatório, filtros | F12 (1.9, V-16) | Painel com filtros por situação, equipe, município e data de criação; a demanda mostra equipe, vistorias agendadas e relatórios | `tests/test_rodada3.py::test_filtros_por_situacao_equipe_municipio_e_data` | Responsável individual (só equipe); data de visita realizada não aparece no painel | Baixa |
| 23 | Dashboard web | F12 (1.6) | Resumo por situação e "Exige atenção"; exportação em formato próprio | `tests/test_interface.py::test_painel_lista_a_demanda_com_situacao_e_prioridade` | Relação com o Painel do art. 18 (LA-10) | Média, depende de LA-10 |
| 24 | Mapa com classes de pasto (Bacia do Rio Uberaba) | F11 (1.8) | Mapa esquemático da demanda, sem base cartográfica, com lista de pontos como alternativa | `tests/test_interface_uso.py::test_mapa_tem_legenda_escala_aviso_e_destaca_o_ponto_na_lista_e_no_mapa` | Mapa base, camadas e classes (LA-05, LA-07) | Média |
| 25 | Enviar o relatório em PDF por e-mail depois da visita | F12 (1.4) | Não há envio: o relatório é aberto ou baixado na interface | — | Envio por rede (fora do escopo sem ambiente real) | Baixa |

## 3. ABRAMPA SOLOS

O pedido citou itens da ABRAMPA SOLOS. **O PDF não está no repositório**, nem em `docs/`, nem em outra pasta (busca por "abrampa" em nomes de arquivo, feita em 05/10/2026).

O repositório só menciona a ABRAMPA na Portaria F13, que fala em "customização da plataforma SIPADE/ABRAMPA" (FC-17, IN-06). Por isso, **nenhum item da ABRAMPA SOLOS foi listado aqui**. Listar sem o documento seria inventar.

Para incluir os itens, o PDF precisa ser fornecido. Na próxima rodada, cada item entra nesta tabela com a página como fonte.

## 4. Como este documento é conferido

`tests/test_rodada5.py` confere, todos em nível **UNITÁRIO**:
- se as colunas estão completas;
- se cada teste citado existe;
- se a divergência 3 × 4 está registrada com as duas fontes;
- se nenhuma lista da ABRAMPA foi criada sem o PDF;
- se não há linguagem vedada.
