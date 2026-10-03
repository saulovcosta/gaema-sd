"""Relatório em HTML: Jinja2 com escape automático, sem script nem recurso externo."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from .mapa import svg

_AMBIENTE = Environment(loader=FileSystemLoader(str(Path(__file__).parent)), autoescape=True,
                        undefined=StrictUndefined, trim_blocks=False, keep_trailing_newline=True)


def renderizar(dados: dict) -> bytes:
    mapa = Markup(svg(dados["area"]["geometria_wkt"], dados["pontos"], "Mapa esquemático da área"))  # já escapado
    texto = _AMBIENTE.get_template("modelo.html.j2").render(d=dados, mapa_svg=mapa)
    return texto.encode("utf-8")
