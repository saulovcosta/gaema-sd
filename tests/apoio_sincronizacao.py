"""Montagem comum dos testes de sincronização: uma central e um dispositivo, cada um com SQLite próprio."""

import dataclasses

from gaema_sd.dominio.enums import Estado
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio
from gaema_sd.sincronizacao import CanalSimulado, Dispositivo, Sincronizador
from gaema_sd.sinteticos import FOTO_SINTETICA

S = Estado


def preparar_central(central, a, c):
    """Leva a demanda sintética até EM_CAMPO na central (campanha já planejada)."""
    for ator, chave in [("analista", "FonteDado"), ("analista", "AreaCandidata"), ("analista", "Alerta"),
                        ("analista", "AreaInteresse"), ("coord", "Equipe"), ("coord", "VersaoProtocolo"),
                        ("coord", "Demanda")]:
        central.registrar(a[ator], c[chave][0])
    d = c["Demanda"][0].id
    t = central.transitar
    t(a["sistema"], d, S.ALERTA)
    t(a["analista"], d, S.EM_TRIAGEM)
    t(a["membro"], d, S.DEMANDA_ABERTA, motivo="abertura para averiguação sintética")
    t(a["coord"], d, S.ATRIBUIDA)
    central.registrar(a["coord"], c["CampanhaVistoria"][0])
    t(a["coord"], d, S.PLANEJADA)
    t(a["tecnico"], d, S.EM_CAMPO)
    return d


class Ambiente:
    """Central + dispositivo + canal. `esperas` guarda as esperas pedidas (sem dormir de verdade)."""

    def __init__(self, tmp_path, atores, cenario, *, banco_dispositivo=":memory:", falhas=()):
        self.a, self.c = atores, cenario
        self.tmp = tmp_path
        self.central = Nucleo(Repositorio(":memory:"), tmp_path / "central")
        self.demanda_id = preparar_central(self.central, atores, cenario)
        self.banco_dispositivo = banco_dispositivo
        self.canal = CanalSimulado(self.central, atores["tecnico"], falhas)
        self.esperas: list[float] = []
        self.abrir_dispositivo()

    def abrir_dispositivo(self):
        self.repo_disp = Repositorio(self.banco_dispositivo)
        self.disp = Dispositivo(Nucleo(self.repo_disp, self.tmp / "dispositivo"), self.a["tecnico"])
        self.sinc = Sincronizador(self.disp, self.canal, tentativas_maximas=3, espera_inicial_s=2.0,
                                  esperar=self.esperas.append)

    def reiniciar_dispositivo(self):
        """Simula fechar o aplicativo e abri-lo de novo sobre o mesmo arquivo."""
        self.repo_disp.fechar()
        self.abrir_dispositivo()

    def coletar_tudo(self):
        c = self.c
        self.disp.coletar(c["PontoAmostral"][0])
        self.disp.coletar(c["Observacao"][0])
        self.disp.coletar(c["MedicaoPenetracao"][0])
        self.disp.coletar(c["Evidencia"][0], FOTO_SINTETICA)

    def na_central(self, cls):
        return self.central.repo.listar(cls)


def acoes(nucleo):
    return [e.acao for e in nucleo.trilha.eventos]


def com(obj, **campos):
    return dataclasses.replace(obj, **campos)
