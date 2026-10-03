"""Canal simulado entre dispositivo e central, com falhas determinísticas.

`falhas` é consumida uma por chamada de `enviar`; None = sem falha. Falhas possíveis:
- PERDA_ANTES: a requisição se perde; a central não recebe nada.
- INDISPONIVEL: serviço da central fora do ar; a central não recebe nada.
- PERDA_DEPOIS: a central aplica, mas a confirmação se perde (o dispositivo não sabe).
- INTERROMPER_ANTES / INTERROMPER_DEPOIS: o processo do dispositivo morre antes / depois da central aplicar.
Simulação local: não há rede, servidor nem ArcGIS/MPTO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Iterable, Optional

from ..acesso.politica import Ator
if TYPE_CHECKING:
    from ..nucleo import Nucleo

from .item import (
    DecisaoConflito,
    ErroRede,
    InterrupcaoSimulada,
    ItemSincronizacao,
    ResultadoSincronizacao,
    ServicoIndisponivel,
)

FALHAS = {"PERDA_ANTES", "INDISPONIVEL", "PERDA_DEPOIS", "INTERROMPER_ANTES", "INTERROMPER_DEPOIS"}


class CanalSimulado:
    def __init__(self, central: Nucleo, ator: Ator, falhas: Iterable[Optional[str]] = ()):
        self.central = central
        self.ator = ator
        self._falhas = list(falhas)
        for f in self._falhas:
            if f is not None and f not in FALHAS:
                raise ValueError(f"falha simulada desconhecida: {f}")
        self.chamadas = 0
        self.entregues = 0   # vezes em que a central realmente recebeu o item

    def programar(self, *falhas: Optional[str]) -> None:
        self._falhas.extend(falhas)

    def consultar_decisoes(self, consultas: list[tuple[str, str]]) -> list[DecisaoConflito]:
        """Pergunta à central o desfecho de conflitos. Usa a mesma lista de falhas simuladas de `enviar`."""
        self.chamadas += 1
        falha = self._falhas.pop(0) if self._falhas else None
        if falha in ("PERDA_ANTES", "INDISPONIVEL", "INTERROMPER_ANTES"):
            self._levantar(falha)
        resposta = self.central.consultar_decisoes_conflito(self.ator, consultas)
        if falha in ("PERDA_DEPOIS", "INTERROMPER_DEPOIS"):
            self._levantar(falha)
        return resposta

    @staticmethod
    def _levantar(falha: str) -> None:
        if falha == "PERDA_ANTES":
            raise ErroRede("requisição perdida (simulação)")
        if falha == "INDISPONIVEL":
            raise ServicoIndisponivel("serviço da central indisponível (simulação)")
        if falha == "PERDA_DEPOIS":
            raise ErroRede("confirmação perdida (simulação)")
        raise InterrupcaoSimulada(f"processo do dispositivo interrompido ({falha}, simulação)")

    def enviar(self, item: ItemSincronizacao, conteudo: bytes | None = None) -> ResultadoSincronizacao:
        self.chamadas += 1
        falha = self._falhas.pop(0) if self._falhas else None
        if falha == "PERDA_ANTES":
            raise ErroRede("requisição perdida (simulação)")
        if falha == "INDISPONIVEL":
            raise ServicoIndisponivel("serviço da central indisponível (simulação)")
        if falha == "INTERROMPER_ANTES":
            raise InterrupcaoSimulada("processo do dispositivo interrompido antes do envio (simulação)")
        self.entregues += 1
        resultado = self.central.receber_sincronizacao(self.ator, item, conteudo)
        if falha == "PERDA_DEPOIS":
            raise ErroRede("confirmação perdida (simulação)")
        if falha == "INTERROMPER_DEPOIS":
            raise InterrupcaoSimulada("processo do dispositivo interrompido após o envio (simulação)")
        return resultado
