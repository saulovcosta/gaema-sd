"""Logs de operação sem dado sensível.

O log leva identificadores, contagens e nomes de erro; nunca conteúdo de registro, texto livre de
usuário, coordenadas nem caminho de arquivo de evidência. O filtro abaixo é uma segunda barreira
(CPF, e-mail e pares `senha=...` são mascarados); não detecta nome de pessoa em texto livre.
"""

from __future__ import annotations

import logging

from .auditoria.trilha import sanear_texto

RAIZ = "gaema_sd"


class FiltroSanear(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        registro.msg = sanear_texto(registro.getMessage())
        registro.args = ()
        if registro.exc_info:  # traceback pode repetir valores; guarda só o tipo
            registro.msg += f" [{registro.exc_info[0].__name__}]"
            registro.exc_info = None
            registro.exc_text = None
        return True


def configurar_logs(nivel: int = logging.INFO, manipulador: logging.Handler | None = None) -> logging.Logger:
    """Instala o filtro no manipulador (padrão: console). Chamar uma vez na partida do aplicativo."""
    log = logging.getLogger(RAIZ)
    log.setLevel(nivel)
    manipulador = manipulador or logging.StreamHandler()
    manipulador.addFilter(FiltroSanear())
    if not any(isinstance(h, type(manipulador)) and any(isinstance(f, FiltroSanear) for f in h.filters)
               for h in log.handlers):
        log.addHandler(manipulador)
    return log
