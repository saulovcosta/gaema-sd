"""Conferência de tipos antes de gravar: evita registro que não pode ser lido depois."""

from __future__ import annotations

import dataclasses
import types
import typing
from datetime import date, datetime
from enum import Enum

from ..dominio.serializacao import _dicas
from .problemas import Problema, erro


def _confere(tipo, valor) -> bool:
    if valor is None:
        origem = typing.get_origin(tipo)
        return origem in (typing.Union, types.UnionType) and type(None) in typing.get_args(tipo)
    origem, args = typing.get_origin(tipo), typing.get_args(tipo)
    if origem in (typing.Union, types.UnionType):
        return any(_confere(a, valor) for a in args if a is not type(None))
    if origem in (list, tuple):
        return isinstance(valor, origem) and all(_confere(args[0], v) for v in valor) if args else True
    if tipo is dict or origem is dict:
        return isinstance(valor, dict)
    if tipo is bool:
        return isinstance(valor, bool)
    if tipo is int:
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo is float:
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    if tipo is date:
        return isinstance(valor, date) and not isinstance(valor, datetime)
    if tipo is datetime:
        return isinstance(valor, datetime) and valor.tzinfo is not None
    if isinstance(tipo, type) and issubclass(tipo, Enum):
        return isinstance(valor, tipo)
    if isinstance(tipo, type) and dataclasses.is_dataclass(tipo):
        return isinstance(valor, tipo) and not validar_tipos(valor)
    if isinstance(tipo, type):
        return isinstance(valor, tipo)
    return True


def validar_tipos(obj) -> list[Problema]:
    dicas = _dicas(type(obj))
    problemas = []
    for f in dataclasses.fields(obj):
        v = getattr(obj, f.name)
        if not _confere(dicas[f.name], v):
            detalhe = " (data/hora precisa de fuso horário)" if isinstance(v, datetime) and v.tzinfo is None else ""
            problemas.append(erro("TIPO_INVALIDO", f.name,
                                  f"tipo {type(v).__name__} não aceito{detalhe}"))
    return problemas
