"""Política de acesso no núcleo (filtro de interface não é controle de acesso).

Menor privilégio: cada papel recebe só as ações de que precisa.
Mudanças de estado têm controle próprio, por transição (estados/maquina.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..dominio.enums import Papel
from ..erros import AcessoNegado


@dataclass(frozen=True)
class Ator:
    id: str
    papeis: frozenset[Papel]
    ativo: bool = True

    @staticmethod
    def de(id: str, *papeis: Papel) -> "Ator":
        return Ator(id, frozenset(papeis))


class Acao(str, Enum):
    REGISTRAR_FONTE = "REGISTRAR_FONTE"
    REGISTRAR_AREA_CANDIDATA = "REGISTRAR_AREA_CANDIDATA"
    REGISTRAR_ALERTA = "REGISTRAR_ALERTA"
    REGISTRAR_DEMANDA = "REGISTRAR_DEMANDA"
    DEFINIR_AREA_INTERESSE = "DEFINIR_AREA_INTERESSE"
    GERIR_EQUIPE = "GERIR_EQUIPE"
    PLANEJAR_CAMPANHA = "PLANEJAR_CAMPANHA"
    COLETAR_CAMPO = "COLETAR_CAMPO"
    REGISTRAR_EVIDENCIA = "REGISTRAR_EVIDENCIA"
    PUBLICAR_PROTOCOLO = "PUBLICAR_PROTOCOLO"
    COMPUTAR_DIAGNOSTICO = "COMPUTAR_DIAGNOSTICO"
    REVISAR_DIAGNOSTICO = "REVISAR_DIAGNOSTICO"
    EMITIR_RELATORIO = "EMITIR_RELATORIO"
    REGISTRAR_PROVIDENCIA = "REGISTRAR_PROVIDENCIA"
    GERIR_PLANO_MONITORAMENTO = "GERIR_PLANO_MONITORAMENTO"
    REGISTRAR_INTEGRACAO = "REGISTRAR_INTEGRACAO"
    LER = "LER"
    LER_RESTRITO = "LER_RESTRITO"
    EXPORTAR = "EXPORTAR"
    VERIFICAR_AUDITORIA = "VERIFICAR_AUDITORIA"
    SINCRONIZAR = "SINCRONIZAR"
    RESOLVER_CONFLITO_SINCRONIZACAO = "RESOLVER_CONFLITO_SINCRONIZACAO"
    GERIR_BACKUP = "GERIR_BACKUP"


P = Papel
MATRIZ: dict[Acao, frozenset[Papel]] = {
    Acao.REGISTRAR_FONTE: frozenset({P.ANALISTA_TRIAGEM, P.COORDENADOR}),
    Acao.REGISTRAR_AREA_CANDIDATA: frozenset({P.ANALISTA_TRIAGEM, P.SISTEMA}),
    Acao.REGISTRAR_ALERTA: frozenset({P.ANALISTA_TRIAGEM, P.COORDENADOR, P.SISTEMA}),
    Acao.REGISTRAR_DEMANDA: frozenset({P.ANALISTA_TRIAGEM, P.COORDENADOR, P.SISTEMA}),
    Acao.DEFINIR_AREA_INTERESSE: frozenset({P.ANALISTA_TRIAGEM, P.COORDENADOR}),
    Acao.GERIR_EQUIPE: frozenset({P.COORDENADOR}),
    Acao.PLANEJAR_CAMPANHA: frozenset({P.COORDENADOR, P.TECNICO_CAMPO}),
    Acao.COLETAR_CAMPO: frozenset({P.TECNICO_CAMPO}),
    Acao.REGISTRAR_EVIDENCIA: frozenset({P.TECNICO_CAMPO}),
    Acao.PUBLICAR_PROTOCOLO: frozenset({P.COORDENADOR}),
    Acao.COMPUTAR_DIAGNOSTICO: frozenset({P.SISTEMA, P.COORDENADOR}),
    Acao.REVISAR_DIAGNOSTICO: frozenset({P.REVISOR_TECNICO}),
    Acao.EMITIR_RELATORIO: frozenset({P.COORDENADOR, P.REVISOR_TECNICO}),
    Acao.REGISTRAR_PROVIDENCIA: frozenset({P.MEMBRO_MP}),
    Acao.GERIR_PLANO_MONITORAMENTO: frozenset({P.COORDENADOR, P.MEMBRO_MP}),
    Acao.REGISTRAR_INTEGRACAO: frozenset({P.ADMINISTRADOR}),
    Acao.LER: frozenset(set(Papel) - {P.SISTEMA}),
    Acao.LER_RESTRITO: frozenset({P.COORDENADOR, P.TECNICO_CAMPO, P.REVISOR_TECNICO,
                                  P.MEMBRO_MP, P.AUDITOR, P.ANALISTA_TRIAGEM}),
    Acao.EXPORTAR: frozenset({P.COORDENADOR, P.MEMBRO_MP}),
    Acao.VERIFICAR_AUDITORIA: frozenset({P.AUDITOR, P.ADMINISTRADOR}),
    Acao.SINCRONIZAR: frozenset({P.TECNICO_CAMPO}),  # o dispositivo envia como o técnico dono dele
    Acao.RESOLVER_CONFLITO_SINCRONIZACAO: frozenset({P.COORDENADOR}),
    Acao.GERIR_BACKUP: frozenset({P.ADMINISTRADOR}),
}


def pode(ator: Ator, acao: Acao) -> bool:
    return ator.ativo and bool(ator.papeis & MATRIZ[acao])


def exigir(ator: Ator, acao: Acao) -> None:
    if not ator.ativo:
        raise AcessoNegado(f"usuário {ator.id} inativo")
    if not pode(ator, acao):
        papeis = ", ".join(sorted(p.value for p in ator.papeis)) or "nenhum"
        raise AcessoNegado(f"ação {acao.value} não permitida para papéis: {papeis}")
