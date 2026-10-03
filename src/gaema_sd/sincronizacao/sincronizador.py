"""Esvazia a fila do dispositivo em ordem, com reenvio, espera crescente e retomada.

Regras:
- ordem preservada: se um item não é confirmado após as tentativas, a rodada para ali;
- item recusado pela central (acesso, validação, anexo) fica REJEITADO e a fila segue;
- conflito fica CONFLITO (a central guardou as duas versões) e a fila segue;
- nada é descartado: o que não foi confirmado continua PENDENTE na próxima rodada.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from ..config import parametro
from ..erros import ErroGaema
from .canal import CanalSimulado
from .dispositivo import Dispositivo
from .item import ErroTransporte, ResultadoSincronizacao

log = logging.getLogger("gaema_sd.sincronizacao")


@dataclass
class ResumoSincronizacao:
    enviados: int = 0
    reenvios_idempotentes: int = 0
    conflitos: int = 0
    rejeitados: int = 0
    pendentes_restantes: int = 0
    interrompido: bool = False
    motivo_interrupcao: str = ""


class Sincronizador:
    def __init__(self, dispositivo: Dispositivo, canal: CanalSimulado, *, tentativas_maximas: int | None = None,
                 espera_inicial_s: float | None = None, esperar: Callable[[float], None] = time.sleep):
        self.disp = dispositivo
        self.canal = canal
        self.tentativas_maximas = tentativas_maximas or parametro("sincronizacao_tentativas_maximas")
        self.espera_inicial_s = espera_inicial_s if espera_inicial_s is not None \
            else parametro("sincronizacao_espera_inicial_s")
        self.esperar = esperar

    def executar(self) -> ResumoSincronizacao:
        resumo = ResumoSincronizacao()
        self.disp.recuperar_nao_enfileirados()
        for seq, item, _ in self.disp.fila.pendentes():
            if not self._enviar_com_reenvio(seq, item, resumo):
                resumo.interrompido = True
                break
        resumo.pendentes_restantes = self.disp.fila.contagem()["PENDENTE"]
        log.info("rodada de sincronização: enviados=%d idempotentes=%d conflitos=%d rejeitados=%d pendentes=%d",
                 resumo.enviados, resumo.reenvios_idempotentes, resumo.conflitos, resumo.rejeitados,
                 resumo.pendentes_restantes)
        return resumo

    def _enviar_com_reenvio(self, seq, item, resumo: ResumoSincronizacao) -> bool:
        conteudo = None
        if item.tipo == "Evidencia":
            conteudo = self.disp.conteudo_evidencia(item.dados["sha256"])
        for tentativa in range(1, self.tentativas_maximas + 1):
            self.disp.fila.registrar_tentativa(seq)
            try:
                resultado = self.canal.enviar(item, conteudo)
            except ErroTransporte as e:
                log.warning("falha de transporte no item %s (tentativa %d): %s", seq, tentativa, type(e).__name__)
                if tentativa < self.tentativas_maximas:
                    self.esperar(self.espera_inicial_s * 2 ** (tentativa - 1))
                    continue
                resumo.motivo_interrupcao = f"{type(e).__name__} após {tentativa} tentativas"
                return False
            except ErroGaema as e:
                self.disp.fila.marcar(seq, "REJEITADO", erro=f"{type(e).__name__}: {e}")
                resumo.rejeitados += 1
                log.warning("item %s rejeitado pela central: %s", seq, type(e).__name__)
                return True
            if resultado is ResultadoSincronizacao.CONFLITO:
                self.disp.fila.marcar(seq, "CONFLITO", resultado=resultado.value)
                resumo.conflitos += 1
            else:
                self.disp.fila.marcar(seq, "ENVIADO", resultado=resultado.value)
                if resultado is ResultadoSincronizacao.APLICADO:
                    resumo.enviados += 1
                else:
                    resumo.reenvios_idempotentes += 1
            return True
        return False
