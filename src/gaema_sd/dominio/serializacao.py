"""Conversão entre entidades e dicionários JSON, sem perda de tipo."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import types
import typing
from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from typing import Any


def para_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: para_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [para_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): para_dict(v) for k, v in obj.items()}
    return obj


def json_canonico(dados: Any) -> str:
    """JSON determinístico (chaves ordenadas, sem espaços) para cálculo de hash."""
    return json.dumps(para_dict(dados), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _dicas(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _converter(tipo: Any, valor: Any) -> Any:
    if valor is None:
        return None
    origem = typing.get_origin(tipo)
    args = typing.get_args(tipo)
    if origem in (typing.Union, types.UnionType):
        nao_nulos = [a for a in args if a is not type(None)]
        return _converter(nao_nulos[0], valor) if len(nao_nulos) == 1 else valor
    if origem in (list, tuple):
        interno = args[0] if args else Any
        convertidos = [_converter(interno, v) for v in valor]
        return tuple(convertidos) if origem is tuple else convertidos
    if origem is dict or tipo is dict:
        return dict(valor)
    if isinstance(tipo, type):
        if issubclass(tipo, Enum):
            return tipo(valor)
        if issubclass(tipo, datetime):
            return datetime.fromisoformat(valor)
        if issubclass(tipo, date):
            return date.fromisoformat(valor)
        if dataclasses.is_dataclass(tipo):
            return de_dict(tipo, valor)
        if tipo is float and isinstance(valor, int):
            return float(valor)
    return valor


def de_dict(cls: type, dados: dict) -> Any:
    dicas = _dicas(cls)
    nomes = {f.name for f in dataclasses.fields(cls)}
    desconhecidos = set(dados) - nomes
    if desconhecidos:
        raise ValueError(f"{cls.__name__}: campos desconhecidos {sorted(desconhecidos)}")
    return cls(**{k: _converter(dicas[k], v) for k, v in dados.items()})
