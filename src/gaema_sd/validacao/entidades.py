"""Regras de validação por entidade. Ver docs/dominio.md."""

from __future__ import annotations

import dataclasses
import re

from ..dominio import entidades as E
from ..dominio.enums import (
    CondicaoAcesso,
    Estado,
    ModoProtocolo,
    Papel,
    SituacaoIntegracao,
    SituacaoMarco,
    VariavelCampo,
)
from . import geometria, gps, unidades
from .problemas import Problema, alerta, erro

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_PERCENTUAIS = {
    VariavelCampo.COBERTURA_FORRAGEIRA,
    VariavelCampo.SOLO_EXPOSTO,
}


def _obrigatorios(obj) -> list[Problema]:
    """Campos sem valor padrão são obrigatórios; texto vazio conta como ausente."""
    problemas = []
    for f in dataclasses.fields(obj):
        sem_padrao = f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
        if not sem_padrao:
            continue
        v = getattr(obj, f.name)
        if f.name == "precisao_gps_m":
            continue  # tratado em gps.validar_precisao, com mensagem própria
        if v is None or (isinstance(v, str) and not v.strip()):
            problemas.append(erro("OBRIGATORIO", f.name, "campo obrigatório ausente"))
    return problemas


def _comum(obj) -> list[Problema]:
    p = _obrigatorios(obj)
    if isinstance(obj, E.Registro):
        if obj.versao < 1:
            p.append(erro("VERSAO_INVALIDA", "versao", "versão deve ser >= 1"))
        if not obj.criado_por.strip():
            p.append(erro("OBRIGATORIO", "criado_por", "identificar quem registrou"))
    return p


def _area_candidata(o: E.AreaCandidata):
    p = geometria.validar_poligono_wkt(o.geometria_wkt)
    if not o.fonte_ids:
        p.append(erro("SEM_FONTE", "fonte_ids", "área candidata precisa de ao menos uma fonte"))
    for i, s in enumerate(o.sinais):
        if s.fonte_id not in o.fonte_ids:
            p.append(erro("SINAL_SEM_FONTE", f"sinais[{i}]", "sinal aponta fonte não listada"))
    return p


def _alerta(o: E.Alerta):
    p = []
    if not o.area_candidata_id and not o.geometria_wkt:
        p.append(erro("ALERTA_SEM_LOCAL", "geometria_wkt",
                      "informar área candidata ou geometria do alerta"))
    if o.geometria_wkt:
        p += geometria.validar_poligono_wkt(o.geometria_wkt)
    return p


def _area_interesse(o: E.AreaInteresse):
    p = geometria.validar_poligono_wkt(o.geometria_wkt)
    for i, c in enumerate(o.cruzamentos):
        if c.sobreposicao_percentual is not None and not 0 <= c.sobreposicao_percentual <= 100:
            p.append(erro("PERCENTUAL_FORA_FAIXA", f"cruzamentos[{i}]", "sobreposição entre 0 e 100"))
    return p


def _demanda(o: E.Demanda):
    p = []
    if o.estado is Estado.DUPLICADA and not o.duplicada_de:
        p.append(erro("DUPLICADA_SEM_ORIGEM", "duplicada_de", "indicar a demanda original"))
    if o.duplicada_de and o.duplicada_de == o.id:
        p.append(erro("DUPLICADA_DE_SI", "duplicada_de", "demanda não pode duplicar a si mesma"))
    return p


def _equipe(o: E.Equipe):
    p = []
    if not o.membros:
        p.append(erro("EQUIPE_VAZIA", "membros", "equipe sem membros"))
    ids = [m.usuario_id for m in o.membros]
    if len(ids) != len(set(ids)):
        p.append(erro("MEMBRO_REPETIDO", "membros", "usuário repetido na equipe"))
    if any(m.papel in (Papel.SISTEMA, Papel.ADMINISTRADOR) for m in o.membros):
        p.append(erro("PAPEL_INADEQUADO", "membros", "SISTEMA/ADMINISTRADOR não compõem equipe"))
    return p


def _campanha(o: E.CampanhaVistoria):
    p = []
    if o.inicio_em and o.fim_em and o.fim_em < o.inicio_em:
        p.append(erro("DATAS_INVERTIDAS", "fim_em", "fim anterior ao início"))
    if o.condicao_acesso is CondicaoAcesso.SEM_ACESSO and not o.nota_acesso.strip():
        p.append(erro("SEM_ACESSO_SEM_NOTA", "nota_acesso", "descrever por que não houve acesso"))
    return p


def _ponto(o: E.PontoAmostral):
    p = geometria.validar_coordenada(o.latitude, o.longitude)
    p += gps.validar_precisao(o.precisao_gps_m)
    if o.geometria_wkt:
        p += geometria.validar_poligono_wkt(o.geometria_wkt)
    if not o.chave_idempotencia:
        p.append(alerta("SEM_CHAVE_IDEMPOTENCIA", "chave_idempotencia",
                        "sem chave de envio; reenvio pode não ser reconhecido"))
    return p


def _observacao(o: E.Observacao):
    p = []
    if o.variavel in _PERCENTUAIS and o.unidade_bruta.strip() in unidades.PERCENTUAL:
        p += unidades.validar_percentual(o.valor_bruto, "valor_bruto")
    if o.variavel is VariavelCampo.OUTRA and not o.nota.strip():
        p.append(erro("OUTRA_SEM_NOTA", "nota", "descrever a variável 'OUTRA'"))
    return p


def _medicao(o: E.MedicaoPenetracao):
    p = []
    if o.repeticao < 1:
        p.append(erro("REPETICAO_INVALIDA", "repeticao", "repetição começa em 1"))
    _, pp = unidades.para_cm(o.profundidade_bruta, o.profundidade_unidade, "profundidade_bruta")
    _, pr = unidades.para_kpa(o.resistencia_bruta, o.resistencia_unidade, "resistencia_bruta")
    return p + pp + pr


def _evidencia(o: E.Evidencia):
    p = []
    if not _HEX64.match(o.sha256 or ""):
        p.append(erro("HASH_INVALIDO", "sha256", "SHA-256 deve ter 64 caracteres hexadecimais"))
    if o.tamanho_bytes <= 0:
        p.append(erro("TAMANHO_INVALIDO", "tamanho_bytes", "tamanho deve ser positivo"))
    if not o.ponto_id and not o.observacao_id:
        p.append(alerta("EVIDENCIA_SEM_VINCULO", "ponto_id",
                        "evidência sem vínculo com ponto ou observação"))
    if (o.latitude_declarada is None) != (o.longitude_declarada is None):
        p.append(erro("COORD_INCOMPLETA", "latitude_declarada", "informar latitude e longitude"))
    elif o.latitude_declarada is not None:
        p += geometria.validar_coordenada(o.latitude_declarada, o.longitude_declarada,
                                          "coordenada_declarada")
    if o.substitui_evidencia_id == o.id:
        p.append(erro("SUBSTITUI_SI", "substitui_evidencia_id", "não pode substituir a si mesma"))
    return p


def _protocolo(o: E.VersaoProtocolo):
    p = []
    if not _SEMVER.match(o.versao_semantica):
        p.append(erro("VERSAO_SEMANTICA", "versao_semantica", "use o formato 1.0.0"))
    if o.modo is ModoProtocolo.PROTOTIPO_TESTE and o.rotulo != E.ROTULO_PROTOTIPO:
        p.append(erro("ROTULO_PROTOTIPO", "rotulo", f"protótipo deve ter o rótulo '{E.ROTULO_PROTOTIPO}'"))
    if o.modo is ModoProtocolo.VALIDADO_CIENTIFICAMENTE and not o.referencia_validacao.strip():
        p.append(erro("SEM_REFERENCIA_VALIDACAO", "referencia_validacao",
                      "modo validado exige referência documental da validação"))
    if not _HEX64.match(o.hash_definicao or ""):
        p.append(erro("HASH_INVALIDO", "hash_definicao", "hash da definição ausente ou inválido"))
    return p


def _diagnostico(o: E.Diagnostico):
    p = []
    for campo in ("hash_definicao_protocolo", "hash_entradas"):
        if not _HEX64.match(getattr(o, campo) or ""):
            p.append(erro("HASH_INVALIDO", campo, "hash ausente ou inválido"))
    if not o.limitacoes.strip():
        p.append(erro("SEM_LIMITACOES", "limitacoes", "todo diagnóstico declara limitações"))
    if o.categoria_descritiva and not o.rotulo_validade.strip():
        p.append(erro("CATEGORIA_SEM_ROTULO", "rotulo_validade",
                      "categoria exige rótulo de validade do protocolo"))
    return p


def _revisao(o: E.RevisaoTecnica):
    if len(o.fundamentacao.strip()) < 20:
        return [erro("FUNDAMENTACAO_CURTA", "fundamentacao", "fundamentar a revisão (mín. 20 caracteres)")]
    return []


def _plano(o: E.PlanoRecuperacao):
    if o.prazo_meses is not None and o.prazo_meses <= 0:
        return [erro("PRAZO_INVALIDO", "prazo_meses", "prazo deve ser positivo")]
    return []


def _marco(o: E.MarcoMonitoramento):
    if o.situacao in (SituacaoMarco.CUMPRIDO, SituacaoMarco.NAO_CUMPRIDO) and not o.data_verificada:
        return [erro("SEM_DATA_VERIFICACAO", "data_verificada", "informar data da verificação")]
    return []


def _relatorio(o: E.Relatorio):
    p = []
    if not _HEX64.match(o.hash_conteudo or ""):
        p.append(erro("HASH_INVALIDO", "hash_conteudo", "hash ausente ou inválido"))
    if o.numero_versao < 1:
        p.append(erro("VERSAO_INVALIDA", "numero_versao", "versão começa em 1"))
    if o.numero_versao > 1 and (not o.substitui_relatorio_id or not o.motivo_reemissao.strip()):
        p.append(erro("REEMISSAO_SEM_MOTIVO", "motivo_reemissao",
                      "reemissão exige relatório substituído e motivo"))
    return p


def _integracao(o: E.IntegracaoExterna):
    p = []
    if o.situacao is SituacaoIntegracao.ATIVA and not o.evidencia_teste.strip():
        p.append(erro("ATIVA_SEM_EVIDENCIA", "evidencia_teste",
                      "integração só é ATIVA com evidência de teste em ambiente real"))
    if o.variavel_configuracao and not re.fullmatch(r"[A-Z][A-Z0-9_]*", o.variavel_configuracao):
        p.append(erro("VARIAVEL_INVALIDA", "variavel_configuracao",
                      "informar só o NOME da variável de ambiente (ex.: ARCGIS_CLIENT_ID)"))
    return p


def _fonte(o: E.FonteDado):
    if o.resolucao_m is not None and o.resolucao_m <= 0:
        return [erro("RESOLUCAO_INVALIDA", "resolucao_m", "resolução deve ser positiva")]
    return []


REGRAS = {
    E.AreaCandidata: _area_candidata,
    E.Alerta: _alerta,
    E.AreaInteresse: _area_interesse,
    E.Demanda: _demanda,
    E.Equipe: _equipe,
    E.CampanhaVistoria: _campanha,
    E.PontoAmostral: _ponto,
    E.Observacao: _observacao,
    E.MedicaoPenetracao: _medicao,
    E.Evidencia: _evidencia,
    E.VersaoProtocolo: _protocolo,
    E.Diagnostico: _diagnostico,
    E.RevisaoTecnica: _revisao,
    E.PlanoRecuperacao: _plano,
    E.MarcoMonitoramento: _marco,
    E.Relatorio: _relatorio,
    E.IntegracaoExterna: _integracao,
    E.FonteDado: _fonte,
}


def validar(obj) -> list[Problema]:
    """Todas as regras da entidade: obrigatórios + regras específicas."""
    regra = REGRAS.get(type(obj))
    return _comum(obj) + (regra(obj) if regra else [])
