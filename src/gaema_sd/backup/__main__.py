"""Uso: python -m gaema_sd.backup criar|verificar|restaurar ..."""

import argparse
import sys
from pathlib import Path

from ..persistencia.sqlite import Repositorio
from .backup import criar_backup, restaurar_backup, rollback, verificar_backup


def main() -> int:
    p = argparse.ArgumentParser(prog="python -m gaema_sd.backup")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("criar"); c.add_argument("banco"); c.add_argument("saida"); c.add_argument("destino")
    v = sub.add_parser("verificar"); v.add_argument("backup")
    r = sub.add_parser("restaurar"); r.add_argument("backup"); r.add_argument("banco_novo"); r.add_argument("saida_nova")
    b = sub.add_parser("rollback"); b.add_argument("backup"); b.add_argument("banco_atual"); b.add_argument("saida_atual")
    a = p.parse_args()
    if a.cmd == "criar":
        if not Path(a.banco).is_file():
            print(f"o banco {a.banco} não existe; nenhum backup foi criado")
            return 2
        repo = Repositorio(a.banco)
        m = criar_backup(repo, a.saida, a.destino)
        repo.fechar()
        print(f"backup criado: {len(m['arquivos'])} arquivos, {m['auditoria']['eventos']} eventos de auditoria")
    elif a.cmd == "verificar":
        problemas = verificar_backup(a.backup)
        print("backup confere" if not problemas else "PROBLEMAS:\n- " + "\n- ".join(problemas))
        return 1 if problemas else 0
    elif a.cmd == "restaurar":
        print(restaurar_backup(a.backup, a.banco_novo, a.saida_nova))
    else:
        print(f"estado anterior guardado em: {rollback(a.backup, a.banco_atual, a.saida_atual)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
