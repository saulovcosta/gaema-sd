"""Aparelho de campo SIMULADO para a interface: núcleo em modo dispositivo, fila, rede simulada e rascunho da coleta.

Só apresentação/uso: grava pelos caminhos que já existem (`Dispositivo.coletar`, `Sincronizador.rodada`). Nada de GPS
real, foto ou rede real. O rascunho fica num arquivo JSON neste aparelho (salvo a cada etapa).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..acesso.politica import Ator
from ..nucleo import Nucleo
from ..persistencia.sqlite import Repositorio
from ..sincronizacao import CanalSimulado, Dispositivo, Sincronizador

DISPOSITIVO_ID = "aparelho-simulado"


@dataclass
class Campo:
    dispositivo: Dispositivo
    sincronizador: Sincronizador
    canal: CanalSimulado
    pasta: Path
    ultima: str | None = None
    ultimo_resultado: str = ""
    _repo: Repositorio | None = field(default=None, repr=False)

    @staticmethod
    def criar(pasta: Path, central: Nucleo, tecnico: Ator) -> "Campo":
        pasta.mkdir(parents=True, exist_ok=True)
        repo = Repositorio(str(pasta / "aparelho.db"))
        disp = Dispositivo(Nucleo(repo, pasta, modo="dispositivo"), tecnico)
        canal = CanalSimulado(central, tecnico)
        sinc = Sincronizador(disp, canal, tentativas_maximas=2, espera_inicial_s=0.0, esperar=lambda s: None)
        return Campo(disp, sinc, canal, pasta, _repo=repo)

    def fechar(self) -> None:
        if self._repo:
            self._repo.fechar()

    # ---- situação para a barra permanente
    def status(self) -> dict:
        cont = self.dispositivo.fila.contagem()
        return {"conectado": not self.canal.fora_do_ar, "pendentes": cont["PENDENTE"],
                "problemas": cont["CONFLITO"] + cont["REJEITADO"], "ultima": self.ultima}

    # ---- rascunho (salvo a cada etapa, neste aparelho)
    @property
    def _arq(self) -> Path:
        return self.pasta / "rascunho-coleta.json"

    def rascunho(self) -> dict | None:
        try:
            return json.loads(self._arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def salvar_rascunho(self, r: dict) -> None:
        tmp = self._arq.with_suffix(".parcial")
        tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._arq)

    def descartar_rascunho(self) -> None:
        self._arq.unlink(missing_ok=True)

    @staticmethod
    def rascunho_novo() -> dict:
        return {"etapa": 1, "max_etapa": 1, "missao": "", "codigo": "", "latitude": "", "longitude": "", "precisao": "",
                "capturado_em": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M"), "presenca": {}, "hipotese": "",
                "medicoes": [], "ultima_unidade_p": "cm", "ultima_unidade_r": "kpa", "ultima_umidade": ""}
