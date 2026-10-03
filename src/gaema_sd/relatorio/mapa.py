"""Mapa esquemático (SVG) da área e dos pontos, sem serviço externo. Sem escala cartográfica."""

from __future__ import annotations

from html import escape

from shapely import wkt as shapely_wkt
from shapely.errors import ShapelyError

LARGURA, ALTURA, MARGEM = 640, 420, 28


def projecao(geometria_wkt: str, pontos: list[dict]):
    """Função lon/lat → x/y (linear, ajustada à extensão). Devolve (projetar, aneis)."""
    aneis = []
    xs, ys = [], []
    if geometria_wkt:
        try:
            g = shapely_wkt.loads(geometria_wkt)
            polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
            aneis = [list(p.exterior.coords) for p in polys]
        except (ShapelyError, ValueError, AttributeError):
            aneis = []
    for anel in aneis:
        xs += [c[0] for c in anel]
        ys += [c[1] for c in anel]
    xs += [p["longitude"] for p in pontos]
    ys += [p["latitude"] for p in pontos]
    if not xs:
        return None, []
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    dx, dy = (maxx - minx) or 1e-4, (maxy - miny) or 1e-4
    escala = min((LARGURA - 2 * MARGEM) / dx, (ALTURA - 2 * MARGEM) / dy)
    folga_x = (LARGURA - 2 * MARGEM - dx * escala) / 2     # centraliza o desenho na moldura
    folga_y = (ALTURA - 2 * MARGEM - dy * escala) / 2

    def projetar(lon: float, lat: float) -> tuple[float, float]:
        return (round(MARGEM + folga_x + (lon - minx) * escala, 2),
                round(ALTURA - MARGEM - folga_y - (lat - miny) * escala, 2))

    return projetar, aneis


def svg(geometria_wkt: str, pontos: list[dict], titulo: str) -> str:
    projetar, aneis = projecao(geometria_wkt, pontos)
    descricao = (f"Esquema da área de interesse com {len(pontos)} ponto(s) amostral(is): "
                 + ", ".join(f"{p['codigo']} ({p['latitude']:.5f}, {p['longitude']:.5f})" for p in pontos)
                 + ". Sem escala cartográfica; coordenadas em WGS84.")
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGURA} {ALTURA}" role="img" '
              f'aria-labelledby="mapa-titulo mapa-desc" width="{LARGURA}" height="{ALTURA}">',
              f'<title id="mapa-titulo">{escape(titulo)}</title>',
              f'<desc id="mapa-desc">{escape(descricao)}</desc>',
              f'<rect x="0" y="0" width="{LARGURA}" height="{ALTURA}" fill="#ffffff" stroke="#555555"/>']
    if projetar:
        for anel in aneis:
            pts = " ".join(f"{x},{y}" for x, y in (projetar(*c[:2]) for c in anel))
            partes.append(f'<polygon points="{pts}" fill="#e8f0e0" stroke="#2f5d1e" stroke-width="2"/>')
        for p in pontos:
            x, y = projetar(p["longitude"], p["latitude"])
            partes.append(f'<circle cx="{x}" cy="{y}" r="6" fill="#8a1c1c"/>')
            partes.append(f'<text x="{x + 8}" y="{y - 6}" font-size="14" font-family="sans-serif" '
                          f'fill="#111111">{escape(p["codigo"])}</text>')
    partes.append(f'<text x="{MARGEM}" y="{ALTURA - 6}" font-size="12" font-family="sans-serif" fill="#333333">'
                  'Esquema sem escala; norte para cima</text>')
    partes.append("</svg>")
    return "".join(partes)
