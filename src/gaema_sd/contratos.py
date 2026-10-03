"""Gera JSON Schema (draft 2020-12) a partir das entidades. Contrato com adaptadores."""

from __future__ import annotations

import dataclasses
import types
import typing
from datetime import date, datetime
from enum import Enum

from .dominio.entidades import ENTIDADES
from .dominio.serializacao import _dicas


def _tipo(t) -> dict:
    origem, args = typing.get_origin(t), typing.get_args(t)
    if origem in (typing.Union, types.UnionType):
        nao_nulos = [a for a in args if a is not type(None)]
        base = _tipo(nao_nulos[0])
        return {"anyOf": [base, {"type": "null"}]}
    if origem in (list, tuple):
        return {"type": "array", "items": _tipo(args[0]) if args else {}}
    if t is dict or origem is dict:
        return {"type": "object"}
    if isinstance(t, type):
        if issubclass(t, Enum):
            return {"type": "string", "enum": [e.value for e in t]}
        if issubclass(t, datetime):
            return {"type": "string", "format": "date-time"}
        if issubclass(t, date):
            return {"type": "string", "format": "date"}
        if t is bool:
            return {"type": "boolean"}
        if t is int:
            return {"type": "integer"}
        if t is float:
            return {"type": "number"}
        if t is str:
            return {"type": "string"}
        if dataclasses.is_dataclass(t):
            return esquema_objeto(t)
    raise TypeError(f"tipo sem mapeamento: {t}")


def esquema_objeto(cls) -> dict:
    dicas = _dicas(cls)
    props, obrig = {}, []
    for f in dataclasses.fields(cls):
        props[f.name] = _tipo(dicas[f.name])
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            obrig.append(f.name)
    return {"type": "object", "properties": props, "required": obrig, "additionalProperties": False}


def esquema(cls) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"gaema-sd/{cls.__name__}.schema.json",
        "title": cls.__name__,
        "description": (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
        **esquema_objeto(cls),
    }


def todos() -> dict[str, dict]:
    return {c.__name__: esquema(c) for c in ENTIDADES}
