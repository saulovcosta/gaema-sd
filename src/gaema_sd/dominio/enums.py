"""Listas fixas de valores do domínio."""

from enum import Enum


class Estado(str, Enum):
    # Fluxo normal
    CANDIDATA = "CANDIDATA"
    ALERTA = "ALERTA"
    EM_TRIAGEM = "EM_TRIAGEM"
    DEMANDA_ABERTA = "DEMANDA_ABERTA"
    ATRIBUIDA = "ATRIBUIDA"
    PLANEJADA = "PLANEJADA"
    EM_CAMPO = "EM_CAMPO"
    COLETA_PARCIAL = "COLETA_PARCIAL"
    AGUARDANDO_SINCRONIZACAO = "AGUARDANDO_SINCRONIZACAO"
    EM_VALIDACAO = "EM_VALIDACAO"
    AGUARDANDO_REVISAO = "AGUARDANDO_REVISAO"
    DIAGNOSTICO_EMITIDO = "DIAGNOSTICO_EMITIDO"
    EM_TRATATIVA = "EM_TRATATIVA"
    EM_MONITORAMENTO = "EM_MONITORAMENTO"
    ENCERRADA = "ENCERRADA"
    REABERTA = "REABERTA"
    # Excepcionais
    DUPLICADA = "DUPLICADA"
    DADOS_INSUFICIENTES = "DADOS_INSUFICIENTES"
    SEM_ACESSO = "SEM_ACESSO"
    GEOMETRIA_INCONSISTENTE = "GEOMETRIA_INCONSISTENTE"
    CONFLITO_SINCRONIZACAO = "CONFLITO_SINCRONIZACAO"
    CANCELADA_JUSTIFICADA = "CANCELADA_JUSTIFICADA"
    DEVOLVIDA_COMPLEMENTACAO = "DEVOLVIDA_COMPLEMENTACAO"


ESTADOS_NORMAIS = tuple(Estado)[:16]
ESTADOS_EXCEPCIONAIS = tuple(Estado)[16:]


class Papel(str, Enum):
    ANALISTA_TRIAGEM = "ANALISTA_TRIAGEM"   # analisa sinais remotos
    COORDENADOR = "COORDENADOR"             # coordena equipe técnica
    TECNICO_CAMPO = "TECNICO_CAMPO"         # executa vistoria
    REVISOR_TECNICO = "REVISOR_TECNICO"     # revisa diagnóstico
    MEMBRO_MP = "MEMBRO_MP"                 # decide providência institucional
    AUDITOR = "AUDITOR"                     # só leitura e verificação
    ADMINISTRADOR = "ADMINISTRADOR"         # configuração; não move o fluxo
    SISTEMA = "SISTEMA"                     # processos automáticos


class Sensibilidade(str, Enum):
    PUBLICA = "PUBLICA"
    INTERNA = "INTERNA"
    RESTRITA = "RESTRITA"
    SIGILOSA = "SIGILOSA"


class Proveniencia(str, Enum):
    INSTITUCIONAL = "INSTITUCIONAL"
    OBSERVACAO_PUBLICA = "OBSERVACAO_PUBLICA"
    DOCUMENTACAO_OFICIAL = "DOCUMENTACAO_OFICIAL"
    CIENTIFICO = "CIENTIFICO"
    AUTORAL = "AUTORAL"
    PENDENTE = "PENDENTE"


class TipoFonte(str, Enum):
    CAMADA_RASTER = "CAMADA_RASTER"
    CAMADA_VETORIAL = "CAMADA_VETORIAL"
    TABELA = "TABELA"
    REGISTRO_MANUAL = "REGISTRO_MANUAL"


class SituacaoIntegracao(str, Enum):
    ESPECIFICADA = "ESPECIFICADA"
    EM_TESTE = "EM_TESTE"
    ATIVA = "ATIVA"
    DESATIVADA = "DESATIVADA"


class Ambiente(str, Enum):
    DESENVOLVIMENTO = "DESENVOLVIMENTO"
    HOMOLOGACAO = "HOMOLOGACAO"
    OPERACAO = "OPERACAO"


class OrigemAlerta(str, Enum):
    SINAL_REMOTO = "SINAL_REMOTO"
    PECA_INFORMACAO_TECNICA = "PECA_INFORMACAO_TECNICA"      # Portaria GAEMA 001/2026, art. 17, caput
    ENCAMINHAMENTO_PROMOTORIA = "ENCAMINHAMENTO_PROMOTORIA"  # idem, art. 17, IV
    NOTICIA_EXTERNA = "NOTICIA_EXTERNA"
    DEMANDA_INTERNA = "DEMANDA_INTERNA"
    MONITORAMENTO = "MONITORAMENTO"


class CriterioPriorizacao(str, Enum):
    """Critério invocado por PESSOA ao priorizar (Portaria GAEMA 001/2026, art. 17). Sem cálculo automático."""

    ART17_I = "ART17_I"      # erosão ativa de grande porte com risco a curso d'água ou rodovia
    ART17_II = "ART17_II"    # pastagem degradada atestada com impacto supramunicipal
    ART17_III = "ART17_III"  # registro humano; indicador de 40% PENDENTE (RQ-65)
    ART17_IV = "ART17_IV"    # encaminhamento de Promotoria, mineração de grande escala
    OUTRO = "OUTRO"


class OrigemAreaInteresse(str, Enum):
    DE_CANDIDATA = "DE_CANDIDATA"
    DESENHADA = "DESENHADA"
    IMPORTADA = "IMPORTADA"


class CondicaoAcesso(str, Enum):
    NAO_INFORMADA = "NAO_INFORMADA"
    ACESSO_REALIZADO = "ACESSO_REALIZADO"
    ACESSO_PARCIAL = "ACESSO_PARCIAL"
    SEM_ACESSO = "SEM_ACESSO"


class StatusSincronizacao(str, Enum):
    LOCAL = "LOCAL"
    PENDENTE = "PENDENTE"
    SINCRONIZADO = "SINCRONIZADO"
    CONFLITO = "CONFLITO"


class VariavelCampo(str, Enum):
    COBERTURA_FORRAGEIRA = "COBERTURA_FORRAGEIRA"
    VIGOR_FORRAGEIRA = "VIGOR_FORRAGEIRA"
    ALTURA_PASTO = "ALTURA_PASTO"                  # F11/F12: "altura do pasto"/"hábito de crescimento"
    SOLO_EXPOSTO = "SOLO_EXPOSTO"
    PLANTAS_INVASORAS = "PLANTAS_INVASORAS"
    CUPINS_MONTICULO = "CUPINS_MONTICULO"
    EROSAO_LAMINAR = "EROSAO_LAMINAR"
    SULCOS = "SULCOS"
    RAVINAS = "RAVINAS"
    VOCOROCAS = "VOCOROCAS"
    UMIDADE_SOLO = "UMIDADE_SOLO"
    PRECIPITACAO_RECENTE = "PRECIPITACAO_RECENTE"  # F12: chuva nas últimas 48 h (contexto da penetrometria)
    TIPO_SOLO = "TIPO_SOLO"                        # F12: informado a partir de mapa de solos
    FORMACAO_GEOLOGICA = "FORMACAO_GEOLOGICA"      # F11/F12: informado a partir de mapa geológico
    ANIMAIS_PASTEJO = "ANIMAIS_PASTEJO"
    CONTEXTO_SAZONAL = "CONTEXTO_SAZONAL"
    DRENAGEM = "DRENAGEM"
    DECLIVIDADE = "DECLIVIDADE"
    MANEJO_INFORMADO = "MANEJO_INFORMADO"
    HIPOTESE_ALTERNATIVA = "HIPOTESE_ALTERNATIVA"
    OUTRA = "OUTRA"


class CategoriaEvidencia(str, Enum):
    FOTO_PANORAMICA = "FOTO_PANORAMICA"
    FOTO_SOLO = "FOTO_SOLO"
    FOTO_FORRAGEIRA = "FOTO_FORRAGEIRA"
    FOTO_INVASORA = "FOTO_INVASORA"
    FOTO_CUPINZEIRO = "FOTO_CUPINZEIRO"
    FOTO_EROSAO = "FOTO_EROSAO"
    FOTO_MEDICAO = "FOTO_MEDICAO"
    DOCUMENTO = "DOCUMENTO"
    OUTRA = "OUTRA"


class ModoProtocolo(str, Enum):
    DESCRITIVO = "DESCRITIVO"
    PROTOTIPO_TESTE = "PROTOTIPO_TESTE"
    VALIDADO_CIENTIFICAMENTE = "VALIDADO_CIENTIFICAMENTE"


class SituacaoPedidoAcesso(str, Enum):
    """Pedido de usuário de TESTE. Não há autenticação real (R-31): aprovar só libera um papel de teste."""

    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class SituacaoDiagnostico(str, Enum):
    COMPUTADO = "COMPUTADO"
    EM_REVISAO = "EM_REVISAO"
    REVISADO = "REVISADO"
    SUBSTITUIDO = "SUBSTITUIDO"


class ResultadoRevisao(str, Enum):
    APROVADO = "APROVADO"
    APROVADO_COM_RESSALVAS = "APROVADO_COM_RESSALVAS"
    DEVOLVIDO = "DEVOLVIDO"
    REJEITADO = "REJEITADO"


class TipoProvidencia(str, Enum):
    """Ações institucionais registradas por decisão humana. Não são conclusões."""

    ENCAMINHAMENTO_TECNICO = "ENCAMINHAMENTO_TECNICO"
    REQUISICAO_INFORMACAO = "REQUISICAO_INFORMACAO"
    REUNIAO_TRATATIVA = "REUNIAO_TRATATIVA"
    RECOMENDACAO = "RECOMENDACAO"
    ACOMPANHAMENTO = "ACOMPANHAMENTO"
    ARQUIVAMENTO_DA_ANALISE = "ARQUIVAMENTO_DA_ANALISE"
    OUTRA = "OUTRA"


class TipoPlano(str, Enum):
    RECUPERACAO = "RECUPERACAO"
    RENOVACAO = "RENOVACAO"
    A_DEFINIR = "A_DEFINIR"


class SituacaoMarco(str, Enum):
    PREVISTO = "PREVISTO"
    VERIFICACAO_PENDENTE = "VERIFICACAO_PENDENTE"
    CUMPRIDO = "CUMPRIDO"
    NAO_CUMPRIDO = "NAO_CUMPRIDO"
    CANCELADO = "CANCELADO"


class FormatoRelatorio(str, Enum):
    HTML = "HTML"
    PDF = "PDF"
