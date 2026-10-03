"""Interfaces dos adaptadores e implementações "não configurado".

Regras (adapters/arcgis/README.md): o adaptador só traduz; regra de negócio, acesso e auditoria ficam no
núcleo. Dados de campo entram por `Nucleo.receber_sincronizacao`, que compara versões e nunca deixa
"a última edição vence" (FC-12) apagar edição concorrente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Protocol, Sequence, runtime_checkable

from ..dominio.entidades import CruzamentoTerritorial
from ..erros import ErroGaema

MOTIVO = ("não há organização ArcGIS, Client ID nem serviço acessível (lacuna LA-05); "
          "este adaptador é apenas interface")


class AmbienteIndisponivel(ErroGaema):
    """O adaptador real não existe nesta fase."""


@dataclass(frozen=True)
class CamadaExterna:
    """Camada de referência (ex.: limites, uso do solo). Só entra o que for autorizado (LA-07, LA-09)."""
    id: str
    nome: str
    autorizada: bool = False   # autorização de uso é decisão institucional, nunca presumida


Submissao = dict[str, Any]     # formato neutro do GAEMA SD (ver traducao.py); o formato real do Survey123 NÃO foi verificado


@runtime_checkable
class CatalogoCamadas(Protocol):
    """Somente leitura."""
    def listar_camadas(self) -> Sequence[CamadaExterna]: ...
    def consultar_sobreposicao(self, geometria_wkt: str, camada_id: str) -> Sequence[CruzamentoTerritorial]: ...


@runtime_checkable
class ImportadorCampo(Protocol):
    """Traz submissões de campo já traduzidas para o formato neutro; quem grava é o núcleo."""
    def baixar_submissoes(self, desde: datetime | None = None) -> Iterable[Submissao]: ...


@runtime_checkable
class PublicadorCampo(Protocol):
    """Leva o formulário e a missão (pacote offline) ao ambiente de campo."""
    def publicar_formulario(self, caminho_xlsx: str) -> str: ...
    def publicar_missao(self, campanha_id: str) -> str: ...


class NaoConfiguradoCatalogo:
    def listar_camadas(self) -> Sequence[CamadaExterna]:
        raise AmbienteIndisponivel(MOTIVO)

    def consultar_sobreposicao(self, geometria_wkt: str, camada_id: str) -> Sequence[CruzamentoTerritorial]:
        raise AmbienteIndisponivel(MOTIVO)


class NaoConfiguradoImportador:
    def baixar_submissoes(self, desde: datetime | None = None) -> Iterable[Submissao]:
        raise AmbienteIndisponivel(MOTIVO)


class NaoConfiguradoPublicador:
    def publicar_formulario(self, caminho_xlsx: str) -> str:
        raise AmbienteIndisponivel(MOTIVO)

    def publicar_missao(self, campanha_id: str) -> str:
        raise AmbienteIndisponivel(MOTIVO)
