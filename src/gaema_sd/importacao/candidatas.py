"""Leitura de áreas candidatas de um arquivo de texto (GeoJSON FeatureCollection ou CSV com WKT).

Função pura: devolve um item por linha/feição, com os problemas encontrados. Não grava nada; quem grava é
`Nucleo.importar_candidatas`. Não há processamento de imagem, índice de vegetação (NDVI) nem triagem por satélite:
a área, a data, a origem e a incerteza são **declaradas** por quem preparou o arquivo.

Colunas (CSV) ou propriedades (GeoJSON): `data_deteccao` (AAAA-MM-DD), `origem_declarada` (obrigatória), `incerteza`
(texto descritivo, opcional), `fonte` (nome da fonte declarada, opcional). No CSV a geometria vem em `geometria_wkt`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import date

from shapely import wkt as shapely_wkt
from shapely.errors import ShapelyError
from shapely.geometry import shape

from ..validacao.geometria import validar_poligono_wkt
from ..validacao.problemas import Problema, erro

FORMATOS = ("geojson", "csv")
COLUNAS_CSV = ("geometria_wkt", "data_deteccao", "origem_declarada", "incerteza", "fonte")
LIMITE_TEXTO = 300


@dataclass
class ItemImportado:
    numero: int                                   # posição no arquivo (1 = primeira feição ou linha de dados)
    geometria_wkt: str = ""
    data_deteccao: date | None = None
    origem_declarada: str = ""
    incerteza: str = ""
    fonte: str = ""
    chave: str = ""                               # hash da geometria normalizada (duplicidade)
    problemas: list[Problema] = field(default_factory=list)

    @property
    def aceito(self) -> bool:
        return not any(p.gravidade.value == "ERRO" for p in self.problemas)


def chave_geometria(texto_wkt: str) -> str:
    """Mesma área → mesma chave, independentemente da ordem dos vértices ou do anel inicial (shapely normalize).
    Coordenadas arredondadas a 7 casas (~1 cm), para não separar a mesma área por ruído de impressão."""
    g = shapely_wkt.loads(texto_wkt).normalize()
    return "geom:" + hashlib.sha256(shapely_wkt.dumps(g, rounding_precision=7).encode()).hexdigest()[:32]


def _texto(v) -> str:
    return str(v if v is not None else "").strip()[:LIMITE_TEXTO]


def _completar(item: ItemImportado, dados: dict, hoje: date) -> ItemImportado:
    item.origem_declarada = _texto(dados.get("origem_declarada"))
    item.incerteza = _texto(dados.get("incerteza"))
    item.fonte = _texto(dados.get("fonte"))[:120]
    if not item.origem_declarada:
        item.problemas.append(erro("ORIGEM_AUSENTE", "origem_declarada", "informe a origem declarada da área"))
    bruto = _texto(dados.get("data_deteccao"))
    try:
        item.data_deteccao = date.fromisoformat(bruto)
        if item.data_deteccao > hoje:
            item.problemas.append(erro("DATA_FUTURA", "data_deteccao", "data de detecção no futuro"))
    except ValueError:
        item.problemas.append(erro("DATA_INVALIDA", "data_deteccao", "data ausente ou fora do formato AAAA-MM-DD"))
    if item.geometria_wkt:
        problemas = validar_poligono_wkt(item.geometria_wkt)
        item.problemas += problemas
        if not any(p.gravidade.value == "ERRO" for p in problemas):
            item.chave = chave_geometria(item.geometria_wkt)
    return item


def _geojson(texto: str, hoje: date) -> list[ItemImportado]:
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"GeoJSON ilegível (linha {e.lineno})") from None
    if not isinstance(dados, dict) or dados.get("type") != "FeatureCollection" or not isinstance(dados.get("features"), list):
        raise ValueError("o GeoJSON precisa ser uma FeatureCollection")
    itens = []
    for i, f in enumerate(dados["features"], 1):
        item = ItemImportado(numero=i)
        geom = f.get("geometry") if isinstance(f, dict) else None
        props = f.get("properties") if isinstance(f, dict) and isinstance(f.get("properties"), dict) else {}
        if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
            item.problemas.append(erro("GEOM_TIPO", "geometry", "cada feição precisa de um Polygon ou MultiPolygon"))
        else:
            try:
                item.geometria_wkt = shape(geom).wkt
            except (ShapelyError, ValueError, TypeError, KeyError, IndexError, AttributeError):
                item.problemas.append(erro("GEOM_ILEGIVEL", "geometry", "coordenadas da feição ilegíveis"))
        itens.append(_completar(item, props, hoje))
    return itens


def _csv(texto: str, hoje: date) -> list[ItemImportado]:
    leitor = csv.DictReader(io.StringIO(texto))
    faltam = [c for c in ("geometria_wkt", "data_deteccao", "origem_declarada") if c not in (leitor.fieldnames or [])]
    if faltam:
        raise ValueError("faltam colunas no CSV: " + ", ".join(faltam))
    itens = []
    for i, linha in enumerate(leitor, 1):
        item = ItemImportado(numero=i, geometria_wkt=_texto(linha.get("geometria_wkt")) if len(
            linha.get("geometria_wkt") or "") <= 20000 else "")
        if not item.geometria_wkt:
            item.problemas.append(erro("GEOM_AUSENTE", "geometria_wkt", "geometria ausente ou longa demais"))
        else:
            try:
                shapely_wkt.loads(item.geometria_wkt)
            except (ShapelyError, ValueError, TypeError):
                item.problemas.append(erro("GEOM_ILEGIVEL", "geometria_wkt", "WKT ilegível"))
                item.geometria_wkt = ""
        itens.append(_completar(item, linha, hoje))
    return itens


def ler_candidatas(texto: str, formato: str, *, hoje: date | None = None, maximo_itens: int = 200) -> list[ItemImportado]:
    """Lê e confere cada item (geometria, data, origem) e marca duplicados dentro do próprio arquivo.
    Erro de estrutura (formato desconhecido, arquivo ilegível, itens demais) levanta ValueError."""
    if formato not in FORMATOS:
        raise ValueError(f"formato desconhecido; use {', '.join(FORMATOS)}")
    hoje = hoje or date.today()
    itens = (_geojson if formato == "geojson" else _csv)(texto, hoje)
    if not itens:
        raise ValueError("o arquivo não tem nenhuma área")
    if len(itens) > maximo_itens:
        raise ValueError(f"o arquivo tem {len(itens)} áreas; o máximo por importação é {maximo_itens}")
    vistos: dict[str, int] = {}
    for item in itens:
        if item.chave and item.aceito:
            if item.chave in vistos:
                item.problemas.append(erro("DUPLICADA_NO_ARQUIVO", "geometria_wkt",
                                           f"mesma área do item {vistos[item.chave]} deste arquivo"))
            else:
                vistos[item.chave] = item.numero
    return itens
