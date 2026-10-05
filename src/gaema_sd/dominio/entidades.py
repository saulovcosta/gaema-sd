"""Entidades do domínio do GAEMA SD.

Regras de fronteira (DEC-006):
- AreaInteresse é um recorte geográfico de análise. Não é imóvel, não é cadastro
  territorial e não identifica ocupante, possuidor ou proprietário.
- Cruzamentos com camadas territoriais são indícios espaciais, não titularidade.
- Nenhuma entidade tem campo de autoria de infração, ilicitude, dano jurídico,
  responsabilidade ou nexo causal. Providencia registra decisão humana.
- Pessoas aparecem apenas como identificador de usuário do sistema.

Detalhamento campo a campo: docs/dominio.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import ClassVar, Optional

from .enums import (
    Ambiente,
    CategoriaEvidencia,
    CondicaoAcesso,
    CriterioPriorizacao,
    Estado,
    FormatoRelatorio,
    ModoProtocolo,
    OrigemAlerta,
    OrigemAreaInteresse,
    Papel,
    Proveniencia,
    ResultadoRevisao,
    Sensibilidade,
    SituacaoDiagnostico,
    SituacaoIntegracao,
    SituacaoMarco,
    SituacaoPedidoAcesso,
    StatusSincronizacao,
    TipoFonte,
    TipoPlano,
    TipoProvidencia,
    VariavelCampo,
)

ROTULO_PROTOTIPO = "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"


def novo_id() -> str:
    return str(uuid.uuid4())


def agora() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(kw_only=True)
class Registro:
    """Campos comuns. `versao` sustenta o controle de concorrência otimista."""

    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.INTERNA

    id: str = field(default_factory=novo_id)
    versao: int = 1
    criado_em: datetime = field(default_factory=agora)
    criado_por: str = ""
    atualizado_em: Optional[datetime] = None
    sintetico: bool = False


# ---------------------------------------------------------------- objetos de valor


@dataclass(kw_only=True)
class SinalRemoto:
    """Um indicador remoto configurável (ex.: NDVI). Sem limiar embutido."""

    nome: str
    valor: Optional[float] = None
    unidade: str = ""
    fonte_id: str
    data_referencia: date
    metodo: str = ""


@dataclass(kw_only=True)
class CruzamentoTerritorial:
    """Sobreposição espacial com uma camada territorial. Indício, não titularidade."""

    fonte_id: str
    camada: str
    identificador_externo: str = ""
    sobreposicao_percentual: Optional[float] = None
    observacao: str = ""


@dataclass(kw_only=True)
class MembroEquipe:
    usuario_id: str
    papel: Papel
    funcao: str = ""


# ---------------------------------------------------------------- entidades


@dataclass(kw_only=True)
class FonteDado(Registro):
    nome: str
    tipo: TipoFonte
    provedor: str
    data_referencia: Optional[date] = None
    resolucao_m: Optional[float] = None
    autorizacao_uso: str = "PENDENTE"
    url_referencia: str = ""
    nota_qualidade: str = ""
    proveniencia: Proveniencia = Proveniencia.PENDENTE


@dataclass(kw_only=True)
class IntegracaoExterna(Registro):
    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    nome: str
    sistema: str
    situacao: SituacaoIntegracao = SituacaoIntegracao.ESPECIFICADA
    ambiente: Ambiente = Ambiente.DESENVOLVIMENTO
    variavel_configuracao: str = ""  # NOME da variável de ambiente; nunca o valor
    evidencia_teste: str = ""
    observacoes: str = ""


@dataclass(kw_only=True)
class AreaCandidata(Registro):
    geometria_wkt: str
    fonte_ids: list[str] = field(default_factory=list)
    sinais: list[SinalRemoto] = field(default_factory=list)
    data_deteccao: date
    metodo_selecao: str = ""
    prioridade: Optional[int] = None
    chave_deduplicacao: str = ""


@dataclass(kw_only=True)
class Alerta(Registro):
    origem: OrigemAlerta
    descricao: str
    data_alerta: date
    area_candidata_id: Optional[str] = None
    geometria_wkt: str = ""
    referencia_documento: str = ""  # ex.: identificação da Peça de Informação Técnica; sem dado pessoal


@dataclass(kw_only=True)
class AreaInteresse(Registro):
    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    geometria_wkt: str
    descricao: str
    origem: OrigemAreaInteresse
    area_candidata_id: Optional[str] = None
    cruzamentos: list[CruzamentoTerritorial] = field(default_factory=list)


@dataclass(kw_only=True)
class Demanda(Registro):
    """Unidade de acompanhamento que percorre a máquina de estados."""

    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    titulo: str
    objetivo: str = ""
    estado: Estado = Estado.CANDIDATA
    estado_anterior: Optional[Estado] = None
    alerta_ids: list[str] = field(default_factory=list)
    area_candidata_id: Optional[str] = None
    area_interesse_id: Optional[str] = None
    equipe_id: Optional[str] = None
    duplicada_de: Optional[str] = None
    referencia_interna: str = ""
    criterio_priorizacao: Optional[CriterioPriorizacao] = None  # escolhido por pessoa
    motivo_priorizacao: str = ""
    municipio: str = ""  # nome do município como informado; texto livre, sem cadastro


@dataclass(kw_only=True)
class Equipe(Registro):
    nome: str
    membros: list[MembroEquipe] = field(default_factory=list)


@dataclass(kw_only=True)
class CampanhaVistoria(Registro):
    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    demanda_id: str
    equipe_id: str
    versao_protocolo_id: str
    objetivo: str
    data_planejada: date
    inicio_em: Optional[datetime] = None
    fim_em: Optional[datetime] = None
    pacote_offline: str = ""
    condicao_acesso: CondicaoAcesso = CondicaoAcesso.NAO_INFORMADA
    nota_acesso: str = ""


@dataclass(kw_only=True)
class PontoAmostral(Registro):
    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    campanha_id: str
    codigo: str
    latitude: float
    longitude: float
    precisao_gps_m: Optional[float]
    altitude_m: Optional[float] = None
    capturado_em: datetime
    dispositivo_id: str = ""
    geometria_wkt: str = ""
    chave_idempotencia: str = ""
    status_sincronizacao: StatusSincronizacao = StatusSincronizacao.LOCAL


@dataclass(kw_only=True)
class Observacao(Registro):
    ponto_id: str
    variavel: VariavelCampo
    valor_bruto: str
    unidade_bruta: str
    valor_normalizado: Optional[float] = None
    unidade_normalizada: str = ""
    observado_em: datetime
    observador_id: str
    nota: str = ""
    chave_idempotencia: str = ""
    status_sincronizacao: StatusSincronizacao = StatusSincronizacao.LOCAL


@dataclass(kw_only=True)
class MedicaoPenetracao(Registro):
    ponto_id: str
    repeticao: int
    profundidade_bruta: str
    profundidade_unidade: str
    resistencia_bruta: str
    resistencia_unidade: str
    profundidade_cm: Optional[float] = None
    resistencia_kpa: Optional[float] = None
    contexto_umidade: str = ""
    equipamento: str = ""
    medido_em: datetime
    chave_idempotencia: str = ""
    status_sincronizacao: StatusSincronizacao = StatusSincronizacao.LOCAL


@dataclass(kw_only=True)
class Evidencia(Registro):
    """Arquivo original nunca é sobrescrito; correção gera nova Evidencia."""

    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    campanha_id: str
    ponto_id: Optional[str] = None
    observacao_id: Optional[str] = None
    categoria: CategoriaEvidencia
    nome_arquivo_original: str
    tipo_mime: str
    tamanho_bytes: int
    sha256: str
    registrado_por: str
    capturado_em_declarado: Optional[datetime] = None
    latitude_declarada: Optional[float] = None   # EXIF/GPS: declarado, não verdade
    longitude_declarada: Optional[float] = None
    armazenamento_ref: str = ""
    substitui_evidencia_id: Optional[str] = None
    chave_idempotencia: str = ""
    status_sincronizacao: StatusSincronizacao = StatusSincronizacao.LOCAL


@dataclass(kw_only=True)
class VersaoProtocolo(Registro):
    """Imutável após publicação: mudança gera nova versão."""

    codigo: str
    versao_semantica: str
    modo: ModoProtocolo = ModoProtocolo.DESCRITIVO
    rotulo: str = ""
    definicao_json: str = "{}"
    hash_definicao: str = ""
    vigente_desde: Optional[date] = None
    referencia_validacao: str = ""
    proveniencia: Proveniencia = Proveniencia.AUTORAL


@dataclass(kw_only=True)
class Diagnostico(Registro):
    """Resultado computado. Descritivo; só vale após RevisaoTecnica."""

    demanda_id: str
    campanha_id: str
    versao_protocolo_id: str
    hash_definicao_protocolo: str
    hash_entradas: str
    resultado_descritivo: str
    categoria_descritiva: str = ""
    regras_disparadas: list[str] = field(default_factory=list)
    limitacoes: str = ""
    hipoteses_alternativas: str = ""
    rotulo_validade: str = ""
    situacao: SituacaoDiagnostico = SituacaoDiagnostico.COMPUTADO
    substitui_diagnostico_id: Optional[str] = None
    entradas_canonicas: str = ""  # fotografia das entradas usadas (reprodução histórica)
    resultado_json: str = ""      # saída completa do motor, para explicação e relatório


@dataclass(kw_only=True)
class RevisaoTecnica(Registro):
    diagnostico_id: str
    revisor_id: str
    resultado: ResultadoRevisao
    fundamentacao: str
    ressalvas: str = ""
    revisado_em: datetime = field(default_factory=agora)


@dataclass(kw_only=True)
class Providencia(Registro):
    """Registro de decisão humana. O sistema não sugere nem infere providência."""

    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    demanda_id: str
    tipo: TipoProvidencia
    descricao: str
    decidido_por: str
    decidido_em: datetime = field(default_factory=agora)
    base_tecnica_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class PlanoRecuperacao(Registro):
    demanda_id: str
    tipo: TipoPlano = TipoPlano.A_DEFINIR
    objetivos: str
    acoes: list[str] = field(default_factory=list)
    origem_documento: str = ""
    elaborado_por: str = ""
    prazo_meses: Optional[int] = None


@dataclass(kw_only=True)
class MarcoMonitoramento(Registro):
    plano_id: str
    descricao: str
    indicador: str = ""
    data_prevista: date
    data_verificada: Optional[date] = None
    situacao: SituacaoMarco = SituacaoMarco.PREVISTO
    campanha_verificacao_id: Optional[str] = None


@dataclass(kw_only=True)
class Relatorio(Registro):
    """Toda correção gera nova versão; a anterior é preservada."""

    SENSIBILIDADE: ClassVar[Sensibilidade] = Sensibilidade.RESTRITA

    demanda_id: str
    numero_versao: int = 1
    diagnostico_id: str
    revisao_id: Optional[str] = None
    versao_protocolo_id: str
    formato: FormatoRelatorio = FormatoRelatorio.HTML
    hash_conteudo: str
    gerado_por: str
    gerado_em: datetime = field(default_factory=agora)
    substitui_relatorio_id: Optional[str] = None
    motivo_reemissao: str = ""


@dataclass(kw_only=True)
class PedidoAcesso(Registro):
    """Pedido de usuário de TESTE (identificador sintético). Sem autenticação real (R-31)."""

    identificador: str            # usuario-sintetico-...; nunca nome, e-mail ou documento de pessoa
    papel: Papel
    motivo: str
    situacao: SituacaoPedidoAcesso = SituacaoPedidoAcesso.PENDENTE
    decidido_por: str = ""
    motivo_decisao: str = ""
    decidido_em: Optional[datetime] = None


@dataclass(kw_only=True, frozen=True)
class EventoAuditoria:
    """Evento imutável, encadeado por hash ao anterior (ver auditoria/trilha.py)."""

    sequencia: int
    ocorrido_em: datetime
    ator_id: str
    papeis: tuple[str, ...]
    acao: str
    entidade: str
    entidade_id: str
    estado_origem: Optional[str] = None
    estado_destino: Optional[str] = None
    motivo: str = ""
    detalhes: dict = field(default_factory=dict)
    hash_anterior: str
    hash_evento: str


ENTIDADES: tuple[type, ...] = (
    AreaCandidata,
    Alerta,
    Demanda,
    AreaInteresse,
    Equipe,
    CampanhaVistoria,
    PontoAmostral,
    Observacao,
    MedicaoPenetracao,
    Evidencia,
    VersaoProtocolo,
    Diagnostico,
    RevisaoTecnica,
    Providencia,
    PlanoRecuperacao,
    MarcoMonitoramento,
    Relatorio,
    EventoAuditoria,
    FonteDado,
    IntegracaoExterna,
    PedidoAcesso,
)

POR_NOME: dict[str, type] = {c.__name__: c for c in ENTIDADES}
