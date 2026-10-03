"""Definição versionada de protocolo (JSON) e sua validação.

Nesta fase só existem condições de presença/ausência. Qualquer operador de
comparação numérica é recusado: limiares dependem de protocolo científico
validado (lacunas LA-02 a LA-04, LA-08).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..dominio.entidades import ROTULO_PROTOTIPO
from ..dominio.enums import ModoProtocolo, Proveniencia, VariavelCampo
from ..dominio.serializacao import json_canonico, sha256_texto
from ..erros import ErroGaema

OPERADORES = {"presente", "ausente", "qualquer_presente"}
DIRETORIO_PADRAO = Path(__file__).resolve().parents[3] / "config" / "protocolos"
_VARIAVEIS = {v.value for v in VariavelCampo}


class DefinicaoInvalida(ErroGaema):
    """Arquivo de protocolo fora do formato aceito."""


@dataclass(frozen=True)
class Condicao:
    operador: str
    variaveis: tuple[str, ...]


@dataclass(frozen=True)
class Regra:
    id: str
    descricao: str
    categoria: str
    condicoes: tuple[Condicao, ...]


@dataclass(frozen=True)
class DefinicaoProtocolo:
    codigo: str
    versao: str
    modo: ModoProtocolo
    rotulo: str
    descricao: str
    proveniencia: Proveniencia
    regras: tuple[Regra, ...]
    categorias: dict[str, str]
    limitacoes: tuple[str, ...]


CODIGO_CATEGORIA = re.compile(r"[A-Z][A-Z0-9_-]{0,19}")


def _exigir(cond: bool, mensagem: str) -> None:
    if not cond:
        raise DefinicaoInvalida(mensagem)


def _chaves(dados: dict, aceitas: set[str], onde: str) -> None:
    sobra = set(dados) - aceitas
    _exigir(not sobra, f"{onde}: campos não aceitos {sorted(sobra)}")


def _condicao(d: dict, onde: str) -> Condicao:
    _exigir(isinstance(d, dict), f"{onde}: condição deve ser objeto")
    _chaves(d, {"operador", "variavel", "variaveis"}, onde)
    op = d.get("operador")
    _exigir(op in OPERADORES,
            f"{onde}: operador '{op}' não permitido; só {sorted(OPERADORES)} (limiar numérico não é aceito)")
    if op == "qualquer_presente":
        vs = d.get("variaveis")
        _exigir(isinstance(vs, list) and len(vs) >= 2, f"{onde}: 'qualquer_presente' exige lista 'variaveis'")
    else:
        vs = [d.get("variavel")]
        _exigir("variaveis" not in d, f"{onde}: '{op}' usa 'variavel' (uma só)")
    for v in vs:
        _exigir(v in _VARIAVEIS, f"{onde}: variável desconhecida '{v}'")
    return Condicao(op, tuple(vs))


def carregar_definicao(dados: dict) -> DefinicaoProtocolo:
    _exigir(isinstance(dados, dict), "definição deve ser um objeto JSON")
    _chaves(dados, {"codigo", "versao", "modo", "rotulo", "descricao", "proveniencia", "regras",
                    "categorias", "limitacoes"}, "protocolo")
    for campo in ("codigo", "versao", "modo", "descricao", "proveniencia"):
        _exigir(isinstance(dados.get(campo), str) and dados[campo].strip(), f"campo obrigatório: {campo}")
    try:
        modo = ModoProtocolo(dados["modo"])
        proveniencia = Proveniencia(dados["proveniencia"])
    except ValueError as e:
        raise DefinicaoInvalida(str(e)) from e
    rotulo = dados.get("rotulo", "")
    _exigir(isinstance(rotulo, str), "rótulo deve ser texto")
    regras_brutas = dados.get("regras", [])
    categorias = dados.get("categorias", {})
    _exigir(isinstance(regras_brutas, list) and isinstance(categorias, dict), "regras/categorias mal formadas")
    _exigir(all(isinstance(k, str) and CODIGO_CATEGORIA.fullmatch(k) for k in categorias),
            "código de categoria fora do padrão (letra maiúscula seguida de letras maiúsculas, dígitos, _ ou -; "
            "até 20 caracteres). Texto livre vai na descrição, não no código")
    if modo is ModoProtocolo.DESCRITIVO:
        _exigir(not regras_brutas and not categorias, "modo DESCRITIVO não tem regras nem categorias")
        _exigir(rotulo == "", "modo DESCRITIVO não tem rótulo (o sistema usa texto fixo)")
    elif modo is ModoProtocolo.PROTOTIPO_TESTE:
        _exigir(rotulo == ROTULO_PROTOTIPO, f"protótipo exige o rótulo exato '{ROTULO_PROTOTIPO}'")
        _exigir(bool(regras_brutas), "protótipo sem regras")
    else:
        raise DefinicaoInvalida("modo VALIDADO_CIENTIFICAMENTE exige protocolo validado; não disponível")
    regras, ids = [], set()
    for i, r in enumerate(regras_brutas):
        onde = f"regras[{i}]"
        _exigir(isinstance(r, dict), f"{onde}: deve ser objeto")
        _chaves(r, {"id", "descricao", "categoria", "condicoes"}, onde)
        _exigir(r.get("id") and r["id"] not in ids, f"{onde}: id ausente ou repetido")
        _exigir(r.get("categoria") in categorias, f"{onde}: categoria não declarada em 'categorias'")
        conds = r.get("condicoes")
        _exigir(isinstance(conds, list) and conds, f"{onde}: sem condições")
        ids.add(r["id"])
        regras.append(Regra(r["id"], r.get("descricao", ""), r["categoria"],
                            tuple(_condicao(c, f"{onde}.condicoes[{j}]") for j, c in enumerate(conds))))
    limitacoes = dados.get("limitacoes", [])
    _exigir(isinstance(limitacoes, list) and all(isinstance(x, str) for x in limitacoes), "limitacoes: lista de textos")
    return DefinicaoProtocolo(dados["codigo"], dados["versao"], modo, rotulo, dados["descricao"], proveniencia,
                              tuple(regras), dict(categorias), tuple(limitacoes))


def canonizar(dados: dict) -> tuple[str, str]:
    """Texto canônico da definição e seu SHA-256 (o que fica gravado na VersaoProtocolo)."""
    carregar_definicao(dados)
    texto = json_canonico(dados)
    return texto, sha256_texto(texto)


def ler_arquivo(nome: str, diretorio: Path = DIRETORIO_PADRAO) -> dict:
    with open(diretorio / nome, encoding="utf-8") as f:
        return json.load(f)
