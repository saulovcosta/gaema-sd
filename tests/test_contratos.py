"""Contrato: esquemas, documento de estados e fixtures gerados conferem com o código."""

import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from gaema_sd.contratos import todos

RAIZ = Path(__file__).resolve().parents[1]


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar", RAIZ / "scripts" / "gerar_contratos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_arquivos_gerados_estao_atualizados():
    for caminho, esperado in _gerador().conteudos().items():
        assert caminho.read_text(encoding="utf-8") == esperado, (
            f"{caminho.relative_to(RAIZ)} desatualizado: rode scripts/gerar_contratos.py")


def test_esquemas_sao_validos():
    for nome, s in todos().items():
        jsonschema.Draft202012Validator.check_schema(s)


def test_fixtures_obedecem_aos_esquemas():
    dados = json.loads((RAIZ / "fixtures" / "sinteticos" / "cenario_basico.json").read_text(encoding="utf-8"))
    esquemas = todos()
    total = 0
    for nome, registros in dados.items():
        if nome.startswith("_"):
            continue
        validador = jsonschema.Draft202012Validator(esquemas[nome], format_checker=jsonschema.FormatChecker())
        for r in registros:
            validador.validate(r)
            total += 1
    assert total == 12


def test_esquema_recusa_campo_extra_e_enum_invalido():
    s = todos()["Demanda"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"titulo": "x", "responsavel_legal": "y"}, s)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"titulo": "x", "estado": "CONDENADA"}, s)


def test_dominio_documenta_as_20_entidades():
    from gaema_sd.dominio import entidades as E
    from gaema_sd.dominio.documento import TEXTOS

    assert set(TEXTOS) == set(E.POR_NOME)
    texto = (RAIZ / "docs" / "dominio.md").read_text(encoding="utf-8")
    for nome in E.POR_NOME:
        assert f"## {nome}\n" in texto
    for chave in ("Finalidade", "Sensibilidade", "Relações", "Validações", "Atualização", "Retenção",
                  "Exemplo sintético"):
        assert texto.count(f"**{chave}.**") == 20, chave
