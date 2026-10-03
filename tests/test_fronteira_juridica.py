"""O modelo não pode conter conclusões jurídicas nem confundir área com imóvel ou pessoa."""

import dataclasses
import re

from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import TipoProvidencia

PROIBIDO = re.compile(
    r"ilicit|culpa|dolo|nexo|responsabil|infrator|infracao|autoria|autor_|dano|sancao|multa|"
    r"proprietari|possuidor|ocupante|imovel|matricula|cpf|cnpj|nome_pessoa|condena|crime",
    re.IGNORECASE,
)


def _todos_os_campos():
    vistos = set()
    pilha = list(E.ENTIDADES) + [E.SinalRemoto, E.CruzamentoTerritorial, E.MembroEquipe]
    for cls in pilha:
        for f in dataclasses.fields(cls):
            vistos.add((cls.__name__, f.name))
    return vistos


def test_nenhum_campo_com_conclusao_juridica_ou_identificacao_de_pessoa():
    violacoes = [(c, f) for c, f in _todos_os_campos() if PROIBIDO.search(f)]
    assert violacoes == []


def test_providencias_sao_acoes_e_nao_conclusoes():
    for t in TipoProvidencia:
        assert not PROIBIDO.search(t.value)


def test_area_de_interesse_declara_que_nao_e_imovel():
    doc = " ".join(E.__doc__.lower().split())
    assert "não é imóvel" in doc and "não é cadastro territorial" in doc
    assert "indício" in E.CruzamentoTerritorial.__doc__.lower()


def test_rotulo_do_prototipo_e_exato():
    assert E.ROTULO_PROTOTIPO == "PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"
