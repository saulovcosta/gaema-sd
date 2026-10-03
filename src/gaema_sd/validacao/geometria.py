"""Validação geoespacial. Coordenadas em WGS84 (EPSG:4326), ordem lon/lat no WKT."""

from __future__ import annotations

import math

from shapely import wkt as shapely_wkt
from shapely.errors import ShapelyError
from shapely.validation import explain_validity

from .. import config
from .problemas import Problema, alerta, erro


def _dentro_recorte(lon: float, lat: float) -> bool:
    r = config.parametro("recorte_aproximado_tocantins")
    return r["lon_min"] <= lon <= r["lon_max"] and r["lat_min"] <= lat <= r["lat_max"]


def validar_coordenada(lat, lon, campo: str = "coordenada") -> list[Problema]:
    if lat is None or lon is None:
        return [erro("COORD_AUSENTE", campo, "latitude e longitude são obrigatórias")]
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return [erro("COORD_NAO_NUMERICA", campo, "latitude/longitude não numéricas")]
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return [erro("COORD_NAO_FINITA", campo, "latitude/longitude não finitas")]
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return [erro("COORD_FORA_WGS84", campo, f"fora da faixa WGS84 (lat={lat}, lon={lon})")]
    if lat == 0 and lon == 0:
        return [erro("COORD_ZERO", campo, "coordenada 0,0 indica GPS sem posição")]
    if not _dentro_recorte(lon, lat):
        return [alerta("COORD_FORA_RECORTE", campo,
                       "ponto fora do recorte aproximado do Tocantins; conferir")]
    return []


def validar_poligono_wkt(texto: str, campo: str = "geometria_wkt") -> list[Problema]:
    if not texto or not texto.strip():
        return [erro("GEOM_AUSENTE", campo, "geometria obrigatória")]
    try:
        g = shapely_wkt.loads(texto)
    except (ShapelyError, ValueError, TypeError) as e:
        return [erro("GEOM_ILEGIVEL", campo, f"WKT ilegível: {e}")]
    if g.geom_type not in ("Polygon", "MultiPolygon"):
        return [erro("GEOM_TIPO", campo, f"esperado polígono, recebido {g.geom_type}")]
    if g.is_empty:
        return [erro("GEOM_VAZIA", campo, "geometria vazia")]
    if g.has_z:
        return [erro("GEOM_3D", campo, "use coordenadas 2D (lon lat)")]
    problemas: list[Problema] = []
    minx, miny, maxx, maxy = g.bounds
    if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
        return [erro("GEOM_FORA_WGS84", campo, "coordenadas fora da faixa WGS84 (lon lat)")]
    if not g.is_valid:
        problemas.append(erro("GEOM_INVALIDA", campo, f"geometria inválida: {explain_validity(g)}"))
    elif g.area == 0:
        problemas.append(erro("GEOM_AREA_ZERO", campo, "polígono sem área"))
    c = g.representative_point() if g.is_valid else g.envelope.centroid
    if not _dentro_recorte(c.x, c.y):
        problemas.append(alerta("GEOM_FORA_RECORTE", campo,
                                "área fora do recorte aproximado do Tocantins; conferir"))
    return problemas
