"""Uso: python -m gaema_sd.interface PASTA [--porta 8765] [--demo]

Abre a interface local em http://127.0.0.1:PORTA. Com --demo, cria na PASTA (nova) o cenário sintético de demonstração
antes de servir. Sem --demo, usa o banco `gaema-demo.db` que já estiver na PASTA. Só dados sintéticos.
"""

import argparse
import logging
import sys
from pathlib import Path

from .. import demo
from ..nucleo import Nucleo
from ..persistencia.sqlite import Repositorio
from . import USUARIOS_DE_TESTE, servir
from .campo import Campo
from .cenario import preparar_vistoria_em_campo


def main() -> int:
    p = argparse.ArgumentParser(prog="python -m gaema_sd.interface", description=__doc__)
    p.add_argument("pasta")
    p.add_argument("--porta", type=int, default=8765)
    p.add_argument("--demo", action="store_true", help="criar o cenário sintético de demonstração na pasta (precisa estar vazia)")
    a = p.parse_args()
    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    if a.demo:
        if any(pasta.iterdir()):
            print(f"A pasta {pasta} não está vazia; use uma pasta nova para o cenário de demonstração.")
            return 2
        demo.executar(pasta, verbose=False)
        repo_demo = Repositorio(str(pasta / "gaema-demo.db"))
        preparar_vistoria_em_campo(Nucleo(repo_demo, pasta))   # 2ª demanda, já em campo, para o aparelho simulado
        repo_demo.fechar()
    banco = pasta / "gaema-demo.db"
    if not banco.is_file():
        print(f"Não há banco em {pasta}. Use --demo numa pasta nova para criar o cenário sintético.")
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    repo = Repositorio(str(banco))
    central = Nucleo(repo, pasta)
    campo = Campo.criar(pasta / "aparelho-simulado", central, USUARIOS_DE_TESTE["tecnico"])
    servidor = servir(central, a.porta, campo=campo)
    print(f"Interface (PROTÓTIPO, dados sintéticos) em http://127.0.0.1:{a.porta}/  — Ctrl+C para encerrar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()
        campo.fechar()
        repo.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
