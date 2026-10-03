from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..erros import ValidacaoFalhou


class Gravidade(str, Enum):
    ERRO = "ERRO"      # impede gravar ou transitar
    ALERTA = "ALERTA"  # grava, mas sinaliza para revisão humana


@dataclass(frozen=True)
class Problema:
    codigo: str
    campo: str
    mensagem: str
    gravidade: Gravidade = Gravidade.ERRO


def erro(codigo: str, campo: str, mensagem: str) -> Problema:
    return Problema(codigo, campo, mensagem, Gravidade.ERRO)


def alerta(codigo: str, campo: str, mensagem: str) -> Problema:
    return Problema(codigo, campo, mensagem, Gravidade.ALERTA)


def tem_erro(problemas) -> bool:
    return any(p.gravidade is Gravidade.ERRO for p in problemas)


def exigir_sem_erros(problemas) -> list[Problema]:
    """Levanta ValidacaoFalhou se houver ERRO; devolve os ALERTAS."""
    problemas = list(problemas)
    erros = [p for p in problemas if p.gravidade is Gravidade.ERRO]
    if erros:
        raise ValidacaoFalhou(erros)
    return problemas
