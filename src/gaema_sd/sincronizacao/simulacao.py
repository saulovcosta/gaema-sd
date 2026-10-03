"""Simulação local do aparelho de campo e da central, com dados SINTÉTICOS (sem rede, sem ArcGIS).

Mostra o ciclo completo: coleta offline → envio → alteração concorrente → conflito → decisão do coordenador →
o aparelho recebe a decisão e as versões voltam a convergir. Uso: python -m gaema_sd.sincronizacao simular PASTA
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

from ..acesso.politica import Ator
from ..dominio import entidades as E
from ..dominio.enums import Estado, Papel
from ..nucleo import Nucleo
from ..persistencia.sqlite import Repositorio
from ..sinteticos import cenario
from .canal import CanalSimulado
from .dispositivo import Dispositivo
from .sincronizador import Sincronizador

ATORES = {
    "analista": Ator.de("usuario-sintetico-10", Papel.ANALISTA_TRIAGEM),
    "coord": Ator.de("usuario-sintetico-03", Papel.COORDENADOR),
    "tecnico": Ator.de("usuario-sintetico-02", Papel.TECNICO_CAMPO),
    "membro": Ator.de("usuario-sintetico-05", Papel.MEMBRO_MP),
    "sistema": Ator.de("processo-sintetico", Papel.SISTEMA),
}


def executar(pasta: Path, *, verbose: bool = True) -> dict:
    log = print if verbose else (lambda *a: None)
    a, c = ATORES, cenario()
    central = Nucleo(Repositorio(str(pasta / "central.db")), pasta / "central")
    for ator, chave in [("analista", "FonteDado"), ("analista", "AreaCandidata"), ("analista", "Alerta"),
                        ("analista", "AreaInteresse"), ("coord", "Equipe"), ("coord", "VersaoProtocolo"),
                        ("coord", "Demanda")]:
        central.registrar(a[ator], c[chave][0])
    d = c["Demanda"][0].id
    for ator, destino, motivo in [("sistema", Estado.ALERTA, ""), ("analista", Estado.EM_TRIAGEM, ""),
                                  ("membro", Estado.DEMANDA_ABERTA, "Abertura de averiguação (simulação)."),
                                  ("coord", Estado.ATRIBUIDA, "")]:
        central.transitar(a[ator], d, destino, motivo=motivo)
    central.registrar(a["coord"], c["CampanhaVistoria"][0])
    central.transitar(a["coord"], d, Estado.PLANEJADA)
    central.transitar(a["tecnico"], d, Estado.EM_CAMPO)
    log("Central pronta: demanda sintética em campo.")

    aparelho = Dispositivo(Nucleo(Repositorio(str(pasta / "aparelho.db")), pasta / "aparelho", modo="dispositivo"),
                           a["tecnico"])
    canal = CanalSimulado(central, a["tecnico"])
    sinc = Sincronizador(aparelho, canal, tentativas_maximas=3, espera_inicial_s=0.0, esperar=lambda s: None)

    aparelho.coletar(c["PontoAmostral"][0])
    obs = aparelho.coletar(c["Observacao"][0])
    r1 = sinc.rodada()
    log(f"1. Aparelho coletou sem rede e enviou: {r1.envio.enviados} registros aplicados na central.")

    na_central = central.repo.listar(E.Observacao)[0]
    central.atualizar(a["tecnico"], dataclasses.replace(na_central, valor_bruto="50", valor_normalizado=50.0),
                      na_central.versao)
    aparelho.corrigir(dataclasses.replace(obs, valor_bruto="30", valor_normalizado=30.0), obs.versao)
    r2 = sinc.rodada()
    log(f"2. Central e aparelho alteraram o mesmo registro: {r2.envio.conflitos} conflito aberto; nada foi sobrescrito.")

    cid = central.repo.con.execute("SELECT id FROM conflitos_sincronizacao WHERE situacao='ABERTO'").fetchone()[0]
    central.resolver_conflito_sincronizacao(a["coord"], cid, "MANTER_CENTRAL",
                                            "Valor da central conferido pela coordenação (simulação).")
    log("3. O coordenador decidiu: manter a versão da central.")
    r3 = sinc.rodada()
    log(f"4. Aparelho consultou a central: {r3.reconciliacao.aplicadas} decisão aplicada.")

    local = aparelho.nucleo.repo.listar(E.Observacao)[0]
    remoto = central.repo.listar(E.Observacao)[0]
    convergiu = local.valor_bruto == remoto.valor_bruto
    log(f"5. Valores: aparelho={local.valor_bruto} central={remoto.valor_bruto} → "
        f"{'convergiram' if convergiu else 'DIVERGEM'}.")
    resultado = {"conflitos_abertos_antes": r2.envio.conflitos, "decisoes_aplicadas": r3.reconciliacao.aplicadas,
                 "convergiu": convergiu, "valor": remoto.valor_bruto,
                 "auditoria_central": central.trilha.verificar()}
    central.repo.fechar()
    aparelho.nucleo.repo.fechar()
    return resultado


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] != "simular":
        print("Uso: python -m gaema_sd.sincronizacao simular PASTA_NOVA  (dados sintéticos, rede simulada)")
        return 2
    pasta = Path(argv[2])
    pasta.mkdir(parents=True, exist_ok=True)
    if any(pasta.iterdir()):
        print(f"A pasta {pasta} não está vazia; use uma pasta nova.")
        return 2
    r = executar(pasta)
    print("Resultado: OK" if r["convergiu"] and r["decisoes_aplicadas"] == 1 else "Resultado: FALHOU")
    return 0 if r["convergiu"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
