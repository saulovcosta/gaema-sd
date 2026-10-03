"""Relatório em HTML: Jinja2 com escape automático, sem script nem recurso externo."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from .mapa import svg

_AMBIENTE = Environment(loader=FileSystemLoader(str(Path(__file__).parent)), autoescape=True,
                        undefined=StrictUndefined, trim_blocks=False, keep_trailing_newline=True)


def data_br(valor) -> str:
    """Data ISO → leitura brasileira. Data e hora em UTC (como gravadas), sem microssegundos. Texto que não é data
    volta como veio."""
    if valor is None:
        return "—"
    texto = str(valor)
    try:
        if len(texto) == 10:
            return date.fromisoformat(texto).strftime("%d/%m/%Y")
        dt = datetime.fromisoformat(texto)
    except ValueError:
        return texto
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    return dt.strftime("%d/%m/%Y %H:%M")


def blocos(valor, tamanho: int = 8) -> Markup:
    """Hash em grupos de `tamanho` caracteres para leitura em voz alta e conferência. Os grupos são separados só por
    estilo (nenhum caractere é inserido): copiar e colar devolve o hash inteiro, que também fica no atributo `value`
    do elemento <data>, para leitura por programa."""
    texto = str(valor or "")
    if not texto or texto == "—":
        return Markup("—")
    partes = (texto[i:i + tamanho] for i in range(0, len(texto), tamanho))
    return Markup('<data class="hash" value="{}">').format(texto) + Markup("").join(
        Markup('<span class="bloco">') + escape(x) + Markup("</span>") for x in partes) + Markup("</data>")


_AMBIENTE.filters.update(data_br=data_br, blocos=blocos)


def renderizar(dados: dict) -> bytes:
    mapa = Markup(svg(dados["area"]["geometria_wkt"], dados["pontos"], "Mapa esquemático da área"))  # já escapado
    texto = _AMBIENTE.get_template("modelo.html.j2").render(d=dados, mapa_svg=mapa)
    return texto.encode("utf-8")
