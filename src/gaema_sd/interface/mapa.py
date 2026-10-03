"""Mapa esquemático da demanda para a tela (SVG, sem serviço externo, sem JavaScript).

- Área de interesse e pontos; cada ponto é um link que destaca o mesmo ponto na lista ao lado (e vice-versa).
- Ponto selecionado muda de FORMA (losango) e de cor, nunca só de cor.
- Escala APROXIMADA: 1° de latitude ≈ 111,32 km e longitude corrigida pelo cosseno da latitude média (aproximação
  esférica usual). Não é mapa cartográfico; a tela diz isso.
"""

from __future__ import annotations

import math
from html import escape

from markupsafe import Markup
from shapely import wkt as shapely_wkt
from shapely.errors import ShapelyError

LARGURA, ALTURA, MARGEM = 640, 400, 36
METROS_POR_GRAU = 111_320.0


def _aneis(geometria_wkt: str) -> list[list[tuple[float, float]]]:
    if not geometria_wkt:
        return []
    try:
        g = shapely_wkt.loads(geometria_wkt)
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        return [[(c[0], c[1]) for c in p.exterior.coords] for p in polys]
    except (ShapelyError, ValueError, AttributeError):
        return []


def _valor_redondo(maximo_m: float) -> float:
    if maximo_m <= 0:
        return 0
    base = 10 ** math.floor(math.log10(maximo_m))
    for f in (5, 2, 1):
        if f * base <= maximo_m:
            return f * base
    return base


def mapa_svg(area_wkt: str, pontos: list[dict], selecionado: str | None, titulo: str) -> tuple[Markup, dict]:
    """Devolve (svg, info) — info traz a escala usada, para a legenda."""
    aneis = _aneis(area_wkt)
    lons = [c[0] for a in aneis for c in a] + [p["longitude"] for p in pontos]
    lats = [c[1] for a in aneis for c in a] + [p["latitude"] for p in pontos]
    desc = (f"Esquema da área de interesse com {len(pontos)} ponto(s): "
            + "; ".join(f"{p['codigo']} em latitude {p['latitude']:.5f}, longitude {p['longitude']:.5f}" for p in pontos)
            + ". Sem base cartográfica; escala aproximada.")
    partes = [f'<svg class="mapa" viewBox="0 0 {LARGURA} {ALTURA}" role="group" aria-labelledby="mapa-titulo mapa-desc" '
              f'xmlns="http://www.w3.org/2000/svg">',
              f'<title id="mapa-titulo">{escape(titulo)}</title><desc id="mapa-desc">{escape(desc)}</desc>']
    info = {"metros": 0, "rotulo": ""}
    if lons:
        lat0 = math.radians(sum(lats) / len(lats))
        fx = math.cos(lat0)
        minx, maxx, miny, maxy = min(lons) * fx, max(lons) * fx, min(lats), max(lats)
        dx, dy = (maxx - minx) or 1e-4, (maxy - miny) or 1e-4
        k = min((LARGURA - 2 * MARGEM) / dx, (ALTURA - 2 * MARGEM - 30) / dy)   # px por "grau corrigido"

        def proj(lon, lat):
            return (round(MARGEM + (lon * fx - minx) * k, 1), round(ALTURA - MARGEM - 30 - (lat - miny) * k, 1))

        for anel in aneis:
            pts = " ".join(f"{x},{y}" for x, y in (proj(*c) for c in anel))
            partes.append(f'<polygon class="area" points="{pts}"/>')
        for p in pontos:
            x, y = proj(p["longitude"], p["latitude"])
            cod = escape(p["codigo"])
            sel = p["codigo"] == selecionado
            forma = (f'<rect class="ponto-sel" x="{x - 9}" y="{y - 9}" width="18" height="18" transform="rotate(45 {x} {y})"/>'
                     if sel else f'<circle class="ponto" cx="{x}" cy="{y}" r="8"/>')
            partes.append(f'<a href="?ponto={cod}#ponto-{cod}" aria-label="Ponto {cod}{" (selecionado)" if sel else ""}">'
                          f'<circle class="alvo" cx="{x}" cy="{y}" r="34" fill="transparent"/>'   # área de toque (≥ 44 px a 360 px)
                          f'{forma}<text x="{x + 12}" y="{y - 10}">{cod}</text></a>')
        metros_por_px = METROS_POR_GRAU / k
        alvo = _valor_redondo(metros_por_px * (LARGURA - 2 * MARGEM) / 4)
        if alvo:
            comp = alvo / metros_por_px
            y = ALTURA - 18
            rotulo = f"{alvo / 1000:g} km" if alvo >= 1000 else f"{alvo:g} m"
            partes.append(f'<line class="escala" x1="{MARGEM}" y1="{y}" x2="{round(MARGEM + comp, 1)}" y2="{y}"/>'
                          f'<text x="{round(MARGEM + comp + 8, 1)}" y="{y + 4}">{rotulo} (aprox.)</text>')
            info = {"metros": alvo, "rotulo": rotulo}
    partes.append("</svg>")
    return Markup("".join(partes)), info
