#!/usr/bin/env python3
"""Regenera schemas/*.schema.json, docs/estados.md, docs/dominio.md, fixtures sintéticas e o XLSForm (CSV) a partir do código."""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from gaema_sd.adaptadores.xlsform import arquivos_csv  # noqa: E402
from gaema_sd.contratos import todos  # noqa: E402
from gaema_sd.dominio.documento import gerar_markdown as gerar_dominio  # noqa: E402
from gaema_sd.estados.documento import gerar_markdown  # noqa: E402
from gaema_sd.exportacao import esquema_json as esquema_exportacao  # noqa: E402
from gaema_sd.sinteticos import cenario, cenario_json  # noqa: E402


def conteudos() -> dict[Path, str]:
    saida = {RAIZ / "schemas" / f"{nome}.schema.json": json.dumps(s, ensure_ascii=False, indent=2) + "\n"
             for nome, s in todos().items()}
    saida[RAIZ / "schemas" / "exportacao-painel.schema.json"] = json.dumps(
        esquema_exportacao(), ensure_ascii=False, indent=2) + "\n"
    saida[RAIZ / "docs" / "estados.md"] = gerar_markdown()
    saida[RAIZ / "docs" / "dominio.md"] = gerar_dominio(cenario())
    saida[RAIZ / "fixtures" / "sinteticos" / "cenario_basico.json"] = cenario_json()
    for nome, texto in arquivos_csv().items():
        saida[RAIZ / "adapters" / "arcgis" / "xlsform" / nome] = texto
    return saida


if __name__ == "__main__":
    for caminho, texto in conteudos().items():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8", newline="")
        print("gerado:", caminho.relative_to(RAIZ))
